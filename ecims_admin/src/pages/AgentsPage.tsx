import { useEffect, useMemo, useState } from 'react';
import { FiKey, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi';
import { CoreApi } from '../api/services';
import { getApiErrorMessage, normalizeListResponse } from '../api/utils';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { Modal } from '../components/ui/Modal';
import { PageHeader } from '../components/ui/PageHeader';
import { ToastStack } from '../components/ui/Toast';
import { useToastStack } from '../hooks/useToastStack';
import type { Agent, DeviceAllowTokenIssueResponse } from '../types';

const defaultSecureReason = 'Endpoint validated after USB security incident';

export const AgentsPage = () => {
  const [rows, setRows] = useState<Agent[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const [secureTarget, setSecureTarget] = useState<Agent | null>(null);
  const [secureReason, setSecureReason] = useState(defaultSecureReason);
  const [secureDuration, setSecureDuration] = useState(30);
  const [secureSubmitting, setSecureSubmitting] = useState(false);

  const [keyTarget, setKeyTarget] = useState<Agent | null>(null);
  const [keyReason, setKeyReason] = useState(defaultSecureReason);
  const [keyDuration, setKeyDuration] = useState(30);
  const [issuedKey, setIssuedKey] = useState<DeviceAllowTokenIssueResponse | null>(null);
  const [keySubmitting, setKeySubmitting] = useState(false);

  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 4600 });

  const loadAgents = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.agents();
      setRows(normalizeListResponse<Agent>(response.data));
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load agents'));
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadAgents();
  }, []);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesSearch =
        !q ||
        row.hostname.toLowerCase().includes(q) ||
        (row.name || '').toLowerCase().includes(q) ||
        row.status.toLowerCase().includes(q);
      const matchesStatus = statusFilter === 'all' || row.status.toLowerCase() === statusFilter.toLowerCase();
      return matchesSearch && matchesStatus;
    });
  }, [rows, query, statusFilter]);

  const columns: DataTableColumn<Agent>[] = useMemo(
    () => [
      { key: 'id', header: 'ID' },
      { key: 'hostname', header: 'Hostname' },
      {
        key: 'name',
        header: 'Name',
        render: (row) => row.name || '-',
      },
      {
        key: 'device_mode_override',
        header: 'Mode',
        render: (row) => row.device_mode_override || 'default',
      },
      { key: 'last_seen', header: 'Last Seen' },
      {
        key: 'status',
        header: 'Status',
        render: (row) => (
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            {row.status}
          </span>
        ),
      },
      {
        key: 'actions',
        header: 'Actions',
        render: (row) => (
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-secondary h-8 px-2 text-xs"
              onClick={() => {
                setSecureTarget(row);
                setSecureReason(defaultSecureReason);
                setSecureDuration(30);
              }}
            >
              <FiShield className="mr-1 text-sm" />
              Declare Secure
            </button>
            <button
              type="button"
              className="btn-secondary h-8 px-2 text-xs"
              onClick={() => {
                setKeyTarget(row);
                setKeyReason(defaultSecureReason);
                setKeyDuration(30);
                setIssuedKey(null);
              }}
            >
              <FiKey className="mr-1 text-sm" />
              Generate Key
            </button>
          </div>
        ),
      },
    ],
    [],
  );

  const submitSecureDeclare = async () => {
    if (!secureTarget) return;
    if (secureReason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setSecureSubmitting(true);
    try {
      const response = await CoreApi.secureDeclareDevice({
        agent_id: secureTarget.id,
        reason: secureReason.trim(),
        duration_minutes: secureDuration,
      });
      pushToast({
        title: `Secure declare issued for ${secureTarget.hostname}`,
        description: `Command #${response.data.command_id} queued`,
        tone: 'success',
      });
      setSecureTarget(null);
      await loadAgents();
    } catch (error: unknown) {
      pushToast({
        title: 'Secure declare failed',
        description: getApiErrorMessage(error, 'Unable to declare endpoint secure'),
        tone: 'error',
      });
    } finally {
      setSecureSubmitting(false);
    }
  };

  const submitGenerateKey = async () => {
    if (!keyTarget) return;
    if (keyReason.trim().length < 5) {
      pushToast({ title: 'Reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setKeySubmitting(true);
    try {
      const response = await CoreApi.issueDeviceAllowToken({
        agent_id: keyTarget.id,
        duration_minutes: keyDuration,
        vid: null,
        pid: null,
        serial: null,
        justification: keyReason.trim(),
      });
      setIssuedKey(response.data);
      pushToast({
        title: 'One-time secure key generated',
        description: `Token ${response.data.claims.token_id} ready to copy`,
        tone: 'success',
      });
    } catch (error: unknown) {
      pushToast({
        title: 'Key generation failed',
        description: getApiErrorMessage(error, 'Unable to generate secure key'),
        tone: 'error',
      });
    } finally {
      setKeySubmitting(false);
    }
  };

  const copyIssuedKey = async () => {
    if (!issuedKey?.token) return;
    try {
      await navigator.clipboard.writeText(issuedKey.token);
      pushToast({ title: 'Secure key copied', tone: 'success' });
    } catch {
      pushToast({ title: 'Clipboard unavailable', tone: 'warning' });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        subtitle="Monitor and inspect enrolled endpoint agents across your fleet."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadAgents()}>
            <FiRefreshCw className="mr-2 text-sm" />
            Refresh
          </button>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search hostname, name, status"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 min-w-[180px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="isolated">Isolated</option>
          </select>
        </div>
      </Card>

      <Card title="Agent Inventory" subtitle="Live endpoint agent records from backend API.">
        {status === 'loading' && <LoadingState title="Loading agents" description="Fetching latest agent inventory." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadAgents()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No agents found"
            description="No agent matched your current search/filter. Try clearing filters or enrolling new endpoints."
            actionLabel="Reload"
            onAction={() => void loadAgents()}
          />
        )}
      </Card>

      <Modal
        open={Boolean(secureTarget)}
        title={`Declare Secure: ${secureTarget?.hostname ?? ''}`}
        description="Issue immediate unblock command to endpoint and mark containment review decision."
        confirmLabel={secureSubmitting ? 'Submitting...' : 'Declare Secure'}
        cancelLabel="Cancel"
        confirmDisabled={secureSubmitting}
        cancelDisabled={secureSubmitting}
        onConfirm={() => void submitSecureDeclare()}
        onCancel={() => setSecureTarget(null)}
      >
        <div className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Duration (minutes)
            <input
              type="number"
              min={1}
              max={240}
              value={secureDuration}
              onChange={(event) => setSecureDuration(Math.min(240, Math.max(1, Number(event.target.value) || 1)))}
              className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Reason
            <textarea
              value={secureReason}
              onChange={(event) => setSecureReason(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
            />
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(keyTarget)}
        title={`One-Time Key: ${keyTarget?.hostname ?? ''}`}
        description="Generate a one-time secure key. Enter this key on client GUI to release USB block once."
        confirmLabel={keySubmitting ? 'Generating...' : 'Generate Key'}
        cancelLabel="Close"
        confirmDisabled={keySubmitting}
        cancelDisabled={keySubmitting}
        onConfirm={() => void submitGenerateKey()}
        onCancel={() => {
          setKeyTarget(null);
          setIssuedKey(null);
        }}
      >
        <div className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Duration (minutes)
            <input
              type="number"
              min={1}
              max={240}
              value={keyDuration}
              onChange={(event) => setKeyDuration(Math.min(240, Math.max(1, Number(event.target.value) || 1)))}
              className="mt-1 h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Reason
            <textarea
              value={keyReason}
              onChange={(event) => setKeyReason(event.target.value)}
              rows={3}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
            />
          </label>

          {issuedKey && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-900/60 dark:bg-amber-950/40">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
                One-time secure key
              </p>
              <textarea
                readOnly
                value={issuedKey.token}
                rows={4}
                className="mt-2 w-full rounded-lg border border-amber-300 bg-white px-3 py-2 font-mono text-xs text-slate-800 dark:border-amber-900/60 dark:bg-slate-900 dark:text-slate-100"
              />
              <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
                Token ID: {issuedKey.claims.token_id} | Expires: {issuedKey.claims.expires_at}
              </p>
              <div className="mt-2 flex justify-end">
                <button type="button" className="btn-secondary h-8 px-3 text-xs" onClick={() => void copyIssuedKey()}>
                  Copy Key
                </button>
              </div>
            </div>
          )}
        </div>
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
