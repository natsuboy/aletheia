"""聊天 API 端点"""
from typing import AsyncGenerator
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
try:
    from loguru import logger
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test env
    import logging
    import logging
    logger = logging.getLogger(__name__)
import json

from src.models.api import ChatRequest, ChatResponse
from src.backend.security import InputValidator
from src.backend.middleware.rate_limit import rate_limit
from src.rag.conversation import ConversationMemory, DialogTurn
from src.rag.context_resolver import ContextResolver

router = APIRouter(prefix="/api", tags=["chat"])

# 模块级单例
_context_resolver = ContextResolver()


def _build_evidence(contexts: list[dict], limit: int = 5) -> list[dict]:
    """将检索上下文转换为证据条目（稳定结构）"""
    evidence = []
    for i, ctx in enumerate(contexts[:limit]):
        meta = ctx.get("metadata", {}) if isinstance(ctx, dict) else {}
        evidence.append(
            {
                "id": f"ev_{i}",
                "content": ctx.get("text", ""),
                "source_type": ctx.get("source", "unknown"),
                "score": float(ctx.get("score", 0.0) or 0.0),
                "file_path": meta.get("path") or meta.get("file_path") or "",
                "symbol": meta.get("name") or "",
                "metadata": meta,
            }
        )
    return evidence


def _estimate_quality(answer: str, evidence: list[dict]) -> float:
    """启发式回答质量分（0-1），用于前端提示与内部监控"""
    if not answer.strip():
        return 0.0
    length_factor = min(len(answer.strip()) / 400.0, 1.0)
    evidence_factor = min(len(evidence) / 5.0, 1.0)
    avg_score = 0.0
    if evidence:
        avg_score = sum(float(e.get("score", 0.0) or 0.0) for e in evidence) / len(evidence)
        avg_score = min(max(avg_score, 0.0), 1.0)
    quality = 0.35 * length_factor + 0.35 * evidence_factor + 0.30 * avg_score
    return round(min(max(quality, 0.0), 1.0), 3)


def get_rag_components(request: Request) -> dict:
    """依赖注入: 从 app.state 获取 RAG 组件单例"""
    return request.app.state.rag_components


def get_conversation_memory(request: Request) -> ConversationMemory:
    """依赖注入: 从 app.state 获取会话记忆"""
    return request.app.state.conversation_memory


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="执行 RAG 聊天查询",
    description="支持多轮对话的 RAG 聊天。传入 session_id 启用会话记忆。",
    responses={
        200: {"description": "成功返回答案和来源"},
        400: {"description": "输入验证失败"},
        429: {"description": "超过速率限制"},
        500: {"description": "服务器内部错误"},
    },
)
@rate_limit(requests_per_minute=30)
async def chat(
    chat_request: ChatRequest,
    components: dict = Depends(get_rag_components),
    memory: ConversationMemory = Depends(get_conversation_memory),
):
    """聊天对话（支持多轮）"""
    try:
        validated_query = InputValidator.validate_query(chat_request.query)
        validated_project_id = InputValidator.validate_project_id(chat_request.project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

    if chat_request.stream:
        return StreamingResponse(
            _chat_stream(chat_request, components, memory, validated_query, validated_project_id),
            media_type="text/event-stream",
        )

    # 非流式响应
    try:
        retriever = components["retriever"]
        llm_client = components["llm_client"]
        prompt_builder = components["prompt_builder"]
        graph_client = components.get("graph_client")
        graph_project_id = InputValidator.to_graph_project_id(validated_project_id)

        # 加载会话历史
        history = []
        if chat_request.session_id:
            history = await memory.get_history(validated_project_id, chat_request.session_id)

        # 上下文解析（代词消解）
        enhanced_query = _context_resolver.resolve(validated_query, history)

        # 检索
        retrieval_result = await retriever.retrieve(
            query=enhanced_query, project_id=graph_project_id, k=10,
        )

        # 构建含历史的 messages
        messages = prompt_builder.build_messages_with_history(
            query=validated_query,
            retrieval_result=retrieval_result,
            history=history,
        )

        from src.rag.tools import GraphAgentTools
        tools_instance = GraphAgentTools(graph_client) if graph_client else None
        tool_defs = tools_instance.get_tool_definitions() if tools_instance else None

        # LLM 生成 (支持 Tool calls 循环)
        answer_or_msg = await llm_client.chat_completion(messages, tools=tool_defs)
        
        while hasattr(answer_or_msg, "tool_calls") and answer_or_msg.tool_calls:
            # 存入完整的带有 tool_calls 的 message (简化的结构以便返回给 LLM)
            msg_dump = answer_or_msg.model_dump()
            # 剔除无法序列化或不必要的字段
            clean_msg = {"role": "assistant", "tool_calls": msg_dump.get("tool_calls")}
            messages.append(clean_msg)
            
            for tool_call in answer_or_msg.tool_calls:
                tool_result = tools_instance.execute_tool({
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": tool_result
                })
            
            answer_or_msg = await llm_client.chat_completion(messages, tools=tool_defs)
            
        answer = answer_or_msg
        
        evidence = _build_evidence(retrieval_result.contexts, limit=5)
        retrieval_trace_id = str(retrieval_result.metadata.get("retrieval_trace_id") or uuid4())
        quality_score = _estimate_quality(answer, evidence)

        # 保存轮次
        if chat_request.session_id:
            entity_ids = [
                e.get("id", "") for e in retrieval_result.graph_context.entities
            ]
            await memory.add_turn(
                validated_project_id,
                chat_request.session_id,
                DialogTurn(
                    user_query=validated_query,
                    assistant_response=answer,
                    retrieved_entity_ids=entity_ids,
                ),
            )

        return ChatResponse(
            answer=answer,
            sources=retrieval_result.contexts[:5],
            evidence=evidence,
            intent=retrieval_result.intent.value,
            quality_score=quality_score,
            retrieval_trace_id=retrieval_trace_id,
            metadata=retrieval_result.metadata,
        )

    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail="Chat failed due to internal error")


