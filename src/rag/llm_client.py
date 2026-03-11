"""LLM 客户端 (支持多供应商)"""
from enum import Enum
from typing import List, Dict, AsyncGenerator, Any, Optional
from openai import AsyncOpenAI
import anthropic
from loguru import logger

from src.backend.config import get_settings
from src.utils.retry import with_async_retry, RetryConfig

_llm_retry = with_async_retry(RetryConfig(
    max_retries=3, base_delay=1.0, backoff_factor=2.0,
    retryable_exceptions=(Exception,),
))


class LLMProvider(str, Enum):
    """LLM 供应商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMClient:
    """LLM 客户端"""

    def __init__(
        self,
        provider: LLMProvider = LLMProvider.OPENAI,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        settings = get_settings()

        if provider == LLMProvider.OPENAI:
            client_kwargs = {"api_key": settings.openai_api_key}
            if settings.openai_base_url:
                client_kwargs["base_url"] = settings.openai_base_url
            self.client = AsyncOpenAI(**client_kwargs)
        elif provider == LLMProvider.ANTHROPIC:
            self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        elif provider == LLMProvider.GOOGLE:
            import google.generativeai as genai
            genai.configure(api_key=settings.google_api_key)
            self.model_client = genai.GenerativeModel(model)
        else:
            raise NotImplementedError(f"Provider {provider} not implemented yet")

        logger.info(f"Initialized LLM client: {provider.value}/{model}")

    @staticmethod
    def _split_system(messages: List[Dict[str, str]]):
        """提取 system 消息，返回 (system_text, non_system_messages)"""
        system_parts = []
        api_messages = []
        for m in messages:
            if m.get("role") == "system":
                system_parts.append(m["content"])
            else:
                api_messages.append(m)
        return "\n\n".join(system_parts) if system_parts else None, api_messages

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)

    @_llm_retry
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        **kwargs
    ) -> Any:  # Returns either a str or a Message with tool_calls
        if self.provider == LLMProvider.ANTHROPIC:
            system_text, api_messages = self._split_system(messages)
            create_kwargs = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "messages": api_messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }
            if tools:
                # Anthropic format is slightly different, but assuming standard format is provided or skipped for now
                pass 
            if system_text:
                create_kwargs["system"] = system_text
            response = await self.client.messages.create(**create_kwargs)
            # returning full response for tool call support
            return response
        elif self.provider == LLMProvider.GOOGLE:
            response = await self.model_client.generate_content_async(
                self._messages_to_prompt(messages)
            )
            # basic support, no tools yet
            return response.text
        else:
            api_kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": False
            }
            if tools:
                api_kwargs["tools"] = tools
            if tool_choice:
                api_kwargs["tool_choice"] = tool_choice
                
            if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                api_kwargs["max_completion_tokens"] = kwargs.get("max_tokens", self.max_tokens)
            else:
                api_kwargs["max_tokens"] = kwargs.get("max_tokens", self.max_tokens)
                api_kwargs["temperature"] = kwargs.get("temperature", self.temperature)
            response = await self.client.chat.completions.create(**api_kwargs)
            message = response.choices[0].message
            
            if hasattr(message, "tool_calls") and message.tool_calls:
                return message  # Return message object with tool_calls
            return message.content

    async def stream_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        **kwargs
    ) -> AsyncGenerator[Any, None]:  # Yields str or Dict with tool_calls
        try:
            if self.provider == LLMProvider.ANTHROPIC:
                system_text, api_messages = self._split_system(messages)
                stream_kwargs = {
                    "model": self.model,
                    "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                    "messages": api_messages,
                    "temperature": kwargs.get("temperature", self.temperature),
                }
                if system_text:
                    stream_kwargs["system"] = system_text
                async with self.client.messages.stream(**stream_kwargs) as stream:
                    async for text in stream.text_stream:
                        yield text
            elif self.provider == LLMProvider.GOOGLE:
                response = await self.model_client.generate_content_async(
                    self._messages_to_prompt(messages), stream=True
                )
                async for chunk in response:
                    yield chunk.text
            else:
                api_kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "stream": True
                }
                if tools:
                    api_kwargs["tools"] = tools
                if tool_choice:
                    api_kwargs["tool_choice"] = tool_choice
                    
                if "gpt-5" in self.model.lower() or "o1" in self.model.lower():
                    api_kwargs["max_completion_tokens"] = kwargs.get("max_tokens", self.max_tokens)
                else:
                    api_kwargs["max_tokens"] = kwargs.get("max_tokens", self.max_tokens)
                    api_kwargs["temperature"] = kwargs.get("temperature", self.temperature)
                
                stream = await self.client.chat.completions.create(**api_kwargs)
                
                tool_calls_accumulator = {}
                
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    
                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_accumulator:
                                tool_calls_accumulator[idx] = {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.function.name or "", "arguments": ""}
                                }
                            if tc.function.arguments:
                                tool_calls_accumulator[idx]["function"]["arguments"] += tc.function.arguments
                    elif delta.content:
                        yield delta.content

                if tool_calls_accumulator:
                    # Sort by index and return as a dict to distinguish from text yields
                    sorted_calls = [tool_calls_accumulator[i] for i in sorted(tool_calls_accumulator.keys())]
                    yield {"tool_calls": sorted_calls}

            logger.info("LLM stream completion finished")

        except Exception as e:
            logger.error(f"LLM stream completion failed: {e}")
            raise


class FallbackLLMClient:
    """带自动降级的 LLM 客户端，依次尝试多个 provider"""

    def __init__(self, clients: List["LLMClient"]):
        if not clients:
            raise ValueError("At least one LLM client required")
        self.clients = clients

    async def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> str:
        last_err = None
        for client in self.clients:
            try:
                return await client.chat_completion(messages, **kwargs)
            except Exception as e:
                logger.warning(f"Provider {client.provider.value} failed: {e}, trying next")
                last_err = e
        raise last_err

    async def stream_completion(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        last_err = None
        for client in self.clients:
            try:
                async for chunk in client.stream_completion(messages, **kwargs):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Stream provider {client.provider.value} failed: {e}, trying next")
                last_err = e
        raise last_err
