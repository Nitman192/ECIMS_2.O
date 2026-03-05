import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';
import { Spinner } from './ui/Spinner';

type ProtectedRouteProps = {
  children: JSX.Element;
  allowedRoles?: string[];
};

export const ProtectedRoute = ({ children, allowedRoles }: ProtectedRouteProps) => {
  const { token, user, isInitializing } = useAuth();
  const location = useLocation();

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 dark:bg-slate-950">
        <Spinner label="Loading session..." />
      </div>
    );
  }

  if (!token || !user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }

  const isPasswordResetRoute = location.pathname === '/auth/reset-password';
  if (user.must_reset_password && !isPasswordResetRoute) {
    return <Navigate to="/auth/reset-password" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
};
