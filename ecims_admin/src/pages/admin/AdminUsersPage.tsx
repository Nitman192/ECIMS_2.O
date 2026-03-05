import { useEffect, useMemo, useState } from 'react';
import { FiKey, FiRefreshCw, FiSearch, FiTrash2, FiUserPlus, FiUserX } from 'react-icons/fi';
import { CoreApi } from '../../api/services';
import { getApiErrorMessage } from '../../api/utils';
import { useToastStack } from '../../hooks/useToastStack';
import { DataTable, type DataTableColumn } from '../../components/DataTable';
import { Card } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { Modal } from '../../components/ui/Modal';
import { PageHeader } from '../../components/ui/PageHeader';
import { ToastStack } from '../../components/ui/Toast';
import { useAuth } from '../../store/AuthContext';
import type { AdminUserCreatePayload, User } from '../../types';

type Role = 'ADMIN' | 'ANALYST' | 'VIEWER';

type CreateValidationErrors = {
  username?: string;
  password?: string;
};

const roleOptions: Role[] = ['ADMIN', 'ANALYST', 'VIEWER'];

const defaultCreateForm: AdminUserCreatePayload = {
  username: '',
  password: '',
  role: 'ANALYST',
  is_active: true,
  must_reset_password: true,
};

const USERNAME_PATTERN = /^[a-zA-Z0-9._-]{3,64}$/;
const PASSWORD_MIN_LENGTH = 12;

const validateUsername = (username: string): string | null => {
  if (!username) return 'Username is required.';
  if (!USERNAME_PATTERN.test(username)) {
    return 'Username must be 3-64 chars and use only letters, numbers, dot, underscore, or hyphen.';
  }
  return null;
};

