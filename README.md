# PaperClaw

PaperClaw 是一个面向公共管理研究的本地文献智能问答工具。它将已导入的学术 PDF 切分为可检索的文献片段，结合网页搜索和大模型结构化生成能力，帮助研究者围绕概念定位、文献综述、机制分析和研究设计快速获得有依据的学术回答。

## 已实现功能

- 本地文献语义检索：基于 PostgreSQL + pgvector 检索内置文献库中的相关 chunk。
- Tavily 网页搜索：在本地文献之外补充公开网页证据。
- MiniMax 结构化回答：综合本地文献、网页证据等来源生成可读的研究回答。
- 四种回答模式：概念定位、文献综述、机制分析、研究设计。
- 证据分源展示：前端分别展示本地文献证据、网页搜索证据和外部学术证据状态。
- 研究者、导师、导师文献库与上传文献管理。

## 技术栈

- 后端：FastAPI、SQLAlchemy、PostgreSQL、pgvector
- 前端：React、Vite、TypeScript
- 模型与外部服务：MiniMax、Tavily
- 文献处理：PDF 解析、chunk 切分、向量化检索

## 当前数据状态

- 已导入法治与公共行政主题文献：281 篇
- 已生成检索 chunk：12230 个

## 项目结构

```text
paperclaw/
├─ paperclaw_backend/
│  ├─ app/
│  │  ├─ api/v1/          # FastAPI v1 接口
│  │  ├─ models/          # SQLAlchemy 数据模型
│  │  ├─ schemas/         # Pydantic 请求/响应结构
│  │  ├─ services/        # 文献解析、语义检索、Agent、外部搜索等业务逻辑
│  │  ├─ config.py        # 环境变量与配置
│  │  ├─ database.py      # 数据库连接与初始化
│  │  ├─ dependencies.py  # 鉴权与上下文依赖
│  │  ├─ exceptions.py    # API 异常封装
│  │  └─ main.py          # FastAPI 应用入口
│  ├─ scripts/            # 初始化、内置文献导入、chunk 重建等脚本
│  ├─ docker-compose.yml  # 本地 Postgres / Redis / API 服务
│  ├─ Makefile            # 常用开发命令
│  └─ requirements.txt
├─ Paperclaw/frontend/    # React + Vite 前端
├─ data/                  # 本地内置 PDF 文献库
└─ paper_uploads/         # 用户上传与解析文件
```

## 启动方式

### 方式一：本地启动

后端：

```powershell
cd paperclaw_backend
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

后端默认地址：

```text
http://127.0.0.1:8000
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

前端：

```powershell
cd Paperclaw\frontend
npm install
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:5173
```

### 方式二：Docker 启动

从后端目录启动服务：

```powershell
cd paperclaw_backend
docker compose up -d
```

初始化数据库：

```powershell
docker compose exec api python scripts/init_db.py
```

查看后端日志：

```powershell
docker compose logs -f api
```

停止服务：

```powershell
docker compose down
```

## Make 命令

`paperclaw_backend/Makefile` 仍保留可用，常用命令如下：

```bash
make install      # 安装后端依赖
make install-dev  # 安装后端依赖和开发工具
make db-init      # 初始化数据库
make db-drop      # 删除所有数据库表
make run          # 启动 FastAPI 开发服务
make test         # 运行测试
make lint         # 运行 flake8 / isort 检查
make format       # black + isort 格式化
make clean        # 清理 Python 缓存
make docker-up    # 启动 Docker 服务
make docker-down  # 停止 Docker 服务
make docker-logs  # 查看 API 日志
```

## API Endpoints (v1)

主要接口挂载在 `/api/v1` 下：

- `POST /auth/register`：注册用户
- `POST /auth/login`：登录并获取 token
- `POST /auth/logout`：退出登录
- `GET /auth/me`：获取当前用户
- `POST /auth/admin-users`：创建管理员/教师等用户
- `GET /researchers/`、`POST /researchers/`：研究者列表与创建
- `GET /researchers/{researcher_id}`、`PUT /researchers/{researcher_id}`、`DELETE /researchers/{researcher_id}`：研究者详情、更新与删除
- `PUT /researchers/{researcher_id}/stage`：更新研究阶段
- `GET /researchers/{researcher_id}/advisors`、`POST /researchers/{researcher_id}/advisors`：研究者-导师关系管理
- `GET /advisors`、`POST /advisors`：导师列表与创建
- `GET /advisors/{advisor_id}`、`PUT /advisors/{advisor_id}`、`DELETE /advisors/{advisor_id}`：导师详情、更新与删除
- `POST /advisors/{advisor_id}/sub-fields`、`GET /advisors/{advisor_id}/sub-fields`：导师研究子领域管理
- `POST /advisors/{advisor_id}/papers`、`GET /advisors/{advisor_id}/papers`：导师文献库管理
- `POST /papers/`、`GET /papers/`：论文创建与列表
- `POST /papers/upload`：上传论文
- `POST /papers/chunks/backfill`：重建/补齐 chunk
- `GET /papers/{paper_id}`、`PUT /papers/{paper_id}`、`DELETE /papers/{paper_id}`：论文详情、更新与删除
- `POST /files/upload`：上传文件并创建解析任务
- `GET /files/history`：文件上传历史
- `GET /files/{file_id}/status`：文件解析状态
- `GET /tasks/{task_id}`：任务状态
- `GET /agent/builtin-collections`：内置文献库板块列表
- `POST /agent/semantic-search`：本地语义检索
- `POST /agent/query`：研究问答 Agent，支持本地文献、Tavily 网页搜索和 WoS 证据输入

完整参数与响应结构以 Swagger 文档为准：`http://127.0.0.1:8000/docs`。

## 环境变量

后端配置文件位于：

```text
paperclaw_backend/.env
```

至少需要配置：

- `DATABASE_URL`
- `SECRET_KEY`
- `MINIMAX_API_KEY`
- `TAVILY_API_KEY`

可选配置：

- `WOS_API_KEY`
- `ENABLE_WEB_SEARCH`
- `ENABLE_WOS_SEARCH`
- `BOOTSTRAP_DEVELOPER_ADMIN_EMAIL`
- `BOOTSTRAP_DEVELOPER_ADMIN_PASSWORD`

## 已知限制

- Web of Science 集成代码已接入 WoS Starter API，但当前 Clarivate 服务器返回 `512 Internal server error`，因此 WoS 学术搜索暂时不可用。
- Tavily 和 MiniMax 需要在 `paperclaw_backend/.env` 中配置有效 API Key。
- 当前系统主要围绕已导入的法治与公共行政文献库进行检索，其他主题需要先导入相应 PDF 后再使用。
