from __future__ import annotations

import unittest


class TestCryptoDependency(unittest.TestCase):
    def test_cryptography_import_available(self) -> None:
        try:
            import cryptography  # noqa: F401
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.fail(
                "cryptography package is missing. Install server dependencies via: "
                "pip install -r server/requirements.txt or offline_bundle/install_offline.sh"
            )


if __name__ == "__main__":
    unittest.main()
