"""JSON-safe complete SDK objects without changing original attempt adapters."""
from enum import Enum
import json

import nlm_sdk_adapter_v2 as previous
from nlm_sdk_adapter_v2 import (BoundedHTTP, full_ref, save, jacob_request,
    teng_request, unique_conversation, validate_answer, dependency_preflight)


class ProviderApplicationError(ValueError):
    """An explicit provider control frame, not a model answer or timeout."""

    def __init__(self, details):
        super().__init__('PROVIDER_APPLICATION_ERROR')
        self.details = details


def application_error(raw):
    """Recognize only the observed structured region rejection, never prose.

    Keep this diagnostic separate from remote-terminal/budget decisions. Unknown
    frame layouts and other reasons still use the existing SDK parser.
    """
    for line in raw.splitlines():
        if not line.lstrip().startswith('['):
            continue
        try:
            rows = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not (isinstance(row, list) and len(row) > 5 and row[0] == 'wrb.fr'
                    and row[2] is None and isinstance(row[5], list)):
                continue
            error = row[5]
            if not (len(error) == 3 and type(error[0]) is int and error[0] == 7
                    and isinstance(error[2], list)):
                continue
            for detail in error[2]:
                if not (isinstance(detail, list) and len(detail) == 2
                        and detail[0] == 'type.googleapis.com/google.rpc.ErrorInfo'
                        and isinstance(detail[1], list)):
                    continue
                info = detail[1]
                if not (len(info) == 3 and info[0] == 'REGION_NOT_SUPPORTED'
                        and isinstance(info[2], list)):
                    continue
                result = {'category': 'provider_application_error', 'rpc_code': 7,
                          'reason': 'REGION_NOT_SUPPORTED'}
                for pair in info[2]:
                    if (isinstance(pair, list) and len(pair) == 2
                            and pair[0] == 'region_code' and isinstance(pair[1], str)
                            and len(pair[1]) == 2 and pair[1].isascii() and pair[1].isupper()
                            and pair[1].isalpha()):
                        result['region_code'] = pair[1]
                return result
    return None


def json_value(value):
    if isinstance(value, Enum):
        return json_value(value.value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def parse_answer(provider, client, raw):
    error = application_error(raw)
    if error:
        raise ProviderApplicationError(error)
    # dataclasses.asdict retains Enum objects in real structured documents.
    # Keep all keys and raw enum values; never drop the document to serialize.
    return json_value(previous.parse_answer(provider, client, raw))
