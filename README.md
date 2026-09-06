<div align="center">

# PaperClaw

### 面向公共管理研究者的研究任务型学术智能体

将研究者画像、导师知识库、语义检索与大模型推理连接起来，帮助研究者从“找到文献”走向“形成有证据的研究判断”。

<p>
  <img alt="Status: MVP" src="https://img.shields.io/badge/status-MVP-3B82F6?style=flat-square">
  <img alt="Python 3.10" src="https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white">
  <img alt="React 18" src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=111827">
  <img alt="PostgreSQL + pgvector" src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white">
</p>

<p>
  <a href="#demo">产品演示</a> ·
  <a href="#features">核心能力</a> ·
  <a href="#architecture">系统架构</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#api">API</a>
</p>

<img src="docs/assets/researcher-workspace.png" alt="PaperClaw 研究者工作台设计图" width="960">

<sub>研究者上下文、Agent 对话与授权文献证据在同一工作台内协同。</sub>

</div>

## PaperClaw 是什么？

PaperClaw 不是一个通用聊天机器人，而是面向公共管理研究场景的学术 Agent。它先理解研究者是谁、处于什么研究阶段以及正在解决什么问题，再在已授权的导师知识库、本地文献库和外部证据中检索，最终生成可追溯的结构化回答。

核心链路：

```text
研究者画像 → 授权知识库 → 检索与重排 → LLM 推理 → 结构化回答 → 研究推进
```

<a id="demo"></a>

## 🎬 产品演示

<div align="center">
  <a href="https://raw.githubusercontent.com/bita06/Paperclaw/main/docs/assets/research-question-demo.mp4">
    <img src="docs/assets/research-demo-preview.gif" alt="PaperClaw 研究问答流程演示" width="900">
  </a>
  <p><strong>进入页面自动播放前 15 秒 · 点击动图查看完整 MP4</strong></p>
</div>

也可以从仓库中[查看或下载视频文件](docs/assets/research-question-demo.mp4)。

<a id="features"></a>

## ✨ 核心能力

| 能力 | PaperClaw 如何支持研究 |
| --- | --- |
| 研究者上下文 | 记录研究阶段、研究任务、研究问题和导师关系，为问答提供稳定上下文 |
| 权限化导师知识库 | 按导师、子领域和指导关系控制文献访问范围，避免无关材料干扰 |
| PDF 解析与入库 | 提取标题、作者、年份、摘要与章节，并生成可检索的文献片段 |
| 本地语义检索 | 使用 PostgreSQL + pgvector 从授权文献中召回相关证据 |
| 多源证据补充 | 可结合 Tavily 网页搜索与 Web of Science 学术检索补充外部证据 |
| 四种研究模式 | 支持概念定位、文献综述、机制分析和研究设计 |
| 结构化学术回答 | 由 MiniMax 综合本地与外部证据，输出分析、依据与后续研究建议 |

### 文献处理流程

```text
PDF 上传
   ↓
元数据与正文解析
   ↓
Paper / Section / Chunk 持久化
   ↓
向量化与 pgvector 索引
   ↓
按研究者权限检索
   ↓
结构化回答与证据展示
```

<a id="architecture"></a>

## 🏗️ 系统架构

<div align="center">
  <img src="docs/assets/system-architecture.png" alt="PaperClaw 系统架构图" width="650">
</div>

PaperClaw 采用前后端分离架构。React 工作台通过 FastAPI 访问研究者、导师、论文与 Agent 服务；PostgreSQL 负责业务数据，pgvector 负责语义向量检索。

### 导师知识库的分域授权

同一位导师可以维护多个研究子领域，并根据具体指导关系向不同研究者开放不同的文献范围。跨领域研究者也可以同时获得多个子领域的授权。

<div align="center">
  <img src="docs/assets/advisor-access-control.png" alt="PaperClaw 导师知识库分域授权示意图" width="900">
</div>

## 🧰 技术栈

| 层级 | 技术 |
| --- | --- |
| Web 前端 | React 18、TypeScript、Vite |
| API 后端 | FastAPI、Pydantic、SQLAlchemy |
| 数据与检索 | PostgreSQL 16、pgvector、全文检索 |
| 文献处理 | PyMuPDF、pypdf、章节切分、向量化 |
| 模型与搜索 | MiniMax、Tavily、Web of Science Starter API |
| 基础设施 | Docker Compose、Redis |

