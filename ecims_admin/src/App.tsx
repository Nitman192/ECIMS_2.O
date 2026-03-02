import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { bindAuthHandlers } from './api/client';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { AlertsPage } from './pages/AlertsPage';
import { SecurityCenterPage } from './pages/SecurityCenterPage';
import { LicensePanelPage } from './pages/LicensePanelPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { useAuth } from './store/AuthContext';

export const App = () => {
  const { token, clearSession } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    bindAuthHandlers(() => token, () => {
      clearSession();
      navigate('/login', { replace: true });
    });
  }, [token, clearSession, navigate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
      </Route>
      <Route path="*" element={<Navigate to={token ? '/' : '/login'} replace />} />
    </Routes>
  );
};
