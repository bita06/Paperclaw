import { FormEvent, useEffect, useMemo, useState } from "react";

import { agentApi } from "../api/agent";
import { researchersApi } from "../api/researchers";
import { useAuth } from "../auth/AuthContext";
import { TsinghuaSeal } from "../components/branding/TsinghuaSeal";
import { LoadingState } from "../components/common/LoadingState";
import { PageHeader } from "../components/common/PageHeader";
import { StatusNotice } from "../components/common/StatusNotice";
import type {
  AgentExternalEvidenceItem,
  AgentLocalEvidenceItem,
  AgentQueryResponse,
  BuiltinCollectionOption,
  ResearchQaMode,
} from "../types/chat";
import type { Researcher, ResearcherAdvisorLink } from "../types/researcher";
import type { AsyncStatus } from "../types/task";

const modeOptions: Array<{ value: ResearchQaMode; label: string; heading: string; evidenceLabel: string }> = [
  { value: "concept_positioning", label: "概念定位", heading: "概念定位回答", evidenceLabel: "概念脉络" },
  { value: "literature_review", label: "文献综述", heading: "文献综述回答", evidenceLabel: "文献脉络" },
  { value: "mechanism_analysis", label: "机制分析", heading: "机制分析回答", evidenceLabel: "机制链条" },
  { value: "research_design", label: "研究设计", heading: "研究设计建议", evidenceLabel: "研究设计建议" },
];

const defaultQuestion = "数字治理中的回应性概念，在公共管理研究中通常如何被界定与操作化？";

