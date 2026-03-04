from __future__ import annotations

import base64
import importlib
import json
import os
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi.testclient import TestClient

from app.db.database import get_db
from app.utils.time import utcnow


class TestPhase12BackgroundScheduler(unittest.TestCase):
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
            'license_id': 'LIC-P12-BG-001',
            'max_agents': 100,
            'expiry_date': (date.today() + timedelta(days=30)).isoformat(),
            'ai_enabled': True,
        }
        sig = private_key.sign(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8'),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        lic = td / 'license.ecims'
        lic.write_text(
            json.dumps({'payload': payload, 'signature_b64': base64.b64encode(sig).decode('ascii')}),
            encoding='utf-8',
        )
        return lic, public_path

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

    def _insert_agent(self, name: str, hostname: str, token: str) -> int:
        with get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents(name, hostname, token, registered_at, last_seen, status, agent_revoked, revoked_at, revocation_reason)
                VALUES(?, ?, ?, ?, ?, 'ONLINE', 0, NULL, NULL)
                """,
                (name, hostname, token, utcnow().isoformat(), utcnow().isoformat()),
            )
            return int(cursor.lastrowid)

    def test_background_scheduler_runs_due_windows_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lic, pub = self._make_license(tmp)
            os.environ['ECIMS_DB_PATH'] = str(tmp / 'db.sqlite')
            os.environ['ECIMS_LICENSE_PATH'] = str(lic)
            os.environ['ECIMS_LICENSE_PUBLIC_KEY_PATH'] = str(pub)
            os.environ['ECIMS_MTLS_REQUIRED'] = 'false'
            os.environ['ECIMS_MTLS_ENABLED'] = 'false'
            os.environ['ECIMS_MAINTENANCE_SCHEDULER_ENABLED'] = 'true'
            os.environ['ECIMS_MAINTENANCE_SCHEDULER_INTERVAL_SEC'] = '1'
            os.environ['ECIMS_MAINTENANCE_SCHEDULER_BATCH_LIMIT'] = '20'

            with self._load_client() as client:
                admin = self._auth_header(client, 'admin', 'admin123')
                agent_id = self._insert_agent('sched-bg-a1', 'sched-bg-h1', 'tok-sched-bg-a1')

                created = client.post(
                    '/api/v1/admin/ops/schedules',
                    headers=admin,
                    json={
                        'window_name': 'Auto Runner Window',
                        'timezone': 'UTC',
                        'start_time_local': '04:00',
                        'duration_minutes': 60,
                        'recurrence': 'DAILY',
                        'weekly_days': [],
                        'target_agent_ids': [agent_id],
                        'orchestration_mode': 'RESTART_ONLY',
                        'status': 'ACTIVE',
                        'reason_code': 'MAINTENANCE',
                        'reason': 'Automatic background runner test',
                        'allow_conflicts': True,
                        'idempotency_key': 'sched-bg-idem-001',
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                schedule_id = int(created.json()['item']['id'])

                with get_db() as conn:
                    conn.execute(
                        'UPDATE maintenance_schedules SET next_run_at = ? WHERE id = ?',
                        ((utcnow() - timedelta(minutes=1)).isoformat(), schedule_id),
                    )

                run_count = 0
                for _ in range(12):
                    time.sleep(0.5)
                    with get_db() as conn:
                        run_row = conn.execute(
                            'SELECT COUNT(*) AS c FROM maintenance_schedule_runs WHERE schedule_id = ?',
                            (schedule_id,),
                        ).fetchone()
                        run_count = int(run_row['c'] if run_row else 0)
                    if run_count > 0:
                        break

                self.assertGreaterEqual(run_count, 1)

                listed = client.get('/api/v1/admin/ops/schedules', headers=admin, params={'q': str(schedule_id)})
                self.assertEqual(listed.status_code, 200, listed.text)
                self.assertGreaterEqual(int(listed.json()['total']), 1)
                self.assertIsNotNone(listed.json()['items'][0]['last_run_at'])


if __name__ == '__main__':
    unittest.main()
