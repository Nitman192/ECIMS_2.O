import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { CoreApi } from '../api/services';
import { normalizeListResponse } from '../api/utils';
import { Container } from '../components/ui/Container';
import { Modal } from '../components/ui/Modal';
import { useSessionTimeout } from '../hooks/useSessionTimeout';
import { useAuth } from '../store/AuthContext';
import type { Alert } from '../types';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const SIDEBAR_COLLAPSE_STORAGE_KEY = 'ecims_admin_sidebar_collapsed_v1';

const isCriticalUsbAlert = (alert: Alert): boolean => {
  const severity = String(alert.severity || '').toUpperCase();
  if (severity !== 'RED') return false;
  const alertType = String(alert.alert_type || '').toUpperCase();
  const message = String(alert.message || '').toLowerCase();
  return alertType.includes('USB') || message.includes('usb') || message.includes('mass-storage') || message.includes('mass storage');
};

const playCriticalAlarmTone = () => {
  const AudioCtx = window.AudioContext;
  if (!AudioCtx) return;
  try {
    const ctx = new AudioCtx();
    const pattern = [920, 640, 980];
    pattern.forEach((freq, index) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.value = freq;
      gain.gain.value = 0.0001;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const start = ctx.currentTime + index * 0.16;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.18, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.14);
      osc.start(start);
      osc.stop(start + 0.15);
    });
    window.setTimeout(() => {
      void ctx.close();
    }, 1200);
  } catch {
    // ignore audio errors caused by browser autoplay restrictions
  }
};

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
  const [criticalUsbAlert, setCriticalUsbAlert] = useState<Alert | null>(null);
  const lastSeenAlertIdRef = useRef<number>(0);

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

  useEffect(() => {
    if (!token || !user) {
      lastSeenAlertIdRef.current = 0;
      setCriticalUsbAlert(null);
      return;
    }

    let cancelled = false;

    const pollAlerts = async (initial: boolean) => {
      try {
        const response = await CoreApi.alerts();
        if (cancelled) return;
        const alerts = normalizeListResponse<Alert>(response.data);
        const latestId = alerts.reduce((acc, item) => Math.max(acc, Number(item.id) || 0), 0);

        if (initial && lastSeenAlertIdRef.current === 0) {
          lastSeenAlertIdRef.current = latestId;
          return;
        }

        const newCritical = alerts
          .filter((item) => (Number(item.id) || 0) > lastSeenAlertIdRef.current)
          .filter(isCriticalUsbAlert)
          .sort((left, right) => (Number(right.id) || 0) - (Number(left.id) || 0));

        if (newCritical.length > 0) {
          setCriticalUsbAlert(newCritical[0]);
          playCriticalAlarmTone();
        }

        if (latestId > lastSeenAlertIdRef.current) {
          lastSeenAlertIdRef.current = latestId;
        }
      } catch {
        // polling should stay silent on transient API errors
      }
    };

    void pollAlerts(true);
    const timer = window.setInterval(() => {
      void pollAlerts(false);
    }, 7000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [token, user]);

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

      <Modal
        open={Boolean(criticalUsbAlert)}
        title="Critical USB Security Incident"
        description={criticalUsbAlert?.message ?? 'Mass-storage activity detected on a protected endpoint.'}
        confirmLabel="Open Alerts"
        cancelLabel="Acknowledge"
        onConfirm={() => {
          setCriticalUsbAlert(null);
          navigate('/alerts');
        }}
        onCancel={() => setCriticalUsbAlert(null)}
      >
        <div className="rounded-xl border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200">
          Mass-storage detected. Endpoint containment workflow triggered. Verify secure declare or one-time unlock action.
        </div>
      </Modal>
    </div>
  );
};
