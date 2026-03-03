import React, { useCallback, useMemo, useState } from 'react';
import { PaginatedTable } from './PaginatedTable';
import { CoreApi } from '../api/services';
import type { Alert } from '../types';

export const AlertsPaginatedTable: React.FC = () => {
  const [data, setData] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageCount, setPageCount] = useState(0);
  const fetchData = useCallback(async ({ pageIndex, pageSize }) => {
    setLoading(true);
    try {
      // Example: server should support ?page=1&page_size=10
      const res = await CoreApi.alerts({ params: { page: pageIndex + 1, page_size: pageSize } });
      setData(res.data.results || res.data); // fallback for old API
      setPageCount(res.data.total_pages || 1);
    } finally {
      setLoading(false);
    }
  }, []);

  const columns = useMemo(
    () => [
      { Header: 'ID', accessor: 'id' },
      { Header: 'Severity', accessor: 'severity' },
      { Header: 'Type', accessor: 'alert_type' },
      { Header: 'Message', accessor: 'message' },
      { Header: 'Timestamp', accessor: 'ts' },
      { Header: 'Status', accessor: 'status' },
    ],
    [],
  );

  return (
    <PaginatedTable
      columns={columns}
      data={data}
      pageCount={pageCount}
      fetchData={fetchData}
      loading={loading}
    />
  );
};

export default AlertsPaginatedTable;
