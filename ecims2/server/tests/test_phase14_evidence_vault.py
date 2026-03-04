from __future__ import annotations

import base64
import copy
import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from app.db.database import get_db


class TestPhase14EvidenceVault(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith("ECIMS_")]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = td / "public.pem"
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

        payload = {
            "org_name": "Test Org",
            "customer_name": "Test Org",
            "license_id": "LIC-P14-001",
            "max_agents": 100,
            "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
            "ai_enabled": True,
        }
        signature = private_key.sign(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

        license_path = td / "license.ecims"
        license_path.write_text(
            json.dumps({"payload": payload, "signature_b64": base64.b64encode(signature).decode("ascii")}),
            encoding="utf-8",
        )
        return license_path, public_path

    def _configure_env(self, td: Path) -> None:
        license_path, pub = self._make_license(td)
        os.environ["ECIMS_DB_PATH"] = str(td / "db.sqlite")
        os.environ["ECIMS_LICENSE_PATH"] = str(license_path)
        os.environ["ECIMS_LICENSE_PUBLIC_KEY_PATH"] = str(pub)
        os.environ["ECIMS_MTLS_REQUIRED"] = "false"
        os.environ["ECIMS_MTLS_ENABLED"] = "false"

    def _load_client(self) -> TestClient:
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _auth_header(self, client: TestClient, username: str, password: str) -> dict[str, str]:
        login = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(login.status_code, 200, login.text)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _create_evidence_payload(self, *, idempotency_key: str) -> dict[str, object]:
        return {
            "object_hash": "a" * 64,
            "hash_algorithm": "SHA256",
            "origin_type": "MANUAL",
            "origin_ref": "case-1001",
            "classification": "CONFIDENTIAL",
            "reason": "Initial evidence capture for triage",
            "idempotency_key": idempotency_key,
            "manifest": {"signed_manifest_id": "sig-001"},
            "metadata": {"source": "phase14-test"},
        }

    def test_evidence_create_list_idempotency_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                payload = self._create_evidence_payload(idempotency_key="evidence-idem-001")

                created = client.post("/api/v1/admin/ops/evidence-vault", headers=admin, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                self.assertTrue(created.json()["created"])
                evidence_id = str(created.json()["item"]["evidence_id"])

                replay = client.post("/api/v1/admin/ops/evidence-vault", headers=admin, json=payload)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertFalse(replay.json()["created"])
                self.assertEqual(str(replay.json()["item"]["evidence_id"]), evidence_id)

                conflict_payload = copy.deepcopy(payload)
                conflict_payload["reason"] = "Different reason should conflict with same idempotency key"
                conflict = client.post("/api/v1/admin/ops/evidence-vault", headers=admin, json=conflict_payload)
                self.assertEqual(conflict.status_code, 409, conflict.text)

                listed = client.get(
                    "/api/v1/admin/ops/evidence-vault",
                    headers=admin,
                    params={"status": "SEALED", "origin": "MANUAL", "q": evidence_id},
                )
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertGreaterEqual(int(listed.json()["total"]), 1)
                self.assertEqual(str(listed.json()["items"][0]["evidence_id"]), evidence_id)

                details = client.get(f"/api/v1/admin/ops/evidence-vault/{evidence_id}", headers=admin)
                self.assertEqual(details.status_code, 200, details.text)
                self.assertEqual(str(details.json()["status"]), "SEALED")

    def test_evidence_custody_timeline_and_chain_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                created = client.post(
                    "/api/v1/admin/ops/evidence-vault",
                    headers=admin,
                    json=self._create_evidence_payload(idempotency_key="evidence-idem-002"),
                )
                self.assertEqual(created.status_code, 201, created.text)
                evidence_id = str(created.json()["item"]["evidence_id"])

                review = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/custody",
                    headers=admin,
                    json={"event_type": "REVIEW_STARTED", "reason": "IR analyst started review", "details": {"ticket": "IR-1"}},
                )
                self.assertEqual(review.status_code, 200, review.text)
                self.assertEqual(review.json()["item"]["status"], "IN_REVIEW")

                released = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/custody",
                    headers=admin,
                    json={"event_type": "RELEASED", "reason": "Approved for legal release", "details": {"approver": "legal"}},
                )
                self.assertEqual(released.status_code, 200, released.text)
                self.assertEqual(released.json()["item"]["status"], "RELEASED")

                archived = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/custody",
                    headers=admin,
                    json={"event_type": "ARCHIVED", "reason": "Retention archive completed", "details": {"bucket": "retention-1"}},
                )
                self.assertEqual(archived.status_code, 200, archived.text)
                self.assertEqual(archived.json()["item"]["status"], "ARCHIVED")

                note = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/custody",
                    headers=admin,
                    json={"event_type": "NOTE_ADDED", "reason": "Archive verification note", "details": {"verifier": "ops"}},
                )
                self.assertEqual(note.status_code, 200, note.text)
                self.assertEqual(note.json()["item"]["status"], "ARCHIVED")

                invalid_transition = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/custody",
                    headers=admin,
                    json={"event_type": "RESEALED", "reason": "Should fail after archived", "details": {}},
                )
                self.assertEqual(invalid_transition.status_code, 409, invalid_transition.text)

                timeline = client.get(f"/api/v1/admin/ops/evidence-vault/{evidence_id}/timeline", headers=admin)
                self.assertEqual(timeline.status_code, 200, timeline.text)
                self.assertEqual(int(timeline.json()["total"]), 5)
                self.assertTrue(bool(timeline.json()["chain_valid"]))

                with get_db() as conn:
                    conn.execute(
                        "UPDATE evidence_custody_events SET event_hash = ? WHERE evidence_id = ? AND sequence_no = 1",
                        ("tampered-event-hash", evidence_id),
                    )

                tampered = client.get(f"/api/v1/admin/ops/evidence-vault/{evidence_id}/timeline", headers=admin)
                self.assertEqual(tampered.status_code, 200, tampered.text)
                self.assertFalse(bool(tampered.json()["chain_valid"]))

    def test_evidence_export_generates_bundle_and_export_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")
                created = client.post(
                    "/api/v1/admin/ops/evidence-vault",
                    headers=admin,
                    json=self._create_evidence_payload(idempotency_key="evidence-idem-003"),
                )
                self.assertEqual(created.status_code, 201, created.text)
                evidence_id = str(created.json()["item"]["evidence_id"])

                exported = client.post(
                    f"/api/v1/admin/ops/evidence-vault/{evidence_id}/export",
                    headers=admin,
                    json={"reason": "Compliance package export"},
                )
                self.assertEqual(exported.status_code, 200, exported.text)
                self.assertEqual(len(str(exported.json()["export_hash"])), 64)
                self.assertTrue(bool(exported.json()["chain_valid"]))
                self.assertEqual(exported.json()["bundle"]["evidence"]["evidence_id"], evidence_id)
                self.assertEqual(exported.json()["bundle"]["export_reason"], "Compliance package export")

                timeline = client.get(f"/api/v1/admin/ops/evidence-vault/{evidence_id}/timeline", headers=admin)
                self.assertEqual(timeline.status_code, 200, timeline.text)
                self.assertEqual(int(timeline.json()["total"]), 2)
                self.assertEqual(timeline.json()["items"][-1]["event_type"], "EXPORT_COMPLETED")
                self.assertTrue(bool(timeline.json()["chain_valid"]))

    def test_evidence_endpoints_are_admin_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, "admin", "admin123")

                create_user = client.post(
                    "/api/v1/admin/users",
                    headers=admin,
                    json={
                        "username": "analyst_evidence",
                        "password": "AnalystPass12345!",
                        "role": "ANALYST",
                        "is_active": True,
                        "must_reset_password": False,
                    },
                )
                self.assertEqual(create_user.status_code, 201, create_user.text)
                analyst = self._auth_header(client, "analyst_evidence", "AnalystPass12345!")

                denied_list = client.get("/api/v1/admin/ops/evidence-vault", headers=analyst)
                self.assertEqual(denied_list.status_code, 403, denied_list.text)

                denied_create = client.post(
                    "/api/v1/admin/ops/evidence-vault",
                    headers=analyst,
                    json=self._create_evidence_payload(idempotency_key="evidence-rbac-001"),
                )
                self.assertEqual(denied_create.status_code, 403, denied_create.text)

                denied_timeline = client.get("/api/v1/admin/ops/evidence-vault/evd_dummy/timeline", headers=analyst)
                self.assertEqual(denied_timeline.status_code, 403, denied_timeline.text)

                denied_custody = client.post(
                    "/api/v1/admin/ops/evidence-vault/evd_dummy/custody",
                    headers=analyst,
                    json={"event_type": "NOTE_ADDED", "reason": "Not allowed", "details": {}},
                )
                self.assertEqual(denied_custody.status_code, 403, denied_custody.text)

                denied_export = client.post(
                    "/api/v1/admin/ops/evidence-vault/evd_dummy/export",
                    headers=analyst,
                    json={"reason": "Not allowed"},
                )
                self.assertEqual(denied_export.status_code, 403, denied_export.text)


if __name__ == "__main__":
    unittest.main()
