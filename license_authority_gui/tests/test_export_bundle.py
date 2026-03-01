"""Tests for activation export bundle manifest behavior."""

from __future__ import annotations

import zipfile

from la_gui.core.export_bundle import ExportBundleService


def test_activation_bundle_create_and_verify(tmp_path) -> None:
    license_path = tmp_path / "license_abc.json"
    license_path.write_text('{"serial":"1"}', encoding="utf-8")

    pub_path = tmp_path / "la_public_key.pem"
    pub_path.write_text("PUBLIC", encoding="utf-8")

    bundle_path = tmp_path / "bundle.zip"
    ExportBundleService.create_activation_bundle(bundle_path, [license_path, pub_path])

    ok, details = ExportBundleService.verify_manifest(bundle_path)
    assert ok
    assert details["file_count"] == 2


def test_activation_bundle_detects_tampered_file(tmp_path) -> None:
    license_path = tmp_path / "license_abc.json"
    license_path.write_text('{"serial":"1"}', encoding="utf-8")

    pub_path = tmp_path / "la_public_key.pem"
    pub_path.write_text("PUBLIC", encoding="utf-8")

    bundle_path = tmp_path / "bundle.zip"
    ExportBundleService.create_activation_bundle(bundle_path, [license_path, pub_path])

    tampered_path = tmp_path / "bundle_tampered.zip"
    with zipfile.ZipFile(bundle_path, "r") as src, zipfile.ZipFile(tampered_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            payload = src.read(name)
            if name == "license.json":
                payload = b"tampered"
            dst.writestr(name, payload)

    ok, _details = ExportBundleService.verify_manifest(tampered_path)
    assert not ok
