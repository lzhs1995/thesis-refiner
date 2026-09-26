import asyncio
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nlm_stream_wait import StreamDeadline, StreamDeadlineExpired, await_stream_operation


class DeadlineTests(unittest.TestCase):
    def test_first_data_notice_does_not_end_original_request(self):
        d = StreamDeadline(0)
        result = d.observe(300, {"chars": 0})
        self.assertEqual(result["notice"], "FIRST_DATA_NOTICE")
        self.assertFalse(result["abort"])
        self.assertFalse(result["remote_completion_inferred"])
        self.assertEqual(d.remaining(300, {"chars": 0}), 600)

    def test_original_180second_idle_is_a_notice(self):
        d = StreamDeadline(0)
        d.observe(23, {"chars": 266153})
        result = d.observe(203, {"chars": 266153})
        self.assertEqual(result["notice"], "NO_CHARACTER_PROGRESS_NOTICE")
        self.assertFalse(result["abort"])
        self.assertEqual(d.remaining(203, {"chars": 266153}), 697)

    def test_progress_never_extends_total_deadline(self):
        d = StreamDeadline(0)
        d.observe(899, {"chars": 1000})
        with self.assertRaises(StreamDeadlineExpired) as error:
            d.remaining(900, {"chars": 1001})
        self.assertEqual(str(error.exception), "ABSOLUTE_STREAM_DEADLINE")

    def test_unchanged_character_count_does_not_reset_progress(self):
        d = StreamDeadline(0)
        d.observe(10, {"chars": 3})
        d.observe(100, {"chars": 3})
        self.assertEqual(d.observe(190, {"chars": 3})["notice"],
                         "NO_CHARACTER_PROGRESS_NOTICE")

    def test_invalid_policy_and_progress_are_rejected(self):
        for kwargs in ({"absolute_seconds": 901}, {"idle_seconds": 0},
                       {"idle_seconds": float("nan")}, {"started": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                StreamDeadline(**{"started": 0, **kwargs})
        d = StreamDeadline(0)
        d.observe(5, {"chars": 10})
        for now, state in ((4, {"chars": 10}), (6, {"chars": 9}),
                           (6, {"chars": True}), (float("nan"), {"chars": 10})):
            with self.subTest(now=now, state=state), self.assertRaises(ValueError):
                d.observe(now, state)


class OriginalReadTests(unittest.IsolatedAsyncioTestCase):
    def deadline(self, absolute=1):
        return StreamDeadline(time.monotonic(), absolute_seconds=absolute,
                              idle_seconds=0.01, first_data_seconds=0.01)

    async def test_notice_preserves_same_pending_read_and_one_factory_call(self):
        ready = asyncio.Event()
        notices, calls, cancelled = [], [], []

        async def original_read():
            try:
                await ready.wait()
                return b"original answer bytes"
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

        def factory():
            calls.append(True)
            return original_read()

        def notice(observation):
            notices.append(observation)
            ready.set()

        value = await await_stream_operation(factory, self.deadline(), {"chars": 1},
                                              on_observation=notice)
        self.assertEqual(value, b"original answer bytes")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(notices), 1)
        self.assertEqual(cancelled, [])

    async def test_total_deadline_cancels_only_local_wait_without_replay(self):
        calls, cancelled, notices = [], [], []

        async def read_forever():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        def factory():
            calls.append(True)
            return read_forever()

        with self.assertRaises(StreamDeadlineExpired):
            await await_stream_operation(factory, self.deadline(0.05), {"chars": 0},
                                         on_observation=notices.append)
        self.assertEqual(len(calls), 1)
        self.assertEqual(cancelled, [True])
        self.assertEqual(sum(bool(n["notice"]) for n in notices), 1)
        self.assertTrue(notices[-1]["abort"])
        self.assertFalse(notices[-1]["remote_completion_inferred"])

    async def test_original_stream_error_propagates_without_retry(self):
        calls = []
        original_error = ConnectionError("original stream disconnected")

        async def broken():
            raise original_error

        def factory():
            calls.append(True)
            return broken()

        with self.assertRaises(ConnectionError) as caught:
            await await_stream_operation(factory, self.deadline(), {"chars": 20})
        self.assertIs(caught.exception, original_error)
        self.assertEqual(len(calls), 1)

    async def test_eof_after_notice_is_preserved(self):
        ready = asyncio.Event()

        async def eof():
            await ready.wait()
            raise StopAsyncIteration

        with self.assertRaises(StopAsyncIteration):
            await await_stream_operation(eof, self.deadline(), {"chars": 5},
                                         on_observation=lambda _: ready.set())

    async def test_external_cancellation_cleans_up_original_read(self):
        started, cleaned = asyncio.Event(), asyncio.Event()

        async def read_forever():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        outer = asyncio.create_task(await_stream_operation(
            read_forever, self.deadline(), {"chars": 0}))
        await started.wait()
        outer.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await outer
        self.assertTrue(cleaned.is_set())

    async def test_logging_failure_does_not_leave_a_background_read(self):
        cleaned = asyncio.Event()

        async def read_forever():
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        def failed_callback(_):
            raise OSError("local evidence disk unavailable")

        with self.assertRaises(OSError):
            await await_stream_operation(read_forever, self.deadline(), {"chars": 0},
                                         on_observation=failed_callback)
        self.assertTrue(cleaned.is_set())

    async def test_expired_total_cap_does_not_start_another_read(self):
        calls = []
        d = StreamDeadline(0)
        with self.assertRaises(StreamDeadlineExpired):
            await await_stream_operation(lambda: calls.append(True), d, {"chars": 0},
                                         clock=lambda: 900)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
