import { useEffect, useState } from 'react';
import { Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts';
import { CoreApi } from '../api/services';

export const DashboardPage = () => {
  const [metrics, setMetrics] = useState<any>(null);
  useEffect(() => { CoreApi.metrics().then((r) => setMetrics(r.data)); }, []);

  const cards = [
    ['Active Agents', metrics?.rollout?.active_agents ?? 0],
    ['License Expiry', 'See License Panel'],
    ['Kill Switch State', metrics?.kill_switch_state?.enabled ? 'ENABLED' : 'DISABLED'],
    ['Enforcement Mode', metrics?.rollout?.mode ?? 'observe'],
    ['Alerts Open', metrics?.device_events_ingested_total?.device?.open_alerts ?? 0]
  ];
  const lineData = Object.entries(metrics?.device_events_ingested_total ?? {}).map(([k, v]) => ({ hour: k.slice(-2), value: Number(v) }));
  const pieData = [
    { name: 'Observe', value: Number(metrics?.rollout?.observe ?? 0) },
    { name: 'Enforce', value: Number(metrics?.rollout?.enforce ?? 0) }
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {cards.map(([label, value]) => <div className="card" key={label}><p className="text-sm text-slate-500 dark:text-slate-300">{label}</p><p className="mt-2 text-2xl font-semibold">{String(value)}</p></div>)}
      </div>
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="card xl:col-span-2"><h3 className="mb-4 font-semibold">Events per hour</h3><div className="h-72"><ResponsiveContainer><LineChart data={lineData}><XAxis dataKey="hour"/><YAxis/><Tooltip/><Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2}/></LineChart></ResponsiveContainer></div></div>
        <div className="card"><h3 className="mb-4 font-semibold">Rollout distribution</h3><div className="h-72"><ResponsiveContainer><PieChart><Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90}>{['#6366f1', '#22c55e'].map((c) => <Cell key={c} fill={c}/> )}</Pie><Tooltip/></PieChart></ResponsiveContainer></div></div>
      </div>
    </div>
  );
};
