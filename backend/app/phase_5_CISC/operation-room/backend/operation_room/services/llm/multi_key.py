"""
Multi-Key LLM Provider with Rotation.

Supports multiple API keys with automatic rotation for:
- Load balancing across keys
- Automatic failover on rate limits
- Per-key usage tracking
- Support for multiple providers (Gemini, OpenAI, Ollama)
"""

import os
import time
import random
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class KeyStatus(Enum):
    """Status of an API key."""
    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"
    ERROR = "error"


@dataclass
class APIKeyInfo:
    """Information about an API key."""
    key: str
    provider: str
    status: KeyStatus = KeyStatus.ACTIVE
    last_used: float = 0.0
    use_count: int = 0
    error_count: int = 0
    rate_limit_until: float = 0.0
    daily_requests: int = 0
    daily_reset: float = 0.0
    
    @property
    def is_available(self) -> bool:
        """Check if key is available for use."""
        now = time.time()
        
        # Reset daily counter at midnight
        if now > self.daily_reset:
            self.daily_requests = 0
            self.daily_reset = now + 86400  # Next day
        
        # Check if still rate limited
        if self.status == KeyStatus.RATE_LIMITED and now > self.rate_limit_until:
            self.status = KeyStatus.ACTIVE
        
        return self.status == KeyStatus.ACTIVE
    
    def mark_used(self) -> None:
        """Mark key as used."""
        self.last_used = time.time()
        self.use_count += 1
        self.daily_requests += 1
    
    def mark_rate_limited(self, retry_after: float = 60.0) -> None:
        """Mark key as rate limited."""
        self.status = KeyStatus.RATE_LIMITED
        self.rate_limit_until = time.time() + retry_after
        logger.warning(f"API key ending in ...{self.key[-4:]} rate limited for {retry_after}s")
    
    def mark_error(self) -> None:
        """Mark key with error."""
        self.error_count += 1
        if self.error_count >= 3:
            self.status = KeyStatus.ERROR
            logger.error(f"API key ending in ...{self.key[-4:]} disabled due to repeated errors")


