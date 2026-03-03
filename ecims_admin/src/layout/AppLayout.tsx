import { useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Container } from '../components/ui/Container';
import { useAuth } from '../store/AuthContext';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

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
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        onToggleCollapse={() => setCollapsed((prev) => !prev)}
      />

      <div className={`transition-[padding-left] duration-300 ${collapsed ? 'lg:pl-[92px]' : 'lg:pl-[272px]'}`}>
        <Topbar
          onOpenSidebar={() => setMobileOpen(true)}
          userName={user?.username ?? 'Operator'}
          userRole={user?.role ?? 'Administrator'}
          onLogout={handleLogout}
        />
        <main className="px-4 py-6 sm:px-6 lg:px-8">
          <Container>
            <Outlet />
          </Container>
        </main>
      </div>
    </div>
  );
};
