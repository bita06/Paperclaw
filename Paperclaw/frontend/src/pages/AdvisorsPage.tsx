import { FormEvent, useEffect, useMemo, useState } from "react";

import { useAuth } from "../auth/AuthContext";
import { advisorsApi } from "../api/advisors";
import { PageHeader } from "../components/common/PageHeader";
import { StatusNotice } from "../components/common/StatusNotice";
import { splitCommaSeparated } from "../lib/strings";
import type { Advisor, AdvisorDetail, AdvisorSubField } from "../types/advisor";

const initialAdvisorForm = {
  name: "",
  email: "",
  affiliation: "",
  researchAreas: "",
  bio: "",
};

const initialSubFieldForm = {
  fieldName: "",
  description: "",
  displayOrder: "0",
};

export function AdvisorsPage() {
  const { isPrivileged } = useAuth();
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [selectedAdvisorId, setSelectedAdvisorId] = useState("");
  const [advisorDetail, setAdvisorDetail] = useState<AdvisorDetail | null>(null);
  const [advisorForm, setAdvisorForm] = useState(initialAdvisorForm);
  const [subFieldForm, setSubFieldForm] = useState(initialSubFieldForm);
  const [editingSubFieldId, setEditingSubFieldId] = useState<string | null>(null);
  const [subFieldEditForm, setSubFieldEditForm] = useState(initialSubFieldForm);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmDeleteSubFieldId, setConfirmDeleteSubFieldId] = useState<string | null>(null);
  const [status, setStatus] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);

  const hasSelection = Boolean(selectedAdvisorId && advisorDetail);

  const pageDescription = useMemo(
    () =>
      isPrivileged
        ? "管理员与开发维护账号可在此维护导师档案、研究方向与子领域配置，并在导师详情区执行删除操作。"
        : "研究者可在此查看导师列表、导师详情、研究方向与已配置子领域；维护操作仅对管理员开放。",
    [isPrivileged],
  );

  const resetSubFieldManagementState = () => {
    setEditingSubFieldId(null);
    setConfirmDeleteSubFieldId(null);
    setSubFieldEditForm(initialSubFieldForm);
  };

  const loadAdvisors = async (preferredAdvisorId?: string) => {
    try {
      const data = await advisorsApi.list();
      setAdvisors(data);
      setSelectedAdvisorId((currentId) => {
        const nextId = preferredAdvisorId ?? currentId;
        if (nextId && data.some((advisor) => advisor.id === nextId)) {
          return nextId;
        }
        return data[0]?.id || "";
      });
    } catch (error) {
      setStatus({ type: "error", message: `导师列表加载失败：${String(error)}` });
    }
  };

  const loadDetail = async (advisorId: string) => {
    if (!advisorId) {
      setAdvisorDetail(null);
      setConfirmDelete(false);
      resetSubFieldManagementState();
      return;
    }

    try {
      const detail = await advisorsApi.getDetail(advisorId);
      setAdvisorDetail(detail);
    } catch (error) {
      setAdvisorDetail(null);
      setStatus({ type: "error", message: `导师详情加载失败：${String(error)}` });
    }
  };

  useEffect(() => {
    void loadAdvisors();
  }, []);

  useEffect(() => {
    setConfirmDelete(false);
    resetSubFieldManagementState();
    void loadDetail(selectedAdvisorId);
  }, [selectedAdvisorId]);

  const handleCreateAdvisor = async (event: FormEvent) => {
    event.preventDefault();
    setStatus(null);

    try {
      const created = await advisorsApi.create({
        name: advisorForm.name,
        email: advisorForm.email,
        affiliation: advisorForm.affiliation || undefined,
        research_areas: splitCommaSeparated(advisorForm.researchAreas),
        bio: advisorForm.bio || undefined,
      });
      setAdvisorForm(initialAdvisorForm);
      setConfirmDelete(false);
      await loadAdvisors(created.id);
      setStatus({ type: "success", message: "导师档案创建成功。" });
    } catch (error) {
      setStatus({ type: "error", message: `导师档案创建失败：${String(error)}` });
    }
  };

  const handleCreateSubField = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedAdvisorId) {
      return;
    }
    setStatus(null);

    try {
      await advisorsApi.createSubField(selectedAdvisorId, {
        field_name: subFieldForm.fieldName,
        description: subFieldForm.description || undefined,
        display_order: Number(subFieldForm.displayOrder || 0),
      });
      setSubFieldForm(initialSubFieldForm);
      await loadDetail(selectedAdvisorId);
      setStatus({ type: "success", message: "导师子领域已添加。" });
    } catch (error) {
      setStatus({ type: "error", message: `子领域添加失败：${String(error)}` });
    }
  };

  const startEditSubField = (subField: AdvisorSubField) => {
    setConfirmDeleteSubFieldId(null);
    setEditingSubFieldId(subField.id);
    setSubFieldEditForm({
      fieldName: subField.field_name,
      description: subField.description || "",
      displayOrder: String(subField.display_order),
    });
  };

  const handleUpdateSubField = async (event: FormEvent) => {
    event.preventDefault();
    if (!editingSubFieldId || !selectedAdvisorId) {
      return;
    }

    setStatus(null);
    try {
      await advisorsApi.updateSubField(editingSubFieldId, {
        field_name: subFieldEditForm.fieldName,
        description: subFieldEditForm.description || undefined,
        display_order: Number(subFieldEditForm.displayOrder || 0),
      });
      resetSubFieldManagementState();
      await loadDetail(selectedAdvisorId);
      setStatus({ type: "success", message: "子领域已更新。" });
    } catch (error) {
      setStatus({ type: "error", message: `子领域更新失败：${String(error)}` });
    }
  };

  const handleDeleteSubField = async (subFieldId: string) => {
    if (!selectedAdvisorId) {
      return;
    }

    setStatus(null);
    try {
      await advisorsApi.removeSubField(subFieldId);
      resetSubFieldManagementState();
      await loadDetail(selectedAdvisorId);
      setStatus({ type: "success", message: "子领域已删除。" });
    } catch (error) {
      setStatus({ type: "error", message: `删除子领域失败：${String(error)}` });
    }
  };

  const handleDeleteAdvisor = async () => {
    if (!selectedAdvisorId || !advisorDetail) {
      return;
    }

    setStatus(null);
    try {
      const deletedName = advisorDetail.name;
      await advisorsApi.remove(selectedAdvisorId);
      setConfirmDelete(false);
      setAdvisorDetail(null);
      await loadAdvisors();
      setStatus({ type: "success", message: `已删除导师档案：${deletedName}。` });
    } catch (error) {
      setStatus({ type: "error", message: `删除导师失败：${String(error)}` });
    }
  };

  const renderReadOnlySubFields = () => {
    if (!advisorDetail) {
      return <div className="muted">请选择导师后查看其子领域配置。</div>;
    }

    if (!advisorDetail.sub_fields.length) {
      return <div className="muted">当前导师尚未配置子领域。</div>;
    }

    return (
      <div className="flow">
        <div className="list-card">
          <strong>当前导师子领域</strong>
          <div className="muted">以下内容为只读展示，用于帮助你理解导师知识库的组织结构。</div>
        </div>
        {advisorDetail.sub_fields.map((item) => (
          <div key={item.id} className="list-card">
            <strong>{item.field_name}</strong>
            <div className="muted">排序：{item.display_order}</div>
            <div>{item.description || "暂无说明"}</div>
          </div>
        ))}
      </div>
    );
  };

  const renderManagedSubFields = () => {
    if (!advisorDetail) {
      return <div className="muted">请选择导师后再维护其子领域。</div>;
    }

    return (
      <div className="flow">
        <div className="list-card">
          <strong>当前子领域配置</strong>
          <div className="muted">管理员可在此编辑或删除子领域。删除前若该子领域仍挂接导师知识库文献，系统会阻止删除并提示原因。</div>
        </div>

        {advisorDetail.sub_fields.length ? (
          <div className="subfield-management-list">
            {advisorDetail.sub_fields.map((item) => {
              const isEditing = editingSubFieldId === item.id;
              const isConfirmingDelete = confirmDeleteSubFieldId === item.id;

              return (
                <div key={item.id} className="list-card subfield-card">
                  <div className="subfield-card-header">
                    <div>
                      <strong>{item.field_name}</strong>
                      <div className="muted">排序：{item.display_order}</div>
                    </div>
                    <div className="subfield-actions">
                      <button
                        type="button"
                        className="button ghost compact-button"
                        onClick={() => startEditSubField(item)}
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        className="button danger compact-button"
                        onClick={() => {
                          setEditingSubFieldId(null);
                          setConfirmDeleteSubFieldId((current) => (current === item.id ? null : item.id));
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <div>{item.description || "暂无说明"}</div>

                  {isEditing ? (
                    <form onSubmit={handleUpdateSubField} className="flow inline-editor-block">
                      <div className="inline-editor-grid">
                        <div className="field">
                          <label>子领域名称</label>
                          <input
                            required
                            value={subFieldEditForm.fieldName}
                            onChange={(event) => setSubFieldEditForm({ ...subFieldEditForm, fieldName: event.target.value })}
                          />
                        </div>
                        <div className="field">
                          <label>显示顺序</label>
                          <input
                            type="number"
                            value={subFieldEditForm.displayOrder}
                            onChange={(event) => setSubFieldEditForm({ ...subFieldEditForm, displayOrder: event.target.value })}
                          />
                        </div>
                        <div className="field inline-editor-full">
                          <label>说明</label>
                          <textarea
                            value={subFieldEditForm.description}
                            onChange={(event) => setSubFieldEditForm({ ...subFieldEditForm, description: event.target.value })}
                          />
                        </div>
                      </div>
                      <div className="actions compact-actions">
                        <button type="submit" className="button secondary">
                          保存修改
                        </button>
                        <button type="button" className="button ghost" onClick={resetSubFieldManagementState}>
                          取消
                        </button>
                      </div>
                    </form>
                  ) : null}

                  {isConfirmingDelete ? (
                    <div className="status-notice error inline-confirm-strip">
                      <div>
                        <strong>确认删除该子领域吗？</strong>
                        <div>此操作可能影响导师知识库中文献的子领域挂接。若当前仍有关联文献，系统会阻止删除并提示原因。</div>
                      </div>
                      <div className="actions compact-actions">
                        <button type="button" className="button danger" onClick={() => void handleDeleteSubField(item.id)}>
                          确认删除
                        </button>
                        <button type="button" className="button ghost" onClick={() => setConfirmDeleteSubFieldId(null)}>
                          取消
                        </button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="muted">当前导师尚未配置子领域。</div>
        )}
      </div>
    );
  };

  return (
    <>
      <PageHeader title="导师档案管理" description={pageDescription} kicker="Faculty Profiles" />

      {status ? <StatusNotice type={status.type} message={status.message} /> : null}

      <section className="split">
        {isPrivileged ? (
          <div className="panel">
            <h2>新建导师档案</h2>
            <form onSubmit={handleCreateAdvisor} className="form-grid">
              <div className="field">
                <label>姓名</label>
                <input required value={advisorForm.name} onChange={(event) => setAdvisorForm({ ...advisorForm, name: event.target.value })} />
              </div>
              <div className="field">
                <label>邮箱</label>
                <input required value={advisorForm.email} onChange={(event) => setAdvisorForm({ ...advisorForm, email: event.target.value })} />
              </div>
              <div className="field">
                <label>机构</label>
                <input value={advisorForm.affiliation} onChange={(event) => setAdvisorForm({ ...advisorForm, affiliation: event.target.value })} />
              </div>
              <div className="field">
                <label>研究方向</label>
                <input
                  value={advisorForm.researchAreas}
                  onChange={(event) => setAdvisorForm({ ...advisorForm, researchAreas: event.target.value })}
                  placeholder="数字治理，协同治理"
                />
              </div>
              <div className="field full">
                <label>简介</label>
                <textarea value={advisorForm.bio} onChange={(event) => setAdvisorForm({ ...advisorForm, bio: event.target.value })} />
              </div>
              <div className="actions">
                <button className="button" type="submit">
                  创建导师档案
                </button>
              </div>
            </form>
          </div>
        ) : (
          <div className="panel">
            <h2>查看说明</h2>
            <div className="flow">
              <div className="list-card">
                <strong>当前为只读视图</strong>
                <div className="muted">研究者账号可以查看导师列表、导师详情、研究方向与已配置子领域，但不能执行新增、删除或维护操作。</div>
              </div>
              <div className="list-card">
                <strong>可见范围</strong>
                <div className="muted">你现在看到的是平台中已建立的导师档案，可用于理解导师研究方向与后续知识库归属。</div>
              </div>
            </div>
          </div>
        )}

        <div className="panel">
          <h2>导师列表</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>导师</th>
                  <th>机构</th>
                  <th>研究方向</th>
                </tr>
              </thead>
              <tbody>
                {advisors.map((advisor) => (
                  <tr
                    key={advisor.id}
                    onClick={() => {
                      setSelectedAdvisorId(advisor.id);
                      setConfirmDelete(false);
                    }}
                    className={selectedAdvisorId === advisor.id ? "row-active" : ""}
                  >
                    <td>{advisor.name}</td>
                    <td>{advisor.affiliation || "未填写"}</td>
                    <td>{advisor.research_areas.join("、") || "未填写"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="split">
        <div className="panel">
          <div className="detail-header-row">
            <div>
              <h2>导师详情</h2>
              <div className="muted">查看导师基本信息、研究方向与当前已配置子领域。</div>
            </div>
            {isPrivileged && hasSelection ? (
              <button
                type="button"
                className="button danger advisor-delete-button"
                onClick={() => setConfirmDelete((current) => !current)}
              >
                删除导师
              </button>
            ) : null}
          </div>

          {confirmDelete && advisorDetail ? (
            <div className="status-notice error inline-confirm-strip">
              <div>
                <strong>确认删除该导师档案吗？</strong>
                <div>此操作可能影响已建立的研究者关系、导师知识库文献和子领域配置。若仍有关联数据，系统会阻止删除并提示原因。</div>
              </div>
              <div className="actions compact-actions">
                <button type="button" className="button danger" onClick={() => void handleDeleteAdvisor()}>
                  确认删除
                </button>
                <button type="button" className="button ghost" onClick={() => setConfirmDelete(false)}>
                  取消
                </button>
              </div>
            </div>
          ) : null}

          {advisorDetail ? (
            <div className="flow">
              <div className="list-card">
                <strong>{advisorDetail.name}</strong>
                <div className="muted">{advisorDetail.email}</div>
                <div>{advisorDetail.affiliation || "未填写机构"}</div>
              </div>
              <div className="list-card">
                <strong>研究方向</strong>
                <div className="tag-list">
                  {advisorDetail.research_areas.length ? (
                    advisorDetail.research_areas.map((item) => (
                      <span key={item} className="tag">
                        {item}
                      </span>
                    ))
                  ) : (
                    <span className="muted">当前还没有填写研究方向。</span>
                  )}
                </div>
              </div>
              <div className="list-card">
                <strong>已配置子领域</strong>
                <div className="tag-list">
                  {advisorDetail.sub_fields.length ? (
                    advisorDetail.sub_fields.map((item) => (
                      <span key={item.id} className="tag">
                        {item.field_name}
                      </span>
                    ))
                  ) : (
                    <span className="muted">当前还没有子领域。</span>
                  )}
                </div>
              </div>
              {advisorDetail.bio ? (
                <div className="list-card">
                  <strong>导师简介</strong>
                  <div>{advisorDetail.bio}</div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="muted">请选择一位导师查看详情。</div>
          )}
        </div>

        <div className="panel">
          <h2>{isPrivileged ? "子领域维护" : "子领域说明"}</h2>
          {isPrivileged ? (
            <div className="flow">
              <form onSubmit={handleCreateSubField} className="form-grid">
                <div className="field">
                  <label>子领域名称</label>
                  <input
                    required
                    value={subFieldForm.fieldName}
                    onChange={(event) => setSubFieldForm({ ...subFieldForm, fieldName: event.target.value })}
                  />
                </div>
                <div className="field">
                  <label>显示顺序</label>
                  <input
                    type="number"
                    value={subFieldForm.displayOrder}
                    onChange={(event) => setSubFieldForm({ ...subFieldForm, displayOrder: event.target.value })}
                  />
                </div>
                <div className="field full">
                  <label>说明</label>
                  <textarea
                    value={subFieldForm.description}
                    onChange={(event) => setSubFieldForm({ ...subFieldForm, description: event.target.value })}
                  />
                </div>
                <div className="actions">
                  <button className="button secondary" disabled={!selectedAdvisorId} type="submit">
                    添加子领域
                  </button>
                </div>
              </form>

              {renderManagedSubFields()}
            </div>
          ) : (
            renderReadOnlySubFields()
          )}
        </div>
      </section>
    </>
  );
}
