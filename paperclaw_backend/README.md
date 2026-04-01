# PaperClaw Backend

Specialized research assistant for public administration scholars.

## Quick Start

### Local Development

1. **Create and activate virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Setup environment variables:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize database:**
```bash
python scripts/init_db.py
```

5. **Run the server:**
```bash
uvicorn app.main:app --reload
```

Server will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Docker Development

```bash
# Start all services
docker-compose up -d

# Initialize database
docker-compose exec api python scripts/init_db.py

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

## Project Structure

```
app/
├── api/v1/              # API endpoints
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic models
├── services/            # Business logic
├── tools/               # Utility functions
├── config.py            # Configuration
├── database.py          # Database setup
├── dependencies.py      # FastAPI dependencies
├── exceptions.py        # Custom exceptions
└── main.py              # Application entry point

tests/                    # Test files
scripts/                  # Utility scripts
migrations/              # Database migrations (Alembic)
```

## Available Commands

```bash
make install              # Install dependencies
make install-dev         # Install development dependencies
make run                 # Run development server
make test               # Run tests with coverage
make lint               # Run linting
make format             # Format code
make db-init            # Initialize database
make docker-up          # Start Docker services
```

## Features (Planned)

- ✅ Database models for researchers, advisors, papers
- 🚀 API endpoints for CRUD operations
- 📚 Advisor library management with multi-classification
- 🔍 Vector search and retrieval
- 🤖 LLM integration for concept extraction
- 📊 Reading history and interaction tracking
- 🔐 Authentication and authorization

## API Endpoints (v1)

(To be implemented as features are completed)

- `/researchers` - Researcher management
- `/advisors` - Advisor and library management
- `/papers` - Paper/literature management
- `/search` - Search and retrieval
- `/concepts` - Concept management
- `/agent` - Agent-based queries

## Technologies

- **Framework:** FastAPI
- **Database:** PostgreSQL + SQLAlchemy
- **Async:** asyncio, asyncpg
- **Vector DB:** Pinecone
- **LLM:** OpenAI GPT
- **Cache:** Redis
- **Testing:** pytest
- **Documentation:** FastAPI Swagger UI

## Development Guidelines

1. **Code Style:** Follow PEP 8
2. **Type Hints:** Use Python type hints
3. **Docstrings:** Use Google-style docstrings
4. **Tests:** Write tests for new features
5. **Git Commits:** Use conventional commit messages

## License

Copyright © 2024 PaperClaw Project
