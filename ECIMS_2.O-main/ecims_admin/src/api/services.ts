import { api } from './client';
import type { Alert, Agent, LoginResponse, User } from '../types';

export const AuthApi = {
  login: (username: string, password: string) => api.post<LoginResponse>('/auth/login', { username, password }),
  me: () => api.get<User>('/auth/me')
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
  restoreAgent: (agentId: number, reason: string) => api.post(`/admin/agents/${agentId}/restore`, { reason })
};
