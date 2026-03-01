"""Tests for safe activity log append/query/export behavior."""

from __future__ import annotations

from la_gui.core.activity_log_service import ActivityLogService


def test_activity_append_and_redaction(tmp_path) -> None:
    service = ActivityLogService(tmp_path / "activity.jsonl")
    service.append(
        actor_role="Admin",
        mode="Advanced",
        action_type="test.action",
        outcome="success",
        safe_metadata={
            "filename": "ok.json",
            "private_key": "SHOULD_NOT_APPEAR",
            "count": 2,
            "nested": {"secret_token": "x", "id": "abc"},
        },
    )

    entries = service.read_entries()
    assert len(entries) == 1
    metadata = entries[0].safe_metadata
    assert metadata["filename"] == "ok.json"
    assert metadata["count"] == 2
    assert "private_key" not in metadata
    assert "secret_token" not in metadata.get("nested", {})


def test_activity_query_and_export(tmp_path) -> None:
    service = ActivityLogService(tmp_path / "activity.jsonl")
    service.append(actor_role="Admin", mode="Advanced", action_type="a", outcome="success", safe_metadata={"id": "1"})
    service.append(actor_role="Auditor", mode="Standard", action_type="b", outcome="fail", safe_metadata={"id": "2"})

    found = service.query(role="Auditor", outcome="fail")
    assert len(found) == 1
    assert found[0].action_type == "b"

    out = service.export(tmp_path / "export.jsonl")
    assert out.exists()
