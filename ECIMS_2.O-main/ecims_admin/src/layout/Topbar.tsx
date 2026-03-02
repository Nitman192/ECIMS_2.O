import { useTheme } from '../store/ThemeContext';
import { useAuth } from '../store/AuthContext';

export const Topbar = () => {
  const { theme, toggle } = useTheme();
  const { user, clearSession } = useAuth();
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-surface-800">
      <div className="text-sm text-slate-500 dark:text-slate-300">Security Operations Console</div>
      <div className="flex items-center gap-3">
        <button className="btn bg-slate-100 dark:bg-surface-700" onClick={toggle}>{theme === 'dark' ? '☀' : '☾'}</button>
        <div className="flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-2 text-sm dark:bg-surface-700">👤 {user?.username ?? 'Operator'}</div>
        <button className="btn bg-rose-600 text-white" onClick={clearSession}>Logout</button>
      </div>
    </header>
  );
};
