"""Canonical JSON form of a decoded session, the expected output of the golden vectors.

It holds wire values only (integers in their fixed-point units, never floats), so
any language's decoder can produce the same document and compare it field by field:

* ``device_id`` is 16 lowercase hex digits (a u64 does not fit a JSON number safely);
* byte strings (``signature``, unknown payloads) are lowercase hex;
* each record is ``{"type": <record_type name>, "t_ms": ..., <fields in wire order>}``,
  and a type the reader does not know is ``{"type": "unknown", "type_id": n, "t_ms": ...,
  "payload": hex}``; payload bytes past the v1 layout are not part of the form;
* enum values are their integers, names come from ``constants.toml``.

The text layout (one record per line) only keeps the files diffable; compare the
parsed JSON, not the text.
"""

from __future__ import annotations

import json
from typing import Any

from .codec import DecodedSession
from .records import FixedRecord, Header, UnknownRecord, format_device_id

type JsonObject = dict[str, Any]


def _value(value: object) -> object:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, int):
        return int(value)  # enum members become plain integers
    return value


def header_to_dict(header: Header) -> JsonObject:
    return {
        "header_flags": int(header.header_flags),
        "device_id": format_device_id(header.device_id),
        "session_id": header.session_id,
        "activity": int(header.activity),
        "hw_rev": header.hw_rev,
        "fw_version": list(header.fw_version),
    }


def record_to_dict(record: FixedRecord | UnknownRecord) -> JsonObject:
    if isinstance(record, UnknownRecord):
        return {"type": "unknown", "type_id": record.type, "t_ms": record.t_ms, "payload": record.payload.hex()}
    return {"type": record.TYPE.name.lower()} | {name: _value(v) for name, v in record.wire_fields().items()}


def to_dict(session: DecodedSession) -> JsonObject:
    return {
        "header": header_to_dict(session.header),
        "records": [record_to_dict(r) for r in session.records],
        "end": None if session.end is None else record_to_dict(session.end),
        "complete": session.complete,
        "issue": session.issue,
    }


def to_json(session: DecodedSession) -> str:
    """The canonical JSON text: deterministic, one record per line, trailing newline."""

    def line(obj: object) -> str:
        return json.dumps(obj, ensure_ascii=False)

    doc = to_dict(session)
    records = "[\n" + ",\n".join(f"    {line(r)}" for r in doc["records"]) + "\n  ]" if doc["records"] else "[]"
    return (
        "{\n"
        f'  "header": {line(doc["header"])},\n'
        f'  "records": {records},\n'
        f'  "end": {line(doc["end"])},\n'
        f'  "complete": {line(doc["complete"])},\n'
        f'  "issue": {line(doc["issue"])}\n'
        "}\n"
    )
