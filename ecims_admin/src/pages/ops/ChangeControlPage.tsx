import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { ChangeControlRow } from '../../types/adminOps';

const columns: DataTableColumn<ChangeControlRow>[] = [
  { key: 'id', header: 'Request ID' },
  { key: 'policyName', header: 'Policy' },
  { key: 'requestedBy', header: 'Requested By' },
  { key: 'approvalState', header: 'Approval State' },
  { key: 'requestedAt', header: 'Requested At' },
];

const filters = [
  {
    key: 'approvalState',
    label: 'Approval State',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'Pending', value: 'pending' },
      { label: 'Approved', value: 'approved' },
      { label: 'Rejected', value: 'rejected' },
    ],
  },
] as const;

const rows: ChangeControlRow[] = [];

export const ChangeControlPage = () => {
  return (
    <OpsWorkspacePage<ChangeControlRow>
      title="Change Control"
      subtitle="Enforce approval workflows and two-person rule before high-risk policy mutations."
      primaryActionLabel="Submit Change"
      primaryActionDescription="Submit a policy change request with justification, reviewers, and compliance metadata."
      searchPlaceholder="Search request ID, policy, requester"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No pending changes"
      emptyStateDescription="Change-control panel is ready for approval chain APIs and two-person rule enforcement in Phase 8."
    />
  );
};