export function ResearchQAPage() {
  const { user, isPrivileged } = useAuth();
  const [researchers, setResearchers] = useState<Researcher[]>([]);
  const [selectedResearcherId, setSelectedResearcherId] = useState("");
  const [researcherDetail, setResearcherDetail] = useState<Researcher | null>(null);
  const [relationships, setRelationships] = useState<ResearcherAdvisorLink[]>([]);
  const [selectedAdvisorId, setSelectedAdvisorId] = useState("");
  const [collectionOptions, setCollectionOptions] = useState<BuiltinCollectionOption[]>([]);
  const [selectedCollectionSlug, setSelectedCollectionSlug] = useState("");
  const [question, setQuestion] = useState(defaultQuestion);
  const [answerMode, setAnswerMode] = useState<ResearchQaMode>("concept_positioning");
  const [includeBuiltinLibrary, setIncludeBuiltinLibrary] = useState(true);
  const [includeUserUploads, setIncludeUserUploads] = useState(false);
  const [includeWebSearch, setIncludeWebSearch] = useState(false);
  const [includeWosSearch, setIncludeWosSearch] = useState(false);
  const [agentResponse, setAgentResponse] = useState<AgentQueryResponse | null>(null);
  const [contextStatus, setContextStatus] = useState<AsyncStatus>("idle");
  const [answerStatus, setAnswerStatus] = useState<AsyncStatus>("idle");
  const [status, setStatus] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);

  const resolvedResearcherId = isPrivileged ? selectedResearcherId : user?.researcher_id || "";

  const accessibleFields = useMemo(
    () => Array.from(new Set(relationships.flatMap((item) => item.sub_fields_access))).filter(Boolean),
    [relationships],
  );

  const answerModeMeta = useMemo(
    () => modeOptions.find((item) => item.value === answerMode) ?? modeOptions[0],
    [answerMode],
  );

  const builtinEvidence = useMemo(
    () => (agentResponse?.local_evidence ?? []).filter((item) => item.source === "builtin_library"),
    [agentResponse],
  );
  const uploadEvidence = useMemo(
    () => (agentResponse?.local_evidence ?? []).filter((item) => item.source === "user_upload"),
    [agentResponse],
  );
  const wosEvidence = agentResponse?.wos_evidence ?? [];
  const webEvidence = agentResponse?.web_evidence ?? [];

  useEffect(() => {
    void (async () => {
      try {
        const [researcherList, builtinCollections] = await Promise.all([
          researchersApi.list(),
          agentApi.listBuiltinCollections(),
        ]);
        setResearchers(researcherList);
        setCollectionOptions(builtinCollections);
        if (isPrivileged) {
          setSelectedResearcherId(researcherList[0]?.id || "");
        } else {
          setSelectedResearcherId(user?.researcher_id || "");
        }
      } catch (error) {
        setStatus({ type: "error", message: `初始化研究问答页失败：${String(error)}` });
      }
    })();
  }, [isPrivileged, user?.researcher_id]);

  useEffect(() => {
    if (!resolvedResearcherId) {
      setResearcherDetail(null);
      setRelationships([]);
      setSelectedAdvisorId("");
      return;
    }

    void (async () => {
      setContextStatus("loading");
      try {
        const [detail, relationList] = await Promise.all([
          researchersApi.getDetail(resolvedResearcherId),
          researchersApi.listRelationships(resolvedResearcherId),
        ]);
        setResearcherDetail(detail);
        setRelationships(relationList);
        setSelectedAdvisorId((prev) =>
          prev && relationList.some((item) => item.advisor_id === prev) ? prev : relationList[0]?.advisor_id ?? "",
        );
        setContextStatus("success");
      } catch (error) {
        setContextStatus("error");
        setStatus({ type: "error", message: `研究者上下文加载失败：${String(error)}` });
      }
    })();
  }, [resolvedResearcherId]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim()) {
      setStatus({ type: "error", message: "请先输入研究问题。" });
      return;
    }
    if (!resolvedResearcherId) {
      setStatus({ type: "error", message: "当前没有可用的研究者上下文。" });
      return;
    }
    if (!includeBuiltinLibrary && !includeUserUploads && !includeWebSearch && !includeWosSearch) {
      setStatus({ type: "error", message: "请至少启用一种证据来源。" });
      return;
    }

    setAnswerStatus("loading");
    setStatus(null);
    try {
      const result = await agentApi.query({
        question,
        mode: answerMode,
        researcher_id: isPrivileged ? resolvedResearcherId : undefined,
        advisor_id: selectedAdvisorId || undefined,
        include_builtin_library: includeBuiltinLibrary,
        include_user_uploads: includeUserUploads,
        include_web: includeWebSearch,
        include_wos: includeWosSearch,
        collection_slug: includeBuiltinLibrary ? selectedCollectionSlug || undefined : undefined,
        top_k: 5,
      });
      setAgentResponse(result);
      setAnswerStatus("success");
      if (!result.local_evidence.length && !result.wos_evidence.length && !result.web_evidence.length) {
        setStatus({
          type: "info",
          message: "当前已返回结构化回答，但所选来源未提供足够证据。建议补充内置文献、上传个人文献，或开启 Web of Science。",
        });
      }
    } catch (error) {
      setAnswerStatus("error");
      setStatus({ type: "error", message: `研究问答生成失败：${String(error)}` });
    }
  };

  const renderLocalEvidence = (items: AgentLocalEvidenceItem[], emptyMessage: string) => {
    if (!items.length) {
      return <div className="muted">{emptyMessage}</div>;
    }
    return items.map((item) => (
      <article key={`${item.source}-${item.paper_id}-${item.section_title ?? "summary"}`} className="evidence-entry">
        <div className="citation-topline">
          <span className="citation-subfield">{item.section_title || item.source_label}</span>
          <span className="muted">{item.year || "年份未填"}</span>
        </div>
        <strong>{item.title}</strong>
        <div className="muted">{item.authors.join("、") || "作者未填"}</div>
        {item.collection_slug ? <div className="muted">板块：{item.collection_slug}</div> : null}
        <p className="citation-abstract">{item.quote_or_summary}</p>
      </article>
    ));
  };

  const renderExternalEvidence = (items: AgentExternalEvidenceItem[], emptyMessage: string) => {
    if (!items.length) {
      return <div className="muted">{emptyMessage}</div>;
    }
    return items.map((item) => (
      <article key={`${item.title}-${item.doi ?? item.external_url ?? item.year ?? item.source}`} className="evidence-entry">
        <div className="citation-topline">
          <span className="citation-subfield">{item.source_label}</span>
          <span className="muted">{item.year || "年份未填"}</span>
        </div>
        <strong>{item.title}</strong>
        <div className="muted">{item.authors.join("、") || "作者未返回"}</div>
        {item.source_name ? <div className="muted">来源：{item.source_name}</div> : null}
        {item.doi ? <div className="muted">DOI：{item.doi}</div> : null}
        <p className="citation-abstract">{item.quote_or_summary}</p>
      </article>
    ));
  };

  return (
    <>
      <PageHeader
        title="研究问答"
        description="围绕当前研究者任务，优先基于系统内置文献库与个人上传文献生成结构化学术回答，并可按需叠加 Web of Science 与网页搜索补充证据。"
        kicker="Research Assistant Workspace"
      />

      {status ? <StatusNotice type={status.type} message={status.message} /> : null}

      <section className="qa-layout research-stage">
        <TsinghuaSeal className="qa-watermark" />

        <aside className="panel qa-context ceremonial-panel">
          <div className="section-heading">
            <span className="section-kicker">Research Context</span>
            <h2>研究者上下文</h2>
          </div>

          {isPrivileged ? (
            <div className="field">
              <label>当前研究者</label>
              <select value={selectedResearcherId} onChange={(event) => setSelectedResearcherId(event.target.value)}>
                <option value="">请选择研究者</option>
                {researchers.map((researcher) => (
                  <option key={researcher.id} value={researcher.id}>
                    {researcher.name}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div className="list-card context-card">
              <strong>我的研究上下文</strong>
              <div className="muted">当前登录账号固定绑定到自己的 researcher 视角，不提供切换其他研究者的入口。</div>
            </div>
          )}

          {contextStatus === "loading" ? (
            <LoadingState label="正在加载研究者上下文..." />
          ) : researcherDetail ? (
            <div className="flow">
              <div className="list-card context-card">
                <strong>{researcherDetail.name}</strong>
                <div className="muted">{researcherDetail.academic_level || "未设置学位层级"}</div>
                <div>{researcherDetail.research_group || "未填写研究组"}</div>
              </div>

              <div className="list-card context-card">
                <strong>当前研究阶段</strong>
                <div>{researcherDetail.current_stage || "尚未设定"}</div>
              </div>

              <div className="list-card context-card">
                <strong>当前研究问题</strong>
                <div>{researcherDetail.current_research_question || "尚未填写研究问题"}</div>
              </div>

              <div className="list-card context-card">
                <strong>已绑定导师</strong>
                <div className="tag-list">
                  {relationships.length ? (
                    relationships.map((item) => (
                      <button
                        key={item.advisor_id}
                        type="button"
                        className={`tag-chip ${selectedAdvisorId === item.advisor_id ? "active" : ""}`}
                        onClick={() => setSelectedAdvisorId(item.advisor_id)}
                      >
                        {item.advisor_name}
                      </button>
                    ))
                  ) : (
                    <span className="muted">尚未绑定导师</span>
                  )}
                </div>
              </div>

              <div className="list-card context-card">
                <strong>当前可访问子领域</strong>
                <div className="tag-list">
                  {accessibleFields.length ? (
                    accessibleFields.map((item) => (
                      <span key={item} className="tag">
                        {item}
                      </span>
                    ))
                  ) : (
                    <span className="muted">尚未配置子领域授权</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="muted">请选择研究者后查看上下文。</div>
          )}
        </aside>

        <section className="panel qa-chat embossed-panel">
          <div className="section-heading">
            <span className="section-kicker">Agent Workspace</span>
            <h2>研究任务问答</h2>
          </div>

          <form onSubmit={handleSubmit} className="qa-form">
            <div className="field full">
              <label>输入研究问题</label>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="例如：数字治理中的回应性概念，在公共管理研究中通常如何被界定与操作化？"
              />
            </div>

            <div className="field full">
              <label>回答模式</label>
              <div className="mode-switch">
                {modeOptions.map((mode) => (
                  <button
                    key={mode.value}
                    type="button"
                    className={`mode-pill ${answerMode === mode.value ? "active" : ""}`}
                    onClick={() => setAnswerMode(mode.value)}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="field full">
              <label>搜索来源</label>
              <div className="source-option-grid">
                <button
                  type="button"
                  className={`source-option ${includeBuiltinLibrary ? "active" : ""}`}
                  onClick={() => setIncludeBuiltinLibrary((value) => !value)}
                >
                  <strong>系统内置文献库</strong>
                  <span>开发者预先导入、按板块组织的本地文献资源。</span>
                </button>
                <button
                  type="button"
                  className={`source-option ${includeUserUploads ? "active" : ""}`}
                  onClick={() => setIncludeUserUploads((value) => !value)}
                >
                  <strong>我的上传文献</strong>
                  <span>仅检索当前账号自己上传并解析成功的文献，不进入公共库。</span>
                </button>
                <button
                  type="button"
                  className={`source-option ${includeWebSearch ? "active" : ""}`}
                  onClick={() => setIncludeWebSearch((value) => !value)}
                >
                  <strong>网页搜索</strong>
                  <span>当前版本仍为结构化占位，用于后续扩展方向演示。</span>
                </button>
                <button
                  type="button"
                  className={`source-option ${includeWosSearch ? "active" : ""}`}
                  onClick={() => setIncludeWosSearch((value) => !value)}
                >
                  <strong>Web of Science</strong>
                  <span>作为外部学术文献补充来源，不替代本地知识库。</span>
                </button>
              </div>
            </div>

            {includeBuiltinLibrary ? (
              <div className="field full">
                <label>内置文献板块</label>
                <select value={selectedCollectionSlug} onChange={(event) => setSelectedCollectionSlug(event.target.value)}>
                  <option value="">全部板块</option>
                  {collectionOptions.map((option) => (
                    <option key={option.collection_slug} value={option.collection_slug}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}

            <div className="actions">
              <button className="button" type="submit" disabled={answerStatus === "loading"}>
                {answerStatus === "loading" ? "正在生成结构化回答..." : "生成结构化回答"}
              </button>
            </div>
          </form>

          <div className="answer-card">
            <div className="answer-eyebrow">{agentResponse?.answer_title || answerModeMeta.heading}</div>
            <h3>{agentResponse?.direct_answer || "系统将结合当前研究者上下文与所选来源范围，生成结构化学术回答。"}</h3>

            <div className="list-card context-card">
              <strong>当前来源策略</strong>
              <div className="muted">
                {[
                  includeBuiltinLibrary ? "系统内置文献库" : null,
                  includeUserUploads ? "我的上传文献" : null,
                  includeWosSearch ? "Web of Science" : null,
                  includeWebSearch ? "网页搜索（占位）" : null,
                ]
                  .filter(Boolean)
                  .join(" + ") || "未选择来源"}
              </div>
            </div>

            {answerStatus === "loading" ? <LoadingState label="正在基于所选来源生成回答..." /> : null}

            {agentResponse ? (
              <>
                <div className="answer-section">
                  <strong>{answerModeMeta.evidenceLabel}</strong>
                  {agentResponse.concept_lineage.length ? (
                    <ul>
                      {agentResponse.concept_lineage.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">当前模型未输出额外的脉络化内容。</p>
                  )}
                </div>

                <div className="answer-section">
                  <strong>后续建议</strong>
                  {agentResponse.next_steps.length ? (
                    <ul>
                      {agentResponse.next_steps.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">当前没有额外建议。</p>
                  )}
                </div>

                <div className="answer-section">
                  <strong>限制说明</strong>
                  {agentResponse.limitations.length ? (
                    <ul>
                      {agentResponse.limitations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">当前未返回限制说明。</p>
                  )}
                </div>

                <div className="answer-section">
                  <strong>证据源状态</strong>
                  <div className="tag-list">
                    <span className="tag">本地来源：{agentResponse.source_status.local}</span>
                    <span className="tag">Web of Science：{agentResponse.source_status.wos}</span>
                    <span className="tag">网页搜索：{agentResponse.source_status.web}</span>
                  </div>
                  {agentResponse.source_status.messages.length ? (
                    <ul>
                      {agentResponse.source_status.messages.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </>
            ) : (
              <div className="answer-section">
                <strong>回答结构</strong>
                <ul>
                  <li>直接回答：优先基于系统内置文献库与个人上传文献给出研究任务型结论。</li>
                  <li>脉络整理：按模式输出概念脉络、文献脉络、机制链条或研究设计建议。</li>
                  <li>证据分源：内置文献库、个人上传、WoS 与网页搜索会分别展示。</li>
                </ul>
              </div>
            )}
          </div>
        </section>

        <aside className="panel qa-citation ceremonial-panel">
          <div className="section-heading">
            <span className="section-kicker">Evidence Panel</span>
            <h2>引用依据区</h2>
          </div>

          <div className="list-card citation-note">
            <strong>来源说明</strong>
            <div className="muted">
              系统内置文献库由开发者预先导入并按板块组织；“我的上传文献”仅属于当前用户本人；WoS 与网页搜索属于外部补充来源。
            </div>
          </div>

          <div className="flow evidence-source-stack">
            <div className="list-card citation-card evidence-source-card">
              <strong>系统内置文献库证据</strong>
              {renderLocalEvidence(
                builtinEvidence,
                includeBuiltinLibrary ? "当前未返回系统内置文献库证据。" : "当前未启用系统内置文献库。",
              )}
            </div>

            <div className="list-card citation-card evidence-source-card">
              <strong>我的上传文献证据</strong>
              {renderLocalEvidence(
                uploadEvidence,
                includeUserUploads ? "当前未返回个人上传文献证据。" : "当前未启用我的上传文献。",
              )}
            </div>

            <div className="list-card citation-card evidence-source-card">
              <strong>WoS 学术证据</strong>
              {renderExternalEvidence(
                wosEvidence,
                includeWosSearch ? "当前未返回 WoS 学术证据。" : "当前未启用 Web of Science。",
              )}
            </div>

            <div className="list-card citation-card evidence-source-card">
              <strong>网页搜索证据</strong>
              {renderExternalEvidence(
                webEvidence,
                includeWebSearch ? "当前未返回网页搜索结果。" : "当前未启用网页搜索。",
              )}
            </div>
          </div>
        </aside>
      </section>
    </>
  );
}
