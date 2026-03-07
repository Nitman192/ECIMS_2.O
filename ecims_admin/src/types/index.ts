export interface LoginResponse {
  access_token: string;
  token_type: string;
  must_reset_password?: boolean;
}

export interface LicenseActivationStatus {
  activation_required: boolean;
  is_activated: boolean;
  activated?: Record<string, unknown> | null;
  pending_request?: {
    request_code?: string;
    installation_id?: string;
    expires_at?: string;
    machine_fingerprint_short?: string;
  } | null;
  license_valid?: boolean;
  license_reason?: string | null;
  license_id?: string | null;
  machine_match?: boolean | null;
  local_fingerprint_short?: string | null;
}

export interface LicenseActivationLicenseKeyResponse {
  status: string;
  license_id?: string | null;
  installation_id?: string | null;
  request_code?: string | null;
  expires_at?: string | null;
  machine_fingerprint_short?: string | null;
}

export interface LicenseActivationRequestResponse {
  status: string;
  license_id?: string | null;
  installation_id?: string | null;
  request_code?: string | null;
  expires_at?: string | null;
  activation?: Record<string, unknown> | null;
}

export interface LicenseActivationVerifyResponse {
  status: string;
  license_state?: Record<string, unknown>;
  activation?: Record<string, unknown>;
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

export interface RoleMatrixEntry {
  role: 'ADMIN' | 'ANALYST' | 'VIEWER' | string;
  scope: string;
  permissions: string[];
  permission_count: number;
  active_users: number;
  total_users: number;
  updated_at?: string | null;
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

export interface FleetDriftItem {
  agent_id: number;
  agent_name: string;
  policy_hash_applied?: string | null;
  expected_policy_hash?: string | null;
  enforcement_mode?: string | null;
  expected_mode?: string | null;
  adapter_status?: string | null;
  last_reconcile_time?: string | null;
  agent_version?: string | null;
}

export interface FleetDriftResponse {
  count: number;
  items: FleetDriftItem[];
}

export interface DeviceRolloutStatusResponse {
  kill_switch: boolean;
  rollout: Record<string, number>;
  command_backlog: Record<string, number>;
}

export interface DeviceAllowTokenClaims {
  token_id: string;
  agent_id: number;
  expires_at: string;
  [key: string]: unknown;
}

export interface DeviceAllowTokenIssuePayload {
  agent_id: number;
  duration_minutes: number;
  vid?: string | null;
  pid?: string | null;
  serial?: string | null;
  justification: string;
}

export interface DeviceAllowTokenIssueResponse {
  token: string;
  claims: DeviceAllowTokenClaims;
}

export interface DeviceSecureDeclarePayload {
  agent_id: number;
  reason: string;
  duration_minutes: number;
}

export interface DeviceSecureDeclareResponse {
  status: string;
  agent_id: number;
  command_id: number;
  token: string;
  claims: DeviceAllowTokenClaims;
}

export interface AdminMetricsResponse {
  request_id: string;
  agent_commands_pending: number;
  agent_commands_applied: number;
  agent_commands_failed: number;
  device_events_ingested_total: Record<string, number>;
  allow_tokens_issued: number;
  allow_tokens_revoked: number;
  allow_tokens_expired: number;
  kill_switch_state: boolean;
  rollout: Record<string, number>;
  rate_limiter_rejections_total: number;
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

export type PlaybookTriggerType = 'MANUAL' | 'ALERT_MATCH' | 'AGENT_HEALTH' | 'SCHEDULED';
export type PlaybookApprovalMode = 'AUTO' | 'MANUAL' | 'TWO_PERSON';
export type PlaybookStatus = 'ACTIVE' | 'DISABLED';
export type PlaybookRiskLevel = 'LOW' | 'HIGH';
export type PlaybookRunStatus =
  | 'PENDING_APPROVAL'
  | 'PARTIALLY_APPROVED'
  | 'REJECTED'
  | 'DISPATCHED'
  | 'FAILED';

export interface Playbook {
  id: number;
  playbook_id: string;
  name: string;
  description: string;
  trigger_type: PlaybookTriggerType | string;
  action: RemoteActionKind | string;
  target_agent_ids: number[];
  approval_mode: PlaybookApprovalMode | string;
  risk_level: PlaybookRiskLevel | string;
  reason_code: string;
  status: PlaybookStatus | string;
  metadata: Record<string, unknown>;
  created_by_user_id: number;
  updated_by_user_id: number;
  created_by_username?: string | null;
  updated_by_username?: string | null;
  created_at: string;
  updated_at: string;
  last_run_at?: string | null;
}

export interface PlaybookListResponse {
  page: number;
  page_size: number;
  total: number;
  items: Playbook[];
}

export interface PlaybookCreatePayload {
  name: string;
  description: string;
  trigger_type: PlaybookTriggerType;
  action: RemoteActionKind;
  target_agent_ids: number[];
  approval_mode: PlaybookApprovalMode;
  risk_level: PlaybookRiskLevel;
  reason_code: string;
  status: PlaybookStatus;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface PlaybookCreateResponse {
  item: Playbook;
  created: boolean;
}

export interface PlaybookExecutePayload {
  reason: string;
}

export interface PlaybookRun {
  id: number;
  run_id: string;
  playbook_id: string;
  playbook_name: string;
  playbook_action: RemoteActionKind | string;
  playbook_approval_mode: PlaybookApprovalMode | string;
  requested_by_user_id: number;
  requested_by_username?: string | null;
  request_reason: string;
  status: PlaybookRunStatus | string;
  first_approver_user_id?: number | null;
  first_approver_username?: string | null;
  second_approver_user_id?: number | null;
  second_approver_username?: string | null;
  decision_reason?: string | null;
  task_id?: number | null;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  decided_at?: string | null;
  dispatched_at?: string | null;
}

export interface PlaybookRunListResponse {
  page: number;
  page_size: number;
  total: number;
  items: PlaybookRun[];
}

export interface PlaybookRunDecisionPayload {
  decision: 'APPROVE' | 'REJECT';
  reason: string;
}

export type ChangeRequestType =
  | 'POLICY'
  | 'FEATURE_FLAG'
  | 'PLAYBOOK'
  | 'SCHEDULE'
  | 'ENROLLMENT_POLICY'
  | 'BREAK_GLASS_POLICY';
export type ChangeRequestRisk = 'LOW' | 'HIGH' | 'CRITICAL';
export type ChangeRequestStatus = 'PENDING' | 'PARTIALLY_APPROVED' | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export interface ChangeRequestItem {
  id: number;
  request_id: string;
  change_type: ChangeRequestType | string;
  target_ref: string;
  summary: string;
  proposed_changes: Record<string, unknown>;
  risk_level: ChangeRequestRisk | string;
  status: ChangeRequestStatus | string;
  approvals_required: number;
  reason: string;
  metadata: Record<string, unknown>;
  requested_by_user_id: number;
  requested_by_username?: string | null;
  first_approver_user_id?: number | null;
  first_approver_username?: string | null;
  second_approver_user_id?: number | null;
  second_approver_username?: string | null;
  decision_reason?: string | null;
  created_at: string;
  updated_at: string;
  decided_at?: string | null;
}

export interface ChangeRequestListResponse {
  page: number;
  page_size: number;
  total: number;
  items: ChangeRequestItem[];
}

export interface ChangeRequestCreatePayload {
  change_type: ChangeRequestType;
  target_ref: string;
  summary: string;
  proposed_changes?: Record<string, unknown>;
  risk_level: ChangeRequestRisk;
  reason: string;
  two_person_rule: boolean;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface ChangeRequestCreateResponse {
  item: ChangeRequestItem;
  created: boolean;
}

export interface ChangeRequestDecisionPayload {
  decision: 'APPROVE' | 'REJECT';
  reason: string;
}

export type BreakGlassScope = 'INCIDENT_RESPONSE' | 'SYSTEM_RECOVERY' | 'FORENSICS' | 'OTHER';
export type BreakGlassStatus = 'ACTIVE' | 'EXPIRED' | 'REVOKED';

export interface BreakGlassSession {
  id: number;
  session_id: string;
  requested_by_user_id: number;
  requested_by_username?: string | null;
  revoked_by_user_id?: number | null;
  revoked_by_username?: string | null;
  reason: string;
  scope: BreakGlassScope | string;
  status: BreakGlassStatus | string;
  duration_minutes: number;
  started_at: string;
  expires_at: string;
  ended_at?: string | null;
  reauth_method: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BreakGlassSessionListResponse {
  page: number;
  page_size: number;
  total: number;
  items: BreakGlassSession[];
}

export interface BreakGlassSessionCreatePayload {
  current_password: string;
  reason: string;
  scope: BreakGlassScope;
  duration_minutes: number;
  idempotency_key: string;
  metadata?: Record<string, unknown>;
}

export interface BreakGlassSessionCreateResponse {
  item: BreakGlassSession;
  created: boolean;
  break_glass_token?: string | null;
}

export interface BreakGlassSessionRevokePayload {
  reason: string;
}

export type StateBackupScope = 'CONFIG_ONLY' | 'FULL';

export interface StateBackupMeta {
  id: number;
  backup_id: string;
  scope: StateBackupScope | string;
  include_sensitive: boolean;
  row_count: number;
  bundle_hash: string;
  created_by_user_id: number;
  created_by_username?: string | null;
  created_at: string;
}

export interface StateBackup extends StateBackupMeta {
  bundle: Record<string, unknown>;
}

export interface StateBackupListResponse {
  page: number;
  page_size: number;
  total: number;
  items: StateBackupMeta[];
}

export interface StateBackupCreatePayload {
  scope: StateBackupScope;
  include_sensitive: boolean;
}

export interface StateBackupRestorePreviewPayload {
  tables?: string[];
  allow_deletes: boolean;
}

export interface StateBackupRestoreTableDiff {
  table: string;
  mode: string;
  key_columns: string[];
  current_rows: number;
  backup_rows: number;
  to_insert: number;
  to_update: number;
  to_delete: number;
  potential_delete_skipped: number;
  unchanged: number;
  warnings: string[];
}

export interface StateBackupRestorePreviewResponse {
  backup_id: string;
  scope: StateBackupScope | string;
  allow_deletes: boolean;
  selected_tables: string[];
  summary: {
    table_count: number;
    inserts: number;
    updates: number;
    deletes: number;
    changed_rows: number;
  };
  table_diffs: StateBackupRestoreTableDiff[];
}

export interface StateBackupRestoreApplyPayload extends StateBackupRestorePreviewPayload {
  reason: string;
  idempotency_key: string;
  confirm_apply: boolean;
}

export interface StateBackupRestoreResult {
  backup_id: string;
  scope: StateBackupScope | string;
  allow_deletes: boolean;
  summary: {
    inserted: number;
    updated: number;
    deleted: number;
    changed_rows: number;
  };
  table_results: Array<{
    table: string;
    status: string;
    inserted: number;
    updated: number;
    deleted: number;
    warnings: string[];
  }>;
}

export interface StateBackupRestoreJob {
  id: number;
  restore_id: string;
  backup_id: string;
  status: 'APPLIED' | 'FAILED' | string;
  reason: string;
  allow_deletes: boolean;
  selected_tables: string[];
  result: StateBackupRestoreResult;
  created_by_user_id: number;
  created_by_username?: string | null;
  created_at: string;
  applied_at?: string | null;
}

export interface StateBackupRestoreApplyResponse {
  item: StateBackupRestoreJob;
  created: boolean;
}

export type PatchUpdateStatus = 'UPLOADED' | 'APPLIED' | 'FAILED' | 'ROLLED_BACK';

export interface PatchUpdateItem {
  patch_id: string;
  version: string;
  filename: string;
  file_path: string;
  sha256: string;
  file_size_bytes: number;
  status: PatchUpdateStatus | string;
  notes: string;
  apply_notes: string;
  backup_id?: string | null;
  created_by_user_id: number;
  applied_by_user_id?: number | null;
  created_at: string;
  applied_at?: string | null;
}

export interface PatchUpdateListResponse {
  page: number;
  page_size: number;
  total: number;
  items: PatchUpdateItem[];
}

export interface PatchUpdateApplyPayload {
  reason: string;
  backup_scope: StateBackupScope;
  include_sensitive: boolean;
}

export interface PatchUpdateApplyResponse {
  item: PatchUpdateItem;
  backup: StateBackup;
  next_steps: string[];
}

export interface Agent {
  id: number;
  hostname: string;
  name: string;
  registered_at?: string;
  last_seen: string;
  status: string;
  agent_revoked?: boolean;
  device_mode_override?: string | null;
}

export interface AgentSelfStatusAgent {
  id: number;
  hostname: string;
  name: string;
  registered_at?: string | null;
  last_seen?: string | null;
  status: string;
  agent_revoked: boolean;
  revoked_at?: string | null;
  revocation_reason?: string | null;
  device_mode_override?: string | null;
  device_tags?: string | null;
}

export interface AgentSelfStatusDeviceStatus {
  policy_hash_applied?: string | null;
  enforcement_mode?: string | null;
  adapter_status?: string | null;
  last_reconcile_time?: string | null;
  agent_version?: string | null;
  runtime_id?: string | null;
  state_root?: string | null;
  updated_at?: string | null;
}

export interface AgentSelfStatusPendingCommand {
  id: number;
  type: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface AgentSelfStatusResponse {
  agent: AgentSelfStatusAgent;
  device_status: AgentSelfStatusDeviceStatus | null;
  command_counts: {
    pending: number;
    applied: number;
    failed: number;
  };
  pending_commands: AgentSelfStatusPendingCommand[];
  server_time_utc: string;
}

export interface Alert {
  id: number;
  agent_id?: number;
  severity: 'RED' | 'YELLOW' | 'GREEN' | string;
  alert_type: string;
  message: string;
  ts: string;
  status: string;
}
