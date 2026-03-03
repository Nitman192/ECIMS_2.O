type SpinnerProps = {
  label?: string;
};

export const Spinner = ({ label = 'Loading...' }: SpinnerProps) => {
  return (
    <div className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900 dark:border-slate-600 dark:border-t-slate-100" />
      {label}
    </div>
  );
};
