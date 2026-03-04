import { api } from './client';
import type {
  AdminUserActivePayload,
  AdminUserCreatePayload,
  AdminUserResetPasswordPayload,
  AdminUserRolePayload,
  Alert,
  Agent,
  FeatureFlag,
  FeatureFlagCreatePayload,
  FeatureFlagListResponse,
  FeatureFlagSetStatePayload,
  EnrollmentToken,
  EnrollmentTokenIssuePayload,
  EnrollmentTokenIssueResponse,
  EnrollmentTokenListResponse,
  EnrollmentTokenRevokePayload,
  LoginResponse,
  MaintenanceScheduleConflictResponse,
  MaintenanceScheduleCreatePayload,
  MaintenanceScheduleCreateResponse,
  MaintenanceScheduleListResponse,
  MaintenanceSchedulePreviewPayload,
  MaintenanceSchedulePreviewResponse,
  MaintenanceScheduleRunDueResponse,
  MaintenanceScheduleStatePayload,
  OfflineEnrollmentKitImportPayload,
  OfflineEnrollmentKitImportResponse,
  RemoteActionTaskCreatePayload,
  RemoteActionTaskCreateResponse,
  RemoteActionTaskListResponse,
  RemoteActionTaskTargetListResponse,
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
  listFeatureFlags: (params?: { q?: string; scope?: string; state?: string }) =>
    api.get<FeatureFlagListResponse>('/admin/features', { params }),
  createFeatureFlag: (payload: FeatureFlagCreatePayload) =>
    api.post<FeatureFlag>('/admin/features', payload),
  setFeatureFlagState: (flagId: number, payload: FeatureFlagSetStatePayload) =>
    api.put<FeatureFlag>(`/admin/features/${flagId}/state`, payload),
  listRemoteActionTasks: (params?: { page?: number; page_size?: number; action?: string; status?: string; q?: string }) =>
    api.get<RemoteActionTaskListResponse>('/admin/ops/remote-actions/tasks', { params }),
  getRemoteActionTaskTargets: (taskId: number) =>
    api.get<RemoteActionTaskTargetListResponse>(`/admin/ops/remote-actions/tasks/${taskId}/targets`),
  createRemoteActionTask: (payload: RemoteActionTaskCreatePayload) =>
    api.post<RemoteActionTaskCreateResponse>('/admin/ops/remote-actions/tasks', payload),
  listSchedules: (params?: { page?: number; page_size?: number; status?: string; timezone?: string; q?: string }) =>
    api.get<MaintenanceScheduleListResponse>('/admin/ops/schedules', { params }),
  createSchedule: (payload: MaintenanceScheduleCreatePayload) =>
    api.post<MaintenanceScheduleCreateResponse>('/admin/ops/schedules', payload),
  previewSchedule: (payload: MaintenanceSchedulePreviewPayload) =>
    api.post<MaintenanceSchedulePreviewResponse>('/admin/ops/schedules/preview', payload),
  getScheduleConflicts: (scheduleId: number) =>
    api.get<MaintenanceScheduleConflictResponse>(`/admin/ops/schedules/${scheduleId}/conflicts`),
  updateScheduleState: (scheduleId: number, payload: MaintenanceScheduleStatePayload) =>
    api.post(`/admin/ops/schedules/${scheduleId}/state`, payload),
  runDueSchedules: (limit = 20) =>
    api.post<MaintenanceScheduleRunDueResponse>('/admin/ops/schedules/run-due', null, { params: { limit } }),
  listEnrollmentTokens: (params?: { page?: number; page_size?: number; mode?: string; status?: string; q?: string }) =>
    api.get<EnrollmentTokenListResponse>('/admin/ops/enrollment/tokens', { params }),
  issueEnrollmentToken: (payload: EnrollmentTokenIssuePayload) =>
    api.post<EnrollmentTokenIssueResponse>('/admin/ops/enrollment/tokens', payload),
  revokeEnrollmentToken: (tokenId: string, payload: EnrollmentTokenRevokePayload) =>
    api.post<{ status: string; item: EnrollmentToken }>(`/admin/ops/enrollment/tokens/${tokenId}/revoke`, payload),
  importOfflineEnrollmentKit: (payload: OfflineEnrollmentKitImportPayload) =>
    api.post<OfflineEnrollmentKitImportResponse>('/admin/ops/enrollment/offline-kit/import', payload),
};
