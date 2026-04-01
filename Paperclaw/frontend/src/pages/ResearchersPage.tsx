import { FormEvent, useEffect, useState } from "react";
import { researchersApi } from "../api/researchers";
import type { Researcher } from "../types/researcher";
import { PageHeader } from "../components/common/PageHeader";
import { StatusNotice } from "../components/common/StatusNotice";

const initialResearcherForm = {
  name: "",
  email: "",
  password: "",
  researchGroup: "",
  academicLevel: "",
  bio: "",
};

const initialStageForm = {
  currentStage: "",
  currentResearchQuestion: "",
};

export function ResearchersPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [selectedResearcherId, setSelectedResearcherId] = useState("");
  const [researcherDetail, setResearcherDetail] = useState<Researcher | null>(null);
  const [researcherForm, setResearcherForm] = useState(initialResearcherForm);
  const [stageForm, setStageForm] = useState(initialStageForm);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const loadResearchers = async () => {
    try {
      const data = await researchersApi.list();
      setResearchers(data);
      if (!selectedResearcherId && data.length > 0) {
        setSelectedResearcherId(data[0].id);
      }
    } catch (error) {
      setStatus({ type: "error", message: `研究者列表加载失败：${String(error)}` });
    }
  };

  const loadDetail = async (researcherId: string) => {
    if (!researcherId) {
      setResearcherDetail(null);
      return;
    }

    try {
      const detail = await researchersApi.getDetail(researcherId);
      setResearcherDetail(detail);
      setStageForm({
        currentStage: detail.current_stage ?? "",
        currentResearchQuestion: detail.current_research_question ?? "",
      });
    } catch (error) {
      setStatus({ type: "error", message: `研究者详情加载失败：${String(error)}` });
    }
  };

  useEffect(() => {
    void loadResearchers();
  }, []);

  useEffect(() => {
    void loadDetail(selectedResearcherId);
  }, [selectedResearcherId]);

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    setStatus(null);

    try {
      const created = await researchersApi.create({
        name: researcherForm.name,
        email: researcherForm.email,
        password: researcherForm.password,
        research_group: researcherForm.researchGroup || undefined,
        academic_level: researcherForm.academicLevel || undefined,
        bio: researcherForm.bio || undefined,
      });
      setResearcherForm(initialResearcherForm);
      setSelectedResearcherId(created.id);
      await loadResearchers();
      setStatus({ type: "success", message: "研究者档案创建成功。" });
    } catch (error) {
      setStatus({ type: "error", message: `研究者创建失败：${String(error)}` });
    }
  };

  const handleUpdateStage = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedResearcherId) {
      return;
    }
    setStatus(null);

    try {
      await researchersApi.updateStage(selectedResearcherId, {
        current_stage: stageForm.currentStage,
        current_research_question: stageForm.currentResearchQuestion || undefined,
      });
      await loadDetail(selectedResearcherId);
      setStatus({ type: "success", message: "研究阶段已更新。" });
    } catch (error) {
      setStatus({ type: "error", message: `研究阶段更新失败：${String(error)}` });
    }
  };

  return (
    <>
      <PageHeader
        title="研究者档案管理"
        description="维护研究者基本档案、研究阶段与当前研究问题，为后续研究问答和个性化检索提供上下文基础。"
        kicker="Researcher Records"
      />

      {status ? <StatusNotice type={status.type} message={status.message} /> : null}

      <section className="split">
        <div className="panel">
          <h2>新建研究者档案</h2>
          <form onSubmit={handleCreate} className="form-grid">
            <div className="field">
              <label>姓名</label>
              <input required value={researcherForm.name} onChange={(event) => setResearcherForm({ ...researcherForm, name: event.target.value })} />
            </div>
            <div className="field">
              <label>邮箱</label>
              <input required value={researcherForm.email} onChange={(event) => setResearcherForm({ ...researcherForm, email: event.target.value })} />
            </div>
            <div className="field">
              <label>密码</label>
              <input required value={researcherForm.password} onChange={(event) => setResearcherForm({ ...researcherForm, password: event.target.value })} />
            </div>
            <div className="field">
              <label>学位层级</label>
              <input
                value={researcherForm.academicLevel}
                onChange={(event) => setResearcherForm({ ...researcherForm, academicLevel: event.target.value })}
                placeholder="博士 / 硕士"
              />
            </div>
            <div className="field full">
              <label>研究团队</label>
              <input
                value={researcherForm.researchGroup}
                onChange={(event) => setResearcherForm({ ...researcherForm, researchGroup: event.target.value })}
              />
            </div>
            <div className="field full">
              <label>简介</label>
              <textarea value={researcherForm.bio} onChange={(event) => setResearcherForm({ ...researcherForm, bio: event.target.value })} />
            </div>
            <div className="actions">
              <button className="button" type="submit">
                创建研究者档案
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <h2>研究者列表</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>研究者</th>
                  <th>学位层级</th>
                  <th>当前阶段</th>
                </tr>
              </thead>
              <tbody>
                {researchers.map((researcher) => (
                  <tr
                    key={researcher.id}
                    onClick={() => setSelectedResearcherId(researcher.id)}
                    className={selectedResearcherId === researcher.id ? "row-active" : ""}
                  >
                    <td>{researcher.name}</td>
                    <td>{researcher.academic_level || "未填写"}</td>
                    <td>{researcher.current_stage || "未填写"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="split">
        <div className="panel">
          <h2>研究者详情</h2>
          {researcherDetail ? (
            <div className="flow">
              <div className="list-card">
                <strong>{researcherDetail.name}</strong>
                <div className="muted">{researcherDetail.email}</div>
                <div>研究团队：{researcherDetail.research_group || "未填写"}</div>
                <div>学位层级：{researcherDetail.academic_level || "未填写"}</div>
              </div>
              <div className="list-card">
                <strong>当前研究任务</strong>
                <div>研究阶段：{researcherDetail.current_stage || "未填写"}</div>
                <div className="muted">
                  {researcherDetail.current_research_question || "尚未记录当前研究问题。"}
                </div>
              </div>
            </div>
          ) : (
            <div className="muted">请选择一位研究者查看详情。</div>
          )}
        </div>

        <div className="panel">
          <h2>更新研究阶段</h2>
          <form onSubmit={handleUpdateStage} className="form-grid">
            <div className="field full">
              <label>当前阶段</label>
              <input
                required
                value={stageForm.currentStage}
                onChange={(event) => setStageForm({ ...stageForm, currentStage: event.target.value })}
                placeholder="文献综述阶段"
              />
            </div>
            <div className="field full">
              <label>当前研究问题</label>
              <textarea
                value={stageForm.currentResearchQuestion}
                onChange={(event) => setStageForm({ ...stageForm, currentResearchQuestion: event.target.value })}
              />
            </div>
            <div className="actions">
              <button className="button secondary" disabled={!selectedResearcherId} type="submit">
                更新研究阶段
              </button>
            </div>
          </form>
        </div>
      </section>
    </>
  );
}
