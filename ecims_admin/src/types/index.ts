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

export interface Agent { id: number; hostname: string; name: string; last_seen: string; status: string; device_mode_override?: string }
export interface Alert { id: number; severity: 'RED' | 'YELLOW' | 'GREEN' | string; alert_type: string; message: string; ts: string; status: string }
