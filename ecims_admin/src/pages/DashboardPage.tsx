// src/pages/DashboardPage.tsx
import { FiActivity, FiAlertCircle, FiPower, FiShield } from 'react-icons/fi';
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartCard } from '../components/ChartCard';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';

const stats = [
  {
    label: 'Active Agents',
    value: '1,284',
    trendLabel: '+4.8% vs last week',
    trend: 'up',
    icon: FiActivity,
  },
  {
    label: 'Open Alerts',
    value: '37',
    trendLabel: '-12.3% vs last week',
    trend: 'down',
    icon: FiAlertCircle,
  },
  {
    label: 'Kill Switch',
    value: 'Armed',
    trendLabel: 'No state changes',
    trend: 'neutral',
    icon: FiPower,
  },
  {
    label: 'Enforcement',
    value: 'Strict',
    trendLabel: 'Policy v2.4 active',
    trend: 'up',
    icon: FiShield,
  },
] as const;

const eventsByHour = [
  { hour: '00', events: 12 },
  { hour: '02', events: 7 },
  { hour: '04', events: 8 },
  { hour: '06', events: 18 },
  { hour: '08', events: 30 },
  { hour: '10', events: 25 },
  { hour: '12', events: 15 },
  { hour: '14', events: 8 },
  { hour: '16', events: 17 },
  { hour: '18', events: 27 },
  { hour: '20', events: 24 },
  { hour: '22', events: 14 },
];

const policyDistribution = [
  { name: 'Strict', value: 48 },
  { name: 'Monitor', value: 27 },
  { name: 'Permissive', value: 18 },
  { name: 'Disabled', value: 7 },
];

const recentIncidents = [
  {
    id: 'INC-4012',
    asset: 'ENG-LAPTOP-17',
    severity: 'High',
    status: 'Investigating',
    time: '2m ago',
  },
  {
    id: 'INC-4008',
    asset: 'FIN-SERVER-03',
    severity: 'Medium',
    status: 'Monitoring',
    time: '19m ago',
  },
  { id: 'INC-4001', asset: 'OPS-DESKTOP-22', severity: 'Low', status: 'Resolved', time: '34m ago' },
];

const PIE_COLORS = ['#0891b2', '#0ea5e9', '#f59e0b', '#ef4444'];

export const DashboardPage = () => {
  return (
    <div className="space-y-8">
      <PageHeader
        title="ECIMS 2.0 Security Operations Dashboard"
        subtitle="Monitor endpoint posture, alert flow, and policy distribution in real time across network."
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => (
          <StatCard
            key={item.label}
            label={item.label}
            value={item.value}
            trendLabel={item.trendLabel}
            trend={item.trend}
            icon={item.icon}
          />
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <ChartCard
          title="Events Per Hour"
          subtitle="Telemetry events observed across protected endpoints"
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={eventsByHour}>
              <CartesianGrid strokeDasharray="4 4" stroke="#64748b33" />
              <XAxis
                dataKey="hour"
                tick={{ fill: '#94a3b8', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="events"
                stroke="#0891b2"
                strokeWidth={3}
                dot={{ fill: '#0891b2', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Policy Distribution"
          subtitle="Current rollout mode split across enrolled machines"
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={policyDistribution}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={72}
                outerRadius={102}
                paddingAngle={2}
              >
                {policyDistribution.map((entry, index) => (
                  <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend verticalAlign="bottom" iconType="circle" />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
          Recent Incidents
        </h2>
        <DataTable
          columns={[
            { key: 'id', header: 'Incident ID' },
            { key: 'asset', header: 'Asset' },
            {
              key: 'severity',
              header: 'Severity',
              render: (row) => {
                const tone =
                  row.severity === 'High'
                    ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                    : row.severity === 'Medium'
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                      : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300';
                return (
                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tone}`}>
                    {row.severity}
                  </span>
                );
              },
            },
            { key: 'status', header: 'Status' },
            { key: 'time', header: 'Updated' },
          ]}
          rows={recentIncidents}
          rowKey={(row) => row.id}
        />
      </section>
    </div>
  );
};
