# PaperClaw

PaperClaw is a private research-assistant platform for public administration work. It combines a local paper library, researcher/advisor context, PDF parsing, structured research Q&A, and optional evidence enhancement from MiniMax and Web of Science.

This repository is prepared for private collaboration. Real API keys, local uploads, local corpora, and personal demo materials are intentionally excluded from Git.

## Repository structure

```text
paperclaw/
├─ Paperclaw/                    # Frontend app and project notes
│  ├─ frontend/                  # React + Vite frontend
│  ├─ config/                    # Frontend-side config assets
│  └─ *.md                       # Project design / onboarding notes
├─ paperclaw_backend/            # FastAPI backend
│  ├─ app/                       # API, models, schemas, services
│  ├─ scripts/                   # Utility and import scripts
│  ├─ requirements.txt           # Python dependencies
│  ├─ docker-compose.yml         # Local Postgres / Redis / API stack
│  └─ .env.example               # Safe backend env template
├─ data/                         # Local builtin PDF corpus (ignored by Git)
└─ paper_uploads/                # Local uploads and generated files (ignored by Git)
```

## Tech stack

- Frontend: React 18, Vite, TypeScript, React Router
- Backend: FastAPI, SQLAlchemy 2, asyncpg, Pydantic Settings
- Database: PostgreSQL 15
- PDF parsing: pypdf + MiniMax enhancement
- LLM answer generation: MiniMax
- External evidence: Web of Science Starter API

## Environment requirements

- Python 3.12 recommended
- Node.js 18+ and npm
- PostgreSQL 15 (or Docker Desktop to run the included compose stack)
- Optional: Redis for cache-related local features
- Optional: GitHub CLI (`gh`) if you want to create/push repositories from the terminal

## First-time setup

### 1. Clone the repository

```bash
git clone <private-repo-url>
cd paperclaw
```

### 2. Configure backend environment

```bash
cd paperclaw_backend
copy .env.example .env
```

Then edit `.env` and fill in the real local values.

Required for the backend to start:
- `DATABASE_URL`
- `SECRET_KEY`

Required for MiniMax-backed structured answers and PDF parse enhancement:
- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL` (default is already filled)
- `MINIMAX_MODEL` (default is already filled)
- `ENABLE_LLM_FEATURES=true`

Optional but recommended:
- `WOS_API_KEY` for Web of Science evidence
- `BOOTSTRAP_DEVELOPER_ADMIN_EMAIL`
- `BOOTSTRAP_DEVELOPER_ADMIN_PASSWORD`
- `BOOTSTRAP_DEVELOPER_ADMIN_NAME`
- `BOOTSTRAP_DEVELOPER_ADMIN_DEPARTMENT`

### 3. Configure frontend environment

```bash
cd ..\Paperclaw\frontend
copy .env.example .env.local
```

Default local development can use:
- `VITE_API_BASE_URL=/api/v1`

This works with the Vite proxy in `vite.config.ts`, which forwards `/api` to `http://127.0.0.1:8000`.

If you run the frontend without the proxy or against another backend host, set:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Local services

### Option A: Docker for Postgres / Redis

From `paperclaw_backend/`:

```bash
docker compose up -d db redis
```

Default local database credentials in `.env.example` match the compose file:
- user: `paperclaw_user`
- password: `password`
- db: `paperclaw_db`
- port: `5432`

### Option B: Your own PostgreSQL instance

If you already have PostgreSQL installed locally, just point `DATABASE_URL` to that instance.

## Backend startup

From `paperclaw_backend/`:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts\init_db.py
python -m uvicorn app.main:app --reload
```

Backend URLs:
- App: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`

Notes:
- `app.main` will also attempt table initialization on startup.
- The backend creates required upload directories when upload/parse flows run.
- Builtin corpus files are not committed. If you want to import builtin PDFs, place them under `data/builtin_library/<collection_slug>/*.pdf` and run the import script locally.

Builtin library import:

```bash
python -m scripts.import_builtin_library --library-root ..\data\builtin_library
```

If you want a smaller first test, add `--collection-slug <slug>`.

## Frontend startup

From `Paperclaw/frontend/`:

```bash
npm install
npm run dev
```

Frontend URL:
- `http://127.0.0.1:5173` or `http://localhost:5173`

Production-style sanity check:

```bash
npm run build
```

## Default local ports

- Frontend (Vite): `5173`
- Backend (FastAPI): `8000`
- PostgreSQL: `5432`
- Redis: `6379`

## What is intentionally not committed

The following stay local and are ignored by Git:
- `paperclaw_backend/.env`
- all `.env.local` / local secret files
- `paper_uploads/`
- `data/` builtin PDF corpus and any local vector/corpus data
- `node_modules/`, `dist/`, `venv/`, `.venv/`, `__pycache__/`
- local logs, caches, sqlite/db files
- personal demo assets such as videos, PPTX, DOCX, screenshots at the repository root

## Common setup notes

### Login works locally but the page still says the model is unavailable

Check:
- `paperclaw_backend/.env` has a real `MINIMAX_API_KEY`
- `ENABLE_LLM_FEATURES=true`
- backend was restarted after changing `.env`

### Backend fails to start with database connection refused

Usually PostgreSQL is not running. Start it with:

```bash
cd paperclaw_backend
docker compose up -d db
```

### Builtin import hangs or is slow

Large PDF batches may spend time in parsing and optional model enhancement. For bulk import, you can temporarily disable LLM enhancement in your local shell before running the import script.

### Frontend cannot reach the backend

Check:
- backend is running on `127.0.0.1:8000`
- frontend is using `VITE_API_BASE_URL=/api/v1` with the Vite proxy, or a full backend URL if not using the proxy
- backend `CORS_ORIGINS` includes `http://localhost:5173` and `http://127.0.0.1:5173`

## What collaborators still need to fill manually

Every collaborator must create their own local files and fill real values for:
- `paperclaw_backend/.env`
- optionally `Paperclaw/frontend/.env.local`

At minimum, real local values are needed for:
- `DATABASE_URL`
- `SECRET_KEY`
- `MINIMAX_API_KEY`

Optional values depending on features used:
- `WOS_API_KEY`
- bootstrap admin credentials

## Collaboration notes

- Keep the repository private.
- Never commit real API keys, access tokens, or passwords.
- Builtin corpora and user-uploaded materials stay local by default; share them through a separate secure channel if needed.
