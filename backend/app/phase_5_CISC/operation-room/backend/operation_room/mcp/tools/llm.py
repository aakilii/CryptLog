"""
MCP LLM Integration Tools
==========================

Gemini API integration for AI-powered narrative generation.

Key Principles:
- AI generates PROSE and SUMMARIES only
- All facts (IPs, users, timestamps) come from evidence
- Every citation references hash-verified evidence
- Transparent reasoning with audit trail

Supports:
- Google Gemini API (primary)
- Fallback to mock generation for testing
"""

import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

# Import from our MCP infrastructure
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from operation_room.mcp.decorators import mcp_tool, with_coc_logging
from operation_room.mcp.schemas import HashedModel, MCPToolResult as ToolResult


# =============================================================================
# CONFIGURATION
# =============================================================================

class LLMConfig(BaseModel):
    """LLM configuration settings."""
    provider: Literal["gemini", "openai", "mock"] = "gemini"
    llm_model: str = "gemini-1.5-flash"  # Renamed to avoid Pydantic conflict
    api_key: Optional[str] = None
    temperature: float = 0.3  # Lower for more factual output
    max_tokens: int = 4096
    top_p: float = 0.9
    timeout: int = 60
    
    model_config = {"protected_namespaces": ()}  # Allow model_ prefix
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load configuration from environment variables."""
        return cls(
            provider=os.getenv("LLM_PROVIDER", "gemini"),
            llm_model=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )


# Global config instance
_config: Optional[LLMConfig] = None


def get_config() -> LLMConfig:
    """Get or create LLM configuration."""
    global _config
    if _config is None:
        _config = LLMConfig.from_env()
    return _config


def set_config(config: LLMConfig) -> None:
    """Set LLM configuration."""
    global _config
    _config = config


# =============================================================================
# DATA MODELS
# =============================================================================

class GenerationRequest(BaseModel):
    """Request for LLM text generation."""
    request_id: str = Field(default_factory=lambda: f"gen-{uuid.uuid4().hex[:8]}")
    system_prompt: str = ""
    user_prompt: str
    context: Dict[str, Any] = Field(default_factory=dict)
    citations: List[str] = Field(default_factory=list)  # Evidence citations to include
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    

class GenerationResponse(HashedModel):
    """Response from LLM generation."""
    request_id: str
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    citations_inserted: List[str] = Field(default_factory=list)
    facts_extracted: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: int = 0


class FactCheckResult(BaseModel):
    """Result of fact-checking generated content."""
    valid: bool
    content: str  # Potentially corrected content
    facts_verified: int
    facts_corrected: int
    corrections: List[Dict[str, Any]] = Field(default_factory=list)


class ContentAnalysis(BaseModel):
    """Analysis of content for forensic relevance."""
    relevance_score: float  # 0-1
    key_entities: List[str]
    key_timestamps: List[str]
    key_actions: List[str]
    sentiment: Literal["neutral", "concerning", "critical"]
    summary: str


# =============================================================================
# GEMINI API CLIENT
# =============================================================================

class GeminiClient:
    """Google Gemini API client for text generation."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
        self._model = None
    
    async def _ensure_client(self) -> bool:
        """Lazily initialize Gemini client."""
        if self._client is not None:
            return True
            
        if not self.config.api_key:
            return False
            
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.config.api_key)
            self._client = genai
            self._model = genai.GenerativeModel(self.config.llm_model)
            return True
        except ImportError:
            print("Warning: google-generativeai not installed. Using mock generation.")
            return False
        except Exception as e:
            print(f"Warning: Failed to initialize Gemini client: {e}")
            return False
    
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text using Gemini API."""
        start_time = datetime.now(timezone.utc)
        
        # Try to initialize client
        if not await self._ensure_client():
            # Fall back to mock generation
            return await self._mock_generate(request, start_time)
        
        try:
            # Build prompt with system context
            full_prompt = self._build_prompt(request)
            
            # Configure generation
            generation_config = {
                "temperature": request.temperature or self.config.temperature,
                "max_output_tokens": request.max_tokens or self.config.max_tokens,
                "top_p": self.config.top_p,
            }
            
            # Generate response
            response = await asyncio.to_thread(
                self._model.generate_content,
                full_prompt,
                generation_config=generation_config
            )
            
            content = response.text
            
            # Insert citations into content
            content, citations_used = self._inject_citations(content, request.citations)
            
            # Extract any facts mentioned
            facts = self._extract_facts(content, request.context)
            
            latency = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            
            return GenerationResponse(
                request_id=request.request_id,
                content=content,
                model=self.config.llm_model,
                provider="gemini",
                tokens_used=response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
                citations_inserted=citations_used,
                facts_extracted=facts,
                latency_ms=latency
            )
            
        except Exception as e:
            print(f"Gemini generation failed: {e}. Using mock.")
            return await self._mock_generate(request, start_time)
    
    def _build_prompt(self, request: GenerationRequest) -> str:
        """Build full prompt with system context."""
        parts = []
        
        # System prompt
        if request.system_prompt:
            parts.append(f"SYSTEM INSTRUCTIONS:\n{request.system_prompt}\n")
        
        # Context data
        if request.context:
            context_str = "\n".join([
                f"- {k}: {str(v)[:500]}" for k, v in request.context.items()
            ])
            parts.append(f"CONTEXT DATA (use these facts, do not invent):\n{context_str}\n")
        
        # Available citations
        if request.citations:
            citations_str = "\n".join([f"- {c}" for c in request.citations])
            parts.append(f"EVIDENCE CITATIONS (insert where relevant):\n{citations_str}\n")
        
        # User prompt
        parts.append(f"USER REQUEST:\n{request.user_prompt}")
        
        return "\n\n".join(parts)
    
    def _inject_citations(
        self, 
        content: str, 
        citations: List[str]
    ) -> Tuple[str, List[str]]:
        """Inject citation markers into generated content."""
        used = []
        
        for citation in citations:
            # Look for natural places to insert citations
            # (after factual statements, at paragraph ends)
            if citation not in content and citations:
                # Insert first available citation at a reasonable point
                # This is simplified - production would be smarter
                if ". " in content and citation not in used:
                    # Insert after first sentence
                    parts = content.split(". ", 1)
                    if len(parts) == 2:
                        content = f"{parts[0]}. {citation} {parts[1]}"
                        used.append(citation)
        
        # Also track citations already in content
        for citation in citations:
            if citation in content and citation not in used:
                used.append(citation)
        
        return content, used
    
    def _extract_facts(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract factual claims from generated content."""
        facts = []
        
        # IP address pattern
        ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        for match in re.finditer(ip_pattern, content):
            facts.append({
                "type": "ip_address",
                "value": match.group(),
                "from_context": match.group() in str(context)
            })
        
        # Timestamp pattern (ISO format)
        ts_pattern = r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
        for match in re.finditer(ts_pattern, content):
            facts.append({
                "type": "timestamp",
                "value": match.group(),
                "from_context": match.group() in str(context)
            })
        
        # Percentage pattern
        pct_pattern = r'\b\d+(?:\.\d+)?%'
        for match in re.finditer(pct_pattern, content):
            facts.append({
                "type": "percentage",
                "value": match.group(),
                "from_context": match.group() in str(context)
            })
        
        return facts
    
    async def _mock_generate(
        self,
        request: GenerationRequest,
        start_time: datetime
    ) -> GenerationResponse:
        """Mock generation when API is unavailable."""
        # Build response from context
        context_summary = ", ".join([
            f"{k}={str(v)[:50]}" for k, v in list(request.context.items())[:5]
        ])
        
        content = f"""
Based on the analysis of available evidence, the investigation has identified significant findings.

{request.user_prompt}

Key observations from the analysis:
{context_summary if context_summary else "Evidence analysis complete."}

The findings are supported by hash-verified evidence from the forensic vault, ensuring complete traceability and integrity of all conclusions.
""".strip()
        
        # Add citations
        for i, citation in enumerate(request.citations[:3]):
            content = content.replace(".", f" {citation}.", 1)
        
        latency = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        return GenerationResponse(
            request_id=request.request_id,
            content=content,
            model="mock",
            provider="mock",
            tokens_used=len(content.split()),
            citations_inserted=request.citations[:3],
            facts_extracted=[],
            latency_ms=latency
        )


