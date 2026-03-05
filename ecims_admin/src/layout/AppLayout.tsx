import { useCallback, useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Container } from '../components/ui/Container';
import { useSessionTimeout } from '../hooks/useSessionTimeout';
import { useAuth } from '../store/AuthContext';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const SIDEBAR_COLLAPSE_STORAGE_KEY = 'ecims_admin_sidebar_collapsed_v1';

const getInitialCollapsed = () => {
  if (typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem(SIDEBAR_COLLAPSE_STORAGE_KEY);
    if (raw === '1') return true;
    if (raw === '0') return false;
  } catch {
    // ignore localStorage failures in restricted environments
  }
  return false;
};

export const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);

  const { token, user, clearSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const sessionTimeoutSeconds = useMemo(
    () => Number(import.meta.env.VITE_SESSION_TIMEOUT_SECONDS ?? 900),
    [],
  );

  const handleLogout = useCallback(
    (reason: 'manual' | 'timeout' = 'manual') => {
      clearSession();
      navigate('/login', {
        replace: true,
        state: reason === 'timeout' ? { reason: 'session-timeout' } : undefined,
      });
    },
    [clearSession, navigate],
  );

  const handleSessionTimeout = useCallback(() => {
    handleLogout('timeout');
  }, [handleLogout]);

  const session = useSessionTimeout({
    enabled: Boolean(token && user),
    timeoutSeconds: sessionTimeoutSeconds,
    warningSeconds: 30,
    onTimeout: handleSessionTimeout,
  });

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_COLLAPSE_STORAGE_KEY, collapsed ? '1' : '0');
    } catch {
      // ignore localStorage failures in restricted environments
    }
  }, [collapsed]);

  useEffect(() => {
    if (!mobileOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [mobileOpen]);

  return (
    <div className="min-h-screen overflow-x-clip bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={toggleCollapse}
      />

      <div className={`app-shell ${collapsed ? 'app-shell-collapsed' : 'app-shell-expanded'}`}>
        <Topbar
          onOpenSidebar={() => setMobileOpen(true)}
          onToggleCollapse={toggleCollapse}
          collapsed={collapsed}
          userName={user?.username ?? 'Operator'}
          userRole={user?.role ?? 'Administrator'}
          sessionRemainingSeconds={session.remainingSeconds}
          sessionIsWarning={session.isWarning}
          onLogout={() => handleLogout('manual')}
        />

        <main className="px-4 py-6 sm:px-6 lg:px-8">
          <Container>
            <div className="rounded-3xl border border-slate-200/80 bg-white/70 p-4 shadow-sm backdrop-blur-sm transition dark:border-slate-800 dark:bg-slate-900/60 sm:p-6">
              <Outlet />
            </div>
          </Container>
        </main>
      </div>

      {Boolean(token && user && session.isWarning) && (
        <>
          <div className="pointer-events-none fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-sm" />
          <div className="pointer-events-none fixed inset-x-0 top-20 z-50 flex justify-center px-4">
            <div className="pointer-events-auto w-full max-w-xl rounded-2xl border border-amber-300 bg-amber-50/95 px-4 py-3 shadow-xl shadow-amber-900/20 dark:border-amber-900 dark:bg-amber-950/90">
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">Session inactivity warning</p>
              <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                Session will close automatically in <span className="font-semibold">{session.remainingSeconds}s</span>. Move mouse, press any key,
                or continue session.
              </p>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={session.resetTimer}
                  className="inline-flex h-8 items-center justify-center rounded-lg border border-amber-400 bg-white px-3 text-xs font-semibold text-amber-700 transition hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-200 dark:hover:bg-amber-900/60"
                >
                  Continue Session
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
