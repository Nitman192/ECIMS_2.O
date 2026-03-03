import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { BreakGlassSessionRow } from '../../types/adminOps';

const columns: DataTableColumn<BreakGlassSessionRow>[] = [
  { key: 'id', header: 'Session ID' },
  { key: 'actor', header: 'Actor' },
  { key: 'reason', header: 'Reason' },
  { key: 'expiresAt', header: 'Expires At' },
  { key: 'state', header: 'State' },
];

const filters = [
  {
    key: 'state',
    label: 'State',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'Active', value: 'active' },
      { label: 'Expired', value: 'expired' },
    ],
  },
] as const;

const rows: BreakGlassSessionRow[] = [];

export const BreakGlassPage = () => {
  return (
    <OpsWorkspacePage<BreakGlassSessionRow>
      title="Break Glass"
      subtitle="Govern emergency access with strict time bounds, reason capture, and forced re-authentication."
      primaryActionLabel="Request Emergency Access"
      primaryActionDescription="Start a break-glass session request with explicit reason and approval policy checks."
      searchPlaceholder="Search session ID, actor, reason"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No emergency sessions"
      emptyStateDescription="Break-glass workflow is scaffolded. Time-bound token enforcement and extra audit linkage will be wired in Phase 8."
    />
  );
};