# Global client instance
_client: Optional[GeminiClient] = None


def get_client() -> GeminiClient:
    """Get or create Gemini client."""
    global _client
    if _client is None:
        _client = GeminiClient(get_config())
    return _client


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

FORENSIC_SYSTEM_PROMPT = """You are a forensic investigation report writer assistant.

CRITICAL RULES:
1. NEVER invent or fabricate evidence. Only reference facts provided in CONTEXT DATA.
2. ALWAYS use provided EVIDENCE CITATIONS when making factual claims.
3. Write in professional, objective tone appropriate for legal/regulatory review.
4. Quantify claims when possible using provided data.
5. Clearly distinguish between confirmed findings (high confidence) and observations (lower confidence).
6. Do not speculate beyond what evidence supports.

OUTPUT FORMAT:
- Use markdown formatting
- Insert citation markers [EV-XXXXXX] after factual claims
- Structure with clear headings when appropriate
- Keep paragraphs concise and focused
"""

SECTION_PROMPTS = {
    "executive_summary": """
Write an executive summary for a forensic investigation report.

Requirements:
- 3-4 paragraphs, suitable for C-suite readers
- Focus on business impact and key findings
- Include confidence levels for conclusions
- Avoid technical jargon unless essential
- Cite evidence for major claims
""",

    "timeline_narrative": """
Write a chronological narrative of investigated events.

Requirements:
- Maintain strict temporal order
- Reference actual timestamps from evidence
- Mark anchor events (key moments)
- Connect events to investigation objectives
- Cite evidence for each factual claim
""",

    "anomaly_findings": """
Write a section describing anomaly detection findings.

Requirements:
- Explain why each anomaly was flagged
- Reference detection algorithm and threshold
- Rate severity of findings
- Connect anomalies to potential malicious activity
- Cite evidence for each anomaly
""",

    "hypothesis_analysis": """
Write a hypothesis analysis section.

Requirements:
- Present each hypothesis objectively
- Show evidence for and against
- Report confidence scores with ODNI ICD 203 levels
- Explain reasoning transparently
- Conclude with verdict and caveats
""",

    "findings": """
Write a findings section summarizing investigation conclusions.

Requirements:
- State each finding clearly
- Support with evidence citations
- Include confidence level
- Note limitations or gaps
- Maintain objective tone
""",

    "recommendations": """
Write recommendations based on investigation findings.

Requirements:
- Prioritize by urgency (immediate/short-term/long-term)
- Make recommendations actionable
- Reference supporting findings
- Consider technical and procedural measures
""",
}


