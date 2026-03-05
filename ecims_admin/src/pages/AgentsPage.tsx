import { useEffect, useMemo, useState } from 'react';
import { FiRefreshCw, FiSearch } from 'react-icons/fi';
import { CoreApi } from '../api/services';
import { getApiErrorMessage, normalizeListResponse } from '../api/utils';
import { DataTable, type DataTableColumn } from '../components/DataTable';
import { Card } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';
import type { Agent } from '../types';

const columns: DataTableColumn<Agent>[] = [
  { key: 'id', header: 'ID' },
  { key: 'hostname', header: 'Hostname' },
  {
    key: 'name',
    header: 'Name',
    render: (row) => row.name || '-',
  },
  {
    key: 'device_mode_override',
    header: 'Mode',
    render: (row) => row.device_mode_override || 'default',
  },
  { key: 'last_seen', header: 'Last Seen' },
  {
    key: 'status',
    header: 'Status',
    render: (row) => (
      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
        {row.status}
      </span>
    ),
  },
];

export const AgentsPage = () => {
  const [rows, setRows] = useState<Agent[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const loadAgents = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.agents();
      setRows(normalizeListResponse<Agent>(response.data));
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load agents'));
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadAgents();
  }, []);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesSearch =
        !q ||
        row.hostname.toLowerCase().includes(q) ||
        (row.name || '').toLowerCase().includes(q) ||
        row.status.toLowerCase().includes(q);
      const matchesStatus = statusFilter === 'all' || row.status.toLowerCase() === statusFilter.toLowerCase();
      return matchesSearch && matchesStatus;
    });
  }, [rows, query, statusFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        subtitle="Monitor and inspect enrolled endpoint agents across your fleet."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadAgents()}>
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
              placeholder="Search hostname, name, status"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 min-w-[180px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="online">Online</option>
            <option value="offline">Offline</option>
            <option value="isolated">Isolated</option>
          </select>
        </div>
      </Card>

      <Card title="Agent Inventory" subtitle="Live endpoint agent records from backend API.">
        {status === 'loading' && <LoadingState title="Loading agents" description="Fetching latest agent inventory." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadAgents()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No agents found"
            description="No agent matched your current search/filter. Try clearing filters or enrolling new endpoints."
            actionLabel="Reload"
            onAction={() => void loadAgents()}
          />
        )}
      </Card>
    </div>
  );
};
