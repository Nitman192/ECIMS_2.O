"""Tests for data key bundle generation and rotation."""

from __future__ import annotations

from la_gui.core.data_key_service import DataKeyService
from la_gui.core.storage_paths import StoragePaths


def test_generate_and_rotate_data_key_bundle(tmp_path) -> None:
    paths = StoragePaths(root=tmp_path)
    paths.ensure_directories()

    first = DataKeyService.generate_data_key_bundle(paths)
    assert first.algorithm == "AES-256"
    assert paths.latest_data_key_bundle_path.exists()

    rotated = DataKeyService.rotate_data_key_bundle(paths)
    assert rotated.previous_key_id == first.key_id
    assert (paths.exports_dir / "data_key_bundle.json").exists()
