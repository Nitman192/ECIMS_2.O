from __future__ import annotations

import argparse
import logging
import time

from ecims_agent.api_client import ApiClient
from ecims_agent.config import load_config
from ecims_agent.scanner import scan_paths
from ecims_agent.storage import load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ecims-agent")


def run(config_path: str) -> None:
    config = load_config(config_path)
    state = load_state()
    client = ApiClient(config.server_url)

    if "agent_id" not in state or "token" not in state:
        logger.info("Registering agent with server")
        registered = client.register(config.agent_name, config.hostname)
        state["agent_id"] = registered["agent_id"]
        state["token"] = registered["token"]
        state["snapshot"] = {}
        save_state(state)

    while True:
        try:
            events, snapshot = scan_paths(config.monitored_paths, state.get("snapshot", {}))
            if events:
                client.post_events(state["agent_id"], state["token"], events)
            client.heartbeat(state["agent_id"], state["token"])
            state["snapshot"] = snapshot
            save_state(state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Agent loop error: %s", exc)
        time.sleep(config.scan_interval_sec)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ECIMS Phase 1 Agent")
    parser.add_argument("--config", default="configs/agent.yaml", help="Path to agent yaml config")
    args = parser.parse_args()
    run(args.config)
