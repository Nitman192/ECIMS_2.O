import type { ReactNode } from 'react';
import { Card } from './ui/Card';

type DataTableColumn<T> = {
  key: keyof T | string;
  header: string;
  render?: (row: T) => ReactNode;
  className?: string;
};

type DataTableProps<T> = {
  title?: string;
  subtitle?: string;
  columns: DataTableColumn<T>[];
  rows: T[];
  emptyText?: string;
};

export const DataTable = <T extends Record<string, ReactNode>>({
  title,
  subtitle,
  columns,
  rows,
  emptyText = 'No data available'
}: DataTableProps<T>) => {
  return (
    <Card title={title} subtitle={subtitle} className="overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead className="bg-slate-50 dark:bg-slate-800/70">
            <tr>
              {columns.map((column) => (
                <th
                  key={String(column.key)}
                  className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 ${column.className ?? ''}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td
                  className="px-4 py-12 text-center text-sm text-slate-500 dark:text-slate-400"
                  colSpan={columns.length}
                >
                  {emptyText}
                </td>
              </tr>
            )}
            {rows.map((row, rowIndex) => (
              <tr
                key={`row-${rowIndex}`}
                className="border-t border-slate-200/80 transition hover:bg-slate-50 dark:border-slate-800/80 dark:hover:bg-slate-800/30"
              >
                {columns.map((column) => (
                  <td
                    key={`${String(column.key)}-${rowIndex}`}
                    className={`px-4 py-3 text-sm text-slate-700 dark:text-slate-300 ${column.className ?? ''}`}
                  >
                    {column.render ? column.render(row) : row[column.key as keyof T]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};
