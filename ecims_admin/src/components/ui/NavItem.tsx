import type { IconType } from 'react-icons';
import { NavLink } from 'react-router-dom';

type NavItemProps = {
  to: string;
  label: string;
  icon: IconType;
  collapsed?: boolean;
  end?: boolean;
  onClick?: () => void;
};

export const NavItem = ({ to, label, icon: Icon, collapsed = false, end = false, onClick }: NavItemProps) => {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) =>
        `group flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition ${
          collapsed ? 'justify-center' : 'justify-start gap-3'
        } ${
          isActive
            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
            : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100'
        }`
      }
      title={collapsed ? label : undefined}
    >
      <Icon className={`text-lg ${collapsed ? '' : 'shrink-0'}`} />
      {!collapsed && <span>{label}</span>}
    </NavLink>
  );
};
