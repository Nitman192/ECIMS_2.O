import { useEffect, useState } from 'react';
import { CoreApi } from '../api/services';

export const SecurityCenterPage = () => {
  const [security, setSecurity] = useState<any>(null);
  useEffect(() => { CoreApi.securityStatus().then((r) => setSecurity(r.data)); }, []);
  return <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{[
    ['Policy mode', security?.policy_mode],
    ['mTLS required', String(security?.mtls_required)],
    ['Storage encryption', String(security?.data_encryption_enabled ?? 'unknown')],
    ['Keyring loaded', String(security?.data_keyring_loaded ?? 'unknown')]
  ].map(([k, v]) => <div key={k} className="card"><p className="text-sm text-slate-500 dark:text-slate-300">{k}</p><p className="mt-2 text-lg font-semibold">{v || '-'}</p></div>)}</div>;
};
