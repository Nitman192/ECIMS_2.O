import { useEffect, useMemo, useState } from 'react';
import {
  FiCheckSquare,
  FiPlay,
  FiPlus,
  FiRefreshCw,
  FiSearch,
  FiShield,
  FiSquare,
  FiXCircle,
} from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage, normalizeListResponse } from '../../api/utils';
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
import type {
  Agent,
  Playbook,
  PlaybookApprovalMode,
  PlaybookRiskLevel,
  PlaybookRun,
  PlaybookRunDecisionPayload,
  PlaybookStatus,
  PlaybookTriggerType,
  RemoteActionKind,
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

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '-');

const parseJsonObject = (raw: string) => {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('JSON object required');
  }
  return parsed as Record<string, unknown>;
};

const statusBadgeClass = (value: string) => {
  if (value === 'ACTIVE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'DISPATCHED') return 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300';
  if (value === 'PARTIALLY_APPROVED') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  if (value === 'PENDING_APPROVAL') return 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300';
  if (value === 'REJECTED' || value === 'FAILED') return 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

const actionLabel = (value: string) => {
  if (value === 'policy_push') return 'Policy Push';
  if (value === 'shutdown') return 'Shutdown';
  if (value === 'restart') return 'Restart';
  if (value === 'lockdown') return 'Lockdown';
  return value;
};

type CreatePlaybookForm = {
  name: string;
  description: string;
  triggerType: PlaybookTriggerType;
  action: RemoteActionKind;
  approvalMode: PlaybookApprovalMode;
  riskLevel: PlaybookRiskLevel;
  reasonCode: ReasonCode;
  status: PlaybookStatus;
  idempotencyKey: string;
  metadataJson: string;
};

const defaultCreatePlaybookForm: CreatePlaybookForm = {
  name: '',
  description: '',
  triggerType: 'MANUAL',
  action: 'restart',
  approvalMode: 'MANUAL',
  riskLevel: 'LOW',
  reasonCode: 'INCIDENT_RESPONSE',
  status: 'ACTIVE',
  idempotencyKey: createIdempotencyKey('playbook'),
  metadataJson: '{"source":"admin-console"}',
};

export const PlaybooksPage = () => {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [runs, setRuns] = useState<PlaybookRun[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [playbookStatus, setPlaybookStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [runStatus, setRunStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [playbookError, setPlaybookError] = useState('');
  const [runError, setRunError] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [approvalFilter, setApprovalFilter] = useState('all');
  const [runStatusFilter, setRunStatusFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState<CreatePlaybookForm>(defaultCreatePlaybookForm);
  const [agentSearch, setAgentSearch] = useState('');
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);

  const [executeOpen, setExecuteOpen] = useState(false);
  const [executeBusy, setExecuteBusy] = useState(false);
  const [executeReason, setExecuteReason] = useState('');
  const [executeTarget, setExecuteTarget] = useState<Playbook | null>(null);

  const [decisionOpen, setDecisionOpen] = useState(false);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionReason, setDecisionReason] = useState('');
  const [decisionValue, setDecisionValue] = useState<PlaybookRunDecisionPayload['decision']>('APPROVE');
  const [decisionTarget, setDecisionTarget] = useState<PlaybookRun | null>(null);

  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 4200);
  };

  const dismissToast = (id: string) => setToasts((prev) => prev.filter((item) => item.id !== id));

  const loadPlaybooks = async () => {
    setPlaybookStatus('loading');
    setPlaybookError('');
    try {
      const response = await CoreApi.listPlaybooks({
        page: 1,
        page_size: 100,
        status: toOptionalFilter(statusFilter),
        approval_mode: toOptionalFilter(approvalFilter),
        q: toOptionalQuery(query),
      });
      setPlaybooks(response.data.items ?? []);
      setPlaybookStatus('ready');
    } catch (error: unknown) {
      setPlaybooks([]);
      setPlaybookStatus('error');
      setPlaybookError(getApiErrorMessage(error, 'Unable to load playbooks'));
    }
  };

  const loadRuns = async () => {
    setRunStatus('loading');
    setRunError('');
    try {
      const response = await CoreApi.listPlaybookRuns({
        page: 1,
        page_size: 100,
        status: toOptionalFilter(runStatusFilter),
        q: toOptionalQuery(query),
      });
      setRuns(response.data.items ?? []);
      setRunStatus('ready');
    } catch (error: unknown) {
      setRuns([]);
      setRunStatus('error');
      setRunError(getApiErrorMessage(error, 'Unable to load playbook runs'));
    }
  };

  const loadAgents = async () => {
    try {
      const response = await CoreApi.agents();
      setAgents(normalizeListResponse<Agent>(response.data));
    } catch {
      setAgents([]);
    }
  };

  useEffect(() => {
    void Promise.all([loadPlaybooks(), loadRuns(), loadAgents()]);
  }, []);

  const filteredAgents = useMemo(() => {
    const needle = agentSearch.trim().toLowerCase();
    if (!needle) return agents;
    return agents.filter((agent) => {
      const haystack = `${agent.id} ${agent.name} ${agent.hostname} ${agent.status}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [agents, agentSearch]);

  const toggleAgent = (agentId: number) => {
    setSelectedAgentIds((prev) => (prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]));
  };

  const openCreate = () => {
    setCreateForm({ ...defaultCreatePlaybookForm, idempotencyKey: createIdempotencyKey('playbook') });
    setAgentSearch('');
    setSelectedAgentIds([]);
    setCreateOpen(true);
  };

  const createPlaybook = async () => {
    if (createForm.name.trim().length < 3) {
      pushToast({ title: 'Playbook name must be at least 3 characters', tone: 'warning' });
      return;
    }
    if (createForm.description.trim().length < 5) {
      pushToast({ title: 'Description should be at least 5 characters', tone: 'warning' });
      return;
    }
    if (!selectedAgentIds.length) {
      pushToast({ title: 'Select at least one target agent', tone: 'warning' });
      return;
    }
    const key = createForm.idempotencyKey.trim();
    const idempotencyError = validateIdempotencyKey(key, { minLength: 12 });
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
      const response = await CoreApi.createPlaybook({
        name: createForm.name.trim(),
        description: createForm.description.trim(),
        trigger_type: createForm.triggerType,
        action: createForm.action,
        target_agent_ids: selectedAgentIds,
        approval_mode: createForm.approvalMode,
        risk_level: createForm.riskLevel,
        reason_code: createForm.reasonCode,
        status: createForm.status,
        idempotency_key: key,
        metadata,
      });
      setCreateOpen(false);
      await loadPlaybooks();
      pushToast({
        title: response.data.created ? 'Playbook created' : 'Idempotent replay returned existing playbook',
        description: `Playbook ID: ${response.data.item.playbook_id}`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Create playbook failed', description: getApiErrorMessage(error, 'Unable to create playbook'), tone: 'error' });
    } finally {
      setCreateBusy(false);
    }
  };

  const openExecute = (row: Playbook) => {
    setExecuteTarget(row);
    setExecuteReason('');
    setExecuteOpen(true);
  };

  const executePlaybook = async () => {
    if (!executeTarget) return;
    if (executeReason.trim().length < 5) {
      pushToast({ title: 'Execution reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setExecuteBusy(true);
    try {
      const response = await CoreApi.executePlaybook(executeTarget.playbook_id, { reason: executeReason.trim() });
      setExecuteOpen(false);
      await Promise.all([loadPlaybooks(), loadRuns()]);
      pushToast({
        title: 'Playbook run created',
        description: `Run ${response.data.run_id} status: ${response.data.status}`,
        tone: response.data.status === 'FAILED' ? 'error' : 'success',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Execute playbook failed', description: getApiErrorMessage(error, 'Unable to execute playbook'), tone: 'error' });
    } finally {
      setExecuteBusy(false);
    }
  };

  const openDecision = (row: PlaybookRun, decision: PlaybookRunDecisionPayload['decision']) => {
    setDecisionTarget(row);
    setDecisionValue(decision);
    setDecisionReason('');
    setDecisionOpen(true);
  };

  const decideRun = async () => {
    if (!decisionTarget) return;
    if (decisionReason.trim().length < 5) {
      pushToast({ title: 'Decision reason should be at least 5 characters', tone: 'warning' });
      return;
    }
    setDecisionBusy(true);
    try {
      const response = await CoreApi.decidePlaybookRun(decisionTarget.run_id, {
        decision: decisionValue,
        reason: decisionReason.trim(),
      });
      setDecisionOpen(false);
      await Promise.all([loadRuns(), loadPlaybooks()]);
      pushToast({
        title: 'Run decision recorded',
        description: `Run ${response.data.run_id} now ${response.data.status}`,
        tone: response.data.status === 'FAILED' ? 'error' : 'success',
      });
    } catch (error: unknown) {
      pushToast({ title: 'Run decision failed', description: getApiErrorMessage(error, 'Unable to record decision'), tone: 'error' });
    } finally {
      setDecisionBusy(false);
    }
  };

  const playbookColumns: DataTableColumn<Playbook>[] = [
    {
      key: 'name',
      header: 'Playbook',
      render: (row) => (
        <div className="flex max-w-[240px] flex-col">
          <span className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.name}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.playbook_id}</span>
        </div>
      ),
    },
    { key: 'trigger_type', header: 'Trigger' },
    { key: 'action', header: 'Action', render: (row) => actionLabel(row.action) },
    { key: 'approval_mode', header: 'Approval' },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    { key: 'last_run_at', header: 'Last Run', render: (row) => formatDate(row.last_run_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <button
          type="button"
          className="btn-secondary h-8 px-2 text-xs"
          onClick={() => openExecute(row)}
          disabled={row.status !== 'ACTIVE'}
        >
          <FiPlay className="mr-1 text-xs" />
          Execute
        </button>
      ),
    },
  ];

  const runColumns: DataTableColumn<PlaybookRun>[] = [
    { key: 'run_id', header: 'Run ID' },
    {
      key: 'playbook_name',
      header: 'Playbook',
      render: (row) => (
        <div className="flex max-w-[210px] flex-col">
          <span className="truncate font-medium">{row.playbook_name}</span>
          <span className="truncate text-xs text-slate-500 dark:text-slate-400">{row.playbook_id}</span>
        </div>
      ),
    },
    { key: 'requested_by_username', header: 'Requested By', render: (row) => row.requested_by_username || `User #${row.requested_by_user_id}` },
    {
      key: 'status',
      header: 'Status',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadgeClass(row.status)}`}>{row.status}</span>
      ),
    },
    { key: 'created_at', header: 'Created', render: (row) => formatDate(row.created_at) },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) =>
        row.status === 'PENDING_APPROVAL' || row.status === 'PARTIALLY_APPROVED' ? (
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Playbooks"
        subtitle="One-click incident actions with approval modes, two-person gate, and auditable run records."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void Promise.all([loadPlaybooks(), loadRuns()])}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={openCreate}>
              <FiPlus className="mr-2 text-sm" />
              Create Playbook
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_180px_180px_180px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search playbook or run"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Playbook Status</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="DISABLED">DISABLED</option>
          </select>

          <select
            value={approvalFilter}
            onChange={(event) => setApprovalFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Approval Modes</option>
            <option value="AUTO">AUTO</option>
            <option value="MANUAL">MANUAL</option>
            <option value="TWO_PERSON">TWO_PERSON</option>
          </select>

          <select
            value={runStatusFilter}
            onChange={(event) => setRunStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Run Status</option>
            <option value="PENDING_APPROVAL">PENDING_APPROVAL</option>
            <option value="PARTIALLY_APPROVED">PARTIALLY_APPROVED</option>
            <option value="DISPATCHED">DISPATCHED</option>
            <option value="REJECTED">REJECTED</option>
            <option value="FAILED">FAILED</option>
          </select>

          <button
            type="button"
            className="btn-secondary h-11"
            onClick={() => void Promise.all([loadPlaybooks(), loadRuns()])}
          >
            Apply
          </button>
        </div>
      </Card>

      <Card title="Playbook Templates" subtitle="Template library used by analysts and responders for repeatable operations.">
        {playbookStatus === 'loading' && <LoadingState title="Loading playbooks" description="Fetching playbook templates." />}
        {playbookStatus === 'error' && <ErrorState description={playbookError} onRetry={() => void loadPlaybooks()} />}
        {playbookStatus === 'ready' && playbooks.length > 0 && (
          <DataTable columns={playbookColumns} rows={playbooks} rowKey={(row) => row.playbook_id} />
        )}
        {playbookStatus === 'ready' && playbooks.length === 0 && (
          <EmptyState
            title="No playbooks configured"
            description="Create your first playbook to standardize incident response actions."
            actionLabel="Create Playbook"
            onAction={openCreate}
          />
        )}
      </Card>

      <Card title="Playbook Runs" subtitle="Execution and approval history with two-person rule enforcement.">
        {runStatus === 'loading' && <LoadingState title="Loading run history" description="Fetching playbook run records." />}
        {runStatus === 'error' && <ErrorState description={runError} onRetry={() => void loadRuns()} />}
        {runStatus === 'ready' && runs.length > 0 && <DataTable columns={runColumns} rows={runs} rowKey={(row) => row.run_id} />}
        {runStatus === 'ready' && runs.length === 0 && (
          <EmptyState title="No playbook runs" description="Execute a playbook to create first run record." />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Create Playbook"
        description="Define trigger, action, approval mode, and target fleet set."
        confirmLabel={createBusy ? 'Creating...' : 'Create Playbook'}
        confirmDisabled={createBusy}
        cancelLabel="Cancel"
        cancelDisabled={createBusy}
        onCancel={() => {
          setCreateOpen(false);
        }}
        onConfirm={() => void createPlaybook()}
      >
        <div className="space-y-3">
          <input
            className="input"
            value={createForm.name}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
            placeholder="Playbook name"
          />
          <textarea
            className="input min-h-[72px] resize-y"
            value={createForm.description}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
            placeholder="Description"
          />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.triggerType}
              disabled={createBusy}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, triggerType: event.target.value as PlaybookTriggerType }))
              }
            >
              <option value="MANUAL">MANUAL</option>
              <option value="ALERT_MATCH">ALERT_MATCH</option>
              <option value="AGENT_HEALTH">AGENT_HEALTH</option>
              <option value="SCHEDULED">SCHEDULED</option>
            </select>
            <select
              className="input"
              value={createForm.action}
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, action: event.target.value as RemoteActionKind }))}
            >
              <option value="restart">Restart</option>
              <option value="policy_push">Policy Push</option>
              <option value="shutdown">Shutdown</option>
              <option value="lockdown">Lockdown</option>
            </select>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.approvalMode}
              disabled={createBusy}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, approvalMode: event.target.value as PlaybookApprovalMode }))
              }
            >
              <option value="AUTO">AUTO</option>
              <option value="MANUAL">MANUAL</option>
              <option value="TWO_PERSON">TWO_PERSON</option>
            </select>
            <select
              className="input"
              value={createForm.riskLevel}
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, riskLevel: event.target.value as PlaybookRiskLevel }))}
            >
              <option value="LOW">LOW</option>
              <option value="HIGH">HIGH</option>
            </select>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.reasonCode}
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, reasonCode: event.target.value as ReasonCode }))}
            >
              {reasonOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              className="input"
              value={createForm.status}
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, status: event.target.value as PlaybookStatus }))}
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="DISABLED">DISABLED</option>
            </select>
          </div>

          <input
            className="input"
            value={createForm.idempotencyKey}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, idempotencyKey: event.target.value }))}
            placeholder="Idempotency key"
          />

          <textarea
            className="input min-h-[92px] resize-y font-mono text-xs"
            value={createForm.metadataJson}
            disabled={createBusy}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, metadataJson: event.target.value }))}
            placeholder="Metadata JSON"
          />

          <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Target Agents ({selectedAgentIds.length} selected)
              </p>
              <button
                type="button"
                className="btn-secondary h-8 px-2 text-xs"
                disabled={createBusy}
                onClick={() => setSelectedAgentIds(agents.filter((agent) => agent.status === 'ONLINE').map((agent) => agent.id))}
              >
                Select Online
              </button>
            </div>
            <label className="mb-2 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
              <FiSearch className="text-slate-400" />
              <input
                value={agentSearch}
                disabled={createBusy}
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
                    disabled={createBusy}
                    onClick={() => toggleAgent(agent.id)}
                    className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm transition ${
                      selected
                        ? 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span className="truncate">
                      #{agent.id} - {agent.name} ({agent.hostname})
                    </span>
                    <span className="ml-2 shrink-0">{selected ? <FiCheckSquare /> : <FiSquare />}</span>
                  </button>
                );
              })}
              {!filteredAgents.length && (
                <p className="py-3 text-center text-xs text-slate-500 dark:text-slate-400">No agents available.</p>
              )}
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        open={executeOpen}
        title={executeTarget ? `Execute ${executeTarget.name}` : 'Execute Playbook'}
        description="Create a run record and dispatch immediately or wait for approvals."
        confirmLabel={executeBusy ? 'Executing...' : 'Execute'}
        confirmDisabled={executeBusy}
        cancelLabel="Cancel"
        cancelDisabled={executeBusy}
        onCancel={() => {
          setExecuteOpen(false);
          setExecuteTarget(null);
        }}
        onConfirm={() => void executePlaybook()}
      >
        <textarea
          className="input min-h-[96px] resize-y"
          value={executeReason}
          disabled={executeBusy}
          onChange={(event) => setExecuteReason(event.target.value)}
          placeholder="Execution reason (min 5 chars)"
        />
      </Modal>

      <Modal
        open={decisionOpen}
        title={decisionTarget ? `Run Decision - ${decisionTarget.run_id}` : 'Run Decision'}
        description={`Decision: ${decisionValue}`}
        confirmLabel={decisionBusy ? 'Submitting...' : decisionValue}
        confirmDisabled={decisionBusy}
        cancelLabel="Cancel"
        cancelDisabled={decisionBusy}
        onCancel={() => {
          setDecisionOpen(false);
          setDecisionTarget(null);
        }}
        onConfirm={() => void decideRun()}
      >
        <textarea
          className="input min-h-[96px] resize-y"
          value={decisionReason}
          disabled={decisionBusy}
          onChange={(event) => setDecisionReason(event.target.value)}
          placeholder="Decision reason (min 5 chars)"
        />
      </Modal>

      <Card>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
          <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            <FiShield className="mr-2 inline text-sm" />
            Playbook safety model
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            `MANUAL` and `TWO_PERSON` modes enforce approval gates before dispatching endpoint actions.
          </p>
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Each run has immutable status progression and full audit entries for requester and approvers.
          </p>
        </div>
      </Card>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
