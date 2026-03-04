import { useEffect, useState } from 'react';
import { FiArchive, FiCheckSquare, FiDownload, FiEye, FiPlus, FiRefreshCw, FiSearch, FiShield, FiXCircle } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import type {
  ChangeRequestCreatePayload,
  ChangeRequestItem,
  ChangeRequestType,
  ChangeRequestRisk,
  ChangeRequestStatus,
  StateBackup,
  StateBackupMeta,
  StateBackupScope,
} from '../../types';

const parseError = (error: any, fallback: string) => error?.response?.data?.detail || error?.message || fallback;
const makeIdempotencyKey = () => `change-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const parseJsonObject = (raw: string): Record<string, unknown> => {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Invalid JSON object');
  }
  return parsed as Record<string, unknown>;
};

const statusBadgeClass = (status: string) => {
  if (status === 'APPROVED') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (status === 'PARTIALLY_APPROVED') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  if (status === 'PENDING') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (status === 'REJECTED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const riskBadgeClass = (risk: string) => {
  if (risk === 'CRITICAL') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (risk === 'HIGH') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
};

type CreateRequestForm = {
  changeType: ChangeRequestType;
  targetRef: string;
  summary: string;
  riskLevel: ChangeRequestRisk;
  reason: string;
  twoPersonRule: boolean;
  idempotencyKey: string;
  proposedJson: string;
  metadataJson: string;
};

const defaultCreateRequestForm: CreateRequestForm = {
  changeType: 'POLICY',
  targetRef: '',
  summary: '',
  riskLevel: 'LOW',
  reason: '',
  twoPersonRule: false,
  idempotencyKey: makeIdempotencyKey(),
  proposedJson: '{}',
  metadataJson: '{"source":"admin-console"}',
};

type BackupCreateForm = {
  scope: StateBackupScope;
  includeSensitive: boolean;
};

const defaultBackupCreateForm: BackupCreateForm = {
  scope: 'CONFIG_ONLY',
  includeSensitive: false,
};

export const ChangeControlPage = () => {
  const [rows, setRows] = useState<ChangeRequestItem[]>([]);
  const [backupRows, setBackupRows] = useState<StateBackupMeta[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [backupStatus, setBackupStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [backupErrorMessage, setBackupErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [riskFilter, setRiskFilter] = useState('all');
  const [backupScopeFilter, setBackupScopeFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState<CreateRequestForm>(defaultCreateRequestForm);

  const [decisionOpen, setDecisionOpen] = useState(false);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionTarget, setDecisionTarget] = useState<ChangeRequestItem | null>(null);
  const [decisionValue, setDecisionValue] = useState<'APPROVE' | 'REJECT'>('APPROVE');
  const [decisionReason, setDecisionReason] = useState('');

  const [backupCreateOpen, setBackupCreateOpen] = useState(false);
  const [backupCreateBusy, setBackupCreateBusy] = useState(false);
  const [backupCreateForm, setBackupCreateForm] = useState<BackupCreateForm>(defaultBackupCreateForm);

  const [backupViewOpen, setBackupViewOpen] = useState(false);
  const [backupViewBusy, setBackupViewBusy] = useState(false);
  const [backupViewData, setBackupViewData] = useState<StateBackup | null>(null);

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 4200);
  };

  const dismissToast = (id: string) => setToasts((prev) => prev.filter((item) => item.id !== id));

  const loadRequests = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listChangeRequests({
        page: 1,
        page_size: 100,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        risk: riskFilter !== 'all' ? riskFilter : undefined,
        q: query.trim() ? query.trim() : undefined,
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: any) {
      setRows([]);
      setStatus('error');
      setErrorMessage(parseError(error, 'Unable to load change requests'));
    }
  };

  const loadBackups = async () => {
    setBackupStatus('loading');
    setBackupErrorMessage('');
    try {
      const response = await CoreApi.listStateBackups({
        page: 1,
        page_size: 100,
        scope: backupScopeFilter !== 'all' ? backupScopeFilter : undefined,
      });
      setBackupRows(response.data.items ?? []);
      setBackupStatus('ready');
    } catch (error: any) {
      setBackupRows([]);
      setBackupStatus('error');
      setBackupErrorMessage(parseError(error, 'Unable to load backups'));
    }
  };

  useEffect(() => {
    void Promise.all([loadRequests(), loadBackups()]);
  }, []);

  const openCreate = () => {
    setCreateForm({ ...defaultCreateRequestForm, idempotencyKey: makeIdempotencyKey() });
    setCreateOpen(true);
  };

  const createRequest = async () => {
    if (createForm.targetRef.trim().length < 2) {
      pushToast({ title: 'Target reference should be at least 2 characters', tone: 'warning' });
      return;
    }
    if (createForm.summary.trim().length < 5) {
      pushToast({ title: 'Summary should be at least 5 characters', tone: 'warning' });
      return;
    }
    if (createForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    let proposedChanges: Record<string, unknown>;
    let metadata: Record<string, unknown>;
    try {
      proposedChanges = parseJsonObject(createForm.proposedJson);
      metadata = parseJsonObject(createForm.metadataJson);
    } catch {
      pushToast({ title: 'Proposed changes or metadata JSON is invalid', tone: 'warning' });
      return;
    }

    const payload: ChangeRequestCreatePayload = {
      change_type: createForm.changeType,
      target_ref: createForm.targetRef.trim(),
      summary: createForm.summary.trim(),
      proposed_changes: proposedChanges,
      risk_level: createForm.riskLevel,
      reason: createForm.reason.trim(),
      two_person_rule: createForm.twoPersonRule,
      idempotency_key: createForm.idempotencyKey.trim(),
      metadata,
    };

    setCreateBusy(true);
    try {
      const response = await CoreApi.createChangeRequest(payload);
      setCreateOpen(false);
      await loadRequests();
      pushToast({
        title: response.data.created ? 'Change request created' : 'Idempotent replay returned existing request',
        description: `Request ID: ${response.data.item.request_id}`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: any) {
      pushToast({ title: 'Create request failed', description: parseError(error, 'Unable to create request'), tone: 'error' });
    } finally {
      setCreateBusy(false);
    }
  };

  const openDecision = (row: ChangeRequestItem, decision: 'APPROVE' | 'REJECT') => {
    setDecisionTarget(row);
    setDecisionValue(decision);
    setDecisionReason('');
    setDecisionOpen(true);
  };

  const decideRequest = async () => {
    if (!decisionTarget) return;
    if (decisionReason.trim().length < 5) {
      pushToast({ title: 'Decision reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setDecisionBusy(true);
    try {
      const response = await CoreApi.decideChangeRequest(decisionTarget.request_id, {
        decision: decisionValue,
        reason: decisionReason.trim(),
      });
      setDecisionOpen(false);
      await loadRequests();
      pushToast({
        title: 'Decision recorded',
        description: `Request ${response.data.request_id} is now ${response.data.status}`,
        tone: response.data.status === 'REJECTED' ? 'warning' : 'success',
      });
    } catch (error: any) {
      pushToast({ title: 'Decision failed', description: parseError(error, 'Unable to decide request'), tone: 'error' });
    } finally {
      setDecisionBusy(false);
    }
  };

  const createBackup = async () => {
    setBackupCreateBusy(true);
    try {
      const response = await CoreApi.createStateBackup({
        scope: backupCreateForm.scope,
        include_sensitive: backupCreateForm.includeSensitive,
      });
      setBackupCreateOpen(false);
      await loadBackups();
      pushToast({
        title: 'Backup snapshot created',
        description: `Backup ID: ${response.data.backup_id}`,
        tone: 'success',
      });
    } catch (error: any) {
      pushToast({ title: 'Backup creation failed', description: parseError(error, 'Unable to create backup'), tone: 'error' });
    } finally {
      setBackupCreateBusy(false);
    }
  };

  const openBackupView = async (backupId: string) => {
    setBackupViewOpen(true);
    setBackupViewBusy(true);
    setBackupViewData(null);
    try {
      const response = await CoreApi.getStateBackup(backupId);
      setBackupViewData(response.data);
    } catch (error: any) {
      pushToast({ title: 'Load backup failed', description: parseError(error, 'Unable to load backup bundle'), tone: 'error' });
      setBackupViewOpen(false);
    } finally {
      setBackupViewBusy(false);
    }
  };

  const downloadBackup = (backup: StateBackup) => {
    const content = JSON.stringify(backup.bundle, null, 2);
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `state-backup-${backup.backup_id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const requestColumns: DataTableColumn<ChangeRequestItem>[] = [
    {
      key: 'request_id',
      header: 'Request',
      render: (row) => (
        <div className="flex max-w-[220px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.request_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.change_type}</span>
        </div>
      ),
    },
    {
      key: 'summary',
      header: 'Summary',
      render: (row) => <span className="max-w-[320px] truncate">{row.summary}</span>,
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${riskBadgeClass(row.risk_level)}`}>{row.risk_level}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    {
      key: 'requested_by',
      header: 'Requested By',
      render: (row) => row.requested_by_username || `User #${row.requested_by_user_id}`,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => formatDate(row.created_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) =>
        row.status === 'PENDING' || row.status === 'PARTIALLY_APPROVED' ? (
          <div className="flex gap-1.5">
            <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openDecision(row, 'APPROVE')}>
              <FiCheckSquare className="mr-1 text-xs" />
              Approve
            </button>
            <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openDecision(row, 'REJECT')}>
              <FiXCircle className="mr-1 text-xs" />
              Reject
            </button>
          </div>
        ) : (
          <span className="text-xs text-slate-400 dark:text-slate-500">-</span>
        ),
    },
  ];

  const backupColumns: DataTableColumn<StateBackupMeta>[] = [
    {
      key: 'backup_id',
      header: 'Backup',
      render: (row) => (
        <div className="flex max-w-[220px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.backup_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.bundle_hash}</span>
        </div>
      ),
    },
    { key: 'scope', header: 'Scope' },
    { key: 'row_count', header: 'Rows' },
    { key: 'created_by_username', header: 'Created By', render: (row) => row.created_by_username || `User #${row.created_by_user_id}` },
    { key: 'created_at', header: 'Created', render: (row) => formatDate(row.created_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void openBackupView(row.backup_id)}>
          <FiEye className="mr-1 text-xs" />
          View
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Change Control"
        subtitle="Approval workflows with two-person rule and auditable state backup snapshots for controlled releases."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void Promise.all([loadRequests(), loadBackups()])}
            >
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-secondary" onClick={() => setBackupCreateOpen(true)}>
              <FiArchive className="mr-2 text-sm" />
              Create Backup
            </button>
            <button type="button" className="btn-primary" onClick={openCreate}>
              <FiPlus className="mr-2 text-sm" />
              Submit Change
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_200px_180px_200px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search request id, summary, target"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Request Status</option>
            <option value="PENDING">PENDING</option>
            <option value="PARTIALLY_APPROVED">PARTIALLY_APPROVED</option>
            <option value="APPROVED">APPROVED</option>
            <option value="REJECTED">REJECTED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>

          <select
            value={riskFilter}
            onChange={(event) => setRiskFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Risk Levels</option>
            <option value="LOW">LOW</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>

          <select
            value={backupScopeFilter}
            onChange={(event) => setBackupScopeFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Backup Scopes</option>
            <option value="CONFIG_ONLY">CONFIG_ONLY</option>
            <option value="FULL">FULL</option>
          </select>

          <button
            type="button"
            className="btn-secondary h-11"
            onClick={() => void Promise.all([loadRequests(), loadBackups()])}
          >
            Apply
          </button>
        </div>
      </Card>

      <Card title="Change Requests" subtitle="Two-step governance for high-risk configuration and policy mutations.">
        {status === 'loading' && <LoadingState title="Loading requests" description="Fetching change-control requests." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadRequests()} />}
        {status === 'ready' && rows.length > 0 && <DataTable columns={requestColumns} rows={rows} rowKey={(row) => row.request_id} />}
        {status === 'ready' && rows.length === 0 && (
          <EmptyState
            title="No change requests"
            description="Submit a request before mutating critical policy or control-plane config."
            actionLabel="Submit Change"
            onAction={openCreate}
          />
        )}
      </Card>

      <Card title="State Backups" subtitle="Point-in-time snapshots for user/config/ops state before patch rollout or risky changes.">
        {backupStatus === 'loading' && <LoadingState title="Loading backups" description="Fetching backup snapshots." />}
        {backupStatus === 'error' && <ErrorState description={backupErrorMessage} onRetry={() => void loadBackups()} />}
        {backupStatus === 'ready' && backupRows.length > 0 && (
          <DataTable columns={backupColumns} rows={backupRows} rowKey={(row) => row.backup_id} />
        )}
        {backupStatus === 'ready' && backupRows.length === 0 && (
          <EmptyState
            title="No backup snapshots"
            description="Create a snapshot before deploying patch updates."
            actionLabel="Create Backup"
            onAction={() => setBackupCreateOpen(true)}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Submit Change Request"
        description="Define target, risk, and proposed config for approval workflow."
        confirmLabel={createBusy ? 'Submitting...' : 'Submit Request'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (createBusy) return;
          setCreateOpen(false);
        }}
        onConfirm={() => void createRequest()}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.changeType}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, changeType: event.target.value as ChangeRequestType }))}
            >
              <option value="POLICY">POLICY</option>
              <option value="FEATURE_FLAG">FEATURE_FLAG</option>
              <option value="PLAYBOOK">PLAYBOOK</option>
              <option value="SCHEDULE">SCHEDULE</option>
              <option value="ENROLLMENT_POLICY">ENROLLMENT_POLICY</option>
              <option value="BREAK_GLASS_POLICY">BREAK_GLASS_POLICY</option>
            </select>
            <select
              className="input"
              value={createForm.riskLevel}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, riskLevel: event.target.value as ChangeRequestRisk }))}
            >
              <option value="LOW">LOW</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
          </div>

          <input
            className="input"
            value={createForm.targetRef}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, targetRef: event.target.value }))}
            placeholder="Target reference (policy key, playbook id, etc)"
          />

          <textarea
            className="input min-h-[84px] resize-y"
            value={createForm.summary}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, summary: event.target.value }))}
            placeholder="Summary"
          />

          <textarea
            className="input min-h-[84px] resize-y"
            value={createForm.reason}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Reason (min 5 chars)"
          />

          <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <input
              type="checkbox"
              checked={createForm.twoPersonRule}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, twoPersonRule: event.target.checked }))}
            />
            Force two-person rule
          </label>

          <input
            className="input"
            value={createForm.idempotencyKey}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, idempotencyKey: event.target.value }))}
            placeholder="Idempotency key"
          />

          <textarea
            className="input min-h-[96px] resize-y font-mono text-xs"
            value={createForm.proposedJson}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, proposedJson: event.target.value }))}
            placeholder="Proposed changes JSON"
          />

          <textarea
            className="input min-h-[96px] resize-y font-mono text-xs"
            value={createForm.metadataJson}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, metadataJson: event.target.value }))}
            placeholder="Metadata JSON"
          />
        </div>
      </Modal>

      <Modal
        open={decisionOpen}
        title={decisionTarget ? `Request Decision - ${decisionTarget.request_id}` : 'Request Decision'}
        description={`Decision: ${decisionValue}`}
        confirmLabel={decisionBusy ? 'Submitting...' : decisionValue}
        cancelLabel="Cancel"
        onCancel={() => {
          if (decisionBusy) return;
          setDecisionOpen(false);
          setDecisionTarget(null);
        }}
        onConfirm={() => void decideRequest()}
      >
        <textarea
          className="input min-h-[96px] resize-y"
          value={decisionReason}
          onChange={(event) => setDecisionReason(event.target.value)}
          placeholder="Decision reason (min 5 chars)"
        />
      </Modal>

      <Modal
        open={backupCreateOpen}
        title="Create State Backup"
        description="Generate point-in-time snapshot for rollback readiness."
        confirmLabel={backupCreateBusy ? 'Creating...' : 'Create Snapshot'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (backupCreateBusy) return;
          setBackupCreateOpen(false);
        }}
        onConfirm={() => void createBackup()}
      >
        <div className="space-y-3">
          <select
            className="input"
            value={backupCreateForm.scope}
            onChange={(event) => setBackupCreateForm((prev) => ({ ...prev, scope: event.target.value as StateBackupScope }))}
          >
            <option value="CONFIG_ONLY">CONFIG_ONLY</option>
            <option value="FULL">FULL</option>
          </select>
          <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900">
            <input
              type="checkbox"
              checked={backupCreateForm.includeSensitive}
              onChange={(event) => setBackupCreateForm((prev) => ({ ...prev, includeSensitive: event.target.checked }))}
            />
            Include sensitive fields (tokens/hash columns)
          </label>
        </div>
      </Modal>

      <Modal
        open={backupViewOpen}
        title={backupViewData ? `Backup ${backupViewData.backup_id}` : 'Backup Snapshot'}
        description="Review and export backup bundle payload."
        cancelLabel="Close"
        onCancel={() => {
          setBackupViewOpen(false);
          setBackupViewData(null);
        }}
      >
        {backupViewBusy && <LoadingState title="Loading backup" description="Fetching backup bundle payload." />}
        {!backupViewBusy && backupViewData && (
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900">
              <p>Scope: {backupViewData.scope}</p>
              <p>Rows: {backupViewData.row_count}</p>
              <p>Created: {formatDate(backupViewData.created_at)}</p>
            </div>
            <div className="flex justify-end">
              <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => downloadBackup(backupViewData)}>
                <FiDownload className="mr-1 text-xs" />
                Download JSON
              </button>
            </div>
            <textarea readOnly value={JSON.stringify(backupViewData.bundle, null, 2)} className="input min-h-[220px] resize-y font-mono text-xs" />
          </div>
        )}
      </Modal>

      <Card>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiShield className="mr-2 inline text-sm" />
            Change governance notes
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            High and critical requests are automatically promoted to two-person approval.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Use `CONFIG_ONLY` backup before daily updates, and `FULL` backup before structural migrations.
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
