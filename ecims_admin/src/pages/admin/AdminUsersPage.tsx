import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { AdminUserRow } from '../../types/adminOps';

const columns: DataTableColumn<AdminUserRow>[] = [
  { key: 'username', header: 'Username' },
  { key: 'role', header: 'Role' },
  { key: 'status', header: 'Status' },
  { key: 'lastLogin', header: 'Last Login' },
];

const filters = [
  {
    key: 'role',
    label: 'Role',
    options: [
      { label: 'All Roles', value: 'all' },
      { label: 'ADMIN', value: 'admin' },
      { label: 'OPERATOR', value: 'operator' },
      { label: 'ANALYST', value: 'analyst' },
    ],
  },
  {
    key: 'status',
    label: 'Status',
    options: [
      { label: 'All Status', value: 'all' },
      { label: 'Active', value: 'active' },
      { label: 'Disabled', value: 'disabled' },
    ],
  },
] as const;

const rows: AdminUserRow[] = [];

export const AdminUsersPage = () => {
  return (
    <OpsWorkspacePage<AdminUserRow>
      title="Users"
      subtitle="Provision, deactivate, and govern operator identities across the control plane."
      primaryActionLabel="Create User"
      primaryActionDescription="Create a new control-plane user with role-scoped access and lifecycle policies."
      searchPlaceholder="Search by username, role, status"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No users available"
      emptyStateDescription="User inventory is empty in this environment. Connect /admin/users API in Phase 2 to enable CRUD, disable, and reset flows."
    />
  );
};

