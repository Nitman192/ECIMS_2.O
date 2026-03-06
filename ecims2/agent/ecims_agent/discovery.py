from __future__ import annotations

import json
import logging
import socket
import time
import uuid
from collections.abc import Iterable
from urllib.parse import urlparse

import requests

from ecims_agent.config import AgentConfig

logger = logging.getLogger(__name__)

DISCOVERY_REQUEST_TYPE = "ECIMS_DISCOVERY_REQUEST"
DISCOVERY_RESPONSE_TYPE = "ECIMS_DISCOVERY_RESPONSE"
DEFAULT_DISCOVERY_PORT = 40110


def resolve_server_url(config: AgentConfig) -> str:
    configured_url = _normalize_server_url(config.server_url)
    if not config.auto_discovery_enabled:
        if configured_url:
            return configured_url
        raise RuntimeError("server_url is empty and auto discovery is disabled")

    candidate_urls: list[str] = []
    if configured_url:
        candidate_urls.append(configured_url)
    if config.discovery_mdns_enabled:
        candidate_urls.extend(_discover_via_mdns(config.discovery_mdns_service_type, config.discovery_timeout_sec))
    if config.discovery_lan_broadcast_enabled:
        candidate_urls.extend(
            _discover_via_udp_broadcast(
                timeout_sec=config.discovery_timeout_sec,
                udp_port=config.discovery_udp_port or DEFAULT_DISCOVERY_PORT,
                targets=config.discovery_broadcast_targets,
            )
        )

    unique_urls = _dedupe(candidate_urls)
    if unique_urls:
        logger.info("Discovery candidates: %s", ", ".join(unique_urls))

    for url in unique_urls:
        if _probe_health(url, config, timeout_sec=config.discovery_timeout_sec):
            return url

    if configured_url:
        logger.warning("Discovery probe failed; falling back to configured server_url=%s", configured_url)
        return configured_url

    raise RuntimeError(
        "Unable to discover ECIMS server via configured methods. "
        "Set server_url explicitly or ensure discovery service is reachable."
    )


def _discover_via_udp_broadcast(*, timeout_sec: int, udp_port: int, targets: Iterable[str]) -> list[str]:
    nonce = uuid.uuid4().hex
    request_payload = json.dumps(
        {
            "type": DISCOVERY_REQUEST_TYPE,
            "version": 1,
            "nonce": nonce,
        },
        ensure_ascii=True,
    ).encode("utf-8")

    discovered: list[str] = []
    deadline = time.monotonic() + max(1, int(timeout_sec))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 0))
        sock.settimeout(0.3)

        for target in _dedupe([str(item).strip() for item in targets if str(item).strip()]):
            try:
                sock.sendto(request_payload, (target, int(udp_port)))
            except OSError as exc:
                logger.debug("UDP discovery send failed target=%s port=%s err=%s", target, udp_port, exc)

        while time.monotonic() < deadline:
            try:
                raw, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                logger.debug("UDP discovery receive failed: %s", exc)
                break
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if str(payload.get("nonce", "")) != nonce:
                continue
            candidate = _candidate_from_payload(payload, sender_ip=addr[0])
            if candidate:
                discovered.append(candidate)
    return _dedupe(discovered)


def _discover_via_mdns(service_type: str, timeout_sec: int) -> list[str]:
    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    except Exception as exc:  # noqa: BLE001
        logger.debug("mDNS discovery unavailable (zeroconf not installed): %s", exc)
        return []

    normalized_type = _normalize_service_type(service_type)
    discovered: list[str] = []

    class _Listener(ServiceListener):
        def add_service(self, zeroconf, type_, name):  # type: ignore[no-untyped-def]
            info = zeroconf.get_service_info(type_, name, timeout=1000)
            if not info:
                return
            discovered.extend(_urls_from_mdns_info(info))

        def update_service(self, zeroconf, type_, name):  # type: ignore[no-untyped-def]
            self.add_service(zeroconf, type_, name)

        def remove_service(self, zeroconf, type_, name):  # type: ignore[no-untyped-def]
            return None

    zeroconf = Zeroconf()
    try:
        ServiceBrowser(zeroconf, normalized_type, _Listener())
        time.sleep(max(1, int(timeout_sec)))
    finally:
        zeroconf.close()
    return _dedupe(discovered)


def _urls_from_mdns_info(info: object) -> list[str]:
    properties = getattr(info, "properties", {}) or {}
    raw_url = _decode_mdns_property(properties, b"server_url")
    if raw_url:
        normalized = _normalize_server_url(raw_url)
        return [normalized] if normalized else []

    scheme = _decode_mdns_property(properties, b"scheme") or "https"
    port = int(getattr(info, "port", 0) or 0)
    if port <= 0:
        return []

    addresses: list[str] = []
    parsed = getattr(info, "parsed_addresses", None)
    if callable(parsed):
        try:
            addresses = [str(item).strip() for item in parsed() if str(item).strip()]
        except Exception:  # noqa: BLE001
            addresses = []

    urls = []
    for address in addresses:
        if ":" in address:
            continue
        host = _format_host_for_url(address)
        urls.append(_normalize_server_url(f"{scheme}://{host}:{port}"))
    return [item for item in urls if item]


def _candidate_from_payload(payload: dict, *, sender_ip: str) -> str | None:
    if str(payload.get("type", "")) != DISCOVERY_RESPONSE_TYPE:
        return None

    server_url = _normalize_server_url(str(payload.get("server_url", "")))
    if server_url:
        return server_url

    scheme = str(payload.get("scheme", "http")).strip().lower() or "http"
    host = str(payload.get("host", "")).strip() or sender_ip
    try:
        port = int(payload.get("port") or 8010)
    except (TypeError, ValueError):
        return None
    return _normalize_server_url(f"{scheme}://{_format_host_for_url(host)}:{port}")


def _probe_health(server_url: str, config: AgentConfig, *, timeout_sec: int) -> bool:
    parsed = urlparse(server_url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.scheme == "http" and not config.allow_plain_https:
        return False

    verify: str | bool = True
    if parsed.scheme == "https" and config.server_ca_bundle_path:
        verify = config.server_ca_bundle_path
    if parsed.scheme == "http":
        verify = False

    try:
        response = requests.get(f"{server_url}/health", timeout=max(1, int(timeout_sec)), verify=verify)
    except Exception:  # noqa: BLE001
        return False
    return response.status_code == 200


def _normalize_server_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    if not candidate:
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return candidate


def _normalize_service_type(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "_ecims._tcp.local."
    if not cleaned.endswith("."):
        cleaned = f"{cleaned}."
    if ".local." not in cleaned:
        cleaned = f"{cleaned}local."
    return cleaned


def _decode_mdns_property(properties: dict, key: bytes) -> str:
    raw = properties.get(key)
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore").strip()
    return str(raw).strip()


def _format_host_for_url(host: str) -> str:
    value = host.strip()
    if ":" in value and not value.startswith("["):
        return f"[{value}]"
    return value


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered

