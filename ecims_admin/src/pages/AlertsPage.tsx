import { useEffect, useMemo, useState } from 'react';
import { CoreApi } from '../api/services';
import type { Alert } from '../types';

const badge = (s: string) => s === 'RED' ? 'bg-rose-500' : s === 'YELLOW' ? 'bg-amber-500' : 'bg-emerald-500';

export const AlertsPage = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [q, setQ] = useState('');
  const [severity, setSeverity] = useState('ALL');
  useEffect(() => { CoreApi.alerts().then((r) => setAlerts(r.data)); }, []);

  const filtered = useMemo(() => alerts.filter((a) => (severity === 'ALL' || a.severity === severity) && JSON.stringify(a).toLowerCase().includes(q.toLowerCase())), [alerts, q, severity]);
  const exportCsv = () => {
    const rows = filtered.map((a) => `${a.id},${a.severity},"${a.message.replace(/"/g, '""')}"`).join('\n');
    const blob = new Blob([`id,severity,message\n${rows}`]);
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'alerts.csv'; a.click();
  };

  return <div className="card"><div className="mb-4 flex gap-3"><input className="input" placeholder="Search alerts" value={q} onChange={(e) => setQ(e.target.value)} /><select className="input max-w-40" value={severity} onChange={(e) => setSeverity(e.target.value)}><option>ALL</option><option>RED</option><option>YELLOW</option><option>GREEN</option></select><button className="btn bg-indigo-600 text-white" onClick={exportCsv}>Export CSV</button></div><div className="space-y-3">{filtered.map((a) => <div key={a.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><span className={`rounded-full px-2 py-1 text-xs text-white ${badge(a.severity)}`}>{a.severity}</span><span className="ml-3 font-medium">{a.alert_type}</span><p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{a.message}</p></div>)}</div></div>;
};
