from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.core.config import get_settings


class TestConfigLoader(unittest.TestCase):
    def test_loads_server_yaml_and_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_override = Path(temp_dir) / "config_test.db"
            os.environ["ECIMS_DB_PATH"] = str(db_override)
            os.environ["ECIMS_DISCOVERY_ENABLED"] = "true"
            os.environ["ECIMS_DISCOVERY_SERVER_URL"] = "http://127.0.0.1:8010"
            get_settings.cache_clear()

            settings = get_settings()

            self.assertEqual(settings.app_name, "ECIMS 2.0 Server")
            self.assertEqual(settings.db_path, str(db_override))
            self.assertGreaterEqual(settings.event_batch_limit, 1)
            self.assertTrue(settings.discovery_enabled)
            self.assertEqual(settings.discovery_server_url, "http://127.0.0.1:8010")

            get_settings.cache_clear()
            os.environ.pop("ECIMS_DB_PATH", None)
            os.environ.pop("ECIMS_DISCOVERY_ENABLED", None)
            os.environ.pop("ECIMS_DISCOVERY_SERVER_URL", None)


if __name__ == "__main__":
    unittest.main()
