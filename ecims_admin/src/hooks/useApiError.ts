import { useState } from 'react';
import { getApiErrorMessage } from '../api/utils';

export const useApiError = () => {
  const [error, setError] = useState<string | null>(null);
  const wrap = async <T,>(fn: () => Promise<T>, fallback = 'Request failed'): Promise<T | null> => {
    try {
      setError(null);
      return await fn();
    } catch (e: unknown) {
      setError(getApiErrorMessage(e, fallback));
      return null;
    }
  };
  return { error, wrap };
};
