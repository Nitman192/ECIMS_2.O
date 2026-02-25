from __future__ import annotations

from datetime import timedelta

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class RetentionService:
    @staticmethod
    def run(events_days: int, alerts_days: int, audit_days: int) -> dict[str, int]:
        now = utcnow()
        events_cutoff = (now - timedelta(days=events_days)).isoformat()
        alerts_cutoff = (now - timedelta(days=alerts_days)).isoformat()
        audit_cutoff = (now - timedelta(days=audit_days)).isoformat()

        with get_db() as conn:
            cur_events = conn.execute("DELETE FROM events WHERE ts < ?", (events_cutoff,))
            cur_alerts = conn.execute("DELETE FROM alerts WHERE ts < ?", (alerts_cutoff,))
            cur_audit = conn.execute("DELETE FROM audit_log WHERE ts < ?", (audit_cutoff,))

            result = {
                "deleted_events": cur_events.rowcount,
                "deleted_alerts": cur_alerts.rowcount,
                "deleted_audit": cur_audit.rowcount,
            }

            AuditService.log(
                conn,
                actor_type="SYSTEM",
                action="RETENTION_RUN",
                target_type="SYSTEM",
                target_id="retention",
                message="Retention cleanup completed",
                metadata=result,
            )
            return result
