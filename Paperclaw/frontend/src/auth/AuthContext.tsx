import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { authApi } from "../api/auth";
import { ApiError } from "../api/client";
import type { CurrentUser, LoginPayload, UserRole } from "../types/auth";
import { clearStoredAppState, getStoredToken, setStoredToken } from "./storage";

type AuthContextValue = {
  user: CurrentUser | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<CurrentUser>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
  isPrivileged: boolean;
  hasRole: (...roles: UserRole[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const clearLocalAuthState = () => {
    clearStoredAppState();
    setToken(null);
    setUser(null);
  };

  const logout = async () => {
    if (getStoredToken()) {
      try {
        await authApi.logout();
      } catch {
        // JWT MVP: local cleanup remains the source of truth for sign-out.
      }
    }
    clearLocalAuthState();
  };

  const refreshMe = async () => {
    if (!getStoredToken()) {
      setUser(null);
      return;
    }

    try {
      const profile = await authApi.me();
      setUser(profile);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearLocalAuthState();
        return;
      }
      throw error;
    }
  };

  useEffect(() => {
    void (async () => {
      try {
        await refreshMe();
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    const handleAuthExpired = () => {
      clearLocalAuthState();
    };

    window.addEventListener("paperclaw:auth-expired", handleAuthExpired);
    return () => window.removeEventListener("paperclaw:auth-expired", handleAuthExpired);
  }, []);

  const login = async (payload: LoginPayload) => {
    const result = await authApi.login(payload);
    setStoredToken(result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    return result.user;
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      isAuthenticated: Boolean(user && token),
      login,
      logout,
      refreshMe,
      isPrivileged: user?.role === "admin" || user?.role === "developer_admin",
      hasRole: (...roles: UserRole[]) => Boolean(user && roles.includes(user.role)),
    }),
    [loading, token, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
