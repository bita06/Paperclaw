import { FormEvent, useEffect, useMemo, useState } from "react";
import { advisorsApi } from "../api/advisors";
import { filesApi } from "../api/files";
import { papersApi } from "../api/papers";
import { researchersApi } from "../api/researchers";
import { useAuth } from "../auth/AuthContext";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import { StatusNotice } from "../components/common/StatusNotice";
import { splitCommaSeparated } from "../lib/strings";
import type { AdvisorDetail } from "../types/advisor";
import type { FileHistoryItem, FileUploadAcceptedResponse, KnowledgeStatusSummary, TaskResponse } from "../types/fileTask";
import type { AdvisorLibraryPaper, PaperUploadResponse } from "../types/paper";
import type { Researcher, ResearcherAdvisorLink } from "../types/researcher";
import type { AsyncStatus, UploadPipelineStatus, UploadQueueItem } from "../types/task";

type PapersPageProps = {
  variant?: "library" | "ingest";
};

const initialUploadForm = {
  title: "",
  authors: "",
  year: "",
  venue: "",
  doi: "",
  abstract: "",
  keywords: "",
  advisorId: "",
  subFieldId: "",
  researcherId: "",
  libraryTags: "",
  notes: "",
};

const UPLOAD_HISTORY_STORAGE_KEY = "paperclaw:file-history:last-selected";

function renderStatusBadges(status: KnowledgeStatusSummary) {
  const badges: Array<{ label: string; tone: "neutral" | "info" | "success" | "warning" | "error" }> = [];

  if (status.uploaded) {
    badges.push({ label: "已上传文件", tone: "neutral" });
  }
  if (status.parsing) {
    badges.push({ label: "解析中", tone: "info" });
  }
  if (status.parse_success) {
    badges.push({ label: "解析成功", tone: "success" });
  }
  if (status.parse_error) {
    badges.push({ label: "解析失败", tone: "error" });
  }
  if (status.paper_generated) {
    badges.push({ label: "已生成 Paper", tone: "success" });
  }
  if (status.researcher_context_bound) {
    badges.push({ label: "已绑定 researcher 上下文", tone: "info" });
  }
  if (status.in_researcher_knowledge_base) {
    badges.push({ label: "已进入研究者知识库", tone: "success" });
  }
  if (status.awaiting_knowledge_base_entry) {
    badges.push({ label: "仅完成解析，尚未入库", tone: "warning" });
  }
  if (status.agent_ready) {
    badges.push({ label: "后续可供 Agent 检索", tone: "success" });
  }

  return badges;
}