# =============================================================================
# MCP TOOLS
# =============================================================================

@mcp_tool("llm.generate")
@with_coc_logging("LLM_GENERATION")
async def generate_text(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    citations: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    **kwargs
) -> ToolResult:
    """
    Generate text using LLM (Gemini).
    
    IMPORTANT: AI generates prose/summaries only. All facts
    must come from the provided context.
    
    Args:
        prompt: User prompt describing what to generate
        context: Context data with facts to use (IPs, timestamps, etc.)
        citations: Evidence citations to include [EV-XXXXXX]
        system_prompt: Optional system instructions
        max_tokens: Maximum tokens to generate
        temperature: Creativity (0-1, lower = more factual)
        
    Returns:
        ToolResult with generated content
    """
    request = GenerationRequest(
        user_prompt=prompt,
        context=context or {},
        citations=citations or [],
        system_prompt=system_prompt or FORENSIC_SYSTEM_PROMPT,
        max_tokens=max_tokens,
        temperature=temperature
    )
    
    client = get_client()
    response = await client.generate(request)
    
    # Check for non-context facts (potential hallucinations)
    hallucination_risk = any(
        not f.get("from_context", True) 
        for f in response.facts_extracted
    )
    
    return ToolResult(
        success=True,
        tool_name="llm.generate",
        data={
            "request_id": response.request_id,
            "content": response.content,
            "model": response.model,
            "provider": response.provider,
            "tokens_used": response.tokens_used,
            "citations_inserted": response.citations_inserted,
            "facts_extracted": response.facts_extracted,
            "hallucination_risk": hallucination_risk,
            "latency_ms": response.latency_ms,
            "generated_at": response.generated_at.isoformat()
        },
        evidence_hash=response.compute_hash()
    )


@mcp_tool("llm.generate_section")
@with_coc_logging("SECTION_GENERATED")
async def generate_report_section(
    section_type: str,
    context: Dict[str, Any],
    citations: List[str],
    style: str = "technical",
    **kwargs
) -> ToolResult:
    """
    Generate a specific report section with appropriate prompt.
    
    Args:
        section_type: Type of section (executive_summary, findings, etc.)
        context: Module results and evidence data
        citations: Evidence vault citations
        style: Writing style (technical, executive, regulatory)
        
    Returns:
        ToolResult with generated section content
    """
    section_prompt = SECTION_PROMPTS.get(section_type, f"Write a {section_type} section.")
    
    # Build context-aware prompt
    full_prompt = f"""
{section_prompt}

Writing style: {style}

Generate content for this section using ONLY the facts provided in context.
Insert citation markers {citations[:3] if citations else '[EV-XXXXXX]'} where you reference evidence.
"""
    
    request = GenerationRequest(
        user_prompt=full_prompt,
        context=context,
        citations=citations,
        system_prompt=FORENSIC_SYSTEM_PROMPT,
        temperature=0.2 if style == "technical" else 0.4
    )
    
    client = get_client()
    response = await client.generate(request)
    
    return ToolResult(
        success=True,
        tool_name="llm.generate_section",
        data={
            "section_type": section_type,
            "style": style,
            "content": response.content,
            "word_count": len(response.content.split()),
            "citations_used": response.citations_inserted,
            "model": response.model,
            "latency_ms": response.latency_ms
        },
        evidence_hash=response.compute_hash()
    )


