import { useCallback, useEffect, useState } from 'react';
import { FiRefreshCw } from 'react-icons/fi';
import { CoreApi } from '../api/services';
import { getApiErrorMessage } from '../api/utils';
import { Card } from '../components/ui/Card';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { PageHeader } from '../components/ui/PageHeader';

type SecurityStatus = {
  policy_mode?: string;
  mtls_required?: boolean;
  data_encryption_enabled?: boolean;
  data_keyring_loaded?: boolean;
};

const formatValue = (value: unknown): string => {
  if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled';
  if (typeof value === 'string') return value;
  if (typeof value === 'number') return String(value);
  return '-';
};

export const SecurityCenterPage = () => {
  const [security, setSecurity] = useState<SecurityStatus | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  const loadSecurityStatus = useCallback(async () => {
    setStatus('loading');
    setErrorMessage('');

    try {
      const response = await CoreApi.securityStatus();
      setSecurity((response.data ?? null) as SecurityStatus | null);
      setStatus('ready');
    } catch (error: unknown) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to load security status'));
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    void loadSecurityStatus();
  }, [loadSecurityStatus]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Security Center"
        subtitle="Inspect hardening status, policy mode, and cryptographic readiness from backend control plane."
        action={
          <button type="button" className="btn-secondary" onClick={() => void loadSecurityStatus()}>
            <FiRefreshCw className="mr-2 text-sm" />
            Refresh
          </button>
        }
      />

      {status === 'loading' && (
        <LoadingState title="Loading security posture" description="Fetching latest platform security signals." />
      )}

      {status === 'error' && <ErrorState description={errorMessage} onRetry={() => void loadSecurityStatus()} />}

      {status === 'ready' && security && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Card>
            <p className="text-sm text-slate-500 dark:text-slate-300">Policy Mode</p>
            <p className="mt-2 text-lg font-semibold">{formatValue(security.policy_mode)}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-500 dark:text-slate-300">mTLS Required</p>
            <p className="mt-2 text-lg font-semibold">{formatValue(security.mtls_required)}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-500 dark:text-slate-300">Storage Encryption</p>
            <p className="mt-2 text-lg font-semibold">{formatValue(security.data_encryption_enabled)}</p>
          </Card>
          <Card>
            <p className="text-sm text-slate-500 dark:text-slate-300">Keyring Loaded</p>
            <p className="mt-2 text-lg font-semibold">{formatValue(security.data_keyring_loaded)}</p>
          </Card>
        </div>
      )}
    </div>
  );
};
