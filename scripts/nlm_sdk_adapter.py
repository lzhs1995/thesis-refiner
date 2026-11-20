"""Single-attempt, archived HTTP seam for explicitly pinned NotebookLM SDKs.

The SDK supplies request construction and parsing. This seam owns only the
bounded transport; it never refreshes auth, retries, deletes history or selects
a notebook. Use behind nlm_runtime's existing account budget/resource broker.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse


def full_ref(path):
    p = Path(path).resolve()
    b = p.read_bytes()
    return {"path": str(p), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def save(path, value):
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.chmod(0o600)
    tmp.replace(p)


class BoundedHTTP:
    """Exactly one send per named operation; HTTPX decodes Content-Encoding once."""

    def __init__(self, folder, *, proxy, cookies, total=240, idle=90, transport=None):
        self.folder = Path(folder)
        self.proxy, self.cookies = proxy, cookies
        self.total, self.idle, self.transport = total, idle, transport
        self.started = time.monotonic()
        self.calls = []

    async def post(self, name, url, body):
        import httpx
        if name in {r["name"] for r in self.calls}:
            raise ValueError("SECOND_POST_FORBIDDEN")
        u = urlparse(url)
        if u.scheme != "https" or u.hostname not in {"notebooklm.google.com", "notebook.google.com"}:
            raise ValueError("UNBOUND_ORIGIN")
        row = {"name": name, "host": u.hostname, "path": u.path, "method": "POST",
               "started_at": time.time(), "send_calls": 0, "decoded_bytes": 0,
               "encoded_bytes": 0, "http_eof": False, "decoder_eof": False}
        self.calls.append(row)
        record = self.folder / "HTTP.json"
        raw = self.folder / (name + ".http.raw")
        save(record, self.calls)
        remaining = self.total - (time.monotonic() - self.started)
        if remaining <= 0:
            raise TimeoutError("TOTAL_DEADLINE")
        transport = self.transport or httpx.AsyncHTTPTransport(proxy=self.proxy, retries=0, http2=True, trust_env=False)
        try:
            async with asyncio.timeout(remaining):
                async with httpx.AsyncClient(transport=transport, cookies=self.cookies, trust_env=False,
                        follow_redirects=False, timeout=httpx.Timeout(connect=15, read=self.idle, write=30, pool=15),
                        headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                                 "Accept-Encoding": "gzip, deflate", "X-Same-Domain": "1"}) as client:
                    row["send_calls"] += 1
                    async with client.stream("POST", url, content=body) as response:
                        row.update(status=response.status_code,
                                   http_version=response.http_version,
                                   encoding=response.headers.get("content-encoding", "").strip().lower())
                        coding = row["encoding"]
                        if coding not in {"", "identity", "gzip", "deflate"}:
                            raise ValueError("UNSUPPORTED_CONTENT_ENCODING")
                        response.raise_for_status()
                        with raw.open("xb") as handle:
                            raw.chmod(0o600)
                            iterator = response.aiter_bytes().__aiter__()
                            while True:
                                try:
                                    chunk = await asyncio.wait_for(anext(iterator), timeout=self.idle)
                                except StopAsyncIteration:
                                    break
                                handle.write(chunk)
                                handle.flush()
                                row.update(decoded_bytes=row["decoded_bytes"] + len(chunk),
                                           encoded_bytes=response.num_bytes_downloaded,
                                           last_byte_at=time.time())
                                save(record, self.calls)
                        row["http_eof"] = True
                        if coding in {"gzip", "deflate"}:
                            from httpx import _decoders
                            kind = _decoders.GZipDecoder if coding == "gzip" else _decoders.DeflateDecoder
                            decoder = response._decoder
                            if not isinstance(decoder, kind) or not decoder.decompressor.eof:
                                raise ValueError("COMPRESSED_TRAILER_MISSING")
                        row["decoder_eof"] = True
                        row["encoded_bytes"] = response.num_bytes_downloaded
            return raw.read_text(encoding="utf-8")
        except BaseException as exc:
            # Do not copy URLs, cookies or token-bearing exception messages.
            row["error_type"] = type(exc).__name__
            raise
        finally:
            row["ended_at"] = time.time()
            if raw.exists():
                row["raw"] = full_ref(raw)
            save(record, self.calls)


def jacob_request(client, notebook_id, question, source_ids, conversation_id):
    """Run the pinned SDK's request builder, intercepting before any network."""
    import notebooklm_tools.core.conversation as conversation
    captured = {}

    class Captured(BaseException):
        pass

    class CaptureClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, *, content):
            captured.update(url=url, body=content)
            raise Captured()

    original = conversation._httpx
    conversation._httpx = SimpleNamespace(Client=CaptureClient, ReadTimeout=original.ReadTimeout)
    try:
        client.query(notebook_id, question, source_ids=source_ids,
                     conversation_id=conversation_id, new_conversation=conversation_id is None, timeout=240)
    except Captured:
        pass
    finally:
        conversation._httpx = original
    if not captured:
        raise ValueError("SDK_REQUEST_NOT_CAPTURED")
    params = json.loads(json.loads(parse_qs(captured["body"])["f.req"][0])[1])
    return captured["url"], captured["body"], params[4]


