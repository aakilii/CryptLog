"""
Ollama LLM Provider.

Implements the LLMProvider interface for Ollama (local LLMs).
Supports streaming and works with models like Qwen3.
"""

import os
import json
import aiohttp
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
)

from .provider import (
    LLMProvider,
    LLMResponse,
    Message,
    GenerationConfig,
    ProviderType,
    StreamChunk,
)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""
    
    def __init__(
        self,
        model: str = "gemma2:2b",
        base_url: Optional[str] = None,
        default_config: Optional[GenerationConfig] = None,
    ):
        """
        Initialize Ollama provider.
        
        Args:
            model: Ollama model name (e.g., "gemma2:2b", "llama3:8b")
            base_url: Ollama server URL (defaults to http://localhost:11434)
            default_config: Default generation configuration
        """
        super().__init__(
            model=model,
            base_url=base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            default_config=default_config,
        )
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.OLLAMA
    
    @property
    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        # Will check connectivity on first use
        return bool(self.base_url)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _check_model_available(self) -> bool:
        """Check if the model is available in Ollama."""
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return self.model in models or self.model.split(":")[0] in [m.split(":")[0] for m in models]
        except Exception:
            pass
        return False
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert messages to Ollama format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]
    
    def _get_options(self, config: GenerationConfig) -> Dict[str, Any]:
        """Convert GenerationConfig to Ollama options."""
        options = {
            "temperature": config.temperature,
            "num_predict": config.max_tokens,
            "top_p": config.top_p,
            "top_k": config.top_k,
        }
        if config.stop_sequences:
            options["stop"] = config.stop_sequences
        return options
    
    async def generate(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        """Generate a response using Ollama."""
        merged_config = self._merge_config(config)
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "options": self._get_options(merged_config),
            "stream": False,
        }
        
        # Handle JSON mode for Qwen3
        if merged_config.json_schema:
            payload["format"] = "json"
        
        try:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Ollama request failed: {error_text}")
                
                data = await response.json()
                
                # Extract response content
                content = data.get("message", {}).get("content", "")
                
                # Extract usage info
                usage = {}
                if "prompt_eval_count" in data:
                    usage["prompt_tokens"] = data["prompt_eval_count"]
                if "eval_count" in data:
                    usage["completion_tokens"] = data["eval_count"]
                if usage:
                    usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                
                return LLMResponse(
                    content=content,
                    finish_reason="stop" if data.get("done", True) else "length",
                    usage=usage,
                    model=self.model,
                    provider="ollama",
                    raw_response=data,
                )
                
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Ollama connection failed: {e}")
    
    async def generate_stream(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming response using Ollama."""
        merged_config = self._merge_config(config)
        session = await self._get_session()
        
        payload = {
            "model": self.model,
            "messages": self._convert_messages(messages),
            "options": self._get_options(merged_config),
            "stream": True,
        }
        
        try:
            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"Ollama request failed: {error_text}")
                
                usage = {}
                async for line in response.content:
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    
                    # Extract content from message
                    content = data.get("message", {}).get("content", "")
                    is_done = data.get("done", False)
                    
                    if content:
                        yield StreamChunk(
                            content=content,
                            is_final=False,
                        )
                    
                    if is_done:
                        # Extract final usage info
                        if "prompt_eval_count" in data:
                            usage["prompt_tokens"] = data["prompt_eval_count"]
                        if "eval_count" in data:
                            usage["completion_tokens"] = data["eval_count"]
                        if usage:
                            usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                        
                        yield StreamChunk(
                            content="",
                            is_final=True,
                            usage=usage,
                        )
                        break
                        
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Ollama streaming failed: {e}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count for Ollama models.
        
        Ollama doesn't have a direct token counting API,
        so we use an estimate based on model type.
        """
        # Qwen3 uses similar tokenization to GPT-style models
        # Rough estimate: ~3.5-4 chars per token for English
        return len(text) // 4
    
    async def pull_model(self) -> bool:
        """
        Pull the model if not available.
        
        Returns:
            True if model was pulled or already available
        """
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model},
            ) as response:
                if response.status == 200:
                    # Stream the pull progress
                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode("utf-8"))
                                if data.get("status") == "success":
                                    return True
                            except json.JSONDecodeError:
                                continue
        except Exception:
            pass
        return False
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
