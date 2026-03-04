import { api } from './client';
import type {
  AdminUserActivePayload,
  AdminUserCreatePayload,
  AdminUserResetPasswordPayload,
  AdminUserRolePayload,
  Alert,
  Agent,
  LoginResponse,
  User,
} from '../types';

export const AuthApi = {
  login: (username: string, password: string) => api.post<LoginResponse>('/auth/login', { username, password }),
  me: () => api.get<User>('/auth/me'),
  resetMyPassword: (payload: { current_password: string; new_password: string }) =>
    api.post('/auth/password/reset', payload),
};

export const CoreApi = {
  metrics: () => api.get('/admin/metrics'),
  agents: () => api.get<Agent[]>('/agents'),
  alerts: () => api.get<Alert[]>('/alerts'),
  securityStatus: () => api.get('/security/status'),
  licenseStatus: () => api.get('/license/status'),
  auditLogs: (params?: Record<string, string>) => api.get('/admin/audit', { params }),
  exportAudit: (payload: Record<string, unknown>) => api.post('/admin/audit/export', payload),
  revokeAgent: (agentId: number, reason: string) => api.post(`/admin/agents/${agentId}/revoke`, { reason }),
  restoreAgent: (agentId: number, reason: string) => api.post(`/admin/agents/${agentId}/restore`, { reason }),
  listUsers: (includeInactive = true) => api.get<User[]>('/admin/users', { params: { include_inactive: includeInactive } }),
  createUser: (payload: AdminUserCreatePayload) => api.post<User>('/admin/users', payload),
  updateUserRole: (userId: number, payload: AdminUserRolePayload) => api.patch<User>(`/admin/users/${userId}/role`, payload),
  updateUserActive: (userId: number, payload: AdminUserActivePayload) =>
    api.patch<User>(`/admin/users/${userId}/active`, payload),
  resetUserPassword: (userId: number, payload: AdminUserResetPasswordPayload) =>
    api.post(`/admin/users/${userId}/reset-password`, payload),
  deleteUser: (userId: number, reason: string) =>
    api.delete(`/admin/users/${userId}`, { params: { reason } }),
};
