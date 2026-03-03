import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { FeatureFlagRow } from '../../types/adminOps';

const columns: DataTableColumn<FeatureFlagRow>[] = [
  { key: 'key', header: 'Flag Key' },
  { key: 'scope', header: 'Scope' },
  { key: 'state', header: 'State' },
  { key: 'risk', header: 'Risk Level' },
];

const filters = [
  {
    key: 'scope',
    label: 'Scope',
    options: [
      { label: 'All Scopes', value: 'all' },
      { label: 'Global', value: 'global' },
      { label: 'User', value: 'user' },
      { label: 'Agent', value: 'agent' },
    ],
  },
  {
    key: 'state',
    label: 'State',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'On', value: 'on' },
      { label: 'Off', value: 'off' },
    ],
  },
] as const;

const rows: FeatureFlagRow[] = [];

export const AdminFeaturesPage = () => {
  return (
    <OpsWorkspacePage<FeatureFlagRow>
      title="Feature Flags & Kill Switches"
      subtitle="Operate risk-gated toggles with reason codes and safe rollout controls."
      primaryActionLabel="Create Flag"
      primaryActionDescription="Create a new feature flag or emergency kill switch with scope and rollback defaults."
      searchPlaceholder="Search by flag key, scope, risk"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.key}
      emptyStateTitle="No feature controls configured"
      emptyStateDescription="Feature flag inventory will appear after backend rollout in Phase 3 with audit-required toggle workflows."
    />
  );
};

