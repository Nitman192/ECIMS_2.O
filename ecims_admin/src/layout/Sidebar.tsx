import type { IconType } from 'react-icons';
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
import { NavLink } from 'react-router-dom';
import { MobileSidebarOverlay } from '../components/MobileSidebarOverlay';

type SidebarProps = {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
};

type SidebarItem = {
  to: string;
  label: string;
  icon: IconType;
  end?: boolean;
};

const navItems: SidebarItem[] = [
  { to: '/', label: 'Dashboard', icon: FiHome, end: true },
  { to: '/agents', label: 'Agents', icon: FiUsers },
  { to: '/alerts', label: 'Alerts', icon: FiAlertTriangle },
  { to: '/security', label: 'Security Center', icon: FiShield },
  { to: '/license', label: 'License Panel', icon: FiActivity },
  { to: '/audit', label: 'Audit Logs', icon: FiFileText }
];

export const Sidebar = ({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile }: SidebarProps) => {
  return (
    <>
      <MobileSidebarOverlay open={mobileOpen} onClose={onCloseMobile} />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-screen border-r border-slate-200 bg-white shadow-xl shadow-slate-900/5 transition-all duration-300 dark:border-slate-800 dark:bg-slate-950 dark:shadow-black/30 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        } w-[272px] lg:translate-x-0 ${collapsed ? 'lg:w-[92px]' : 'lg:w-[272px]'}`}
      >
        <div className="flex w-full flex-col">
          <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-800">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900">
                <FiShield className="text-base" />
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold tracking-wide text-slate-900 dark:text-slate-100">
                    ECIMS 2.0
                  </p>
                  <p className="truncate text-xs text-slate-500 dark:text-slate-400">Admin Console</p>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:inline-flex"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <FiChevronRight /> : <FiChevronLeft />}
            </button>
          </div>

          <nav className="flex-1 space-y-1 p-3">
            {navItems.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onCloseMobile}
                className={({ isActive }) =>
                  `group flex h-11 items-center rounded-xl px-3 text-sm font-medium transition ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm dark:bg-slate-100 dark:text-slate-900'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
                  } ${collapsed ? 'justify-center' : 'gap-3'}`
                }
                title={collapsed ? label : undefined}
              >
                <Icon className="text-lg" />
                {!collapsed && <span className="truncate">{label}</span>}
              </NavLink>
            ))}
          </nav>
        </div>
      </aside>
    </>
  );
};