<a id="quick-start"></a>

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Docker Desktop（用于 PostgreSQL / pgvector 与 Redis）

### 1. 克隆仓库

```bash
git clone https://github.com/bita06/Paperclaw.git
cd Paperclaw
```

### 2. 启动数据库

```powershell
cd paperclaw_backend
docker compose up -d db redis
```

### 3. 配置并启动后端

```powershell
Copy-Item .env.example .env
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python scripts\init_db.py
python -m uvicorn app.main:app --reload
```

编辑 `paperclaw_backend/.env`，至少设置：

```dotenv
DATABASE_URL=postgresql+asyncpg://paperclaw_user:password@127.0.0.1:5432/paperclaw_db
SECRET_KEY=replace_with_a_secure_random_secret
MINIMAX_API_KEY=your_minimax_api_key
```

需要网页搜索或 Web of Science 时，再配置 `TAVILY_API_KEY` 或 `WOS_API_KEY`。所有真实密钥都应只保存在本地 `.env` 中。

后端默认运行于 <http://127.0.0.1:8000>，Swagger 文档位于 <http://127.0.0.1:8000/docs>。

### 4. 启动前端

打开新的终端：

```powershell
cd Paperclaw\frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

访问 <http://127.0.0.1:5173>。

<details>
<summary><strong>使用 Docker Compose 启动完整后端</strong></summary>

```powershell
cd paperclaw_backend
docker compose up -d
docker compose exec api python scripts/init_db.py
```

查看日志或停止服务：

```powershell
docker compose logs -f api
docker compose down
```

</details>

<a id="api"></a>

## 🔌 主要 API

所有接口挂载于 `/api/v1`：

| 模块 | 代表性接口 |
| --- | --- |
| 身份认证 | `POST /auth/register`、`POST /auth/login`、`GET /auth/me` |
| 研究者 | `GET/POST /researchers/`、`PUT /researchers/{id}/stage` |
| 导师与权限 | `GET/POST /advisors`、`POST /researchers/{id}/advisors` |
| 论文与文件 | `POST /papers/upload`、`POST /files/upload`、`GET /files/{id}/status` |
| 语义检索 | `POST /agent/semantic-search` |
| 研究问答 | `POST /agent/query` |

完整请求参数与响应结构请以本地 Swagger 文档为准。

## 📁 项目结构

```text
Paperclaw/
├── Paperclaw/frontend/          # React + TypeScript 前端
├── paperclaw_backend/
│   ├── app/api/v1/              # FastAPI 路由
│   ├── app/models/              # SQLAlchemy 数据模型
│   ├── app/schemas/             # Pydantic 请求与响应结构
│   ├── app/services/            # 解析、检索、Agent 与外部搜索服务
│   ├── scripts/                 # 初始化、导入与索引维护脚本
│   └── docker-compose.yml       # PostgreSQL、Redis 与 API
├── Paperclaw/                   # 架构与功能设计文档
└── docs/assets/                 # README 图片与演示视频
```

## 📊 当前状态

项目目前处于 MVP 阶段，已完成研究者/导师关系管理、PDF 解析入库、本地文献语义检索、多源搜索编排和结构化研究问答主链路。

开发环境当前使用的法治与公共行政语料包含 281 篇文献、12,230 个检索片段；语料文件与数据库内容不随公开仓库分发，使用者需导入自己的 PDF。

### 已知限制

- MiniMax、Tavily 与 Web of Science 功能需要分别配置有效 API Key。
- 外部学术检索的可用性取决于对应服务账户与网络状态。
- 当前界面与工作流仍在迭代，演示内容代表 MVP，而非最终产品形态。

## 📚 设计文档

- [技术架构设计](Paperclaw/01_技术架构设计.md)
- [导师库多分类管理实现细节](Paperclaw/02_导师库多分类管理_实现细节.md)
- [项目结构设计](Paperclaw/03_项目结构设计.md)
- [差异化功能分析](Paperclaw/paperclaw_差异化功能分析.md)

## 🤝 参与项目

欢迎通过 Issue 提交问题、功能建议或研究场景需求，也欢迎通过 Pull Request 参与改进。

---

<div align="center">
  <strong>PaperClaw — From papers to research insight.</strong>
</div>
