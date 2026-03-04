import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';

type ProtectedRouteProps = {
  children: JSX.Element;
  allowedRoles?: string[];
};

export const ProtectedRoute = ({ children, allowedRoles }: ProtectedRouteProps) => {
  const { token, user } = useAuth();
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  const isPasswordResetRoute = location.pathname === '/auth/reset-password';
  if (user?.must_reset_password && !isPasswordResetRoute) {
    return <Navigate to="/auth/reset-password" replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
};
