"""SDK successor fixes; the original pinned adapter stays byte-for-byte intact."""
from importlib import import_module, metadata

import nlm_sdk_adapter as original
from nlm_sdk_adapter import (BoundedHTTP, full_ref, save, jacob_request,
    teng_request, unique_conversation, validate_answer)


def dependency_preflight(expected):
    """Resolve HTTP/2's lazy imports before account admission or network I/O."""
    required = {'h2': 'h2.connection', 'hpack': 'hpack', 'hyperframe': 'hyperframe.frame'}
    result = {}
    for package, module in required.items():
        actual = metadata.version(package)
        if expected.get(package) != actual:
            raise ValueError('TRANSPORT_DEPENDENCY_VERSION_MISMATCH:' + package)
        loaded = import_module(module)
        result[package] = {'version': actual, 'module': loaded.__file__}
    import_module('httpcore._async.http2')
    return result


def parse_answer(provider, client, raw):
    value = original.parse_answer(provider, client, raw)
    if provider == 'teng':
        # Runtime's existing citation-map normalizer consumes these original
        # reference IDs. Keep the entire SDK reference object alongside it.
        value['citations'] = {str(ref['citation_number']): ref['source_id']
                              for ref in value['references']}
    return value
