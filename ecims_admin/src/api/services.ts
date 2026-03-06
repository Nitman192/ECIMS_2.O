import { api } from './client';
import type {
  AdminUserActivePayload,
  AdminMetricsResponse,
  AdminUserCreatePayload,
  AdminUserResetPasswordPayload,
  AdminUserRolePayload,
  Alert,
  Agent,
  AgentSelfStatusResponse,
  BreakGlassSession,
  BreakGlassSessionCreatePayload,
  BreakGlassSessionCreateResponse,
  BreakGlassSessionListResponse,
  BreakGlassSessionRevokePayload,
  ChangeRequestCreatePayload,
  ChangeRequestCreateResponse,
  ChangeRequestDecisionPayload,
  ChangeRequestItem,
  ChangeRequestListResponse,
  DeviceRolloutStatusResponse,
  DeviceAllowTokenIssuePayload,
  DeviceAllowTokenIssueResponse,
  DeviceSecureDeclarePayload,
  DeviceSecureDeclareResponse,
  FeatureFlag,
  FeatureFlagCreatePayload,
  FeatureFlagListResponse,
  FeatureFlagSetStatePayload,
  FleetDriftResponse,
  EnrollmentToken,
  EvidenceCustodyEventCreatePayload,
  EvidenceCustodyEvent,
  EvidenceExportPayload,
  EvidenceExportResponse,
  EvidenceObject,
  EvidenceObjectCreatePayload,
  EvidenceObjectCreateResponse,
  EvidenceTimelineResponse,
  EvidenceVaultListResponse,
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
  PatchUpdateApplyPayload,
  PatchUpdateApplyResponse,
  PatchUpdateItem,
  PatchUpdateListResponse,
  Playbook,
  PlaybookCreatePayload,
  PlaybookCreateResponse,
  PlaybookExecutePayload,
  PlaybookListResponse,
  PlaybookRun,
  PlaybookRunDecisionPayload,
  PlaybookRunListResponse,
  RemoteActionTaskCreatePayload,
  RemoteActionTaskCreateResponse,
  RemoteActionTaskListResponse,
  RemoteActionTaskTargetListResponse,
  StateBackup,
  StateBackupRestoreApplyPayload,
  StateBackupRestoreApplyResponse,
  StateBackupCreatePayload,
  StateBackupListResponse,
  StateBackupRestorePreviewPayload,
  StateBackupRestorePreviewResponse,
  RoleMatrixEntry,
  User,
} from '../types';

export const AuthApi = {
  login: (username: string, password: string) => api.post<LoginResponse>('/auth/login', { username, password }),
  me: () => api.get<User>('/auth/me'),
  resetMyPassword: (payload: { current_password: string; new_password: string }) =>
    api.post('/auth/password/reset', payload),
};

