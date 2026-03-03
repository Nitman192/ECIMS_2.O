import { createContext, useContext, useMemo, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { User } from '../types';
import { bindAuthHandlers } from '../api/client';

type AuthCtx = {
  token: string | null;
  user: User | null;
  setSession: (token: string, user: User) => void;
  clearSession: () => void;
};

const AuthContext = createContext<AuthCtx | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  //  Bind interceptor ONLY when token exists
  useEffect(() => {
    if (!token) return;

    bindAuthHandlers(
      () => token,
      () => {
        clearSession();
      }
    );
  }, [token, clearSession]);

  const setSession = useCallback((nextToken: string, nextUser: User) => {
    //  Immediately bind using fresh token (avoid race condition)
    bindAuthHandlers(
      () => nextToken,
      () => {
        clearSession();
      }
    );

    setToken(nextToken);
    setUser(nextUser);
  }, [clearSession]);

  const value = useMemo(
    () => ({
      token,
      user,
      setSession,
      clearSession,
    }),
    [token, user, setSession, clearSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used in provider');
  return ctx;
};