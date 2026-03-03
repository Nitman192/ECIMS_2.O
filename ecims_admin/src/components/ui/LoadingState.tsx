import { Spinner } from './Spinner';

type LoadingStateProps = {
  title?: string;
  description?: string;
};

export const LoadingState = ({
  title = 'Loading workspace',
  description = 'Fetching latest control-plane data.',
}: LoadingStateProps) => {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-slate-50/80 px-6 py-14 text-center dark:border-slate-800 dark:bg-slate-900/70">
      <Spinner label="Loading" />
      <h3 className="mt-4 text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{description}</p>
    </div>
  );
};

