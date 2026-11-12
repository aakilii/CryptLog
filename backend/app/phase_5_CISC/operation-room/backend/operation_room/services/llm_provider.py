"""
Switchable LLM Provider Layer.

Supports:
  • Qwen3 via Ollama (local, default)
  • Gemini via Google Generative AI SDK (API key) with multi-key rotation

Usage:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm()                        # uses config default
    llm = get_llm(provider="gemini")       # explicit override
    response = await llm.generate("Summarise the attack path", system="You are a forensic analyst")
"""

import json
import logging
import random
from abc import ABC, abstractmethod
from threading import Lock

import httpx

from operation_room.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "", temperature: float = 0.3, max_tokens: int = 2048) -> str:
        ...

    @abstractmethod
    def name(self) -> str:
        ...


class OllamaProvider(LLMProvider):
    """Qwen3 / any Ollama model."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or settings.OLLAMA_URL).rstrip("/")
        configured_model = model or settings.LLM_MODEL
        # Guard against mixed-provider config (e.g., LLM_MODEL set to Gemini name).
        if isinstance(configured_model, str) and configured_model.lower().startswith("gemini"):
            configured_model = "gemma2:2b"
        self.model = configured_model

    def name(self) -> str:
        return f"ollama/{self.model}"

    async def generate(self, prompt: str, system: str = "", temperature: float = 0.3, max_tokens: int = 2048) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", "")
        except httpx.ConnectError:
            logger.error(f"[LLM] Cannot connect to Ollama at {self.base_url}")
            return "[LLM Error] Ollama not reachable. Please ensure Ollama is running."
        except Exception as e:
            logger.error(f"[LLM] Ollama error: {e}")
            return f"[LLM Error] {str(e)}"


class GeminiKeyRotator:
    """Manages multiple API keys with rotation strategies."""
    
    def __init__(self, keys: list[str], strategy: str = "round_robin"):
        self.keys = [k for k in keys if k]  # Filter empty keys
        self.strategy = strategy
        self.current_index = 0
        self.key_usage = {k: 0 for k in self.keys}
        self.key_errors = {k: 0 for k in self.keys}
        self._lock = Lock()
    
    def get_next_key(self) -> str:
        """Get the next API key based on rotation strategy."""
        if not self.keys:
            return ""
        
        with self._lock:
            if self.strategy == "round_robin":
                key = self.keys[self.current_index % len(self.keys)]
                self.current_index += 1
            elif self.strategy == "random":
                key = random.choice(self.keys)
            elif self.strategy == "least_used":
                # Get key with least usage that hasn't errored too much
                available_keys = [k for k in self.keys if self.key_errors.get(k, 0) < 3]
                if not available_keys:
                    available_keys = self.keys  # Reset if all have errors
                key = min(available_keys, key=lambda k: self.key_usage.get(k, 0))
            else:
                key = self.keys[0]
            
            self.key_usage[key] = self.key_usage.get(key, 0) + 1
            return key
    
    def report_error(self, key: str):
        """Report an error for a key (for rate limiting handling)."""
        with self._lock:
            self.key_errors[key] = self.key_errors.get(key, 0) + 1
    
    def report_success(self, key: str):
        """Report success to reset error count."""
        with self._lock:
            self.key_errors[key] = 0


class GeminiProvider(LLMProvider):
    """Google Gemini via generativeai SDK with multi-key rotation."""

    _rotator = None  # Class-level rotator shared across instances
    _rotator_lock = Lock()

    def __init__(self, api_key: str = None, model: str = None):
        self.model_name = model or settings.LLM_MODEL or "gemini-2.5-flash"
        # Ensure model is a Gemini model
        if not self.model_name.lower().startswith("gemini"):
            self.model_name = "gemini-2.5-flash"
        
        # Initialize rotator with all available keys
        with GeminiProvider._rotator_lock:
            if GeminiProvider._rotator is None:
                all_keys = settings.get_gemini_keys()
                if api_key and api_key not in all_keys:
                    all_keys.append(api_key)
                GeminiProvider._rotator = GeminiKeyRotator(all_keys, settings.KEY_ROTATION)
        
        self.single_key = api_key  # Fallback single key

    def name(self) -> str:
        return f"gemini/{self.model_name}"
    
    def _get_api_key(self) -> str:
        """Get the next API key to use."""
        if GeminiProvider._rotator and GeminiProvider._rotator.keys:
            return GeminiProvider._rotator.get_next_key()
        return self.single_key or settings.GEMINI_API_KEY

    async def generate(self, prompt: str, system: str = "", temperature: float = 0.3, max_tokens: int = 2048) -> str:
        api_key = self._get_api_key()
        
        if not api_key:
            return "[LLM Error] No Gemini API key configured. Set OPROOM_GEMINI_API_KEY or OPROOM_GEMINI_API_KEYS in .env"
        
        # Try with current key, rotate on failure
        max_retries = min(3, len(GeminiProvider._rotator.keys) if GeminiProvider._rotator else 1)
        last_error = None
        
        for attempt in range(max_retries):
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=system if system else None,
                )
                full_prompt = prompt
                response = model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                
                # Report success
                if GeminiProvider._rotator:
                    GeminiProvider._rotator.report_success(api_key)
                
                return response.text
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Check if it's a rate limit or quota error
                if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
                    logger.warning(f"[LLM] Gemini rate limit hit, rotating key...")
                    if GeminiProvider._rotator:
                        GeminiProvider._rotator.report_error(api_key)
                        api_key = GeminiProvider._rotator.get_next_key()
                    continue
                else:
                    logger.error(f"[LLM] Gemini error: {e}")
                    break
        
        return f"[LLM Error] {str(last_error)}"


# ── Factory ──────────────────────────────────────────────

_providers = {}


def get_llm(provider: str = None) -> LLMProvider:
    """Get an LLM provider instance. Caches by provider name."""
    prov = provider or settings.LLM_PROVIDER

    if prov not in _providers:
        if prov == "ollama":
            _providers[prov] = OllamaProvider()
        elif prov == "gemini":
            _providers[prov] = GeminiProvider()
        else:
            logger.warning(f"[LLM] Unknown provider '{prov}', defaulting to gemini")
            _providers[prov] = GeminiProvider()

    return _providers[prov]


def list_providers() -> list[dict]:
    """List available LLM providers and their status."""
    gemini_keys = settings.get_gemini_keys()
    return [
        {
            "id": "ollama",
            "name": "Qwen3 (Ollama)",
            "description": "Local LLM via Ollama — fast, private, no API key needed",
            "requires_key": False,
            "configured": True,
            "default": settings.LLM_PROVIDER == "ollama",
        },
        {
            "id": "gemini",
            "name": "Gemini (Google AI)",
            "description": f"Google Gemini API — {len(gemini_keys)} key(s) configured",
            "requires_key": True,
            "configured": len(gemini_keys) > 0,
            "default": settings.LLM_PROVIDER == "gemini",
            "key_count": len(gemini_keys),
        },
    ]
