import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { RemoteActionTaskRow } from '../../types/adminOps';

const columns: DataTableColumn<RemoteActionTaskRow>[] = [
  { key: 'id', header: 'Task ID' },
  { key: 'action', header: 'Action' },
  { key: 'targetCount', header: 'Target Count' },
  { key: 'status', header: 'Status' },
  { key: 'createdAt', header: 'Created At' },
];

const filters = [
  {
    key: 'action',
    label: 'Action',
    options: [
      { label: 'All Actions', value: 'all' },
      { label: 'Shutdown', value: 'shutdown' },
      { label: 'Restart', value: 'restart' },
      { label: 'Lockdown', value: 'lockdown' },
      { label: 'Policy Push', value: 'policy-push' },
    ],
  },
  {
    key: 'status',
    label: 'Status',
    options: [
      { label: 'All Status', value: 'all' },
      { label: 'PENDING', value: 'pending' },
      { label: 'SENT', value: 'sent' },
      { label: 'ACK', value: 'ack' },
      { label: 'DONE', value: 'done' },
      { label: 'FAILED', value: 'failed' },
    ],
  },
] as const;

const rows: RemoteActionTaskRow[] = [];

export const RemoteActionsPage = () => {
  return (
    <OpsWorkspacePage<RemoteActionTaskRow>
      title="Remote Actions"
      subtitle="Safely execute shutdown, restart, lockdown, and policy push tasks across endpoint cohorts."
      primaryActionLabel="Issue Action"
      primaryActionDescription="Create a new remote action task with batching, validation, and rollback safeguards."
      searchPlaceholder="Search task ID, action, status"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No remote action tasks"
      emptyStateDescription="Task queue UI is ready. Backend idempotent queue lifecycle will be connected in Phase 4."
    />
  );
};

