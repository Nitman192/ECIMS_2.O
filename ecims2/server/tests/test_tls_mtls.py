from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.security.mtls import is_mtls_enabled, validate_client_certificate_subject
from app.security.tls import create_server_ssl_context


class TestTLSMTLS(unittest.TestCase):
    def test_validate_client_certificate_subject(self) -> None:
        subject = ((("countryName", "IN"),), (("commonName", "ecims-agent"),))
        self.assertTrue(validate_client_certificate_subject(subject, "ecims-agent"))
        self.assertFalse(validate_client_certificate_subject(subject, "other-agent"))

    def test_is_mtls_enabled(self) -> None:
        os.environ["ECIMS_MTLS_ENABLED"] = "true"
        self.assertTrue(is_mtls_enabled())
        os.environ["ECIMS_MTLS_ENABLED"] = "false"
        self.assertFalse(is_mtls_enabled())
        os.environ.pop("ECIMS_MTLS_ENABLED", None)

    def test_create_server_ssl_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cert = Path(temp_dir) / "server.crt"
            key = Path(temp_dir) / "server.key"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(key),
                    "-out",
                    str(cert),
                    "-days",
                    "1",
                    "-subj",
                    "/CN=localhost",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ctx = create_server_ssl_context(str(cert), str(key), require_client_cert=False)
            self.assertIsNotNone(ctx)


if __name__ == "__main__":
    unittest.main()
