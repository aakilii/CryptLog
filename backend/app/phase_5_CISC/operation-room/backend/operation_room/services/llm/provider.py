"""
LLM Provider Abstract Base Class.

Defines the interface that all LLM providers must implement.
Supports:
- Synchronous generation
- Streaming generation
- Structured JSON output
- Token counting
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Literal,
    Optional,
    Union,
)
from enum import Enum
import json


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class Message:
    """A chat message."""
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: str
    finish_reason: str = "stop"
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    provider: str = ""
    raw_response: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "model": self.model,
            "provider": self.provider,
        }


@dataclass
class StreamChunk:
    """A chunk from streaming generation."""
    content: str
    is_final: bool = False
    usage: Optional[Dict[str, int]] = None
    

@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    top_k: int = 40
    stop_sequences: Optional[List[str]] = None
    
    # For JSON mode
    json_schema: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }
        if self.stop_sequences:
            result["stop_sequences"] = self.stop_sequences
        if self.json_schema:
            result["json_schema"] = self.json_schema
        return result


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_config: Optional[GenerationConfig] = None,
    ):
        """
        Initialize the provider.
        
        Args:
            model: The model identifier (e.g., "gemini-pro", "qwen3:8b")
            api_key: API key for cloud providers
            base_url: Base URL for self-hosted providers
            default_config: Default generation configuration
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.default_config = default_config or GenerationConfig()
    
    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Return the provider type."""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> LLMResponse:
        """
        Generate a response from messages.
        
        Args:
            messages: List of chat messages
            config: Generation configuration (overrides default)
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Message],
        config: Optional[GenerationConfig] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Generate a streaming response.
        
        Args:
            messages: List of chat messages
            config: Generation configuration
            
        Yields:
            StreamChunk objects with content fragments
        """
        pass
    
    async def generate_json(
        self,
        messages: List[Message],
        schema: Dict[str, Any],
        config: Optional[GenerationConfig] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Args:
            messages: List of chat messages
            schema: JSON schema for the expected output
            config: Generation configuration
            
        Returns:
            Parsed JSON object matching the schema
        """
        # Create config with JSON schema
        json_config = config or GenerationConfig()
        json_config.json_schema = schema
        
        # Add JSON instruction to messages
        json_messages = messages.copy()
        json_instruction = Message(
            role="system",
            content=f"You must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}\n\nRespond ONLY with the JSON object, no additional text."
        )
        json_messages.insert(0, json_instruction)
        
        # Generate response
        response = await self.generate(json_messages, json_config)
        
        # Parse JSON from response
        content = response.content.strip()
        
        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nContent: {content}")
    
    async def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Default implementation uses a rough estimate.
        Subclasses should override with provider-specific counting.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 chars per token for English text
        return len(text) // 4
    
    def _merge_config(self, config: Optional[GenerationConfig]) -> GenerationConfig:
        """Merge provided config with defaults."""
        if config is None:
            return self.default_config
        
        return GenerationConfig(
            temperature=config.temperature or self.default_config.temperature,
            max_tokens=config.max_tokens or self.default_config.max_tokens,
            top_p=config.top_p or self.default_config.top_p,
            top_k=config.top_k or self.default_config.top_k,
            stop_sequences=config.stop_sequences or self.default_config.stop_sequences,
            json_schema=config.json_schema or self.default_config.json_schema,
        )
