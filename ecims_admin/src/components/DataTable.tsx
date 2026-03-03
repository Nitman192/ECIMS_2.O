// src/components/DataTable.tsx
import type { ReactNode } from 'react';

type Column<T> = {
  key: keyof T | string;
  header: string;
  className?: string;
  render?: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: Array<Column<T>>;
  rows: T[];
  rowKey: (row: T, index: number) => string;
  emptyText?: string;
};

export const DataTable = <T,>({
  columns,
  rows,
  rowKey,
  emptyText = 'No records found.',
}: DataTableProps<T>) => {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-950/60">
            <tr>
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  className={`whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 ${column.className ?? ''}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
            {rows.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400"
                >
                  {emptyText}
                </td>
              </tr>
            )}

            {rows.map((row, index) => (
              <tr
                key={rowKey(row, index)}
                className="transition hover:bg-slate-50 dark:hover:bg-slate-800/40"
              >
                {columns.map((column) => (
                  <td
                    key={String(column.key)}
                    className="whitespace-nowrap px-4 py-3 text-sm text-slate-700 dark:text-slate-200"
                  >
                    {column.render
                      ? column.render(row)
                      : String((row as Record<string, unknown>)[String(column.key)] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