async def _chat_stream(
    chat_request: ChatRequest,
    components: dict,
    memory: ConversationMemory,
    validated_query: str,
    validated_project_id: str,
) -> AsyncGenerator[str, None]:
    """流式聊天响应（支持多轮）"""
    try:
        retriever = components["retriever"]
        llm_client = components["llm_client"]
        prompt_builder = components["prompt_builder"]
        graph_client = components.get("graph_client")
        graph_project_id = InputValidator.to_graph_project_id(validated_project_id)

        # 加载会话历史
        history = []
        if chat_request.session_id:
            history = await memory.get_history(validated_project_id, chat_request.session_id)

        # 上下文解析
        enhanced_query = _context_resolver.resolve(validated_query, history)

        # 检索
        retrieval_result = await retriever.retrieve(
            query=enhanced_query, project_id=graph_project_id, k=10,
        )

        # 构建含历史的 messages
        messages = prompt_builder.build_messages_with_history(
            query=validated_query,
            retrieval_result=retrieval_result,
            history=history,
        )

        from src.rag.tools import GraphAgentTools
        tools_instance = GraphAgentTools(graph_client) if graph_client else None
        tool_defs = tools_instance.get_tool_definitions() if tools_instance else None

        # 流式生成与 Tool 循环
        full_answer = ""
        while True:
            stream_gen = llm_client.stream_completion(messages, tools=tool_defs)
            has_tool_call = False
            
            async for chunk in stream_gen:
                if isinstance(chunk, dict) and "tool_calls" in chunk:
                    has_tool_call = True
                    tool_calls = chunk["tool_calls"]
                    
                    messages.append({
                        "role": "assistant",
                        "tool_calls": tool_calls
                    })
                    
                    for tc in tool_calls:
                        tool_name = tc["function"]["name"]
                        yield f"data: {json.dumps({'type': 'reasoning', 'delta': f'\n> 正在执行图谱分析工具: `{tool_name}`...\n'})}\n\n"
                        
                        tool_result = tools_instance.execute_tool(tc)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["function"]["name"],
                            "content": tool_result
                        })
                    break  # 退出当前的 async for，进入外层 while 的新一轮 LLM 请求
                else:
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'content', 'delta': chunk})}\n\n"
                    
            if not has_tool_call:
                break

        # 保存轮次
        entity_ids = [
            e.get("id", "") for e in retrieval_result.graph_context.entities
        ]
        if chat_request.session_id and full_answer:
            await memory.add_turn(
                validated_project_id,
                chat_request.session_id,
                DialogTurn(
                    user_query=validated_query,
                    assistant_response=full_answer,
                    retrieved_entity_ids=entity_ids,
                ),
            )

        # 发送图谱高亮节点
        if entity_ids:
            yield f"data: {json.dumps({'type': 'nodes', 'node_ids': entity_ids})}\n\n"

        # 发送来源、证据与元信息
        evidence = _build_evidence(retrieval_result.contexts, limit=5)
        retrieval_trace_id = str(retrieval_result.metadata.get("retrieval_trace_id") or uuid4())
        quality_score = _estimate_quality(full_answer, evidence)
        yield f"data: {json.dumps({'type': 'sources', 'sources': retrieval_result.contexts[:5]})}\n\n"
        yield f"data: {json.dumps({'type': 'evidence', 'evidence': evidence})}\n\n"
        yield f"data: {json.dumps({'type': 'meta', 'quality_score': quality_score, 'retrieval_trace_id': retrieval_trace_id})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Stream chat failed: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': 'Internal server error'})}\n\n"
