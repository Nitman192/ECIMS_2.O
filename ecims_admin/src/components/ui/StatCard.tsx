import type { IconType } from 'react-icons';
import { FiArrowDownRight, FiArrowUpRight, FiMinus } from 'react-icons/fi';
import { Card } from './Card';

type Trend = 'up' | 'down' | 'neutral';

type StatCardProps = {
  label: string;
  value: string;
  trendLabel: string;
  trend: Trend;
  icon: IconType;
};

const trendMap: Record<Trend, { icon: typeof FiArrowUpRight; className: string }> = {
  up: {
    icon: FiArrowUpRight,
    className: 'text-emerald-600 dark:text-emerald-400'
  },
  down: {
    icon: FiArrowDownRight,
    className: 'text-rose-600 dark:text-rose-400'
  },
  neutral: {
    icon: FiMinus,
    className: 'text-slate-500 dark:text-slate-400'
  }
};

export const StatCard = ({ label, value, trendLabel, trend, icon: Icon }: StatCardProps) => {
  const trendMeta = trendMap[trend];
  const TrendIcon = trendMeta.icon;

  return (
    <Card className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-sm text-slate-500 dark:text-slate-400">{label}</p>
          <p className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{value}</p>
          <p className={`inline-flex items-center gap-1 text-xs font-medium ${trendMeta.className}`}>
            <TrendIcon className="text-sm" />
            {trendLabel}
          </p>
        </div>
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
          <Icon className="text-lg" />
        </div>
      </div>
    </Card>
  );
};
