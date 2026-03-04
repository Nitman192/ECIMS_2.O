from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Any

from app.db.database import get_db
from app.services.audit_service import AuditService
from app.utils.time import utcnow


class EvidenceVaultService:
    VALID_HASH_ALGORITHMS = {"SHA256"}
    VALID_ORIGINS = {"ALERT", "EVENT", "AGENT", "MANUAL", "FORENSICS_IMPORT"}
    VALID_CLASSIFICATIONS = {"INTERNAL", "CONFIDENTIAL", "RESTRICTED"}
    VALID_STATUSES = {"SEALED", "IN_REVIEW", "RELEASED", "ARCHIVED"}
    VALID_CUSTODY_EVENTS = {
        "CREATED",
        "REVIEW_STARTED",
        "RESEALED",
        "RELEASED",
        "ARCHIVED",
        "NOTE_ADDED",
        "TRANSFERRED",
        "EXPORT_COMPLETED",
    }
    STATUS_EVENT_MAP = {
        "REVIEW_STARTED": "IN_REVIEW",
        "RESEALED": "SEALED",
        "RELEASED": "RELEASED",
        "ARCHIVED": "ARCHIVED",
    }

    @staticmethod
    def list_evidence(
        *,
        page: int,
        page_size: int,
        status_filter: str | None,
        origin_filter: str | None,
        query: str | None,
    ) -> dict[str, Any]:
        where: list[str] = []
        params: list[Any] = []

        if status_filter and status_filter.strip().upper() != "ALL":
            normalized_status = status_filter.strip().upper()
            if normalized_status not in EvidenceVaultService.VALID_STATUSES:
                raise ValueError("INVALID_STATUS")
            where.append("e.status = ?")
            params.append(normalized_status)

        if origin_filter and origin_filter.strip().upper() != "ALL":
            normalized_origin = origin_filter.strip().upper()
            if normalized_origin not in EvidenceVaultService.VALID_ORIGINS:
                raise ValueError("INVALID_ORIGIN")
            where.append("e.origin_type = ?")
            params.append(normalized_origin)

        if query and query.strip():
            q = query.strip().lower()
            term = f"%{q}%"
            where.append(
                "(lower(e.evidence_id) LIKE ? OR lower(e.object_hash) LIKE ? OR lower(coalesce(e.origin_ref, '')) LIKE ?)"
            )
            params.extend([term, term, term])

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        offset = (page - 1) * page_size

        with get_db() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM evidence_objects e {where_sql}",
                tuple(params),
            ).fetchone()
            total = int(total_row["c"] if total_row else 0)

            rows = conn.execute(
                f"""
                SELECT e.*, cu.username AS created_by_username, uu.username AS updated_by_username
                FROM evidence_objects e
                LEFT JOIN users cu ON cu.id = e.created_by_user_id
                LEFT JOIN users uu ON uu.id = e.updated_by_user_id
                {where_sql}
                ORDER BY e.id DESC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, page_size, offset]),
            ).fetchall()
            items = [EvidenceVaultService._row_to_evidence(row) for row in rows]
        return {"page": page, "page_size": page_size, "total": total, "items": items}

    @staticmethod
    def create_evidence(
        *,
        object_hash: str,
        hash_algorithm: str,
        origin_type: str,
        origin_ref: str | None,
        classification: str,
        reason: str,
        idempotency_key: str,
        manifest: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        actor_id: int,
        actor_role: str = "ADMIN",
    ) -> tuple[dict[str, Any], bool]:
        normalized_hash = object_hash.strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", normalized_hash):
            raise ValueError("INVALID_HASH")

        algorithm = hash_algorithm.strip().upper()
        if algorithm not in EvidenceVaultService.VALID_HASH_ALGORITHMS:
            raise ValueError("INVALID_HASH_ALGORITHM")

        origin = origin_type.strip().upper()
        if origin not in EvidenceVaultService.VALID_ORIGINS:
            raise ValueError("INVALID_ORIGIN")

        normalized_classification = classification.strip().upper()
        if normalized_classification not in EvidenceVaultService.VALID_CLASSIFICATIONS:
            raise ValueError("INVALID_CLASSIFICATION")

        idem = idempotency_key.strip()
        if len(idem) < 8:
            raise ValueError("INVALID_IDEMPOTENCY_KEY")

        metadata_obj = metadata or {}
        if not isinstance(metadata_obj, dict):
            raise ValueError("INVALID_METADATA")
        manifest_obj = manifest or {}
        if not isinstance(manifest_obj, dict):
            raise ValueError("INVALID_MANIFEST")

        metadata_json = json.dumps(metadata_obj, sort_keys=True, separators=(",", ":"))
        manifest_json = json.dumps(manifest_obj, sort_keys=True, separators=(",", ":"))
        normalized_origin_ref = (origin_ref or "").strip() or None
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")
        request_hash = EvidenceVaultService._build_create_request_hash(
            object_hash=normalized_hash,
            hash_algorithm=algorithm,
            origin_type=origin,
            origin_ref=normalized_origin_ref,
            classification=normalized_classification,
            reason=normalized_reason,
            metadata_json=metadata_json,
            manifest_json=manifest_json,
        )

        evidence_id = f"evd_{secrets.token_hex(8)}"
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id, request_hash FROM evidence_objects WHERE create_idempotency_key = ?",
                (idem,),
            ).fetchone()
            if existing:
                if str(existing["request_hash"]) != request_hash:
                    raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
                item = EvidenceVaultService._get_evidence_with_conn(conn, int(existing["id"]))
                if not item:
                    raise ValueError("EVIDENCE_NOT_FOUND")
                return item, False

            conn.execute(
                """
                INSERT INTO evidence_objects(
                    evidence_id, object_hash, hash_algorithm, origin_type, origin_ref, classification, status,
                    manifest_json, metadata_json, create_idempotency_key, request_hash, chain_version,
                    immutability_chain_head, sealed_at, released_at, archived_at, created_by_user_id, updated_by_user_id,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, 'SEALED', ?, ?, ?, ?, '1', NULL, ?, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    normalized_hash,
                    algorithm,
                    origin,
                    normalized_origin_ref,
                    normalized_classification,
                    manifest_json,
                    metadata_json,
                    idem,
                    request_hash,
                    now_iso,
                    actor_id,
                    actor_id,
                    now_iso,
                    now_iso,
                ),
            )

            event = EvidenceVaultService._append_event_with_conn(
                conn,
                evidence_id=evidence_id,
                event_type="CREATED",
                reason=normalized_reason,
                details={
                    "origin_type": origin,
                    "origin_ref": normalized_origin_ref,
                    "classification": normalized_classification,
                },
                actor_id=actor_id,
                actor_role=actor_role,
                event_ts=now_iso,
            )
            conn.execute(
                "UPDATE evidence_objects SET immutability_chain_head = ? WHERE evidence_id = ?",
                (event["event_hash"], evidence_id),
            )
            row = conn.execute("SELECT id FROM evidence_objects WHERE evidence_id = ?", (evidence_id,)).fetchone()
            if not row:
                raise ValueError("EVIDENCE_NOT_FOUND")

            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="EVIDENCE_OBJECT_CREATED",
                target_type="EVIDENCE",
                target_id=evidence_id,
                message="Evidence object registered in vault",
                metadata={
                    "hash_algorithm": algorithm,
                    "origin_type": origin,
                    "classification": normalized_classification,
                },
            )
            item = EvidenceVaultService._get_evidence_with_conn(conn, int(row["id"]))
            if not item:
                raise ValueError("EVIDENCE_NOT_FOUND")
            return item, True

    @staticmethod
    def get_evidence(evidence_id: str) -> dict[str, Any] | None:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT e.*, cu.username AS created_by_username, uu.username AS updated_by_username
                FROM evidence_objects e
                LEFT JOIN users cu ON cu.id = e.created_by_user_id
                LEFT JOIN users uu ON uu.id = e.updated_by_user_id
                WHERE e.evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
            if not row:
                return None
            return EvidenceVaultService._row_to_evidence(row)

    @staticmethod
    def get_timeline(evidence_id: str) -> dict[str, Any]:
        with get_db() as conn:
            exists = conn.execute(
                "SELECT evidence_id FROM evidence_objects WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
            if not exists:
                raise ValueError("EVIDENCE_NOT_FOUND")
            rows = conn.execute(
                """
                SELECT c.*, u.username AS actor_username
                FROM evidence_custody_events c
                LEFT JOIN users u ON u.id = c.actor_user_id
                WHERE c.evidence_id = ?
                ORDER BY c.sequence_no ASC
                """,
                (evidence_id,),
            ).fetchall()
            items = [EvidenceVaultService._row_to_custody_event(row) for row in rows]
            chain_valid = EvidenceVaultService._verify_chain(items)
        return {"evidence_id": evidence_id, "total": len(items), "chain_valid": chain_valid, "items": items}

    @staticmethod
    def append_custody_event(
        *,
        evidence_id: str,
        event_type: str,
        reason: str,
        details: dict[str, Any] | None,
        actor_id: int,
        actor_role: str = "ADMIN",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        normalized_event = event_type.strip().upper()
        if normalized_event not in EvidenceVaultService.VALID_CUSTODY_EVENTS:
            raise ValueError("INVALID_EVENT_TYPE")
        if normalized_event == "CREATED":
            raise ValueError("INVALID_EVENT_TYPE")

        details_obj = details or {}
        if not isinstance(details_obj, dict):
            raise ValueError("INVALID_DETAILS")
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")
        now_iso = utcnow().isoformat()

        with get_db() as conn:
            row = conn.execute(
                "SELECT id, status FROM evidence_objects WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()
            if not row:
                raise ValueError("EVIDENCE_NOT_FOUND")

            current_status = str(row["status"])
            if current_status == "ARCHIVED" and normalized_event != "NOTE_ADDED":
                raise ValueError("INVALID_TRANSITION")

            event = EvidenceVaultService._append_event_with_conn(
                conn,
                evidence_id=evidence_id,
                event_type=normalized_event,
                reason=normalized_reason,
                details=details_obj,
                actor_id=actor_id,
                actor_role=actor_role,
                event_ts=now_iso,
            )

            next_status = EvidenceVaultService.STATUS_EVENT_MAP.get(normalized_event, current_status)
            sealed_at = now_iso if next_status == "SEALED" else None
            released_at = now_iso if next_status == "RELEASED" else None
            archived_at = now_iso if next_status == "ARCHIVED" else None
            conn.execute(
                """
                UPDATE evidence_objects
                SET status = ?, immutability_chain_head = ?, updated_by_user_id = ?, updated_at = ?,
                    sealed_at = COALESCE(?, sealed_at),
                    released_at = COALESCE(?, released_at),
                    archived_at = COALESCE(?, archived_at)
                WHERE evidence_id = ?
                """,
                (
                    next_status,
                    event["event_hash"],
                    actor_id,
                    now_iso,
                    sealed_at,
                    released_at,
                    archived_at,
                    evidence_id,
                ),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="EVIDENCE_CUSTODY_EVENT_APPENDED",
                target_type="EVIDENCE",
                target_id=evidence_id,
                message="Evidence custody event appended",
                metadata={"event_type": normalized_event, "status_after": next_status},
            )
            item = EvidenceVaultService._get_evidence_with_conn(conn, int(row["id"]))
            if not item:
                raise ValueError("EVIDENCE_NOT_FOUND")
            return item, event

    @staticmethod
    def export_evidence_bundle(
        *,
        evidence_id: str,
        reason: str,
        actor_id: int,
        actor_role: str = "ADMIN",
    ) -> dict[str, Any]:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 5:
            raise ValueError("INVALID_REASON")
        exported_at = utcnow().isoformat()
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT e.*, cu.username AS created_by_username, uu.username AS updated_by_username
                FROM evidence_objects e
                LEFT JOIN users cu ON cu.id = e.created_by_user_id
                LEFT JOIN users uu ON uu.id = e.updated_by_user_id
                WHERE e.evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
            if not row:
                raise ValueError("EVIDENCE_NOT_FOUND")

            timeline_rows = conn.execute(
                """
                SELECT c.*, u.username AS actor_username
                FROM evidence_custody_events c
                LEFT JOIN users u ON u.id = c.actor_user_id
                WHERE c.evidence_id = ?
                ORDER BY c.sequence_no ASC
                """,
                (evidence_id,),
            ).fetchall()
            timeline_items = [EvidenceVaultService._row_to_custody_event(item) for item in timeline_rows]
            chain_valid = EvidenceVaultService._verify_chain(timeline_items)

            bundle = {
                "evidence": EvidenceVaultService._row_to_evidence(row),
                "timeline": timeline_items,
                "chain_valid": chain_valid,
                "exported_at": exported_at,
                "export_reason": normalized_reason,
            }
            export_hash = hashlib.sha256(
                json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            event = EvidenceVaultService._append_event_with_conn(
                conn,
                evidence_id=evidence_id,
                event_type="EXPORT_COMPLETED",
                reason=normalized_reason,
                details={"export_hash": export_hash, "exported_at": exported_at},
                actor_id=actor_id,
                actor_role=actor_role,
                event_ts=exported_at,
            )
            conn.execute(
                """
                UPDATE evidence_objects
                SET immutability_chain_head = ?, updated_by_user_id = ?, updated_at = ?
                WHERE evidence_id = ?
                """,
                (event["event_hash"], actor_id, exported_at, evidence_id),
            )
            AuditService.log(
                conn,
                actor_type="ADMIN",
                actor_id=actor_id,
                action="EVIDENCE_BUNDLE_EXPORTED",
                target_type="EVIDENCE",
                target_id=evidence_id,
                message="Evidence bundle exported",
                metadata={"export_hash": export_hash, "chain_valid": chain_valid},
            )
            return {"bundle": bundle, "export_hash": export_hash, "chain_valid": chain_valid, "event": event}

    @staticmethod
    def _append_event_with_conn(
        conn,
        *,
        evidence_id: str,
        event_type: str,
        reason: str,
        details: dict[str, Any],
        actor_id: int,
        actor_role: str,
        event_ts: str | None = None,
    ) -> dict[str, Any]:
        last = conn.execute(
            """
            SELECT sequence_no, event_hash
            FROM evidence_custody_events
            WHERE evidence_id = ?
            ORDER BY sequence_no DESC
            LIMIT 1
            """,
            (evidence_id,),
        ).fetchone()
        sequence_no = int(last["sequence_no"] if last else 0) + 1
        prev_hash = str(last["event_hash"] if last else "")
        ts = event_ts or utcnow().isoformat()
        details_json = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))
        event_hash = EvidenceVaultService._build_event_hash(
            evidence_id=evidence_id,
            sequence_no=sequence_no,
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
            details_json=details_json,
            prev_event_hash=prev_hash,
            event_ts=ts,
        )
        conn.execute(
            """
            INSERT INTO evidence_custody_events(
                evidence_id, sequence_no, event_type, actor_user_id, actor_role, reason, details_json,
                prev_event_hash, event_hash, event_ts
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                sequence_no,
                event_type,
                actor_id,
                actor_role,
                reason,
                details_json,
                prev_hash or None,
                event_hash,
                ts,
            ),
        )
        return {
            "evidence_id": evidence_id,
            "sequence_no": sequence_no,
            "event_type": event_type,
            "actor_user_id": actor_id,
            "actor_role": actor_role,
            "reason": reason,
            "details": json.loads(details_json),
            "prev_event_hash": prev_hash or None,
            "event_hash": event_hash,
            "event_ts": ts,
        }

    @staticmethod
    def _get_evidence_with_conn(conn, row_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT e.*, cu.username AS created_by_username, uu.username AS updated_by_username
            FROM evidence_objects e
            LEFT JOIN users cu ON cu.id = e.created_by_user_id
            LEFT JOIN users uu ON uu.id = e.updated_by_user_id
            WHERE e.id = ?
            """,
            (row_id,),
        ).fetchone()
        if not row:
            return None
        return EvidenceVaultService._row_to_evidence(row)

    @staticmethod
    def _build_create_request_hash(
        *,
        object_hash: str,
        hash_algorithm: str,
        origin_type: str,
        origin_ref: str | None,
        classification: str,
        reason: str,
        metadata_json: str,
        manifest_json: str,
    ) -> str:
        payload = {
            "object_hash": object_hash,
            "hash_algorithm": hash_algorithm,
            "origin_type": origin_type,
            "origin_ref": origin_ref,
            "classification": classification,
            "reason": reason,
            "metadata_json": metadata_json,
            "manifest_json": manifest_json,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _build_event_hash(
        *,
        evidence_id: str,
        sequence_no: int,
        event_type: str,
        actor_id: int,
        actor_role: str,
        reason: str,
        details_json: str,
        prev_event_hash: str,
        event_ts: str,
    ) -> str:
        payload = {
            "evidence_id": evidence_id,
            "sequence_no": sequence_no,
            "event_type": event_type,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": reason,
            "details_json": details_json,
            "prev_event_hash": prev_event_hash,
            "event_ts": event_ts,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _verify_chain(items: list[dict[str, Any]]) -> bool:
        prev_hash = ""
        for item in sorted(items, key=lambda row: int(row["sequence_no"])):
            details_json = json.dumps(item.get("details") or {}, sort_keys=True, separators=(",", ":"))
            calculated = EvidenceVaultService._build_event_hash(
                evidence_id=str(item["evidence_id"]),
                sequence_no=int(item["sequence_no"]),
                event_type=str(item["event_type"]),
                actor_id=int(item["actor_user_id"]) if item.get("actor_user_id") is not None else 0,
                actor_role=str(item["actor_role"]),
                reason=str(item["reason"]),
                details_json=details_json,
                prev_event_hash=prev_hash,
                event_ts=str(item["event_ts"]),
            )
            if str(item.get("prev_event_hash") or "") != prev_hash:
                return False
            if str(item.get("event_hash") or "") != calculated:
                return False
            prev_hash = calculated
        return True

    @staticmethod
    def _row_to_evidence(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "evidence_id": str(row_map["evidence_id"]),
            "object_hash": str(row_map["object_hash"]),
            "hash_algorithm": str(row_map["hash_algorithm"]),
            "origin_type": str(row_map["origin_type"]),
            "origin_ref": row_map.get("origin_ref"),
            "classification": str(row_map["classification"]),
            "status": str(row_map["status"]),
            "manifest": json.loads(row_map.get("manifest_json") or "{}"),
            "metadata": json.loads(row_map.get("metadata_json") or "{}"),
            "chain_version": str(row_map.get("chain_version") or "1"),
            "immutability_chain_head": row_map.get("immutability_chain_head"),
            "sealed_at": row_map.get("sealed_at"),
            "released_at": row_map.get("released_at"),
            "archived_at": row_map.get("archived_at"),
            "created_by_user_id": int(row_map["created_by_user_id"]),
            "updated_by_user_id": int(row_map["updated_by_user_id"]),
            "created_by_username": row_map.get("created_by_username"),
            "updated_by_username": row_map.get("updated_by_username"),
            "created_at": row_map["created_at"],
            "updated_at": row_map["updated_at"],
        }

    @staticmethod
    def _row_to_custody_event(row) -> dict[str, Any]:
        row_map = dict(row)
        return {
            "id": int(row_map["id"]),
            "evidence_id": str(row_map["evidence_id"]),
            "sequence_no": int(row_map["sequence_no"]),
            "event_type": str(row_map["event_type"]),
            "actor_user_id": int(row_map["actor_user_id"]) if row_map["actor_user_id"] is not None else None,
            "actor_username": row_map.get("actor_username"),
            "actor_role": str(row_map["actor_role"]),
            "reason": str(row_map["reason"]),
            "details": json.loads(row_map.get("details_json") or "{}"),
            "prev_event_hash": row_map.get("prev_event_hash"),
            "event_hash": str(row_map["event_hash"]),
            "event_ts": row_map["event_ts"],
        }
