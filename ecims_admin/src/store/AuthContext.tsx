import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { api } from '../api/client';
import type { User } from '../types';

type AuthCtx = {
  token: string | null;
  user: User | null;
  isInitializing: boolean;
  isAuthenticated: boolean;
  setSession: (token: string, user: User) => void;
  clearSession: () => void;
};

type PersistedSession = {
  token: string;
  user: User | null;
};

const SESSION_STORAGE_KEY = 'ecims_admin_session_v1';

const AuthContext = createContext<AuthCtx | null>(null);

const readPersistedSession = (): PersistedSession | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<PersistedSession>;
    if (typeof parsed.token !== 'string' || parsed.token.length === 0) return null;
    return {
      token: parsed.token,
      user: parsed.user ?? null,
    };
  } catch {
    return null;
  }
};

const persistSession = (payload: PersistedSession) => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
};

const clearPersistedSession = () => {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const hasRestoredRef = useRef(false);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
    clearPersistedSession();
  }, []);

  const setSession = useCallback((nextToken: string, nextUser: User) => {
    setToken(nextToken);
    setUser(nextUser);
    persistSession({ token: nextToken, user: nextUser });
  }, []);

  useEffect(() => {
    if (hasRestoredRef.current) return;
    hasRestoredRef.current = true;

    const persisted = readPersistedSession();
    if (!persisted) {
      setIsInitializing(false);
      return;
    }

    setToken(persisted.token);
    if (persisted.user) {
      setUser(persisted.user);
    }

    let canceled = false;
    void api
      .get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${persisted.token}` },
      })
      .then((response) => {
        if (canceled) return;
        setUser(response.data);
        persistSession({ token: persisted.token, user: response.data });
      })
      .catch(() => {
        if (canceled) return;
        clearSession();
      })
      .finally(() => {
        if (canceled) return;
        setIsInitializing(false);
      });

    return () => {
      canceled = true;
    };
  }, [clearSession]);

  const value = useMemo(
    () => ({
      token,
      user,
      isInitializing,
      isAuthenticated: Boolean(token && user),
      setSession,
      clearSession,
    }),
    [token, user, isInitializing, setSession, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used in provider');
  return ctx;
};
