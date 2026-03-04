import { useEffect, useMemo, useState } from 'react';
import { FiKey, FiRefreshCw, FiSearch, FiTrash2, FiUserPlus, FiUserX } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack, type ToastItem } from '../../components/ui/Toast';
import { useAuth } from '../../store/AuthContext';
import type { AdminUserCreatePayload, User } from '../../types';

type Role = 'ADMIN' | 'ANALYST' | 'VIEWER';

const roleOptions: Role[] = ['ADMIN', 'ANALYST', 'VIEWER'];

const defaultCreateForm: AdminUserCreatePayload = {
  username: '',
  password: '',
  role: 'ANALYST',
  is_active: true,
  must_reset_password: true,
};

export const AdminUsersPage = () => {
  const { user: currentUser } = useAuth();

  const [rows, setRows] = useState<User[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<AdminUserCreatePayload>(defaultCreateForm);
  const [createBusy, setCreateBusy] = useState(false);

  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetMustReset, setResetMustReset] = useState(true);
  const [resetBusy, setResetBusy] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [actionBusyUserId, setActionBusyUserId] = useState<number | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 3600);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  };

  const loadUsers = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listUsers(true);
      setRows(response.data);
      setStatus('ready');
    } catch (error: any) {
      setErrorMessage(error?.response?.data?.detail || error?.message || 'Unable to load users');
      setStatus('error');
    }
  };

  useEffect(() => {
    void loadUsers();
  }, []);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return rows.filter((row) => {
      const matchesQuery =
        !normalizedQuery ||
        row.username.toLowerCase().includes(normalizedQuery) ||
        row.role.toLowerCase().includes(normalizedQuery);

      const matchesRole = roleFilter === 'all' || row.role === roleFilter;
      const rowStatus = row.is_active ? 'active' : 'disabled';
      const matchesStatus = statusFilter === 'all' || rowStatus === statusFilter;

      return matchesQuery && matchesRole && matchesStatus;
    });
  }, [rows, query, roleFilter, statusFilter]);

  const updateRole = async (target: User, role: Role) => {
    setActionBusyUserId(target.id);
    try {
      await CoreApi.updateUserRole(target.id, { role });
      setRows((prev) => prev.map((row) => (row.id === target.id ? { ...row, role } : row)));
      pushToast({ title: 'Role updated', tone: 'success' });
    } catch (error: any) {
      pushToast({
        title: 'Role update failed',
        description: error?.response?.data?.detail || error?.message || 'Request failed',
        tone: 'error',
      });
      await loadUsers();
    } finally {
      setActionBusyUserId(null);
    }
  };

  const toggleActive = async (target: User) => {
    setActionBusyUserId(target.id);
    try {
      await CoreApi.updateUserActive(target.id, {
        is_active: !target.is_active,
        reason: target.is_active ? 'Disabled from admin console' : 'Re-enabled from admin console',
      });
      setRows((prev) =>
        prev.map((row) => (row.id === target.id ? { ...row, is_active: !target.is_active } : row)),
      );
      pushToast({
        title: target.is_active ? 'User disabled' : 'User enabled',
        tone: 'success',
      });
    } catch (error: any) {
      pushToast({
        title: 'Status update failed',
        description: error?.response?.data?.detail || error?.message || 'Request failed',
        tone: 'error',
      });
      await loadUsers();
    } finally {
      setActionBusyUserId(null);
    }
  };

  const submitCreateUser = async () => {
    if (!createForm.username.trim()) {
      pushToast({ title: 'Username is required', tone: 'warning' });
      return;
    }
    if (createForm.password.length < 12) {
      pushToast({ title: 'Password must be at least 12 chars', tone: 'warning' });
      return;
    }

    setCreateBusy(true);
    try {
      const response = await CoreApi.createUser({
        ...createForm,
        username: createForm.username.trim(),
      });
      setRows((prev) => [...prev, response.data]);
      setCreateOpen(false);
      setCreateForm(defaultCreateForm);
      pushToast({ title: 'User created', tone: 'success' });
    } catch (error: any) {
      pushToast({
        title: 'Create user failed',
        description: error?.response?.data?.detail || error?.message || 'Request failed',
        tone: 'error',
      });
    } finally {
      setCreateBusy(false);
    }
  };

  const submitResetPassword = async () => {
    if (!resetTarget) return;
    if (resetPassword.length < 12) {
      pushToast({ title: 'Password must be at least 12 chars', tone: 'warning' });
      return;
    }

    setResetBusy(true);
    try {
      await CoreApi.resetUserPassword(resetTarget.id, {
        new_password: resetPassword,
        must_reset_password: resetMustReset,
        reason: 'Reset from admin console',
      });
      setRows((prev) =>
        prev.map((row) =>
          row.id === resetTarget.id ? { ...row, must_reset_password: resetMustReset } : row,
        ),
      );
      setResetTarget(null);
      setResetPassword('');
      setResetMustReset(true);
      pushToast({ title: 'Password reset issued', tone: 'success' });
    } catch (error: any) {
      pushToast({
        title: 'Reset password failed',
        description: error?.response?.data?.detail || error?.message || 'Request failed',
        tone: 'error',
      });
    } finally {
      setResetBusy(false);
    }
  };

  const submitDeleteUser = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    try {
      await CoreApi.deleteUser(deleteTarget.id, 'Deleted from admin console');
      setRows((prev) => prev.filter((row) => row.id !== deleteTarget.id));
      setDeleteTarget(null);
      pushToast({ title: 'User deleted', tone: 'success' });
    } catch (error: any) {
      pushToast({
        title: 'Delete failed',
        description: error?.response?.data?.detail || error?.message || 'Request failed',
        tone: 'error',
      });
    } finally {
      setDeleteBusy(false);
    }
  };

  const columns: DataTableColumn<User>[] = [
    { key: 'username', header: 'Username' },
    {
      key: 'role',
      header: 'Role',
      render: (row) => (
        <select
          value={row.role}
          disabled={actionBusyUserId === row.id}
          onChange={(event) => void updateRole(row, event.target.value as Role)}
          className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700 outline-none transition focus:border-cyan-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
        >
          {roleOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: 'is_active',
      header: 'Status',
      render: (row) => (
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
            row.is_active
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
              : 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
          }`}
        >
          {row.is_active ? 'Active' : 'Disabled'}
        </span>
      ),
    },
    {
      key: 'must_reset_password',
      header: 'Must Reset',
      render: (row) => (
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
          {row.must_reset_password ? 'Yes' : 'No'}
        </span>
      ),
    },
    {
      key: 'last_login_at',
      header: 'Last Login',
      render: (row) => (row.last_login_at ? new Date(row.last_login_at).toLocaleString() : 'Never'),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (row) => (
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary h-8 px-2 text-xs"
            onClick={() => void toggleActive(row)}
            disabled={actionBusyUserId === row.id || row.id === currentUser?.id}
            title={row.id === currentUser?.id ? 'Cannot disable own account' : undefined}
          >
            {row.is_active ? <FiUserX className="mr-1" /> : <FiRefreshCw className="mr-1" />}
            {row.is_active ? 'Disable' : 'Enable'}
          </button>
          <button
            type="button"
            className="btn-secondary h-8 px-2 text-xs"
            onClick={() => {
              setResetTarget(row);
              setResetPassword('');
              setResetMustReset(true);
            }}
          >
            <FiKey className="mr-1" />
            Reset
          </button>
          <button
            type="button"
            className="btn-secondary h-8 px-2 text-xs text-rose-600 dark:text-rose-400"
            onClick={() => setDeleteTarget(row)}
            disabled={row.id === currentUser?.id}
            title={row.id === currentUser?.id ? 'Cannot delete own account' : undefined}
          >
            <FiTrash2 className="mr-1" />
            Delete
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Users"
        subtitle="Manage identity lifecycle, role assignments, password resets, and account status controls."
        action={
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" onClick={() => void loadUsers()}>
              <FiRefreshCw className="mr-2 text-sm" />
              Refresh
            </button>
            <button type="button" className="btn-primary" onClick={() => setCreateOpen(true)}>
              <FiUserPlus className="mr-2 text-sm" />
              Create User
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search username or role"
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          <select
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value)}
            className="h-11 min-w-[180px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Roles</option>
            <option value="ADMIN">ADMIN</option>
            <option value="ANALYST">ANALYST</option>
            <option value="VIEWER">VIEWER</option>
          </select>

          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="h-11 min-w-[180px] rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
        </div>
      </Card>

      <Card title="User Directory" subtitle="All control-plane users with RBAC and lifecycle controls.">
        {status === 'loading' && <LoadingState title="Loading users" description="Fetching identity records." />}
        {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadUsers()} />}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={(row) => String(row.id)} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title="No users found"
            description="No identity record matched your current query/filter settings."
            actionLabel="Reload"
            onAction={() => void loadUsers()}
          />
        )}
      </Card>

      <Modal
        open={createOpen}
        title="Create User"
        description="Create a new user with secure defaults and role-based access."
        confirmLabel={createBusy ? 'Creating...' : 'Create User'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (createBusy) return;
          setCreateOpen(false);
          setCreateForm(defaultCreateForm);
        }}
        onConfirm={() => void submitCreateUser()}
      >
        <div className="space-y-3">
          <input
            className="input"
            placeholder="Username"
            value={createForm.username}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, username: event.target.value }))}
          />
          <input
            className="input"
            type="password"
            placeholder="Temporary Password"
            value={createForm.password}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, password: event.target.value }))}
          />
          <select
            className="input"
            value={createForm.role}
            onChange={(event) => setCreateForm((prev) => ({ ...prev, role: event.target.value as Role }))}
          >
            {roleOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={createForm.is_active}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, is_active: event.target.checked }))}
            />
            User is active
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={createForm.must_reset_password}
              onChange={(event) =>
                setCreateForm((prev) => ({ ...prev, must_reset_password: event.target.checked }))
              }
            />
            Force password reset on next login
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(resetTarget)}
        title={resetTarget ? `Reset Password · ${resetTarget.username}` : 'Reset Password'}
        description="Set a temporary password and optionally require forced rotation at next login."
        confirmLabel={resetBusy ? 'Resetting...' : 'Reset Password'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (resetBusy) return;
          setResetTarget(null);
          setResetPassword('');
          setResetMustReset(true);
        }}
        onConfirm={() => void submitResetPassword()}
      >
        <div className="space-y-3">
          <input
            className="input"
            type="password"
            placeholder="New temporary password"
            value={resetPassword}
            onChange={(event) => setResetPassword(event.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={resetMustReset}
              onChange={(event) => setResetMustReset(event.target.checked)}
            />
            Require password reset on next login
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title={deleteTarget ? `Delete User · ${deleteTarget.username}` : 'Delete User'}
        description="This permanently removes the account. This action is audited."
        confirmLabel={deleteBusy ? 'Deleting...' : 'Delete User'}
        cancelLabel="Cancel"
        onCancel={() => {
          if (deleteBusy) return;
          setDeleteTarget(null);
        }}
        onConfirm={() => void submitDeleteUser()}
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Confirm deletion only if this identity is no longer needed.
        </p>
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
