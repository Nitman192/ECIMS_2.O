import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  FiChevronLeft,
  FiChevronRight,
  FiClock,
  FiCommand,
  FiMenu,
  FiMoon,
  FiSearch,
  FiSun,
} from 'react-icons/fi';
import { useLocation, useNavigate } from 'react-router-dom';
import { UserDropdown } from '../components/UserDropdown';
import { Container } from '../components/ui/Container';
import { useTheme } from '../store/ThemeContext';

type TopbarProps = {
  onOpenSidebar: () => void;
  onToggleCollapse: () => void;
  collapsed: boolean;
  userName: string;
  userRole: string;
  sessionRemainingSeconds: number;
  sessionIsWarning: boolean;
  onLogout: () => void;
};

type ShortcutItem = {
  label: string;
  to: string;
  hotkey: string;
  key: string;
  keywords: string[];
};

const SHORTCUTS: ShortcutItem[] = [
  { label: 'Dashboard', to: '/', hotkey: 'Alt+1', key: '1', keywords: ['dashboard', 'home', 'overview'] },
  { label: 'Agents', to: '/agents', hotkey: 'Alt+2', key: '2', keywords: ['agents', 'endpoints', 'fleet'] },
  { label: 'Alerts', to: '/alerts', hotkey: 'Alt+3', key: '3', keywords: ['alerts', 'incidents', 'threats'] },
  { label: 'Remote Actions', to: '/ops/remote-actions', hotkey: 'Alt+4', key: '4', keywords: ['remote', 'actions', 'tasks'] },
  { label: 'Schedules', to: '/ops/schedules', hotkey: 'Alt+5', key: '5', keywords: ['schedule', 'maintenance'] },
  { label: 'Change Control', to: '/ops/change-control', hotkey: 'Alt+6', key: '6', keywords: ['change', 'backup', 'restore'] },
];

const formatRemaining = (seconds: number) => {
  const safe = Math.max(seconds, 0);
  const minutesPart = Math.floor(safe / 60);
  const secondsPart = safe % 60;
  return `${String(minutesPart).padStart(2, '0')}:${String(secondsPart).padStart(2, '0')}`;
};

const resolveSearchRoute = (rawValue: string): string | null => {
  const value = rawValue.trim().toLowerCase();
  if (!value) return null;
  if (value.startsWith('/')) return value;
  const match = SHORTCUTS.find((item) => item.label.toLowerCase().includes(value) || item.keywords.some((keyword) => keyword.includes(value)));
  return match ? match.to : null;
};

const shortcutAccent = (to: string): 'red' | 'green' => (to === '/alerts' ? 'red' : 'green');

const shortcutLineClass = (accent: 'red' | 'green', isActive: boolean) => {
  if (accent === 'red') {
    return isActive ? 'w-full bg-rose-400 dark:bg-rose-400' : 'w-0 bg-rose-300/80 dark:bg-rose-500/70 group-hover:w-6';
  }
  return isActive ? 'w-full bg-emerald-400 dark:bg-emerald-400' : 'w-0 bg-emerald-300/80 dark:bg-emerald-500/70 group-hover:w-6';
};

