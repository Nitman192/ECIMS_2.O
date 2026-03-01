"""Tests for wizard step state computation."""

from __future__ import annotations

from la_gui.core.settings_service import AppSettings
from la_gui.core.storage_paths import StoragePaths
from la_gui.ui.wizard_state import build_snapshot, evaluate_steps


def test_wizard_step_gating(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    snapshot = build_snapshot(paths, unlocked=False, offline_ack=False)
    steps = evaluate_steps(snapshot, AppSettings())

    by_key = {step.key: step for step in steps}
    assert by_key["offline"].status == "Missing"
    assert by_key["license"].enabled is False
    assert by_key["bundle"].enabled is False

    paths.root_public_key_path.write_text("pub", encoding="utf-8")
    (paths.exports_dir / "license_x.json").write_text("{}", encoding="utf-8")
    snapshot2 = build_snapshot(paths, unlocked=True, offline_ack=True)
    steps2 = {step.key: step for step in evaluate_steps(snapshot2, AppSettings())}
    assert steps2["bundle"].enabled is True
