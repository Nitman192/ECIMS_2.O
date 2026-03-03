import { FiActivity, FiAlertCircle, FiPower, FiShield } from 'react-icons/fi';
import {
  Cell,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts';
import { ChartCard } from '../components/ChartCard';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';

const stats = [
  { label: 'Active Agents', value: '1,284', trendLabel: '+4.8% vs last week', trend: 'up', icon: FiActivity },
  { label: 'Open Alerts', value: '37', trendLabel: '-12.3% vs last week', trend: 'down', icon: FiAlertCircle },
  { label: 'Kill Switch', value: 'Armed', trendLabel: 'No state changes', trend: 'neutral', icon: FiPower },
  { label: 'Enforcement', value: 'Strict', trendLabel: 'Policy v2.4 active', trend: 'up', icon: FiShield }
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
  { hour: '22', events: 14 }
];

const policyDistribution = [
  { name: 'Strict', value: 48 },
  { name: 'Monitor', value: 27 },
  { name: 'Permissive', value: 18 },
  { name: 'Disabled', value: 7 }
];

const PIE_COLORS = ['#0f766e', '#0369a1', '#f59e0b', '#dc2626'];

export const DashboardPage = () => {
  return (
    <div className="space-y-8">
      <PageHeader
        title="Security Operations Dashboard"
        subtitle="Monitor endpoint posture, alert flow, and policy distribution in real time across your enterprise fleet."
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
        <ChartCard title="Events Per Hour" subtitle="Total telemetry events observed across protected endpoints">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={eventsByHour} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="4 4" stroke="#64748b33" />
              <XAxis dataKey="hour" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="events"
                stroke="#0f766e"
                strokeWidth={3}
                dot={{ fill: '#0f766e', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Policy Distribution" subtitle="Current rollout mode split across enrolled machines">
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
    </div>
  );
};
