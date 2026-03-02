import { NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: 'Dashboard', icon: '▣' },
  { to: '/agents', label: 'Agents', icon: '◈' },
  { to: '/alerts', label: 'Alerts', icon: '⚠' },
  { to: '/security', label: 'Security Center', icon: '🛡' },
  { to: '/license', label: 'License Panel', icon: '🔑' },
  { to: '/audit', label: 'Audit Logs', icon: '🧾' }
];

export const Sidebar = ({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) => (
  <aside className={`h-screen border-r border-slate-200 bg-white transition-all duration-300 dark:border-slate-800 dark:bg-surface-800 ${collapsed ? 'w-20' : 'w-72'}`}>
    <div className="flex items-center justify-between px-4 py-5">
      <div className="flex items-center gap-3 text-indigo-500">
        <span className="text-xl">🛡</span>{!collapsed && <span className="font-semibold text-slate-900 dark:text-white">ECIMS 2.0</span>}
      </div>
      <button className="btn bg-slate-100 dark:bg-surface-700" onClick={onToggle}>{collapsed ? '→' : '←'}</button>
    </div>
    <nav className="space-y-2 px-3">
      {links.map(({ to, label, icon }) => (
        <NavLink key={to} to={to} className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2 text-sm ${isActive ? 'bg-indigo-500 text-white' : 'text-slate-600 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-surface-700'}`}>
          <span>{icon}</span> {!collapsed && label}
        </NavLink>
      ))}
    </nav>
  </aside>
);
