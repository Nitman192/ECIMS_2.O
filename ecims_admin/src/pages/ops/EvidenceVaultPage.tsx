import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { EvidenceItemRow } from '../../types/adminOps';

const columns: DataTableColumn<EvidenceItemRow>[] = [
  { key: 'id', header: 'Evidence ID' },
  { key: 'hash', header: 'Hash' },
  { key: 'source', header: 'Source' },
  { key: 'custodyState', header: 'Custody State' },
  { key: 'capturedAt', header: 'Captured At' },
];

const filters = [
  {
    key: 'custodyState',
    label: 'Custody',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'Sealed', value: 'sealed' },
      { label: 'In Review', value: 'in_review' },
    ],
  },
] as const;

const rows: EvidenceItemRow[] = [];

export const EvidenceVaultPage = () => {
  return (
    <OpsWorkspacePage<EvidenceItemRow>
      title="Evidence Vault"
      subtitle="Manage immutable evidence objects and chain-of-custody timelines with integrity-first controls."
      primaryActionLabel="Register Evidence"
      primaryActionDescription="Register an evidence object with source metadata, checksum, and custody attestations."
      searchPlaceholder="Search evidence ID, hash, source"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No evidence entries"
      emptyStateDescription="Evidence vault UI is ready for append-only object integration and manifest signing in Phase 7."
    />
  );
};

