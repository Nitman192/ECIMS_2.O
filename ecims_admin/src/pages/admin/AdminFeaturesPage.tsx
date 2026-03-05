import { useEffect, useMemo, useState } from 'react';
import { FiFlag, FiPlus, FiRefreshCw, FiSearch, FiShield } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { useToastStack } from '../../hooks/useToastStack';
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
  FeatureFlag,
  FeatureFlagCreatePayload,
  FeatureFlagRiskLevel,
  FeatureFlagScope,
} from '../../types';

type ReasonCode =
  | 'SECURITY_INCIDENT'
  | 'EMERGENCY_MITIGATION'
  | 'POLICY_CHANGE'
  | 'ROLLBACK'
  | 'MAINTENANCE'
  | 'COMPLIANCE'
  | 'TESTING';

type CreateFormState = {
  key: string;
  description: string;
  scope: FeatureFlagScope;
  scopeTarget: string;
  isEnabled: boolean;
  riskLevel: FeatureFlagRiskLevel;
  reasonCode: ReasonCode;
  reason: string;
  confirmRisky: boolean;
};

const reasonCodeOptions: Array<{ value: ReasonCode; label: string }> = [
  { value: 'POLICY_CHANGE', label: 'Policy Change' },
  { value: 'SECURITY_INCIDENT', label: 'Security Incident' },
  { value: 'EMERGENCY_MITIGATION', label: 'Emergency Mitigation' },
  { value: 'ROLLBACK', label: 'Rollback' },
  { value: 'MAINTENANCE', label: 'Maintenance' },
  { value: 'COMPLIANCE', label: 'Compliance' },
  { value: 'TESTING', label: 'Testing' },
];

const defaultCreateForm: CreateFormState = {
  key: '',
  description: '',
  scope: 'GLOBAL',
  scopeTarget: '',
  isEnabled: false,
  riskLevel: 'LOW',
  reasonCode: 'POLICY_CHANGE',
  reason: '',
  confirmRisky: false,
};