export const Topbar = ({
  onOpenSidebar,
  onToggleCollapse,
  collapsed,
  userName,
  userRole,
  sessionRemainingSeconds,
  sessionIsWarning,
  onLogout,
}: TopbarProps) => {
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchValue, setSearchValue] = useState('');
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const shortcutsRef = useRef<HTMLDivElement | null>(null);

  const timerText = useMemo(() => formatRemaining(sessionRemainingSeconds), [sessionRemainingSeconds]);

  const navigateTo = (path: string) => {
    if (!path || path === location.pathname) return;
    navigate(path);
  };

  const onSearchSubmit = (event: FormEvent) => {
    event.preventDefault();
    const route = resolveSearchRoute(searchValue);
    if (route) {
      navigateTo(route);
      return;
    }
    setShortcutsOpen(true);
  };

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (!shortcutsRef.current) return;
      if (event.target instanceof Node && !shortcutsRef.current.contains(event.target)) {
        setShortcutsOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
        return;
      }

      if (event.altKey && event.key.toLowerCase() === 'b') {
        event.preventDefault();
        onToggleCollapse();
        return;
      }

      if (event.altKey) {
        const target = SHORTCUTS.find((item) => item.key === event.key);
        if (target) {
          event.preventDefault();
          navigate(target.to);
        }
      }
    };

    document.addEventListener('mousedown', onClickOutside);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [navigate, onToggleCollapse]);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/85 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
      <Container className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenSidebar}
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:hidden"
            aria-label="Open navigation"
          >
            <FiMenu className="text-lg" />
          </button>

          <button
            type="button"
            onClick={onToggleCollapse}
            className="hidden h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100 lg:inline-flex"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title="Toggle sidebar (Alt+B)"
          >
            {collapsed ? <FiChevronRight className="text-base" /> : <FiChevronLeft className="text-base" />}
          </button>

          <div className="hidden xl:flex items-center gap-1">
            {SHORTCUTS.slice(0, 3).map((item) => (
              (() => {
                const isActive =
                  location.pathname === item.to || (item.to !== '/' && location.pathname.startsWith(`${item.to}/`));
                const accent = shortcutAccent(item.to);
                return (
                  <button
                    key={item.to}
                    type="button"
                    onClick={() => navigateTo(item.to)}
                    className={`group h-9 rounded-lg px-2 text-xs font-medium transition ${
                      isActive
                        ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950/40 dark:text-cyan-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`}
                    title={item.hotkey}
                  >
                    <span className="relative inline-flex items-center pb-0.5">
                      {item.label}
                      <span
                        className={`pointer-events-none absolute -bottom-0.5 left-0 h-0.5 rounded-full transition-all duration-300 ${shortcutLineClass(accent, isActive)}`}
                      />
                    </span>
                  </button>
                );
              })()
            ))}
          </div>
        </div>

        <div className="flex flex-1 justify-center">
          <form onSubmit={onSearchSubmit} className="hidden w-full max-w-2xl sm:block">
            <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500/60 focus-within:bg-white dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400/60 dark:focus-within:bg-slate-900">
              <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
              <input
                ref={searchRef}
                type="text"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="Quick jump (Ctrl+K): dashboard, alerts, agents, schedules..."
                className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
              />
            </label>
          </form>
        </div>

        <div className="flex items-center justify-end gap-2">
          <div
            className={`hidden items-center gap-1 rounded-xl border px-2.5 py-2 text-xs font-semibold sm:inline-flex ${
              sessionIsWarning
                ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300'
                : 'border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
            }`}
            title="Session timeout countdown (resets on activity)"
          >
            <FiClock className="text-sm" />
            {timerText}
          </div>

          <div ref={shortcutsRef} className="relative hidden sm:block">
            <button
              type="button"
              onClick={() => setShortcutsOpen((prev) => !prev)}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              title="Keyboard shortcuts"
            >
              <FiCommand className="text-sm" />
              <span className="hidden text-xs font-medium lg:inline">Shortcuts</span>
            </button>

            <div
              className={`absolute right-0 z-40 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/10 transition dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40 ${
                shortcutsOpen ? 'translate-y-0 opacity-100' : 'pointer-events-none -translate-y-1 opacity-0'
              }`}
            >
              <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                Quick Navigation
              </p>
              <div className="space-y-1">
                {SHORTCUTS.map((item) => (
                  <button
                    key={item.to}
                    type="button"
                    onClick={() => {
                      setShortcutsOpen(false);
                      navigateTo(item.to);
                    }}
                    className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm text-slate-700 transition hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    <span>{item.label}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      {item.hotkey}
                    </span>
                  </button>
                ))}
              </div>
              <p className="mt-2 px-2 text-[11px] text-slate-500 dark:text-slate-400">Sidebar toggle: Alt+B</p>
            </div>
          </div>

          <button
            type="button"
            onClick={toggle}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
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
