import type { DataTableColumn } from '../../components/DataTable';
import { OpsWorkspacePage } from '../../components/ops/OpsWorkspacePage';
import type { MaintenanceScheduleRow } from '../../types/adminOps';

const columns: DataTableColumn<MaintenanceScheduleRow>[] = [
  { key: 'windowName', header: 'Window Name' },
  { key: 'timezone', header: 'Timezone' },
  { key: 'nextRun', header: 'Next Run' },
  { key: 'state', header: 'State' },
];

const filters = [
  {
    key: 'state',
    label: 'State',
    options: [
      { label: 'All States', value: 'all' },
      { label: 'Draft', value: 'draft' },
      { label: 'Active', value: 'active' },
      { label: 'Paused', value: 'paused' },
    ],
  },
  {
    key: 'timezone',
    label: 'Timezone',
    options: [
      { label: 'All Timezones', value: 'all' },
      { label: 'UTC', value: 'utc' },
      { label: 'Asia/Kolkata', value: 'asia/kolkata' },
      { label: 'America/New_York', value: 'america/new_york' },
    ],
  },
] as const;

const rows: MaintenanceScheduleRow[] = [];

export const SchedulesPage = () => {
  return (
    <OpsWorkspacePage<MaintenanceScheduleRow>
      title="Maintenance Schedules"
      subtitle="Plan safe shutdown/start orchestration windows with conflict awareness and staged execution."
      primaryActionLabel="Create Schedule"
      primaryActionDescription="Create a maintenance window with safe shutdown/start sequence and health checks."
      searchPlaceholder="Search window name, timezone, state"
      filters={filters.map((item) => ({ ...item, options: [...item.options] }))}
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      emptyStateTitle="No maintenance windows"
      emptyStateDescription="Scheduling UI is ready. Runner, conflict detection, and next-run preview wiring will land in Phase 5."
    />
  );
};