const validateTemporaryPassword = (password: string): string | null => {
  if (password.length < PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) {
    return 'Password must include at least one letter and one number.';
  }
  return null;
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
  const [createErrors, setCreateErrors] = useState<CreateValidationErrors>({});

  const [resetTarget, setResetTarget] = useState<User | null>(null);
  const [resetPassword, setResetPassword] = useState('');
  const [resetMustReset, setResetMustReset] = useState(true);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [actionBusyUserId, setActionBusyUserId] = useState<number | null>(null);
  const { toasts, pushToast, dismissToast } = useToastStack({ durationMs: 3600 });

  const loadUsers = async () => {
    setStatus('loading');
    setErrorMessage('');
    try {
      const response = await CoreApi.listUsers(true);
      setRows(response.data);
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load users'));
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

  const openCreateModal = () => {
    setCreateForm(defaultCreateForm);
    setCreateErrors({});
    setCreateOpen(true);
  };

  const openResetModal = (target: User) => {
    setResetTarget(target);
    setResetPassword('');
    setResetMustReset(true);
    setResetError(null);
  };

  const openDeleteModal = (target: User) => {
    setDeleteTarget(target);
    setDeleteConfirmText('');
    setDeleteError(null);
  };

  const closeCreateModal = () => {
    if (createBusy) return;
    setCreateOpen(false);
    setCreateForm(defaultCreateForm);
    setCreateErrors({});
  };

  const closeResetModal = () => {
    if (resetBusy) return;
    setResetTarget(null);
    setResetPassword('');
    setResetMustReset(true);
    setResetError(null);
  };

  const closeDeleteModal = () => {
    if (deleteBusy) return;
    setDeleteTarget(null);
    setDeleteConfirmText('');
    setDeleteError(null);
  };

  const updateRole = async (target: User, role: Role) => {
    if (target.role === role) return;

    setActionBusyUserId(target.id);
    try {
      await CoreApi.updateUserRole(target.id, { role });
      setRows((prev) => prev.map((row) => (row.id === target.id ? { ...row, role } : row)));
      pushToast({ title: 'Role updated', tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'Role update failed',
        description: getApiErrorMessage(error, 'Request failed'),
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
    } catch (error: unknown) {
      pushToast({
        title: 'Status update failed',
        description: getApiErrorMessage(error, 'Request failed'),
        tone: 'error',
      });
      await loadUsers();
    } finally {
      setActionBusyUserId(null);
    }
  };

  const submitCreateUser = async () => {
    const normalizedUsername = createForm.username.trim();
    const nextErrors: CreateValidationErrors = {};

    const usernameError = validateUsername(normalizedUsername);
    if (usernameError) {
      nextErrors.username = usernameError;
    }

    const passwordError = validateTemporaryPassword(createForm.password);
    if (passwordError) {
      nextErrors.password = passwordError;
    }

    setCreateErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      pushToast({
        title: 'Validation failed',
        description: 'Fix highlighted fields before creating user.',
        tone: 'warning',
      });
      return;
    }

    setCreateBusy(true);
    try {
      const response = await CoreApi.createUser({
        ...createForm,
        username: normalizedUsername,
      });
      setRows((prev) => [...prev, response.data]);
      setCreateOpen(false);
      setCreateForm(defaultCreateForm);
      setCreateErrors({});
      pushToast({ title: 'User created', tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'Create user failed',
        description: getApiErrorMessage(error, 'Request failed'),
        tone: 'error',
      });
    } finally {
      setCreateBusy(false);
    }
  };

  const submitResetPassword = async () => {
    if (!resetTarget) return;

    const passwordError = validateTemporaryPassword(resetPassword);
    setResetError(passwordError);
    if (passwordError) {
      pushToast({
        title: 'Validation failed',
        description: passwordError,
        tone: 'warning',
      });
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
      setResetError(null);
      pushToast({ title: 'Password reset issued', tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'Reset password failed',
        description: getApiErrorMessage(error, 'Request failed'),
        tone: 'error',
      });
    } finally {
      setResetBusy(false);
    }
  };

  const submitDeleteUser = async () => {
    if (!deleteTarget) return;

    if (deleteConfirmText.trim() !== deleteTarget.username) {
      const message = 'Type the exact username to confirm deletion.';
      setDeleteError(message);
      pushToast({ title: 'Delete confirmation required', description: message, tone: 'warning' });
      return;
    }

    setDeleteBusy(true);
    try {
      await CoreApi.deleteUser(deleteTarget.id, 'Deleted from admin console');
      setRows((prev) => prev.filter((row) => row.id !== deleteTarget.id));
      setDeleteTarget(null);
      setDeleteConfirmText('');
      setDeleteError(null);
      pushToast({ title: 'User deleted', tone: 'success' });
    } catch (error: unknown) {
      pushToast({
        title: 'Delete failed',
        description: getApiErrorMessage(error, 'Request failed'),
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
          disabled={actionBusyUserId === row.id || row.id === currentUser?.id}
          onChange={(event) => void updateRole(row, event.target.value as Role)}
          className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-700 outline-none transition focus:border-cyan-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
          title={row.id === currentUser?.id ? 'Cannot change own role in this view' : undefined}
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
            onClick={() => openResetModal(row)}
          >
            <FiKey className="mr-1" />
            Reset
          </button>
          <button
            type="button"
            className="btn-secondary h-8 px-2 text-xs text-rose-600 dark:text-rose-400"
            onClick={() => openDeleteModal(row)}
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
            <button type="button" className="btn-primary" onClick={openCreateModal}>
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
        confirmDisabled={createBusy}
        cancelLabel="Cancel"
        cancelDisabled={createBusy}
        onCancel={closeCreateModal}
        onConfirm={() => void submitCreateUser()}
      >
        <div className="space-y-3">
          <div>
            <input
              className="input"
              placeholder="Username"
              autoComplete="username"
              value={createForm.username}
              disabled={createBusy}
              onChange={(event) => {
                const value = event.target.value;
                setCreateForm((prev) => ({ ...prev, username: value }));
                if (createErrors.username) {
                  setCreateErrors((prev) => ({ ...prev, username: undefined }));
                }
              }}
            />
            {createErrors.username && (
              <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{createErrors.username}</p>
            )}
          </div>

          <div>
            <input
              className="input"
              type="password"
              placeholder="Temporary Password"
              autoComplete="new-password"
              value={createForm.password}
              disabled={createBusy}
              onChange={(event) => {
                const value = event.target.value;
                setCreateForm((prev) => ({ ...prev, password: value }));
                if (createErrors.password) {
                  setCreateErrors((prev) => ({ ...prev, password: undefined }));
                }
              }}
            />
            {createErrors.password && (
              <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{createErrors.password}</p>
            )}
          </div>

          <select
            className="input"
            value={createForm.role}
            disabled={createBusy}
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
              disabled={createBusy}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, is_active: event.target.checked }))}
            />
            User is active
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={createForm.must_reset_password}
              disabled={createBusy}
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
        title={resetTarget ? `Reset Password - ${resetTarget.username}` : 'Reset Password'}
        description="Set a temporary password and optionally require forced rotation at next login."
        confirmLabel={resetBusy ? 'Resetting...' : 'Reset Password'}
        confirmDisabled={resetBusy}
        cancelLabel="Cancel"
        cancelDisabled={resetBusy}
        onCancel={closeResetModal}
        onConfirm={() => void submitResetPassword()}
      >
        <div className="space-y-3">
          <div>
            <input
              className="input"
              type="password"
              placeholder="New temporary password"
              autoComplete="new-password"
              value={resetPassword}
              disabled={resetBusy}
              onChange={(event) => {
                setResetPassword(event.target.value);
                if (resetError) setResetError(null);
              }}
            />
            {resetError && <p className="mt-1 text-xs text-rose-600 dark:text-rose-400">{resetError}</p>}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={resetMustReset}
              disabled={resetBusy}
              onChange={(event) => setResetMustReset(event.target.checked)}
            />
            Require password reset on next login
          </label>
        </div>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title={deleteTarget ? `Delete User - ${deleteTarget.username}` : 'Delete User'}
        description="This permanently removes the account. This action is audited."
        confirmLabel={deleteBusy ? 'Deleting...' : 'Delete User'}
        confirmDisabled={deleteBusy}
        cancelLabel="Cancel"
        cancelDisabled={deleteBusy}
        onCancel={closeDeleteModal}
        onConfirm={() => void submitDeleteUser()}
      >
        <div className="space-y-3">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Confirm deletion by typing <span className="font-semibold">{deleteTarget?.username}</span> below.
          </p>
          <input
            className="input"
            value={deleteConfirmText}
            disabled={deleteBusy}
            onChange={(event) => {
              setDeleteConfirmText(event.target.value);
              if (deleteError) setDeleteError(null);
            }}
            placeholder="Type username to confirm"
          />
          {deleteError && <p className="text-xs text-rose-600 dark:text-rose-400">{deleteError}</p>}
        </div>
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};
