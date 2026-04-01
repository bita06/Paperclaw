import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import type { UserRole } from "../types/auth";

export function RequireAuth() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="auth-shell"><div className="auth-card">正在加载登录状态...</div></div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}

export function RequireRole({ roles }: { roles: UserRole[] }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-shell"><div className="auth-card">正在校验权限...</div></div>;
  }

  if (!user || !roles.includes(user.role)) {
    return <Navigate to="/qa" replace />;
  }

  return <Outlet />;
}
