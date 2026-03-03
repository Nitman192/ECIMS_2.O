import React from 'react';
import { useTable, usePagination, HeaderGroup, Column, Row, Cell } from 'react-table';

export interface PaginatedTableProps<T extends object> {
  readonly columns: Column<T>[];
  readonly data: T[];
  readonly pageCount: number;
  readonly fetchData: ({ pageIndex, pageSize }: { pageIndex: number; pageSize: number }) => void;
  readonly loading: boolean;
}

export function PaginatedTable<T extends object>({
  columns,
  data,
  pageCount,
  fetchData,
  loading,
}: PaginatedTableProps<T>) {
  const tableInstance = useTable<T>(
    {
      columns,
      data,
      manualPagination: true,
      pageCount,
      initialState: { pageIndex: 0, pageSize: 10 } as any,
    } as any,
    usePagination,
  ) as any;

  const {
    getTableProps,
    getTableBodyProps,
    headerGroups,
    prepareRow,
    page,
    canPreviousPage,
    canNextPage,
    pageOptions,
    pageCount: controlledPageCount,
    gotoPage,
    nextPage,
    previousPage,
    setPageSize,
    state: { pageIndex, pageSize },
  } = tableInstance;

  React.useEffect(() => {
    fetchData({ pageIndex, pageSize });
  }, [fetchData, pageIndex, pageSize]);

  let tableBody;
  if (loading) {
    tableBody = (
      <tr>
        <td colSpan={columns.length} className="text-center py-8">
          Loading...
        </td>
      </tr>
    );
  } else if (page.length === 0) {
    tableBody = (
      <tr>
        <td colSpan={columns.length} className="text-center py-8">
          No data
        </td>
      </tr>
    );
  } else {
    tableBody = page.map((row: Row<T>) => {
      prepareRow(row);
      return (
        <tr {...row.getRowProps()}>
          {row.cells.map((cell: Cell<T>) => (
            <td
              {...cell.getCellProps()}
              className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
            >
              {cell.render('Cell')}
            </td>
          ))}
        </tr>
      );
    });
  }

  return (
    <div>
      <table {...getTableProps()} className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          {headerGroups.map((headerGroup: HeaderGroup<T>) => (
            <tr {...headerGroup.getHeaderGroupProps()}>
              {headerGroup.headers.map((column: HeaderGroup<T>['headers'][0]) => (
                <th
                  {...column.getHeaderProps()}
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {column.render('Header')}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody {...getTableBodyProps()} className="bg-white divide-y divide-gray-200">
          {tableBody}
        </tbody>
      </table>
      <div className="flex items-center justify-between py-2">
        <div>
          <button
            onClick={() => gotoPage(0)}
            disabled={!canPreviousPage}
            className="mr-2 px-2 py-1 border rounded disabled:opacity-50"
          >
            {'<<'}
          </button>
          <button
            onClick={() => previousPage()}
            disabled={!canPreviousPage}
            className="mr-2 px-2 py-1 border rounded disabled:opacity-50"
          >
            {'<'}
          </button>
          <button
            onClick={() => nextPage()}
            disabled={!canNextPage}
            className="mr-2 px-2 py-1 border rounded disabled:opacity-50"
          >
            {'>'}
          </button>
          <button
            onClick={() => gotoPage(controlledPageCount - 1)}
            disabled={!canNextPage}
            className="px-2 py-1 border rounded disabled:opacity-50"
          >
            {'>>'}
          </button>
        </div>
        <span>
          Page{' '}
          <strong>
            {pageIndex + 1} of {pageOptions.length}
          </strong>
        </span>
        <select
          className="ml-2 border rounded"
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
        >
          {[10, 20, 30, 40, 50].map((size) => (
            <option key={size} value={size}>
              Show {size}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
