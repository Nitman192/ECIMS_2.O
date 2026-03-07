import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ActivationApi, AuthApi } from '../api/services';
import { getApiErrorMessage } from '../api/utils';
import { useAuth } from '../store/AuthContext';
import type { LicenseActivationStatus, User } from '../types';

type LoginLocationState = {
  reason?: 'session-timeout' | 'session-expired';
  from?: string;
};

export const LoginPage = () => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activationStatus, setActivationStatus] = useState<LicenseActivationStatus | null>(null);
  const [activationLoading, setActivationLoading] = useState(false);
  const [activationBusy, setActivationBusy] = useState(false);
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activationInfo, setActivationInfo] = useState<string | null>(null);
  const [licenseKey, setLicenseKey] = useState('');
  const [requestCode, setRequestCode] = useState('');
  const [verificationId, setVerificationId] = useState('');
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const locationState = useMemo(
    () => (location.state as LoginLocationState | null) ?? null,
    [location.state],
  );

  const timeoutNotice = useMemo(() => {
    if (locationState?.reason === 'session-timeout') {
      return 'Session timed out due to inactivity. Please sign in again.';
    }

    if (locationState?.reason === 'session-expired') {
      return 'Session expired or unauthorized. Please sign in again.';
    }

    return null;
  }, [locationState]);

  const redirectPath = useMemo(() => {
    if (!locationState?.from || locationState.from === '/login') return '/';
    return locationState.from;
  }, [locationState]);

  const activationRequired = Boolean(activationStatus?.activation_required && !activationStatus?.is_activated);

  const refreshActivationStatus = async () => {
    setActivationLoading(true);
    setActivationError(null);
    try {
      const status = await ActivationApi.status();
      setActivationStatus(status.data);
      const pendingRequestCode = status.data?.pending_request?.request_code;
      if (pendingRequestCode) {
        setRequestCode(pendingRequestCode);
      }
    } catch (err: unknown) {
      setActivationStatus(null);
      setActivationError(getApiErrorMessage(err, 'Unable to fetch activation status'));
    } finally {
      setActivationLoading(false);
    }
  };

  useEffect(() => {
    void refreshActivationStatus();
  }, []);

  const submitLicenseKey = async () => {
    const trimmed = licenseKey.trim();
    if (!trimmed) {
      setActivationError('Please paste a license key first.');
      return;
    }

    setActivationBusy(true);
    setActivationError(null);
    setActivationInfo(null);
    try {
      const response = await ActivationApi.importLicenseKey(trimmed);
      const payload = response.data;
      if (payload.request_code) setRequestCode(payload.request_code);
      setActivationInfo('License key accepted. Copy request code into Activation App and generate verification ID.');
      await refreshActivationStatus();
    } catch (err: unknown) {
      setActivationError(getApiErrorMessage(err, 'License key import failed'));
    } finally {
      setActivationBusy(false);
    }
  };

  const issueRequestCode = async () => {
    setActivationBusy(true);
    setActivationError(null);
    setActivationInfo(null);
    try {
      const response = await ActivationApi.issueRequest(true);
      if (response.data.request_code) setRequestCode(response.data.request_code);
      setActivationInfo('New request code generated. Use it in Activation App.');
      await refreshActivationStatus();
    } catch (err: unknown) {
      setActivationError(getApiErrorMessage(err, 'Failed to issue activation request'));
    } finally {
      setActivationBusy(false);
    }
  };

  const submitVerificationId = async () => {
    const trimmed = verificationId.trim();
    if (!trimmed) {
      setActivationError('Please paste verification ID.');
      return;
    }

    setActivationBusy(true);
    setActivationError(null);
    setActivationInfo(null);
    try {
      await ActivationApi.verify(trimmed);
      setVerificationId('');
      setActivationInfo('Server activated successfully. You can now sign in.');
      await refreshActivationStatus();
    } catch (err: unknown) {
      setActivationError(getApiErrorMessage(err, 'Activation verification failed'));
    } finally {
      setActivationBusy(false);
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (activationRequired) {
      setError('Server activation is pending. Complete activation below, then sign in.');
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const loginRes = await AuthApi.login(username.trim(), password);
      const token = loginRes.data.access_token;
      const me = await api.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSession(token, me.data);

      if (me.data.must_reset_password || loginRes.data.must_reset_password) {
        navigate('/auth/reset-password', { replace: true });
      } else {
        navigate(redirectPath, { replace: true });
      }
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, 'Login failed'));
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
          {activationRequired && (
            <div className="space-y-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4">
              <p className="text-sm font-semibold text-amber-200">Server Activation Required</p>
              <p className="text-xs text-amber-100/90">
                Paste license key, generate request code, then paste verification ID from Activation App.
              </p>
              <textarea
                className="input min-h-24 resize-y"
                value={licenseKey}
                onChange={(event) => setLicenseKey(event.target.value)}
                placeholder="Paste license key here"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-ghost flex-1"
                  onClick={() => void submitLicenseKey()}
                  disabled={activationBusy || activationLoading}
                >
                  Import License Key
                </button>
                <button
                  type="button"
                  className="btn-ghost flex-1"
                  onClick={() => void issueRequestCode()}
                  disabled={activationBusy || activationLoading}
                >
                  Generate Request Code
                </button>
              </div>
              <textarea
                className="input min-h-20 resize-y"
                value={requestCode}
                onChange={(event) => setRequestCode(event.target.value)}
                placeholder="Request code (copy to Activation App)"
              />
              <textarea
                className="input min-h-20 resize-y"
                value={verificationId}
                onChange={(event) => setVerificationId(event.target.value)}
                placeholder="Paste verification ID from Activation App"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  className="btn-primary flex-1"
                  onClick={() => void submitVerificationId()}
                  disabled={activationBusy || activationLoading}
                >
                  Verify Activation
                </button>
                <button
                  type="button"
                  className="btn-ghost flex-1"
                  onClick={() => void refreshActivationStatus()}
                  disabled={activationBusy || activationLoading}
                >
                  {activationLoading ? 'Refreshing...' : 'Refresh Status'}
                </button>
              </div>
              {activationInfo && <p className="text-xs text-emerald-300">{activationInfo}</p>}
              {activationError && <p className="text-xs text-rose-300">{activationError}</p>}
            </div>
          )}
          {timeoutNotice && (
            <p className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              {timeoutNotice}
            </p>
          )}
          <input
            className="input"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="Username"
            required
          />
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Password"
            required
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
