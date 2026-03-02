import { useState } from 'react';

export const useApiError = () => {
  const [error, setError] = useState<string | null>(null);
  const wrap = async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    try {
      setError(null);
      return await fn();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Request failed');
      return null;
    }
  };
  return { error, wrap };
};
