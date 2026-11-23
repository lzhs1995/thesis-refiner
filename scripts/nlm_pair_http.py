"""Observe raw HTTP stream timing without replacing the original HTTP contract.

Only monotonic observations are added. Original BoundedHTTP still owns POST,
cookies, decoding, response status, deadlines, raw files and HTTP.json. These
observations are not acceptance or overlap claims. A body interval is usable
only with the same operation's successful original HTTP/decoder EOF evidence.
"""
from __future__ import annotations

import os
import socket
import time

import httpx
from nlm_sdk_adapter_v3 import BoundedHTTP, save


class _ObservedStream(httpx.AsyncByteStream):
    def __init__(self, inner, row, persist):
        self.inner, self.row, self.persist = inner, row, persist

    async def __aiter__(self):
        if self.row['body_read_started_monotonic_ns'] is not None:
            raise ValueError('PAIR_RESPONSE_STREAM_REITERATION_FORBIDDEN')
        self.row['body_read_started_monotonic_ns'] = time.monotonic_ns()
        self.persist()
        iterator = self.inner.__aiter__()
        while True:
            interval = {'started_monotonic_ns': time.monotonic_ns(),
                        'ended_monotonic_ns': None, 'result': 'PENDING'}
            self.row['raw_read_intervals'].append(interval)
            self.persist()
            try:
                chunk = await anext(iterator)
            except StopAsyncIteration:
                stamp = time.monotonic_ns()
                interval.update(ended_monotonic_ns=stamp, result='EOF')
                self.row['body_eof_monotonic_ns'] = stamp
                self.persist()
                return
            except BaseException as exc:
                interval.update(ended_monotonic_ns=time.monotonic_ns(), result='ERROR',
                                error_type=type(exc).__name__)
                self.persist()
                raise
            stamp = time.monotonic_ns()
            interval.update(ended_monotonic_ns=stamp, result='CHUNK', bytes=len(chunk))
            self.row['raw_chunk_count'] += 1
            self.row['raw_bytes'] += len(chunk)
            if self.row['first_chunk_monotonic_ns'] is None:
                self.row['first_chunk_monotonic_ns'] = stamp
            self.row['last_chunk_monotonic_ns'] = stamp
            self.persist()
            yield chunk

    async def aclose(self):
        # Close is not EOF: HTTP errors or cancellation may close an unread body.
        try:
            await self.inner.aclose()
        finally:
            self.row['stream_closed_monotonic_ns'] = time.monotonic_ns()
            self.persist()


class _ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, inner, row, persist):
        self.inner, self.row, self.persist = inner, row, persist

    async def __aenter__(self):
        await self.inner.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.inner.__aexit__(*args)

    async def handle_async_request(self, request):
        if self.row['request_transport_monotonic_ns'] is not None:
            raise ValueError('SECOND_TRANSPORT_SEND_FORBIDDEN')
        self.row['request_transport_monotonic_ns'] = time.monotonic_ns()
        self.persist()
        try:
            response = await self.inner.handle_async_request(request)
        except BaseException as exc:
            self.row['transport_error_type'] = type(exc).__name__
            self.persist()
            raise
        self.row['response_headers_monotonic_ns'] = time.monotonic_ns()
        self.row['response_status'] = response.status_code
        self.persist()
        if not isinstance(response.stream, httpx.AsyncByteStream):
            raise TypeError('ASYNC_RAW_RESPONSE_STREAM_REQUIRED')
        response.stream = _ObservedStream(response.stream, self.row, self.persist)
        return response

    async def aclose(self):
        return await self.inner.aclose()


class PairBoundedHTTP(BoundedHTTP):
    """Original signature; default creates a fresh raw transport for every POST.

    For offline tests, transport may be a zero-argument factory returning a new
    AsyncBaseTransport. An explicit instance is single-use, never reopened after
    AsyncClient closes it. A single PairBoundedHTTP handles sequential named
    calls; separate child processes own concurrent queries.
    """
    def __init__(self, folder, *, proxy, cookies, total=240, idle=90, transport=None):
        super().__init__(folder, proxy=proxy, cookies=cookies, total=total, idle=idle)
        self._injected_transport = transport
        self._owned_transports = []
        self._post_active = False
        self.measurements = []

    def _persist(self):
        save(self.folder / 'HTTP-MEASUREMENTS.json', self.measurements)

    def _new_transport(self):
        supplied = self._injected_transport
        if supplied is None:
            inner = httpx.AsyncHTTPTransport(proxy=self.proxy, retries=0,
                                             http2=True, trust_env=False)
        elif isinstance(supplied, httpx.AsyncBaseTransport):
            inner = supplied
        elif callable(supplied):
            inner = supplied()
        else:
            raise TypeError('ASYNC_TRANSPORT_OR_FACTORY_REQUIRED')
        if not isinstance(inner, httpx.AsyncBaseTransport):
            raise TypeError('ASYNC_TRANSPORT_FACTORY_RESULT_REQUIRED')
        if any(inner is previous for previous in self._owned_transports):
            raise ValueError('PAIR_RAW_TRANSPORT_REUSE_FORBIDDEN')
        self._owned_transports.append(inner)
        return inner

    async def post(self, name, url, body):
        if self._post_active:
            raise ValueError('ONE_ACTIVE_POST_PER_CHILD_HTTP_INSTANCE')
        if name in {row['name'] for row in self.calls}:
            raise ValueError('SECOND_POST_FORBIDDEN')
        row = {'schema': 'nlm-http-monotonic-observation-v1', 'name': name,
               'clock': 'time.monotonic_ns', 'clock_scope': 'same-host-kernel-monotonic',
               'source': 'httpx.AsyncBaseTransport/AsyncByteStream',
               'hostname': socket.gethostname(), 'pid': os.getpid(),
               'scope': 'client raw response read interval; includes waits between chunks, not server compute',
               'acceptance': 'OBSERVATIONS_ONLY_REQUIRES_ORIGINAL_HTTP_AND_DECODER_EOF',
               'request_transport_monotonic_ns': None, 'response_headers_monotonic_ns': None,
               'body_read_started_monotonic_ns': None, 'first_chunk_monotonic_ns': None,
               'last_chunk_monotonic_ns': None, 'body_eof_monotonic_ns': None,
               'raw_chunk_count': 0, 'raw_bytes': 0, 'raw_read_intervals': []}
        self.measurements.append(row)
        self._persist()
        self._post_active = True
        try:
            self.transport = _ObservedTransport(self._new_transport(), row, self._persist)
            # Do not reset self.started: query and subsequent metadata share
            # the same original total deadline, including measurement overhead.
            return await super().post(name, url, body)
        except BaseException as exc:
            row['error_type'] = type(exc).__name__
            raise
        finally:
            self.transport = None
            self._post_active = False
            row['post_finished_monotonic_ns'] = time.monotonic_ns()
            record = self.folder / 'HTTP.json'
            if record.is_file():
                # HTTP.json remains appendable until this child's last named
                # call. The parent pins both completed files together; storing
                # an intermediate hash here would become stale on the next call.
                row['original_http_path'] = str(record.resolve())
                row['original_http_match'] = 'exact name in final HTTP.json'
            self._persist()
