import { useEffect, useMemo, useState } from 'react';
import { FiActivity, FiEye, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { useToastStack } from '../../hooks/useToastStack';
import { createIdempotencyKey } from '../../utils/idempotency';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack } from '../../components/ui/Toast';
import type { Agent, AgentSelfStatusResponse, FleetDriftItem } from '../../types';

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

const formatDateTime = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const formatText = (value?: string | null) => (value && value.trim() ? value : '-');

const toPrettyJson = (value: Record<string, unknown>) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '{}';
  }
};

const baseColumns: DataTableColumn<HealthRow>[] = [
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
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
  const [selfStatus, setSelfStatus] = useState<AgentSelfStatusResponse | null>(null);
  const [selfStatusView, setSelfStatusView] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [selfStatusError, setSelfStatusError] = useState('');
  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 4000 });

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
      if (selectedAgentId && !nextRows.some((row) => row.agent_id === selectedAgentId)) {
        setSelectedAgentId(null);
        setSelfStatus(null);
        setSelfStatusView('idle');
        setSelfStatusError('');
      }
      setStatus('ready');
    } catch (error: unknown) {
      setRows([]);
      setStatus('error');
      setErrorMessage(getApiErrorMessage(error, 'Unable to load fleet health data'));
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

  const loadSelfStatus = async (agentId: number) => {
    setSelectedAgentId(agentId);
    setSelfStatusView('loading');
    setSelfStatusError('');
    try {
      const response = await CoreApi.getAgentSelfStatus(agentId);
      setSelfStatus(response.data);
      setSelfStatusView('ready');
    } catch (error: unknown) {
      setSelfStatus(null);
      setSelfStatusView('error');
      setSelfStatusError(getApiErrorMessage(error, 'Unable to load agent self-status snapshot'));
    }
  };

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
        idempotency_key: createIdempotencyKey('health-sync'),
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
    } catch (error: unknown) {
      pushToast({ title: 'Policy sync failed', description: getApiErrorMessage(error, 'Unable to push policy'), tone: 'error' });
    } finally {
      setSyncBusy(false);
    }
  };

  const onlineCount = rows.filter((row) => row.status === 'ONLINE').length;
  const driftCount = rows.filter((row) => row.drift).length;
  const tableColumns: DataTableColumn<HealthRow>[] = [
    ...baseColumns,
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => {
        const isSelected = selectedAgentId === row.agent_id;
        return (
          <button
            type="button"
            className={`btn-secondary h-8 px-2 text-xs ${isSelected ? '!border-cyan-500 !text-cyan-700 dark:!text-cyan-300' : ''}`}
            onClick={() => void loadSelfStatus(row.agent_id)}
          >
            <FiEye className="mr-1 text-xs" />
            {isSelected ? 'Reload' : 'Inspect'}
          </button>
        );
      },
    },
  ];

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
        {status === 'ready' && filteredRows.length > 0 && <DataTable columns={tableColumns} rows={filteredRows} rowKey={(row) => String(row.agent_id)} />}
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

      <Card title="Fleet Drill-down" subtitle="AGR self-status snapshot with runtime isolation and pending command queue.">
        {selfStatusView === 'idle' && (
          <EmptyState
            title="Select agent to inspect"
            description="Fleet Health Matrix mein kisi bhi row ka Inspect button click karo to live self-status snapshot yahan render hoga."
          />
        )}
        {selfStatusView === 'loading' && (
          <LoadingState
            title="Loading self-status snapshot"
            description={selectedAgentId ? `Fetching data for agent #${selectedAgentId}.` : 'Fetching agent self-status snapshot.'}
          />
        )}
        {selfStatusView === 'error' && (
          <ErrorState
            description={selfStatusError}
            onRetry={selectedAgentId ? () => void loadSelfStatus(selectedAgentId) : undefined}
          />
        )}
        {selfStatusView === 'ready' && selfStatus && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Agent #{selfStatus.agent.id}: {selfStatus.agent.hostname}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {selfStatus.agent.name} | Server snapshot: {formatDateTime(selfStatus.server_time_utc)}
                </p>
              </div>
              <button type="button" className="btn-secondary h-9 px-3 text-xs" onClick={() => void loadSelfStatus(selfStatus.agent.id)}>
                <FiRefreshCw className="mr-1 text-xs" />
                Refresh Snapshot
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-700 xl:col-span-2">
                <p className="font-semibold text-slate-900 dark:text-slate-100">Agent State</p>
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <p className="text-slate-600 dark:text-slate-300">Status: {formatText(selfStatus.agent.status)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Revoked: {selfStatus.agent.agent_revoked ? 'Yes' : 'No'}</p>
                  <p className="text-slate-600 dark:text-slate-300">Last Seen: {formatDateTime(selfStatus.agent.last_seen)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Registered: {formatDateTime(selfStatus.agent.registered_at)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Mode Override: {formatText(selfStatus.agent.device_mode_override)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Device Tags: {formatText(selfStatus.agent.device_tags)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Revoked At: {formatDateTime(selfStatus.agent.revoked_at)}</p>
                  <p className="text-slate-600 dark:text-slate-300">Revocation Reason: {formatText(selfStatus.agent.revocation_reason)}</p>
                </div>
              </div>
              <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-700">
                <p className="font-semibold text-slate-900 dark:text-slate-100">Command Queue</p>
                <div className="mt-2 space-y-1 text-slate-600 dark:text-slate-300">
                  <p>Pending: {selfStatus.command_counts.pending}</p>
                  <p>Applied: {selfStatus.command_counts.applied}</p>
                  <p>Failed: {selfStatus.command_counts.failed}</p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-700">
              <p className="font-semibold text-slate-900 dark:text-slate-100">Runtime and Device Status</p>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                <p className="text-slate-600 dark:text-slate-300">Runtime ID: {formatText(selfStatus.device_status?.runtime_id)}</p>
                <p className="text-slate-600 dark:text-slate-300">Agent Version: {formatText(selfStatus.device_status?.agent_version)}</p>
                <p className="text-slate-600 dark:text-slate-300">Adapter Status: {formatText(selfStatus.device_status?.adapter_status)}</p>
                <p className="text-slate-600 dark:text-slate-300">Enforcement Mode: {formatText(selfStatus.device_status?.enforcement_mode)}</p>
                <p className="text-slate-600 dark:text-slate-300">Policy Hash Applied: {formatText(selfStatus.device_status?.policy_hash_applied)}</p>
                <p className="text-slate-600 dark:text-slate-300">Last Reconcile: {formatDateTime(selfStatus.device_status?.last_reconcile_time)}</p>
                <p className="break-all text-slate-600 dark:text-slate-300 sm:col-span-2 xl:col-span-3">
                  State Root: {formatText(selfStatus.device_status?.state_root)}
                </p>
                <p className="text-slate-600 dark:text-slate-300">Updated: {formatDateTime(selfStatus.device_status?.updated_at)}</p>
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 p-3 text-xs dark:border-slate-700">
              <p className="font-semibold text-slate-900 dark:text-slate-100">Pending Commands Preview ({selfStatus.pending_commands.length})</p>
              {selfStatus.pending_commands.length === 0 && (
                <p className="mt-2 text-slate-500 dark:text-slate-400">No pending commands for this agent.</p>
              )}
              {selfStatus.pending_commands.length > 0 && (
                <div className="mt-2 space-y-2">
                  {selfStatus.pending_commands.map((command) => (
                    <div key={command.id} className="rounded-lg border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-900">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="font-semibold text-slate-700 dark:text-slate-200">
                          #{command.id} | {command.type}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">{formatDateTime(command.created_at)}</p>
                      </div>
                      <pre className="mt-2 overflow-x-auto rounded-md bg-slate-100 p-2 text-[11px] text-slate-700 dark:bg-slate-950 dark:text-slate-200">
                        {toPrettyJson(command.payload)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
