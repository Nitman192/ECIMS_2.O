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
    { to: '/', label: 'Dashboard', icon: FiHome, end: true },
    { to: '/agents', label: 'Agents', icon: FiUsers },
    { to: '/alerts', label: 'Alerts', icon: FiAlertTriangle },
    { to: '/security', label: 'Security Center', icon: FiShield },
    { to: '/license', label: 'License Panel', icon: FiActivity },
    { to: '/audit', label: 'Audit Logs', icon: FiFileText },
  ],
};

const adminOpsGroups: SidebarGroup[] = [
  {
    label: 'Admin / Ops · Core Admin',
    items: [
      { to: '/admin/users', label: 'Users', icon: FiUserCheck, requiresAdmin: true },
      { to: '/admin/roles', label: 'Roles Matrix', icon: FiClipboard, requiresAdmin: true },
      { to: '/admin/features', label: 'Feature Flags', icon: FiFlag, requiresAdmin: true },
      { to: '/admin/audit', label: 'Audit Explorer', icon: FiFileText, requiresAdmin: true },
    ],
  },
  {
    label: 'Admin / Ops · Fleet Operations',
    items: [
      { to: '/ops/remote-actions', label: 'Remote Actions', icon: FiPower },
      { to: '/ops/schedules', label: 'Schedules', icon: FiClock },
      { to: '/ops/enrollment', label: 'Enrollment', icon: FiKey },
      { to: '/ops/health', label: 'Fleet Health', icon: FiActivity },
      { to: '/ops/quarantine', label: 'Quarantine', icon: FiShieldOff },
    ],
  },
  {
    label: 'Admin / Ops · High-Need Fixes',
    items: [
      { to: '/ops/evidence-vault', label: 'Evidence Vault', icon: FiHardDrive },
      { to: '/ops/playbooks', label: 'Playbooks', icon: FiBookOpen },
      { to: '/ops/change-control', label: 'Change Control', icon: FiGitMerge },
      { to: '/ops/break-glass', label: 'Break Glass', icon: FiLock },
    ],
  },
];

const navClass = ({ isActive }: { isActive: boolean }, collapsed: boolean) =>
  `group flex h-10 items-center rounded-xl px-3 text-sm font-medium transition-colors ${
    isActive
      ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-900/25 dark:bg-cyan-500 dark:text-slate-950'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
  } ${collapsed ? 'justify-center' : 'gap-3'}`;

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
        className={`fixed inset-y-0 left-0 z-40 flex h-screen border-r border-slate-200 bg-white shadow-xl shadow-slate-900/10 transition-all duration-300 dark:border-slate-800 dark:bg-slate-950 dark:shadow-black/40 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        } w-[280px] lg:translate-x-0 ${collapsed ? 'lg:w-[96px]' : 'lg:w-[280px]'}`}
      >
        <div className="flex w-full flex-col">
          <div className="flex h-16 items-center justify-between border-b border-slate-200 px-4 dark:border-slate-800">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-cyan-600 to-blue-700 text-white shadow-md shadow-cyan-900/30">
                <FiTool className="text-base" />
              </div>
              {!collapsed && (
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold tracking-wide text-slate-900 dark:text-slate-100">
                    ECIMS 2.0
                  </p>
                  <p className="truncate text-xs text-slate-500 dark:text-slate-400">Security Ops Control Plane</p>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:inline-flex"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <FiChevronRight /> : <FiChevronLeft />}
            </button>
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
                    <Icon className="text-base" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
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
                      <Icon className="text-base" />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  );
                })}
              </div>
            );
            })}
          </nav>
        </div>
      </aside>
    </>
  );
};

