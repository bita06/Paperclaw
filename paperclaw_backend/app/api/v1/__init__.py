"""
API v1 Routers
"""
from fastapi import APIRouter

from app.api.v1 import advisor_library, agent, auth, files, papers, researchers, tasks

router = APIRouter()

router.include_router(auth.router)
router.include_router(agent.router)
router.include_router(files.router)
router.include_router(tasks.router)
router.include_router(papers.router)
router.include_router(advisor_library.router)
router.include_router(researchers.router)
