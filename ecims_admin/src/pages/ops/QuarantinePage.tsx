import { useEffect, useMemo, useState } from 'react';
import { FiCheckSquare, FiRefreshCw, FiSearch, FiShieldOff, FiSquare, FiUnlock } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { useToastStack } from '../../hooks/useToastStack';
import { createIdempotencyKey, validateIdempotencyKey } from '../../utils/idempotency';
import { toOptionalFilter, toOptionalQuery } from '../../utils/listQuery';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack } from '../../components/ui/Toast';
import type { Agent, RemoteActionTask } from '../../types';

const statusBadgeClass = (value: string) => {
  if (value === 'DONE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'FAILED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (value === 'ACK') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (value === 'SENT') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const quarantineState = (status: string) => {
  if (status === 'DONE') return 'Isolated';
  if (status === 'FAILED') return 'Failed';
  return 'Isolation In Progress';
};

export const QuarantinePage = () => {
  const [tasks, setTasks] = useState<RemoteActionTask[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const [isolateOpen, setIsolateOpen] = useState(false);
  const [isolateBusy, setIsolateBusy] = useState(false);
  const [isolateReason, setIsolateReason] = useState('');
  const [isolateIdempotencyKey, setIsolateIdempotencyKey] = useState(createIdempotencyKey('iso'));
  const [isolateSearch, setIsolateSearch] = useState('');
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);

  const [releaseOpen, setReleaseOpen] = useState(false);
  const [releaseBusy, setReleaseBusy] = useState(false);
  const [releaseReason, setReleaseReason] = useState('');
  const [releaseIdempotencyKey, setReleaseIdempotencyKey] = useState(createIdempotencyKey('rel'));
  const [releaseTask, setReleaseTask] = useState<RemoteActionTask | null>(null);
  const [releaseAgentIds, setReleaseAgentIds] = useState<number[]>([]);

  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 4000 });

  const loadPage = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const [tasksResponse, agentsResponse] = await Promise.all([
        CoreApi.listRemoteActionTasks({
          page: 1,
          page_size: 100,
          action: 'lockdown',
          status: toOptionalFilter(statusFilter),
          q: toOptionalQuery(query),
        }),
        CoreApi.agents(),
      ]);
      setTasks(tasksResponse.data.items ?? []);
      setAgents(agentsResponse.data ?? []);
      setStatus('ready');
    } catch (error: unknown) {
      setTasks([]);
      setStatus('error');
      setErrorMessage(getApiErrorMessage(error, 'Unable to load quarantine workflow data'));
    }
  };

  useEffect(() => {
    void loadPage();
  }, []);

  const filteredTasks = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return tasks.filter((task) => {
      if (statusFilter !== 'all' && task.status !== statusFilter) return false;
      if (!normalized) return true;
      const haystack =
        `${task.id} ${task.idempotency_key} ${task.reason} ${task.reason_code} ${task.requested_by_username || ''} ${task.status}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [tasks, query, statusFilter]);

  const visibleAgents = useMemo(() => {
    const normalized = isolateSearch.trim().toLowerCase();
    if (!normalized) return agents;
    return agents.filter((agent) => `${agent.id} ${agent.name} ${agent.hostname} ${agent.status}`.toLowerCase().includes(normalized));
  }, [agents, isolateSearch]);

  const toggleAgent = (agentId: number) => {
    setSelectedAgentIds((prev) => (prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]));
  };

  const selectAllOnlineAgents = () => {
    setSelectedAgentIds(agents.filter((agent) => agent.status === 'ONLINE').map((agent) => agent.id));
  };

  const submitIsolation = async () => {
    if (!selectedAgentIds.length) {
      pushToast({ title: 'Select at least one agent', tone: 'warning' });
      return;
    }
    if (isolateReason.trim().length < 5) {
      pushToast({ title: 'Isolation reason must be at least 5 characters', tone: 'warning' });
      return;
    }
    const isolationIdempotencyError = validateIdempotencyKey(isolateIdempotencyKey, { minLength: 8 });
    if (isolationIdempotencyError) {
      pushToast({ title: isolationIdempotencyError, tone: 'warning' });
      return;
    }
    setIsolateBusy(true);
    try {
      const response = await CoreApi.createRemoteActionTask({
        action: 'lockdown',
        agent_ids: selectedAgentIds,
        idempotency_key: isolateIdempotencyKey.trim(),
        reason_code: 'INCIDENT_RESPONSE',
        reason: isolateReason.trim(),
        confirm_high_risk: true,
        metadata: { source: 'ops/quarantine', workflow: 'start-isolation' },
      });
      setIsolateOpen(false);
      setIsolateReason('');
      setIsolateIdempotencyKey(createIdempotencyKey('iso'));
      setSelectedAgentIds([]);
      pushToast({
        title: response.data.created ? 'Isolation task created' : 'Idempotent replay returned existing isolation task',
        description: `Task #${response.data.item.id} for ${response.data.item.target_count} agents.`,
        tone: response.data.created ? 'success' : 'info',
      });
      await loadPage();
    } catch (error: unknown) {
      pushToast({ title: 'Isolation failed', description: getApiErrorMessage(error, 'Unable to create isolation task'), tone: 'error' });
    } finally {
      setIsolateBusy(false);
    }
  };

  const openRelease = async (task: RemoteActionTask) => {
    setReleaseTask(task);
    setReleaseReason('');
    setReleaseIdempotencyKey(createIdempotencyKey('rel'));
    setReleaseOpen(true);
    setReleaseBusy(true);
    try {
      const response = await CoreApi.getRemoteActionTaskTargets(task.id);
      const targetIds = (response.data.items ?? []).map((item) => item.agent_id);
      setReleaseAgentIds(Array.from(new Set(targetIds)));
    } catch (error: unknown) {
      setReleaseOpen(false);
      setReleaseTask(null);
      setReleaseAgentIds([]);
      pushToast({ title: 'Unable to load task targets', description: getApiErrorMessage(error, 'Release pre-check failed'), tone: 'error' });
    } finally {
      setReleaseBusy(false);
    }
  };

  const submitRelease = async () => {
    if (!releaseTask) return;
    if (!releaseAgentIds.length) {
      pushToast({ title: 'No releasable agents found on this task', tone: 'warning' });
      return;
    }
    if (releaseReason.trim().length < 5) {
      pushToast({ title: 'Release reason must be at least 5 characters', tone: 'warning' });
      return;
    }
    const releaseIdempotencyError = validateIdempotencyKey(releaseIdempotencyKey, { minLength: 8 });
    if (releaseIdempotencyError) {
      pushToast({ title: releaseIdempotencyError, tone: 'warning' });
      return;
    }
    setReleaseBusy(true);
    try {
      const response = await CoreApi.createRemoteActionTask({
        action: 'policy_push',
        agent_ids: releaseAgentIds,
        idempotency_key: releaseIdempotencyKey.trim(),
        reason_code: 'ROLLBACK',
        reason: releaseReason.trim(),
        confirm_high_risk: false,
        metadata: {
          source: 'ops/quarantine',
          workflow: 'release-isolation',
          release_from_task_id: releaseTask.id,
        },
      });
      setReleaseOpen(false);
      setReleaseTask(null);
      setReleaseAgentIds([]);
      pushToast({
        title: response.data.created ? 'Release workflow queued' : 'Release reused existing idempotent task',
        description: `Task #${response.data.item.id} for ${response.data.item.target_count} agents.`,
        tone: response.data.created ? 'success' : 'info',
      });
      await loadPage();
    } catch (error: unknown) {
      pushToast({ title: 'Release workflow failed', description: getApiErrorMessage(error, 'Unable to create release task'), tone: 'error' });
    } finally {
      setReleaseBusy(false);
    }
  };

  const columns: DataTableColumn<RemoteActionTask>[] = [
    {
      key: 'case',
      header: 'Case',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-semibold text-slate-900 dark:text-slate-100">Q-{row.id}</span>
          <span className="text-xs text-slate-500 dark:text-slate-400">{new Date(row.created_at).toLocaleString()}</span>
        </div>
      ),
    },
    {
      key: 'state',
      header: 'State',
      render: (row) => <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{quarantineState(row.status)}</span>,
    },
    {
      key: 'targets',
      header: 'Targets',
      render: (row) => `${row.target_count} hosts`,
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (row) => <span className="max-w-[300px] truncate">{row.reason}</span>,
    },
    {
      key: 'requested_by',
      header: 'Requested By',
      render: (row) => row.requested_by_username || `User #${row.requested_by_user_id}`,
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void openRelease(row)}>
          <FiUnlock className="mr-1 text-xs" />
          Start Release
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Quarantine"
        subtitle="Reversible host isolation workflow backed by lockdown and rollback remote action tasks."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadPage()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                setIsolateReason('');
                setIsolateIdempotencyKey(createIdempotencyKey('iso'));
                setSelectedAgentIds([]);
                setIsolateSearch('');
                setIsolateOpen(true);
              }}
            >
              <FiShieldOff className="mr-2 text-sm" />
              Start Isolation
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_220px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search case id, reason, requester"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="PENDING">PENDING</option>
            <option value="SENT">SENT</option>
            <option value="ACK">ACK</option>
            <option value="DONE">DONE</option>
            <option value="FAILED">FAILED</option>
          </select>
          <button type="button" className="btn-secondary h-11" onClick={() => void loadPage()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Quarantine Cases" subtitle="Cases are backed by lockdown tasks and can be released with policy rollback.">
        {status === 'loading' && <LoadingState title="Loading quarantine cases" description="Fetching lockdown task history." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadPage()} />}
        {status === 'ready' && filteredTasks.length > 0 && <DataTable columns={columns} rows={filteredTasks} rowKey={(row) => String(row.id)} />}
        {status === 'ready' && filteredTasks.length === 0 && (
          <EmptyState
            title="No quarantine cases"
            description="No lockdown tasks matched current filters."
            actionLabel="Start Isolation"
            onAction={() => setIsolateOpen(true)}
          />
        )}
      </Card>

      <Modal
        open={isolateOpen}
        title="Start Isolation Workflow"
        description="Create lockdown task for selected hosts."
        confirmLabel={isolateBusy ? 'Queuing...' : 'Queue Isolation'}
        cancelLabel="Cancel"
        confirmDisabled={isolateBusy}
        cancelDisabled={isolateBusy}
        onCancel={() => {
          if (isolateBusy) return;
          setIsolateOpen(false);
        }}
        onConfirm={() => void submitIsolation()}
      >
        <div className="space-y-3">
          <textarea
            className="input min-h-[80px] resize-y"
            value={isolateReason}
            disabled={isolateBusy}
            onChange={(event) => setIsolateReason(event.target.value)}
            placeholder="Isolation reason (min 5 chars)"
          />
          <input
            className="input"
            value={isolateIdempotencyKey}
            disabled={isolateBusy}
            onChange={(event) => setIsolateIdempotencyKey(event.target.value)}
            placeholder="Idempotency key"
          />

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-900">
            <div className="mb-2 flex items-center gap-2">
              <input
                value={isolateSearch}
                disabled={isolateBusy}
                onChange={(event) => setIsolateSearch(event.target.value)}
                className="input h-9"
                placeholder="Search agent id, name, hostname"
              />
              <button type="button" className="btn-secondary h-9 px-2 text-xs disabled:opacity-60" disabled={isolateBusy} onClick={selectAllOnlineAgents}>
                <FiCheckSquare className="mr-1 text-xs" />
                Select Online
              </button>
            </div>

            <div className="max-h-44 space-y-1 overflow-y-auto">
              {visibleAgents.map((agent) => {
                const selected = selectedAgentIds.includes(agent.id);
                return (
                  <button
                    key={agent.id}
                    type="button"
                    className={`flex w-full items-center justify-between rounded-lg border px-2 py-1.5 text-left text-xs transition ${
                      selected
                        ? 'border-cyan-500 bg-cyan-50 text-cyan-700 dark:border-cyan-400 dark:bg-cyan-950/30 dark:text-cyan-300'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
                    }`}
                    disabled={isolateBusy}
                    onClick={() => toggleAgent(agent.id)}
                  >
                    <span className="truncate">
                      #{agent.id} {agent.name} ({agent.hostname})
                    </span>
                    {selected ? <FiCheckSquare className="text-sm" /> : <FiSquare className="text-sm" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        open={releaseOpen}
        title={releaseTask ? `Release Workflow for Q-${releaseTask.id}` : 'Release Workflow'}
        description="Create policy rollback task to reverse isolation."
        confirmLabel={releaseBusy ? 'Queuing...' : 'Queue Release'}
        cancelLabel="Cancel"
        confirmDisabled={releaseBusy}
        cancelDisabled={releaseBusy}
        onCancel={() => {
          if (releaseBusy) return;
          setReleaseOpen(false);
          setReleaseTask(null);
          setReleaseAgentIds([]);
        }}
        onConfirm={() => void submitRelease()}
      >
        <div className="space-y-3">
          <textarea
            className="input min-h-[80px] resize-y"
            value={releaseReason}
            disabled={releaseBusy}
            onChange={(event) => setReleaseReason(event.target.value)}
            placeholder="Release reason (min 5 chars)"
          />
          <input
            className="input"
            value={releaseIdempotencyKey}
            disabled={releaseBusy}
            onChange={(event) => setReleaseIdempotencyKey(event.target.value)}
            placeholder="Idempotency key"
          />
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-900">
            <p>Release targets: {releaseAgentIds.length}</p>
            <p>Reason code: ROLLBACK</p>
            {releaseTask && <p>Source isolation task: #{releaseTask.id}</p>}
          </div>
        </div>
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
