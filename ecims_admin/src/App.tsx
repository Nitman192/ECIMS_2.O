import { useEffect } from 'react';
import { Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { bindAuthHandlers } from './api/client';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Spinner } from './components/ui/Spinner';
import { AppLayout } from './layout/AppLayout';
import { AdminAuditExplorerPage } from './pages/admin/AdminAuditExplorerPage';
import { AdminFeaturesPage } from './pages/admin/AdminFeaturesPage';
import { AdminRolesPage } from './pages/admin/AdminRolesPage';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { AgentsPage } from './pages/AgentsPage';
import { AlertsPage } from './pages/AlertsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { DashboardPage } from './pages/DashboardPage';
import { LicensePanelPage } from './pages/LicensePanelPage';
import { LoginPage } from './pages/LoginPage';
import { BreakGlassPage } from './pages/ops/BreakGlassPage';
import { ChangeControlPage } from './pages/ops/ChangeControlPage';
import { EnrollmentPage } from './pages/ops/EnrollmentPage';
import { EvidenceVaultPage } from './pages/ops/EvidenceVaultPage';
import { HealthPage } from './pages/ops/HealthPage';
import { PlaybooksPage } from './pages/ops/PlaybooksPage';
import { QuarantinePage } from './pages/ops/QuarantinePage';
import { RemoteActionsPage } from './pages/ops/RemoteActionsPage';
import { SchedulesPage } from './pages/ops/SchedulesPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { SecurityCenterPage } from './pages/SecurityCenterPage';
import { useAuth } from './store/AuthContext';

export const App = () => {
  const { token, clearSession, isInitializing, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    bindAuthHandlers(
      () => token,
      () => {
        clearSession();
        navigate('/login', { replace: true, state: { reason: 'session-expired' } });
      },
    );
  }, [token, clearSession, navigate]);

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-950">
        <Spinner label="Restoring session..." />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="security" element={<SecurityCenterPage />} />
        <Route path="license" element={<LicensePanelPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="auth/reset-password" element={<ResetPasswordPage />} />

        <Route
          path="admin"
          element={
            <ProtectedRoute allowedRoles={['ADMIN']}>
              <Outlet />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="users" replace />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="roles" element={<AdminRolesPage />} />
          <Route path="features" element={<AdminFeaturesPage />} />
          <Route path="audit" element={<AdminAuditExplorerPage />} />
        </Route>

        <Route path="ops">
          <Route index element={<Navigate to="remote-actions" replace />} />
          <Route path="remote-actions" element={<RemoteActionsPage />} />
          <Route path="schedules" element={<SchedulesPage />} />
          <Route path="enrollment" element={<EnrollmentPage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="quarantine" element={<QuarantinePage />} />
          <Route path="evidence-vault" element={<EvidenceVaultPage />} />
          <Route path="playbooks" element={<PlaybooksPage />} />
          <Route path="change-control" element={<ChangeControlPage />} />
          <Route path="break-glass" element={<BreakGlassPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to={isAuthenticated ? '/' : '/login'} replace />} />
    </Routes>
  );
};
