"""Three offline HTTPX stream cases; no SDK authentication or real network."""
import asyncio
import gzip
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest


if sys.version_info < (3, 11):
    raise unittest.SkipTest("Pair controller requires Python 3.11+")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import httpx
from nlm_pair_http import PairBoundedHTTP

# The original transport enforces this public origin before the injected mock
# is called. No DNS, TLS or live request occurs in these tests.
URL = 'https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute'


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks, *, delay=0):
        self.chunks, self.delay = chunks, delay
        self.closed = False
        self.started = False

    async def __aiter__(self):
        self.started = True
        for chunk in self.chunks:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield chunk

    async def aclose(self):
        self.closed = True


class PairHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_error_is_recorded_once_without_retry_or_eof(self):
        calls = []
        async def fail(request):
            calls.append(request)
            raise httpx.ConnectError('synthetic connection failure', request=request)
        out = self.folder('connection-error')
        network = PairBoundedHTTP(out, proxy=None, cookies={}, transport=httpx.MockTransport(fail))
        with self.assertRaises(httpx.ConnectError):
            await network.post('query', URL, '')
        with self.assertRaisesRegex(ValueError, 'SECOND_POST_FORBIDDEN'):
            await network.post('query', URL, '')
        self.assertEqual(len(calls), 1)
        row = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())[0]
        self.assertEqual(row['transport_error_type'], 'ConnectError')
        self.assertIsNone(row['body_eof_monotonic_ns'])
        self.assertIsNone(row['response_headers_monotonic_ns'])

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def folder(self, name):
        out = self.root / name
        out.mkdir()
        return out

    async def test_two_calls_get_distinct_transports_and_actual_stream_events(self):
        transports, streams = [], []
        def factory():
            stream = Chunks([b'first ', b'second'], delay=.001)
            streams.append(stream)
            async def handle(request):
                return httpx.Response(200, stream=stream)
            transport = httpx.MockTransport(handle)
            transports.append(transport)
            return transport
        out = self.folder('complete')
        network = PairBoundedHTTP(out, proxy='http://unused.invalid', cookies={}, transport=factory)
        original_started = network.started
        self.assertEqual(await network.post('query', URL, 'body'), 'first second')
        self.assertEqual(await network.post('rpc-hPTbtc-after-query', URL, 'body'), 'first second')
        self.assertEqual(len(transports), 2)
        self.assertIsNot(transports[0], transports[1])
        self.assertEqual(network.started, original_started)
        self.assertTrue(all(stream.closed for stream in streams))
        observations = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())
        original = json.loads((out / 'HTTP.json').read_text())
        for row, raw in zip(observations, original):
            stamps = [row[key] for key in ('request_transport_monotonic_ns',
                'response_headers_monotonic_ns', 'body_read_started_monotonic_ns',
                'first_chunk_monotonic_ns', 'last_chunk_monotonic_ns', 'body_eof_monotonic_ns')]
            self.assertEqual(stamps, sorted(stamps))
            self.assertTrue(all(type(stamp) is int for stamp in stamps))
            self.assertEqual(row['raw_chunk_count'], 2)
            self.assertEqual([r['result'] for r in row['raw_read_intervals']], ['CHUNK', 'CHUNK', 'EOF'])
            self.assertEqual(row['clock'], 'time.monotonic_ns')
            self.assertEqual(row['original_http_path'], str((out / 'HTTP.json').resolve()))
            self.assertEqual(row['original_http_match'], 'exact name in final HTTP.json')
            self.assertTrue(raw['http_eof'] and raw['decoder_eof'])
        with self.assertRaisesRegex(ValueError, 'SECOND_POST_FORBIDDEN'):
            await network.post('query', URL, 'body')
        self.assertEqual(len(transports), 2)

    async def test_missing_compression_tail_and_429_do_not_become_complete_eof(self):
        compressed = gzip.compress(b'raw encoded payload')[:-4]
        stream = Chunks([compressed])
        async def truncated(request):
            return httpx.Response(200, headers={'Content-Encoding': 'gzip'}, stream=stream)
        out = self.folder('truncated')
        network = PairBoundedHTTP(out, proxy=None, cookies={}, transport=httpx.MockTransport(truncated))
        with self.assertRaisesRegex(ValueError, 'COMPRESSED_TRAILER_MISSING'):
            await network.post('query', URL, '')
        row = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())[0]
        original = json.loads((out / 'HTTP.json').read_text())[0]
        self.assertIsInstance(row['body_eof_monotonic_ns'], int)  # Raw bytes ended.
        self.assertTrue(original['http_eof'])
        self.assertFalse(original['decoder_eof'])  # Original contract still rejects.
        unread = Chunks([b'this body must not be read'])
        async def quota(request):
            return httpx.Response(429, stream=unread)
        out = self.folder('quota')
        network = PairBoundedHTTP(out, proxy=None, cookies={}, transport=httpx.MockTransport(quota))
        with self.assertRaises(httpx.HTTPStatusError):
            await network.post('query', URL, '')
        row = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())[0]
        original = json.loads((out / 'HTTP.json').read_text())[0]
        self.assertEqual(row['response_status'], 429)
        self.assertIsInstance(row['response_headers_monotonic_ns'], int)
        self.assertIsNone(row['body_read_started_monotonic_ns'])
        self.assertIsNone(row['body_eof_monotonic_ns'])
        self.assertFalse(unread.started)
        self.assertFalse(original['http_eof'] or original['decoder_eof'])

    async def test_total_and_idle_limits_preserved_and_instance_not_reused(self):
        slow = Chunks([b'late'], delay=2)
        async def delayed(request):
            return httpx.Response(200, stream=slow)
        out = self.folder('idle')
        network = PairBoundedHTTP(out, proxy=None, cookies={}, total=1, idle=.01,
                                  transport=httpx.MockTransport(delayed))
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            await network.post('query', URL, '')
        self.assertLess(time.monotonic() - started, .75)
        row = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())[0]
        self.assertIsNotNone(row['body_read_started_monotonic_ns'])
        self.assertIsNone(row['body_eof_monotonic_ns'])
        self.assertEqual(row['raw_read_intervals'][-1]['result'], 'ERROR')
        with self.assertRaisesRegex(ValueError, 'PAIR_RAW_TRANSPORT_REUSE_FORBIDDEN'):
            await network.post('second-name', URL, '')
        out = self.folder('expired')
        network = PairBoundedHTTP(out, proxy=None, cookies={}, total=.01,
                                  transport=lambda: httpx.MockTransport(delayed))
        network.started -= .02
        with self.assertRaisesRegex(TimeoutError, 'TOTAL_DEADLINE'):
            await network.post('query', URL, '')
        row = json.loads((out / 'HTTP-MEASUREMENTS.json').read_text())[0]
        self.assertIsNone(row['request_transport_monotonic_ns'])
        self.assertIsNone(row['body_eof_monotonic_ns'])


if __name__ == '__main__':
    unittest.main()
