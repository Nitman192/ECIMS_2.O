export type DataStatus = 'ready' | 'loading' | 'error';

export type AdminUserRow = {
  id: string;
  username: string;
  role: string;
  status: 'active' | 'disabled';
  lastLogin: string;
};

export type RbacMatrixRow = {
  role: string;
  scope: string;
  permissions: string;
  updatedAt: string;
};

export type FeatureFlagRow = {
  key: string;
  scope: 'global' | 'user' | 'agent';
  state: 'on' | 'off';
  risk: 'low' | 'high';
};

export type AuditEventRow = {
  id: string;
  actor: string;
  action: string;
  resource: string;
  timestamp: string;
};

export type RemoteActionTaskRow = {
  id: string;
  action: string;
  targetCount: number;
  status: 'PENDING' | 'SENT' | 'ACK' | 'DONE' | 'FAILED';
  createdAt: string;
};

export type MaintenanceScheduleRow = {
  id: string;
  windowName: string;
  timezone: string;
  nextRun: string;
  state: 'draft' | 'active' | 'paused';
};

export type EnrollmentTokenRow = {
  id: string;
  mode: 'online' | 'offline';
  expiresAt: string;
  remainingUses: number;
  createdBy: string;
};

export type FleetHealthRow = {
  hostname: string;
  lastSeen: string;
  policyVersion: string;
  encryption: 'enabled' | 'disabled';
  mtls: 'healthy' | 'degraded';
};

export type QuarantineCaseRow = {
  caseId: string;
  host: string;
  trigger: string;
  state: 'isolated' | 'pending_release';
  updatedAt: string;
};

export type EvidenceItemRow = {
  id: string;
  hash: string;
  source: string;
  custodyState: 'sealed' | 'in_review';
  capturedAt: string;
};

export type PlaybookRow = {
  id: string;
  name: string;
  trigger: string;
  approvalMode: 'manual' | 'auto';
  updatedAt: string;
};

export type ChangeControlRow = {
  id: string;
  policyName: string;
  requestedBy: string;
  approvalState: 'pending' | 'approved' | 'rejected';
  requestedAt: string;
};

export type BreakGlassSessionRow = {
  id: string;
  actor: string;
  reason: string;
  expiresAt: string;
  state: 'active' | 'expired';
};

