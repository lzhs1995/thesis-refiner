"""Observe an owned response without cancelling its read at a soft idle notice.

This module does not send requests, retry, poll a server, or release resources.
Adopt it explicitly in a task's pinned transport after the old run has returned.
The original total deadline remains hard and is never reset by progress.
"""
from __future__ import annotations

import asyncio
import math
import time


class StreamDeadlineExpired(TimeoutError):
    def __init__(self, observation):
        super().__init__(observation["reason"])
        self.observation = observation


class StreamDeadline:
    """The idle/first-data thresholds are notices; only the total cap stops a read."""

    def __init__(self, started, *, absolute_seconds=900, idle_seconds=180,
                 first_data_seconds=300):
        values = (started, absolute_seconds, idle_seconds, first_data_seconds)
        if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
            raise ValueError("FINITE_STREAM_DEADLINES_REQUIRED")
        if not 0 < idle_seconds <= first_data_seconds <= absolute_seconds <= 900:
            raise ValueError("BOUNDED_STREAM_DEADLINES_REQUIRED")
        self.started = self.progress_at = self.last_observed = started
        self.absolute = absolute_seconds
        self.idle = idle_seconds
        self.first_data = first_data_seconds
        self.characters = 0
        self._notice_for_characters = None

    def observe(self, now, state):
        count = state.get("chars")
        if (type(now) not in (int, float) or not math.isfinite(now)
                or now < self.last_observed or type(count) is not int
                or count < self.characters):
            raise ValueError("STREAM_PROGRESS_REGRESSION")
        self.last_observed = now
        if count > self.characters:
            self.characters, self.progress_at = count, now
        terminal = state.get("status") in ("DONE", "ERROR")
        elapsed = now - self.started
        idle = now - self.progress_at
        threshold = self.idle if self.characters else self.first_data
        abort = not terminal and elapsed >= self.absolute
        notice = (not terminal and not abort and idle >= threshold
                  and self._notice_for_characters != self.characters)
        return {
            "abort": abort,
            "reason": "ABSOLUTE_STREAM_DEADLINE" if abort else None,
            "terminal": terminal,
            "elapsed_seconds": round(elapsed, 3),
            "seconds_since_character_progress": round(idle, 3),
            "received_characters": self.characters,
            "absolute_seconds": self.absolute,
            "idle_notice_seconds": threshold,
            "notice": ("NO_CHARACTER_PROGRESS_NOTICE" if self.characters
                       else "FIRST_DATA_NOTICE") if notice else None,
            "idle_notice_cancels_read": False,
            "remote_completion_inferred": False,
        }

    def remaining(self, now, state):
        observation = self.observe(now, state)
        if observation["abort"]:
            raise StreamDeadlineExpired(observation)
        return max(0.0, self.started + self.absolute - now)

    def _wait_seconds(self, now):
        hard_end = self.started + self.absolute
        threshold = self.idle if self.characters else self.first_data
        if self._notice_for_characters == self.characters:
            return max(0.0, hard_end - now)
        return max(0.0, min(hard_end, self.progress_at + threshold) - now)


async def await_stream_operation(operation_factory, deadline, state, *,
                                 on_observation=None, clock=time.monotonic):
    """Await exactly one operation, keeping its pending task across idle notices.

    Pass a factory such as ``lambda: iterator.__anext__()``. The factory is not
    called if the total deadline has already expired. A timeout/cancellation
    stops only local reception; the caller must preserve its UNKNOWN remote
    outcome and reconcile the original request. EOF/errors propagate unchanged.
    ``on_observation`` is a synchronous local callback, never a network probe.
    """
    observation = deadline.observe(clock(), state)
    if observation["abort"]:
        if on_observation is not None:
            on_observation(observation)
        raise StreamDeadlineExpired(observation)
    pending = asyncio.ensure_future(operation_factory())
    try:
        while True:
            # Consume an already available original result, including real EOF.
            if pending.done():
                return pending.result()
            now = clock()
            observation = deadline.observe(now, state)
            if observation["abort"]:
                if on_observation is not None:
                    on_observation(observation)
                raise StreamDeadlineExpired(observation)
            if observation["notice"]:
                deadline._notice_for_characters = deadline.characters
                if on_observation is not None:
                    on_observation(observation)
            done, _ = await asyncio.wait({pending}, timeout=deadline._wait_seconds(now))
            if done:
                return pending.result()
    finally:
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
