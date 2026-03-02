import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthApi } from '../api/services';
import { useAuth } from '../store/AuthContext';

export const LoginPage = () => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setSession } = useAuth();
  const navigate = useNavigate();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const login = await AuthApi.login(username, password);
      const token = login.data.access_token;
      const me = await AuthApi.me();
      setSession(token, me.data);
      navigate('/');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-surface-900 to-slate-950 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-md rounded-2xl border border-slate-700 bg-surface-800 p-8 shadow-soft">
        <h1 className="mb-2 text-2xl font-semibold text-white">ECIMS Admin Console</h1>
        <p className="mb-6 text-sm text-slate-400">Enterprise Security Operations Portal</p>
        <div className="space-y-4">
          <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" />
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
          {error && <p className="text-sm text-rose-400">{error}</p>}
          <button className="btn w-full bg-indigo-600 text-white" disabled={loading}>{loading ? 'Signing in...' : 'Sign In'}</button>
        </div>
      </form>
    </div>
  );
};
