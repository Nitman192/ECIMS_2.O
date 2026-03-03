// src/layout/AppLayout.tsx
import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Container } from '../components/ui/Container';
import { useAuth } from '../store/AuthContext';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

const SIDEBAR_EXPANDED = 280;
const SIDEBAR_COLLAPSED = 96;

export const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const { user, clearSession } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    clearSession();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={() => setCollapsed((prev) => !prev)}
      />

      <div
        className="transition-[padding-left] duration-300 ease-out lg:pl-[var(--sbw)]"
        style={{ ['--sbw' as any]: `${collapsed ? SIDEBAR_COLLAPSED : SIDEBAR_EXPANDED}px` }}
      >
        <Topbar
          onOpenSidebar={() => setMobileOpen(true)}
          userName={user?.username ?? 'Operator'}
          userRole={user?.role ?? 'Administrator'}
          onLogout={handleLogout}
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