export const AdminFeaturesPage = () => {
  const [rows, setRows] = useState<FeatureFlag[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [scopeFilter, setScopeFilter] = useState('all');
  const [stateFilter, setStateFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createForm, setCreateForm] = useState<CreateFormState>(defaultCreateForm);

  const [toggleTarget, setToggleTarget] = useState<FeatureFlag | null>(null);
  const [toggleEnabled, setToggleEnabled] = useState(false);
  const [toggleReasonCode, setToggleReasonCode] = useState<ReasonCode>('POLICY_CHANGE');
  const [toggleReason, setToggleReason] = useState('');
  const [toggleConfirmRisky, setToggleConfirmRisky] = useState(false);
  const [toggleBusy, setToggleBusy] = useState(false);

  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 3800 });

  const loadFlags = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listFeatureFlags({
        q: toOptionalQuery(query),
        scope: toOptionalFilter(scopeFilter),
        state: toOptionalFilter(stateFilter),
      });
      setRows(response.data.items ?? []);
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load feature flags'));
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadFlags();
  }, []);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      if (a.is_kill_switch !== b.is_kill_switch) return a.is_kill_switch ? -1 : 1;
      return a.key.localeCompare(b.key);
    });
  }, [rows]);

  const openToggleModal = (row: FeatureFlag) => {
    const targetState = !row.enabled;
    setToggleTarget(row);
    setToggleEnabled(targetState);
    setToggleReasonCode(targetState ? 'EMERGENCY_MITIGATION' : 'ROLLBACK');
    setToggleReason('');
    setToggleConfirmRisky(false);
  };

  const submitCreateFlag = async () => {
    const key = createForm.key.trim();
    if (!/^[a-z][a-z0-9_.-]{2,63}$/.test(key)) {
      pushToast({
        title: 'Invalid key format',
        description: 'Use lowercase letters, numbers, dot, underscore, or hyphen (3-64 chars).',
        tone: 'warning',
      });
      return;
    }

    if (createForm.scope !== 'GLOBAL' && !createForm.scopeTarget.trim()) {
      pushToast({
        title: 'Scope target required',
        description: 'Provide scope target for USER or AGENT scoped flags.',
        tone: 'warning',
      });
      return;
    }

    if (createForm.reason.trim().length < 5) {
      pushToast({
        title: 'Reason is required',
        description: 'Provide an operator reason with at least 5 characters.',
        tone: 'warning',
      });
      return;
    }

    const isRiskyEnable = createForm.riskLevel === 'HIGH' && createForm.isEnabled;
    if (isRiskyEnable && !createForm.confirmRisky) {
      pushToast({
        title: 'Risk confirmation required',
        description: 'High-risk flags must be explicitly confirmed before enabling.',
        tone: 'warning',
      });
      return;
    }

    setCreateBusy(true);
    try {
      const payload: FeatureFlagCreatePayload = {
        key,
        description: createForm.description.trim(),
        scope: createForm.scope,
        scope_target: createForm.scope === 'GLOBAL' ? null : createForm.scopeTarget.trim(),
        is_enabled: createForm.isEnabled,
        risk_level: createForm.riskLevel,
        reason_code: createForm.reasonCode,
        reason: createForm.reason.trim(),
        confirm_risky: createForm.confirmRisky,
      };
      const response = await CoreApi.createFeatureFlag(payload);
      setRows((prev) => [response.data, ...prev.filter((row) => row.id !== response.data.id)]);
      setCreateOpen(false);
      setCreateForm(defaultCreateForm);
      pushToast({ title: 'Feature flag created', tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'Create failed',
        description: getApiErrorMessage(error, 'Unable to create feature flag'),
        tone: 'error',
      });
    } finally {
      setCreateBusy(false);
    }
  };

  const submitToggleFlag = async () => {
    if (!toggleTarget) return;

    if (toggleReason.trim().length < 5) {
      pushToast({
        title: 'Reason is required',
        description: 'Provide a reason with at least 5 characters.',
        tone: 'warning',
      });
      return;
    }

    if (toggleTarget.risk_level === 'HIGH' && !toggleConfirmRisky) {
      pushToast({
        title: 'Risk confirmation required',
        description: 'High-risk toggles require explicit operator confirmation.',
        tone: 'warning',
      });
      return;
    }

    setToggleBusy(true);
    try {
      const response = await CoreApi.setFeatureFlagState(toggleTarget.id, {
        enabled: toggleEnabled,
        reason_code: toggleReasonCode,
        reason: toggleReason.trim(),
        confirm_risky: toggleConfirmRisky,
      });
      setRows((prev) => prev.map((row) => (row.id === response.data.id ? response.data : row)));
      setToggleTarget(null);
      pushToast({
        title: toggleEnabled ? 'Flag enabled' : 'Flag disabled',
        tone: 'success',
      });
    } catch (error: unknown) {
      pushToast({
        title: 'State update failed',
        description: getApiErrorMessage(error, 'Unable to update feature state'),
        tone: 'error',
      });
    } finally {
      setToggleBusy(false);
    }
  };

  const columns: DataTableColumn<FeatureFlag>[] = [
    {
      key: 'key',
      header: 'Flag',
      render: (row) => (
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-900 dark:text-slate-100">{row.key}</span>
            {row.is_kill_switch && (
              <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
                Kill Switch
              </span>
            )}
          </div>
          <span className="max-w-[320px] truncate text-xs text-slate-500 dark:text-slate-400">
            {row.description || 'No description'}
          </span>
        </div>
      ),
    },
    {
      key: 'scope',
      header: 'Scope',
      render: (row) => (
        <div className="text-xs">
          <p className="font-semibold text-slate-700 dark:text-slate-200">{row.scope}</p>
          {row.scope_target && <p className="text-slate-500 dark:text-slate-400">{row.scope_target}</p>}
        </div>
      ),
    },
    {
      key: 'enabled',
      header: 'State',
      render: (row) => (
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            row.enabled
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
              : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
          }`}
        >
          {row.enabled ? 'Enabled' : 'Disabled'}
        </span>
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (row) => (
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            row.risk_level === 'HIGH'
              ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
              : 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
          }`}
        >
          {row.risk_level}
        </span>
      ),
    },
    {
      key: 'updated_at',
      header: 'Updated',
      render: (row) => (
        <span className="text-xs text-slate-600 dark:text-slate-300">
          {new Date(row.updated_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <button type="button" className="btn-secondary h-8 px-2 text-xs" onClick={() => openToggleModal(row)}>
          {row.enabled ? 'Disable' : 'Enable'}
        </button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Feature Flags & Kill Switches"
        subtitle="Operate scoped control-plane toggles with risk gates, reason codes, and audited state transitions."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadFlags()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={() => setCreateOpen(true)}>
              <FiPlus className="mr-2 text-sm" />
              Create Flag
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_180px_160px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search key, description, target"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={scopeFilter}
            onChange={(event) => setScopeFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Scopes</option>
            <option value="GLOBAL">GLOBAL</option>
            <option value="USER">USER</option>
            <option value="AGENT">AGENT</option>
          </select>

          <select
            value={stateFilter}
            onChange={(event) => setStateFilter(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All States</option>
            <option value="on">Enabled</option>
            <option value="off">Disabled</option>
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadFlags()}>
            Apply
          </button>
        </div>
      </Card>

      <Card
        title="Feature Control Inventory"
        subtitle="Global, user, and agent scoped runtime controls with safe defaults and audit trace."
      >
        {status === 'loading' && (
          <LoadingState title="Loading feature controls" description="Fetching current flag states." />
        )}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadFlags()} />}
        {status === 'ready' && sortedRows.length > 0 && (
          <DataTable columns={columns} rows={sortedRows} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && sortedRows.length === 0 && (
          <EmptyState
            title="No feature flags found"
            description="No flag matched the current filters. Clear filters or create a new control."
            actionLabel="Create Flag"
            onAction={() => setCreateOpen(true)}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Create Feature Flag"
        description="Add a new scoped control with risk classification, initial state, and audit reason."
        confirmLabel={createBusy ? 'Creating...' : 'Create Flag'}
        cancelLabel="Cancel"
        confirmDisabled={createBusy}
        cancelDisabled={createBusy}
        onCancel={() => {
          if (createBusy) return;
          setCreateOpen(false);
          setCreateForm(defaultCreateForm);
        }}
        onConfirm={() => void submitCreateFlag()}
      >
        <div className="space-y-3">
          <input
            className="input"
            placeholder="Flag key (e.g. remote_lockdown_mode)"
            value={createForm.key}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, key: event.target.value }))}
          />

          <input
            className="input"
            placeholder="Description"
            value={createForm.description}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <select
              className="input"
              value={createForm.scope}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, scope: event.target.value as FeatureFlagScope }))
              }
            >
              <option value="GLOBAL">GLOBAL</option>
              <option value="USER">USER</option>
              <option value="AGENT">AGENT</option>
            </select>

            <select
              className="input"
              value={createForm.riskLevel}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, riskLevel: event.target.value as FeatureFlagRiskLevel }))
              }
            >
              <option value="LOW">LOW</option>
              <option value="HIGH">HIGH</option>
            </select>
          </div>

          {createForm.scope !== 'GLOBAL' && (
            <input
              className="input"
              placeholder={createForm.scope === 'USER' ? 'Scope target (user id/username)' : 'Scope target (agent id)'}
              value={createForm.scopeTarget}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, scopeTarget: event.target.value }))}
            />
          )}

          <select
            className="input"
            value={createForm.reasonCode}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reasonCode: event.target.value as ReasonCode }))}
          >
            {reasonCodeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          <textarea
            className="input min-h-[84px] resize-y"
            placeholder="Change reason (min 5 chars)"
            value={createForm.reason}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, reason: event.target.value }))}
          />

          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={createForm.isEnabled}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, isEnabled: event.target.checked }))}
            />
            Enable immediately
          </label>

          {createForm.riskLevel === 'HIGH' && createForm.isEnabled && (
            <label className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
              <input
                type="checkbox"
                checked={createForm.confirmRisky}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, confirmRisky: event.target.checked }))
                }
              />
              Confirm high-risk enable action
            </label>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(toggleTarget)}
        title={toggleTarget ? `${toggleEnabled ? 'Enable' : 'Disable'} · ${toggleTarget.key}` : 'Update Flag State'}
        description="Provide reason code and operator note. High-risk toggles require explicit confirmation."
        confirmLabel={toggleBusy ? 'Applying...' : 'Apply'}
        cancelLabel="Cancel"
        confirmDisabled={toggleBusy}
        cancelDisabled={toggleBusy}
        onCancel={() => {
          if (toggleBusy) return;
          setToggleTarget(null);
        }}
        onConfirm={() => void submitToggleFlag()}
      >
        {toggleTarget && (
          <div className="space-y-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center gap-2">
                {toggleTarget.is_kill_switch ? (
                  <FiShield className="text-rose-500" />
                ) : (
                  <FiFlag className="text-cyan-500" />
                )}
                <p className="font-semibold text-slate-700 dark:text-slate-200">
                  {toggleTarget.scope}
                  {toggleTarget.scope_target ? ` · ${toggleTarget.scope_target}` : ''}
                </p>
              </div>
              <p className="mt-1 text-slate-500 dark:text-slate-400">
                Risk level: <span className="font-semibold">{toggleTarget.risk_level}</span>
              </p>
            </div>

            <select
              className="input"
              value={toggleReasonCode}
              onChange={(event) => setToggleReasonCode(event.target.value as ReasonCode)}
            >
              {reasonCodeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <textarea
              className="input min-h-[84px] resize-y"
              placeholder="Change reason (min 5 chars)"
              value={toggleReason}
              onChange={(event) => setToggleReason(event.target.value)}
            />

            {toggleTarget.risk_level === 'HIGH' && (
              <label className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
                <input
                  type="checkbox"
                  checked={toggleConfirmRisky}
                  onChange={(event) => setToggleConfirmRisky(event.target.checked)}
                />
                Confirm high-risk toggle
              </label>
            )}
          </div>
        )}
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
