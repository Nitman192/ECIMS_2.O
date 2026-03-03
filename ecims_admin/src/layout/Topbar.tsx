import { FiMenu, FiMoon, FiSearch, FiSun } from 'react-icons/fi';
import { Container } from '../components/ui/Container';
import { UserDropdown } from '../components/UserDropdown';
import { useTheme } from '../store/ThemeContext';

type TopbarProps = {
  onOpenSidebar: () => void;
  userName: string;
  userRole: string;
  onLogout: () => void;
};

export const Topbar = ({ onOpenSidebar, userName, userRole, onLogout }: TopbarProps) => {
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/85">
      <Container className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <div className="flex w-14 items-center justify-start">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:hidden"
            aria-label="Open navigation"
          >
            <FiMenu className="text-lg" />
          </button>
        </div>

        <div className="flex flex-1 justify-center">
          <label className="group hidden w-full max-w-2xl items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-slate-400 dark:border-slate-700 dark:bg-slate-900 sm:flex">
            <FiSearch className="text-slate-400 transition group-focus-within:text-slate-600 dark:group-focus-within:text-slate-200" />
            <input
              type="text"
              placeholder="Search incidents, assets, users..."
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>
        </div>

        <div className="flex w-14 items-center justify-end gap-2 sm:w-auto">
          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {theme === 'dark' ? <FiSun className="text-base" /> : <FiMoon className="text-base" />}
          </button>
          <UserDropdown userName={userName} userRole={userRole} onLogout={onLogout} />
        </div>
      </Container>
    </header>
  );
};
