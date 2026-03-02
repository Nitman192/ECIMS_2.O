import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export const AppLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <div className="flex min-h-screen bg-slate-100 text-slate-900 dark:bg-surface-900 dark:text-slate-100">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 p-6"><Outlet /></main>
      </div>
    </div>
  );
};
