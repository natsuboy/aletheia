"""文档生成 API 端点"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from pydantic import BaseModel

from src.backend.api.chat import get_rag_components
from src.backend.security import InputValidator


router = APIRouter(prefix="/api/doc", tags=["doc"])


class DocGenerateRequest(BaseModel):
    project_id: str
    symbol_id: str


class DocGenerateResponse(BaseModel):
    symbol_id: str
    documentation: str
    generated_at: str


@router.post("/generate", response_model=DocGenerateResponse)
async def generate_doc(
    request: DocGenerateRequest,
    components: dict = Depends(get_rag_components)
):
    try:
        validated_project_id = InputValidator.validate_project_id(request.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

    try:
        retriever = components["retriever"]
        llm_client = components["llm_client"]

        graph_project_id = InputValidator.to_graph_project_id(validated_project_id)
        retrieval_result = await retriever.retrieve(
            query=f"documentation for {request.symbol_id}",
            project_id=graph_project_id,
            k=5
        )

        context_text = "\n".join(
            ctx.get("text", "") for ctx in retrieval_result.contexts
        )

        messages = [
            {
                "role": "system",
                "content": "You are a code documentation assistant. Generate clear, concise documentation."
            },
            {
                "role": "user",
                "content": f"Generate documentation for symbol `{request.symbol_id}`.\n\nContext:\n{context_text}"
            }
        ]

        documentation = await llm_client.chat_completion(messages)

        return DocGenerateResponse(
            symbol_id=request.symbol_id,
            documentation=documentation,
            generated_at=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Doc generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Doc generation failed: {str(e)}")
