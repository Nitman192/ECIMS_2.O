import React, { useCallback, useMemo, useState } from 'react';
import { PaginatedTable } from './PaginatedTable';
import { CoreApi } from '../api/services';
import type { Agent } from '../types';

export const AgentsPaginatedTable: React.FC = () => {
  const [data, setData] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageCount, setPageCount] = useState(0);
  const fetchData = useCallback(async ({ pageIndex, pageSize }) => {
    setLoading(true);
    try {
      // Example: server should support ?page=1&page_size=10
      const res = await CoreApi.agents({ params: { page: pageIndex + 1, page_size: pageSize } });
      setData(res.data.results || res.data); // fallback for old API
      setPageCount(res.data.total_pages || 1);
    } finally {
      setLoading(false);
    }
  }, []);

  const columns = useMemo(
    () => [
      { Header: 'ID', accessor: 'id' },
      { Header: 'Hostname', accessor: 'hostname' },
      { Header: 'Mode', accessor: 'device_mode_override' },
      { Header: 'Last Seen', accessor: 'last_seen' },
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

export default AgentsPaginatedTable;
