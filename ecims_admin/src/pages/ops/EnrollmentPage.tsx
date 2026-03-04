import { useEffect, useState } from 'react';
import {
  FiCopy,
  FiDownload,
  FiKey,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiSlash,
  FiUpload,
} from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import type { EnrollmentMode, EnrollmentReasonCode, EnrollmentToken } from '../../types';

const reasonOptions: Array<{ value: EnrollmentReasonCode; label: string }> = [
  { value: 'MAINTENANCE', label: 'Maintenance' },
  { value: 'OFFLINE_AIRGAP', label: 'Offline / Air-gapped' },
  { value: 'BOOTSTRAP', label: 'Bootstrap' },
  { value: 'INCIDENT_RESPONSE', label: 'Incident Response' },
  { value: 'TESTING', label: 'Testing' },
  { value: 'COMPLIANCE', label: 'Compliance' },
];

const makeIdempotencyKey = () => `enroll-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
const parseError = (error: any, fallback: string) => error?.response?.data?.detail || error?.message || fallback;

const modeBadgeClass = (value: string) => {
  if (value === 'OFFLINE') return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300';
  return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
};

const statusBadgeClass = (value: string) => {
  if (value === 'ACTIVE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'REVOKED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (value === 'EXPIRED') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

type IssueForm = {
  mode: EnrollmentMode;
  expiresInHours: number;
  maxUses: number;
  reasonCode: EnrollmentReasonCode;
  reason: string;
  idempotencyKey: string;
  metadataJson: string;
};

type IssueResult = {
  item: EnrollmentToken;
  enrollmentToken?: string | null;
  cliSnippets?: {
    powershell: string;
    linux: string;
  } | null;
  offlineKitBundle?: Record<string, unknown> | null;
};

const defaultIssueForm: IssueForm = {
  mode: 'ONLINE',
  expiresInHours: 72,
  maxUses: 1,
  reasonCode: 'BOOTSTRAP',
  reason: '',
  idempotencyKey: makeIdempotencyKey(),
  metadataJson: '{"source":"admin-console"}',
};

export const EnrollmentPage = () => {
  const [rows, setRows] = useState<EnrollmentToken[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [modeFilter, setModeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const [issueOpen, setIssueOpen] = useState(false);
  const [issueBusy, setIssueBusy] = useState(false);
  const [issueForm, setIssueForm] = useState<IssueForm>(defaultIssueForm);
  const [issueResult, setIssueResult] = useState<IssueResult | null>(null);
  const [resultOpen, setResultOpen] = useState(false);

  const [importOpen, setImportOpen] = useState(false);
  const [importBusy, setImportBusy] = useState(false);
  const [importJson, setImportJson] = useState('');

  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState(false);
  const [revokeReason, setRevokeReason] = useState('');
  const [revokeTarget, setRevokeTarget] = useState<EnrollmentToken | null>(null);

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 4200);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  };

  const loadTokens = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listEnrollmentTokens({
        page: 1,
        page_size: 100,
        mode: modeFilter !== 'all' ? modeFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        q: query.trim() ? query.trim() : undefined,
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: any) {
      setRows([]);
      setStatus('error');
      setErrorMessage(parseError(error, 'Unable to load enrollment tokens'));
    }
  };

  useEffect(() => {
    void loadTokens();
  }, []);

  const resetIssueForm = () => {
    setIssueForm({ ...defaultIssueForm, idempotencyKey: makeIdempotencyKey() });
  };

  const openIssueModal = () => {
    resetIssueForm();
    setIssueOpen(true);
  };

  const issueToken = async () => {
    if (issueForm.reason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }

    let metadata: Record<string, unknown> = {};
    try {
      const parsed = issueForm.metadataJson.trim() ? JSON.parse(issueForm.metadataJson) : {};
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        metadata = parsed as Record<string, unknown>;
      } else {
        pushToast({ title: 'Metadata JSON must be an object', tone: 'warning' });
        return;
      }
    } catch {
      pushToast({ title: 'Metadata JSON is invalid', tone: 'warning' });
      return;
    }

    setIssueBusy(true);
    try {
      const response = await CoreApi.issueEnrollmentToken({
        mode: issueForm.mode,
        expires_in_hours: issueForm.expiresInHours,
        max_uses: issueForm.maxUses,
        reason_code: issueForm.reasonCode,
        reason: issueForm.reason.trim(),
        idempotency_key: issueForm.idempotencyKey.trim(),
        metadata,
      });
      setIssueOpen(false);
      await loadTokens();

      setIssueResult({
        item: response.data.item,
        enrollmentToken: response.data.enrollment_token,
        cliSnippets: response.data.cli_snippets,
        offlineKitBundle: response.data.offline_kit_bundle,
      });
      setResultOpen(Boolean(response.data.enrollment_token || response.data.offline_kit_bundle));

      pushToast({
        title: response.data.created ? 'Enrollment token issued' : 'Idempotent replay returned existing token',
        description: response.data.created
          ? `Token ${response.data.item.token_id} created in ${response.data.item.mode} mode`
          : `Token ${response.data.item.token_id} already existed for this request key`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: any) {
      pushToast({
        title: 'Issue token failed',
        description: parseError(error, 'Unable to issue enrollment token'),
        tone: 'error',
      });
    } finally {
      setIssueBusy(false);
    }
  };

  const openImportModal = () => {
    setImportJson('');
    setImportOpen(true);
  };

  const importKit = async () => {
    let bundle: Record<string, unknown>;
    try {
      const parsed = JSON.parse(importJson.trim());
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        pushToast({ title: 'Bundle JSON must be an object', tone: 'warning' });
        return;
      }
      bundle = parsed as Record<string, unknown>;
    } catch {
      pushToast({ title: 'Bundle JSON is invalid', tone: 'warning' });
      return;
    }

    setImportBusy(true);
    try {
      const response = await CoreApi.importOfflineEnrollmentKit({ bundle });
      setImportOpen(false);
      await loadTokens();
      pushToast({
        title: 'Offline kit imported',
        description: `Token ${response.data.item.token_id} (created_token=${response.data.created_token ? 'yes' : 'no'}, created_kit=${response.data.created_kit ? 'yes' : 'no'})`,
        tone: 'success',
      });
    } catch (error: any) {
      pushToast({
        title: 'Import failed',
        description: parseError(error, 'Unable to import offline enrollment kit'),
        tone: 'error',
      });
    } finally {
      setImportBusy(false);
    }
  };

  const openRevokeModal = (row: EnrollmentToken) => {
    setRevokeTarget(row);
    setRevokeReason('');
    setRevokeOpen(true);
  };

  const revokeToken = async () => {
    if (!revokeTarget) return;
    if (revokeReason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setRevokeBusy(true);
    try {
      await CoreApi.revokeEnrollmentToken(revokeTarget.token_id, { reason: revokeReason.trim() });
      setRevokeOpen(false);
      setRevokeTarget(null);
      await loadTokens();
      pushToast({
        title: 'Enrollment token revoked',
        description: `Token ${revokeTarget.token_id} moved to REVOKED`,
        tone: 'success',
      });
    } catch (error: any) {
      pushToast({
        title: 'Revoke failed',
        description: parseError(error, 'Unable to revoke token'),
        tone: 'error',
      });
    } finally {
      setRevokeBusy(false);
    }
  };

  const copyText = async (value: string, label: string) => {
    try {
      if (!navigator.clipboard) {
        pushToast({ title: `${label} copy unavailable`, description: 'Clipboard API not available.', tone: 'warning' });
        return;
      }
      await navigator.clipboard.writeText(value);
      pushToast({ title: `${label} copied`, tone: 'success' });
    } catch {
      pushToast({ title: `${label} copy failed`, tone: 'error' });
    }
  };

  const downloadBundle = (bundle: Record<string, unknown>, tokenId: string) => {
    const content = JSON.stringify(bundle, null, 2);
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `offline-enrollment-kit-${tokenId}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const columns: DataTableColumn<EnrollmentToken>[] = [
    {
      key: 'token_id',
      header: 'Token',
      render: (row) => (
        <div className="flex max-w-[220px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.token_id}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.reason_code}</span>
        </div>
      ),
    },
    {
      key: 'mode',
      header: 'Mode',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${modeBadgeClass(row.mode)}`}>{row.mode}</span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>
          {row.status}
        </span>
      ),
    },
    {
      key: 'remaining_uses',
      header: 'Uses',
      render: (row) => (
        <span className="text-sm text-slate-700 dark:text-slate-200">
          {row.used_count}/{row.max_uses} used ({row.remaining_uses} left)
        </span>
      ),
    },
    { key: 'expires_at', header: 'Expires', render: (row) => formatDate(row.expires_at) },
    {
      key: 'created_by_username',
      header: 'Created By',
      render: (row) => row.created_by_username || `User #${row.created_by_user_id}`,
    },
    { key: 'last_used_at', header: 'Last Used', render: (row) => formatDate(row.last_used_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) =>
        row.status === 'ACTIVE' ? (
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openRevokeModal(row)}>
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
        title="Enrollment Control"
        subtitle="Issue, import, revoke, and monitor token-based enrollment workflows for online and air-gapped fleet onboarding."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadTokens()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-secondary" onClick={openImportModal}>
              <FiUpload className="mr-2 text-sm" />
              Import Kit
            </button>
            <button type="button" className="btn-primary" onClick={openIssueModal}>
              <FiPlus className="mr-2 text-sm" />
              Generate Token
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_180px_180px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search token id or reason"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={modeFilter}
            onChange={(event) => setModeFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Modes</option>
            <option value="ONLINE">ONLINE</option>
            <option value="OFFLINE">OFFLINE</option>
          </select>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="REVOKED">REVOKED</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="CONSUMED">CONSUMED</option>
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadTokens()}>
            Apply
          </button>
        </div>
      </Card>

      <Card
        title="Enrollment Token Inventory"
        subtitle="One-time secret visibility, lifecycle status, and consumption telemetry for fleet onboarding."
      >
        {status === 'loading' && (
          <LoadingState title="Loading enrollment tokens" description="Fetching token inventory and lifecycle states." />
        )}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadTokens()} />}
        {status === 'ready' && rows.length > 0 && <DataTable columns={columns} rows={rows} rowKey={(row) => row.token_id} />}
        {status === 'ready' && rows.length === 0 && (
          <EmptyState
            title="No enrollment tokens"
            description="Issue your first enrollment token to bootstrap agents."
            actionLabel="Generate Token"
            onAction={openIssueModal}
          />
        )}
      </Card>

      <Modal
        open={issueOpen}
        title="Generate Enrollment Token"
        description="Issue a token with expiry, usage limit, reason code, and optional metadata for audit context."
        confirmLabel={issueBusy ? 'Issuing...' : 'Issue Token'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (issueBusy) return;
          setIssueOpen(false);
        }}
        onConfirm={() => void issueToken()}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={issueForm.mode}
              onChange={(event) => setIssueForm((prev) => ({ ...prev, mode: event.target.value as EnrollmentMode }))}
            >
              <option value="ONLINE">ONLINE</option>
              <option value="OFFLINE">OFFLINE</option>
            </select>
            <select
              className="input"
              value={issueForm.reasonCode}
              onChange={(event) =>
                setIssueForm((prev) => ({ ...prev, reasonCode: event.target.value as EnrollmentReasonCode }))
              }
            >
              {reasonOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              type="number"
              min={1}
              max={720}
              className="input"
              value={issueForm.expiresInHours}
              onChange={(event) =>
                setIssueForm((prev) => ({
                  ...prev,
                  expiresInHours: Math.max(1, Math.min(720, Number(event.target.value) || 1)),
                }))
              }
              placeholder="Expires in hours"
            />
            <input
              type="number"
              min={1}
              max={1000}
              className="input"
              value={issueForm.maxUses}
              onChange={(event) =>
                setIssueForm((prev) => ({
                  ...prev,
                  maxUses: Math.max(1, Math.min(1000, Number(event.target.value) || 1)),
                }))
              }
              placeholder="Max uses"
            />
          </div>

          <textarea
            className="input min-h-[84px] resize-y"
            value={issueForm.reason}
            onChange={(event) => setIssueForm((prev) => ({ ...prev, reason: event.target.value }))}
            placeholder="Reason (min 5 chars)"
          />

          <input
            className="input"
            value={issueForm.idempotencyKey}
            onChange={(event) => setIssueForm((prev) => ({ ...prev, idempotencyKey: event.target.value }))}
            placeholder="Idempotency key"
          />

          <textarea
            className="input min-h-[92px] resize-y font-mono text-xs"
            value={issueForm.metadataJson}
            onChange={(event) => setIssueForm((prev) => ({ ...prev, metadataJson: event.target.value }))}
            placeholder='Metadata JSON (example: {"source":"admin-console"})'
          />

          {issueForm.mode === 'OFFLINE' && (
            <p className="rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-700 dark:border-indigo-900/60 dark:bg-indigo-950/30 dark:text-indigo-300">
              Offline mode also generates an exportable offline enrollment kit bundle.
            </p>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(resultOpen && issueResult)}
        title="Enrollment Token Issued"
        description="Copy secrets now. For security, token value is shown only once."
        cancelLabel="Close"
        onCancel={() => {
          setResultOpen(false);
          setIssueResult(null);
        }}
      >
        {issueResult && (
          <div className="space-y-3">
            {issueResult.enrollmentToken && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Enrollment Token</p>
                  <button
                    type="button"
                    className="btn-secondary h-8 px-2 text-xs"
                    onClick={() => void copyText(issueResult.enrollmentToken || '', 'Token')}
                  >
                    <FiCopy className="mr-1 text-xs" />
                    Copy
                  </button>
                </div>
                <p className="break-all rounded-lg border border-slate-200 bg-white px-2 py-1.5 font-mono text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200">
                  {issueResult.enrollmentToken}
                </p>
              </div>
            )}

            {issueResult.cliSnippets?.powershell && (
              <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">PowerShell CLI</p>
                  <button
                    type="button"
                    className="btn-secondary h-8 px-2 text-xs"
                    onClick={() => void copyText(issueResult.cliSnippets?.powershell || '', 'PowerShell snippet')}
                  >
                    <FiCopy className="mr-1 text-xs" />
                    Copy
                  </button>
                </div>
                <textarea
                  readOnly
                  value={issueResult.cliSnippets.powershell}
                  className="input min-h-[96px] resize-y font-mono text-xs"
                />
              </div>
            )}

            {issueResult.cliSnippets?.linux && (
              <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Linux CLI</p>
                  <button
                    type="button"
                    className="btn-secondary h-8 px-2 text-xs"
                    onClick={() => void copyText(issueResult.cliSnippets?.linux || '', 'Linux snippet')}
                  >
                    <FiCopy className="mr-1 text-xs" />
                    Copy
                  </button>
                </div>
                <textarea
                  readOnly
                  value={issueResult.cliSnippets.linux}
                  className="input min-h-[96px] resize-y font-mono text-xs"
                />
              </div>
            )}

            {issueResult.offlineKitBundle && (
              <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">Offline Enrollment Kit</p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-secondary h-8 px-2 text-xs"
                      onClick={() => void copyText(JSON.stringify(issueResult.offlineKitBundle, null, 2), 'Offline kit JSON')}
                    >
                      <FiCopy className="mr-1 text-xs" />
                      Copy JSON
                    </button>
                    <button
                      type="button"
                      className="btn-secondary h-8 px-2 text-xs"
                      onClick={() => downloadBundle(issueResult.offlineKitBundle || {}, issueResult.item.token_id)}
                    >
                      <FiDownload className="mr-1 text-xs" />
                      Download
                    </button>
                  </div>
                </div>
                <textarea
                  readOnly
                  value={JSON.stringify(issueResult.offlineKitBundle, null, 2)}
                  className="input min-h-[128px] resize-y font-mono text-xs"
                />
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal
        open={importOpen}
        title="Import Offline Enrollment Kit"
        description="Paste exported offline kit JSON to register token and kit metadata."
        confirmLabel={importBusy ? 'Importing...' : 'Import Kit'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (importBusy) return;
          setImportOpen(false);
        }}
        onConfirm={() => void importKit()}
      >
        <div className="space-y-3">
          <textarea
            className="input min-h-[220px] resize-y font-mono text-xs"
            value={importJson}
            onChange={(event) => setImportJson(event.target.value)}
            placeholder='Paste bundle JSON here (contains "kit_id" and "token").'
          />
          <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
            Import is idempotent per kit_id + bundle hash. Conflicts are rejected for safety.
          </p>
        </div>
      </Modal>

      <Modal
        open={revokeOpen}
        title={revokeTarget ? `Revoke ${revokeTarget.token_id}` : 'Revoke Token'}
        description="Revocation is immediate and prevents future enrollments."
        confirmLabel={revokeBusy ? 'Revoking...' : 'Revoke Token'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (revokeBusy) return;
          setRevokeOpen(false);
          setRevokeTarget(null);
        }}
        onConfirm={() => void revokeToken()}
      >
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900">
            <p className="text-slate-600 dark:text-slate-300">
              {revokeTarget ? `Mode: ${revokeTarget.mode} | Uses: ${revokeTarget.used_count}/${revokeTarget.max_uses}` : ''}
            </p>
          </div>
          <textarea
            className="input min-h-[84px] resize-y"
            value={revokeReason}
            onChange={(event) => setRevokeReason(event.target.value)}
            placeholder="Revocation reason (min 5 chars)"
          />
        </div>
      </Modal>

      <Card>
        <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiShield className="mr-2 inline text-sm" />
            Enrollment hardening defaults
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Token values are returned once, secrets are hashed at rest, and every lifecycle action is audit logged.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Use low max_uses and short expiries for bootstrap, and prefer OFFLINE mode only for constrained networks.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            <FiKey className="mr-1 inline text-xs" />
            Endpoint enroll API: <code>/api/v1/agents/enroll</code>
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
