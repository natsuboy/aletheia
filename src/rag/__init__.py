"""RAG 引擎模块（惰性导入，避免可选依赖在导入期强耦合）。"""
from importlib import import_module
from typing import Any

__all__ = [
    "VectorStore",
    "EmbeddingGenerator",
    "IntentClassifier",
    "QueryIntent",
    "IntentClassification",
    "GraphRetriever",
    "GraphContext",
    "HybridRetriever",
    "RetrievalResult",
    "LLMClient",
    "LLMProvider",
    "PromptBuilder",
]

_EXPORT_MAP = {
    "VectorStore": ("src.rag.vector_store", "VectorStore"),
    "EmbeddingGenerator": ("src.rag.vector_store", "EmbeddingGenerator"),
    "IntentClassifier": ("src.rag.intent_classifier", "IntentClassifier"),
    "QueryIntent": ("src.rag.intent_classifier", "QueryIntent"),
    "IntentClassification": ("src.rag.intent_classifier", "IntentClassification"),
    "GraphRetriever": ("src.rag.graph_retriever", "GraphRetriever"),
    "GraphContext": ("src.rag.graph_retriever", "GraphContext"),
    "HybridRetriever": ("src.rag.retriever", "HybridRetriever"),
    "RetrievalResult": ("src.rag.retriever", "RetrievalResult"),
    "LLMClient": ("src.rag.llm_client", "LLMClient"),
    "LLMProvider": ("src.rag.llm_client", "LLMProvider"),
    "PromptBuilder": ("src.rag.prompt_builder", "PromptBuilder"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORT_MAP.get(name)
    if not target:
        raise AttributeError(f"module 'src.rag' has no attribute '{name}'")
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)
