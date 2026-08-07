'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { apiMe, TOKEN_KEY, UserResponse } from './api';

interface AuthState {
  token: string;
  user: UserResponse | null;
  loading: boolean;
  setToken: (t: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthState>({
  token: '',
  user: null,
  loading: true,
  setToken: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState('');
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const setToken = useCallback((t: string) => {
    setTokenState(t);
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    setTokenState('');
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
  }, []);

  // Bootstrap from localStorage
  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) {
      setTokenState(saved);
      apiMe(saved)
        .then(setUser)
        .catch(() => {
          // Token stale — clear
          localStorage.removeItem(TOKEN_KEY);
          setTokenState('');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  // Fetch user whenever token changes (login / register flow)
  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    apiMe(token)
      .then(setUser)
      .catch(() => setUser(null));
  }, [token]);

  return (
    <AuthContext.Provider value={{ token, user, loading, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
