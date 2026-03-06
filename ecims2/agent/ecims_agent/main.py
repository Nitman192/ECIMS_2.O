from __future__ import annotations

import argparse
import logging
import time

from ecims_agent.api_client import ApiClient, TLSClientConfig
from ecims_agent.config import load_config
from ecims_agent.device_adapter import select_adapter
from ecims_agent.device_control import DeviceControlManager
from ecims_agent.discovery import resolve_server_url
from ecims_agent.runtime import RuntimeLock, build_runtime_context, configure_runtime_storage
from ecims_agent.scanner import scan_paths
from ecims_agent.storage import load_state, save_state
from ecims_agent.version import AGENT_VERSION

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ecims-agent")


def _with_runtime_suffix(value: str, runtime_id: str, max_length: int) -> str:
    suffix = f"-{runtime_id}"
    if value.endswith(suffix):
        return value
    base = value
    if len(base) + len(suffix) > max_length:
        base = base[: max(1, max_length - len(suffix))]
    return f"{base}{suffix}"


def run(config_path: str, runtime_id_override: str | None = None, state_dir_override: str | None = None) -> None:
    config = load_config(config_path)
    server_url = resolve_server_url(config)
    logger.info("Server endpoint resolved: %s", server_url)
    runtime_id = runtime_id_override or config.runtime_id or config.agent_name
    state_dir = state_dir_override or config.state_dir
    runtime = build_runtime_context(state_dir=state_dir, runtime_id=runtime_id)
    configure_runtime_storage(runtime)

    runtime_lock = RuntimeLock(runtime.lock_file)
    runtime_lock.acquire()
    logger.info("Runtime initialized: id=%s state_root=%s", runtime.runtime_id, runtime.runtime_root)

    state = load_state()
    client = ApiClient(
        server_url,
        TLSClientConfig(
            cert_path=config.agent_client_cert_path,
            key_path=config.agent_client_key_path,
            pfx_path=config.agent_pfx_path,
            pfx_password=config.agent_pfx_password,
            ca_bundle_path=config.server_ca_bundle_path,
            server_cert_pin_sha256=config.server_cert_pin_sha256,
            pinning_required=config.pinning_required,
            allow_plain_https=config.allow_plain_https,
        ),
    )
    adapter = select_adapter()
    device_mgr = DeviceControlManager(
        enforcement_mode=config.device_enforcement_mode,
        failsafe_offline_minutes=config.failsafe_offline_minutes,
        token_public_key_path=config.token_public_key_path,
        local_event_queue_retention_hours=config.local_event_queue_retention_hours,
        enforcement_grace_seconds=config.enforcement_grace_seconds,
    )
    adapter.reconcile_state(config.device_enforcement_mode)

    register_name = config.agent_name
    register_hostname = config.hostname
    if runtime_id_override and runtime_id_override != (config.runtime_id or ""):
        register_name = _with_runtime_suffix(config.agent_name, runtime.runtime_id, 128)
        register_hostname = _with_runtime_suffix(config.hostname, runtime.runtime_id, 255)

    if "agent_id" not in state or "token" not in state:
        if config.enrollment_token:
            logger.info("Enrolling agent with server enrollment token")
            registered = client.enroll(register_name, register_hostname, config.enrollment_token)
        else:
            logger.info("Registering agent with server")
            registered = client.register(register_name, register_hostname)
        state["agent_id"] = registered["agent_id"]
        state["token"] = registered["token"]
        state["snapshot"] = {}
        save_state(state)

    last_cmd_poll = 0.0
    known_devices = {}

    while True:
        try:
            events, snapshot = scan_paths(config.monitored_paths, state.get("snapshot", {}))
            if events:
                client.post_events(state["agent_id"], state["token"], events)
                device_mgr.mark_server_contact()

            current_devices = {device.device_id: device for device in adapter.detect_mass_storage()}
            for device_id, device in current_devices.items():
                if device_id in known_devices:
                    continue
                known_devices[device_id] = device
                device_events = device_mgr.build_detection_events(device)
                client.post_events(state["agent_id"], state["token"], device_events)
                device_mgr.maybe_block_device(client, state["agent_id"], state["token"], adapter, device)
                device_mgr.mark_server_contact()
            known_devices = current_devices

            now = time.time()
            if now - last_cmd_poll >= config.command_poll_interval_sec:
                device_mgr.process_commands(client, state["agent_id"], state["token"], adapter, known_devices)
                client.post_device_status(
                    state["agent_id"],
                    state["token"],
                    {
                        "policy_hash_applied": device_mgr.policy_hash,
                        "enforcement_mode": device_mgr.enforcement_mode,
                        "adapter_status": "ok",
                        "last_reconcile_time": device_mgr.last_server_contact_utc.isoformat(),
                        "agent_version": AGENT_VERSION,
                        "runtime_id": runtime.runtime_id,
                        "state_root": str(runtime.runtime_root),
                    },
                )
                last_cmd_poll = now
                device_mgr.mark_server_contact()

            client.heartbeat(state["agent_id"], state["token"])
            device_mgr.mark_server_contact()
            device_mgr.flush_event_queue(client, state["agent_id"], state["token"])
            state["snapshot"] = snapshot
            save_state(state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent loop error: %s", exc)
        time.sleep(config.scan_interval_sec)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ECIMS Phase 1 Agent")
    parser.add_argument("--config", default="configs/agent.yaml", help="Path to agent yaml config")
    parser.add_argument(
        "--runtime-id",
        default=None,
        help="Unique runtime id (required for parallel local runs using same config)",
    )
    parser.add_argument(
        "--state-dir",
        default=None,
        help="Base directory for runtime state files (default from config.state_dir)",
    )
    args = parser.parse_args()
    run(args.config, runtime_id_override=args.runtime_id, state_dir_override=args.state_dir)
