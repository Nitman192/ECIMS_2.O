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


class TestPhase13Enrollment(unittest.TestCase):
    def tearDown(self) -> None:
        for key in [k for k in os.environ.keys() if k.startswith('ECIMS_')]:
            os.environ.pop(key, None)
        from app.core.config import get_settings

        get_settings.cache_clear()

    def _make_license(self, td: Path) -> tuple[Path, Path]:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_path = td / 'public.pem'
        public_path.write_bytes(
            private_key.public_key().public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

        payload = {
            'org_name': 'Test Org',
            'customer_name': 'Test Org',
            'license_id': 'LIC-P13-001',
            'max_agents': 100,
            'expiry_date': (date.today() + timedelta(days=30)).isoformat(),
            'ai_enabled': True,
        }
        signature = private_key.sign(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

        license_path = td / 'license.ecims'
        license_path.write_text(
            json.dumps({'payload': payload, 'signature_b64': base64.b64encode(signature).decode('ascii')}),
            encoding='utf-8',
        )
        return license_path, public_path

    def _load_client(self) -> TestClient:
        from app.core.config import get_settings
        from app import main as main_module

        get_settings.cache_clear()
        importlib.reload(main_module)
        return TestClient(main_module.app)

    def _auth_header(self, client: TestClient, username: str, password: str) -> dict[str, str]:
        login = client.post('/api/v1/auth/login', json={'username': username, 'password': password})
        self.assertEqual(login.status_code, 200, login.text)
        return {'Authorization': f"Bearer {login.json()['access_token']}"}

    def _configure_env(self, tmp: Path) -> None:
        license_path, pub = self._make_license(tmp)
        os.environ['ECIMS_DB_PATH'] = str(tmp / 'db.sqlite')
        os.environ['ECIMS_LICENSE_PATH'] = str(license_path)
        os.environ['ECIMS_LICENSE_PUBLIC_KEY_PATH'] = str(pub)
        os.environ['ECIMS_MTLS_REQUIRED'] = 'false'
        os.environ['ECIMS_MTLS_ENABLED'] = 'false'

    def test_admin_enrollment_token_lifecycle_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, 'admin', 'admin123')

                payload = {
                    'mode': 'ONLINE',
                    'expires_in_hours': 48,
                    'max_uses': 2,
                    'reason_code': 'BOOTSTRAP',
                    'reason': 'Bootstrap enrollment for field rollout',
                    'idempotency_key': 'enroll-idem-001',
                    'metadata': {'source': 'tests'},
                }
                created = client.post('/api/v1/admin/ops/enrollment/tokens', headers=admin, json=payload)
                self.assertEqual(created.status_code, 201, created.text)
                self.assertTrue(created.json()['created'])
                self.assertIsNotNone(created.json().get('enrollment_token'))
                token_id = created.json()['item']['token_id']

                replay = client.post('/api/v1/admin/ops/enrollment/tokens', headers=admin, json=payload)
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertFalse(replay.json()['created'])
                self.assertIsNone(replay.json().get('enrollment_token'))

                conflict_payload = dict(payload)
                conflict_payload['reason'] = 'Different reason should conflict with same idempotency key'
                conflict = client.post('/api/v1/admin/ops/enrollment/tokens', headers=admin, json=conflict_payload)
                self.assertEqual(conflict.status_code, 409, conflict.text)

                listed = client.get(
                    '/api/v1/admin/ops/enrollment/tokens',
                    headers=admin,
                    params={'mode': 'ONLINE', 'status': 'ACTIVE', 'q': token_id},
                )
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertGreaterEqual(int(listed.json()['total']), 1)

                revoked = client.post(
                    f'/api/v1/admin/ops/enrollment/tokens/{token_id}/revoke',
                    headers=admin,
                    json={'reason': 'Token compromised during test'},
                )
                self.assertEqual(revoked.status_code, 200, revoked.text)
                self.assertEqual(revoked.json()['status'], 'revoked')
                self.assertEqual(revoked.json()['item']['status'], 'REVOKED')

                listed_revoked = client.get(
                    '/api/v1/admin/ops/enrollment/tokens',
                    headers=admin,
                    params={'status': 'REVOKED', 'q': token_id},
                )
                self.assertEqual(listed_revoked.status_code, 200, listed_revoked.text)
                self.assertGreaterEqual(int(listed_revoked.json()['total']), 1)

    def test_offline_kit_import_idempotency_and_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, 'admin', 'admin123')

                issue = client.post(
                    '/api/v1/admin/ops/enrollment/tokens',
                    headers=admin,
                    json={
                        'mode': 'OFFLINE',
                        'expires_in_hours': 72,
                        'max_uses': 3,
                        'reason_code': 'OFFLINE_AIRGAP',
                        'reason': 'Offline onboarding kit generation test',
                        'idempotency_key': 'enroll-offline-001',
                        'metadata': {'site': 'airgap-lab'},
                    },
                )
                self.assertEqual(issue.status_code, 201, issue.text)
                bundle = issue.json().get('offline_kit_bundle')
                self.assertIsInstance(bundle, dict)

                imported = client.post(
                    '/api/v1/admin/ops/enrollment/offline-kit/import',
                    headers=admin,
                    json={'bundle': bundle},
                )
                self.assertEqual(imported.status_code, 200, imported.text)
                self.assertFalse(imported.json()['created_token'])
                self.assertFalse(imported.json()['created_kit'])

                replay = client.post(
                    '/api/v1/admin/ops/enrollment/offline-kit/import',
                    headers=admin,
                    json={'bundle': bundle},
                )
                self.assertEqual(replay.status_code, 200, replay.text)
                self.assertFalse(replay.json()['created_token'])
                self.assertFalse(replay.json()['created_kit'])

                kit_conflict = copy.deepcopy(bundle)
                kit_conflict['token']['reason'] = 'changed reason causing bundle hash mismatch'
                kit_conflict_resp = client.post(
                    '/api/v1/admin/ops/enrollment/offline-kit/import',
                    headers=admin,
                    json={'bundle': kit_conflict},
                )
                self.assertEqual(kit_conflict_resp.status_code, 409, kit_conflict_resp.text)

                token_conflict = copy.deepcopy(bundle)
                token_conflict['kit_id'] = f"{bundle['kit_id']}-conflict"
                current = str(token_conflict['token']['enrollment_token'])
                token_prefix, _secret = current.split('.', 1)
                token_conflict['token']['enrollment_token'] = f'{token_prefix}.different-secret-value'
                token_conflict_resp = client.post(
                    '/api/v1/admin/ops/enrollment/offline-kit/import',
                    headers=admin,
                    json={'bundle': token_conflict},
                )
                self.assertEqual(token_conflict_resp.status_code, 409, token_conflict_resp.text)

    def test_agent_enroll_consumption_invalid_and_revoked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                from app.api.deps import require_registration_allowed

                # Local test environments can report tamper state for generated licenses;
                # enrollment behavior is validated here by overriding only the license gate.
                client.app.dependency_overrides[require_registration_allowed] = lambda: None
                try:
                    admin = self._auth_header(client, 'admin', 'admin123')

                    issued = client.post(
                        '/api/v1/admin/ops/enrollment/tokens',
                        headers=admin,
                        json={
                            'mode': 'ONLINE',
                            'expires_in_hours': 24,
                            'max_uses': 1,
                            'reason_code': 'BOOTSTRAP',
                            'reason': 'Single-use enrollment token',
                            'idempotency_key': 'enroll-agent-001',
                            'metadata': {'source': 'phase13-test'},
                        },
                    )
                    self.assertEqual(issued.status_code, 201, issued.text)
                    enroll_token = issued.json()['enrollment_token']
                    token_id = issued.json()['item']['token_id']

                    first_enroll = client.post(
                        '/api/v1/agents/enroll',
                        json={
                            'name': 'agent-enr-1',
                            'hostname': 'agent-host-1',
                            'enrollment_token': enroll_token,
                        },
                    )
                    self.assertEqual(first_enroll.status_code, 200, first_enroll.text)
                    agent_id = int(first_enroll.json()['agent_id'])

                    with get_db() as conn:
                        use_row = conn.execute(
                            "SELECT agent_id FROM enrollment_token_uses WHERE token_id = ? ORDER BY id DESC LIMIT 1",
                            (token_id,),
                        ).fetchone()
                        self.assertIsNotNone(use_row)
                        self.assertEqual(int(use_row['agent_id']), agent_id)

                    consumed = client.post(
                        '/api/v1/agents/enroll',
                        json={
                            'name': 'agent-enr-2',
                            'hostname': 'agent-host-2',
                            'enrollment_token': enroll_token,
                        },
                    )
                    self.assertEqual(consumed.status_code, 403, consumed.text)

                    invalid = client.post(
                        '/api/v1/agents/enroll',
                        json={
                            'name': 'agent-invalid',
                            'hostname': 'agent-invalid-host',
                            'enrollment_token': 'ectk_invalid.invalid-secret',
                        },
                    )
                    self.assertEqual(invalid.status_code, 401, invalid.text)

                    issued_revokable = client.post(
                        '/api/v1/admin/ops/enrollment/tokens',
                        headers=admin,
                        json={
                            'mode': 'ONLINE',
                            'expires_in_hours': 24,
                            'max_uses': 2,
                            'reason_code': 'TESTING',
                            'reason': 'Revoked token path test',
                            'idempotency_key': 'enroll-agent-002',
                            'metadata': {'source': 'phase13-test'},
                        },
                    )
                    self.assertEqual(issued_revokable.status_code, 201, issued_revokable.text)
                    revoked_token_id = issued_revokable.json()['item']['token_id']
                    revoked_token_value = issued_revokable.json()['enrollment_token']

                    revoke = client.post(
                        f'/api/v1/admin/ops/enrollment/tokens/{revoked_token_id}/revoke',
                        headers=admin,
                        json={'reason': 'Revoked before use'},
                    )
                    self.assertEqual(revoke.status_code, 200, revoke.text)

                    revoked_enroll = client.post(
                        '/api/v1/agents/enroll',
                        json={
                            'name': 'agent-revoked',
                            'hostname': 'agent-revoked-host',
                            'enrollment_token': revoked_token_value,
                        },
                    )
                    self.assertEqual(revoked_enroll.status_code, 403, revoked_enroll.text)
                finally:
                    client.app.dependency_overrides.pop(require_registration_allowed, None)

    def test_admin_enrollment_endpoints_are_admin_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._configure_env(tmp)

            with self._load_client() as client:
                admin = self._auth_header(client, 'admin', 'admin123')

                create_user = client.post(
                    '/api/v1/admin/users',
                    headers=admin,
                    json={
                        'username': 'analyst_enroll',
                        'password': 'AnalystPass12345!',
                        'role': 'ANALYST',
                        'is_active': True,
                        'must_reset_password': False,
                    },
                )
                self.assertEqual(create_user.status_code, 201, create_user.text)

                analyst = self._auth_header(client, 'analyst_enroll', 'AnalystPass12345!')

                denied_list = client.get('/api/v1/admin/ops/enrollment/tokens', headers=analyst)
                self.assertEqual(denied_list.status_code, 403, denied_list.text)

                denied_issue = client.post(
                    '/api/v1/admin/ops/enrollment/tokens',
                    headers=analyst,
                    json={
                        'mode': 'ONLINE',
                        'expires_in_hours': 24,
                        'max_uses': 1,
                        'reason_code': 'TESTING',
                        'reason': 'Should fail for analyst role',
                        'idempotency_key': 'enroll-rbac-001',
                        'metadata': {'source': 'rbac-test'},
                    },
                )
                self.assertEqual(denied_issue.status_code, 403, denied_issue.text)

                denied_import = client.post(
                    '/api/v1/admin/ops/enrollment/offline-kit/import',
                    headers=analyst,
                    json={'bundle': {'kit_id': 'x', 'token': {}}},
                )
                self.assertEqual(denied_import.status_code, 403, denied_import.text)

                denied_revoke = client.post(
                    '/api/v1/admin/ops/enrollment/tokens/nonexistent/revoke',
                    headers=analyst,
                    json={'reason': 'Should fail for analyst role'},
                )
                self.assertEqual(denied_revoke.status_code, 403, denied_revoke.text)


if __name__ == '__main__':
    unittest.main()
