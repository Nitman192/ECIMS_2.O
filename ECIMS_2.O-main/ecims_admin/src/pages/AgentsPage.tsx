import { useEffect, useState } from 'react';
import { CoreApi } from '../api/services';
import type { Agent } from '../types';

export const AgentsPage = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selected, setSelected] = useState<Agent | null>(null);
  const load = () => CoreApi.agents().then((r) => setAgents(r.data));
  useEffect(load, []);

  const act = async (id: number, type: 'revoke' | 'restore') => {
    if (type === 'revoke') await CoreApi.revokeAgent(id, 'Console action');
    else await CoreApi.restoreAgent(id, 'Console action');
    load();
  };

  return <div className="card"><h2 className="mb-4 text-xl font-semibold">Agents</h2><table className="w-full text-sm"><thead><tr className="text-left text-slate-500"><th>ID</th><th>Hostname</th><th>Mode</th><th>Last Seen</th><th>Status</th><th/></tr></thead><tbody>{agents.map((a) => <tr key={a.id} className="border-t border-slate-200 dark:border-slate-700"><td>{a.id}</td><td><button className="underline" onClick={() => setSelected(a)}>{a.hostname || a.name}</button></td><td>{a.device_mode_override || 'default'}</td><td>{a.last_seen}</td><td>{a.status}</td><td className="space-x-2"><button className="btn bg-rose-600 text-white" onClick={() => act(a.id, 'revoke')}>Revoke</button><button className="btn bg-emerald-600 text-white" onClick={() => act(a.id, 'restore')}>Restore</button></td></tr>)}</tbody></table>{selected && <div className="fixed right-0 top-0 h-full w-96 bg-white p-5 shadow-soft dark:bg-surface-800"><h3 className="font-semibold">Agent Details</h3><pre className="mt-3 text-xs">{JSON.stringify(selected, null, 2)}</pre><button className="btn mt-4 bg-slate-200 dark:bg-surface-700" onClick={() => setSelected(null)}>Close</button></div>}</div>;
};
