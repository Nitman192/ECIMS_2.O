import { useEffect, useMemo, useState } from 'react';
import { FiCalendar, FiClock, FiEye, FiPause, FiPlay, FiPlus, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage, normalizeListResponse } from '../../api/utils';
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
import type {
  Agent,
  MaintenanceOrchestrationMode,
  MaintenanceSchedule,
  MaintenanceScheduleConflict,
  MaintenanceScheduleRecurrence,
  MaintenanceScheduleStatus,
} from '../../types';

const timezoneOptions = ['UTC', 'Asia/Kolkata', 'America/New_York', 'Europe/London'];
const weekdays = [
  { label: 'Mon', value: 0 },
  { label: 'Tue', value: 1 },
  { label: 'Wed', value: 2 },
  { label: 'Thu', value: 3 },
  { label: 'Fri', value: 4 },
  { label: 'Sat', value: 5 },
  { label: 'Sun', value: 6 },
];

const reasonCodes = [
  { value: 'MAINTENANCE', label: 'Maintenance' },
  { value: 'COMPLIANCE', label: 'Compliance' },
  { value: 'INCIDENT_RESPONSE', label: 'Incident Response' },
  { value: 'TESTING', label: 'Testing' },
  { value: 'ROLLBACK', label: 'Rollback' },
  { value: 'POLICY_CHANGE', label: 'Policy Change' },
] as const;

const modeOptions: Array<{ value: MaintenanceOrchestrationMode; label: string; description: string }> = [
  {
    value: 'SAFE_SHUTDOWN_START',
    label: 'Safe Shutdown + Start',
    description: 'notify -> drain -> shutdown -> restart verify',
  },
  { value: 'SHUTDOWN_ONLY', label: 'Shutdown Only', description: 'single shutdown stage' },
  { value: 'RESTART_ONLY', label: 'Restart Only', description: 'single restart stage' },
  { value: 'POLICY_PUSH_ONLY', label: 'Policy Push Only', description: 'single policy push stage' },
];

type CreateForm = {
  windowName: string;
  timezone: string;
  startTimeLocal: string;
  durationMinutes: number;
  recurrence: MaintenanceScheduleRecurrence;
  weeklyDays: number[];
  targetAgentIds: number[];
  orchestrationMode: MaintenanceOrchestrationMode;
  status: MaintenanceScheduleStatus;
  reasonCode: (typeof reasonCodes)[number]['value'];
  reason: string;
  allowConflicts: boolean;
  idempotencyKey: string;
};

type CreateFormErrors = {
  windowName?: string;
  durationMinutes?: string;
  weeklyDays?: string;
  targetAgentIds?: string;
  reason?: string;
  idempotencyKey?: string;
};

const defaultForm: CreateForm = {
  windowName: '',
  timezone: 'UTC',
  startTimeLocal: '02:00',
  durationMinutes: 60,
  recurrence: 'DAILY',
  weeklyDays: [1, 3, 5],
  targetAgentIds: [],
  orchestrationMode: 'SAFE_SHUTDOWN_START',
  status: 'ACTIVE',
  reasonCode: 'MAINTENANCE',
  reason: '',
  allowConflicts: false,
  idempotencyKey: createIdempotencyKey('sched'),
};

const modeLabel = (value: string) => modeOptions.find((item) => item.value === value)?.label || value;

const statusClass = (value: string) => {
  if (value === 'ACTIVE') return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
  if (value === 'PAUSED') return 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300';
};

