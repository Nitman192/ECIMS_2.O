import type { IconType } from 'react-icons';
import {
  FiActivity,
  FiAlertTriangle,
  FiBookOpen,
  FiChevronLeft,
  FiChevronRight,
  FiClipboard,
  FiClock,
  FiFileText,
  FiFlag,
  FiGitMerge,
  FiHardDrive,
  FiHome,
  FiKey,
  FiLock,
  FiPower,
  FiShield,
  FiShieldOff,
  FiTool,
  FiUsers,
  FiUserCheck,
  FiX,
  FiZap,
} from 'react-icons/fi';
import { NavLink } from 'react-router-dom';
import { MobileSidebarOverlay } from '../components/MobileSidebarOverlay';
import { useAuth } from '../store/AuthContext';

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
  accent: 'red' | 'green';
  end?: boolean;
  requiresAdmin?: boolean;
};

type SidebarGroup = {
  label: string;
  items: SidebarItem[];
};

const coreGroup: SidebarGroup = {
  label: 'Core',
  items: [
    { to: '/', label: 'Dashboard', icon: FiHome, accent: 'green', end: true },
    { to: '/agents', label: 'Agents', icon: FiUsers, accent: 'green' },
    { to: '/alerts', label: 'Alerts', icon: FiAlertTriangle, accent: 'red' },
    { to: '/security', label: 'Security Center', icon: FiShield, accent: 'red' },
    { to: '/license', label: 'License Panel', icon: FiActivity, accent: 'green' },
    { to: '/audit', label: 'Audit Logs', icon: FiFileText, accent: 'green' },
  ],
};

const adminOpsGroups: SidebarGroup[] = [
  {
    label: 'Admin / Ops - Core Admin',
    items: [
      { to: '/admin/users', label: 'Users', icon: FiUserCheck, accent: 'green', requiresAdmin: true },
      { to: '/admin/roles', label: 'Roles Matrix', icon: FiClipboard, accent: 'green', requiresAdmin: true },
      { to: '/admin/features', label: 'Feature Flags', icon: FiFlag, accent: 'green', requiresAdmin: true },
      { to: '/admin/audit', label: 'Audit Explorer', icon: FiFileText, accent: 'green', requiresAdmin: true },
    ],
  },
  {
    label: 'Admin / Ops - Fleet Operations',
    items: [
      { to: '/ops/remote-actions', label: 'Remote Actions', icon: FiPower, accent: 'green' },
      { to: '/ops/schedules', label: 'Schedules', icon: FiClock, accent: 'green' },
      { to: '/ops/enrollment', label: 'Enrollment', icon: FiKey, accent: 'green' },
      { to: '/ops/health', label: 'Fleet Health', icon: FiActivity, accent: 'green' },
      { to: '/ops/quarantine', label: 'Quarantine', icon: FiShieldOff, accent: 'red' },
    ],
  },
  {
    label: 'Admin / Ops - High-Need Fixes',
    items: [
      { to: '/ops/evidence-vault', label: 'Evidence Vault', icon: FiHardDrive, accent: 'green' },
      { to: '/ops/playbooks', label: 'Playbooks', icon: FiBookOpen, accent: 'green' },
      { to: '/ops/change-control', label: 'Change Control', icon: FiGitMerge, accent: 'green' },
      { to: '/ops/break-glass', label: 'Break Glass', icon: FiLock, accent: 'red' },
    ],
  },
];

const quickAccess: Array<{ label: string; to: string; hotkey: string; accent: 'red' | 'green' }> = [
  { label: 'Dashboard', to: '/', hotkey: 'Alt+1', accent: 'green' },
  { label: 'Alerts', to: '/alerts', hotkey: 'Alt+3', accent: 'red' },
  { label: 'Remote Actions', to: '/ops/remote-actions', hotkey: 'Alt+4', accent: 'green' },
];

const navClass = ({ isActive }: { isActive: boolean }, collapsed: boolean) =>
  `group flex h-10 items-center rounded-xl px-3 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-900/25 dark:bg-cyan-500 dark:text-slate-950'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
  } ${collapsed ? 'justify-center' : 'gap-3'}`;

const accentLineClass = (accent: 'red' | 'green', isActive: boolean) => {
  if (accent === 'red') {
    return isActive ? 'w-full bg-rose-300 dark:bg-rose-400' : 'w-0 bg-rose-300/80 dark:bg-rose-500/70 group-hover:w-8';
  }
  return isActive ? 'w-full bg-emerald-300 dark:bg-emerald-400' : 'w-0 bg-emerald-300/80 dark:bg-emerald-500/70 group-hover:w-8';
};

