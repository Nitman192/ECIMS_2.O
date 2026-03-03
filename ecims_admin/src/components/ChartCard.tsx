import type { ReactNode } from 'react';
import { Card } from './ui/Card';

type ChartCardProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
};

export const ChartCard = ({ title, subtitle, action, children }: ChartCardProps) => {
  return (
    <Card title={title} subtitle={subtitle} action={action} className="h-full">
      <div className="h-[320px]">{children}</div>
    </Card>
  );
};
