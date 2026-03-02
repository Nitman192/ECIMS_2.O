import { useEffect, useState } from 'react';
import { CoreApi } from '../api/services';

export const AuditLogsPage = () => {
  const [rows, setRows] = useState<any[]>([]);
  const [action, setAction] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');

  const load = () => CoreApi.auditLogs({ action_type: action, start_ts: start, end_ts: end }).then((r) => setRows(r.data.items || []));
  useEffect(load, []);
  const exportAudit = async () => {
    const r = await CoreApi.exportAudit({ start_ts: start || '1970-01-01T00:00:00Z', end_ts: end || new Date().toISOString(), redaction_profile: 'standard' });
    alert(`Export generated: ${r.data.path}`);
  };

  return <div className="card"><div className="mb-4 grid gap-3 md:grid-cols-4"><input className="input" placeholder="Action" value={action} onChange={(e) => setAction(e.target.value)} /><input className="input" type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /><input className="input" type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /><div className="flex gap-2"><button className="btn bg-indigo-600 text-white" onClick={load}>Filter</button><button className="btn bg-slate-600 text-white" onClick={exportAudit}>Export</button></div></div><div className="space-y-2">{rows.map((r) => <div key={r.id} className="rounded-xl border border-slate-200 p-3 dark:border-slate-700"><p className="text-xs text-slate-500">{r.ts} • {r.action}</p><p className="font-medium">{r.message}</p></div>)}</div></div>;
};
