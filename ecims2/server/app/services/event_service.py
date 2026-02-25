from __future__ import annotations

import json
from typing import Any, Iterable

from pydantic import ValidationError

from app.db.database import get_db
from app.schemas.event import FileEventV1, LegacyFileEvent, SCHEMA_VERSION
from app.services.audit_service import AuditService
from app.utils.time import utcnow

SEVERITY_MAP = {
    "NEW_FILE": "AMBER",
    "FILE_MODIFIED": "RED",
    "FILE_DELETED": "RED",
}


class EventService:
    @staticmethod
    def normalize_event(raw_event: dict[str, Any], allow_legacy: bool) -> tuple[FileEventV1, bool]:
        if "schema_version" in raw_event:
            if raw_event.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"Unsupported schema_version: {raw_event.get('schema_version')}")
            try:
                return FileEventV1(**raw_event), False
            except ValidationError as exc:
                raise ValueError(str(exc)) from exc

        if not allow_legacy:
            raise ValueError("Missing schema_version")

        try:
            legacy = LegacyFileEvent(**raw_event)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

        normalized = FileEventV1(
            schema_version=SCHEMA_VERSION,
            ts=legacy.ts,
            event_type=legacy.event_type,
            file_path=legacy.file_path,
            sha256=legacy.sha256,
            file_size_bytes=None,
            mtime_epoch=None,
            user=None,
            process_name=None,
            host_ip=None,
            details_json=legacy.details_json or {},
        )
        return normalized, True

    @staticmethod
    def process_events(
        agent_id: int,
        events: Iterable[dict[str, Any]],
        *,
        allow_legacy: bool,
        baseline_update_mode: str,
    ) -> tuple[int, int]:
        processed = 0
        alerts_created = 0

        with get_db() as conn:
            for raw_event in events:
                event, legacy_used = EventService.normalize_event(raw_event, allow_legacy)
                processed += 1

                event_ts = event.normalized_ts()
                conn.execute(
                    """
                    INSERT INTO events(agent_id, ts, event_type, file_path, sha256, details_json)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_id,
                        event_ts,
                        event.event_type.value,
                        event.file_path,
                        event.sha256,
                        json.dumps(
                            {
                                "schema_version": event.schema_version,
                                "file_size_bytes": event.file_size_bytes,
                                "mtime_epoch": event.mtime_epoch,
                                "user": event.user,
                                "process_name": event.process_name,
                                "host_ip": event.host_ip,
                                "details": event.details_json,
                            }
                        ),
                    ),
                )

                if legacy_used:
                    AuditService.log(
                        conn,
                        actor_type="SYSTEM",
                        action="LEGACY_EVENT_ACCEPTED",
                        target_type="EVENT",
                        target_id=f"agent:{agent_id}",
                        message="Accepted legacy Phase 1 event and normalized to schema v1",
                        metadata={"agent_id": agent_id, "file_path": event.file_path},
                    )

                baseline = conn.execute(
                    "SELECT id, sha256 FROM baseline WHERE agent_id = ? AND file_path = ?",
                    (agent_id, event.file_path),
                ).fetchone()

                if event.event_type.value == "FILE_PRESENT":
                    if baseline is None:
                        conn.execute(
                            """
                            INSERT INTO baseline(agent_id, file_path, sha256, first_seen, last_updated)
                            VALUES(?, ?, ?, ?, ?)
                            """,
                            (agent_id, event.file_path, event.sha256, event_ts, event_ts),
                        )
                        AuditService.log(
                            conn,
                            actor_type="SYSTEM",
                            action="BASELINE_CREATED",
                            target_type="BASELINE",
                            target_id=f"{agent_id}:{event.file_path}",
                            message="Baseline created for new file",
                            metadata={"agent_id": agent_id, "file_path": event.file_path, "new_sha256": event.sha256},
                        )
                        EventService._create_alert(
                            conn,
                            agent_id,
                            event_ts,
                            "NEW_FILE",
                            event.file_path,
                            None,
                            event.sha256,
                            f"New file observed: {event.file_path}",
                        )
                        alerts_created += 1
                    elif baseline["sha256"] != event.sha256:
                        previous = baseline["sha256"]
                        if baseline_update_mode == "AUTO":
                            conn.execute(
                                "UPDATE baseline SET sha256 = ?, last_updated = ? WHERE id = ?",
                                (event.sha256, event_ts, baseline["id"]),
                            )
                            AuditService.log(
                                conn,
                                actor_type="SYSTEM",
                                action="BASELINE_UPDATED",
                                target_type="BASELINE",
                                target_id=f"{agent_id}:{event.file_path}",
                                message="Baseline updated automatically after file modification",
                                metadata={
                                    "agent_id": agent_id,
                                    "file_path": event.file_path,
                                    "previous_sha256": previous,
                                    "new_sha256": event.sha256,
                                    "mode": baseline_update_mode,
                                },
                            )

                        EventService._create_alert(
                            conn,
                            agent_id,
                            event_ts,
                            "FILE_MODIFIED",
                            event.file_path,
                            previous,
                            event.sha256,
                            f"File hash changed: {event.file_path}",
                        )
                        alerts_created += 1
                elif event.event_type.value == "FILE_DELETED":
                    previous = baseline["sha256"] if baseline else None
                    if baseline:
                        conn.execute("DELETE FROM baseline WHERE id = ?", (baseline["id"],))
                    EventService._create_alert(
                        conn,
                        agent_id,
                        event_ts,
                        "FILE_DELETED",
                        event.file_path,
                        previous,
                        None,
                        f"File deleted: {event.file_path}",
                    )
                    alerts_created += 1

        return processed, alerts_created

    @staticmethod
    def approve_baseline(agent_id: int, file_path: str, approve_sha256: str, reason: str) -> bool:
        with get_db() as conn:
            baseline = conn.execute(
                "SELECT id, sha256 FROM baseline WHERE agent_id = ? AND file_path = ?",
                (agent_id, file_path),
            ).fetchone()

            if baseline is None:
                return False

            previous = baseline["sha256"]
            conn.execute(
                "UPDATE baseline SET sha256 = ?, last_updated = ? WHERE id = ?",
                (approve_sha256, utcnow().isoformat(), baseline["id"]),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                action="BASELINE_APPROVED",
                target_type="BASELINE",
                target_id=f"{agent_id}:{file_path}",
                message="Manual baseline approval applied",
                metadata={
                    "agent_id": agent_id,
                    "file_path": file_path,
                    "previous_sha256": previous,
                    "new_sha256": approve_sha256,
                    "reason": reason,
                },
            )
            return True

    @staticmethod
    def _create_alert(
        conn,
        agent_id: int,
        ts: str,
        alert_type: str,
        file_path: str | None,
        previous_sha256: str | None,
        new_sha256: str | None,
        message: str,
    ) -> None:
        cursor = conn.execute(
            """
            INSERT INTO alerts(agent_id, ts, alert_type, severity, file_path, previous_sha256, new_sha256, message, status)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """,
            (
                agent_id,
                ts,
                alert_type,
                SEVERITY_MAP[alert_type],
                file_path,
                previous_sha256,
                new_sha256,
                message,
            ),
        )
        AuditService.log(
            conn,
            actor_type="SYSTEM",
            action="ALERT_CREATED",
            target_type="ALERT",
            target_id=cursor.lastrowid,
            message=message,
            metadata={
                "agent_id": agent_id,
                "alert_type": alert_type,
                "file_path": file_path,
                "previous_sha256": previous_sha256,
                "new_sha256": new_sha256,
            },
        )
