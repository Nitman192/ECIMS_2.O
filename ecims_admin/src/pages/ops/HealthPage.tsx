import { useEffect, useMemo, useState } from 'react';
import { FiActivity, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import type { Agent, FleetDriftItem } from '../../types';

type HealthRow = {
  agent_id: number;
  hostname: string;
  name: string;
  status: string;
  last_seen: string;
  policy_hash_applied: string;
  expected_policy_hash: string;
  drift: boolean;
  encryption: 'Enabled' | 'Disabled';
  mtls: 'Healthy' | 'Degraded' | 'Disabled';
  adapter_status: string;
  enforcement_mode: string;
  agent_version: string;
};

type RolloutStatus = {
  kill_switch: boolean;
};

const parseError = (error: any, fallback: string) => error?.response?.data?.detail || error?.message || fallback;
const makeIdempotencyKey = () => `health-sync-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const trimHash = (value: string) => (value.length > 12 ? `${value.slice(0, 12)}...` : value || '-');

const statusBadgeClass = (value: string) => {
  if (value === 'ONLINE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'OFFLINE') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const driftBadgeClass = (value: boolean) =>
  value
    ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
    : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';

const mtlsBadgeClass = (value: HealthRow['mtls']) => {
  if (value === 'Healthy') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'Disabled') return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
  return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
};

const columns: DataTableColumn<HealthRow>[] = [
  {
    key: 'host',
    header: 'Host',
    render: (row) => (
      <div className="flex max-w-[220px] flex-col">
        <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.hostname}</span>
        <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.name}</span>
      </div>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    render: (row) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>,
  },
  {
    key: 'last_seen',
    header: 'Last Seen',
    render: (row) => (row.last_seen ? new Date(row.last_seen).toLocaleString() : '-'),
  },
  {
    key: 'drift',
    header: 'Policy Drift',
    render: (row) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${driftBadgeClass(row.drift)}`}>{row.drift ? 'Drifted' : 'Aligned'}</span>,
  },
  {
    key: 'policy_hash',
    header: 'Policy Hash',
    render: (row) => (
      <div className="text-xs">
        <p>Applied: {trimHash(row.policy_hash_applied)}</p>
        <p>Expected: {trimHash(row.expected_policy_hash)}</p>
      </div>
    ),
  },
  {
    key: 'encryption',
    header: 'Encryption',
  },
  {
    key: 'mtls',
    header: 'mTLS',
    render: (row) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${mtlsBadgeClass(row.mtls)}`}>{row.mtls}</span>,
  },
];

export const HealthPage = () => {
  const [rows, setRows] = useState<HealthRow[]>([]);
  const [rollout, setRollout] = useState<RolloutStatus>({ kill_switch: false });
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [syncBusy, setSyncBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [driftFilter, setDriftFilter] = useState('all');
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 4000);
  };

  const dismissToast = (id: string) => setToasts((prev) => prev.filter((toast) => toast.id !== id));

  const loadHealth = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const [agentsResponse, driftResponse, securityResponse, rolloutResponse] = await Promise.all([
        CoreApi.agents(),
        CoreApi.fleetDrift(),
        CoreApi.securityStatus(),
        CoreApi.deviceRolloutStatus(),
      ]);

      const agents = agentsResponse.data ?? [];
      const driftItems = driftResponse.data.items ?? [];
      const security = securityResponse.data as { data_encryption_enabled?: boolean; mtls_required?: boolean };
      setRollout({ kill_switch: Boolean(rolloutResponse.data.kill_switch) });

      const driftMap = new Map<number, FleetDriftItem>();
      for (const drift of driftItems) {
        driftMap.set(drift.agent_id, drift);
      }

      const nextRows: HealthRow[] = agents.map((agent: Agent) => {
        const drift = driftMap.get(agent.id);
        const mtlsRequired = Boolean(security?.mtls_required);
        const encryptionEnabled = Boolean(security?.data_encryption_enabled);
        const isOnline = agent.status === 'ONLINE';
        return {
          agent_id: agent.id,
          hostname: agent.hostname,
          name: agent.name,
          status: agent.status,
          last_seen: agent.last_seen,
          policy_hash_applied: String(drift?.policy_hash_applied || ''),
          expected_policy_hash: String(drift?.expected_policy_hash || ''),
          drift: Boolean(drift),
          encryption: encryptionEnabled ? 'Enabled' : 'Disabled',
          mtls: mtlsRequired ? (isOnline ? 'Healthy' : 'Degraded') : 'Disabled',
          adapter_status: String(drift?.adapter_status || ''),
          enforcement_mode: String(drift?.enforcement_mode || ''),
          agent_version: String(drift?.agent_version || ''),
        };
      });

      setRows(nextRows);
      setStatus('ready');
    } catch (error: any) {
      setRows([]);
      setStatus('error');
      setErrorMessage(parseError(error, 'Unable to load fleet health data'));
    }
  };

  useEffect(() => {
    void loadHealth();
  }, []);

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return rows.filter((row) => {
      if (statusFilter !== 'all' && row.status.toLowerCase() !== statusFilter) return false;
      if (driftFilter === 'drifted' && !row.drift) return false;
      if (driftFilter === 'aligned' && row.drift) return false;
      if (!normalized) return true;
      const haystack =
        `${row.agent_id} ${row.hostname} ${row.name} ${row.status} ${row.policy_hash_applied} ${row.expected_policy_hash} ${row.enforcement_mode} ${row.adapter_status}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [rows, query, statusFilter, driftFilter]);

  const driftedAgentIds = useMemo(() => rows.filter((item) => item.drift).map((item) => item.agent_id), [rows]);

  const pushPolicyToDrifted = async () => {
    if (!driftedAgentIds.length) {
      pushToast({ title: 'No drifted agents', description: 'All visible agents are currently aligned.', tone: 'info' });
      return;
    }
    setSyncBusy(true);
    try {
      const response = await CoreApi.createRemoteActionTask({
        action: 'policy_push',
        agent_ids: driftedAgentIds,
        idempotency_key: makeIdempotencyKey(),
        reason_code: 'POLICY_SYNC',
        reason: 'Fleet health drift remediation push',
        confirm_high_risk: false,
        metadata: { source: 'ops/health', trigger: 'bulk-policy-sync' },
      });
      pushToast({
        title: response.data.created ? 'Policy sync task created' : 'Policy sync reused existing idempotent task',
        description: `Task #${response.data.item.id} for ${response.data.item.target_count} agents.`,
        tone: response.data.created ? 'success' : 'info',
      });
      await loadHealth();
    } catch (error: any) {
      pushToast({ title: 'Policy sync failed', description: parseError(error, 'Unable to push policy'), tone: 'error' });
    } finally {
      setSyncBusy(false);
    }
  };

  const onlineCount = rows.filter((row) => row.status === 'ONLINE').length;
  const driftCount = rows.filter((row) => row.drift).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fleet Health"
        subtitle="Live endpoint posture, policy drift, encryption, and mTLS alignment from production APIs."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadHealth()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" disabled={syncBusy} onClick={() => void pushPolicyToDrifted()}>
              <FiShield className="mr-2 text-sm" />
              {syncBusy ? 'Queuing...' : 'Push Policy to Drifted'}
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Total Agents</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">{rows.length}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Online</p>
          <p className="mt-2 text-2xl font-semibold text-emerald-600 dark:text-emerald-300">{onlineCount}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Policy Drifted</p>
          <p className="mt-2 text-2xl font-semibold text-amber-600 dark:text-amber-300">{driftCount}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">Kill Switch</p>
          <p className={`mt-2 text-2xl font-semibold ${rollout.kill_switch ? 'text-rose-600 dark:text-rose-300' : 'text-slate-900 dark:text-slate-100'}`}>
            {rollout.kill_switch ? 'Enabled' : 'Disabled'}
          </p>
        </Card>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_190px_190px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search host, policy hash, mode"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="unknown">Unknown</option>
          </select>
          <select
            value={driftFilter}
            onChange={(event) => setDriftFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Drift States</option>
            <option value="drifted">Drifted</option>
            <option value="aligned">Aligned</option>
          </select>
          <button type="button" className="btn-secondary h-11" onClick={() => void loadHealth()}>
            <FiActivity className="mr-2 text-sm" />
            Recompute
          </button>
        </div>
      </Card>

      <Card title="Fleet Health Matrix" subtitle="Agent posture with drift and control-plane remediation path.">
        {status === 'loading' && <LoadingState title="Loading fleet health" description="Collecting posture from agents and drift APIs." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadHealth()} />}
        {status === 'ready' && filteredRows.length > 0 && <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.agent_id)} />}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No health records found"
            description="No agents matched the current search and filter set."
            actionLabel="Clear Filters"
            onAction={() => {
              setQuery('');
              setStatusFilter('all');
              setDriftFilter('all');
            }}
          />
        )}
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
