import { FiAlertTriangle } from 'react-icons/fi';

type ErrorStateProps = {
  title?: string;
  description: string;
  retryLabel?: string;
  onRetry?: () => void;
};

export const ErrorState = ({
  title = 'Something went wrong',
  description,
  retryLabel = 'Try again',
  onRetry,
}: ErrorStateProps) => {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-6 py-10 text-center dark:border-rose-900/70 dark:bg-rose-950/30">
      <div className="mx-auto mb-4 grid h-11 w-11 place-items-center rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-300">
        <FiAlertTriangle className="text-lg" />
      </div>
      <h3 className="text-lg font-semibold text-rose-700 dark:text-rose-300">{title}</h3>
      <p className="mt-2 text-sm text-rose-600/90 dark:text-rose-200/90">{description}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-secondary mt-5">
          {retryLabel}
        </button>
      )}
    </div>
  );
};

