"""Canonical JSON serialization helpers used for signing."""

from __future__ import annotations

import json
from typing import Any


def canonicalize_json(data: Any) -> bytes:
    """Serialize a Python object to canonical UTF-8 JSON bytes.

    This canonical form enforces deterministic signatures by sorting keys and
    using compact separators.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
