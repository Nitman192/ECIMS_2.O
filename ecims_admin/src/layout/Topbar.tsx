import { FiLogOut, FiMenu, FiMoon, FiSearch, FiSun, FiUser } from 'react-icons/fi';
import { useTheme } from '../store/ThemeContext';

type TopbarProps = {
  onOpenSidebar: () => void;
  userName?: string;
  onLogout?: () => void;
};

export const Topbar = ({ onOpenSidebar, userName = 'Operator', onLogout }: TopbarProps) => {
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90 sm:px-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:hidden"
            aria-label="Open sidebar"
          >
            <FiMenu className="text-lg" />
          </button>
          <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400 dark:border-slate-700 dark:bg-slate-900 sm:flex">
            <FiSearch />
            <span>Search dashboards, agents, alerts...</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            {theme === 'dark' ? <FiSun className="text-base" /> : <FiMoon className="text-base" />}
          </button>
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-800">
            <div className="grid h-7 w-7 place-items-center rounded-full bg-slate-900 text-white dark:bg-slate-200 dark:text-slate-900">
              <FiUser className="text-xs" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-xs text-slate-500 dark:text-slate-400">Logged in as</p>
              <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{userName}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            <FiLogOut />
            Logout
          </button>
        </div>
      </div>
    </header>
  );
};
