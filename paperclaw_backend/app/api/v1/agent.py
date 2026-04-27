from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, resolve_researcher_context
from app.models import User
from app.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    BuiltinCollectionOption,
    SemanticSearchRequest,
    SemanticSearchResponse,
)
from app.services.agent_service import agent_service
from app.services.local_retrieval_service import local_retrieval_service
from app.services.semantic_search_service import semantic_search_service

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.get("/builtin-collections", response_model=list[BuiltinCollectionOption])
async def list_builtin_collections(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[BuiltinCollectionOption]:
    collections = await local_retrieval_service.list_builtin_collections(db)
    return [
        BuiltinCollectionOption(collection_slug=slug, label=slug.replace("-", " ").replace("_", " ").strip() or slug)
        for slug in collections
    ]


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(
    payload: AgentQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentQueryResponse:
    researcher_context = resolve_researcher_context(current_user, payload.researcher_id)
    return await agent_service.query(
        db,
        current_user=current_user,
        researcher_id=researcher_context,
        advisor_id=payload.advisor_id,
        question=payload.question,
        mode=payload.mode,
        top_k=payload.top_k,
        include_builtin_library=payload.include_builtin_library,
        include_user_uploads=payload.include_user_uploads,
        use_web_search=payload.include_web,
        use_wos_search=payload.include_wos,
        collection_slug=payload.collection_slug,
        session_id=payload.session_id,
    )


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(
    payload: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SemanticSearchResponse:
    researcher_context = resolve_researcher_context(current_user, payload.researcher_id)
    researcher = await agent_service._get_researcher(db, researcher_context)
    items = await semantic_search_service.search_chunks(
        db,
        current_user=current_user,
        researcher=researcher,
        query=payload.query,
        include_builtin_library=payload.include_builtin_library,
        include_user_uploads=payload.include_user_uploads,
        collection_slug=payload.collection_slug,
        top_k=payload.top_k,
    )
    return SemanticSearchResponse(query=payload.query, items=items)
