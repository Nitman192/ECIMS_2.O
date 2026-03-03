import type { ReactNode } from 'react';

type PageHeaderProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
};

export const PageHeader = ({ title, subtitle, action }: PageHeaderProps) => {
  return (
    <header className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
};
