import { useEffect, useMemo, useState } from 'react';
import { FiRefreshCw, FiSearch } from 'react-icons/fi';
import { CoreApi } from '../api/services';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';
import type { Alert } from '../types';

const columns: DataTableColumn<Alert>[] = [
  { key: 'id', header: 'ID' },
  {
    key: 'severity',
    header: 'Severity',
    render: (row) => {
      const tone =
        row.severity === 'RED'
          ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
          : row.severity === 'YELLOW'
            ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
            : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
      return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>{row.severity}</span>;
    },
  },
  { key: 'alert_type', header: 'Type' },
  { key: 'message', header: 'Message' },
  { key: 'ts', header: 'Timestamp' },
  { key: 'status', header: 'Status' },
];

const normalizeAlerts = (payload: unknown): Alert[] => {
  if (Array.isArray(payload)) return payload as Alert[];
  if (payload && typeof payload === 'object') {
    const obj = payload as Record<string, unknown>;
    if (Array.isArray(obj.results)) return obj.results as Alert[];
    if (Array.isArray(obj.items)) return obj.items as Alert[];
    if (Array.isArray(obj.data)) return obj.data as Alert[];
  }
  return [];
};

export const AlertsPage = () => {
  const [rows, setRows] = useState<Alert[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [query, setQuery] = useState('');
  const [severity, setSeverity] = useState('all');

  const loadAlerts = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.alerts();
      setRows(normalizeAlerts(response.data));
      setStatus('ready');
    } catch (error: any) {
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Unable to load alerts');
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadAlerts();
  }, []);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesSearch =
        !q ||
        row.alert_type.toLowerCase().includes(q) ||
        row.message.toLowerCase().includes(q) ||
        row.status.toLowerCase().includes(q);
      const matchesSeverity =
        severity === 'all' || row.severity.toLowerCase() === severity.toLowerCase();
      return matchesSearch && matchesSeverity;
    });
  }, [rows, query, severity]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alerts"
        subtitle="Review and triage security alerts from connected endpoints."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadAlerts()}>
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
              placeholder="Search type, message, status"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            className="h-11 min-w-[180px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Severity</option>
            <option value="red">Red</option>
            <option value="yellow">Yellow</option>
            <option value="green">Green</option>
          </select>
        </div>
      </Card>

      <Card title="Alert Stream" subtitle="Latest alert feed with search and severity filtering.">
        {status === 'loading' && <LoadingState title="Loading alerts" description="Fetching latest alert stream." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadAlerts()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No alerts found"
            description="No alert matched your current search/filter. Try broadening filters or refresh."
            actionLabel="Reload"
            onAction={() => void loadAlerts()}
          />
        )}
      </Card>
    </div>
  );
};
