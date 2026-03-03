import type { ReactNode } from 'react';
import { FiX } from 'react-icons/fi';

type ModalProps = {
  open: boolean;
  title: string;
  description?: string;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  onCancel: () => void;
};

export const Modal = ({
  open,
  title,
  description,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ModalProps) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/55 backdrop-blur-sm"
        onClick={onCancel}
        aria-label="Close dialog"
      />

      <div className="relative z-10 w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
            {description && <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
            aria-label="Close"
          >
            <FiX />
          </button>
        </div>

        {children && <div className="mt-4">{children}</div>}

        <div className="mt-6 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="btn-secondary">
            {cancelLabel}
          </button>
          {onConfirm && (
            <button type="button" onClick={onConfirm} className="btn-primary">
              {confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

