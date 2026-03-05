import { useMemo, useState } from 'react';
import { FiFilter, FiPlus, FiRefreshCw, FiSearch } from 'react-icons/fi';
import { DataTable, type DataTableColumn } from '../DataTable';
import { Card } from '../ui/Card';
import { EmptyState } from '../ui/EmptyState';
import { ErrorState } from '../ui/ErrorState';
import { LoadingState } from '../ui/LoadingState';
import { Modal } from '../ui/Modal';
import { PageHeader } from '../ui/PageHeader';
import { ToastStack, type ToastItem } from '../ui/Toast';
import type { DataStatus } from '../../types/adminOps';

type FilterOption = {
  label: string;
  value: string;
};

type FilterControl = {
  key: string;
  label: string;
  options: FilterOption[];
};

type OpsWorkspacePageProps<T> = {
  title: string;
  subtitle: string;
  primaryActionLabel: string;
  primaryActionDescription: string;
  secondaryActionLabel?: string;
  searchPlaceholder: string;
  filters: FilterControl[];
  columns: Array<DataTableColumn<T>>;
  rows: T[];
  rowKey: (row: T, index: number) => string;
  status?: DataStatus;
  errorMessage?: string;
  emptyStateTitle: string;
  emptyStateDescription: string;
};

export const OpsWorkspacePage = <T,>({
  title,
  subtitle,
  primaryActionLabel,
  primaryActionDescription,
  secondaryActionLabel = 'Refresh',
  searchPlaceholder,
  filters,
  columns,
  rows,
  rowKey,
  status = 'ready',
  errorMessage = 'Unable to load data. Check connectivity and retry.',
  emptyStateTitle,
  emptyStateDescription,
}: OpsWorkspacePageProps<T>) => {
  const [query, setQuery] = useState('');
  const [selectedFilters, setSelectedFilters] = useState<Record<string, string>>(() =>
    filters.reduce<Record<string, string>>((acc, filter) => {
      acc[filter.key] = filter.options[0]?.value ?? '';
      return acc;
    }, {}),
  );
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return rows.filter((row) => {
      const record = row as Record<string, unknown>;

      const matchesQuery =
        !normalizedQuery ||
        Object.values(record).some((value) => String(value ?? '').toLowerCase().includes(normalizedQuery));

      const matchesFilters = filters.every((filter) => {
        const selectedValue = selectedFilters[filter.key];
        if (!selectedValue || selectedValue === 'all') return true;
        const fieldValue = String(record[filter.key] ?? '').toLowerCase();
        return fieldValue === selectedValue.toLowerCase();
      });

      return matchesQuery && matchesFilters;
    });
  }, [rows, query, filters, selectedFilters]);

  const pushToast = (toast: Omit<ToastItem, 'id'>) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setToasts((prev) => [...prev, { ...toast, id }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== id));
    }, 3500);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  const triggerPlaceholderAction = () => {
    setConfirmOpen(false);
    pushToast({
      title: `${primaryActionLabel} queued`,
      description: 'Action template triggered. Connect this control to your target API workflow.',
      tone: 'info',
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={title}
        subtitle={subtitle}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => pushToast({ title: `${secondaryActionLabel} completed`, tone: 'success' })}
            >
              <FiRefreshCw className="mr-2 text-sm" />
              {secondaryActionLabel}
            </button>
            <button type="button" className="btn-primary" onClick={() => setConfirmOpen(true)}>
              <FiPlus className="mr-2 text-sm" />
              {primaryActionLabel}
            </button>
          </div>
        }
      />

      <Card>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_auto_auto]">
          <label className="group flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 transition focus-within:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-cyan-400">
            <FiSearch className="text-slate-400 transition group-focus-within:text-cyan-600 dark:group-focus-within:text-cyan-400" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent text-sm text-slate-700 placeholder:text-slate-400 outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
            />
          </label>

          {filters.map((filter) => (
            <label key={filter.key} className="relative">
              <span className="sr-only">{filter.label}</span>
              <FiFilter className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <select
                value={selectedFilters[filter.key] ?? ''}
                onChange={(event) =>
                  setSelectedFilters((prev) => ({
                    ...prev,
                    [filter.key]: event.target.value,
                  }))
                }
                className="h-11 min-w-[180px] appearance-none rounded-xl border border-slate-200 bg-white pl-9 pr-9 text-sm text-slate-700 outline-none transition focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:focus:border-cyan-400"
              >
                {filter.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </Card>

      <Card title={`${title} Workspace`} subtitle="Designed for production data wiring with validation, RBAC, and audit-ready workflows.">
        {status === 'loading' && <LoadingState />}
        {status === 'error' && (
          <ErrorState
            description={errorMessage}
            onRetry={() => pushToast({ title: 'Retry triggered', tone: 'info' })}
          />
        )}
        {status === 'ready' && filteredRows.length > 0 && (
          <DataTable columns={columns} rows={filteredRows} rowKey={rowKey} />
        )}
        {status === 'ready' && filteredRows.length === 0 && (
          <EmptyState
            title={emptyStateTitle}
            description={emptyStateDescription}
            actionLabel={primaryActionLabel}
            onAction={() => setConfirmOpen(true)}
          />
        )}
      </Card>

      <Modal
        open={confirmOpen}
        title={primaryActionLabel}
        description={primaryActionDescription}
        confirmLabel="Continue"
        cancelLabel="Cancel"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={triggerPlaceholderAction}
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          This action template is ready for integration with validation, idempotency, and audit-ready backend handlers.
        </p>
      </Modal>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

