import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { EnrollmentTokenRow } from '../../types/adminOps';

const columns: DataTableColumn<EnrollmentTokenRow>[] = [
  { key: 'id', header: 'Token ID' },
  { key: 'mode', header: 'Mode' },
  { key: 'expiresAt', header: 'Expires At' },
  { key: 'remainingUses', header: 'Remaining Uses' },
  { key: 'createdBy', header: 'Created By' },
];

const filters = [
  {
    key: 'mode',
    label: 'Mode',
    options: [
      { label: 'All Modes', value: 'all' },
      { label: 'Online', value: 'online' },
      { label: 'Offline', value: 'offline' },
    ],
  },
] as const;

const rows: EnrollmentTokenRow[] = [];

export const EnrollmentPage = () => {
  return (
    <OpsWorkspacePage<EnrollmentTokenRow>
      title="Enrollment"
      subtitle="Manage token-based enrollment for connected and air-gapped deployments with lifecycle controls."
      primaryActionLabel="Generate Token"
      primaryActionDescription="Generate an enrollment token or offline kit bundle with expiry and usage limits."
      searchPlaceholder="Search token ID, mode, creator"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No enrollment tokens"
      emptyStateDescription="Enrollment workflows are scaffolded and ready for token + offline kit API integration in Phase 6."
    />
  );
};

