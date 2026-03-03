import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { RbacMatrixRow } from '../../types/adminOps';

const columns: DataTableColumn<RbacMatrixRow>[] = [
  { key: 'role', header: 'Role' },
  { key: 'scope', header: 'Scope' },
  { key: 'permissions', header: 'Permissions' },
  { key: 'updatedAt', header: 'Updated At' },
];

const filters = [
  {
    key: 'scope',
    label: 'Scope',
    options: [
      { label: 'All Scopes', value: 'all' },
      { label: 'Admin', value: 'admin' },
      { label: 'Ops', value: 'ops' },
      { label: 'Read Only', value: 'readonly' },
    ],
  },
] as const;

const rows: RbacMatrixRow[] = [];

export const AdminRolesPage = () => {
  return (
    <OpsWorkspacePage<RbacMatrixRow>
      title="Roles & RBAC Matrix"
      subtitle="Inspect role permissions and scope boundaries before policy and workflow rollout."
      primaryActionLabel="Review Matrix"
      primaryActionDescription="Open RBAC matrix review workflow with compare and export controls."
      searchPlaceholder="Search role, permission, scope"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row, index) => `${row.role}-${row.scope}-${index}`}
      emptyStateTitle="RBAC matrix not loaded"
      emptyStateDescription="The RBAC matrix endpoint is pending Phase 2 integration. This workspace is ready for policy diff and access validation views."
    />
  );
};

