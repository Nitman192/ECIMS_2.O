from __future__ import annotations

import base64
import hashlib
import logging
import socket
import ssl
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

logger = logging.getLogger(__name__)


@dataclass
class TLSClientConfig:
    cert_path: str | None = None
    key_path: str | None = None
    pfx_path: str | None = None
    pfx_password: str | None = None
    ca_bundle_path: str | None = None
    server_cert_pin_sha256: str | None = None
    pinning_required: bool = True
    allow_plain_https: bool = False


class ApiClient:
    def __init__(self, server_url: str, tls_config: TLSClientConfig | None = None):
        self.server_url = server_url.rstrip("/")
        self.tls = tls_config or TLSClientConfig()
        self.session = requests.Session()
        self._tmp_files: list[str] = []

        self._configure_tls()

    def _configure_tls(self) -> None:
        parsed = urlparse(self.server_url)
        if parsed.scheme != "https":
            if self.tls.allow_plain_https:
                self.session.verify = False
                return
            raise RuntimeError("HTTPS is required by current security policy")

        self.session.verify = self.tls.ca_bundle_path if self.tls.ca_bundle_path else True

        if self.tls.pfx_path:
            cert_path, key_path = self._extract_pfx(self.tls.pfx_path, self.tls.pfx_password)
            self.session.cert = (cert_path, key_path)
        elif self.tls.cert_path and self.tls.key_path:
            self.session.cert = (self.tls.cert_path, self.tls.key_path)

        self._check_server_pin()

    def _extract_pfx(self, pfx_path: str, password: str | None) -> tuple[str, str]:
        key, cert, _ = pkcs12.load_key_and_certificates(Path(pfx_path).read_bytes(), password.encode("utf-8") if password else None)
        if key is None or cert is None:
            raise RuntimeError("Invalid PFX content")
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_file = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".crt")
        key_file = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".key")
        cert_file.write(cert_pem)
        key_file.write(key_pem)
        cert_file.close()
        key_file.close()
        self._tmp_files.extend([cert_file.name, key_file.name])
        return cert_file.name, key_file.name

    def _check_server_pin(self) -> None:
        pin = (self.tls.server_cert_pin_sha256 or "").lower().replace(":", "")
        if not pin:
            if self.tls.pinning_required:
                raise RuntimeError("Server certificate pinning is required but no pin is configured")
            return

        parsed = urlparse(self.server_url)
        host = parsed.hostname or ""
        port = parsed.port or 443
        context = ssl.create_default_context(cafile=self.tls.ca_bundle_path) if self.tls.ca_bundle_path else ssl.create_default_context()
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as wrapped:
                cert_der = wrapped.getpeercert(binary_form=True)
        actual = hashlib.sha256(cert_der).hexdigest()
        if actual != pin:
            raise RuntimeError("Server certificate pin mismatch")

    def _client_cert_header(self) -> dict[str, str]:
        cert_path = None
        if isinstance(self.session.cert, tuple):
            cert_path = self.session.cert[0]
        elif isinstance(self.session.cert, str):
            cert_path = self.session.cert
        if not cert_path:
            return {}
        cert_pem = Path(cert_path).read_bytes()
        cert = ssl.PEM_cert_to_DER_cert(cert_pem.decode("utf-8"))
        return {"X-ECIMS-CLIENT-CERT-B64": base64.b64encode(cert).decode("ascii")}

    def register(self, name: str, hostname: str) -> dict:
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/register",
            json={"name": name, "hostname": hostname},
            headers=self._client_cert_header(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def enroll(self, name: str, hostname: str, enrollment_token: str) -> dict:
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/enroll",
            json={"name": name, "hostname": hostname, "enrollment_token": enrollment_token},
            headers=self._client_cert_header(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(self, agent_id: int, token: str) -> None:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/heartbeat",
            headers=headers,
            json={"agent_id": agent_id},
            timeout=10,
        )
        response.raise_for_status()

    def post_events(self, agent_id: int, token: str, events: list[dict]) -> dict:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/events",
            headers=headers,
            json={"agent_id": agent_id, "events": events},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Events posted: processed=%s alerts=%s", data.get("processed"), data.get("alerts_created"))
        return data

    def get_commands(self, agent_id: int, token: str) -> list[dict]:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.get(
            f"{self.server_url}/api/v1/agents/{agent_id}/commands",
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def ack_command(self, agent_id: int, token: str, command_id: int, *, applied: bool, error: str | None = None) -> None:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/{agent_id}/commands/{command_id}/ack",
            headers=headers,
            json={"applied": applied, "error": error},
            timeout=15,
        )
        response.raise_for_status()

    def post_device_status(self, agent_id: int, token: str, payload: dict) -> None:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/{agent_id}/device/status",
            headers=headers,
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

    def consume_allow_token(self, agent_id: int, token: str, allow_token: str) -> dict:
        headers = {"X-ECIMS-TOKEN": token}
        headers.update(self._client_cert_header())
        response = self.session.post(
            f"{self.server_url}/api/v1/agents/{agent_id}/device/allow-token/consume",
            headers=headers,
            json={"allow_token": allow_token},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
