export interface LoginResponse {
  access_token: string;
  token_type: string;
  must_reset_password?: boolean;
}

export interface User {
  id: number;
  username: string;
  role: 'ADMIN' | 'ANALYST' | 'VIEWER' | string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string | null;
  last_login_at?: string | null;
  must_reset_password?: boolean;
}

export interface AdminUserCreatePayload {
  username: string;
  password: string;
  role: 'ADMIN' | 'ANALYST' | 'VIEWER';
  is_active: boolean;
  must_reset_password: boolean;
}

export interface AdminUserActivePayload {
  is_active: boolean;
  reason: string;
}

export interface AdminUserRolePayload {
  role: 'ADMIN' | 'ANALYST' | 'VIEWER';
}

export interface AdminUserResetPasswordPayload {
  new_password: string;
  must_reset_password: boolean;
  reason: string;
}

export type FeatureFlagScope = 'GLOBAL' | 'USER' | 'AGENT';
export type FeatureFlagRiskLevel = 'LOW' | 'HIGH';

export interface FeatureFlag {
  id: number;
  key: string;
  description: string;
  scope: FeatureFlagScope | string;
  scope_target?: string | null;
  enabled: boolean;
  risk_level: FeatureFlagRiskLevel | string;
  is_kill_switch: boolean;
  created_by_user_id?: number | null;
  updated_by_user_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlagListResponse {
  items: FeatureFlag[];
  total: number;
}

export interface FeatureFlagCreatePayload {
  key: string;
  description: string;
  scope: FeatureFlagScope;
  scope_target?: string | null;
  is_enabled: boolean;
  risk_level: FeatureFlagRiskLevel;
  reason_code: string;
  reason: string;
  confirm_risky: boolean;
}

export interface FeatureFlagSetStatePayload {
  enabled: boolean;
  reason_code: string;
  reason: string;
  confirm_risky: boolean;
}

export type RemoteActionStatus = 'PENDING' | 'SENT' | 'ACK' | 'DONE' | 'FAILED';
export type RemoteActionKind = 'shutdown' | 'restart' | 'lockdown' | 'policy_push';

export interface RemoteActionTask {
  id: number;
  idempotency_key: string;
  action: RemoteActionKind | string;
  reason_code: string;
  reason: string;
  requested_by_user_id: number;
  requested_by_username?: string | null;
  status: RemoteActionStatus | string;
  target_count: number;
  sent_count: number;
  ack_count: number;
  done_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
  sent_at?: string | null;
  completed_at?: string | null;
  metadata?: Record<string, unknown>;
}

export interface RemoteActionTaskListResponse {
  page: number;
  page_size: number;
  total: number;
  items: RemoteActionTask[];
}

export interface RemoteActionTaskTarget {
  id: number;
  task_id: number;
  agent_id: number;
  agent_name?: string | null;
  agent_hostname?: string | null;
  command_id?: number | null;
  status: RemoteActionStatus | string;
  ack_applied?: boolean | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  sent_at?: string | null;
  ack_at?: string | null;
  completed_at?: string | null;
}

export interface RemoteActionTaskTargetListResponse {
  task: RemoteActionTask;
  total: number;
  items: RemoteActionTaskTarget[];
}

export interface RemoteActionTaskCreatePayload {
  action: RemoteActionKind;
  agent_ids: number[];
  idempotency_key: string;
  reason_code: string;
  reason: string;
  confirm_high_risk: boolean;
  metadata?: Record<string, unknown>;
}

export interface RemoteActionTaskCreateResponse {
  item: RemoteActionTask;
  created: boolean;
}

export type MaintenanceScheduleStatus = 'DRAFT' | 'ACTIVE' | 'PAUSED';
export type MaintenanceScheduleRecurrence = 'DAILY' | 'WEEKLY';
export type MaintenanceOrchestrationMode =
  | 'SAFE_SHUTDOWN_START'
  | 'SHUTDOWN_ONLY'
  | 'RESTART_ONLY'
  | 'POLICY_PUSH_ONLY';

export interface MaintenanceSchedule {
  id: number;
  window_name: string;
  timezone: string;
  start_time_local: string;
  duration_minutes: number;
  recurrence: MaintenanceScheduleRecurrence | string;
  weekly_days: number[];
  target_agent_ids: number[];
  orchestration_mode: MaintenanceOrchestrationMode | string;
  status: MaintenanceScheduleStatus | string;
  reason_code: string;
  reason: string;
  next_run_at?: string | null;
  next_run_local?: string | null;
  last_run_at?: string | null;
  conflict_count?: number;
  has_conflict?: boolean;
  created_by_username?: string | null;
  updated_by_username?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceScheduleListResponse {
  page: number;
  page_size: number;
  total: number;
  items: MaintenanceSchedule[];
}

export interface MaintenanceScheduleCreatePayload {
  window_name: string;
  timezone: string;
  start_time_local: string;
  duration_minutes: number;
  recurrence: MaintenanceScheduleRecurrence;
  weekly_days: number[];
  target_agent_ids: number[];
  orchestration_mode: MaintenanceOrchestrationMode;
  status: MaintenanceScheduleStatus;
  reason_code: string;
  reason: string;
  allow_conflicts: boolean;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface MaintenanceScheduleCreateResponse {
  item: MaintenanceSchedule;
  created: boolean;
}

export interface MaintenanceSchedulePreviewPayload {
  window_name: string;
  timezone: string;
  start_time_local: string;
  duration_minutes: number;
  recurrence: MaintenanceScheduleRecurrence;
  weekly_days: number[];
  target_agent_ids: number[];
  orchestration_mode: MaintenanceOrchestrationMode;
  metadata?: Record<string, unknown>;
}

export interface MaintenanceScheduleConflict {
  schedule_id: number;
  window_name: string;
  schedule_status: string;
  overlap_start_utc: string;
  overlap_start_local: string;
  shared_agent_ids: number[];
  shared_agent_count: number;
}

export interface MaintenanceSchedulePreviewResponse {
  next_runs: Array<{
    run_at_utc: string;
    run_at_local: string;
    window_end_utc: string;
    window_end_local: string;
  }>;
  conflicts: MaintenanceScheduleConflict[];
  conflict_count: number;
}

export interface MaintenanceScheduleConflictResponse {
  schedule_id: number;
  total: number;
  conflicts: MaintenanceScheduleConflict[];
}

export interface MaintenanceScheduleRunDueResponse {
  due_count: number;
  executed_count: number;
  failed_count: number;
  tasks_dispatched: number;
  items: Array<{
    schedule_id: number;
    run_key: string;
    status: string;
    task_ids: number[];
    errors: string[];
  }>;
}

export interface MaintenanceScheduleStatePayload {
  status: MaintenanceScheduleStatus;
  reason: string;
}

export type EnrollmentMode = 'ONLINE' | 'OFFLINE';
export type EnrollmentStatus = 'ACTIVE' | 'REVOKED' | 'EXPIRED' | 'CONSUMED';
export type EnrollmentReasonCode =
  | 'MAINTENANCE'
  | 'OFFLINE_AIRGAP'
  | 'BOOTSTRAP'
  | 'INCIDENT_RESPONSE'
  | 'TESTING'
  | 'COMPLIANCE';

export interface EnrollmentToken {
  id: number;
  token_id: string;
  mode: EnrollmentMode | string;
  status: EnrollmentStatus | string;
  expires_at: string;
  max_uses: number;
  used_count: number;
  remaining_uses: number;
  reason_code: EnrollmentReasonCode | string;
  reason: string;
  metadata: Record<string, unknown>;
  created_by_user_id: number;
  created_by_username?: string | null;
  created_at: string;
  updated_at: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
  revoked_by_user_id?: number | null;
  revoked_by_username?: string | null;
}

export interface EnrollmentTokenListResponse {
  page: number;
  page_size: number;
  total: number;
  items: EnrollmentToken[];
}

export interface EnrollmentTokenIssuePayload {
  mode: EnrollmentMode;
  expires_in_hours: number;
  max_uses: number;
  reason_code: EnrollmentReasonCode;
  reason: string;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface EnrollmentTokenIssueResponse {
  item: EnrollmentToken;
  created: boolean;
  enrollment_token?: string | null;
  cli_snippets?: {
    powershell: string;
    linux: string;
  } | null;
  offline_kit_bundle?: Record<string, unknown> | null;
}

export interface EnrollmentTokenRevokePayload {
  reason: string;
}

export interface OfflineEnrollmentKitImportPayload {
  bundle: Record<string, unknown>;
}

export interface OfflineEnrollmentKitImportResponse {
  item: EnrollmentToken;
  created_token: boolean;
  created_kit: boolean;
}

export type EvidenceStatus = 'SEALED' | 'IN_REVIEW' | 'RELEASED' | 'ARCHIVED';
export type EvidenceOriginType = 'ALERT' | 'EVENT' | 'AGENT' | 'MANUAL' | 'FORENSICS_IMPORT';
export type EvidenceClassification = 'INTERNAL' | 'CONFIDENTIAL' | 'RESTRICTED';
export type EvidenceCustodyEventType =
  | 'CREATED'
  | 'REVIEW_STARTED'
  | 'RESEALED'
  | 'RELEASED'
  | 'ARCHIVED'
  | 'NOTE_ADDED'
  | 'TRANSFERRED'
  | 'EXPORT_COMPLETED';

export interface EvidenceObject {
  id: number;
  evidence_id: string;
  object_hash: string;
  hash_algorithm: string;
  origin_type: EvidenceOriginType | string;
  origin_ref?: string | null;
  classification: EvidenceClassification | string;
  status: EvidenceStatus | string;
  manifest: Record<string, unknown>;
  metadata: Record<string, unknown>;
  chain_version: string;
  immutability_chain_head?: string | null;
  sealed_at?: string | null;
  released_at?: string | null;
  archived_at?: string | null;
  created_by_user_id: number;
  updated_by_user_id: number;
  created_by_username?: string | null;
  updated_by_username?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceVaultListResponse {
  page: number;
  page_size: number;
  total: number;
  items: EvidenceObject[];
}

export interface EvidenceObjectCreatePayload {
  object_hash: string;
  hash_algorithm: 'SHA256';
  origin_type: EvidenceOriginType;
  origin_ref?: string | null;
  classification: EvidenceClassification;
  reason: string;
  idempotency_key: string;
  manifest?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface EvidenceObjectCreateResponse {
  item: EvidenceObject;
  created: boolean;
}

export interface EvidenceCustodyEvent {
  id: number;
  evidence_id: string;
  sequence_no: number;
  event_type: EvidenceCustodyEventType | string;
  actor_user_id?: number | null;
  actor_username?: string | null;
  actor_role: string;
  reason: string;
  details: Record<string, unknown>;
  prev_event_hash?: string | null;
  event_hash: string;
  event_ts: string;
}

export interface EvidenceTimelineResponse {
  evidence_id: string;
  total: number;
  chain_valid: boolean;
  items: EvidenceCustodyEvent[];
}

export interface EvidenceCustodyEventCreatePayload {
  event_type: Exclude<EvidenceCustodyEventType, 'CREATED'>;
  reason: string;
  details?: Record<string, unknown>;
}

export interface EvidenceExportPayload {
  reason: string;
}

export interface EvidenceExportResponse {
  bundle: {
    evidence: EvidenceObject;
    timeline: EvidenceCustodyEvent[];
    chain_valid: boolean;
    exported_at: string;
    export_reason: string;
  };
  export_hash: string;
  chain_valid: boolean;
  event: EvidenceCustodyEvent;
}

export interface Agent { id: number; hostname: string; name: string; last_seen: string; status: string; device_mode_override?: string }
export interface Alert { id: number; severity: 'RED' | 'YELLOW' | 'GREEN' | string; alert_type: string; message: string; ts: string; status: string }
