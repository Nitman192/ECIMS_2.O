import { FiActivity, FiAlertCircle, FiPower, FiShield } from 'react-icons/fi';
import { Card } from '../components/ui/Card';
// ...existing code...
import ChartCard from '../components/ChartCard';

const stats = [
  {
    label: 'Active Agents',
    value: '1,284',
    trend: '+4.8%',
    icon: FiActivity,
  },
  {
    label: 'Alerts',
    value: '37',
    trend: '-12.3%',
    icon: FiAlertCircle,
  },
  {
    label: 'Kill Switch',
    value: 'Armed',
    trend: 'Operational',
    icon: FiPower,
  },
  {
    label: 'Enforcement Mode',
    value: 'Strict',
    trend: 'Policy v2.4',
    icon: FiShield,
  },
];

export const DashboardPage = () => {
  return (
    <div className="space-y-6">
      <section className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            Dashboard Overview
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Real-time operational posture for your endpoint security deployment.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
                    {item.value}
                  </p>
                  <p className="mt-2 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    {item.trend}
                  </p>
                </div>
                <div className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  <Icon className="text-lg" />
                </div>
              </div>
            </Card>
          );
        })}
      </section>

      <section>
        <ChartCard />
      </section>
    </div>
  );
};
