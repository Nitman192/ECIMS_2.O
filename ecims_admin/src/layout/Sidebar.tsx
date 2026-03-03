import {
  FiActivity,
  FiAlertTriangle,
  FiChevronLeft,
  FiChevronRight,
  FiFileText,
  FiHome,
  FiShield,
  FiUsers
} from 'react-icons/fi';
import { NavItem } from '../components/ui/NavItem';

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

const navItems = [
  { to: '/', label: 'Dashboard', icon: FiHome, end: true },
  { to: '/agents', label: 'Agents', icon: FiUsers },
  { to: '/alerts', label: 'Alerts', icon: FiAlertTriangle },
  { to: '/security', label: 'Security Center', icon: FiShield },
  { to: '/license', label: 'License Panel', icon: FiActivity },
  { to: '/audit', label: 'Audit Logs', icon: FiFileText }
];

export const Sidebar = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile
}: SidebarProps) => {
  return (
    <>
      <div
        className={`fixed inset-0 z-30 bg-slate-950/40 transition-opacity lg:hidden ${
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onCloseMobile}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-screen flex-col border-r border-slate-200 bg-white/95 backdrop-blur transition-all duration-300 dark:border-slate-800 dark:bg-slate-900/95 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        } ${collapsed ? 'lg:w-20' : 'lg:w-72'} w-72 lg:translate-x-0`}
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-slate-900 text-white dark:bg-white dark:text-slate-900">
              <FiShield className="text-lg" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">ECIMS Admin</p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">Security Dashboard</p>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:block"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <FiChevronRight /> : <FiChevronLeft />}
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {navItems.map(({ to, label, icon, end }) => (
            <NavItem
              key={to}
              to={to}
              label={label}
              icon={icon}
              end={end}
              collapsed={collapsed}
              onClick={onCloseMobile}
            />
          ))}
        </nav>
      </aside>
    </>
  );
};
