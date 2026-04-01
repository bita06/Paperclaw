import { FormEvent, useEffect, useMemo, useState } from "react";
import { advisorsApi } from "../api/advisors";
import { researchersApi } from "../api/researchers";
import type { AdvisorDetail } from "../types/advisor";
import type { Researcher, ResearcherAdvisorLink } from "../types/researcher";
import { PageHeader } from "../components/common/PageHeader";
import { StatusNotice } from "../components/common/StatusNotice";

const initialRelationForm = {
  advisorId: "",
  relationshipType: "co_advisor",
  accessLevel: "readonly",
  subFieldsAccess: [] as string[],
};

export function RelationshipsPage() {
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [advisors, setAdvisors] = useState<AdvisorDetail[]>([]);
  const [selectedResearcherId, setSelectedResearcherId] = useState("");
  const [selectedAdvisorId, setSelectedAdvisorId] = useState("");
  const [relationships, setRelationships] = useState<ResearcherAdvisorLink[]>([]);
  const [relationshipDetail, setRelationshipDetail] = useState<ResearcherAdvisorLink | null>(null);
  const [relationForm, setRelationForm] = useState(initialRelationForm);
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const selectedAdvisor = useMemo(
    () => advisors.find((advisor) => advisor.id === relationForm.advisorId || advisor.id === selectedAdvisorId) ?? null,
    [advisors, relationForm.advisorId, selectedAdvisorId],
  );

  const loadBaseData = async () => {
    try {
      const [researcherList, advisorList] = await Promise.all([researchersApi.list(), advisorsApi.list()]);
      const advisorDetails = await Promise.all(advisorList.map((advisor) => advisorsApi.getDetail(advisor.id)));
      setResearchers(researcherList);
      setAdvisors(advisorDetails);
      if (!selectedResearcherId && researcherList.length > 0) {
        setSelectedResearcherId(researcherList[0].id);
      }
      if (!relationForm.advisorId && advisorDetails.length > 0) {
        setRelationForm((prev) => ({ ...prev, advisorId: advisorDetails[0].id }));
      }
    } catch (error) {
      setStatus({ type: "error", message: `基础数据加载失败：${String(error)}` });
    }
  };

  const loadRelationships = async (researcherId: string) => {
    if (!researcherId) {
      setRelationships([]);
      return;
    }

    try {
      const data = await researchersApi.listRelationships(researcherId);
      setRelationships(data);
    } catch (error) {
      setStatus({ type: "error", message: `指导关系列表加载失败：${String(error)}` });
    }
  };

  useEffect(() => {
    void loadBaseData();
  }, []);

  useEffect(() => {
    void loadRelationships(selectedResearcherId);
  }, [selectedResearcherId]);

  useEffect(() => {
    if (!selectedResearcherId || !selectedAdvisorId) {
      setRelationshipDetail(null);
      return;
    }

    void (async () => {
      try {
        const detail = await researchersApi.getRelationship(selectedResearcherId, selectedAdvisorId);
        setRelationshipDetail(detail);
      } catch {
        setRelationshipDetail(null);
      }
    })();
  }, [selectedResearcherId, selectedAdvisorId]);

  const toggleSubField = (fieldName: string) => {
    setRelationForm((prev) => ({
      ...prev,
      subFieldsAccess: prev.subFieldsAccess.includes(fieldName)
        ? prev.subFieldsAccess.filter((item) => item !== fieldName)
        : [...prev.subFieldsAccess, fieldName],
    }));
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedResearcherId) {
      return;
    }
    setStatus(null);

    try {
      const created = await researchersApi.createRelationship(selectedResearcherId, {
        advisor_id: relationForm.advisorId,
        relationship_type: relationForm.relationshipType,
        access_level: relationForm.accessLevel,
        sub_fields_access: relationForm.subFieldsAccess,
      });
      setSelectedAdvisorId(created.advisor_id);
      await loadRelationships(selectedResearcherId);
      setStatus({ type: "success", message: "导师指导关系创建成功。" });
    } catch (error) {
      setStatus({ type: "error", message: `导师指导关系创建失败：${String(error)}` });
    }
  };

  const handleUpdate = async () => {
    if (!selectedResearcherId || !selectedAdvisorId) {
      return;
    }
    setStatus(null);

    try {
      const updated = await researchersApi.updateRelationship(selectedResearcherId, selectedAdvisorId, {
        relationship_type: relationForm.relationshipType,
        access_level: relationForm.accessLevel,
        sub_fields_access: relationForm.subFieldsAccess,
      });
      setRelationshipDetail(updated);
      await loadRelationships(selectedResearcherId);
      setStatus({ type: "success", message: "指导关系已更新。" });
    } catch (error) {
      setStatus({ type: "error", message: `指导关系更新失败：${String(error)}` });
    }
  };

  const handleDelete = async () => {
    if (!selectedResearcherId || !selectedAdvisorId) {
      return;
    }
    setStatus(null);

    try {
      await researchersApi.deleteRelationship(selectedResearcherId, selectedAdvisorId);
      setSelectedAdvisorId("");
      setRelationshipDetail(null);
      await loadRelationships(selectedResearcherId);
      setStatus({ type: "success", message: "指导关系已删除。" });
    } catch (error) {
      setStatus({ type: "error", message: `指导关系删除失败：${String(error)}` });
    }
  };

  return (
    <>
      <PageHeader
        title="导师指导关系"
        description="用于演示研究者与导师之间的多对多指导关系、关系类型、访问级别和子领域授权，体现平台的权限细化能力。"
        kicker="Advising Permissions"
      />

      {status ? <StatusNotice type={status.type} message={status.message} /> : null}

      <section className="split">
        <div className="panel">
          <h2>创建或更新关系</h2>
          <form onSubmit={handleCreate} className="form-grid">
            <div className="field full">
              <label>研究者</label>
              <select value={selectedResearcherId} onChange={(event) => setSelectedResearcherId(event.target.value)} required>
                <option value="">请选择研究者</option>
                {researchers.map((researcher) => (
                  <option key={researcher.id} value={researcher.id}>
                    {researcher.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field full">
              <label>导师</label>
              <select
                value={relationForm.advisorId}
                onChange={(event) => {
                  setRelationForm({ ...relationForm, advisorId: event.target.value, subFieldsAccess: [] });
                  setSelectedAdvisorId(event.target.value);
                }}
                required
              >
                <option value="">请选择导师</option>
                {advisors.map((advisor) => (
                  <option key={advisor.id} value={advisor.id}>
                    {advisor.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>关系类型</label>
              <select
                value={relationForm.relationshipType}
                onChange={(event) => setRelationForm({ ...relationForm, relationshipType: event.target.value })}
              >
                <option value="primary_advisor">主导师</option>
                <option value="co_advisor">联合导师</option>
                <option value="mentor">指导教师</option>
              </select>
            </div>
            <div className="field">
              <label>访问级别</label>
              <select value={relationForm.accessLevel} onChange={(event) => setRelationForm({ ...relationForm, accessLevel: event.target.value })}>
                <option value="full">完全访问</option>
                <option value="readonly">只读访问</option>
              </select>
            </div>
            <div className="field full">
              <label>可访问子领域</label>
              <div className="tag-list">
                {selectedAdvisor?.sub_fields.length ? (
                  selectedAdvisor.sub_fields.map((subField) => (
                    <button
                      key={subField.id}
                      type="button"
                      className={`tag-chip ${relationForm.subFieldsAccess.includes(subField.field_name) ? "active" : ""}`}
                      onClick={() => toggleSubField(subField.field_name)}
                    >
                      {subField.field_name}
                    </button>
                  ))
                ) : (
                  <span className="muted">请选择导师后配置子领域授权。</span>
                )}
              </div>
            </div>
            <div className="actions">
              <button className="button" type="submit">
                绑定关系
              </button>
              <button className="button secondary" onClick={handleUpdate} type="button" disabled={!selectedAdvisorId}>
                更新关系
              </button>
              <button className="button danger" onClick={handleDelete} type="button" disabled={!selectedAdvisorId}>
                删除关系
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <h2>当前研究者的导师关系</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>导师</th>
                  <th>关系类型</th>
                  <th>访问级别</th>
                  <th>子领域授权</th>
                </tr>
              </thead>
              <tbody>
                {relationships.map((item) => (
                  <tr
                    key={item.advisor_id}
                    onClick={() => {
                      setSelectedAdvisorId(item.advisor_id);
                      setRelationForm({
                        advisorId: item.advisor_id,
                        relationshipType: item.relationship_type,
                        accessLevel: item.access_level,
                        subFieldsAccess: item.sub_fields_access,
                      });
                    }}
                    className={selectedAdvisorId === item.advisor_id ? "row-active" : ""}
                  >
                    <td>{item.advisor_name}</td>
                    <td>{item.relationship_type}</td>
                    <td>{item.access_level}</td>
                    <td>{item.sub_fields_access.join("、") || "未授权"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>单条关系详情</h2>
        {relationshipDetail ? (
          <div className="grid-3">
            <div className="list-card">
              <strong>导师</strong>
              <div>{relationshipDetail.advisor_name}</div>
            </div>
            <div className="list-card">
              <strong>关系类型</strong>
              <div>{relationshipDetail.relationship_type}</div>
            </div>
            <div className="list-card">
              <strong>访问级别</strong>
              <div>{relationshipDetail.access_level}</div>
            </div>
            <div className="list-card">
              <strong>子领域授权</strong>
              <div>{relationshipDetail.sub_fields_access.join("、") || "未授权"}</div>
            </div>
            <div className="list-card">
              <strong>建立时间</strong>
              <div>{new Date(relationshipDetail.joined_at).toLocaleString()}</div>
            </div>
          </div>
        ) : (
          <div className="muted">点击上方关系列表中的某条记录后，这里会显示单条关系详情。</div>
        )}
      </section>
    </>
  );
}
