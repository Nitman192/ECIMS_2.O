import { FiAlertCircle, FiCheckCircle, FiInfo, FiX, FiAlertTriangle } from 'react-icons/fi';

export type ToastTone = 'success' | 'info' | 'warning' | 'error';

export type ToastItem = {
  id: string;
  title: string;
  description?: string;
  tone?: ToastTone;
};

type ToastStackProps = {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
};

const toneMap: Record<ToastTone, { icon: typeof FiCheckCircle; className: string }> = {
  success: { icon: FiCheckCircle, className: 'text-emerald-600 dark:text-emerald-400' },
  info: { icon: FiInfo, className: 'text-cyan-600 dark:text-cyan-400' },
  warning: { icon: FiAlertTriangle, className: 'text-amber-600 dark:text-amber-400' },
  error: { icon: FiAlertCircle, className: 'text-rose-600 dark:text-rose-400' },
};

export const ToastStack = ({ toasts, onDismiss }: ToastStackProps) => {
  if (!toasts.length) return null;

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2 sm:bottom-6 sm:right-6">
      {toasts.map((toast) => {
        const tone = toneMap[toast.tone ?? 'info'];
        const ToneIcon = tone.icon;

        return (
          <div
            key={toast.id}
            className="pointer-events-auto rounded-xl border border-slate-200 bg-white p-3 shadow-lg shadow-slate-900/10 dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40"
            role="status"
          >
            <div className="flex items-start gap-3">
              <ToneIcon className={`mt-0.5 text-base ${tone.className}`} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{toast.title}</p>
                {toast.description && (
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{toast.description}</p>
                )}
              </div>
              <button
                type="button"
                className="inline-flex h-6 w-6 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                onClick={() => onDismiss(toast.id)}
                aria-label="Dismiss"
              >
                <FiX className="text-sm" />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
};

