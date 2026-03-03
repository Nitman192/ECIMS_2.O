import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { AuditEventRow } from '../../types/adminOps';

const columns: DataTableColumn<AuditEventRow>[] = [
  { key: 'id', header: 'Event ID' },
  { key: 'actor', header: 'Actor' },
  { key: 'action', header: 'Action' },
  { key: 'resource', header: 'Resource' },
  { key: 'timestamp', header: 'Timestamp' },
];

const filters = [
  {
    key: 'action',
    label: 'Action',
    options: [
      { label: 'All Actions', value: 'all' },
      { label: 'Create', value: 'create' },
      { label: 'Update', value: 'update' },
      { label: 'Delete', value: 'delete' },
      { label: 'Access', value: 'access' },
    ],
  },
  {
    key: 'resource',
    label: 'Resource',
    options: [
      { label: 'All Resources', value: 'all' },
      { label: 'Users', value: 'users' },
      { label: 'Policies', value: 'policies' },
      { label: 'Agents', value: 'agents' },
    ],
  },
] as const;

const rows: AuditEventRow[] = [];

export const AdminAuditExplorerPage = () => {
  return (
    <OpsWorkspacePage<AuditEventRow>
      title="Advanced Audit Explorer"
      subtitle="Query actor intent, approval trails, and control-plane state transitions with high-fidelity audit context."
      primaryActionLabel="Export Audit"
      primaryActionDescription="Generate a signed audit export package using current query filters and scope restrictions."
      searchPlaceholder="Search actor, event ID, resource"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No audit events yet"
      emptyStateDescription="Audit explorer is scaffolded and ready for /admin/audit backend binding with pagination and exports in Phase 2."
    />
  );
};

