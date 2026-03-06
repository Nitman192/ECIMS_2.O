import { Suspense, lazy, useEffect } from 'react';
import { Navigate, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import { bindAuthHandlers } from './api/client';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Spinner } from './components/ui/Spinner';
import { useAuth } from './store/AuthContext';

const AppLayout = lazy(() => import('./layout/AppLayout').then((module) => ({ default: module.AppLayout })));
const LoginPage = lazy(() => import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })));
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })));
const AgentsPage = lazy(() => import('./pages/AgentsPage').then((module) => ({ default: module.AgentsPage })));
const AlertsPage = lazy(() => import('./pages/AlertsPage').then((module) => ({ default: module.AlertsPage })));
const SecurityCenterPage = lazy(() =>
  import('./pages/SecurityCenterPage').then((module) => ({ default: module.SecurityCenterPage })),
);
const LicensePanelPage = lazy(() => import('./pages/LicensePanelPage').then((module) => ({ default: module.LicensePanelPage })));
const AuditLogsPage = lazy(() => import('./pages/AuditLogsPage').then((module) => ({ default: module.AuditLogsPage })));
const ResetPasswordPage = lazy(() =>
  import('./pages/ResetPasswordPage').then((module) => ({ default: module.ResetPasswordPage })),
);
const AdminUsersPage = lazy(() => import('./pages/admin/AdminUsersPage').then((module) => ({ default: module.AdminUsersPage })));
const AdminRolesPage = lazy(() => import('./pages/admin/AdminRolesPage').then((module) => ({ default: module.AdminRolesPage })));
const AdminFeaturesPage = lazy(() =>
  import('./pages/admin/AdminFeaturesPage').then((module) => ({ default: module.AdminFeaturesPage })),
);
const AdminAuditExplorerPage = lazy(() =>
  import('./pages/admin/AdminAuditExplorerPage').then((module) => ({ default: module.AdminAuditExplorerPage })),
);
const RemoteActionsPage = lazy(() =>
  import('./pages/ops/RemoteActionsPage').then((module) => ({ default: module.RemoteActionsPage })),
);
const SchedulesPage = lazy(() => import('./pages/ops/SchedulesPage').then((module) => ({ default: module.SchedulesPage })));
const EnrollmentPage = lazy(() => import('./pages/ops/EnrollmentPage').then((module) => ({ default: module.EnrollmentPage })));
const HealthPage = lazy(() => import('./pages/ops/HealthPage').then((module) => ({ default: module.HealthPage })));
const QuarantinePage = lazy(() => import('./pages/ops/QuarantinePage').then((module) => ({ default: module.QuarantinePage })));
const EvidenceVaultPage = lazy(() =>
  import('./pages/ops/EvidenceVaultPage').then((module) => ({ default: module.EvidenceVaultPage })),
);
const PlaybooksPage = lazy(() => import('./pages/ops/PlaybooksPage').then((module) => ({ default: module.PlaybooksPage })));
const ChangeControlPage = lazy(() =>
  import('./pages/ops/ChangeControlPage').then((module) => ({ default: module.ChangeControlPage })),
);
const BreakGlassPage = lazy(() => import('./pages/ops/BreakGlassPage').then((module) => ({ default: module.BreakGlassPage })));
const PatchUpdatesPage = lazy(() =>
  import('./pages/ops/PatchUpdatesPage').then((module) => ({ default: module.PatchUpdatesPage })),
);

const PageLoadingState = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-950">
    <Spinner label="Loading page..." />
  </div>
);

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
    <Suspense fallback={<PageLoadingState />}>
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
            <Route path="patch-updates" element={<PatchUpdatesPage />} />
            <Route path="break-glass" element={<BreakGlassPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to={isAuthenticated ? '/' : '/login'} replace />} />
      </Routes>
    </Suspense>
  );
};