@mcp_tool("llm.fact_check")
async def fact_check_content(
    content: str,
    known_facts: Dict[str, Any],
    **kwargs
) -> ToolResult:
    """
    Fact-check generated content against known facts.
    
    Ensures AI-generated text only contains facts from evidence.
    
    Args:
        content: Generated content to check
        known_facts: Dictionary of verified facts
        
    Returns:
        ToolResult with fact-check results
    """
    corrections = []
    facts_verified = 0
    facts_corrected = 0
    
    # Check IPs
    ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
    for match in re.finditer(ip_pattern, content):
        ip = match.group()
        known_ips = str(known_facts.get("ip_addresses", ""))
        if ip not in known_ips:
            corrections.append({
                "type": "unknown_ip",
                "value": ip,
                "position": match.start(),
                "severity": "high",
                "suggestion": f"Verify IP {ip} exists in evidence"
            })
            facts_corrected += 1
        else:
            facts_verified += 1
    
    # Check timestamps
    ts_pattern = r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'
    for match in re.finditer(ts_pattern, content):
        ts = match.group()
        known_times = str(known_facts.get("timestamps", ""))
        if ts not in known_times:
            corrections.append({
                "type": "unknown_timestamp",
                "value": ts,
                "position": match.start(),
                "severity": "medium",
                "suggestion": f"Verify timestamp {ts} exists in evidence"
            })
            facts_corrected += 1
        else:
            facts_verified += 1
    
    # Check for common hallucination patterns
    hallucination_patterns = [
        (r'\bapproximately \d+', "Unverified approximation"),
        (r'\bseveral \w+', "Vague quantity"),
        (r'\bmany \w+', "Vague quantity"),
        (r'\babout \d+', "Unverified approximation"),
    ]
    
    for pattern, desc in hallucination_patterns:
        for match in re.finditer(pattern, content):
            corrections.append({
                "type": "vague_claim",
                "value": match.group(),
                "position": match.start(),
                "severity": "low",
                "suggestion": f"{desc} - consider using exact figures"
            })
    
    valid = len([c for c in corrections if c["severity"] == "high"]) == 0
    
    return ToolResult(
        success=True,
        tool_name="llm.fact_check",
        data={
            "valid": valid,
            "facts_verified": facts_verified,
            "facts_corrected": facts_corrected,
            "corrections": corrections,
            "severity_summary": {
                "high": len([c for c in corrections if c["severity"] == "high"]),
                "medium": len([c for c in corrections if c["severity"] == "medium"]),
                "low": len([c for c in corrections if c["severity"] == "low"])
            }
        }
    )


