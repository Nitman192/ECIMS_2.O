import { useCallback, useEffect, useRef, useState } from 'react';
import type { ToastItem } from '../components/ui/Toast';

type UseToastStackOptions = {
  durationMs?: number;
};

type ToastInput = Omit<ToastItem, 'id'>;

export const useToastStack = (options: UseToastStackOptions = {}) => {
  const { durationMs = 4000 } = options;
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timersRef = useRef<Record<string, number>>({});

  const dismissToast = useCallback((id: string) => {
    const timeoutId = timersRef.current[id];
    if (typeof timeoutId === 'number') {
      window.clearTimeout(timeoutId);
      delete timersRef.current[id];
    }
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: ToastInput) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      setToasts((prev) => [...prev, { ...toast, id }]);
      timersRef.current[id] = window.setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
        delete timersRef.current[id];
      }, durationMs);
      return id;
    },
    [durationMs],
  );

  useEffect(
    () => () => {
      Object.values(timersRef.current).forEach((timeoutId) => window.clearTimeout(timeoutId));
      timersRef.current = {};
    },
    [],
  );

  return { toasts, pushToast, dismissToast };
};
