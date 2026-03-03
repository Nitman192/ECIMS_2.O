import { FiInbox } from 'react-icons/fi';

type EmptyStateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
};

export const EmptyState = ({ title, description, actionLabel, onAction }: EmptyStateProps) => {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300/80 bg-slate-50/80 px-6 py-14 text-center dark:border-slate-700 dark:bg-slate-900/70">
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
        <FiInbox className="text-lg" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-2 max-w-xl text-sm text-slate-500 dark:text-slate-400">{description}</p>
      {actionLabel && onAction && (
        <button type="button" onClick={onAction} className="btn-primary mt-6">
          {actionLabel}
        </button>
      )}
    </div>
  );
};