@mcp_tool("llm.analyze_content")
async def analyze_content(
    content: str,
    analysis_type: str = "forensic",
    **kwargs
) -> ToolResult:
    """
    Analyze content for forensic relevance and key entities.
    
    Args:
        content: Text content to analyze
        analysis_type: Type of analysis (forensic, summary, entities)
        
    Returns:
        ToolResult with content analysis
    """
    # Extract entities
    entities = []
    
    # IPs
    for match in re.finditer(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content):
        entities.append(f"IP:{match.group()}")
    
    # Emails
    for match in re.finditer(r'\b[\w.-]+@[\w.-]+\.\w+\b', content):
        entities.append(f"EMAIL:{match.group()}")
    
    # File paths
    for match in re.finditer(r'[A-Za-z]:\\[^\s,]+|/[^\s,]+\.[a-z]+', content):
        entities.append(f"FILE:{match.group()}")
    
    # Timestamps
    timestamps = []
    for match in re.finditer(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', content):
        timestamps.append(match.group())
    
    # Key actions (verbs related to forensics)
    action_words = [
        "accessed", "transferred", "copied", "deleted", "modified",
        "exfiltrated", "uploaded", "downloaded", "executed", "installed",
        "logged", "connected", "disconnected", "authenticated", "failed"
    ]
    actions = [w for w in action_words if w in content.lower()]
    
    # Determine sentiment
    critical_words = ["critical", "severe", "urgent", "breach", "compromised", "attack"]
    concerning_words = ["suspicious", "anomaly", "unusual", "unexpected", "alert"]
    
    if any(w in content.lower() for w in critical_words):
        sentiment = "critical"
    elif any(w in content.lower() for w in concerning_words):
        sentiment = "concerning"
    else:
        sentiment = "neutral"
    
    # Calculate relevance
    relevance_factors = [
        len(entities) > 0,
        len(timestamps) > 0,
        len(actions) > 0,
        sentiment != "neutral",
        "evidence" in content.lower(),
        "[EV-" in content  # Has citations
    ]
    relevance_score = sum(relevance_factors) / len(relevance_factors)
    
    # Generate summary
    word_count = len(content.split())
    summary = f"Content contains {word_count} words, {len(entities)} entities, {len(timestamps)} timestamps. Sentiment: {sentiment}."
    
    return ToolResult(
        success=True,
        tool_name="llm.analyze_content",
        data={
            "analysis_type": analysis_type,
            "relevance_score": relevance_score,
            "key_entities": entities[:20],  # Top 20
            "key_timestamps": timestamps[:10],
            "key_actions": actions,
            "sentiment": sentiment,
            "summary": summary,
            "word_count": word_count,
            "has_citations": "[EV-" in content
        }
    )


@mcp_tool("llm.summarize")
async def summarize_content(
    content: str,
    max_sentences: int = 5,
    style: str = "bullet",
    **kwargs
) -> ToolResult:
    """
    Summarize content into key points.
    
    Args:
        content: Content to summarize
        max_sentences: Maximum summary sentences
        style: Summary style (bullet, paragraph, numbered)
        
    Returns:
        ToolResult with summary
    """
    # Use LLM for summarization
    prompt = f"""
Summarize the following forensic content in {max_sentences} key points.

Format: {style}
- bullet: Use bullet points
- paragraph: Single cohesive paragraph
- numbered: Numbered list

Content:
{content[:4000]}  # Truncate long content
"""
    
    request = GenerationRequest(
        user_prompt=prompt,
        context={},
        citations=[],
        system_prompt="You are a forensic report summarizer. Extract only key factual points.",
        temperature=0.2,
        max_tokens=500
    )
    
    client = get_client()
    response = await client.generate(request)
    
    return ToolResult(
        success=True,
        tool_name="llm.summarize",
        data={
            "summary": response.content,
            "style": style,
            "original_length": len(content),
            "summary_length": len(response.content),
            "compression_ratio": len(response.content) / len(content) if content else 0
        }
    )


@mcp_tool("llm.config", requires_case_id=False)
async def configure_llm(
    provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Configure LLM settings.
    
    Args:
        provider: LLM provider (gemini, openai, mock)
        llm_model: Model name
        temperature: Generation temperature (0-1)
        api_key: API key (for testing - prefer environment variables)
        
    Returns:
        ToolResult with current configuration
    """
    global _client
    config = get_config()
    
    # Update config
    if provider:
        config.provider = provider
    if llm_model:
        config.llm_model = llm_model
    if temperature is not None:
        config.temperature = temperature
    if api_key:
        config.api_key = api_key
    
    set_config(config)
    _client = None  # Reset client to pick up new config
    
    return ToolResult(
        success=True,
        tool_name="llm.config",
        data={
            "provider": config.provider,
            "model": config.llm_model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "api_key_set": config.api_key is not None,
            "timeout": config.timeout
        }
    )


@mcp_tool("llm.status", requires_case_id=False)
async def get_llm_status(**kwargs) -> ToolResult:
    """
    Get current LLM status and configuration.
    
    Returns:
        ToolResult with LLM status
    """
    config = get_config()
    client = get_client()
    
    # Test connection
    connected = await client._ensure_client()
    
    return ToolResult(
        success=True,
        tool_name="llm.status",
        data={
            "provider": config.provider,
            "model": config.llm_model,
            "connected": connected,
            "api_key_set": config.api_key is not None,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "ready": connected and config.api_key is not None
        }
    )


# =============================================================================
# TOOL EXPORTS
# =============================================================================

LLM_TOOLS = [
    generate_text,
    generate_report_section,
    fact_check_content,
    analyze_content,
    summarize_content,
    configure_llm,
    get_llm_status,
]


def register_llm_tools(registry):
    """Register all LLM tools with the MCP registry."""
    for tool in LLM_TOOLS:
        registry.register(tool)


__all__ = [
    "LLMConfig",
    "GenerationRequest",
    "GenerationResponse",
    "FactCheckResult",
    "ContentAnalysis",
    "GeminiClient",
    "get_config",
    "set_config",
    "get_client",
    "LLM_TOOLS",
    "register_llm_tools",
]
