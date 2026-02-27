from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from ecims_agent.api_client import ApiClient, TLSClientConfig
except Exception as _dep_exc:  # noqa: BLE001
    ApiClient = None  # type: ignore[assignment]
    TLSClientConfig = None  # type: ignore[assignment]
    _CLIENT_IMPORT_ERR = _dep_exc
else:
    _CLIENT_IMPORT_ERR = None


class TestAgentTLSClient(unittest.TestCase):
    def setUp(self) -> None:
        if _CLIENT_IMPORT_ERR is not None:
            raise unittest.SkipTest(f"agent client deps unavailable: {_CLIENT_IMPORT_ERR}")

    @patch("ecims_agent.api_client.socket.create_connection")
    @patch("ecims_agent.api_client.ssl.create_default_context")
    def test_pinning_mismatch_raises(self, mock_ctx, mock_conn) -> None:
        wrapped = mock_ctx.return_value.wrap_socket.return_value.__enter__.return_value
        wrapped.getpeercert.return_value = b"cert-bytes"
        expected_pin = "00" * 32

        with self.assertRaises(RuntimeError):
            ApiClient(
                "https://server.local",
                TLSClientConfig(server_cert_pin_sha256=expected_pin, pinning_required=True),
            )

    def test_http_blocked_when_plain_not_allowed(self) -> None:
        with self.assertRaises(RuntimeError):
            ApiClient("http://127.0.0.1:8000", TLSClientConfig(pinning_required=False, allow_plain_https=False))


if __name__ == "__main__":
    unittest.main()