export const SchedulesPage = () => {
  const [schedules, setSchedules] = useState<MaintenanceSchedule[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [timezoneFilter, setTimezoneFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [form, setForm] = useState<CreateForm>(defaultForm);
  const [formErrors, setFormErrors] = useState<CreateFormErrors>({});
  const [previewRuns, setPreviewRuns] = useState<Array<{ run_at_local: string; window_end_local: string }>>([]);
  const [previewConflicts, setPreviewConflicts] = useState<MaintenanceScheduleConflict[]>([]);

  const [conflictsOpen, setConflictsOpen] = useState(false);
  const [conflictsBusy, setConflictsBusy] = useState(false);
  const [conflictsSchedule, setConflictsSchedule] = useState<MaintenanceSchedule | null>(null);
  const [conflictsRows, setConflictsRows] = useState<MaintenanceScheduleConflict[]>([]);

  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 3800 });

  const loadAgents = async () => {
    try {
      const response = await CoreApi.agents();
      setAgents(normalizeListResponse<Agent>(response.data));
    } catch {
      setAgents([]);
    }
  };

  const loadSchedules = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listSchedules({
        page: 1,
        page_size: 100,
        status: toOptionalFilter(statusFilter),
        timezone: toOptionalFilter(timezoneFilter),
        q: toOptionalQuery(query),
      });
      setSchedules(response.data.items ?? []);
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load maintenance schedules'));
      setStatus('error');
    }
  };

  useEffect(() => {
    void Promise.all([loadAgents(), loadSchedules()]);
  }, []);

  const sortedAgents = useMemo(() => [...agents].sort((a, b) => a.id - b.id), [agents]);

  const openCreate = () => {
    setForm({ ...defaultForm, idempotencyKey: createIdempotencyKey('sched') });
    setFormErrors({});
    setPreviewRuns([]);
    setPreviewConflicts([]);
    setCreateOpen(true);
  };

  const validateForm = (strict = false): CreateFormErrors => {
    const nextErrors: CreateFormErrors = {};
    if (form.windowName.trim().length < 3) {
      nextErrors.windowName = 'Window name must be at least 3 characters.';
    }
    if (form.durationMinutes < 15 || form.durationMinutes > 1440) {
      nextErrors.durationMinutes = 'Duration must be between 15 and 1440 minutes.';
    }
    if (!form.targetAgentIds.length) {
      nextErrors.targetAgentIds = 'Select at least one target agent.';
    }
    if (form.recurrence === 'WEEKLY' && form.weeklyDays.length === 0) {
      nextErrors.weeklyDays = 'Select at least one weekday for weekly recurrence.';
    }
    if (strict) {
      if (form.reason.trim().length < 5) {
        nextErrors.reason = 'Reason should be at least 5 characters.';
      }
      nextErrors.idempotencyKey = validateIdempotencyKey(form.idempotencyKey, { minLength: 8 });
    }
    return nextErrors;
  };

  const toggleWeeklyDay = (day: number) => {
    setForm((prev) => {
      const exists = prev.weeklyDays.includes(day);
      return {
        ...prev,
        weeklyDays: exists ? prev.weeklyDays.filter((item) => item !== day) : [...prev.weeklyDays, day].sort(),
      };
    });
  };

  const toggleTargetAgent = (agentId: number) => {
    setForm((prev) => {
      const exists = prev.targetAgentIds.includes(agentId);
      return {
        ...prev,
        targetAgentIds: exists ? prev.targetAgentIds.filter((item) => item !== agentId) : [...prev.targetAgentIds, agentId],
      };
    });
  };

  const previewSchedule = async () => {
    const nextErrors = validateForm(false);
    setFormErrors((prev) => ({
      ...prev,
      windowName: nextErrors.windowName,
      durationMinutes: nextErrors.durationMinutes,
      weeklyDays: nextErrors.weeklyDays,
      targetAgentIds: nextErrors.targetAgentIds,
    }));
    if (Object.keys(nextErrors).length > 0) {
      pushToast({ title: 'Validation failed', description: 'Fix highlighted fields before preview.', tone: 'warning' });
      return;
    }
    setPreviewBusy(true);
    try {
      const response = await CoreApi.previewSchedule({
        window_name: form.windowName.trim(),
        timezone: form.timezone,
        start_time_local: form.startTimeLocal,
        duration_minutes: form.durationMinutes,
        recurrence: form.recurrence,
        weekly_days: form.recurrence === 'WEEKLY' ? form.weeklyDays : [],
        target_agent_ids: form.targetAgentIds,
        orchestration_mode: form.orchestrationMode,
        metadata: { source: 'admin-console' },
      });
      setPreviewRuns(
        (response.data.next_runs ?? []).map((item) => ({
          run_at_local: item.run_at_local,
          window_end_local: item.window_end_local,
        })),
      );
      setPreviewConflicts(response.data.conflicts ?? []);
      pushToast({
        title: 'Preview updated',
        description: `${response.data.next_runs?.length ?? 0} upcoming runs, ${response.data.conflict_count ?? 0} conflicts`,
        tone: 'info',
      });
    } catch (error: unknown) {
      pushToast({
        title: 'Preview failed',
        description: getApiErrorMessage(error, 'Unable to preview schedule'),
        tone: 'error',
      });
    } finally {
      setPreviewBusy(false);
    }
  };

  const createSchedule = async () => {
    const nextErrors = validateForm(true);
    setFormErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      pushToast({ title: 'Validation failed', description: 'Fix highlighted fields before create.', tone: 'warning' });
      return;
    }

    setCreateBusy(true);
    try {
      const response = await CoreApi.createSchedule({
        window_name: form.windowName.trim(),
        timezone: form.timezone,
        start_time_local: form.startTimeLocal,
        duration_minutes: form.durationMinutes,
        recurrence: form.recurrence,
        weekly_days: form.recurrence === 'WEEKLY' ? form.weeklyDays : [],
        target_agent_ids: form.targetAgentIds,
        orchestration_mode: form.orchestrationMode,
        status: form.status,
        reason_code: form.reasonCode,
        reason: form.reason.trim(),
        allow_conflicts: form.allowConflicts,
        idempotency_key: form.idempotencyKey.trim(),
        metadata: { source: 'admin-console', module: 'schedules' },
      });
      setCreateOpen(false);
      await loadSchedules();
      pushToast({
        title: response.data.created ? 'Schedule created' : 'Idempotent replay returned existing schedule',
        description: `Schedule #${response.data.item.id} saved`,
        tone: response.data.created ? 'success' : 'info',
      });
    } catch (error: unknown) {
      pushToast({
        title: 'Create schedule failed',
        description: getApiErrorMessage(error, 'Unable to create schedule'),
        tone: 'error',
      });
    } finally {
      setCreateBusy(false);
    }
  };

  const runDueSchedules = async () => {
    try {
      const response = await CoreApi.runDueSchedules(20);
      await loadSchedules();
      pushToast({
        title: 'Runner executed',
        description: `Due: ${response.data.due_count}, executed: ${response.data.executed_count}, failed: ${response.data.failed_count}`,
        tone: response.data.failed_count > 0 ? 'warning' : 'success',
      });
    } catch (error: unknown) {
      pushToast({
        title: 'Runner failed',
        description: getApiErrorMessage(error, 'Unable to run due schedules'),
        tone: 'error',
      });
    }
  };

  const updateScheduleState = async (row: MaintenanceSchedule, nextStatus: MaintenanceScheduleStatus) => {
    try {
      await CoreApi.updateScheduleState(row.id, {
        status: nextStatus,
        reason: nextStatus === 'PAUSED' ? 'Paused from schedule console' : 'Activated from schedule console',
      });
      await loadSchedules();
      pushToast({ title: `Schedule ${nextStatus.toLowerCase()}`, tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'State update failed',
        description: getApiErrorMessage(error, 'Unable to update schedule state'),
        tone: 'error',
      });
    }
  };

  const openConflicts = async (row: MaintenanceSchedule) => {
    setConflictsOpen(true);
    setConflictsBusy(true);
    setConflictsSchedule(row);
    setConflictsRows([]);
    try {
      const response = await CoreApi.getScheduleConflicts(row.id);
      setConflictsRows(response.data.conflicts ?? []);
    } catch (error: unknown) {
      pushToast({
        title: 'Unable to load conflicts',
        description: getApiErrorMessage(error, 'Conflict fetch failed'),
        tone: 'error',
      });
    } finally {
      setConflictsBusy(false);
    }
  };

  const columns: DataTableColumn<MaintenanceSchedule>[] = [
    {
      key: 'window_name',
      header: 'Window',
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-semibold text-slate-900 dark:text-slate-100">{row.window_name}</span>
          <span className="text-xs text-slate-500 dark:text-slate-400">{modeLabel(row.orchestration_mode)}</span>
        </div>
      ),
    },
    { key: 'timezone', header: 'Timezone' },
    {
      key: 'next_run_local',
      header: 'Next Run',
      render: (row) =>
        row.next_run_local ? new Date(row.next_run_local).toLocaleString() : row.next_run_at ? new Date(row.next_run_at).toLocaleString() : 'Not scheduled',
    },
    {
      key: 'status',
      header: 'State',
      render: (row) => (
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(row.status)}`}>{row.status}</span>
      ),
    },
    {
      key: 'conflict_count',
      header: 'Conflicts',
      render: (row) => (
        <span className={`text-xs font-semibold ${row.conflict_count ? 'text-rose-600 dark:text-rose-300' : 'text-slate-500 dark:text-slate-400'}`}>
          {row.conflict_count ?? 0}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-2">
          <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void openConflicts(row)}>
            <FiEye className="mr-1 text-xs" />
            Conflicts
          </button>
          {row.status === 'ACTIVE' ? (
            <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void updateScheduleState(row, 'PAUSED')}>
              <FiPause className="mr-1 text-xs" />
              Pause
            </button>
          ) : (
            <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => void updateScheduleState(row, 'ACTIVE')}>
              <FiPlay className="mr-1 text-xs" />
              Activate
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Maintenance Schedules"
        subtitle="Plan safe maintenance windows with next-run preview, overlap detection, and controlled orchestration runner."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadSchedules()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-secondary" onClick={() => void runDueSchedules()}>
              <FiClock className="mr-2 text-sm" />
              Run Due
            </button>
            <button type="button" className="btn-primary" onClick={openCreate}>
              <FiPlus className="mr-2 text-sm" />
              Create Schedule
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
              placeholder="Search window name or reason"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All States</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="PAUSED">PAUSED</option>
            <option value="DRAFT">DRAFT</option>
          </select>

          <select
            value={timezoneFilter}
            onChange={(event) => setTimezoneFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Timezones</option>
            {timezoneOptions.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadSchedules()}>
            Apply
          </button>
        </div>
      </Card>

      <Card title="Schedule Inventory" subtitle="Upcoming maintenance windows with conflict and status visibility.">
        {status === 'loading' && <LoadingState title="Loading schedules" description="Fetching maintenance schedule inventory." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadSchedules()} />}
        {status === 'ready' && schedules.length > 0 && (
          <DataTable columns={columns} rows={schedules} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && schedules.length === 0 && (
          <EmptyState
            title="No maintenance windows"
            description="Create your first schedule with next-run preview and conflict checks."
            actionLabel="Create Schedule"
            onAction={openCreate}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Create Maintenance Schedule"
        description="Define schedule policy, target fleet, conflict policy, and preview next runs before saving."
        confirmLabel={createBusy ? 'Saving...' : 'Create Schedule'}
        confirmDisabled={createBusy || previewBusy}
        cancelLabel="Cancel"
        cancelDisabled={createBusy || previewBusy}
        onCancel={() => setCreateOpen(false)}
        onConfirm={() => void createSchedule()}
      >
        <div className="space-y-3">
          <input
            className="input"
            placeholder="Window name"
            value={form.windowName}
            disabled={createBusy || previewBusy}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, windowName: event.target.value }));
              if (formErrors.windowName) {
                setFormErrors((prev) => ({ ...prev, windowName: undefined }));
              }
            }}
          />
          {formErrors.windowName && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.windowName}</p>}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={form.timezone}
              disabled={createBusy || previewBusy}
              onChange={(event) => setForm((prev) => ({ ...prev, timezone: event.target.value }))}
            >
              {timezoneOptions.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </select>
            <input
              type="time"
              className="input"
              value={form.startTimeLocal}
              disabled={createBusy || previewBusy}
              onChange={(event) => setForm((prev) => ({ ...prev, startTimeLocal: event.target.value }))}
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              type="number"
              className="input"
              min={15}
              max={1440}
              value={form.durationMinutes}
              disabled={createBusy || previewBusy}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, durationMinutes: Number(event.target.value) || 60 }));
                if (formErrors.durationMinutes) {
                  setFormErrors((prev) => ({ ...prev, durationMinutes: undefined }));
                }
              }}
              placeholder="Duration (minutes)"
            />
            <select
              className="input"
              value={form.recurrence}
              disabled={createBusy || previewBusy}
              onChange={(event) => setForm((prev) => ({ ...prev, recurrence: event.target.value as MaintenanceScheduleRecurrence }))}
            >
              <option value="DAILY">DAILY</option>
              <option value="WEEKLY">WEEKLY</option>
            </select>
          </div>
          {formErrors.durationMinutes && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.durationMinutes}</p>}

          {form.recurrence === 'WEEKLY' && (
            <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-900">
              {weekdays.map((day) => {
                const selected = form.weeklyDays.includes(day.value);
                return (
                  <button
                    key={day.value}
                    type="button"
                    disabled={createBusy || previewBusy}
                    className={`rounded-lg px-2 py-1 text-xs font-semibold transition ${
                      selected
                        ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
                        : 'bg-white text-slate-600 hover:bg-slate-100 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                    }`}
                    onClick={() => toggleWeeklyDay(day.value)}
                  >
                    {day.label}
                  </button>
                );
              })}
            </div>
          )}
          {formErrors.weeklyDays && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.weeklyDays}</p>}

          <select
            className="input"
            value={form.orchestrationMode}
            disabled={createBusy || previewBusy}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, orchestrationMode: event.target.value as MaintenanceOrchestrationMode }))
            }
          >
            {modeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} - {option.description}
              </option>
            ))}
          </select>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={form.status}
              disabled={createBusy || previewBusy}
              onChange={(event) => setForm((prev) => ({ ...prev, status: event.target.value as MaintenanceScheduleStatus }))}
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="PAUSED">PAUSED</option>
              <option value="DRAFT">DRAFT</option>
            </select>
            <select
              className="input"
              value={form.reasonCode}
              disabled={createBusy || previewBusy}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, reasonCode: event.target.value as (typeof reasonCodes)[number]['value'] }))
              }
            >
              {reasonCodes.map((reason) => (
                <option key={reason.value} value={reason.value}>
                  {reason.label}
                </option>
              ))}
            </select>
          </div>

          <textarea
            className="input min-h-[84px] resize-y"
            value={form.reason}
            disabled={createBusy || previewBusy}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, reason: event.target.value }));
              if (formErrors.reason) {
                setFormErrors((prev) => ({ ...prev, reason: undefined }));
              }
            }}
            placeholder="Reason (min 5 chars)"
          />
          {formErrors.reason && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.reason}</p>}

          <input
            className="input"
            value={form.idempotencyKey}
            disabled={createBusy || previewBusy}
            onChange={(event) => {
              setForm((prev) => ({ ...prev, idempotencyKey: event.target.value }));
              if (formErrors.idempotencyKey) {
                setFormErrors((prev) => ({ ...prev, idempotencyKey: undefined }));
              }
            }}
            placeholder="Idempotency key"
          />
          {formErrors.idempotencyKey && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.idempotencyKey}</p>}

          <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-700">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                Target Agents ({form.targetAgentIds.length})
              </p>
              <button
                type="button"
                className="btn-secondary h-8 px-2 text-xs"
                disabled={createBusy || previewBusy}
                onClick={() => setForm((prev) => ({ ...prev, targetAgentIds: agents.filter((a) => a.status === 'ONLINE').map((a) => a.id) }))}
              >
                Select Online
              </button>
            </div>
            <div className="max-h-40 space-y-1 overflow-y-auto">
              {sortedAgents.map((agent) => {
                const selected = form.targetAgentIds.includes(agent.id);
                return (
                  <button
                    key={agent.id}
                    type="button"
                    disabled={createBusy || previewBusy}
                    onClick={() => toggleTargetAgent(agent.id)}
                    className={`flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-xs transition ${
                      selected
                        ? 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                  >
                    <span>
                      #{agent.id} {agent.name} ({agent.hostname})
                    </span>
                    <span className="font-semibold">{selected ? 'Selected' : agent.status}</span>
                  </button>
                );
              })}
            </div>
          </div>
          {formErrors.targetAgentIds && <p className="text-xs text-rose-600 dark:text-rose-400">{formErrors.targetAgentIds}</p>}

          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={form.allowConflicts}
              disabled={createBusy || previewBusy}
              onChange={(event) => setForm((prev) => ({ ...prev, allowConflicts: event.target.checked }))}
            />
            Allow conflicting schedules (not recommended)
          </label>

          <button type="button" className="btn-secondary h-9 w-full text-sm" onClick={() => void previewSchedule()} disabled={previewBusy}>
            <FiCalendar className="mr-2 text-sm" />
            {previewBusy ? 'Generating Preview...' : 'Preview Next Runs & Conflicts'}
          </button>

          {(previewRuns.length > 0 || previewConflicts.length > 0) && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900">
              <p className="mb-2 font-semibold text-slate-700 dark:text-slate-200">Preview</p>
              {previewRuns.length > 0 && (
                <div className="space-y-1">
                  {previewRuns.slice(0, 3).map((run, index) => (
                    <p key={`${run.run_at_local}-${index}`} className="text-slate-600 dark:text-slate-300">
                      {index + 1}. {new Date(run.run_at_local).toLocaleString()} {'->'}{' '}
                      {new Date(run.window_end_local).toLocaleString()}
                    </p>
                  ))}
                </div>
              )}
              {previewConflicts.length > 0 && (
                <p className="mt-2 text-rose-600 dark:text-rose-300">
                  {previewConflicts.length} conflict(s) detected with existing schedules.
                </p>
              )}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        open={conflictsOpen}
        title={conflictsSchedule ? `Conflicts · ${conflictsSchedule.window_name}` : 'Schedule Conflicts'}
        description="Overlapping windows for shared target agents."
        cancelLabel="Close"
        onCancel={() => {
          setConflictsOpen(false);
          setConflictsRows([]);
          setConflictsSchedule(null);
        }}
      >
        {conflictsBusy && <p className="text-sm text-slate-500 dark:text-slate-400">Loading conflicts...</p>}
        {!conflictsBusy && conflictsRows.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-300">No conflicts detected.</p>
        )}
        {!conflictsBusy && conflictsRows.length > 0 && (
          <div className="space-y-2">
            {conflictsRows.map((conflict) => (
              <div key={`${conflict.schedule_id}-${conflict.overlap_start_utc}`} className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs dark:border-rose-900/60 dark:bg-rose-950/20">
                <p className="font-semibold text-rose-700 dark:text-rose-300">
                  Schedule #{conflict.schedule_id} · {conflict.window_name}
                </p>
                <p className="mt-1 text-rose-600 dark:text-rose-300">
                  Overlap: {new Date(conflict.overlap_start_local).toLocaleString()}
                </p>
                <p className="mt-1 text-rose-600 dark:text-rose-300">
                  Shared Agents: {conflict.shared_agent_ids.join(', ')}
                </p>
              </div>
            ))}
          </div>
        )}
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
