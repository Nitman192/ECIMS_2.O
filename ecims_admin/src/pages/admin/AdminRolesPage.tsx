import { useEffect, useMemo, useState } from 'react';
import { FiRefreshCw, FiSearch } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { PageHeader } from '../../components/ui/PageHeader';
import type { RoleMatrixEntry } from '../../types';

const columns: DataTableColumn<RoleMatrixEntry>[] = [
  { key: 'role', header: 'Role' },
  {
    key: 'scope',
    header: 'Scope',
    render: (row) => (
      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-200">
        {row.scope}
      </span>
    ),
  },
  {
    key: 'permission_count',
    header: 'Permissions',
    render: (row) => (
      <div className="space-y-1">
        <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">{row.permission_count} permissions</p>
        <p className="max-w-[520px] truncate text-xs text-slate-500 dark:text-slate-400" title={row.permissions.join(', ')}>
          {row.permissions.join(', ')}
        </p>
      </div>
    ),
  },
  {
    key: 'active_users',
    header: 'User Coverage',
    render: (row) => (
      <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
        {row.active_users} active / {row.total_users} total
      </span>
    ),
  },
  {
    key: 'updated_at',
    header: 'Updated At',
    render: (row) => (row.updated_at ? new Date(row.updated_at).toLocaleString() : '-'),
  },
];

export const AdminRolesPage = () => {
  const [rows, setRows] = useState<RoleMatrixEntry[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [query, setQuery] = useState('');
  const [scopeFilter, setScopeFilter] = useState('all');

  const loadMatrix = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.rolesMatrix();
      setRows(response.data);
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load role matrix'));
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadMatrix();
  }, []);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesQuery =
        !q ||
        row.role.toLowerCase().includes(q) ||
        row.scope.toLowerCase().includes(q) ||
        row.permissions.some((permission) => permission.toLowerCase().includes(q));
      const matchesScope = scopeFilter === 'all' || row.scope.toLowerCase() === scopeFilter.toLowerCase();
      return matchesQuery && matchesScope;
    });
  }, [rows, query, scopeFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Roles & RBAC Matrix"
        subtitle="Inspect role boundaries, permission bundles, and active user coverage before privilege-sensitive rollout."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadMatrix()}>
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
              placeholder="Search role, scope, permission"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={scopeFilter}
            onChange={(event) => setScopeFilter(event.target.value)}
            className="h-11 min-w-[220px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Scopes</option>
            <option value="CONTROL_PLANE">CONTROL_PLANE</option>
            <option value="OPERATIONS">OPERATIONS</option>
            <option value="READ_ONLY">READ_ONLY</option>
          </select>
        </div>
      </Card>

      <Card title="RBAC Matrix" subtitle="Server-backed role model with live user coverage counts.">
        {status === 'loading' && <LoadingState title="Loading RBAC matrix" description="Fetching roles and permission bundles." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadMatrix()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row) => `${row.role}-${row.scope}`} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No RBAC rows found"
            description="Current search/filter did not match any role matrix rows."
            actionLabel="Reload"
            onAction={() => void loadMatrix()}
          />
        )}
      </Card>
    </div>
  );
};
