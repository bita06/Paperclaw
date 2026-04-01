"""
FastAPI Application Factory
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.config import settings
from app.database import async_session_maker, init_db
from app.services.auth_service import auth_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting PaperClaw application...")
    await init_db()
    async with async_session_maker() as session:
        await auth_service.ensure_bootstrap_developer_admin(session)
    print("Database initialized")
    yield
    print("Shutting down PaperClaw application...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="PaperClaw - Specialized Research Assistant for Public Administration Scholars",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


app.include_router(v1_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
