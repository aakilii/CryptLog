"""
Unified LLM Service with Provider Switching and Multi-Key Support.

Manages multiple LLM providers and allows switching between them.
Provides a consistent interface for all LLM operations.
Supports automatic API key rotation for rate limit handling.
"""

import os
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Optional,
    Type,
)
from functools import lru_cache
import logging

from .provider import (
    LLMProvider,
    LLMResponse,
    Message,
    GenerationConfig,
    ProviderType,
    StreamChunk,
)
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .multi_key import get_multi_key_provider, MultiKeyProvider


logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM Service with provider switching.
    
    Supports:
    - Multiple providers (Gemini, Ollama)
    - Runtime provider switching
    - Fallback behavior
    - Consistent interface
    """
    
    # Default models for each provider
    DEFAULT_MODELS = {
        ProviderType.GEMINI: "gemini-1.5-flash",
        ProviderType.OLLAMA: "gemma2:2b",
    }
    
    # Provider classes
    PROVIDER_CLASSES: Dict[ProviderType, Type[LLMProvider]] = {
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.OLLAMA: OllamaProvider,
    }
    
    def __init__(
        self,
        default_provider: ProviderType = ProviderType.GEMINI,
        gemini_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        fallback_enabled: bool = True,
        use_multi_key: bool = True,
    ):
        """
        Initialize the LLM service.
        
        Args:
            default_provider: Default provider to use
            gemini_api_key: API key for Gemini (or use multi-key)
            ollama_base_url: Base URL for Ollama server
            fallback_enabled: Whether to fallback to other providers on failure
            use_multi_key: Use multi-key rotation for Gemini
        """
        self._default_provider = default_provider
        self._current_provider = default_provider
        self._fallback_enabled = fallback_enabled
        self._use_multi_key = use_multi_key
        
        # Multi-key provider for rotation
        self._multi_key_provider = get_multi_key_provider() if use_multi_key else None
        
        # Store configuration
        self._config = {
            "gemini_api_key": gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPROOM_GEMINI_API_KEY"),
            "ollama_base_url": ollama_base_url or os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OPROOM_OLLAMA_URL", "http://localhost:11434"),
        }
        
        # Initialize providers lazily
        self._providers: Dict[ProviderType, LLMProvider] = {}
    
    async def _get_gemini_key(self) -> Optional[str]:
        """Get the next Gemini API key (with rotation if multi-key enabled)."""
        if self._use_multi_key and self._multi_key_provider:
            if self._multi_key_provider.has_keys("gemini"):
                return await self._multi_key_provider.get_next_key("gemini")
        return self._config.get("gemini_api_key")
    
    def _get_provider(self, provider_type: ProviderType) -> LLMProvider:
        """Get or create a provider instance."""
        if provider_type not in self._providers:
            if provider_type == ProviderType.GEMINI:
                # For multi-key, we'll rotate keys on each request
                api_key = self._config.get("gemini_api_key")
                if self._use_multi_key and self._multi_key_provider:
                    # Get first available key synchronously for initialization
                    available = self._multi_key_provider.get_available_keys("gemini")
                    if available:
                        api_key = available[0].key
                
                self._providers[provider_type] = GeminiProvider(
                    model=self.DEFAULT_MODELS[ProviderType.GEMINI],
                    api_key=api_key,
                )
            elif provider_type == ProviderType.OLLAMA:
                self._providers[provider_type] = OllamaProvider(
                    model=self.DEFAULT_MODELS[ProviderType.OLLAMA],
                    base_url=self._config["ollama_base_url"],
                )
            else:
                raise ValueError(f"Unknown provider type: {provider_type}")
        
        return self._providers[provider_type]
    
    @property
    def current_provider(self) -> ProviderType:
        """Get the current active provider."""
        return self._current_provider
    
    @property
    def provider(self) -> LLMProvider:
        """Get the current provider instance."""
        return self._get_provider(self._current_provider)
    
    def switch_provider(
        self,
        provider_type: ProviderType,
        model: Optional[str] = None,
    ) -> None:
        """
        Switch to a different provider.
        
        Args:
            provider_type: Provider to switch to
            model: Optional model override
        """
        self._current_provider = provider_type
        
        # Update model if specified
        if model:
            provider = self._get_provider(provider_type)
            provider.model = model
        
        logger.info(f"Switched LLM provider to: {provider_type.value}")
    
    def set_model(self, model: str) -> None:
        """Set the model for the current provider."""
        self.provider.model = model
        logger.info(f"Set model to: {model}")
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List all available providers and their status."""
        providers = []
        for provider_type in ProviderType:
            try:
                provider = self._get_provider(provider_type)
                providers.append({
                    "type": provider_type.value,
                    "model": provider.model,
                    "is_available": provider.is_available,
                    "is_current": provider_type == self._current_provider,
                })
            except Exception as e:
                providers.append({
                    "type": provider_type.value,
                    "model": self.DEFAULT_MODELS.get(provider_type, "unknown"),
                    "is_available": False,
                    "is_current": provider_type == self._current_provider,
                    "error": str(e),
                })
        return providers
    
    async def generate(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
        provider_type: Optional[ProviderType] = None,
    ) -> LLMResponse:
        """
        Generate a response.
        
        Args:
            messages: Chat messages
            config: Generation configuration
            provider_type: Override current provider
            
        Returns:
            LLMResponse with generated content
        """
        target_provider = provider_type or self._current_provider
        provider = self._get_provider(target_provider)
        
        try:
            return await provider.generate(messages, config)
        except Exception as e:
            if self._fallback_enabled and target_provider != self._default_provider:
                logger.warning(f"Provider {target_provider} failed, falling back: {e}")
                return await self._get_provider(self._default_provider).generate(messages, config)
            raise
    
    async def generate_stream(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
        provider_type: Optional[ProviderType] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Generate a streaming response.
        
        Args:
            messages: Chat messages
            config: Generation configuration
            provider_type: Override current provider
            
        Yields:
            StreamChunk objects
        """
        target_provider = provider_type or self._current_provider
        provider = self._get_provider(target_provider)
        
        try:
            async for chunk in provider.generate_stream(messages, config):
                yield chunk
        except Exception as e:
            if self._fallback_enabled and target_provider != self._default_provider:
                logger.warning(f"Provider {target_provider} streaming failed, falling back: {e}")
                async for chunk in self._get_provider(self._default_provider).generate_stream(messages, config):
                    yield chunk
            else:
                raise
    
    async def generate_json(
        self,
        messages: List[Message],
        schema: Dict[str, Any],
        config: Optional[GenerationConfig] = None,
        provider_type: Optional[ProviderType] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Args:
            messages: Chat messages
            schema: JSON schema for output
            config: Generation configuration
            provider_type: Override current provider
            
        Returns:
            Parsed JSON object
        """
        target_provider = provider_type or self._current_provider
        provider = self._get_provider(target_provider)
        
        try:
            return await provider.generate_json(messages, schema, config)
        except Exception as e:
            if self._fallback_enabled and target_provider != self._default_provider:
                logger.warning(f"Provider {target_provider} JSON failed, falling back: {e}")
                return await self._get_provider(self._default_provider).generate_json(messages, schema, config)
            raise
    
    async def count_tokens(
        self,
        text: str,
        provider_type: Optional[ProviderType] = None,
    ) -> int:
        """Count tokens using the specified provider."""
        target_provider = provider_type or self._current_provider
        provider = self._get_provider(target_provider)
        return await provider.count_tokens(text)
    
    async def close(self):
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, "close"):
                await provider.close()
    
    # Convenience methods for common operations
    
    async def chat(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> str:
        """
        Simple chat interface.
        
        Args:
            user_message: User's message
            system_message: Optional system prompt
            config: Generation configuration
            
        Returns:
            Assistant's response text
        """
        messages = []
        if system_message:
            messages.append(Message(role="system", content=system_message))
        messages.append(Message(role="user", content=user_message))
        
        response = await self.generate(messages, config)
        return response.content
    
    async def chat_stream(
        self,
        user_message: str,
        system_message: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[str]:
        """
        Simple streaming chat interface.
        
        Args:
            user_message: User's message
            system_message: Optional system prompt
            config: Generation configuration
            
        Yields:
            Response text chunks
        """
        messages = []
        if system_message:
            messages.append(Message(role="system", content=system_message))
        messages.append(Message(role="user", content=user_message))
        
        async for chunk in self.generate_stream(messages, config):
            if chunk.content:
                yield chunk.content


# Global singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the global LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def configure_llm_service(
    default_provider: ProviderType = ProviderType.GEMINI,
    gemini_api_key: Optional[str] = None,
    ollama_base_url: Optional[str] = None,
    fallback_enabled: bool = True,
) -> LLMService:
    """Configure and return the global LLM service."""
    global _llm_service
    _llm_service = LLMService(
        default_provider=default_provider,
        gemini_api_key=gemini_api_key,
        ollama_base_url=ollama_base_url,
        fallback_enabled=fallback_enabled,
    )
    return _llm_service
