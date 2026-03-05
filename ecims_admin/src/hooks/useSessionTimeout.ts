import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

type UseSessionTimeoutOptions = {
  enabled: boolean;
  timeoutSeconds: number;
  warningSeconds?: number;
  onTimeout: () => void;
};

const ACTIVITY_EVENTS: Array<keyof WindowEventMap> = [
  'mousemove',
  'mousedown',
  'keydown',
  'touchstart',
  'scroll',
];

export const useSessionTimeout = ({
  enabled,
  timeoutSeconds,
  warningSeconds = 120,
  onTimeout,
}: UseSessionTimeoutOptions) => {
  const safeTimeout = useMemo(() => {
    if (!Number.isFinite(timeoutSeconds)) return 900;
    return Math.min(Math.max(Math.floor(timeoutSeconds), 60), 86400);
  }, [timeoutSeconds]);

  const [remainingSeconds, setRemainingSeconds] = useState(safeTimeout);
  const deadlineRef = useRef<number>(Date.now() + safeTimeout * 1000);
  const timedOutRef = useRef(false);

  const resetTimer = useCallback(() => {
    deadlineRef.current = Date.now() + safeTimeout * 1000;
    timedOutRef.current = false;
  }, [safeTimeout]);

  useEffect(() => {
    if (!enabled) {
      setRemainingSeconds(safeTimeout);
      timedOutRef.current = false;
      return;
    }

    resetTimer();
    setRemainingSeconds(safeTimeout);

    const onActivity = () => {
      deadlineRef.current = Date.now() + safeTimeout * 1000;
    };

    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, onActivity, { passive: true });
    }

    const timer = window.setInterval(() => {
      const remaining = Math.max(Math.ceil((deadlineRef.current - Date.now()) / 1000), 0);
      setRemainingSeconds(remaining);
      if (remaining === 0 && !timedOutRef.current) {
        timedOutRef.current = true;
        onTimeout();
      }
    }, 1000);

    return () => {
      window.clearInterval(timer);
      for (const eventName of ACTIVITY_EVENTS) {
        window.removeEventListener(eventName, onActivity);
      }
    };
  }, [enabled, onTimeout, resetTimer, safeTimeout]);

  return {
    remainingSeconds,
    isWarning: remainingSeconds <= warningSeconds,
    timeoutSeconds: safeTimeout,
    resetTimer,
  };
};
