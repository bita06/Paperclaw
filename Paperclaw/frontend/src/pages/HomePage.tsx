import { PageHeader } from "../components/common/PageHeader";
import { StatCard } from "../components/common/StatCard";
import { TsinghuaSeal } from "../components/branding/TsinghuaSeal";

const completedCapabilities = [
  "导师档案、子领域与研究方向维护",
  "研究者档案、研究阶段与研究问题记录",
  "研究者—导师关系管理与多导师绑定",
  "关系级 sub_fields_access 子领域授权",
  "文献上传、导师库挂接与标签管理",
  "按 researcher_id 过滤导师库可见文献",
];

const currentWorkflow = [
  "先建立导师档案与子领域，明确导师知识边界。",
  "再为研究者填写当前研究阶段、研究问题与已绑定导师。",
  "通过关系级授权配置研究者在不同导师名下可访问的子领域。",
  "把文献入库到导师知识库，并按子领域与标签组织。",
  "在研究问答页中，以研究者上下文为核心查看结构化回答与引用依据。",
];

const nextExtensions = [
  "PDF / DOCX 元数据自动解析",
  "章节切分与文献片段引用",
  "概念抽取与概念定位",
  "个性化检索与导师优先排序",
  "真实 Agent 问答与写作辅助",
];

export function HomePage() {
  return (
    <>
      <PageHeader
        title="研究工作台"
        description="PaperClaw 面向公共管理研究者，围绕“研究者上下文—导师知识库—权限过滤—结构化回答”建立研究辅助闭环。本页用于向老师快速说明平台当前已完成的能力与可演示路径。"
        kicker="Institution Overview"
      />

      <section className="hero-banner institutional-hero">
        <TsinghuaSeal className="hero-watermark" />
        <div className="hero-copy panel ceremonial-panel">
          <span className="section-kicker">Platform Positioning</span>
          <h2>面向谁</h2>
          <p>
            该平台面向清华公管内部的研究者、导师与研究助理。它不是通用聊天工具，而是以研究任务推进为目标，把导师库、授权子领域和文献依据组织进同一研究工作流。
          </p>

          <h2>解决什么问题</h2>
          <p>
            当前研究辅助最大的断点在于：研究问题、导师知识边界、可访问文献与回答依据往往分散。PaperClaw
            通过研究者档案、导师指导关系和导师知识库，把“谁在研究什么、能看哪些文献、为什么给出这段回答”连接起来。
          </p>
          <div className="institution-note">
            平台定位于院内研究辅助场景，强调研究秩序、导师知识边界与可解释引用，而不是无依据的通用问答。
          </div>
        </div>

        <div className="panel value-map embossed-panel">
          <span className="section-kicker">Demonstration Path</span>
          <h2>平台工作链路</h2>
          <div className="value-steps">
            <div className="flow-step">研究者档案：记录当前阶段、问题与导师关系</div>
            <div className="flow-step">导师知识库：按子领域与标签管理文献</div>
            <div className="flow-step">关系级授权：限定研究者可访问的导师子领域</div>
            <div className="flow-step">研究问答：在有依据的前提下展示结构化回答</div>
          </div>
        </div>
      </section>

      <section className="grid-3">
        <StatCard label="当前稳定入口" value="7" hint="研究工作台、研究问答、我的导师库与四类管理页" />
        <StatCard label="可演示核心逻辑" value="授权驱动" hint="研究者上下文决定导师库文献的可见范围与引用结果" />
        <StatCard label="后续扩展方式" value="平滑接入" hint="高级检索与 Agent 将沿用当前工作台结构继续扩展" />
      </section>

      <section className="hero">
        <div className="panel ceremonial-panel">
          <span className="section-kicker">Completed Today</span>
          <h2>当前已完成的能力</h2>
          <div className="tag-list">
            {completedCapabilities.map((item) => (
              <span key={item} className="tag">
                {item}
              </span>
            ))}
          </div>
        </div>

        <div className="panel ceremonial-panel">
          <span className="section-kicker">How To Demo</span>
          <h2>建议演示顺序</h2>
          <div className="flow">
            {currentWorkflow.map((item, index) => (
              <div key={item} className="flow-step">
                <strong>{index + 1}. </strong>
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="hero">
        <div className="panel embossed-panel">
          <span className="section-kicker">System Logic</span>
          <h2>老师最容易看懂的关系图</h2>
          <div className="flow">
            <div className="flow-step">导师档案 → 子领域</div>
            <div className="flow-step">研究者档案 → 当前研究问题 / 当前研究阶段</div>
            <div className="flow-step">导师指导关系 → relationship_type / access_level / sub_fields_access</div>
            <div className="flow-step">文献入库 → 挂接导师与子领域</div>
            <div className="flow-step">研究问答 → 按研究者上下文展示结构化回答与引用依据</div>
          </div>
        </div>

        <div className="panel embossed-panel">
          <span className="section-kicker">Next Layer</span>
          <h2>后续可平滑扩展的能力</h2>
          <div className="flow">
            {nextExtensions.map((item) => (
              <div key={item} className="flow-step">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
