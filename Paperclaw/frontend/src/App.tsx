import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth, RequireRole } from "./auth/RequireAuth";
import { AppLayout } from "./components/layout/AppLayout";
import { HomePage } from "./pages/HomePage";
import { ResearchQAPage } from "./pages/ResearchQAPage";
import { AdvisorsPage } from "./pages/AdvisorsPage";
import { ResearchersPage } from "./pages/ResearchersPage";
import { RelationshipsPage } from "./pages/RelationshipsPage";
import { PapersPage } from "./pages/PapersPage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<HomePage />} />
          <Route path="qa" element={<ResearchQAPage />} />
          <Route path="library" element={<PapersPage variant="library" />} />
          <Route path="advisors" element={<AdvisorsPage />} />
          <Route element={<RequireRole roles={["admin", "developer_admin"]} />}>
            <Route path="papers" element={<PapersPage variant="ingest" />} />
            <Route path="researchers" element={<ResearchersPage />} />
            <Route path="relationships" element={<RelationshipsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
