import { createContext, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { User } from '../types';

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

  const value = useMemo(() => ({
    token,
    user,
    setSession: (nextToken: string, nextUser: User) => {
      setToken(nextToken);
      setUser(nextUser);
    },
    clearSession: () => {
      setToken(null);
      setUser(null);
    }
  }), [token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used in provider');
  return ctx;
};
