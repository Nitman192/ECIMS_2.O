import { useEffect, useState } from 'react';
import { CoreApi } from '../api/services';

export const LicensePanelPage = () => {
  const [license, setLicense] = useState<any>(null);
  useEffect(() => { CoreApi.licenseStatus().then((r) => setLicense(r.data)); }, []);
  return <div className="card"><h2 className="mb-4 text-xl font-semibold">License Panel</h2><div className="grid gap-4 md:grid-cols-2">{[
    ['Org name', license?.org_name || license?.customer_name],
    ['Expiry', license?.expiry_date],
    ['Max agents', license?.max_agents],
    ['AI enabled', String(license?.ai_enabled)]
  ].map(([k, v]) => <div key={k} className="rounded-xl border border-slate-200 p-4 dark:border-slate-700"><p className="text-sm text-slate-500 dark:text-slate-300">{k}</p><p className="mt-2 font-semibold">{v || '-'}</p></div>)}</div></div>;
};
