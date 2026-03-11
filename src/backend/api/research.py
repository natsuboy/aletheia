"""DeepResearch API 端点"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.backend.security import InputValidator
from src.backend.middleware.rate_limit import rate_limit
from src.rag.conversation import ConversationMemory
from src.research.engine import ResearchEngine
from src.research.models import ResearchSession

router = APIRouter(prefix="/api/research", tags=["research"])


# ── request / response models ──────────────────────────────────

class StartResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    project_id: str = Field(..., min_length=1, max_length=100)


class ContinueResearchRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)


# ── dependency injection ────────────────────────────────────────

def _get_engine(request: Request) -> ResearchEngine:
    """从 app.state 构建 ResearchEngine"""
    components = request.app.state.rag_components
    return ResearchEngine(
        llm_client=components["llm_client"],
        retriever=components["retriever"],
        graph_client=components["graph_client"],
        conversation_memory=request.app.state.conversation_memory,
    )


# ── SSE streaming helper ───────────────────────────────────────

async def _stream_session(session: ResearchSession) -> AsyncGenerator[str, None]:
    """将 ResearchSession 以 SSE 事件流输出"""
    last = session.iterations[-1] if session.iterations else None
    if last:
        yield f"data: {json.dumps({'type': 'iteration', 'iteration': last.iteration, 'findings': last.findings}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'session', 'session': json.loads(session.model_dump_json())}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ── endpoints ───────────────────────────────────────────────────

@router.post("/start", summary="启动深度研究会话")
@rate_limit(requests_per_minute=10)
async def start_research(
    body: StartResearchRequest,
    stream: bool = Query(default=False),
    engine: ResearchEngine = Depends(_get_engine),
):
    """创建研究会话并执行首轮迭代"""
    try:
        validated_query = InputValidator.validate_query(body.query)
        validated_pid = InputValidator.validate_project_id(body.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await engine.start_research(validated_query, validated_pid)
    except Exception as e:
        logger.error(f"start_research failed: {e}")
        raise HTTPException(status_code=500, detail="Research failed due to internal error")

    if stream:
        return StreamingResponse(
            _stream_session(session), media_type="text/event-stream"
        )
    return session.model_dump()


@router.post("/{session_id}/continue", summary="继续下一轮研究迭代")
@rate_limit(requests_per_minute=20)
async def continue_research(
    session_id: str,
    body: ContinueResearchRequest,
    stream: bool = Query(default=False),
    engine: ResearchEngine = Depends(_get_engine),
):
    """执行下一轮研究迭代"""
    try:
        validated_pid = InputValidator.validate_project_id(body.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await engine.load_session(validated_pid, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Research session not found")

    try:
        session = await engine.continue_research(session)
    except Exception as e:
        logger.error(f"continue_research failed: {e}")
        raise HTTPException(status_code=500, detail="Research failed due to internal error")

    if stream:
        return StreamingResponse(
            _stream_session(session), media_type="text/event-stream"
        )
    return session.model_dump()


@router.get("/{session_id}", summary="获取研究会话状态")
async def get_session(
    session_id: str,
    project_id: str = Query(..., min_length=1, max_length=100),
    engine: ResearchEngine = Depends(_get_engine),
):
    """获取研究会话当前状态"""
    try:
        validated_pid = InputValidator.validate_project_id(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await engine.load_session(validated_pid, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Research session not found")

    return session.model_dump()


@router.post("/{session_id}/conclude", summary="强制结束研究并生成总结")
@rate_limit(requests_per_minute=10)
async def conclude_research(
    session_id: str,
    body: ContinueResearchRequest,
    stream: bool = Query(default=False),
    engine: ResearchEngine = Depends(_get_engine),
):
    """强制执行最终总结迭代"""
    try:
        validated_pid = InputValidator.validate_project_id(body.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await engine.load_session(validated_pid, session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Research session not found")

    try:
        session = await engine.conclude_research(session)
    except Exception as e:
        logger.error(f"conclude_research failed: {e}")
        raise HTTPException(status_code=500, detail="Research failed due to internal error")

    if stream:
        return StreamingResponse(
            _stream_session(session), media_type="text/event-stream"
        )
    return session.model_dump()
