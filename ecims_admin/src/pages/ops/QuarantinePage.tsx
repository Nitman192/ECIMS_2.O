import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { QuarantineCaseRow } from '../../types/adminOps';

const columns: DataTableColumn<QuarantineCaseRow>[] = [
  { key: 'caseId', header: 'Case ID' },
  { key: 'host', header: 'Host' },
  { key: 'trigger', header: 'Trigger' },
  { key: 'state', header: 'State' },
  { key: 'updatedAt', header: 'Updated At' },
];

const filters = [
  {
    key: 'state',
    label: 'State',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'Isolated', value: 'isolated' },
      { label: 'Pending Release', value: 'pending_release' },
    ],
  },
] as const;

const rows: QuarantineCaseRow[] = [];

export const QuarantinePage = () => {
  return (
    <OpsWorkspacePage<QuarantineCaseRow>
      title="Quarantine"
      subtitle="Operate reversible host or network isolation with guardrails, approvals, and traceability."
      primaryActionLabel="Start Isolation"
      primaryActionDescription="Launch a quarantine workflow for selected assets with staged release criteria."
      searchPlaceholder="Search case ID, host, trigger"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.caseId}
      emptyStateTitle="No quarantine cases"
      emptyStateDescription="Isolation control plane is scaffolded. Backend reversible action orchestration will be added in future phases."
    />
  );
};

