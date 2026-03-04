import { useEffect, useMemo, useState } from 'react';
import {
  FiCheckSquare,
  FiClock,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiSquare,
  FiUsers,
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
import type {
  Agent,
  RemoteActionKind,
  RemoteActionTask,
  RemoteActionTaskCreatePayload,
  RemoteActionTaskTarget,
} from '../../types';

type ReasonCode =
  | 'MAINTENANCE'
  | 'POLICY_SYNC'
  | 'INCIDENT_RESPONSE'
  | 'ROLLBACK'
  | 'EMERGENCY_MITIGATION'
  | 'TESTING';

const reasonOptions: Array<{ value: ReasonCode; label: string }> = [
  { value: 'MAINTENANCE', label: 'Maintenance' },
  { value: 'POLICY_SYNC', label: 'Policy Sync' },
  { value: 'INCIDENT_RESPONSE', label: 'Incident Response' },
  { value: 'ROLLBACK', label: 'Rollback' },
  { value: 'EMERGENCY_MITIGATION', label: 'Emergency Mitigation' },
  { value: 'TESTING', label: 'Testing' },
];

const actionOptions: Array<{ value: RemoteActionKind; label: string; isHighRisk: boolean }> = [
  { value: 'restart', label: 'Restart', isHighRisk: false },
  { value: 'policy_push', label: 'Policy Push', isHighRisk: false },
  { value: 'shutdown', label: 'Shutdown', isHighRisk: true },
  { value: 'lockdown', label: 'Lockdown', isHighRisk: true },
];

const makeIdempotencyKey = () => `ra-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const parseError = (error: any, fallback: string) => error?.response?.data?.detail || error?.message || fallback;

const actionLabel = (value: string) => {
  if (value === 'policy_push') return 'Policy Push';
  if (value === 'shutdown') return 'Shutdown';
  if (value === 'restart') return 'Restart';
  if (value === 'lockdown') return 'Lockdown';
  return value;
};

const statusBadgeClass = (value: string) => {
  if (value === 'DONE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'FAILED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  if (value === 'ACK') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (value === 'SENT') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

export const RemoteActionsPage = () => {
  const [tasks, setTasks] = useState<RemoteActionTask[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasksStatus, setTasksStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [tasksError, setTasksError] = useState('');

  const [query, setQuery] = useState('');
  const [actionFilter, setActionFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const [issueOpen, setIssueOpen] = useState(false);
  const [issueBusy, setIssueBusy] = useState(false);
  const [issueAction, setIssueAction] = useState<RemoteActionKind>('restart');
  const [issueReasonCode, setIssueReasonCode] = useState<ReasonCode>('MAINTENANCE');
  const [issueReason, setIssueReason] = useState('');
  const [issueIdempotencyKey, setIssueIdempotencyKey] = useState(makeIdempotencyKey);
  const [issueConfirmHighRisk, setIssueConfirmHighRisk] = useState(false);
  const [agentSearch, setAgentSearch] = useState('');
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);

  const [detailTask, setDetailTask] = useState<RemoteActionTask | null>(null);
  const [detailRows, setDetailRows] = useState<RemoteActionTaskTarget[]>([]);
  const [detailStatus, setDetailStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [detailError, setDetailError] = useState('');

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 3800);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  };

  const loadAgents = async () => {
    try {
      const response = await CoreApi.agents();
      setAgents(response.data ?? []);
    } catch {
      setAgents([]);
    }
  };

  const loadTasks = async () => {
    setTasksStatus('loading');
    setTasksError('');
    try {
      const response = await CoreApi.listRemoteActionTasks({
        page: 1,
        page_size: 100,
        action: actionFilter !== 'all' ? actionFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        q: query.trim() ? query.trim() : undefined,
      });
      setTasks(response.data.items ?? []);
      setTasksStatus('ready');
    } catch (error: any) {
      setTasksError(parseError(error, 'Unable to load remote action tasks'));
      setTasksStatus('error');
    }
  };

  useEffect(() => {
    void Promise.all([loadAgents(), loadTasks()]);
  }, []);

  const resetIssueForm = () => {
    setIssueAction('restart');
    setIssueReasonCode('MAINTENANCE');
    setIssueReason('');
    setIssueIdempotencyKey(makeIdempotencyKey());
    setIssueConfirmHighRisk(false);
    setAgentSearch('');
    setSelectedAgentIds([]);
  };

  const openIssueModal = () => {
    resetIssueForm();
    setIssueOpen(true);
  };

  const filteredAgents = useMemo(() => {
    const normalized = agentSearch.trim().toLowerCase();
    if (!normalized) return agents;
    return agents.filter((agent) => {
      const haystack = `${agent.id} ${agent.name} ${agent.hostname} ${agent.status}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [agents, agentSearch]);

  const selectedAction = actionOptions.find((item) => item.value === issueAction);
  const isHighRiskAction = Boolean(selectedAction?.isHighRisk);

  const toggleAgent = (agentId: number) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId) ? prev.filter((item) => item !== agentId) : [...prev, agentId],
    );
  };

  const selectAllOnlineAgents = () => {
    setSelectedAgentIds(agents.filter((agent) => agent.status === 'ONLINE').map((agent) => agent.id));
  };

  const submitIssueAction = async () => {
    if (!selectedAgentIds.length) {
      pushToast({ title: 'Select at least one agent', tone: 'warning' });
      return;
    }
    if (issueReason.trim().length < 5) {
      pushToast({
        title: 'Reason is required',
        description: 'Provide a reason with at least 5 characters.',
        tone: 'warning',
      });
      return;
    }
    if (isHighRiskAction && !issueConfirmHighRisk) {
      pushToast({
        title: 'High-risk confirmation required',
        description: 'Shutdown/Lockdown requires explicit operator confirmation.',
        tone: 'warning',
      });
      return;
    }

    setIssueBusy(true);
    try {
      const payload: RemoteActionTaskCreatePayload = {
        action: issueAction,
        agent_ids: selectedAgentIds,
        idempotency_key: issueIdempotencyKey.trim(),
        reason_code: issueReasonCode,
        reason: issueReason.trim(),
        confirm_high_risk: issueConfirmHighRisk,
        metadata: {
          source: 'admin-console',
          page: 'ops/remote-actions',
        },
      };
      const response = await CoreApi.createRemoteActionTask(payload);
      setIssueOpen(false);
      await loadTasks();
      pushToast({
        title: response.data.created ? 'Task created' : 'Idempotent replay returned existing task',
        description: `Task #${response.data.item.id} queued for ${response.data.item.target_count} agents.`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: any) {
      pushToast({
        title: 'Issue action failed',
        description: parseError(error, 'Unable to issue remote action'),
        tone: 'error',
      });
    } finally {
      setIssueBusy(false);
    }
  };

  const openTargetDetails = async (task: RemoteActionTask) => {
    setDetailTask(task);
    setDetailStatus('loading');
    setDetailError('');
    try {
      const response = await CoreApi.getRemoteActionTaskTargets(task.id);
      setDetailRows(response.data.items ?? []);
      setDetailStatus('ready');
    } catch (error: any) {
      setDetailRows([]);
      setDetailStatus('error');
      setDetailError(parseError(error, 'Unable to load task target details'));
    }
  };

  const taskColumns: DataTableColumn<RemoteActionTask>[] = [
    {
      key: 'id',
      header: 'Task',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-semibold text-slate-900 dark:text-slate-100">#{row.id}</span>
          <span className="max-w-[240px] truncate text-xs text-slate-500 dark:text-slate-400">
            {row.idempotency_key}
          </span>
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (row) => <span className="text-sm font-medium">{actionLabel(row.action)}</span>,
    },
    {
      key: 'progress',
      header: 'Progress',
      render: (row) => (
        <div className="text-xs text-slate-600 dark:text-slate-300">
          <p>
            Done {row.done_count}/{row.target_count}
          </p>
          <p>Failed {row.failed_count}</p>
        </div>
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
      key: 'requested_by_username',
      header: 'Requested By',
      render: (row) => row.requested_by_username || `User #${row.requested_by_user_id}`,
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void openTargetDetails(row)}>
          Targets
        </button>
      ),
    },
  ];

  const targetColumns: DataTableColumn<RemoteActionTaskTarget>[] = [
    { key: 'agent_id', header: 'Agent ID' },
    {
      key: 'agent_name',
      header: 'Agent',
      render: (row) => row.agent_name || row.agent_hostname || '-',
    },
    { key: 'command_id', header: 'Command ID', render: (row) => (row.command_id ? String(row.command_id) : '-') },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>
          {row.status}
        </span>
      ),
    },
    {
      key: 'error',
      header: 'Error',
      render: (row) => (
        <span className="max-w-[280px] truncate text-xs text-rose-600 dark:text-rose-300">{row.error || '-'}</span>
      ),
    },
    { key: 'updated_at', header: 'Updated', render: (row) => new Date(row.updated_at).toLocaleString() },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Remote Actions"
        subtitle="Issue controlled restart, shutdown, lockdown, and policy push tasks with idempotent queue safety."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadTasks()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={openIssueModal}>
              <FiPlus className="mr-2 text-sm" />
              Issue Action
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_180px_180px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search task id, idempotency key, reason"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={actionFilter}
            onChange={(event) => setActionFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Actions</option>
            {actionOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

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

          <button type="button" className="btn-secondary h-11" onClick={() => void loadTasks()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Remote Action Queue" subtitle="Task queue with sent/ack/done/failed lifecycle tracking.">
        {tasksStatus === 'loading' && (
          <LoadingState title="Loading task queue" description="Fetching latest remote action tasks." />
        )}
        {tasksStatus === 'error' && <ErrorState description={tasksError} onRetry={() => void loadTasks()} />}
        {tasksStatus === 'ready' && tasks.length > 0 && (
          <DataTable columns={taskColumns} rows={tasks} rowKey={(row) => String(row.id)} />
        )}
        {tasksStatus === 'ready' && tasks.length === 0 && (
          <EmptyState
            title="No remote action tasks"
            description="Issue a remote action to create the first queue task."
            actionLabel="Issue Action"
            onAction={openIssueModal}
          />
        )}
      </Card>

      <Modal
        open={issueOpen}
        title="Issue Remote Action"
        description="Create an idempotent task for one or many agents with safe batching and audit reason."
        confirmLabel={issueBusy ? 'Issuing...' : 'Issue Task'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (issueBusy) return;
          setIssueOpen(false);
        }}
        onConfirm={() => void submitIssueAction()}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={issueAction}
              onChange={(event) => {
                setIssueAction(event.target.value as RemoteActionKind);
                setIssueConfirmHighRisk(false);
              }}
            >
              {actionOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <select
              className="input"
              value={issueReasonCode}
              onChange={(event) => setIssueReasonCode(event.target.value as ReasonCode)}
            >
              {reasonOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <input
            className="input"
            value={issueIdempotencyKey}
            onChange={(event) => setIssueIdempotencyKey(event.target.value)}
            placeholder="Idempotency key"
          />

          <textarea
            className="input min-h-[84px] resize-y"
            value={issueReason}
            onChange={(event) => setIssueReason(event.target.value)}
            placeholder="Reason (min 5 chars)"
          />

          {isHighRiskAction && (
            <label className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
              <input
                type="checkbox"
                checked={issueConfirmHighRisk}
                onChange={(event) => setIssueConfirmHighRisk(event.target.checked)}
              />
              Confirm high-risk action ({actionLabel(issueAction)})
            </label>
          )}

          <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Target Agents ({selectedAgentIds.length} selected)
              </p>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={selectAllOnlineAgents}>
                  <FiUsers className="mr-1 text-xs" />
                  Select Online
                </button>
                <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => setSelectedAgentIds([])}>
                  Clear
                </button>
              </div>
            </div>

            <label className="mb-2 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
              <FiSearch className="text-slate-400" />
              <input
                value={agentSearch}
                onChange={(event) => setAgentSearch(event.target.value)}
                placeholder="Search agent id, name, hostname"
                className="w-full bg-transparent text-sm text-slate-700 outline-none dark:text-slate-200"
              />
            </label>

            <div className="max-h-52 space-y-1 overflow-y-auto pr-1">
              {filteredAgents.map((agent) => {
                const selected = selectedAgentIds.includes(agent.id);
                return (
                  <button
                    type="button"
                    key={agent.id}
                    onClick={() => toggleAgent(agent.id)}
                    className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm transition ${
                      selected
                        ? 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span className="truncate">
                      #{agent.id} · {agent.name} ({agent.hostname})
                    </span>
                    <span className="ml-2 shrink-0">
                      {selected ? <FiCheckSquare className="text-base" /> : <FiSquare className="text-base" />}
                    </span>
                  </button>
                );
              })}
              {!filteredAgents.length && (
                <p className="py-3 text-center text-xs text-slate-500 dark:text-slate-400">No agents found.</p>
              )}
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(detailTask)}
        title={detailTask ? `Task #${detailTask.id} Targets` : 'Task Targets'}
        description={detailTask ? `${actionLabel(detailTask.action)} · ${detailTask.status}` : undefined}
        cancelLabel="Close"
        onCancel={() => {
          setDetailTask(null);
          setDetailRows([]);
          setDetailStatus('idle');
          setDetailError('');
        }}
      >
        {detailTask && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900">
              <p className="text-slate-600 dark:text-slate-300">Targets: {detailTask.target_count}</p>
              <p className="text-slate-600 dark:text-slate-300">Done: {detailTask.done_count}</p>
              <p className="text-slate-600 dark:text-slate-300">Failed: {detailTask.failed_count}</p>
              <p className="text-slate-600 dark:text-slate-300">
                Updated: {new Date(detailTask.updated_at).toLocaleString()}
              </p>
            </div>

            {detailStatus === 'loading' && (
              <div className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
                <FiClock className="mx-auto mb-2 text-base" />
                Loading targets...
              </div>
            )}
            {detailStatus === 'error' && (
              <ErrorState description={detailError} onRetry={() => void openTargetDetails(detailTask)} />
            )}
            {detailStatus === 'ready' && detailRows.length > 0 && (
              <DataTable columns={targetColumns} rows={detailRows} rowKey={(row) => String(row.id)} />
            )}
            {detailStatus === 'ready' && detailRows.length === 0 && (
              <EmptyState
                title="No targets available"
                description="Task targets were not found for this record."
                actionLabel="Close"
                onAction={() => setDetailTask(null)}
              />
            )}
          </div>
        )}
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
