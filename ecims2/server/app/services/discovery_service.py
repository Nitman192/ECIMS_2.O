from __future__ import annotations

import json
import logging
import socket
import threading
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.version import SERVER_VERSION
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

DISCOVERY_REQUEST_TYPE = "ECIMS_DISCOVERY_REQUEST"
DISCOVERY_RESPONSE_TYPE = "ECIMS_DISCOVERY_RESPONSE"

_stop_event = threading.Event()
_udp_thread: threading.Thread | None = None
_mdns_runtime: tuple[object, object] | None = None


def _normalize_service_type(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "_ecims._tcp.local."
    if not cleaned.endswith("."):
        cleaned = f"{cleaned}."
    if ".local." not in cleaned:
        cleaned = f"{cleaned}local."
    return cleaned


def _resolve_interface_ip(peer_ip: str | None = None) -> str:
    target = peer_ip or "8.8.8.8"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target, 9))
            return str(sock.getsockname()[0])
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def _build_server_url(*, sender_ip: str) -> str:
    settings = get_settings()
    explicit = settings.discovery_server_url.strip().rstrip("/")
    if explicit:
        return explicit
    scheme = "https" if settings.mtls_enabled else "http"
    host = _resolve_interface_ip(sender_ip)
    return f"{scheme}://{host}:{settings.discovery_http_port}"


def _build_response_payload(*, nonce: str, sender_ip: str) -> dict[str, object]:
    settings = get_settings()
    server_url = _build_server_url(sender_ip=sender_ip)
    parsed = urlparse(server_url)
    return {
        "type": DISCOVERY_RESPONSE_TYPE,
        "version": 1,
        "nonce": nonce,
        "server_url": server_url,
        "scheme": parsed.scheme,
        "host": parsed.hostname or "",
        "port": parsed.port or settings.discovery_http_port,
        "api_prefix": settings.api_prefix,
        "server_version": SERVER_VERSION,
        "server_time_utc": utcnow().isoformat(),
    }


def _udp_discovery_loop() -> None:
    settings = get_settings()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", int(settings.discovery_udp_port)))
        except OSError as exc:
            logger.error("Discovery UDP bind failed port=%s err=%s", settings.discovery_udp_port, exc)
            return
        sock.settimeout(1.0)
        while not _stop_event.is_set():
            try:
                raw, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                if _stop_event.is_set():
                    break
                continue

            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

            if str(payload.get("type", "")) != DISCOVERY_REQUEST_TYPE:
                continue
            nonce = str(payload.get("nonce", "")).strip()
            if not nonce:
                continue

            response = _build_response_payload(nonce=nonce, sender_ip=addr[0])
            try:
                sock.sendto(json.dumps(response, ensure_ascii=True).encode("utf-8"), addr)
            except OSError:
                continue


def _start_mdns_advertisement() -> None:
    global _mdns_runtime
    settings = get_settings()
    if not settings.discovery_mdns_enabled:
        return
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except Exception as exc:  # noqa: BLE001
        logger.warning("mDNS advertisement disabled: zeroconf unavailable (%s)", exc)
        return

    server_url = _build_server_url(sender_ip="")
    parsed = urlparse(server_url)
    host_ip = parsed.hostname or _resolve_interface_ip()
    if ":" in host_ip:
        logger.warning("mDNS advertisement currently supports IPv4 only; host=%s", host_ip)
        return

    service_type = _normalize_service_type(settings.discovery_mdns_service_type)
    service_name = f"{settings.discovery_mdns_service_name}.{service_type}"
    properties = {
        b"server_url": server_url.encode("utf-8"),
        b"scheme": parsed.scheme.encode("utf-8"),
        b"api_prefix": settings.api_prefix.encode("utf-8"),
    }
    info = ServiceInfo(
        type_=service_type,
        name=service_name,
        addresses=[socket.inet_aton(host_ip)],
        port=parsed.port or settings.discovery_http_port,
        properties=properties,
        server=f"{settings.discovery_mdns_service_name}.local.",
    )
    zeroconf = Zeroconf()
    zeroconf.register_service(info)
    _mdns_runtime = (zeroconf, info)
    logger.info("mDNS service advertised type=%s name=%s url=%s", service_type, service_name, server_url)


def _stop_mdns_advertisement() -> None:
    global _mdns_runtime
    if not _mdns_runtime:
        return
    zeroconf, info = _mdns_runtime
    try:
        zeroconf.unregister_service(info)
    except Exception:  # noqa: BLE001
        pass
    try:
        zeroconf.close()
    except Exception:  # noqa: BLE001
        pass
    _mdns_runtime = None


class DiscoveryService:
    @staticmethod
    def start() -> None:
        global _udp_thread
        settings = get_settings()
        if not settings.discovery_enabled:
            logger.info("Discovery service disabled by configuration")
            return
        if _udp_thread and _udp_thread.is_alive():
            return

        _stop_event.clear()
        _start_mdns_advertisement()
        _udp_thread = threading.Thread(target=_udp_discovery_loop, name="discovery-udp-loop", daemon=True)
        _udp_thread.start()
        logger.info("Discovery service started udp_port=%s", settings.discovery_udp_port)

    @staticmethod
    def stop(timeout_sec: float = 3.0) -> None:
        global _udp_thread
        _stop_event.set()
        if _udp_thread:
            _udp_thread.join(timeout=timeout_sec)
            _udp_thread = None
        _stop_mdns_advertisement()

