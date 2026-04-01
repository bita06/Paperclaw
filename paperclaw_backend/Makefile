.PHONY: help install install-dev db-init db-drop run test lint format clean docker-up docker-down

help:
	@echo "PaperClaw Development Commands"
	@echo "=============================="
	@echo "make install              - Install dependencies"
	@echo "make install-dev          - Install dependencies with dev tools"
	@echo "make db-init              - Initialize database"
	@echo "make db-drop              - Drop all database tables"
	@echo "make run                  - Run FastAPI server"
	@echo "make test                 - Run tests"
	@echo "make lint                 - Run linting"
	@echo "make format               - Format code"
	@echo "make clean                - Clean Python cache"
	@echo "make docker-up            - Start Docker containers"
	@echo "make docker-down          - Stop Docker containers"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio pytest-cov black flake8 isort

db-init:
	python scripts/init_db.py

db-drop:
	python -c "import asyncio; from app.database import drop_db; asyncio.run(drop_db())"

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v --cov=app tests/

lint:
	flake8 app --max-line-length=120
	isort app --check-only

format:
	black app
	isort app

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f api
