"""
Enhanced LLM Service for Multi-Agent System.

Provides:
- Async LLM calls with retry logic
- Structured output parsing (JSON mode)
- Token counting and rate limiting
- Conversation memory management
- Prompt templates for agents

Author: NFLIP Development Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TypeVar, Generic
from functools import wraps

from operation_room.config import settings
from operation_room.services.llm_provider import get_llm, LLMProvider

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LLMResponse:
    """Structured response from LLM."""
    content: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    model: str = ""
    success: bool = True
    error: Optional[str] = None
    parsed_json: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "model": self.model,
            "success": self.success,
            "error": self.error,
            "parsed_json": self.parsed_json,
        }


@dataclass
class ConversationMessage:
    """A message in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Conversation:
    """Manages conversation history for multi-turn interactions."""
    conversation_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    max_messages: int = 20
    
    def add_message(self, role: str, content: str):
        """Add a message, pruning old messages if needed."""
        self.messages.append(ConversationMessage(role=role, content=content))
        if len(self.messages) > self.max_messages:
            # Keep system message + last N messages
            system_msgs = [m for m in self.messages if m.role == "system"]
            other_msgs = [m for m in self.messages if m.role != "system"]
            self.messages = system_msgs + other_msgs[-(self.max_messages - len(system_msgs)):]
            
    def get_context(self) -> str:
        """Get conversation context as formatted string."""
        lines = []
        for msg in self.messages:
            prefix = {"user": "User", "assistant": "Assistant", "system": "System"}.get(msg.role, msg.role)
            lines.append(f"{prefix}: {msg.content}")
        return "\n\n".join(lines)
        
    def clear(self):
        """Clear conversation history."""
        self.messages = []


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_PROMPTS = {
    "hypothesis_analysis": """You are a forensic hypothesis analyst. Analyze the given scenario and generate testable hypotheses.

For each hypothesis:
1. State the hypothesis clearly
2. List required evidence to prove/disprove
3. Identify relevant attack vectors (MITRE ATT&CK)
4. Estimate initial probability

Respond in JSON format:
{
    "hypotheses": [
        {
            "id": "H1",
            "statement": "...",
            "evidence_required": ["..."],
            "attack_vectors": ["T1566", "..."],
            "initial_probability": 0.7,
            "reasoning": "..."
        }
    ],
    "entities": [
        {"name": "...", "type": "...", "role": "..."}
    ],
    "timeline_markers": ["..."]
}""",

    "evidence_analysis": """You are a digital forensics evidence analyst. Analyze the provided evidence and assess its relevance to the hypotheses.

For each piece of evidence:
1. Determine which hypotheses it supports or refutes
2. Assess evidence quality (0-1)
3. Identify any gaps or inconsistencies

Respond in JSON format:
{
    "evidence_analysis": [
        {
            "evidence_id": "...",
            "supports_hypotheses": ["H1"],
            "refutes_hypotheses": [],
            "quality_score": 0.85,
            "notes": "..."
        }
    ],
    "gaps": ["..."],
    "recommendations": ["..."]
}""",

    "confidence_assessment": """You are a forensic confidence assessor using intelligence community standards (ICD 203).

Evaluate the overall confidence level based on:
- Evidence coverage and quality
- Source reliability
- Analytical methodology
- Consistency of findings

Respond in JSON format:
{
    "overall_confidence": 0.75,
    "confidence_level": "high",
    "factors": {
        "evidence_quality": 0.8,
        "source_reliability": 0.7,
        "methodology": 0.75,
        "consistency": 0.8
    },
    "caveats": ["..."],
    "key_assumptions": ["..."]
}""",

    "report_synthesis": """You are a forensic report writer. Synthesize the analysis into a clear, professional report.

Structure:
1. Executive Summary (2-3 sentences)
2. Key Findings (bullet points)
3. Timeline of Events
4. Technical Analysis
5. Confidence Assessment
6. Recommendations

Write in clear, professional language suitable for both technical and executive audiences.""",

    "entity_extraction": """Extract all entities from the following text. Include:
- IP addresses, domains, URLs
- File paths, hashes
- User accounts, email addresses
- Timestamps, dates
- Organization names
- Malware names, CVE IDs

Respond in JSON format:
{
    "entities": [
        {"value": "...", "type": "ip_address", "context": "..."},
        {"value": "...", "type": "domain", "context": "..."}
    ]
}""",

    "attack_chain": """Analyze the evidence to reconstruct the attack chain.

Map to MITRE ATT&CK phases:
1. Initial Access
2. Execution
3. Persistence
4. Privilege Escalation
5. Defense Evasion
6. Credential Access
7. Discovery
8. Lateral Movement
9. Collection
10. Exfiltration

Respond in JSON format:
{
    "attack_chain": [
        {
            "phase": "Initial Access",
            "technique_id": "T1566.001",
            "technique_name": "Spearphishing Attachment",
            "evidence": ["..."],
            "timestamp": "...",
            "confidence": 0.85
        }
    ],
    "gaps": ["..."],
    "alternative_interpretations": ["..."]
}"""
}


# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED LLM SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedLLMService:
    """
    Enhanced LLM service with retry logic, structured output, and conversation management.
    """
    
    def __init__(
        self,
        provider: str = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        self.provider_name = provider or settings.LLM_PROVIDER
        self._llm: Optional[LLMProvider] = None
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._conversations: Dict[str, Conversation] = {}
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0,
        }
        
    @property
    def llm(self) -> LLMProvider:
        """Lazy-load LLM provider."""
        if self._llm is None:
            self._llm = get_llm(self.provider_name)
        return self._llm
        
    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False
    ) -> LLMResponse:
        """
        Generate response with retry logic.
        
        Args:
            prompt: User prompt
            system: System prompt
            temperature: Sampling temperature
            max_tokens: Max output tokens
            json_mode: If True, parse response as JSON
            
        Returns:
            LLMResponse with content and metadata
        """
        start_time = time.time()
        self._metrics["total_calls"] += 1
        
        if json_mode:
            system = f"{system}\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanations, just JSON."
            
        last_error = None
        for attempt in range(self.max_retries):
            try:
                content = await self.llm.generate(
                    prompt=prompt,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Check for error responses
                if content.startswith("[LLM Error]"):
                    raise Exception(content)
                    
                response = LLMResponse(
                    content=content,
                    tokens_used=len(content.split()),  # Rough estimate
                    latency_ms=latency_ms,
                    model=self.llm.name(),
                    success=True
                )
                
                # Parse JSON if requested
                if json_mode:
                    response.parsed_json = self._parse_json(content)
                    
                self._metrics["successful_calls"] += 1
                self._metrics["total_tokens"] += response.tokens_used
                self._metrics["total_latency_ms"] += latency_ms
                
                return response
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                    
        self._metrics["failed_calls"] += 1
        
        return LLMResponse(
            content="",
            latency_ms=(time.time() - start_time) * 1000,
            model=self.llm.name(),
            success=False,
            error=last_error
        )
        
    def _parse_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from response, handling markdown code blocks."""
        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
                
        # Try finding JSON object/array
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            match = re.search(pattern, content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
                    
        logger.warning(f"Failed to parse JSON from response: {content[:200]}...")
        return None
        
    async def generate_with_template(
        self,
        template_name: str,
        context: str,
        **kwargs
    ) -> LLMResponse:
        """
        Generate using a predefined prompt template.
        
        Args:
            template_name: Name of template from AGENT_PROMPTS
            context: Context to include in prompt
            **kwargs: Additional args for generate()
            
        Returns:
            LLMResponse
        """
        template = AGENT_PROMPTS.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
            
        prompt = f"{context}\n\n---\n\nAnalyze the above and respond as instructed."
        
        return await self.generate(
            prompt=prompt,
            system=template,
            json_mode=True,
            **kwargs
        )
        
    # ───────────────────────────────────────────────────────────────────────────
    # CONVERSATION MANAGEMENT
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_conversation(self, conversation_id: str) -> Conversation:
        """Get or create a conversation."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(conversation_id=conversation_id)
        return self._conversations[conversation_id]
        
    async def chat(
        self,
        conversation_id: str,
        message: str,
        system: str = "",
        **kwargs
    ) -> LLMResponse:
        """
        Multi-turn conversation.
        
        Args:
            conversation_id: Conversation identifier
            message: User message
            system: System prompt
            **kwargs: Additional args for generate()
            
        Returns:
            LLMResponse
        """
        conversation = self.get_conversation(conversation_id)
        conversation.add_message("user", message)
        
        # Build prompt with context
        context = conversation.get_context()
        
        response = await self.generate(
            prompt=context,
            system=system,
            **kwargs
        )
        
        if response.success:
            conversation.add_message("assistant", response.content)
            
        return response
        
    def clear_conversation(self, conversation_id: str):
        """Clear a conversation."""
        if conversation_id in self._conversations:
            self._conversations[conversation_id].clear()
            
    # ───────────────────────────────────────────────────────────────────────────
    # SPECIALIZED METHODS FOR AGENTS
    # ───────────────────────────────────────────────────────────────────────────
    
    async def analyze_hypothesis(self, scenario: str) -> LLMResponse:
        """Analyze scenario and generate hypotheses."""
        return await self.generate_with_template(
            "hypothesis_analysis",
            scenario,
            temperature=0.4
        )
        
    async def analyze_evidence(
        self,
        evidence: List[Dict[str, Any]],
        hypotheses: List[Dict[str, Any]]
    ) -> LLMResponse:
        """Analyze evidence against hypotheses."""
        context = f"""
Hypotheses:
{json.dumps(hypotheses, indent=2)}

Evidence:
{json.dumps(evidence, indent=2)}
"""
        return await self.generate_with_template(
            "evidence_analysis",
            context,
            temperature=0.3
        )
        
    async def assess_confidence(
        self,
        analysis: Dict[str, Any]
    ) -> LLMResponse:
        """Assess overall confidence."""
        return await self.generate_with_template(
            "confidence_assessment",
            json.dumps(analysis, indent=2),
            temperature=0.2
        )
        
    async def synthesize_report(
        self,
        findings: Dict[str, Any],
        report_type: str = "technical"
    ) -> LLMResponse:
        """Synthesize final report."""
        context = f"""
Report Type: {report_type}

Findings:
{json.dumps(findings, indent=2)}
"""
        return await self.generate(
            prompt=context,
            system=AGENT_PROMPTS["report_synthesis"],
            temperature=0.5,
            max_tokens=4096
        )
        
    async def extract_entities(self, text: str) -> LLMResponse:
        """Extract entities from text."""
        return await self.generate_with_template(
            "entity_extraction",
            text,
            temperature=0.1
        )
        
    async def analyze_attack_chain(
        self,
        evidence: List[Dict[str, Any]]
    ) -> LLMResponse:
        """Analyze evidence to reconstruct attack chain."""
        return await self.generate_with_template(
            "attack_chain",
            json.dumps(evidence, indent=2),
            temperature=0.3
        )
        
    # ───────────────────────────────────────────────────────────────────────────
    # METRICS
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        return {
            **self._metrics,
            "avg_latency_ms": (
                self._metrics["total_latency_ms"] / self._metrics["total_calls"]
                if self._metrics["total_calls"] > 0 else 0
            ),
            "success_rate": (
                self._metrics["successful_calls"] / self._metrics["total_calls"]
                if self._metrics["total_calls"] > 0 else 0
            ),
            "provider": self.provider_name,
            "model": self.llm.name() if self._llm else "not initialized",
        }
        
    def reset_metrics(self):
        """Reset service metrics."""
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency_ms": 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_llm_service: Optional[EnhancedLLMService] = None


def get_llm_service(provider: str = None) -> EnhancedLLMService:
    """Get or create the global LLM service instance."""
    global _llm_service
    
    if _llm_service is None or (provider and provider != _llm_service.provider_name):
        _llm_service = EnhancedLLMService(provider=provider)
        
    return _llm_service


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "LLMResponse",
    "ConversationMessage",
    "Conversation",
    "EnhancedLLMService",
    "get_llm_service",
    "AGENT_PROMPTS",
]
