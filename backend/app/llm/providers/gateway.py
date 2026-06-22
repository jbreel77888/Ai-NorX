"""
LLM Gateway - unified interface for multiple LLM providers.
For MVP, uses NVIDIA NIM, OpenCode.ai, and HuggingFace (all free).
"""
import logging
from typing import AsyncIterator, Optional, List, Dict, Any
from dataclasses import dataclass
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
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMChunk:
    type: str  # text, tool_call, usage, reasoning, done
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
            async for chunk in self._stream_nvidia(messages, model, temperature, max_tokens, tools):
                yield chunk
        elif provider == "opencode":
            async for chunk in self._stream_opencode(messages, model, temperature, max_tokens, tools):
                yield chunk
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _stream_nvidia(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict]],
    ) -> AsyncIterator[LLMChunk]:
        """Stream from NVIDIA NIM API."""
        # Convert messages
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        payload = {
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
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.NVIDIA_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data = line[6:]
                        if data == "[DONE]":
                            yield LLMChunk(type="done")
                            return

                        try:
                            chunk = orjson.loads(data)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})

                            if delta.get("content"):
                                yield LLMChunk(type="text", content=delta["content"])

                            if delta.get("tool_calls"):
                                yield LLMChunk(type="tool_call", tool_call=delta["tool_calls"][0])

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
                                    cost=self._estimate_cost_nvidia(
                                        usage.get("prompt_tokens", 0),
                                        usage.get("completion_tokens", 0),
                                        model,
                                    ),
                                )
                        except Exception as e:
                            logger.warning(f"Failed to parse NVIDIA chunk: {e}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"NVIDIA API error: {e.response.text}")
            yield LLMChunk(type="error", content=f"LLM error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"NVIDIA stream error: {e}")
            yield LLMChunk(type="error", content=str(e))

    async def _stream_opencode(
        self,
        messages: List[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: Optional[List[Dict]],
    ) -> AsyncIterator[LLMChunk]:
        """Stream from OpenCode.ai API."""
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {settings.OPENCODE_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{settings.OPENCODE_BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data = line[6:]
                        if data == "[DONE]":
                            yield LLMChunk(type="done")
                            return

                        try:
                            chunk = orjson.loads(data)
                            choice = chunk.get("choices", [{}])[0]
                            delta = choice.get("delta", {})

                            if delta.get("content"):
                                yield LLMChunk(type="text", content=delta["content"])

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
                                    cost=0.0,  # Free
                                )
                        except Exception as e:
                            logger.warning(f"Failed to parse OpenCode chunk: {e}")
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenCode API error: {e.response.text}")
            yield LLMChunk(type="error", content=f"LLM error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"OpenCode stream error: {e}")
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
                    # Average the token vectors
                    import numpy as np
                    arr = np.array(result)
                    return arr.mean(axis=0).tolist()
                return result
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise

    def _estimate_cost_nvidia(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost (NVIDIA free tier = $0)."""
        return 0.0  # Free tier


# Singleton
llm_gateway = LLMGateway()
