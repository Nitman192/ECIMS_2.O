from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.services.remote_action_task_service import RemoteActionTaskService
from app.utils.time import utcnow


class MaintenanceScheduleService:
    VALID_RECURRENCE = {"DAILY", "WEEKLY"}
    VALID_STATUS = {"DRAFT", "ACTIVE", "PAUSED"}
    VALID_MODES = {"SAFE_SHUTDOWN_START", "SHUTDOWN_ONLY", "RESTART_ONLY", "POLICY_PUSH_ONLY"}
    VALID_REASON_CODES = {"MAINTENANCE", "COMPLIANCE", "INCIDENT_RESPONSE", "TESTING", "ROLLBACK", "POLICY_CHANGE"}
    CONFLICT_STATES = {"DRAFT", "ACTIVE"}

    @staticmethod
    def list_schedules(*, page: int, page_size: int, status_filter: str | None, timezone_filter: str | None, query: str | None) -> dict:
        where: list[str] = []
        params: list[object] = []

        if status_filter and status_filter.strip().upper() != "ALL":
            normalized_status = status_filter.strip().upper()
            if normalized_status not in MaintenanceScheduleService.VALID_STATUS:
                raise ValueError("INVALID_STATUS")
            where.append("s.status = ?")
            params.append(normalized_status)

        if timezone_filter and timezone_filter.strip().lower() != "all":
            where.append("lower(s.timezone) = ?")
            params.append(timezone_filter.strip().lower())

        if query and query.strip():
            q = query.strip()
            term = f"%{q.lower()}%"
            if q.isdigit():
                where.append("(lower(s.window_name) LIKE ? OR lower(s.reason) LIKE ? OR s.id = ?)")
                params.extend([term, term, int(q)])
            else:
                where.append("(lower(s.window_name) LIKE ? OR lower(s.reason) LIKE ?)")
                params.extend([term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM maintenance_schedules s {where_sql}",
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT s.*, u.username AS created_by_username, uu.username AS updated_by_username
                FROM maintenance_schedules s
                LEFT JOIN users u ON u.id = s.created_by_user_id
                LEFT JOIN users uu ON uu.id = s.updated_by_user_id
                {where_sql}
                ORDER BY s.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()

            items: list[dict] = []
            for row in rows:
                item = MaintenanceScheduleService._row_to_schedule(row)
                conflicts = MaintenanceScheduleService._detect_conflicts_with_conn(
                    conn,
                    candidate=item,
                    ignore_schedule_id=item["id"],
                    include_states=MaintenanceScheduleService.CONFLICT_STATES,
                    max_results=5,
                )
                item["conflict_count"] = len(conflicts)
                item["has_conflict"] = len(conflicts) > 0
                items.append(item)

        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def preview_schedule(
        *,
        window_name: str,
        timezone_name: str,
        start_time_local: str,
        duration_minutes: int,
        recurrence: str,
        weekly_days: list[int],
        target_agent_ids: list[int],
        orchestration_mode: str,
        metadata: dict | None,
        ignore_schedule_id: int | None = None,
    ) -> dict:
        candidate = MaintenanceScheduleService._normalize_candidate(
            window_name=window_name,
            timezone_name=timezone_name,
            start_time_local=start_time_local,
            duration_minutes=duration_minutes,
            recurrence=recurrence,
            weekly_days=weekly_days,
            target_agent_ids=target_agent_ids,
            orchestration_mode=orchestration_mode,
            metadata=metadata,
        )
        next_runs = MaintenanceScheduleService._preview_next_runs(candidate, count=5)
        with get_db() as conn:
            conflicts = MaintenanceScheduleService._detect_conflicts_with_conn(
                conn,
                candidate=candidate,
                ignore_schedule_id=ignore_schedule_id,
                include_states=MaintenanceScheduleService.CONFLICT_STATES,
                max_results=20,
            )
        return {"next_runs": next_runs, "conflicts": conflicts, "conflict_count": len(conflicts)}

    @staticmethod
    def create_schedule(
        *,
        window_name: str,
        timezone_name: str,
        start_time_local: str,
        duration_minutes: int,
        recurrence: str,
        weekly_days: list[int],
        target_agent_ids: list[int],
        orchestration_mode: str,
        status_value: str,
        reason_code: str,
        reason: str,
        allow_conflicts: bool,
        idempotency_key: str,
        metadata: dict | None,
        actor_id: int,
    ) -> tuple[dict, bool]:
        candidate = MaintenanceScheduleService._normalize_candidate(
            window_name=window_name,
            timezone_name=timezone_name,
            start_time_local=start_time_local,
            duration_minutes=duration_minutes,
            recurrence=recurrence,
            weekly_days=weekly_days,
            target_agent_ids=target_agent_ids,
            orchestration_mode=orchestration_mode,
            metadata=metadata,
        )

        normalized_status = status_value.strip().upper()
        if normalized_status not in MaintenanceScheduleService.VALID_STATUS:
            raise ValueError("INVALID_STATUS")

        normalized_reason_code = reason_code.strip().upper()
        if normalized_reason_code not in MaintenanceScheduleService.VALID_REASON_CODES:
            raise ValueError("INVALID_REASON_CODE")

        idem = idempotency_key.strip()
        if len(idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        req_hash = MaintenanceScheduleService._create_request_hash(
            candidate=candidate,
            status_value=normalized_status,
            reason_code=normalized_reason_code,
            reason=reason.strip(),
        )
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id, request_hash FROM maintenance_schedules WHERE create_idempotency_key = ?",
                (idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != req_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = MaintenanceScheduleService._get_schedule_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("SCHEDULE_NOT_FOUND")
                return item, False

            conflicts = MaintenanceScheduleService._detect_conflicts_with_conn(
                conn,
                candidate=candidate,
                ignore_schedule_id=None,
                include_states=MaintenanceScheduleService.CONFLICT_STATES,
                max_results=50,
            )
            if conflicts and not allow_conflicts:
                ids = ",".join(str(item["schedule_id"]) for item in conflicts[:10])
                raise ValueError(f"CONFLICT_DETECTED:{ids}")

            next_run_at = None
            if normalized_status == "ACTIVE":
                nxt = MaintenanceScheduleService._next_run_after(candidate, after_utc=utcnow())
                next_run_at = nxt.isoformat() if nxt else None

            cursor = conn.execute(
                """
                INSERT INTO maintenance_schedules(
                    window_name, timezone, start_time_local, duration_minutes, recurrence, weekly_days_json,
                    target_agent_ids_json, orchestration_mode, status, reason_code, reason, create_idempotency_key,
                    request_hash, next_run_at, last_run_at, metadata_json, created_by_user_id, updated_by_user_id,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    candidate["window_name"],
                    candidate["timezone"],
                    candidate["start_time_local"],
                    candidate["duration_minutes"],
                    candidate["recurrence"],
                    json.dumps(candidate["weekly_days"]),
                    json.dumps(candidate["target_agent_ids"]),
                    candidate["orchestration_mode"],
                    normalized_status,
                    normalized_reason_code,
                    reason.strip(),
                    idem,
                    req_hash,
                    next_run_at,
                    candidate["metadata_json"],
                    actor_id,
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )
            schedule_id = int(cursor.lastrowid)
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="MAINTENANCE_SCHEDULE_CREATED",
                target_type="MAINTENANCE_SCHEDULE",
                target_id=schedule_id,
                message="Maintenance schedule created",
                metadata={"window_name": candidate["window_name"], "status": normalized_status, "conflict_count": len(conflicts)},
            )
            created = MaintenanceScheduleService._get_schedule_with_conn(conn, schedule_id)
            if not created:
                raise ValueError("SCHEDULE_NOT_FOUND")
            return created, True

    @staticmethod
    def update_schedule_state(*, schedule_id: int, status_value: str, reason: str, actor_id: int) -> dict | None:
        normalized_status = status_value.strip().upper()
        if normalized_status not in MaintenanceScheduleService.VALID_STATUS:
            raise ValueError("INVALID_STATUS")

        with get_db() as conn:
            row = conn.execute("SELECT * FROM maintenance_schedules WHERE id = ?", (schedule_id,)).fetchone()
            if not row:
                return None
            previous = str(row["status"])
            schedule = MaintenanceScheduleService._row_to_schedule(row)

            next_run_at = row["next_run_at"]
            if normalized_status == "ACTIVE":
                nxt = MaintenanceScheduleService._next_run_after(schedule, after_utc=utcnow())
                next_run_at = nxt.isoformat() if nxt else None

            now_iso = utcnow().isoformat()
            conn.execute(
                "UPDATE maintenance_schedules SET status = ?, next_run_at = ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
                (normalized_status, next_run_at, actor_id, now_iso, schedule_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="MAINTENANCE_SCHEDULE_STATE_UPDATED" if previous != normalized_status else "MAINTENANCE_SCHEDULE_STATE_NOOP",
                target_type="MAINTENANCE_SCHEDULE",
                target_id=schedule_id,
                message="Maintenance schedule state changed",
                metadata={"previous_status": previous, "new_status": normalized_status, "reason": reason.strip()},
            )
            return MaintenanceScheduleService._get_schedule_with_conn(conn, schedule_id)

    @staticmethod
    def get_schedule(schedule_id: int) -> dict | None:
        with get_db() as conn:
            return MaintenanceScheduleService._get_schedule_with_conn(conn, schedule_id)

    @staticmethod
    def get_schedule_conflicts(schedule_id: int) -> list[dict]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM maintenance_schedules WHERE id = ?", (schedule_id,)).fetchone()
            if not row:
                raise ValueError("SCHEDULE_NOT_FOUND")
            candidate = MaintenanceScheduleService._row_to_schedule(row)
            return MaintenanceScheduleService._detect_conflicts_with_conn(
                conn,
                candidate=candidate,
                ignore_schedule_id=schedule_id,
                include_states=MaintenanceScheduleService.CONFLICT_STATES,
                max_results=50,
            )

    @staticmethod
    def run_due_schedules(*, actor_id: int, limit: int = 20) -> dict:
        due_rows: list[dict] = []
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM maintenance_schedules
                WHERE status = 'ACTIVE' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                LIMIT ?
                """,
                (utcnow().isoformat(), limit),
            ).fetchall()
            due_rows = [dict(row) for row in rows]

        result_items: list[dict] = []
        executed = 0
        failed = 0
        tasks_dispatched = 0

        for row_dict in due_rows:
            schedule = MaintenanceScheduleService._row_to_schedule(row_dict)
            run_stamp = (schedule.get("next_run_at") or utcnow().isoformat()).replace(":", "").replace("-", "")
            run_key = f"schedule-{schedule['id']}-{run_stamp}"
            with get_db() as conn:
                already = conn.execute("SELECT id FROM maintenance_schedule_runs WHERE run_key = ?", (run_key,)).fetchone()
                if already:
                    continue
                run_cursor = conn.execute(
                    """
                    INSERT INTO maintenance_schedule_runs(schedule_id, run_key, status, started_at, finished_at, dispatched_task_ids_json, details_json, error)
                    VALUES(?, ?, 'RUNNING', ?, NULL, '[]', '{}', NULL)
                    """,
                    (schedule["id"], run_key, utcnow().isoformat()),
                )
                run_id = int(run_cursor.lastrowid)

            stage_task_ids: list[int] = []
            errors: list[str] = []
            for idx, stage in enumerate(MaintenanceScheduleService._orchestration_stages(schedule["orchestration_mode"]), start=1):
                try:
                    task, _ = RemoteActionTaskService.create_task(
                        action=stage["action"],
                        agent_ids=list(schedule["target_agent_ids"]),
                        idempotency_key=f"{run_key}-stage-{idx}",
                        reason_code="MAINTENANCE",
                        reason=f"{schedule['window_name']} · {stage['phase']}",
                        confirm_high_risk=bool(stage["high_risk"]),
                        metadata={
                            "schedule_id": schedule["id"],
                            "run_key": run_key,
                            "phase": stage["phase"],
                            "orchestration_mode": schedule["orchestration_mode"],
                        },
                        actor_id=actor_id,
                    )
                    stage_task_ids.append(int(task["id"]))
                    tasks_dispatched += 1
                except ValueError as exc:
                    errors.append(str(exc))
                    break

            run_status = "FAILED" if errors else "DONE"
            if run_status == "DONE":
                executed += 1
            else:
                failed += 1

            next_after = utcnow()
            if schedule.get("next_run_at"):
                try:
                    next_after = datetime.fromisoformat(str(schedule["next_run_at"])).astimezone(timezone.utc)
                except Exception:
                    next_after = utcnow()
            nxt = MaintenanceScheduleService._next_run_after(schedule, after_utc=next_after)
            next_run_at = nxt.isoformat() if nxt else None

            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE maintenance_schedule_runs
                    SET status = ?, finished_at = ?, dispatched_task_ids_json = ?, details_json = ?, error = ?
                    WHERE run_key = ?
                    """,
                    (
                        run_status,
                        utcnow().isoformat(),
                        json.dumps(stage_task_ids),
                        json.dumps({"completed_stages": len(stage_task_ids)}),
                        "; ".join(errors) if errors else None,
                        run_key,
                    ),
                )
                conn.execute(
                    "UPDATE maintenance_schedules SET last_run_at = ?, next_run_at = ?, updated_by_user_id = ?, updated_at = ? WHERE id = ?",
                    (utcnow().isoformat(), next_run_at, actor_id, utcnow().isoformat(), schedule["id"]),
                )
                AuditService.log(
                    conn,
                    actor_type="SYSTEM",
                    action="MAINTENANCE_SCHEDULE_RUN_COMPLETED" if run_status == "DONE" else "MAINTENANCE_SCHEDULE_RUN_FAILED",
                    target_type="MAINTENANCE_SCHEDULE_RUN",
                    target_id=run_id,
                    message="Maintenance schedule run finished",
                    metadata={"schedule_id": schedule["id"], "run_key": run_key, "task_ids": stage_task_ids, "errors": errors},
                )

            result_items.append({"schedule_id": schedule["id"], "run_key": run_key, "status": run_status, "task_ids": stage_task_ids, "errors": errors})

        return {
            "due_count": len(due_rows),
            "executed_count": executed,
            "failed_count": failed,
            "tasks_dispatched": tasks_dispatched,
            "items": result_items,
        }

    @staticmethod
    def _normalize_candidate(
        *,
        window_name: str,
        timezone_name: str,
        start_time_local: str,
        duration_minutes: int,
        recurrence: str,
        weekly_days: list[int],
        target_agent_ids: list[int],
        orchestration_mode: str,
        metadata: dict | None,
    ) -> dict:
        name = window_name.strip()
        tz_name = timezone_name.strip()
        if not name:
            raise ValueError("INVALID_WINDOW_NAME")
        MaintenanceScheduleService._validate_timezone(tz_name)
        MaintenanceScheduleService._validate_time(start_time_local)

        rec = recurrence.strip().upper()
        if rec not in MaintenanceScheduleService.VALID_RECURRENCE:
            raise ValueError("INVALID_RECURRENCE")

        mode = orchestration_mode.strip().upper()
        if mode not in MaintenanceScheduleService.VALID_MODES:
            raise ValueError("INVALID_ORCHESTRATION_MODE")

        duration = int(duration_minutes)
        if duration < 15 or duration > 1440:
            raise ValueError("INVALID_DURATION")

        days = MaintenanceScheduleService._normalize_weekly_days(rec=rec, weekly_days=weekly_days)
        targets = MaintenanceScheduleService._validate_target_agents(target_agent_ids)

        return {
            "window_name": name,
            "timezone": tz_name,
            "start_time_local": start_time_local,
            "duration_minutes": duration,
            "recurrence": rec,
            "weekly_days": days,
            "target_agent_ids": targets,
            "orchestration_mode": mode,
            "metadata": metadata or {},
            "metadata_json": json.dumps(metadata or {}, sort_keys=True),
        }

    @staticmethod
    def _validate_target_agents(agent_ids: list[int]) -> list[int]:
        deduped = sorted({int(agent_id) for agent_id in agent_ids if int(agent_id) > 0})
        if not deduped:
            raise ValueError("INVALID_AGENT_IDS")
        if len(deduped) > 100:
            raise ValueError("BATCH_TOO_LARGE")

        with get_db() as conn:
            rows = conn.execute(
                f"SELECT id, agent_revoked FROM agents WHERE id IN ({','.join('?' for _ in deduped)})",
                tuple(deduped),
            ).fetchall()
        found = {int(row["id"]) for row in rows}
        missing = sorted(set(deduped) - found)
        if missing:
            raise ValueError(f"MISSING_AGENTS:{','.join(str(item) for item in missing)}")
        revoked = sorted(int(row["id"]) for row in rows if bool(row["agent_revoked"]))
        if revoked:
            raise ValueError(f"REVOKED_AGENTS:{','.join(str(item) for item in revoked)}")
        return deduped

    @staticmethod
    def _normalize_weekly_days(*, rec: str, weekly_days: list[int]) -> list[int]:
        if rec == "DAILY":
            return []
        days = sorted({int(day) for day in weekly_days})
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError("INVALID_WEEKLY_DAYS")
        return days

    @staticmethod
    def _validate_timezone(timezone_name: str) -> None:
        MaintenanceScheduleService._get_tzinfo(timezone_name)

    @staticmethod
    def _validate_time(value: str) -> None:
        if len(value) != 5 or value[2] != ":":
            raise ValueError("INVALID_TIME_FORMAT")
        try:
            hour = int(value[:2])
            minute = int(value[3:5])
        except Exception as exc:
            raise ValueError("INVALID_TIME_FORMAT") from exc
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("INVALID_TIME_FORMAT")

    @staticmethod
    def _next_run_after(candidate: dict, *, after_utc: datetime) -> datetime | None:
        tz = MaintenanceScheduleService._get_tzinfo(candidate["timezone"])
        hour, minute = map(int, candidate["start_time_local"].split(":"))
        local_after = after_utc.astimezone(tz)

        for offset in range(0, 21):
            day = local_after.date() + timedelta(days=offset)
            if candidate["recurrence"] == "WEEKLY" and day.weekday() not in candidate["weekly_days"]:
                continue
            run_local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            if run_local <= local_after:
                continue
            return run_local.astimezone(timezone.utc)
        return None

    @staticmethod
    def _preview_next_runs(candidate: dict, *, count: int) -> list[dict]:
        out: list[dict] = []
        cursor = utcnow()
        duration = timedelta(minutes=int(candidate["duration_minutes"]))
        tz = MaintenanceScheduleService._get_tzinfo(candidate["timezone"])
        for _ in range(count):
            nxt = MaintenanceScheduleService._next_run_after(candidate, after_utc=cursor)
            if not nxt:
                break
            local_start = nxt.astimezone(tz)
            out.append(
                {
                    "run_at_utc": nxt.isoformat(),
                    "run_at_local": local_start.isoformat(),
                    "window_end_utc": (nxt + duration).isoformat(),
                    "window_end_local": (local_start + duration).isoformat(),
                }
            )
            cursor = nxt + timedelta(seconds=1)
        return out

    @staticmethod
    def _detect_conflicts_with_conn(conn, *, candidate: dict, ignore_schedule_id: int | None, include_states: set[str], max_results: int) -> list[dict]:
        where = ["status IN ({})".format(",".join("?" for _ in include_states))]
        params: list[object] = list(include_states)
        if ignore_schedule_id is not None:
            where.append("id != ?")
            params.append(ignore_schedule_id)

        rows = conn.execute(
            f"SELECT * FROM maintenance_schedules WHERE {' AND '.join(where)} ORDER BY id DESC",
            tuple(params),
        ).fetchall()

        candidate_runs = MaintenanceScheduleService._preview_next_runs(candidate, count=8)
        candidate_duration = timedelta(minutes=int(candidate["duration_minutes"]))
        candidate_targets = set(candidate["target_agent_ids"])
        tz = MaintenanceScheduleService._get_tzinfo(candidate["timezone"])

        conflicts: list[dict] = []
        for row in rows:
            existing = MaintenanceScheduleService._row_to_schedule(row)
            shared = sorted(candidate_targets.intersection(set(existing["target_agent_ids"])))
            if not shared:
                continue

            existing_runs = MaintenanceScheduleService._preview_next_runs(existing, count=8)
            existing_duration = timedelta(minutes=int(existing["duration_minutes"]))

            overlap_found = None
            for can in candidate_runs:
                can_start = datetime.fromisoformat(can["run_at_utc"]).astimezone(timezone.utc)
                can_end = can_start + candidate_duration
                for ex in existing_runs:
                    ex_start = datetime.fromisoformat(ex["run_at_utc"]).astimezone(timezone.utc)
                    ex_end = ex_start + existing_duration
                    if can_start < ex_end and ex_start < can_end:
                        overlap_found = max(can_start, ex_start)
                        break
                if overlap_found:
                    break

            if overlap_found:
                conflicts.append(
                    {
                        "schedule_id": existing["id"],
                        "window_name": existing["window_name"],
                        "schedule_status": existing["status"],
                        "overlap_start_utc": overlap_found.isoformat(),
                        "overlap_start_local": overlap_found.astimezone(tz).isoformat(),
                        "shared_agent_ids": shared,
                        "shared_agent_count": len(shared),
                    }
                )
                if len(conflicts) >= max_results:
                    break
        return conflicts

    @staticmethod
    def _get_schedule_with_conn(conn, schedule_id: int) -> dict | None:
        row = conn.execute(
            """
            SELECT s.*, u.username AS created_by_username, uu.username AS updated_by_username
            FROM maintenance_schedules s
            LEFT JOIN users u ON u.id = s.created_by_user_id
            LEFT JOIN users uu ON uu.id = s.updated_by_user_id
            WHERE s.id = ?
            """,
            (schedule_id,),
        ).fetchone()
        if not row:
            return None
        return MaintenanceScheduleService._row_to_schedule(row)

    @staticmethod
    def _row_to_schedule(row: dict) -> dict:
        row_map = dict(row)
        weekly_days = MaintenanceScheduleService._safe_json_list(row_map.get("weekly_days_json"))
        target_ids = MaintenanceScheduleService._safe_json_list(row_map.get("target_agent_ids_json"))
        metadata = MaintenanceScheduleService._safe_json_dict(row_map.get("metadata_json"))
        next_run_local = None
        if row_map.get("next_run_at"):
            try:
                next_run_local = (
                    datetime.fromisoformat(str(row_map["next_run_at"]))
                    .astimezone(MaintenanceScheduleService._get_tzinfo(str(row_map["timezone"])))
                    .isoformat()
                )
            except Exception:
                next_run_local = None

        return {
            "id": int(row_map["id"]),
            "window_name": str(row_map["window_name"]),
            "timezone": str(row_map["timezone"]),
            "start_time_local": str(row_map["start_time_local"]),
            "duration_minutes": int(row_map["duration_minutes"]),
            "recurrence": str(row_map["recurrence"]),
            "weekly_days": weekly_days,
            "target_agent_ids": target_ids,
            "orchestration_mode": str(row_map["orchestration_mode"]),
            "status": str(row_map["status"]),
            "reason_code": str(row_map["reason_code"]),
            "reason": str(row_map["reason"]),
            "create_idempotency_key": str(row_map.get("create_idempotency_key") or ""),
            "next_run_at": row_map.get("next_run_at"),
            "next_run_local": next_run_local,
            "last_run_at": row_map.get("last_run_at"),
            "metadata": metadata,
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "updated_by_user_id": int(row_map["updated_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "updated_by_username": row_map.get("updated_by_username"),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
        }

    @staticmethod
    def _safe_json_list(value: object) -> list[int]:
        try:
            parsed = json.loads(str(value or "[]"))
            if not isinstance(parsed, list):
                return []
            return [int(item) for item in parsed]
        except Exception:
            return []

    @staticmethod
    def _safe_json_dict(value: object) -> dict:
        try:
            parsed = json.loads(str(value or "{}"))
            if not isinstance(parsed, dict):
                return {}
            return parsed
        except Exception:
            return {}

    @staticmethod
    def _orchestration_stages(mode: str) -> list[dict]:
        if mode == "SAFE_SHUTDOWN_START":
            return [
                {"action": "policy_push", "phase": "notify", "high_risk": False},
                {"action": "policy_push", "phase": "drain", "high_risk": False},
                {"action": "shutdown", "phase": "shutdown", "high_risk": True},
                {"action": "restart", "phase": "start_verify", "high_risk": False},
            ]
        if mode == "SHUTDOWN_ONLY":
            return [{"action": "shutdown", "phase": "shutdown", "high_risk": True}]
        if mode == "RESTART_ONLY":
            return [{"action": "restart", "phase": "restart", "high_risk": False}]
        if mode == "POLICY_PUSH_ONLY":
            return [{"action": "policy_push", "phase": "policy_push", "high_risk": False}]
        raise ValueError("INVALID_ORCHESTRATION_MODE")

    @staticmethod
    def _create_request_hash(*, candidate: dict, status_value: str, reason_code: str, reason: str) -> str:
        canonical = json.dumps(
            {
                "window_name": candidate["window_name"],
                "timezone": candidate["timezone"],
                "start_time_local": candidate["start_time_local"],
                "duration_minutes": candidate["duration_minutes"],
                "recurrence": candidate["recurrence"],
                "weekly_days": candidate["weekly_days"],
                "target_agent_ids": candidate["target_agent_ids"],
                "orchestration_mode": candidate["orchestration_mode"],
                "status": status_value,
                "reason_code": reason_code,
                "reason": reason,
                "metadata_json": candidate["metadata_json"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_tzinfo(timezone_name: str):
        normalized = timezone_name.strip()
        if normalized.upper() in {"UTC", "ETC/UTC", "GMT"}:
            return timezone.utc
        try:
            return ZoneInfo(normalized)
        except Exception as exc:
            raise ValueError("INVALID_TIMEZONE") from exc