export function PapersPage({ variant = "ingest" }: PapersPageProps) {
  const { isPrivileged, user } = useAuth();
  const [advisors, setAdvisors] = useState<AdvisorDetail[]>([]);
  const [researcherAdvisors, setResearcherAdvisors] = useState<ResearcherAdvisorLink[]>([]);
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [uploadForm, setUploadForm] = useState(initialUploadForm);
  const [ingestFiles, setIngestFiles] = useState<File[]>([]);
  const [researcherFiles, setResearcherFiles] = useState<File[]>([]);
  const [uploadResult, setUploadResult] = useState<PaperUploadResponse | null>(null);
  const [taskUploadReceipt, setTaskUploadReceipt] = useState<FileUploadAcceptedResponse | null>(null);
  const [taskDetail, setTaskDetail] = useState<TaskResponse | null>(null);
  const [fileHistory, setFileHistory] = useState<FileHistoryItem[]>([]);
  const [historyStatus, setHistoryStatus] = useState<AsyncStatus>("idle");
  const [selectedHistoryFileId, setSelectedHistoryFileId] = useState("");
  const [libraryPapers, setLibraryPapers] = useState<AdvisorLibraryPaper[]>([]);
  const [filterAdvisorId, setFilterAdvisorId] = useState("");
  const [filterResearcherId, setFilterResearcherId] = useState("");
  const [filterSubFieldId, setFilterSubFieldId] = useState("");
  const [filterTag, setFilterTag] = useState("");
  const [ingestUploadStatus, setIngestUploadStatus] = useState<UploadPipelineStatus>("idle");
  const [taskUploadStatus, setTaskUploadStatus] = useState<UploadPipelineStatus>("idle");
  const [queryStatus, setQueryStatus] = useState<AsyncStatus>("idle");
  const [status, setStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const uploadAdvisor = useMemo(
    () => advisors.find((advisor) => advisor.id === uploadForm.advisorId) ?? null,
    [advisors, uploadForm.advisorId],
  );

  const filterAdvisor = useMemo(
    () => advisors.find((advisor) => advisor.id === filterAdvisorId) ?? null,
    [advisors, filterAdvisorId],
  );

  const selectedHistoryItem = useMemo(
    () => fileHistory.find((item) => item.file_id === selectedHistoryFileId) ?? null,
    [fileHistory, selectedHistoryFileId],
  );
  const selectedKnowledgeStatus = selectedHistoryItem?.knowledge_status;
  const selectedMetadata = (taskDetail?.result.metadata || {}) as {
    title?: string;
    authors?: string[];
    year?: number | null;
    abstract?: string | null;
    keywords?: string[];
  };

  const effectiveResearcherId = isPrivileged ? filterResearcherId : user?.researcher_id || "";
  const primaryIngestFile = ingestFiles[0] ?? null;
  const primaryResearcherFile = researcherFiles[0] ?? null;

  const ingestQueue: UploadQueueItem[] = useMemo(
    () =>
      ingestFiles.map((file, index) => ({
        id: `ingest-${file.name}-${index}`,
        name: file.name,
        size: file.size,
        status: index === 0 ? ingestUploadStatus : "idle",
      })),
    [ingestFiles, ingestUploadStatus],
  );

  const researcherQueue: UploadQueueItem[] = useMemo(
    () =>
      researcherFiles.map((file, index) => ({
        id: `researcher-${file.name}-${index}`,
        name: file.name,
        size: file.size,
        status: index === 0 ? taskUploadStatus : "idle",
      })),
    [researcherFiles, taskUploadStatus],
  );

  const pageMeta =
    variant === "library"
      ? {
          title: "我的导师库",
          description: "查看研究者已授权的导师库内容，并上传 PDF 进入解析与入库流程。",
        }
      : {
          title: "文献入库与导师知识库",
          description: "将文献挂接到导师与子领域，用于知识库维护与权限验证。",
        };

  const syncTaskUploadState = (nextTask: TaskResponse | null) => {
    if (!nextTask) {
      setTaskUploadStatus("idle");
      return;
    }
    if (nextTask.status === "queued") {
      setTaskUploadStatus("uploaded");
      return;
    }
    if (nextTask.status === "processing") {
      setTaskUploadStatus("parsing");
      return;
    }
    if (nextTask.status === "success") {
      setTaskUploadStatus("ready");
      return;
    }
    setTaskUploadStatus("error");
  };

  const refreshFileHistory = async () => {
    setHistoryStatus("loading");
    const history = await filesApi.listHistory({
      researcherId: isPrivileged ? filterResearcherId || undefined : user?.researcher_id || undefined,
      limit: 20,
    });
    setFileHistory(history);
    setHistoryStatus("success");
    return history;
  };

  useEffect(() => {
    void (async () => {
      try {
        if (isPrivileged) {
          const [researcherList, advisorList] = await Promise.all([researchersApi.list(), advisorsApi.list()]);
          const advisorDetails = await Promise.all(advisorList.map((advisor) => advisorsApi.getDetail(advisor.id)));
          setResearchers(researcherList);
          setAdvisors(advisorDetails);
          setResearcherAdvisors([]);

          if (!uploadForm.advisorId && advisorDetails.length > 0) {
            setUploadForm((prev) => ({ ...prev, advisorId: advisorDetails[0].id }));
          }
          if (!filterAdvisorId && advisorDetails.length > 0) {
            setFilterAdvisorId(advisorDetails[0].id);
          }
          return;
        }

        if (!user?.researcher_id) {
          setStatus({ type: "error", message: "当前账号未绑定 researcher 档案。" });
          return;
        }

        const ownRelationships = await researchersApi.listRelationships(user.researcher_id);
        setResearcherAdvisors(ownRelationships);
        if (!filterAdvisorId && ownRelationships.length > 0) {
          setFilterAdvisorId(ownRelationships[0].advisor_id);
        }
      } catch (error) {
        setStatus({ type: "error", message: `基础数据加载失败：${String(error)}` });
      }
    })();
  }, [filterAdvisorId, isPrivileged, uploadForm.advisorId, user?.researcher_id]);

  useEffect(() => {
    if (variant !== "library") {
      return;
    }

    void (async () => {
      try {
        const history = await refreshFileHistory();
        const storedSelection = window.localStorage.getItem(UPLOAD_HISTORY_STORAGE_KEY);
        const nextSelection =
          (storedSelection && history.some((item) => item.file_id === storedSelection) && storedSelection) ||
          history[0]?.file_id ||
          "";
        setSelectedHistoryFileId(nextSelection);
      } catch (error) {
        setHistoryStatus("error");
        setStatus({ type: "error", message: `解析历史加载失败：${String(error)}` });
      }
    })();
  }, [filterResearcherId, isPrivileged, user?.researcher_id, variant]);

  useEffect(() => {
    if (!selectedHistoryFileId) {
      return;
    }
    window.localStorage.setItem(UPLOAD_HISTORY_STORAGE_KEY, selectedHistoryFileId);
  }, [selectedHistoryFileId]);

  useEffect(() => {
    if (!selectedHistoryItem) {
      return;
    }
    setTaskUploadReceipt({
      file_id: selectedHistoryItem.file_id,
      task_id: selectedHistoryItem.latest_task?.id || "",
      status: "uploaded",
    });
    setTaskDetail(selectedHistoryItem.latest_task ?? null);
    syncTaskUploadState(selectedHistoryItem.latest_task ?? null);
  }, [selectedHistoryItem]);

  useEffect(() => {
    if (!taskUploadReceipt?.task_id) {
      return;
    }
    if (taskDetail?.status === "success" || taskDetail?.status === "error") {
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(async () => {
      try {
        const nextTask = await filesApi.getTask(taskUploadReceipt.task_id);
        if (cancelled) {
          return;
        }

        setTaskDetail(nextTask);
        syncTaskUploadState(nextTask);

        setFileHistory((prev) =>
          prev.map((item) =>
            item.file_id === taskUploadReceipt.file_id
              ? {
                  ...item,
                  file_status: nextTask.status === "success" ? "ready" : nextTask.status === "error" ? "error" : "processing",
                  linked_paper_id: nextTask.result.paper_id ?? item.linked_paper_id,
                  latest_task: nextTask,
                }
              : item,
          ),
        );

        if (nextTask.status === "success") {
          setStatus({ type: "success", message: "PDF 上传成功，解析任务已完成。" });
          void refreshFileHistory();
        } else if (nextTask.status === "error") {
          setStatus({
            type: "error",
            message: nextTask.error_message || "PDF 解析失败，请稍后重试。",
          });
          void refreshFileHistory();
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        setTaskUploadStatus("error");
        setStatus({ type: "error", message: `任务状态获取失败：${String(error)}` });
      }
    }, 1500);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [taskDetail?.status, taskUploadReceipt?.file_id, taskUploadReceipt?.task_id]);

  const handleIngestUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!primaryIngestFile || !uploadForm.advisorId) {
      setStatus({ type: "error", message: "请先选择文件和导师。" });
      return;
    }

    setStatus(null);
    setIngestUploadStatus("uploading");
    try {
      const result = await papersApi.upload({
        file: primaryIngestFile,
        title: uploadForm.title || undefined,
        authors: splitCommaSeparated(uploadForm.authors),
        year: uploadForm.year || undefined,
        venue: uploadForm.venue || undefined,
        doi: uploadForm.doi || undefined,
        abstract: uploadForm.abstract || undefined,
        keywords: splitCommaSeparated(uploadForm.keywords),
        advisorIds: [uploadForm.advisorId],
        subFieldIds: uploadForm.subFieldId ? [uploadForm.subFieldId] : [],
        libraryTags: splitCommaSeparated(uploadForm.libraryTags),
        notes: uploadForm.notes || undefined,
        researcherId: uploadForm.researcherId || undefined,
      });
      setUploadResult(result);
      setIngestUploadStatus("uploaded");
      setStatus({ type: "success", message: "文献已上传并成功挂接到导师知识库。" });
    } catch (error) {
      setIngestUploadStatus("error");
      setStatus({ type: "error", message: `文献上传失败：${String(error)}` });
    }
  };

  const handleResearcherUpload = async (event: FormEvent) => {
    event.preventDefault();
    if (!primaryResearcherFile) {
      setStatus({ type: "error", message: "请先选择一个 PDF 文件。" });
      return;
    }

    setStatus(null);
    setTaskUploadReceipt(null);
    setTaskDetail(null);
    setTaskUploadStatus("uploading");

    try {
      const receipt = await filesApi.upload(
        primaryResearcherFile,
        isPrivileged ? effectiveResearcherId || undefined : user?.researcher_id || undefined,
      );
      setTaskUploadReceipt(receipt);
      setTaskUploadStatus("uploaded");
      setSelectedHistoryFileId(receipt.file_id);
      setStatus({ type: "success", message: "PDF 已上传，解析任务已创建。" });
      await refreshFileHistory();
    } catch (error) {
      setTaskUploadStatus("error");
      setStatus({ type: "error", message: `上传失败：${String(error)}` });
    }
  };

  const handleQueryLibrary = async () => {
    if (!filterAdvisorId) {
      setStatus({ type: "error", message: "请先选择导师。" });
      return;
    }

    setStatus(null);
    setQueryStatus("loading");
    try {
      const data = await advisorsApi.listPapers(filterAdvisorId, {
        subFieldId: isPrivileged ? filterSubFieldId || undefined : undefined,
        tag: filterTag || undefined,
        researcherId: effectiveResearcherId || undefined,
      });
      setLibraryPapers(data);
      setQueryStatus("success");
    } catch (error) {
      setQueryStatus("error");
      setStatus({ type: "error", message: `导师知识库查询失败：${String(error)}` });
    }
  };

  return (
    <>
      <PageHeader
        title={pageMeta.title}
        description={pageMeta.description}
        kicker={variant === "library" ? "Knowledge Library" : "Ingestion Workflow"}
      />

      {status ? <StatusNotice type={status.type} message={status.message} /> : null}

      {variant === "library" ? (
        <section className="stack-section">
          <div className="panel">
            <h2>研究者上传 PDF</h2>
            <form onSubmit={handleResearcherUpload} className="form-grid">
              <div className="field full">
                <label>选择 PDF 文件</label>
                <input
                  type="file"
                  accept=".pdf"
                  multiple
                  onChange={(event) => setResearcherFiles(Array.from(event.target.files ?? []))}
                  required
                />
              </div>

              {isPrivileged ? (
                <div className="field full">
                  <label>研究者上下文</label>
                  <select value={filterResearcherId} onChange={(event) => setFilterResearcherId(event.target.value)}>
                    <option value="">不指定研究者上下文</option>
                    {researchers.map((researcher) => (
                      <option key={researcher.id} value={researcher.id}>
                        {researcher.name}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div className="field full">
                  <label>当前模式</label>
                  <div className="list-card">
                    <strong>我的研究上下文</strong>
                    <div className="muted">researcher 角色上传的 PDF 会自动绑定到本人 researcher 上下文。</div>
                  </div>
                </div>
              )}

              <div className="actions">
                <button className="button" type="submit">
                  上传并创建解析任务
                </button>
              </div>
            </form>

            {researcherQueue.length ? (
              <div className="flow upload-queue">
                {researcherQueue.map((item, index) => (
                  <div key={item.id} className="list-card">
                    <strong>{item.name}</strong>
                    <div className="muted">
                      {(item.size / 1024 / 1024).toFixed(2)} MB · {item.status}
                    </div>
                    {index > 0 ? (
                      <div className="muted">当前最小版本仅处理第一份文件，队列结构已为后续多文件上传保留。</div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="panel">
            <h2>解析任务状态</h2>
            {taskUploadStatus === "uploading" ? <LoadingState label="正在上传 PDF..." /> : null}
            {taskUploadStatus === "parsing" ? <LoadingState label="正在解析 PDF..." /> : null}

            {taskUploadReceipt || taskDetail ? (
              <div className="flow">
                <div className="list-card">
                  <strong>{selectedHistoryItem?.original_name || primaryResearcherFile?.name || "当前上传文件"}</strong>
                  <div className="muted">file_id：{taskUploadReceipt?.file_id || taskDetail?.result.file_id || "未生成"}</div>
                  <div className="muted">task_id：{taskUploadReceipt?.task_id || taskDetail?.id || "未生成"}</div>
                  <div>任务状态：{taskDetail?.status || taskUploadStatus || "idle"}</div>
                  <div>文件状态：{selectedHistoryItem?.file_status || "uploaded"}</div>
                  <div>知识库归属：{selectedHistoryItem?.researcher_id ? "已绑定研究者上下文" : "未绑定研究者上下文"}</div>
                  {selectedKnowledgeStatus ? (
                    <div className="status-badge-row" style={{ marginTop: 12 }}>
                      {renderStatusBadges(selectedKnowledgeStatus).map((badge) => (
                        <span key={badge.label} className={`status-badge ${badge.tone}`}>
                          {badge.label}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="list-card">
                  <strong>知识库关联说明</strong>
                  <div className="muted" style={{ marginTop: 8 }}>
                    {selectedKnowledgeStatus?.summary_text ||
                      "当前文件状态摘要暂不可用。"}
                  </div>
                  <div className="flow" style={{ marginTop: 12 }}>
                    <div>Paper 记录：{selectedKnowledgeStatus?.paper_generated ? "已生成" : "尚未生成"}</div>
                    <div>researcher 上下文：{selectedKnowledgeStatus?.researcher_context_bound ? "已建立关联" : "未建立关联"}</div>
                    <div>研究者知识库：{selectedKnowledgeStatus?.in_researcher_knowledge_base ? "已进入" : "尚未进入"}</div>
                    <div>Agent 使用：{selectedKnowledgeStatus?.agent_ready ? "后续可检索" : "暂未就绪"}</div>
                  </div>
                </div>
                <div className="list-card">
                  <strong>解析结果</strong>
                  <div className="metadata-grid" style={{ marginTop: 12 }}>
                    <div className="metadata-card full">
                      <div className="metadata-label">标题</div>
                      <div className="metadata-value">{selectedMetadata.title || "未提取"}</div>
                    </div>
                    <div className="metadata-card">
                      <div className="metadata-label">作者</div>
                      <div className="metadata-value">
                        {selectedMetadata.authors?.length ? selectedMetadata.authors.join("、") : "未提取"}
                      </div>
                    </div>
                    <div className="metadata-card">
                      <div className="metadata-label">年份</div>
                      <div className="metadata-value">{selectedMetadata.year || "未提取"}</div>
                    </div>
                    <div className="metadata-card full">
                      <div className="metadata-label">摘要</div>
                      <div className="metadata-value large">{selectedMetadata.abstract || "未提取"}</div>
                    </div>
                    <div className="metadata-card full">
                      <div className="metadata-label">关键词</div>
                      <div className="tag-list">
                        {selectedMetadata.keywords?.length ? (
                          selectedMetadata.keywords.map((keyword) => (
                            <span key={keyword} className="tag">
                              {keyword}
                            </span>
                          ))
                        ) : (
                          <span className="muted">未提取</span>
                        )}
                      </div>
                    </div>
                    <div className="metadata-card">
                      <div className="metadata-label">Paper ID</div>
                      <div className="metadata-value">{taskDetail?.result.paper_id || "尚未生成"}</div>
                    </div>
                    <div className="metadata-card">
                      <div className="metadata-label">章节数量</div>
                      <div className="metadata-value">{taskDetail?.result.sections_count ?? 0}</div>
                    </div>
                    <div className="metadata-card full">
                      <div className="metadata-label">章节标题</div>
                      <div className="tag-list">
                        {taskDetail?.result.section_titles?.length ? (
                          taskDetail.result.section_titles.map((title) => (
                            <span key={title} className="tag">
                              {title}
                            </span>
                          ))
                        ) : (
                          <span className="muted">尚未提取</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="muted">上传成功后，这里会显示 file_id、task_id、任务状态和解析结果。</div>
            )}
          </div>

          <div className="panel">
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <h2>文献上传与解析历史</h2>
              <button className="button secondary" type="button" onClick={() => void refreshFileHistory()}>
                刷新历史
              </button>
            </div>
            {historyStatus === "loading" ? <LoadingState label="正在加载解析历史..." /> : null}
            <div className="flow">
              {fileHistory.length ? (
                fileHistory.map((item) => (
                  <button
                    key={item.file_id}
                    type="button"
                    className={`list-card history-item-card ${selectedHistoryFileId === item.file_id ? "active" : ""}`}
                    style={{ textAlign: "left" }}
                    onClick={() => setSelectedHistoryFileId(item.file_id)}
                  >
                    <strong>{item.original_name}</strong>
                    <div className="muted">
                      {new Date(item.created_at).toLocaleString("zh-CN")} · {item.file_status}
                    </div>
                    <div className="muted">paper_id：{item.linked_paper_id || "尚未生成"}</div>
                    <div className="muted">task：{item.latest_task?.status || "未创建"}</div>
                    <div className="status-badge-row" style={{ marginTop: 10 }}>
                      {renderStatusBadges(item.knowledge_status).map((badge) => (
                        <span key={badge.label} className={`status-badge ${badge.tone}`}>
                          {badge.label}
                        </span>
                      ))}
                    </div>
                  </button>
                ))
              ) : (
                <div className="muted">当前还没有上传历史。上传 PDF 后，这里会持续保留解析记录和状态。</div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {variant === "ingest" ? (
        <section className="stack-section">
          <div className="panel">
            <h2>文献上传与入库</h2>
            <form onSubmit={handleIngestUpload} className="form-grid">
              <div className="field full">
                <label>文件</label>
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  multiple
                  onChange={(event) => setIngestFiles(Array.from(event.target.files ?? []))}
                  required
                />
              </div>
              <div className="field full">
                <label>标题</label>
                <input
                  value={uploadForm.title}
                  onChange={(event) => setUploadForm({ ...uploadForm, title: event.target.value })}
                  placeholder="可留空，后端会暂时用文件名推断"
                />
              </div>
              <div className="field">
                <label>作者</label>
                <input
                  value={uploadForm.authors}
                  onChange={(event) => setUploadForm({ ...uploadForm, authors: event.target.value })}
                  placeholder="作者1, 作者2"
                />
              </div>
              <div className="field">
                <label>关键词</label>
                <input
                  value={uploadForm.keywords}
                  onChange={(event) => setUploadForm({ ...uploadForm, keywords: event.target.value })}
                  placeholder="数字治理, 协同治理"
                />
              </div>
              <div className="field">
                <label>导师</label>
                <select
                  value={uploadForm.advisorId}
                  onChange={(event) => setUploadForm({ ...uploadForm, advisorId: event.target.value, subFieldId: "" })}
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
                <label>子领域</label>
                <select
                  value={uploadForm.subFieldId}
                  onChange={(event) => setUploadForm({ ...uploadForm, subFieldId: event.target.value })}
                >
                  <option value="">不指定子领域</option>
                  {uploadAdvisor?.sub_fields.map((subField) => (
                    <option key={subField.id} value={subField.id}>
                      {subField.field_name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>研究者上下文</label>
                <select
                  value={uploadForm.researcherId}
                  onChange={(event) => setUploadForm({ ...uploadForm, researcherId: event.target.value })}
                >
                  <option value="">不启用权限过滤</option>
                  {researchers.map((researcher) => (
                    <option key={researcher.id} value={researcher.id}>
                      {researcher.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>导师库标签</label>
                <input
                  value={uploadForm.libraryTags}
                  onChange={(event) => setUploadForm({ ...uploadForm, libraryTags: event.target.value })}
                  placeholder="核心文献, 方法参考"
                />
              </div>
              <div className="field full">
                <label>摘要</label>
                <textarea value={uploadForm.abstract} onChange={(event) => setUploadForm({ ...uploadForm, abstract: event.target.value })} />
              </div>
              <div className="field full">
                <label>备注</label>
                <textarea value={uploadForm.notes} onChange={(event) => setUploadForm({ ...uploadForm, notes: event.target.value })} />
              </div>
              <div className="actions">
                <button className="button" type="submit">
                  上传并入库
                </button>
              </div>
            </form>

            {ingestQueue.length ? (
              <div className="flow upload-queue">
                {ingestQueue.map((item, index) => (
                  <div key={item.id} className="list-card">
                    <strong>{item.name}</strong>
                    <div className="muted">
                      {(item.size / 1024 / 1024).toFixed(2)} MB · {item.status}
                    </div>
                    {index > 0 ? (
                      <div className="muted">当前后端 MVP 仅处理第一份文件；队列结构已为后续批量上传、解析与任务跟踪预留。</div>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div className="panel">
            <h2>上传结果</h2>
            {ingestUploadStatus === "uploading" ? <LoadingState label="正在上传文献并写入导师知识库..." /> : null}
            {uploadResult ? (
              <div className="flow">
                <div className="list-card">
                  <strong>{uploadResult.paper.title}</strong>
                  <div className="muted">Paper ID: {uploadResult.paper.id}</div>
                  <div>作者：{uploadResult.paper.authors.join("、") || "未填写"}</div>
                </div>
                <div className="list-card">
                  <strong>导师库挂接结果</strong>
                  {uploadResult.advisor_links.length ? (
                    <div className="flow">
                      {uploadResult.advisor_links.map((item) => (
                        <div key={item.id}>
                          导师 {item.advisor_id} · 子领域 {item.sub_field_name || "未指定"} · 标签{" "}
                          {item.library_tags.join("、") || "未设置"}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="muted">本次上传没有创建导师知识库关联记录。</div>
                  )}
                </div>
              </div>
            ) : (
              <div className="muted">上传成功后，这里会展示 paper 与 advisor_links 的返回结果。</div>
            )}
          </div>
        </section>
      ) : null}

      <section className="panel">
        <h2>导师知识库查询</h2>
        <div className="form-grid">
          <div className="field">
            <label>{isPrivileged ? "导师" : "我的导师"}</label>
            <select
              value={filterAdvisorId}
              onChange={(event) => {
                setFilterAdvisorId(event.target.value);
                setFilterSubFieldId("");
              }}
            >
              <option value="">请选择导师</option>
              {isPrivileged
                ? advisors.map((advisor) => (
                    <option key={advisor.id} value={advisor.id}>
                      {advisor.name}
                    </option>
                  ))
                : researcherAdvisors.map((advisor) => (
                    <option key={advisor.advisor_id} value={advisor.advisor_id}>
                      {advisor.advisor_name}
                    </option>
                  ))}
            </select>
          </div>

          {isPrivileged ? (
            <div className="field">
              <label>研究者上下文</label>
              <select value={filterResearcherId} onChange={(event) => setFilterResearcherId(event.target.value)}>
                <option value="">不启用权限过滤</option>
                {researchers.map((researcher) => (
                  <option key={researcher.id} value={researcher.id}>
                    {researcher.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="field">
              <label>当前模式</label>
              <div className="list-card">
                <strong>我的研究上下文</strong>
                <div className="muted">普通 researcher 账户不会显示研究者切换入口，只能查看自己已授权的导师知识库结果。</div>
              </div>
            </div>
          )}

          {isPrivileged ? (
            <div className="field">
              <label>子领域</label>
              <select value={filterSubFieldId} onChange={(event) => setFilterSubFieldId(event.target.value)}>
                <option value="">全部子领域</option>
                {filterAdvisor?.sub_fields.map((subField) => (
                  <option key={subField.id} value={subField.id}>
                    {subField.field_name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="field">
            <label>标签</label>
            <input value={filterTag} onChange={(event) => setFilterTag(event.target.value)} placeholder="核心文献" />
          </div>
        </div>
        <div className="actions">
          <button className="button secondary" onClick={handleQueryLibrary} type="button">
            查询导师知识库
          </button>
        </div>
        {queryStatus === "loading" ? <LoadingState label="正在查询导师知识库..." /> : null}

        <div className="table-wrap" style={{ marginTop: 20 }}>
          <table>
            <thead>
              <tr>
                <th>标题</th>
                <th>作者</th>
                <th>子领域</th>
                <th>标签</th>
              </tr>
            </thead>
            <tbody>
              {libraryPapers.length ? (
                libraryPapers.map((item) => (
                  <tr key={item.id}>
                    <td>{item.paper.title}</td>
                    <td>{item.paper.authors.join("、") || "未填写"}</td>
                    <td>{item.sub_field_name || "未指定"}</td>
                    <td>{item.library_tags.join("、") || "未设置"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="muted">
                    当前没有结果。可以先上传文献，或切换 researcher_id 观察权限过滤后的导师知识库视图。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
