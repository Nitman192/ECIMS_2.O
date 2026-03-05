import { useEffect, useState } from 'react';
import { FiCopy, FiKey, FiPlus, FiRefreshCw, FiSearch, FiShield, FiSlash } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { createIdempotencyKey, validateIdempotencyKey } from '../../utils/idempotency';
import { toOptionalFilter, toOptionalQuery } from '../../utils/listQuery';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import type { BreakGlassScope, BreakGlassSession } from '../../types';

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const parseJsonObject = (raw: string): Record<string, unknown> => {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON object expected');
  }
  return parsed as Record<string, unknown>;
};

const statusBadgeClass = (status: string) => {
  if (status === 'ACTIVE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (status === 'EXPIRED') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
};

type CreateForm = {
  currentPassword: string;
  reason: string;
  scope: BreakGlassScope;
  durationMinutes: number;
  idempotencyKey: string;
  metadataJson: string;
};

const defaultCreateForm: CreateForm = {
  currentPassword: '',
  reason: '',
  scope: 'INCIDENT_RESPONSE',
  durationMinutes: 30,
  idempotencyKey: createIdempotencyKey('breakglass'),
  metadataJson: '{"source":"admin-console"}',
};

export const BreakGlassPage = () => {
  const [rows, setRows] = useState<BreakGlassSession[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(defaultCreateForm);
  const [resultOpen, setResultOpen] = useState(false);
  const [resultToken, setResultToken] = useState('');
  const [resultSessionId, setResultSessionId] = useState('');

  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<BreakGlassSession | null>(null);
  const [revokeReason, setRevokeReason] = useState('');

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((item) => item.id !== id)), 4200);
  };

  const dismissToast = (id: string) => setToasts((prev) => prev.filter((item) => item.id !== id));

  const loadSessions = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listBreakGlassSessions({
        page: 1,
        page_size: 100,
        status: toOptionalFilter(statusFilter),
        q: toOptionalQuery(query),
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: unknown) {
      setRows([]);
      setStatus('error');
      setErrorMessage(getApiErrorMessage(error, 'Unable to load break-glass sessions'));
    }
  };

  useEffect(() => {
    void loadSessions();
  }, []);

  const openCreate = () => {
    setCreateForm({ ...defaultCreateForm, idempotencyKey: createIdempotencyKey('breakglass') });
    setCreateOpen(true);
  };

  const createSession = async () => {
    if (createForm.currentPassword.trim().length < 1) {
      pushToast({ title: 'Current password is required for re-auth', tone: 'warning' });
      return;
    }
    if (createForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    if (createForm.durationMinutes < 5 || createForm.durationMinutes > 240) {
      pushToast({ title: 'Duration must be between 5 and 240 minutes', tone: 'warning' });
      return;
    }
    const key = createForm.idempotencyKey.trim();
    const idempotencyError = validateIdempotencyKey(key, { minLength: 8 });
    if (idempotencyError) {
      pushToast({ title: idempotencyError, tone: 'warning' });
      return;
    }

    let metadata: Record<string, unknown>;
    try {
      metadata = parseJsonObject(createForm.metadataJson);
    } catch {
      pushToast({ title: 'Metadata JSON is invalid', tone: 'warning' });
      return;
    }

    setCreateBusy(true);
    try {
      const response = await CoreApi.createBreakGlassSession({
        current_password: createForm.currentPassword,
        reason: createForm.reason.trim(),
        scope: createForm.scope,
        duration_minutes: createForm.durationMinutes,
        idempotency_key: key,
        metadata,
      });
      setCreateOpen(false);
      await loadSessions();
      pushToast({
        title: response.data.created ? 'Break-glass session started' : 'Idempotent replay returned existing session',
        description: `Session ID: ${response.data.item.session_id}`,
        tone: response.data.created ? 'success' : 'info',
      });
      if (response.data.break_glass_token) {
        setResultToken(response.data.break_glass_token);
        setResultSessionId(response.data.item.session_id);
        setResultOpen(true);
      }
    } catch (error: unknown) {
      pushToast({ title: 'Start session failed', description: getApiErrorMessage(error, 'Unable to start break-glass session'), tone: 'error' });
    } finally {
      setCreateBusy(false);
    }
  };

  const openRevoke = (row: BreakGlassSession) => {
    setRevokeTarget(row);
    setRevokeReason('');
    setRevokeOpen(true);
  };

  const revokeSession = async () => {
    if (!revokeTarget) return;
    if (revokeReason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    setRevokeBusy(true);
    try {
      await CoreApi.revokeBreakGlassSession(revokeTarget.session_id, { reason: revokeReason.trim() });
      setRevokeOpen(false);
      setRevokeTarget(null);
      await loadSessions();
      pushToast({
        title: 'Session revoked',
        description: `Session ${revokeTarget.session_id} moved to REVOKED`,
        tone: 'success',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Revoke failed', description: getApiErrorMessage(error, 'Unable to revoke session'), tone: 'error' });
    } finally {
      setRevokeBusy(false);
    }
  };

  const copyToken = async () => {
    try {
      if (!navigator.clipboard) {
        pushToast({ title: 'Clipboard unavailable', tone: 'warning' });
        return;
      }
      await navigator.clipboard.writeText(resultToken);
      pushToast({ title: 'Break-glass token copied', tone: 'success' });
    } catch {
      pushToast({ title: 'Token copy failed', tone: 'error' });
    }
  };

  const columns: DataTableColumn<BreakGlassSession>[] = [
    {
      key: 'session_id',
      header: 'Session',
      render: (row) => (
        <div className="flex max-w-[220px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.session_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.scope}</span>
        </div>
      ),
    },
    {
      key: 'requested_by_username',
      header: 'Requested By',
      render: (row) => row.requested_by_username || `User #${row.requested_by_user_id}`,
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    { key: 'duration_minutes', header: 'Duration', render: (row) => `${row.duration_minutes} min` },
    { key: 'expires_at', header: 'Expires', render: (row) => formatDate(row.expires_at) },
    { key: 'reason', header: 'Reason', render: (row) => <span className="max-w-[220px] truncate">{row.reason}</span> },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) =>
        row.status === 'ACTIVE' ? (
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openRevoke(row)}>
            <FiSlash className="mr-1 text-xs" />
            Revoke
          </button>
        ) : (
          <span className="text-xs text-slate-400 dark:text-slate-500">-</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Break Glass"
        subtitle="Emergency access sessions with forced re-authentication, strict expiry, and full audit coverage."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadSessions()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={openCreate}>
              <FiPlus className="mr-2 text-sm" />
              Start Session
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_200px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search session id, reason, requester"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="REVOKED">REVOKED</option>
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadSessions()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Emergency Sessions" subtitle="Time-bound emergency access sessions with revocation and expiry tracking.">
        {status === 'loading' && <LoadingState title="Loading sessions" description="Fetching break-glass sessions." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadSessions()} />}
        {status === 'ready' && rows.length > 0 && <DataTable columns={columns} rows={rows} rowKey={(row) => row.session_id} />}
        {status === 'ready' && rows.length === 0 && (
          <EmptyState
            title="No emergency sessions"
            description="Start a session only when normal access paths are blocked."
            actionLabel="Start Session"
            onAction={openCreate}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Start Break-glass Session"
        description="Requires current password re-auth and explicit emergency reason."
        confirmLabel={createBusy ? 'Starting...' : 'Start Session'}
        confirmDisabled={createBusy}
        cancelLabel="Cancel"
        cancelDisabled={createBusy}
        onCancel={() => {
          setCreateOpen(false);
        }}
        onConfirm={() => void createSession()}
      >
        <div className="space-y-3">
          <input
            type="password"
            className="input"
            value={createForm.currentPassword}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, currentPassword: event.target.value }))}
            placeholder="Current password (re-auth)"
          />
          <textarea
            className="input min-h-[84px] resize-y"
            value={createForm.reason}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Emergency reason (min 5 chars)"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.scope}
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, scope: event.target.value as BreakGlassScope }))}
            >
              <option value="INCIDENT_RESPONSE">INCIDENT_RESPONSE</option>
              <option value="SYSTEM_RECOVERY">SYSTEM_RECOVERY</option>
              <option value="FORENSICS">FORENSICS</option>
              <option value="OTHER">OTHER</option>
            </select>
            <input
              type="number"
              min={5}
              max={240}
              className="input"
              value={createForm.durationMinutes}
              disabled={createBusy}
              onChange={(event) =>
                setCreateForm((prev) => ({
                  ...prev,
                  durationMinutes: Math.max(5, Math.min(240, Number(event.target.value) || 5)),
                }))
              }
              placeholder="Duration (min)"
            />
          </div>
          <input
            className="input"
            value={createForm.idempotencyKey}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, idempotencyKey: event.target.value }))}
            placeholder="Idempotency key"
          />
          <textarea
            className="input min-h-[96px] resize-y font-mono text-xs"
            value={createForm.metadataJson}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, metadataJson: event.target.value }))}
            placeholder="Metadata JSON"
          />
        </div>
      </Modal>

      <Modal
        open={revokeOpen}
        title={revokeTarget ? `Revoke ${revokeTarget.session_id}` : 'Revoke Session'}
        description="Revocation is immediate and audit logged."
        confirmLabel={revokeBusy ? 'Revoking...' : 'Revoke'}
        confirmDisabled={revokeBusy}
        cancelLabel="Cancel"
        cancelDisabled={revokeBusy}
        onCancel={() => {
          setRevokeOpen(false);
          setRevokeTarget(null);
        }}
        onConfirm={() => void revokeSession()}
      >
        <textarea
          className="input min-h-[96px] resize-y"
          value={revokeReason}
          disabled={revokeBusy}
          onChange={(event) => setRevokeReason(event.target.value)}
          placeholder="Revoke reason (min 5 chars)"
        />
      </Modal>

      <Modal
        open={resultOpen}
        title="Break-glass Session Token"
        description={`Session ${resultSessionId} started. Copy token now; it is shown once.`}
        cancelLabel="Close"
        onCancel={() => {
          setResultOpen(false);
          setResultToken('');
          setResultSessionId('');
        }}
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Session Token</p>
              <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void copyToken()}>
                <FiCopy className="mr-1 text-xs" />
                Copy
              </button>
            </div>
            <p className="break-all rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
              {resultToken}
            </p>
          </div>
        </div>
      </Modal>

      <Card>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiShield className="mr-2 inline text-sm" />
            Break-glass controls
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Forced re-auth with current password is mandatory for every session creation request.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Sessions auto-expire by duration, and all start/revoke events are audited.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            <FiKey className="mr-1 inline text-xs" />
            Keep emergency tokens inside secure incident vault only.
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
