"""
LLM Gateway - unified interface for multiple LLM providers.
For MVP, uses NVIDIA NIM, OpenCode.ai, and HuggingFace (all free).
"""
import logging
from typing import AsyncIterator, Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

import httpx
import orjson

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    NVIDIA = "nvidia"
    OPENCODE = "opencode"
    HUGGINGFACE = "huggingface"


@dataclass
class LLMMessage:
    """LLM message - supports system/user/assistant/tool roles."""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    name: Optional[str] = None

    def to_api_dict(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible API dict."""
        msg: Dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }

        # Add tool_calls for assistant messages that called tools
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls

        # For tool response messages, include tool_call_id and name
        if self.role == "tool":
            if self.tool_call_id:
                msg["tool_call_id"] = self.tool_call_id
            if self.tool_name or self.name:
                msg["name"] = self.tool_name or self.name

        return msg


@dataclass
class LLMChunk:
    type: str  # text, tool_call, usage, reasoning, done, error
    content: str = ""
    tool_call: Optional[Dict] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    finish_reason: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Available models per provider
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NVIDIA_MODELS = {
    "llama-3.1-70b": "meta/llama-3.1-70b-instruct",
    "llama-3.3-70b": "meta/llama-3.3-70b-instruct",
    "nemotron-70b": "nvidia/llama-3.1-nemotron-70b-instruct",
    "nemotron-51b": "nvidia/llama-3.1-nemotron-51b-instruct",
    "mixtral-8x7b": "mistralai/mixtral-8x7b-instruct-v0.1",
    "mistral-large": "mistralai/mistral-large-2-instruct",
    "gemma-2-9b": "google/gemma-2-9b-it",
    "qwen2.5-7b": "qwen/qwen2.5-7b-instruct",
    "phi-3.5-mini": "microsoft/phi-3.5-mini-instruct",
}

OPENCODE_MODELS = {
    "mimo-v2.5-free": "mimo-v2.5-free",
    "north-mini-code-free": "north-mini-code-free",
    "nemotron-3-ultra-free": "nemotron-3-ultra-free",
    "deepseek-v4-flash-free": "deepseek-v4-flash-free",
}


def get_all_available_models() -> Dict[str, List[Dict]]:
    """Get all available models across providers."""
    return {
        "nvidia": [
            {"id": mid, "name": mid, "provider": "nvidia", "free": True}
            for mid in NVIDIA_MODELS.values()
        ],
        "opencode": [
            {"id": mid, "name": mid, "provider": "opencode", "free": True}
            for mid in OPENCODE_MODELS.values()
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM Gateway
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class LLMGateway:
    """Unified LLM Gateway for streaming completions."""

    def __init__(self):
        self.timeout = httpx.Timeout(120.0, connect=10.0)

    async def chat_stream(
        self,
        messages: List[LLMMessage],
        model: str,
        provider: str = "nvidia",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
    ) -> AsyncIterator[LLMChunk]:
        """Stream a chat completion from the specified provider."""
        if provider == "nvidia":
            async for chunk in self._stream_openai_compat(
                messages, model, temperature, max_tokens, tools,
                base_url=settings.NVIDIA_BASE_URL,
                api_key=settings.NVIDIA_API_KEY,
            ):
                yield chunk
        elif provider == "opencode":
            async for chunk in self._stream_openai_compat(
                messages, model, temperature, max_tokens, tools,
                base_url=settings.OPENCODE_BASE_URL,
                api_key=settings.OPENCODE_API_KEY,
            ):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _stream_openai_compat(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict]],
        base_url: str,
        api_key: str,
    ) -> AsyncIterator[LLMChunk]:
        """Stream from any OpenAI-compatible API (NVIDIA, OpenCode, etc)."""
        # Convert messages using the new to_api_dict method
        api_messages = [m.to_api_dict() for m in messages]

        payload: Dict[str, Any] = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        error_text = body.decode("utf-8", errors="replace")[:500]
                        logger.error(f"LLM API error {response.status_code}: {error_text}")
                        yield LLMChunk(
                            type="error",
                            content=f"LLM API error {response.status_code}: {error_text[:200]}",
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data = line[6:]
                        if data == "[DONE]":
                            yield LLMChunk(type="done")
                            return

                        try:
                            chunk = orjson.loads(data)
                            choices = chunk.get("choices", [])
                            if not choices:
                                # Maybe usage-only chunk
                                if chunk.get("usage"):
                                    usage = chunk["usage"]
                                    yield LLMChunk(
                                        type="usage",
                                        input_tokens=usage.get("prompt_tokens", 0),
                                        output_tokens=usage.get("completion_tokens", 0),
                                        cost=0.0,
                                    )
                                continue

                            choice = choices[0]
                            delta = choice.get("delta", {})

                            if delta.get("content"):
                                yield LLMChunk(type="text", content=delta["content"])

                            if delta.get("tool_calls"):
                                for tc in delta["tool_calls"]:
                                    # Accumulate tool calls (delta may be partial)
                                    yield LLMChunk(type="tool_call", tool_call=tc)

                            if choice.get("finish_reason"):
                                yield LLMChunk(
                                    type="done",
                                    finish_reason=choice["finish_reason"],
                                )

                            if chunk.get("usage"):
                                usage = chunk["usage"]
                                yield LLMChunk(
                                    type="usage",
                                    input_tokens=usage.get("prompt_tokens", 0),
                                    output_tokens=usage.get("completion_tokens", 0),
                                    cost=0.0,
                                )
                        except Exception as e:
                            logger.warning(f"Failed to parse LLM chunk: {e}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API HTTP error: {e}")
            yield LLMChunk(type="error", content=f"LLM HTTP error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"LLM stream error: {e}", exc_info=True)
            yield LLMChunk(type="error", content=str(e))

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings using HuggingFace."""
        if not settings.HUGGINGFACE_TOKEN:
            raise ValueError("HuggingFace token not configured")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"https://api-inference.huggingface.co/pipeline/feature-extraction/{settings.HUGGINGFACE_EMBEDDING_MODEL}",
                    headers={"Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}"},
                    json={"inputs": text, "options": {"wait_for_model": True}},
                )
                response.raise_for_status()
                result = response.json()

                # BGE-M3 returns a list of vectors; average them
                if isinstance(result, list) and result and isinstance(result[0], list):
                    import numpy as np
                    arr = np.array(result)
                    return arr.mean(axis=0).tolist()
                return result
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise

    async def chat_complete(
        self,
        messages: List[LLMMessage],
        model: str,
        provider: str = "nvidia",
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Non-streaming chat completion (for memory consolidation, dreams, etc)."""
        if provider == "nvidia":
            base_url = settings.NVIDIA_BASE_URL
            api_key = settings.NVIDIA_API_KEY
        elif provider == "opencode":
            base_url = settings.OPENCODE_BASE_URL
            api_key = settings.OPENCODE_API_KEY
        else:
            raise ValueError(f"Unknown provider: {provider}")

        api_messages = [m.to_api_dict() for m in messages]

        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
        except Exception as e:
            logger.error(f"chat_complete error: {e}")
            raise

    def _estimate_cost_nvidia(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost (NVIDIA free tier = $0)."""
        return 0.0


# Singleton
llm_gateway = LLMGateway()