class MultiKeyProvider:
    """
    Multi-key provider with automatic rotation.
    
    Features:
    - Round-robin key selection
    - Automatic failover on rate limits
    - Per-key usage tracking
    - Support for multiple providers
    """
    
    def __init__(
        self,
        gemini_keys: Optional[List[str]] = None,
        openai_keys: Optional[List[str]] = None,
        rotation_strategy: str = "round_robin",  # round_robin, random, least_used
    ):
        """
        Initialize multi-key provider.
        
        Args:
            gemini_keys: List of Gemini API keys
            openai_keys: List of OpenAI API keys
            rotation_strategy: Key selection strategy
        """
        self._keys: Dict[str, List[APIKeyInfo]] = {
            "gemini": [],
            "openai": [],
        }
        
        self._rotation_strategy = rotation_strategy
        self._current_indices: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        
        # Load keys from parameters or environment
        self._load_keys(gemini_keys, openai_keys)
    
    def _load_keys(
        self,
        gemini_keys: Optional[List[str]] = None,
        openai_keys: Optional[List[str]] = None,
    ) -> None:
        """Load API keys from parameters or environment."""
        
        # Gemini keys
        if gemini_keys:
            for key in gemini_keys:
                if key and key.strip():
                    self._keys["gemini"].append(APIKeyInfo(key=key.strip(), provider="gemini"))
        else:
            # Load from environment (comma-separated or numbered)
            env_keys = os.environ.get("GEMINI_API_KEYS", "")
            if env_keys:
                for key in env_keys.split(","):
                    if key.strip():
                        self._keys["gemini"].append(APIKeyInfo(key=key.strip(), provider="gemini"))
            
            # Also check numbered keys: GEMINI_API_KEY_1, GEMINI_API_KEY_2, etc.
            for i in range(1, 10):
                key = os.environ.get(f"GEMINI_API_KEY_{i}", "")
                if key.strip():
                    self._keys["gemini"].append(APIKeyInfo(key=key.strip(), provider="gemini"))
            
            # Also check the single key
            single_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPROOM_GEMINI_API_KEY")
            if single_key and single_key.strip():
                # Avoid duplicates
                existing = {k.key for k in self._keys["gemini"]}
                if single_key.strip() not in existing:
                    self._keys["gemini"].append(APIKeyInfo(key=single_key.strip(), provider="gemini"))
        
        # OpenAI keys
        if openai_keys:
            for key in openai_keys:
                if key and key.strip():
                    self._keys["openai"].append(APIKeyInfo(key=key.strip(), provider="openai"))
        else:
            env_keys = os.environ.get("OPENAI_API_KEYS", "")
            if env_keys:
                for key in env_keys.split(","):
                    if key.strip():
                        self._keys["openai"].append(APIKeyInfo(key=key.strip(), provider="openai"))
            
            for i in range(1, 10):
                key = os.environ.get(f"OPENAI_API_KEY_{i}", "")
                if key.strip():
                    self._keys["openai"].append(APIKeyInfo(key=key.strip(), provider="openai"))
            
            single_key = os.environ.get("OPENAI_API_KEY")
            if single_key and single_key.strip():
                existing = {k.key for k in self._keys["openai"]}
                if single_key.strip() not in existing:
                    self._keys["openai"].append(APIKeyInfo(key=single_key.strip(), provider="openai"))
        
        # Log key counts
        for provider, keys in self._keys.items():
            if keys:
                logger.info(f"Loaded {len(keys)} {provider} API keys")
    
    def add_key(self, key: str, provider: str) -> None:
        """Add a new API key."""
        if provider not in self._keys:
            self._keys[provider] = []
        
        existing = {k.key for k in self._keys[provider]}
        if key not in existing:
            self._keys[provider].append(APIKeyInfo(key=key, provider=provider))
            logger.info(f"Added new {provider} API key ending in ...{key[-4:]}")
    
    def remove_key(self, key: str, provider: str) -> None:
        """Remove an API key."""
        if provider in self._keys:
            self._keys[provider] = [k for k in self._keys[provider] if k.key != key]
    
    def get_available_keys(self, provider: str) -> List[APIKeyInfo]:
        """Get all available keys for a provider."""
        if provider not in self._keys:
            return []
        return [k for k in self._keys[provider] if k.is_available]
    
    def has_keys(self, provider: str) -> bool:
        """Check if any keys are available for a provider."""
        return len(self.get_available_keys(provider)) > 0
    
    async def get_next_key(self, provider: str) -> Optional[str]:
        """
        Get the next available API key using the rotation strategy.
        
        Args:
            provider: Provider name (gemini, openai)
            
        Returns:
            API key string or None if no keys available
        """
        async with self._lock:
            available = self.get_available_keys(provider)
            
            if not available:
                logger.warning(f"No available {provider} API keys")
                return None
            
            if self._rotation_strategy == "random":
                key_info = random.choice(available)
            elif self._rotation_strategy == "least_used":
                key_info = min(available, key=lambda k: k.use_count)
            else:  # round_robin (default)
                idx = self._current_indices[provider] % len(available)
                key_info = available[idx]
                self._current_indices[provider] = idx + 1
            
            key_info.mark_used()
            return key_info.key
    
    def mark_rate_limited(self, key: str, provider: str, retry_after: float = 60.0) -> None:
        """Mark a key as rate limited."""
        for key_info in self._keys.get(provider, []):
            if key_info.key == key:
                key_info.mark_rate_limited(retry_after)
                break
    
    def mark_error(self, key: str, provider: str) -> None:
        """Mark a key with error."""
        for key_info in self._keys.get(provider, []):
            if key_info.key == key:
                key_info.mark_error()
                break
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics for all keys."""
        stats = {}
        for provider, keys in self._keys.items():
            stats[provider] = {
                "total_keys": len(keys),
                "available_keys": len([k for k in keys if k.is_available]),
                "rate_limited": len([k for k in keys if k.status == KeyStatus.RATE_LIMITED]),
                "errored": len([k for k in keys if k.status == KeyStatus.ERROR]),
                "total_requests": sum(k.use_count for k in keys),
                "keys": [
                    {
                        "id": f"...{k.key[-4:]}",
                        "status": k.status.value,
                        "use_count": k.use_count,
                        "daily_requests": k.daily_requests,
                        "error_count": k.error_count,
                    }
                    for k in keys
                ],
            }
        return stats


# Global instance
_multi_key_provider: Optional[MultiKeyProvider] = None


def get_multi_key_provider() -> MultiKeyProvider:
    """Get the global multi-key provider instance."""
    global _multi_key_provider
    if _multi_key_provider is None:
        _multi_key_provider = MultiKeyProvider()
    return _multi_key_provider


def configure_multi_key_provider(
    gemini_keys: Optional[List[str]] = None,
    openai_keys: Optional[List[str]] = None,
    rotation_strategy: str = "round_robin",
) -> MultiKeyProvider:
    """Configure the global multi-key provider."""
    global _multi_key_provider
    _multi_key_provider = MultiKeyProvider(
        gemini_keys=gemini_keys,
        openai_keys=openai_keys,
        rotation_strategy=rotation_strategy,
    )
    return _multi_key_provider


# ═══════════════════════════════════════════════════════════════
# Enhanced Gemini Provider with Multi-Key Support
# ═══════════════════════════════════════════════════════════════

class MultiKeyGeminiProvider:
    """
    Gemini provider with multi-key rotation.
    
    Uses MultiKeyProvider for automatic key rotation and failover.
    """
    
    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        multi_key_provider: Optional[MultiKeyProvider] = None,
    ):
        self.model = model
        self._mkp = multi_key_provider or get_multi_key_provider()
        self._current_key: Optional[str] = None
        self._client = None
        self._model_instance = None
    
    async def _ensure_client(self, force_new: bool = False) -> bool:
        """Initialize or rotate the Gemini client."""
        if self._client is not None and not force_new:
            return True
        
        key = await self._mkp.get_next_key("gemini")
        if not key:
            return False
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=key)
            self._client = genai
            self._model_instance = genai.GenerativeModel(self.model)
            self._current_key = key
            return True
        except ImportError:
            raise ImportError("google-generativeai required: pip install google-generativeai")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini with key ...{key[-4:]}: {e}")
            self._mkp.mark_error(key, "gemini")
            return await self._ensure_client(force_new=True)  # Try next key
    
    async def generate(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        max_retries: int = 3,
    ) -> str:
        """
        Generate text with automatic key rotation on rate limits.
        
        Args:
            prompt: The prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_retries: Maximum retry attempts
            
        Returns:
            Generated text
        """
        for attempt in range(max_retries):
            if not await self._ensure_client():
                raise RuntimeError("No available Gemini API keys")
            
            try:
                response = await self._model_instance.generate_content_async(
                    prompt,
                    generation_config={
                        "max_output_tokens": max_tokens,
                        "temperature": temperature,
                    }
                )
                return response.text
                
            except Exception as e:
                error_msg = str(e).lower()
                
                if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
                    # Rate limited - rotate to next key
                    logger.warning(f"Rate limit hit, rotating key (attempt {attempt + 1})")
                    self._mkp.mark_rate_limited(self._current_key, "gemini", retry_after=60)
                    self._client = None  # Force new client
                    continue
                    
                elif "invalid" in error_msg or "401" in error_msg or "403" in error_msg:
                    # Invalid key
                    self._mkp.mark_error(self._current_key, "gemini")
                    self._client = None
                    continue
                    
                else:
                    raise
        
        raise RuntimeError(f"Failed to generate after {max_retries} attempts")
    
    async def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Generate streaming text with key rotation."""
        if not await self._ensure_client():
            raise RuntimeError("No available Gemini API keys")
        
        try:
            response = await self._model_instance.generate_content_async(
                prompt,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                },
                stream=True,
            )
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            error_msg = str(e).lower()
            if "rate" in error_msg or "quota" in error_msg:
                self._mkp.mark_rate_limited(self._current_key, "gemini")
                raise
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get multi-key statistics."""
        return self._mkp.get_stats()
