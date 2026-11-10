"""JSON-safe complete SDK objects without changing original attempt adapters."""
from enum import Enum

import nlm_sdk_adapter_v2 as previous
from nlm_sdk_adapter_v2 import (BoundedHTTP, full_ref, save, jacob_request,
    teng_request, unique_conversation, validate_answer, dependency_preflight)


def json_value(value):
    if isinstance(value, Enum):
        return json_value(value.value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def parse_answer(provider, client, raw):
    # dataclasses.asdict retains Enum objects in real structured documents.
    # Keep all keys and raw enum values; never drop the document to serialize.
    return json_value(previous.parse_answer(provider, client, raw))
