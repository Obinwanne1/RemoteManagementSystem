import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User } from '../api/types';
import api from '../api/client';

interface AuthState {
  token: string | null;
  user: User | null;
  login: (email: string, password: string) => Promise<{ mfaRequired?: boolean; mfaToken?: string; error?: string }>;
  mfaLogin: (mfaToken: string, code: string) => Promise<{ error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'));
  const [user, setUser] = useState<User | null>(null);

  // Load user profile when token exists
  useEffect(() => {
    if (token && !user) {
      api.get('/auth/me').then((r) => setUser(r.data)).catch(() => logout());
    }
  }, [token, user, logout]);

  const _storeTokens = (access: string, refresh: string, userData: User) => {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    setToken(access);
    setUser(userData);
  };

  const login = useCallback(async (email: string, password: string) => {
    try {
      const res = await api.post('/auth/login', { email, password });
      const data = res.data;
      if (data.status === 'mfa_required') {
        return { mfaRequired: true, mfaToken: data.mfa_token };
      }
      _storeTokens(data.access_token, data.refresh_token, data.user);
      return {};
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Login failed';
      return { error: msg };
    }
  }, []);

  const mfaLogin = useCallback(async (mfaToken: string, code: string) => {
    try {
      const res = await api.post('/auth/mfa/login', { mfa_token: mfaToken, code });
      _storeTokens(res.data.access_token, res.data.refresh_token, res.data.user);
      return {};
    } catch (err: any) {
      return { error: err.response?.data?.error || 'Invalid code' };
    }
  }, []);

  const logout = useCallback(() => {
    api.post('/auth/logout').catch(() => {});
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, mfaLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// oxlint-disable-next-line react/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
