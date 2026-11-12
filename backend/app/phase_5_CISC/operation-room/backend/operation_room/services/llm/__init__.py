"""
LLM Provider Module for NFLIP Deep Research Investigation Assistant.

Supports:
- Google Gemini API
- Ollama (local LLMs like Qwen3)

With provider switching capability.
"""

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
from .service import LLMService, get_llm_service, configure_llm_service

__all__ = [
    # Base classes
    "LLMProvider",
    "LLMResponse",
    "Message",
    "GenerationConfig",
    "ProviderType",
    "StreamChunk",
    # Providers
    "GeminiProvider", 
    "OllamaProvider",
    # Service
    "LLMService",
    "get_llm_service",
    "configure_llm_service",
]


def init_from_settings():
    """Initialize LLM service from app settings."""
    from operation_room.config import settings
    
    # Determine provider type from settings
    if settings.LLM_PROVIDER.lower() == "gemini":
        provider = ProviderType.GEMINI
    else:
        provider = ProviderType.OLLAMA
    
    # Configure the service
    service = configure_llm_service(
        default_provider=provider,
        gemini_api_key=settings.GEMINI_API_KEY,
        ollama_base_url=settings.OLLAMA_URL,
        fallback_enabled=True,
    )
    
    # Set the model
    service.set_model(settings.LLM_MODEL)
    
    return service
