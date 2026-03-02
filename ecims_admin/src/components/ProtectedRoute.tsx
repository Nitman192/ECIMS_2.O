import { Navigate } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';

export const ProtectedRoute = ({ children }: { children: JSX.Element }) => {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" replace />;
};
