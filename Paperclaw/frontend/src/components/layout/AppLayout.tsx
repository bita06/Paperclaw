import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../../auth/AuthContext";
import { TsinghuaSeal } from "../branding/TsinghuaSeal";

const allNavItems = [
  { to: "/", label: "研究工作台", note: "平台价值与当前进展", roles: ["researcher", "admin", "developer_admin"] },
  { to: "/qa", label: "研究问答", note: "研究助手核心入口", roles: ["researcher", "admin", "developer_admin"] },
  { to: "/library", label: "我的导师库", note: "按研究上下文查看文献", roles: ["researcher", "admin", "developer_admin"] },
  { to: "/papers", label: "文献入库与导师知识库", note: "上传与挂接导师库", roles: ["admin", "developer_admin"] },
  { to: "/advisors", label: "导师档案管理", note: "导师列表、详情与研究方向", roles: ["researcher", "admin", "developer_admin"] },
  { to: "/researchers", label: "研究者档案管理", note: "研究阶段与问题维护", roles: ["admin", "developer_admin"] },
  { to: "/relationships", label: "导师指导关系", note: "关系类型与子领域授权", roles: ["admin", "developer_admin"] },
];

function getRoleLabel(role: string | undefined) {
  if (role === "researcher") {
    return "研究者账号";
  }
  if (role === "admin") {
    return "内部管理员";
  }
  if (role === "developer_admin") {
    return "开发维护账号";
  }
  return "未识别角色";
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const navItems = allNavItems.filter((item) => item.roles.includes(user?.role || "researcher"));

  const handleLogout = async () => {
    await logout();
    navigate("/login", {
      replace: true,
      state: { notice: "您已退出当前账号。" },
    });
  };

  const handleSwitchAccount = async () => {
    await logout();
    navigate("/login", {
      replace: true,
      state: { notice: "请重新登录以切换账号。" },
    });
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-crest">
          <TsinghuaSeal className="sidebar-crest-mark" />
        </div>

        <div className="brand">
          <div className="brand-mark">
            <TsinghuaSeal className="brand-seal" decorative={false} />
          </div>
          <div>
            <div className="brand-title">PaperClaw 清华公管研究辅助平台</div>
            <div className="brand-subtitle">内部版 · 研究工作台与导师知识库</div>
          </div>
        </div>

        <div className="sidebar-block user-panel">
          <div className="sidebar-caption">Account Identity</div>
          <div className="user-name">{user?.name || "未登录用户"}</div>
          <div className="user-role">{getRoleLabel(user?.role)}</div>
          <div className="sidebar-note">{user?.email || "请先登录"}</div>

          <div className="user-panel-actions">
            <button
              type="button"
              className="button secondary logout-button"
              onClick={() => void handleLogout()}
              title="退出当前账号，并返回登录页"
            >
              退出登录
            </button>
            <button
              type="button"
              className="button ghost logout-button"
              onClick={() => void handleSwitchAccount()}
              title="退出当前账号并返回登录页，以便使用其他账号重新登录"
            >
              切换账号
            </button>
          </div>
        </div>

        <div className="sidebar-block">
          <div className="sidebar-caption">Research Navigation</div>
          <nav className="nav">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
              >
                <span className="nav-label">{item.label}</span>
                <span className="nav-note">{item.note}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-note sidebar-context-note">
          {user?.role === "researcher"
            ? "当前为“我的研究上下文”。系统已固定为本人研究档案，不提供切换其他研究者视角的入口。"
            : "当前角色可进入院内配置、演示与维护页面，并可切换研究者上下文进行测试与讲解。"}
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}

