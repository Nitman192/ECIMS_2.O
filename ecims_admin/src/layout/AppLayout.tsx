import { useCallback, useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Container } from '../components/ui/Container';
import { useSessionTimeout } from '../hooks/useSessionTimeout';
import { useAuth } from '../store/AuthContext';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const { token, user, clearSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const sessionTimeoutSeconds = useMemo(
    () => Number(import.meta.env.VITE_SESSION_TIMEOUT_SECONDS ?? 60),
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

  const session = useSessionTimeout({
    enabled: Boolean(token && user),
    timeoutSeconds: sessionTimeoutSeconds,
    warningSeconds: 30,
    onTimeout: () => handleLogout('timeout'),
  });

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
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
    </div>
  );
};
