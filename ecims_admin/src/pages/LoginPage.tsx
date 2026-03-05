import { FormEvent, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { bindAuthHandlers } from '../api/client';
import { AuthApi } from '../api/services';
import { useAuth } from '../store/AuthContext';

export const LoginPage = () => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setSession, clearSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const timeoutNotice = useMemo(() => {
    const state = location.state as { reason?: string } | null;
    if (state?.reason === 'session-timeout') {
      return 'Session timed out due to inactivity. Please sign in again.';
    }
    return null;
  }, [location.state]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const loginRes = await AuthApi.login(username, password);
      const token = loginRes.data.access_token;

      bindAuthHandlers(
        () => token,
        () => {
          clearSession();
          navigate('/login', { replace: true });
        },
      );

      const me = await AuthApi.me();
      setSession(token, me.data);

      if (me.data.must_reset_password) {
        navigate('/auth/reset-password', { replace: true });
      } else {
        navigate('/', { replace: true });
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-900 to-slate-950 p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border border-slate-700 bg-surface-800 p-8 shadow-soft"
      >
        <h1 className="mb-2 text-2xl font-semibold text-white">ECIMS 2.0 Admin Console</h1>
        <p className="mb-6 text-sm text-slate-400">Endpoint Configuration Incident Mgmt Sys</p>
        <div className="space-y-4">
          {timeoutNotice && (
            <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              {timeoutNotice}
            </p>
          )}
          <input
            className="input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Username"
          />
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
          />
          {error && <p className="text-sm text-rose-400">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </div>
      </form>
    </div>
  );
};
