"""Tests for canonical JSON stability guarantees."""

from __future__ import annotations

from la_gui.core.canonical_json import canonicalize_json


def test_canonicalization_stable_for_different_key_order() -> None:
    obj_a = {"b": 1, "a": {"z": 9, "k": 7}}
    obj_b = {"a": {"k": 7, "z": 9}, "b": 1}

    assert canonicalize_json(obj_a) == canonicalize_json(obj_b)
