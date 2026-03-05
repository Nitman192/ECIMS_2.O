import { useEffect, useMemo, useState } from 'react';
import { FiDownload, FiFilter, FiRefreshCw, FiSearch } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { toOptionalFilter, toOptionalQuery } from '../../utils/listQuery';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';

type AuditExplorerRow = {
  id: number;
  ts: string;
  actor_type: string;
  actor_id?: number | null;
  actor_username?: string | null;
  actor_role?: string | null;
  action: string;
  target_type: string;
  target_id?: string | null;
  message: string;
  metadata?: Record<string, unknown>;
};

const formatDateTimeInput = (value: string): string => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString();
};

const rowActor = (row: AuditExplorerRow) => {
  if (row.actor_username) return `${row.actor_username}${row.actor_role ? ` (${row.actor_role})` : ''}`;
  if (row.actor_id) return `${row.actor_type} #${row.actor_id}`;
  return row.actor_type;
};

const rowTarget = (row: AuditExplorerRow) => {
  if (row.target_id) return `${row.target_type}:${row.target_id}`;
  return row.target_type;
};

const columns: DataTableColumn<AuditExplorerRow>[] = [
  {
    key: 'id',
    header: 'Event',
    render: (row) => (
      <div className="flex max-w-[180px] flex-col">
        <span className="truncate font-semibold text-slate-900 dark:text-slate-100">#{row.id}</span>
        <span className="truncate text-xs text-slate-500 dark:text-slate-400">{new Date(row.ts).toLocaleString()}</span>
      </div>
    ),
  },
  {
    key: 'actor',
    header: 'Actor',
    render: (row) => rowActor(row),
  },
  {
    key: 'action',
    header: 'Action',
    render: (row) => <span className="font-medium">{row.action}</span>,
  },
  {
    key: 'target',
    header: 'Target',
    render: (row) => rowTarget(row),
  },
  {
    key: 'message',
    header: 'Message',
    render: (row) => <span className="max-w-[360px] truncate">{row.message}</span>,
  },
];

export const AdminAuditExplorerPage = () => {
  const [rows, setRows] = useState<AuditExplorerRow[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [exportNotice, setExportNotice] = useState('');
  const [exportBusy, setExportBusy] = useState(false);

  const [query, setQuery] = useState('');
  const [actionType, setActionType] = useState('');
  const [role, setRole] = useState('');
  const [user, setUser] = useState('');
  const [outcome, setOutcome] = useState('all');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');

  const loadAudit = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.auditLogs({
        page: '1',
        page_size: '200',
        action_type: toOptionalQuery(actionType) ?? '',
        role: toOptionalQuery(role) ?? '',
        user: toOptionalQuery(user) ?? '',
        outcome: toOptionalFilter(outcome) ?? '',
        start_ts: formatDateTimeInput(start),
        end_ts: formatDateTimeInput(end),
      });
      const payload = response.data as { items?: AuditExplorerRow[] } | AuditExplorerRow[];
      const nextRows = Array.isArray(payload) ? payload : payload.items ?? [];
      setRows(nextRows);
      setStatus('ready');
    } catch (error: unknown) {
      setRows([]);
      setStatus('error');
      setErrorMessage(getApiErrorMessage(error, 'Unable to load audit explorer data'));
    }
  };

  useEffect(() => {
    void loadAudit();
  }, []);

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return rows;
    return rows.filter((row) => {
      const haystack =
        `${row.id} ${row.ts} ${row.actor_type} ${row.actor_username || ''} ${row.actor_role || ''} ${row.action} ${row.target_type} ${row.target_id || ''} ${row.message}`.toLowerCase();
      return haystack.includes(normalized);
    });
  }, [rows, query]);

  const exportAudit = async () => {
    setExportNotice('');
    setExportBusy(true);
    try {
      const response = await CoreApi.exportAudit({
        start_ts: formatDateTimeInput(start) || '1970-01-01T00:00:00Z',
        end_ts: formatDateTimeInput(end) || new Date().toISOString(),
        action_type: toOptionalQuery(actionType),
        outcome: toOptionalFilter(outcome),
        role: toOptionalQuery(role),
        user: toOptionalQuery(user),
        redaction_profile: 'standard',
        max_rows: 100000,
      });
      const outputPath = (response.data as Record<string, unknown>)?.path;
      const rowsCount = (response.data as Record<string, unknown>)?.rows;
      setExportNotice(
        `Export ready${outputPath ? `: ${String(outputPath)}` : ''}${rowsCount ? ` (${String(rowsCount)} rows)` : ''}`,
      );
    } catch (error: unknown) {
      setExportNotice(getApiErrorMessage(error, 'Audit export failed'));
    } finally {
      setExportBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Advanced Audit Explorer"
        subtitle="Investigate actor intent, outcome, and target transitions with export-ready filtering."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadAudit()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" disabled={exportBusy} onClick={() => void exportAudit()}>
              <FiDownload className="mr-2 text-sm" />
              {exportBusy ? 'Exporting...' : 'Export Audit'}
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_220px_180px_180px_180px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search actor, action, target, message"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <input
            value={actionType}
            onChange={(event) => setActionType(event.target.value)}
            className="input h-11"
            placeholder="Action type"
          />
          <input value={role} onChange={(event) => setRole(event.target.value)} className="input h-11" placeholder="Role" />
          <input value={user} onChange={(event) => setUser(event.target.value)} className="input h-11" placeholder="Username" />
          <select
            value={outcome}
            onChange={(event) => setOutcome(event.target.value)}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Outcomes</option>
            <option value="SUCCESS">Success</option>
            <option value="FAILED">Failed</option>
          </select>

          <button type="button" className="btn-secondary h-11" onClick={() => void loadAudit()}>
            <FiFilter className="mr-2 text-sm" />
            Apply
          </button>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <input className="input h-11" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} />
          <input className="input h-11" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} />
        </div>

        {exportNotice && <p className="mt-3 text-xs text-slate-600 dark:text-slate-300">{exportNotice}</p>}
      </Card>

      <Card title="Audit Event Stream" subtitle="Server-backed audit listing with resilient query filters and export flow.">
        {status === 'loading' && <LoadingState title="Loading audit explorer" description="Fetching audit events." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadAudit()} />}
        {status === 'ready' && filteredRows.length > 0 && <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.id)} />}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No audit events found"
            description="No records matched your filters. Try broadening the time range or clearing filters."
            actionLabel="Reload"
            onAction={() => void loadAudit()}
          />
        )}
      </Card>
    </div>
  );
};
