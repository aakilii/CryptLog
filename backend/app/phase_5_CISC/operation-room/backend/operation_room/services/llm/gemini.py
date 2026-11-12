"""
Google Gemini LLM Provider.

Implements the LLMProvider interface for Google's Gemini API.
Supports streaming and structured JSON output.
"""

import os
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


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""
    
    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        api_key: Optional[str] = None,
        default_config: Optional[GenerationConfig] = None,
    ):
        """
        Initialize Gemini provider.
        
        Args:
            model: Gemini model name (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
            api_key: Google API key (or uses GEMINI_API_KEY env var)
            default_config: Default generation configuration
        """
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("GEMINI_API_KEY"),
            default_config=default_config,
        )
        self._client = None
        self._model_instance = None
    
    @property
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.GEMINI
    
    @property
    def is_available(self) -> bool:
        """Check if Gemini is available."""
        return bool(self.api_key)
    
    def _ensure_client(self):
        """Initialize the Gemini client if not already done."""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
                self._model_instance = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError(
                    "google-generativeai package is required. "
                    "Install with: pip install google-generativeai"
                )
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to Gemini format."""
        gemini_messages = []
        system_content = ""
        
        for msg in messages:
            if msg.role == "system":
                # Gemini handles system messages differently
                system_content += msg.content + "\n"
            elif msg.role == "user":
                content = msg.content
                if system_content and not gemini_messages:
                    # Prepend system content to first user message
                    content = f"{system_content}\n{content}"
                    system_content = ""
                gemini_messages.append({
                    "role": "user",
                    "parts": [content]
                })
            elif msg.role == "assistant":
                gemini_messages.append({
                    "role": "model",
                    "parts": [msg.content]
                })
        
        return gemini_messages
    
    def _get_generation_config(self, config: GenerationConfig) -> Dict[str, Any]:
        """Convert GenerationConfig to Gemini format."""
        return {
            "temperature": config.temperature,
            "max_output_tokens": config.max_tokens,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "stop_sequences": config.stop_sequences or [],
        }
    
    async def generate(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        """Generate a response using Gemini."""
        self._ensure_client()
        merged_config = self._merge_config(config)
        
        gemini_messages = self._convert_messages(messages)
        generation_config = self._get_generation_config(merged_config)
        
        try:
            # Use chat for multi-turn, generate_content for single turn
            if len(gemini_messages) == 1:
                response = await self._model_instance.generate_content_async(
                    gemini_messages[0]["parts"][0],
                    generation_config=generation_config,
                )
            else:
                chat = self._model_instance.start_chat(history=gemini_messages[:-1])
                response = await chat.send_message_async(
                    gemini_messages[-1]["parts"][0],
                    generation_config=generation_config,
                )
            
            # Extract usage information
            usage = {}
            if hasattr(response, "usage_metadata"):
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                }
            
            return LLMResponse(
                content=response.text,
                finish_reason=response.candidates[0].finish_reason.name if response.candidates else "stop",
                usage=usage,
                model=self.model,
                provider="gemini",
                raw_response=response,
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {e}")
    
    async def generate_stream(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate streaming response using Gemini."""
        self._ensure_client()
        merged_config = self._merge_config(config)
        
        gemini_messages = self._convert_messages(messages)
        generation_config = self._get_generation_config(merged_config)
        
        try:
            if len(gemini_messages) == 1:
                response = await self._model_instance.generate_content_async(
                    gemini_messages[0]["parts"][0],
                    generation_config=generation_config,
                    stream=True,
                )
            else:
                chat = self._model_instance.start_chat(history=gemini_messages[:-1])
                response = await chat.send_message_async(
                    gemini_messages[-1]["parts"][0],
                    generation_config=generation_config,
                    stream=True,
                )
            
            async for chunk in response:
                if chunk.text:
                    yield StreamChunk(
                        content=chunk.text,
                        is_final=False,
                    )
            
            # Final chunk with usage info
            usage = None
            if hasattr(response, "usage_metadata"):
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count,
                }
            
            yield StreamChunk(
                content="",
                is_final=True,
                usage=usage,
            )
            
        except Exception as e:
            raise RuntimeError(f"Gemini streaming failed: {e}")
    
    async def count_tokens(self, text: str) -> int:
        """Count tokens using Gemini's tokenizer."""
        self._ensure_client()
        try:
            result = await self._model_instance.count_tokens_async(text)
            return result.total_tokens
        except Exception:
            # Fall back to estimate
            return len(text) // 4
