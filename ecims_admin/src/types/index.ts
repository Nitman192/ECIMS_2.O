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

export interface Agent { id: number; hostname: string; name: string; last_seen: string; status: string; device_mode_override?: string }
export interface Alert { id: number; severity: 'RED' | 'YELLOW' | 'GREEN' | string; alert_type: string; message: string; ts: string; status: string }