export const Sidebar = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}: SidebarProps) => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';

  return (
    <>
      <MobileSidebarOverlay open={mobileOpen} onClose={onCloseMobile} />

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen border-r border-slate-200 bg-white shadow-xl shadow-slate-900/10 transition-all duration-300 dark:border-slate-800 dark:bg-slate-950 dark:shadow-black/40 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        } w-[280px] will-change-transform lg:translate-x-0 ${collapsed ? 'lg:w-[96px]' : 'lg:w-[280px]'}`}
      >
        <div className="flex w-full flex-col">
          <div
            className={`relative flex h-16 items-center border-b border-slate-200 dark:border-slate-800 ${
              collapsed ? 'justify-center px-2' : 'justify-between px-4'
            }`}
          >
            <div className={`flex min-w-0 items-center ${collapsed ? '' : 'gap-3'}`}>
              <div
                className={`grid shrink-0 place-items-center bg-gradient-to-br from-cyan-600 to-blue-700 text-white shadow-md shadow-cyan-900/30 ${
                  collapsed ? 'h-9 w-9 rounded-xl' : 'h-10 w-10 rounded-2xl'
                }`}
              >
                <FiTool className="text-base" />
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold tracking-wide text-slate-900 dark:text-slate-100">ECIMS 2.0</p>
                  <p className="truncate text-xs text-slate-500 dark:text-slate-400">Security Ops Control Plane</p>
                </div>
              )}
            </div>

            <div
              className={`flex items-center gap-1 ${
                collapsed ? 'absolute right-2 top-1/2 -translate-y-1/2' : ''
              }`}
            >
              <button
                type="button"
                onClick={onCloseMobile}
                className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:hidden"
                aria-label="Close sidebar"
              >
                <FiX />
              </button>
              <button
                type="button"
                onClick={onToggleCollapse}
                className="hidden h-8 w-8 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:inline-flex"
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <FiChevronRight /> : <FiChevronLeft />}
              </button>
            </div>
          </div>

          <nav className="flex-1 space-y-4 overflow-y-auto p-3">
            <div className="space-y-1.5">
              {!collapsed && (
                <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
                  {coreGroup.label}
                </p>
              )}
              {coreGroup.items.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    title={collapsed ? item.label : undefined}
                    onClick={onCloseMobile}
                    className={(state) => navClass(state, collapsed)}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon className="text-base" />
                        {!collapsed && (
                          <span className="relative truncate pb-0.5">
                            {item.label}
                            <span
                              className={`pointer-events-none absolute -bottom-0.5 left-0 h-0.5 rounded-full transition-all duration-300 ${accentLineClass(item.accent, isActive)}`}
                            />
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </div>

            {adminOpsGroups.map((group) => {
              const visibleItems = group.items.filter((item) => !(item.requiresAdmin && !isAdmin));
              if (!visibleItems.length) return null;
              return (
                <div key={group.label} className="space-y-1.5">
                  {!collapsed && (
                    <p className="px-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400 dark:text-slate-500">
                      {group.label}
                    </p>
                  )}
                  {visibleItems.map((item) => {
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        title={collapsed ? item.label : undefined}
                        onClick={onCloseMobile}
                        className={(state) => navClass(state, collapsed)}
                      >
                        {({ isActive }) => (
                          <>
                            <Icon className="text-base" />
                            {!collapsed && (
                              <span className="relative truncate pb-0.5">
                                {item.label}
                                <span
                                  className={`pointer-events-none absolute -bottom-0.5 left-0 h-0.5 rounded-full transition-all duration-300 ${accentLineClass(item.accent, isActive)}`}
                                />
                              </span>
                            )}
                          </>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              );
            })}
          </nav>

          <div className="border-t border-slate-200 p-3 dark:border-slate-800">
            {!collapsed ? (
              <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-2.5 dark:border-slate-700 dark:bg-slate-900">
                <p className="flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                  <FiZap />
                  Shortcuts
                </p>
                {quickAccess.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={onCloseMobile}
                    className="group flex items-center justify-between rounded-lg px-2 py-1.5 text-xs text-slate-600 transition hover:bg-white hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                  >
                    {({ isActive }) => (
                      <>
                        <span className="relative truncate pb-0.5">
                          {item.label}
                          <span
                            className={`pointer-events-none absolute -bottom-0.5 left-0 h-0.5 rounded-full transition-all duration-300 ${accentLineClass(item.accent, isActive)}`}
                          />
                        </span>
                        <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                          {item.hotkey}
                        </span>
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            ) : (
              <div className="flex justify-center">
                <span
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400"
                  title="Use Alt+1..Alt+6 for quick navigation"
                >
                  <FiZap />
                </span>
              </div>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
