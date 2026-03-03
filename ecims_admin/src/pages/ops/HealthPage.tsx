import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { FleetHealthRow } from '../../types/adminOps';

const columns: DataTableColumn<FleetHealthRow>[] = [
  { key: 'hostname', header: 'Host' },
  { key: 'lastSeen', header: 'Last Seen' },
  { key: 'policyVersion', header: 'Policy Version' },
  { key: 'encryption', header: 'Encryption' },
  { key: 'mtls', header: 'mTLS' },
];

const filters = [
  {
    key: 'encryption',
    label: 'Encryption',
    options: [
      { label: 'All', value: 'all' },
      { label: 'Enabled', value: 'enabled' },
      { label: 'Disabled', value: 'disabled' },
    ],
  },
  {
    key: 'mtls',
    label: 'mTLS',
    options: [
      { label: 'All', value: 'all' },
      { label: 'Healthy', value: 'healthy' },
      { label: 'Degraded', value: 'degraded' },
    ],
  },
] as const;

const rows: FleetHealthRow[] = [];

export const HealthPage = () => {
  return (
    <OpsWorkspacePage<FleetHealthRow>
      title="Fleet Health"
      subtitle="Track endpoint freshness, policy drift, encryption posture, and mTLS trust status at fleet scale."
      primaryActionLabel="Run Health Scan"
      primaryActionDescription="Trigger a fleet-wide health posture evaluation job with policy drift signals."
      searchPlaceholder="Search host, policy version, status"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row, index) => `${row.hostname}-${index}`}
      emptyStateTitle="Fleet health data unavailable"
      emptyStateDescription="Health explorer is ready for endpoint heartbeat and policy state ingestion in upcoming phases."
    />
  );
};