def teng_request(profile, notebook_id, question, source_ids, conversation_id):
    from notebooklm._web.params.chat_stream import build_streaming_chat_request
    snapshot = SimpleNamespace(csrf_token=profile.csrf_token, session_id=profile.session_id,
                               authuser=0, account_email=profile.email)
    url, body, _ = build_streaming_chat_request(snapshot=snapshot, notebook_id=notebook_id,
        question=question, source_ids=source_ids, conversation_history=None,
        conversation_id=conversation_id, reqid=int(time.time() * 1000) % 900000 + 100000)
    return url, body, conversation_id


def parse_answer(provider, client, raw):
    from notebooklm._web.rows.chat_stream import _extract_chunk_with_parseable
    final_lines = []
    marked = False
    terminal = False
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith('['):
            continue
        chunk = _extract_chunk_with_parseable(line)
        marked |= bool(chunk.is_answer and chunk.text)
        terminal |= chunk.is_final_response or chunk.terminal_sequence is not None
        if chunk.is_answer and chunk.text and chunk.is_final_response:
            final_lines.append(line)
    if not marked or not terminal:
        raise ValueError("MARKED_ANSWER_AND_TERMINAL_REQUIRED")
    if provider == "jacob":
        answer, data, stream_id = client._parse_query_response(raw)
        # Jacob 0.16.1 picks the longest answer; a marked final chunk may be
        # shorter. Reuse its extractor on that exact final chunk when present.
        if final_lines:
            answer, _, data, stream_id = client._extract_answer_from_chunk(final_lines[-1])
        result = {"answer": answer, **data, "stream_id": stream_id}
    elif provider == "teng":
        from notebooklm._web.rows.chat_stream import parse_streaming_chat_response
        value = parse_streaming_chat_response(raw)
        result = asdict(value)
        result["stream_id"] = result.pop("conversation_id")
        result["sources_used"] = list(dict.fromkeys(r["source_id"] for r in result["references"]))
    else:
        raise ValueError("EXPLICIT_PROVIDER_REQUIRED")
    if not result.get("answer", "").strip():
        raise ValueError("EMPTY_ANSWER")
    result["provider"] = provider
    result["stream_id_is_persistent_conversation"] = False
    # Full raw is archived separately; no reduction of reference/table/coordinates.
    return result


def validate_answer(value, request):
    sources = set(request["source_ids"])
    references = value.get("references")
    if not value.get("answer", "").strip() or not references:
        raise ValueError("ANSWER_AND_REFERENCES_REQUIRED")
    if any(r.get("source_id") not in sources for r in references):
        raise ValueError("REFERENCE_OUTSIDE_BOUND_SOURCES")
    if not set(value.get("sources_used", [])) <= sources:
        raise ValueError("SOURCE_SET_CHANGED")
    if not value.get("conversation_id"):
        raise ValueError("PERSISTENT_CONVERSATION_READBACK_REQUIRED")
    if request.get("conversation_id") and value["conversation_id"] != request["conversation_id"]:
        raise ValueError("PERSISTENT_CONVERSATION_CHANGED")
    return value


def unique_conversation(value):
    """Accept only a single conversation from our newly created notebook."""
    import re
    ids = []
    def walk(x):
        if isinstance(x, str) and re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", x):
            ids.append(x)
        elif isinstance(x, list):
            for item in x:
                walk(item)
    walk(value)
    ids = list(dict.fromkeys(ids))
    if len(ids) != 1:
        raise ValueError("PERSISTENT_CONVERSATION_NOT_UNIQUE")
    return ids[0]