export const CoreApi = {
  metrics: () => api.get<AdminMetricsResponse>('/admin/metrics'),
  deviceRolloutStatus: () => api.get<DeviceRolloutStatusResponse>('/admin/device/rollout/status'),
  fleetDrift: () => api.get<FleetDriftResponse>('/admin/device/fleet/drift'),
  secureDeclareDevice: (payload: DeviceSecureDeclarePayload) =>
    api.post<DeviceSecureDeclareResponse>('/admin/device/secure-declare', payload),
  issueDeviceAllowToken: (payload: DeviceAllowTokenIssuePayload) =>
    api.post<DeviceAllowTokenIssueResponse>('/admin/device/allow-token', payload),
  agents: () => api.get<Agent[]>('/agents'),
  alerts: () => api.get<Alert[]>('/alerts'),
  securityStatus: () => api.get('/security/status'),
  licenseStatus: () => api.get('/license/status'),
  auditLogs: (params?: Record<string, string>) => api.get('/admin/audit', { params }),
  exportAudit: (payload: Record<string, unknown>) => api.post('/admin/audit/export', payload),
  revokeAgent: (agentId: number, reason: string) => api.post(`/admin/agents/${agentId}/revoke`, { reason }),
  restoreAgent: (agentId: number, reason: string) => api.post(`/admin/agents/${agentId}/restore`, { reason }),
  getAgentSelfStatus: (agentId: number) => api.get<AgentSelfStatusResponse>(`/admin/agents/${agentId}/self-status`),
  rolesMatrix: () => api.get<RoleMatrixEntry[]>('/admin/roles/matrix'),
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
  listEvidenceVault: (params?: { page?: number; page_size?: number; status?: string; origin?: string; q?: string }) =>
    api.get<EvidenceVaultListResponse>('/admin/ops/evidence-vault', { params }),
  createEvidenceObject: (payload: EvidenceObjectCreatePayload) =>
    api.post<EvidenceObjectCreateResponse>('/admin/ops/evidence-vault', payload),
  getEvidenceObject: (evidenceId: string) =>
    api.get<EvidenceObject>(`/admin/ops/evidence-vault/${evidenceId}`),
  getEvidenceTimeline: (evidenceId: string) =>
    api.get<EvidenceTimelineResponse>(`/admin/ops/evidence-vault/${evidenceId}/timeline`),
  appendEvidenceCustodyEvent: (evidenceId: string, payload: EvidenceCustodyEventCreatePayload) =>
    api.post<{ item: EvidenceObject; event: EvidenceCustodyEvent }>(`/admin/ops/evidence-vault/${evidenceId}/custody`, payload),
  exportEvidenceBundle: (evidenceId: string, payload: EvidenceExportPayload) =>
    api.post<EvidenceExportResponse>(`/admin/ops/evidence-vault/${evidenceId}/export`, payload),
  listPlaybooks: (params?: { page?: number; page_size?: number; status?: string; approval_mode?: string; q?: string }) =>
    api.get<PlaybookListResponse>('/admin/ops/playbooks', { params }),
  createPlaybook: (payload: PlaybookCreatePayload) =>
    api.post<PlaybookCreateResponse>('/admin/ops/playbooks', payload),
  listPlaybookRuns: (params?: { page?: number; page_size?: number; playbook_id?: string; status?: string; q?: string }) =>
    api.get<PlaybookRunListResponse>('/admin/ops/playbooks/runs', { params }),
  executePlaybook: (playbookId: string, payload: PlaybookExecutePayload) =>
    api.post<PlaybookRun>(`/admin/ops/playbooks/${playbookId}/execute`, payload),
  decidePlaybookRun: (runId: string, payload: PlaybookRunDecisionPayload) =>
    api.post<PlaybookRun>(`/admin/ops/playbooks/runs/${runId}/decision`, payload),
  listChangeRequests: (params?: { page?: number; page_size?: number; status?: string; risk?: string; q?: string }) =>
    api.get<ChangeRequestListResponse>('/admin/ops/change-control/requests', { params }),
  createChangeRequest: (payload: ChangeRequestCreatePayload) =>
    api.post<ChangeRequestCreateResponse>('/admin/ops/change-control/requests', payload),
  decideChangeRequest: (requestId: string, payload: ChangeRequestDecisionPayload) =>
    api.post<ChangeRequestItem>(`/admin/ops/change-control/requests/${requestId}/decision`, payload),
  listBreakGlassSessions: (params?: { page?: number; page_size?: number; status?: string; q?: string }) =>
    api.get<BreakGlassSessionListResponse>('/admin/ops/break-glass/sessions', { params }),
  createBreakGlassSession: (payload: BreakGlassSessionCreatePayload) =>
    api.post<BreakGlassSessionCreateResponse>('/admin/ops/break-glass/sessions', payload),
  revokeBreakGlassSession: (sessionId: string, payload: BreakGlassSessionRevokePayload) =>
    api.post<{ status: string; item: BreakGlassSession }>(`/admin/ops/break-glass/sessions/${sessionId}/revoke`, payload),
  listStateBackups: (params?: { page?: number; page_size?: number; scope?: string; q?: string }) =>
    api.get<StateBackupListResponse>('/admin/ops/state-backups', { params }),
  createStateBackup: (payload: StateBackupCreatePayload) =>
    api.post<StateBackup>('/admin/ops/state-backups', payload),
  getStateBackup: (backupId: string) =>
    api.get<StateBackup>(`/admin/ops/state-backups/${backupId}`),
  previewStateBackupRestore: (backupId: string, payload: StateBackupRestorePreviewPayload) =>
    api.post<StateBackupRestorePreviewResponse>(`/admin/ops/state-backups/${backupId}/restore/preview`, payload),
  applyStateBackupRestore: (backupId: string, payload: StateBackupRestoreApplyPayload) =>
    api.post<StateBackupRestoreApplyResponse>(`/admin/ops/state-backups/${backupId}/restore/apply`, payload),
  listPatchUpdates: (params?: { page?: number; page_size?: number; status?: string; q?: string }) =>
    api.get<PatchUpdateListResponse>('/admin/ops/patch-updates', { params }),
  uploadPatchUpdate: (payload: FormData) =>
    api.post<{ item: PatchUpdateItem }>('/admin/ops/patch-updates/upload', payload, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  downloadPatchUpdate: (patchId: string) =>
    api.get<Blob>(`/admin/ops/patch-updates/${patchId}/download`, { responseType: 'blob' }),
  applyPatchUpdate: (patchId: string, payload: PatchUpdateApplyPayload) =>
    api.post<PatchUpdateApplyResponse>(`/admin/ops/patch-updates/${patchId}/apply`, payload),
};
