from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")

    def register(self, name: str, hostname: str) -> dict:
        response = requests.post(
            f"{self.server_url}/api/v1/agents/register",
            json={"name": name, "hostname": hostname},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(self, agent_id: int, token: str) -> None:
        response = requests.post(
            f"{self.server_url}/api/v1/agents/heartbeat",
            headers={"X-ECIMS-TOKEN": token},
            json={"agent_id": agent_id},
            timeout=10,
        )
        response.raise_for_status()

    def post_events(self, agent_id: int, token: str, events: list[dict]) -> dict:
        response = requests.post(
            f"{self.server_url}/api/v1/agents/events",
            headers={"X-ECIMS-TOKEN": token},
            json={"agent_id": agent_id, "events": events},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Events posted: processed=%s alerts=%s", data.get("processed"), data.get("alerts_created"))
        return data
