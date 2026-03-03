import type { ReactNode } from 'react';
import { Card } from './Card';

type ChartContainerProps = {
  title: string;
  subtitle?: string;
  children?: ReactNode;
};

export const ChartContainer = ({ title, subtitle, children }: ChartContainerProps) => {
  return (
    <Card title={title} subtitle={subtitle} className="h-full">
      {children ?? (
        <div className="grid h-72 place-items-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-400">
          Chart Placeholder
        </div>
      )}
    </Card>
  );
};
