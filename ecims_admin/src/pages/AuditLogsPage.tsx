import { useEffect, useMemo, useState } from 'react';
import { FiDownload, FiFilter, FiRefreshCw, FiSearch } from 'react-icons/fi';
import { CoreApi } from '../api/services';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';

type AuditRow = {
  id: string | number;
  ts?: string;
  action?: string;
  message?: string;
  actor?: string;
  resource?: string;
};

const columns: DataTableColumn<AuditRow>[] = [
  { key: 'id', header: 'Event ID' },
  {
    key: 'ts',
    header: 'Timestamp',
    render: (row) => row.ts || '-',
  },
  {
    key: 'action',
    header: 'Action',
    render: (row) => row.action || '-',
  },
  {
    key: 'actor',
    header: 'Actor',
    render: (row) => row.actor || '-',
  },
  {
    key: 'resource',
    header: 'Resource',
    render: (row) => row.resource || '-',
  },
  {
    key: 'message',
    header: 'Message',
    render: (row) => row.message || '-',
  },
];

const normalizeAuditRows = (payload: unknown): AuditRow[] => {
  if (Array.isArray(payload)) return payload as AuditRow[];
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (Array.isArray(obj.items)) return obj.items as AuditRow[];
    if (Array.isArray(obj.results)) return obj.results as AuditRow[];
    if (Array.isArray(obj.data)) return obj.data as AuditRow[];
  }
  return [];
};

const formatDateTimeInput = (value: string): string => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toISOString();
};

export const AuditLogsPage = () => {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [action, setAction] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [exportNotice, setExportNotice] = useState('');

  const loadAudit = async () => {
    setStatus('loading');
    setErrorMessage('');
    setExportNotice('');
    try {
      const params: Record<string, string> = {};
      if (action.trim()) params.action_type = action.trim();
      if (start) params.start_ts = formatDateTimeInput(start);
      if (end) params.end_ts = formatDateTimeInput(end);
      const response = await CoreApi.auditLogs(params);
      setRows(normalizeAuditRows(response.data));
      setStatus('ready');
    } catch (error: any) {
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Unable to load audit logs');
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadAudit();
  }, []);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) => {
      const haystack = `${row.id} ${row.action || ''} ${row.message || ''} ${row.actor || ''} ${row.resource || ''} ${row.ts || ''}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [rows, query]);

  const exportAudit = async () => {
    setExportNotice('');
    try {
      const response = await CoreApi.exportAudit({
        start_ts: formatDateTimeInput(start) || '1970-01-01T00:00:00Z',
        end_ts: formatDateTimeInput(end) || new Date().toISOString(),
        action_type: action || undefined,
        redaction_profile: 'standard',
      });
      const path = (response.data as Record<string, unknown>)?.path;
      setExportNotice(path ? `Export generated: ${String(path)}` : 'Export requested successfully.');
    } catch (error: any) {
      setExportNotice(error?.response?.data?.detail || error?.message || 'Audit export failed');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        subtitle="Explore and export control-plane audit events with action and time filtering."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadAudit()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={() => void exportAudit()}>
              <FiDownload className="mr-2 text-sm" />
              Export
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_220px_220px_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search action, message, actor"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <input
            className="input h-11"
            placeholder="Action Type"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />

          <input
            className="input h-11"
            type="datetime-local"
            value={start}
            onChange={(event) => setStart(event.target.value)}
          />

          <div className="flex items-center gap-2">
            <input
              className="input h-11"
              type="datetime-local"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
            <button type="button" className="btn-secondary h-11" onClick={() => void loadAudit()}>
              <FiFilter className="mr-2 text-sm" />
              Apply
            </button>
          </div>
        </div>
        {exportNotice && (
          <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{exportNotice}</p>
        )}
      </Card>

      <Card title="Audit Event Stream" subtitle="Backend audit feed with resilient fallback parsing.">
        {status === 'loading' && <LoadingState title="Loading audit logs" description="Fetching latest audit events." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadAudit()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row, index) => `${row.id}-${index}`} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No audit events found"
            description="No audit event matched your current filters. Try clearing filters or expanding date range."
            actionLabel="Reload"
            onAction={() => void loadAudit()}
          />
        )}
      </Card>
    </div>
  );
};
