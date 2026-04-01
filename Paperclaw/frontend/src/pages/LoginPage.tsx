import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { TsinghuaSeal } from "../components/branding/TsinghuaSeal";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated, user } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const notice = (location.state as { notice?: string } | null)?.notice ?? "";

  useEffect(() => {
    if (isAuthenticated && user) {
      navigate(user.role === "researcher" ? "/qa" : "/", { replace: true });
    }
  }, [isAuthenticated, navigate, user]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const loggedInUser = await login({ identifier, password });
      const nextPath = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(nextPath || (loggedInUser.role === "researcher" ? "/qa" : "/"), { replace: true });
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(cause.detail);
      } else {
        setError(String(cause));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-mark">
          <TsinghuaSeal className="auth-seal" decorative={false} />
        </div>
        <h1>PaperClaw 内部平台</h1>
        <p>
          先登录，再进入研究工作台。普通研究者将自动进入自己的研究上下文；管理员和开发维护账号可继续进入配置与演示页面。
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="field">
            <label>邮箱或学号</label>
            <input value={identifier} onChange={(event) => setIdentifier(event.target.value)} required />
          </div>
          <div className="field">
            <label>密码</label>
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </div>
          {notice ? <div className="status-notice info">{notice}</div> : null}
          {error ? <div className="status-notice error">{error}</div> : null}
          <button className="button auth-button" type="submit" disabled={submitting}>
            {submitting ? "登录中..." : "登录进入平台"}
          </button>
        </form>
      </div>
    </div>
  );
}
