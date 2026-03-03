import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { PlaybookRow } from '../../types/adminOps';

const columns: DataTableColumn<PlaybookRow>[] = [
  { key: 'id', header: 'Playbook ID' },
  { key: 'name', header: 'Name' },
  { key: 'trigger', header: 'Trigger' },
  { key: 'approvalMode', header: 'Approval Mode' },
  { key: 'updatedAt', header: 'Updated At' },
];

const filters = [
  {
    key: 'approvalMode',
    label: 'Approval',
    options: [
      { label: 'All Modes', value: 'all' },
      { label: 'Manual', value: 'manual' },
      { label: 'Auto', value: 'auto' },
    ],
  },
] as const;

const rows: PlaybookRow[] = [];

export const PlaybooksPage = () => {
  return (
    <OpsWorkspacePage<PlaybookRow>
      title="Playbooks"
      subtitle="Create repeatable, one-click incident actions that reduce operator response friction."
      primaryActionLabel="Create Playbook"
      primaryActionDescription="Create a playbook template with trigger conditions, approvals, and rollback blocks."
      searchPlaceholder="Search playbook, trigger, approval mode"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No playbooks defined"
      emptyStateDescription="Playbook automation workspace is scaffolded for backend template and execution APIs in Phase 8."
    />
  );
};

