"""
Report Studio Writer Agent — LangGraph-powered AI Writing System.

A sophisticated multi-node pipeline that generates professional forensic
report sections by synthesizing insights from all investigative modules.

Pipeline Architecture:
  1. gather_context    → Pulls relevant insights based on section type
  2. generate_draft    → LLM generates initial prose with citations
  3. inject_citations  → Adds evidence references with hashes
  4. harmonize_style   → Ensures consistent voice across sections
  5. validate_facts    → Cross-checks numbers/dates against source data

The Writer Agent produces court-ready forensic prose that maintains
evidence integrity through SHA-256 backed citations.
"""

import json
import uuid
import logging
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import TypedDict, Optional, Literal

from langgraph.graph import StateGraph, END

from operation_room.services.llm_provider import get_llm
from operation_room.services.report_studio_service import get_writer_context, get_all_insights, get_module_insight
from operation_room.services.audit_service import record_coc_event
from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_content(content: str) -> str:
    """SHA-256 hash of text content."""
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _normalize_style(style: Optional[str]) -> str:
    """Normalize style input to a supported style key."""
    normalized = (style or "technical").strip().lower()
    if normalized == "formal":
        return "regulatory"
    if normalized not in STYLE_INSTRUCTIONS:
        return "technical"
    return normalized


def _build_validation_case_data(all_insights: dict) -> dict:
    """Flatten insight payload into the shape expected by FactCheckerService."""
    modules = all_insights.get("modules", {}) if isinstance(all_insights, dict) else {}

    timeline = modules.get("timeline", {})
    anomaly = modules.get("anomaly", {})
    correlation = modules.get("correlation", {})

    return {
        "timeline": {
            "total_events": timeline.get("summary", {}).get("total_events"),
            "events": timeline.get("anchor_events", []),
        },
        "anomaly": {
            "total_anomalies": anomaly.get("summary", {}).get("anomaly_count"),
            "top_anomalies": anomaly.get("top_anomalies", []),
        },
        "correlation": {
            "node_count": correlation.get("summary", {}).get("node_count"),
            "edge_count": correlation.get("summary", {}).get("edge_count"),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WRITER AGENT STATE
# ═══════════════════════════════════════════════════════════════════════════════

class WriterAgentState(TypedDict, total=False):
    # Input
    case_id: str
    section_type: str
    selected_modules: list[str]
    style: Literal["technical", "executive", "regulatory"]
    custom_instructions: Optional[str]
    
    # Context (gathered)
    context: dict
    all_insights: dict
    
    # Generated
    draft: str
    draft_with_citations: str
    final_content: str
    citations: list[dict]
    validation: dict
    
    # Metadata
    generation_id: str
    content_hash: str
    iteration: int
    status: str
    error: Optional[str]
    timestamps: dict


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION-SPECIFIC PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

SECTION_PROMPTS = {
    "executive_summary": """Write a concise executive summary (3-4 paragraphs) for a forensic incident report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Lead with the most critical finding and overall severity
- Include: incident type, time range, systems affected, business impact
- Mention key metrics: anomaly count, entities involved, data exposure
- End with high-level remediation priority
- Professional, non-technical language suitable for C-suite
- Use specific numbers from the data provided""",

    "case_overview": """Write a case overview section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Describe the investigation scope and objectives
- List log sources and time range analyzed
- Identify key actors and systems under investigation
- Provide context on evidence collection methodology
- Reference evidence hashes for integrity verification
- Professional forensic analyst tone""",

    "timeline_narrative": """Write a narrative timeline analysis for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Chronicle events in temporal order with specific timestamps
- Highlight anchor events and severity changes
- Identify suspicious activity patterns
- Note correlation between event clusters
- Use data visualization references (charts, timelines)
- Include specific timestamps and event counts""",

    "anomaly_findings": """Write the anomaly detection findings section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Explain the detection methodology (algorithm, threshold)
- Detail the top anomalies with SHAP feature explanations
- Identify the most anomalous actors and their behaviors
- Provide statistical context (detection rate, score distribution)
- Link anomalies to specific suspicious events
- Technical but accessible language""",

    "attack_chain": """Write the attack chain and correlation analysis section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Map the attack progression using entity relationships
- Reference MITRE ATT&CK tactics if available
- Describe the entity graph structure (nodes, edges, relationships)
- Identify root cause entities and their connections
- Include the AI-generated correlation narrative if available
- Use graph terminology appropriately""",

    "data_access": """Write the data access and CRUD analysis section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Summarize CRUD operation distribution (Create/Read/Update/Delete)
- Highlight high-risk data access events
- Detail sensitivity levels of accessed data
- Identify suspicious actors and their data targets
- Quantify data volume by operation type
- Focus on potential data exfiltration or destruction""",

    "network_activity": """Write the network and exfiltration analysis section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Summarize network flow statistics (volume, protocols, directions)
- Detail suspicious flows and destinations
- Describe exfiltration candidates with confidence scores
- Include threat intelligence matches if available
- Quantify data transfer volumes
- Highlight geographic anomalies""",

    "depth_assessment": """Write the depth and impact assessment section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Explain the 4-dimension depth model (account, system, data, control)
- Present scores for each dimension with evidence
- Identify the most compromised dimension
- Assess overall severity and business impact
- Compare against industry benchmarks if applicable
- Provide clear severity classification""",

    "remediation": """Write the remediation and recommendations section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Prioritize actions based on depth assessment severity
- Address each compromised dimension specifically
- Include immediate containment actions
- Provide long-term security improvements
- Reference specific entities/systems needing attention
- Actionable, specific recommendations""",

    "chain_of_custody": """Write the chain of custody and evidence integrity section for a forensic report.

CONTEXT DATA:
{context}

REQUIREMENTS:
- Document evidence handling procedures
- List evidence hashes and verification status
- Summarize chain of custody events
- Confirm integrity verification methodology
- Reference SHA-256 hash values
- Court-admissible documentation standard""",
}

STYLE_INSTRUCTIONS = {
    "technical": "Write in detailed technical forensic language suitable for security analysts and incident responders. Include specific technical details, metrics, and evidence references.",
    "executive": "Write in clear, business-focused language suitable for executives and board members. Emphasize business impact and high-level findings. Avoid jargon.",
    "regulatory": "Write in compliance-focused language suitable for regulatory submissions. Follow breach notification standards. Emphasize personal data impact and remediation steps.",
}


# ═══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH NODES
# ═══════════════════════════════════════════════════════════════════════════════

async def gather_context(state: WriterAgentState) -> WriterAgentState:
    """Node 1: Gather relevant context from modules based on section type."""
    logger.info(f"[WriterAgent] Gathering context for section: {state['section_type']}")
    
    state["timestamps"] = state.get("timestamps", {})
    state["timestamps"]["gather_start"] = _now_iso()
    
    try:
        # Get section-specific context
        context = get_writer_context(
            state["case_id"],
            state["section_type"],
            state.get("selected_modules"),
        )
        
        # Also get full insights for cross-referencing
        all_insights = get_all_insights(state["case_id"])
        
        state["context"] = context
        state["all_insights"] = all_insights
        state["status"] = "context_gathered"
        state["timestamps"]["gather_end"] = _now_iso()
        
    except Exception as e:
        logger.error(f"[WriterAgent] Context gathering failed: {e}")
        state["error"] = str(e)
        state["status"] = "error"
    
    return state


async def generate_draft(state: WriterAgentState) -> WriterAgentState:
    """Node 2: Generate initial draft using LLM."""
    if state.get("status") == "error":
        return state
    
    logger.info(f"[WriterAgent] Generating draft for section: {state['section_type']}")
    state["timestamps"]["generate_start"] = _now_iso()
    
    # Get section prompt
    section_type = state["section_type"]
    prompt_template = SECTION_PROMPTS.get(section_type)
    
    if not prompt_template:
        state["error"] = f"Unknown section type: {section_type}"
        state["status"] = "error"
        return state
    
    # Build context string for LLM
    context_str = json.dumps(state["context"], indent=2, default=str)
    prompt = prompt_template.format(context=context_str)
    
    # Add style instruction
    style = state.get("style", "technical")
    style_instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["technical"])
    
    # Add custom instructions if provided
    custom = state.get("custom_instructions", "")
    if custom:
        prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n{custom}"
    
    system_prompt = f"""You are a senior digital forensics analyst writing an official incident report.

STYLE REQUIREMENTS:
{style_instruction}

OUTPUT REQUIREMENTS:
- Write in clear, professional prose (not bullet points unless listing specific items)
- Use specific numbers, timestamps, and entity names from the provided data
- Maintain an objective, evidence-based tone
- Structure with clear paragraphs
- Do NOT include section headers (the header is added separately)
- Length: 2-5 paragraphs depending on available data"""

    try:
        llm = get_llm()
        draft = await llm.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.3,
            max_tokens=2000,
        )
        
        state["draft"] = draft.strip()
        state["status"] = "draft_generated"
        state["timestamps"]["generate_end"] = _now_iso()
        
    except Exception as e:
        logger.error(f"[WriterAgent] Draft generation failed: {e}")
        state["error"] = str(e)
        state["status"] = "error"
    
    return state


async def inject_citations(state: WriterAgentState) -> WriterAgentState:
    """Node 3: Add evidence citations with integrity hashes."""
    if state.get("status") == "error":
        return state
    
    logger.info("[WriterAgent] Injecting citations")
    state["timestamps"]["citation_start"] = _now_iso()
    
    draft = state.get("draft", "")
    citations = []
    
    # Extract module data hashes for citation references
    context = state.get("context", {})
    modules = context.get("modules", {})
    
    citation_index = 1
    citation_map = {}
    
    for module_name, module_data in modules.items():
        if module_data.get("summary"):
            # Create citation for module data
            citation_id = f"EVD-{module_name.upper()[:3]}-{citation_index:03d}"
            data_hash = module_data.get("data_hash", state["all_insights"]["modules"].get(module_name, {}).get("data_hash", ""))
            
            citations.append({
                "id": citation_id,
                "module": module_name,
                "type": "module_summary",
                "hash": data_hash,
                "extracted_at": context.get("extracted_at", _now_iso()),
            })
            
            citation_map[module_name] = citation_id
            citation_index += 1
    
    # Simple citation injection (add reference section at end)
    if citations:
        citation_refs = "\n\n---\n**Evidence References:**\n"
        for c in citations:
            citation_refs += f"- [{c['id']}] {c['module'].title()} module data (Hash: `{c['hash'][:24]}...`)\n"
        
        draft_with_citations = draft + citation_refs
    else:
        draft_with_citations = draft
    
    state["draft_with_citations"] = draft_with_citations
    state["citations"] = citations
    state["status"] = "citations_injected"
    state["timestamps"]["citation_end"] = _now_iso()
    
    return state


async def harmonize_style(state: WriterAgentState) -> WriterAgentState:
    """Node 4: Ensure consistent voice and style (optional refinement)."""
    if state.get("status") == "error":
        return state
    
    logger.info("[WriterAgent] Harmonizing style")
    state["timestamps"]["harmonize_start"] = _now_iso()
    
    # For now, pass through. In future, can use LLM for style refinement
    state["final_content"] = state.get("draft_with_citations", state.get("draft", ""))
    
    # Compute final content hash
    state["content_hash"] = _hash_content(state["final_content"])
    state["status"] = "style_harmonized"
    state["timestamps"]["harmonize_end"] = _now_iso()
    
    return state


async def validate_facts(state: WriterAgentState) -> WriterAgentState:
    """Node 5: Run lightweight factual validation on generated content."""
    if state.get("status") == "error":
        return state

    logger.info("[WriterAgent] Validating generated facts")
    state["timestamps"]["validate_start"] = _now_iso()

    try:
        from operation_room.services.validation_service import FactCheckerService

        validator = FactCheckerService(state["case_id"])
        validation_result = await validator.validate_content(
            content=state.get("final_content", ""),
            case_data=_build_validation_case_data(state.get("all_insights", {})),
            citations=state.get("citations", []),
        )

        issues = [issue.dict() for issue in validation_result.issues]
        state["validation"] = {
            "is_valid": validation_result.is_valid,
            "summary": validation_result.summary,
            "issues": issues,
        }
        state["status"] = "completed"

        error_issues = [i for i in validation_result.issues if i.severity.value == "error"]
        if error_issues:
            alert_block = "\n\n---\n**Validation Alerts:**\n"
            for issue in error_issues[:5]:
                alert_block += f"- [{issue.id}] {issue.title}: {issue.description}\n"
            state["final_content"] = f"{state.get('final_content', '').rstrip()}{alert_block}"
            state["content_hash"] = _hash_content(state["final_content"])

    except Exception as e:
        # Validation should not block report generation.
        logger.warning(f"[WriterAgent] Validation skipped due to error: {e}")
        state["validation"] = {
            "is_valid": False,
            "summary": {"error": str(e)},
            "issues": [],
        }
        state["status"] = "completed"

    state["timestamps"]["validate_end"] = _now_iso()
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# LANGGRAPH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def build_writer_graph():
    """Build the LangGraph state machine for the Writer Agent."""
    graph = StateGraph(WriterAgentState)
    
    # Add nodes
    graph.add_node("gather_context", gather_context)
    graph.add_node("generate_draft", generate_draft)
    graph.add_node("inject_citations", inject_citations)
    graph.add_node("harmonize_style", harmonize_style)
    graph.add_node("validate_facts", validate_facts)
    
    # Define edges (linear pipeline)
    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "generate_draft")
    graph.add_edge("generate_draft", "inject_citations")
    graph.add_edge("inject_citations", "harmonize_style")
    graph.add_edge("harmonize_style", "validate_facts")
    graph.add_edge("validate_facts", END)
    
    return graph.compile()


# Global compiled graph
_writer_graph = None


def get_writer_graph():
    """Get or create the compiled writer graph."""
    global _writer_graph
    if _writer_graph is None:
        _writer_graph = build_writer_graph()
    return _writer_graph


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_section(
    case_id: str,
    section_type: str,
    selected_modules: list[str] = None,
    style: str = "technical",
    custom_instructions: str = None,
) -> dict:
    """
    Generate a single report section using the Writer Agent.
    
    Args:
        case_id: The case ID
        section_type: Type of section to generate (e.g., 'executive_summary')
        selected_modules: Optional list of modules to include
        style: Writing style ('technical', 'executive', 'regulatory')
        custom_instructions: Optional custom instructions for the LLM
    
    Returns:
        Dict with generated content, citations, and metadata
    """
    generation_id = str(uuid.uuid4())
    normalized_style = _normalize_style(style)
    
    initial_state: WriterAgentState = {
        "case_id": case_id,
        "section_type": section_type,
        "selected_modules": selected_modules or [],
        "style": normalized_style,
        "custom_instructions": custom_instructions,
        "generation_id": generation_id,
        "iteration": 0,
        "status": "initialized",
        "timestamps": {"started": _now_iso()},
    }
    
    try:
        graph = get_writer_graph()
        final_state = await graph.ainvoke(initial_state)
        
        # Record CoC event
        if final_state.get("status") == "completed":
            record_coc_event(
                case_id=case_id,
                actor="writer_agent",
                action="SECTION_GENERATED",
                target_artefact=f"section:{section_type}",
                justification=f"AI-generated {section_type} section",
                hash_after=final_state.get("content_hash", ""),
                details={
                    "generation_id": generation_id,
                    "style": normalized_style,
                    "modules_used": list(final_state.get("context", {}).get("modules", {}).keys()),
                }
            )
        
        return {
            "generation_id": generation_id,
            "section_type": section_type,
            "style": normalized_style,
            "content": final_state.get("final_content", ""),
            "draft": final_state.get("draft", ""),
            "citations": final_state.get("citations", []),
            "validation": final_state.get("validation", {}),
            "content_hash": final_state.get("content_hash", ""),
            "status": final_state.get("status", "unknown"),
            "error": final_state.get("error"),
            "timestamps": final_state.get("timestamps", {}),
        }
        
    except Exception as e:
        logger.error(f"[WriterAgent] Section generation failed: {e}")
        return {
            "generation_id": generation_id,
            "section_type": section_type,
            "status": "error",
            "error": str(e),
        }


async def generate_multiple_sections(
    case_id: str,
    section_types: list[str],
    style: str = "technical",
) -> dict:
    """
    Generate multiple sections in parallel.
    
    Returns a dict mapping section_type to generation result.
    """
    tasks = [
        generate_section(case_id, section_type, style=style)
        for section_type in section_types
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return {
        section_types[i]: (
            results[i] if not isinstance(results[i], Exception)
            else {"status": "error", "error": str(results[i])}
        )
        for i in range(len(section_types))
    }


async def improve_content(
    case_id: str,
    content: str,
    instruction: str,
    style: str = "technical",
) -> dict:
    """
    Improve existing content based on user instruction.
    
    Args:
        case_id: The case ID
        content: Existing content to improve
        instruction: User instruction (e.g., "make it more concise", "add more technical details")
        style: Writing style
    
    Returns:
        Dict with improved content and metadata
    """
    generation_id = str(uuid.uuid4())

    normalized_style = _normalize_style(style)
    style_instruction = STYLE_INSTRUCTIONS.get(normalized_style, STYLE_INSTRUCTIONS["technical"])
    
    prompt = f"""Improve the following forensic report content based on the user's instruction.

CURRENT CONTENT:
{content}

USER INSTRUCTION:
{instruction}

OUTPUT:
Provide the improved content only, no explanations."""

    system_prompt = f"""You are a senior digital forensics analyst editing an incident report.

STYLE REQUIREMENTS:
{style_instruction}

Maintain professional forensic report standards while following the user's improvement instruction."""

    try:
        llm = get_llm()
        improved = await llm.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.3,
            max_tokens=2000,
        )
        
        improved_content = improved.strip()
        content_hash = _hash_content(improved_content)
        
        # Record CoC event
        record_coc_event(
            case_id=case_id,
            actor="writer_agent",
            action="CONTENT_IMPROVED",
            target_artefact=f"content:{generation_id}",
            justification=f"AI-improved content: {instruction[:50]}...",
            hash_after=content_hash,
        )
        
        return {
            "generation_id": generation_id,
            "original_content": content,
            "improved_content": improved_content,
            "instruction": instruction,
            "style": normalized_style,
            "content_hash": content_hash,
            "status": "completed",
        }
        
    except Exception as e:
        logger.error(f"[WriterAgent] Content improvement failed: {e}")
        return {
            "generation_id": generation_id,
            "status": "error",
            "error": str(e),
        }


def list_available_sections() -> list[dict]:
    """List all available section types with their descriptions."""
    return [
        {"type": "executive_summary", "title": "Executive Summary", "description": "High-level overview for executives"},
        {"type": "case_overview", "title": "Case Overview", "description": "Investigation scope and methodology"},
        {"type": "timeline_narrative", "title": "Timeline Narrative", "description": "Chronological event analysis"},
        {"type": "anomaly_findings", "title": "Anomaly Findings", "description": "Detection results with SHAP explanations"},
        {"type": "attack_chain", "title": "Attack Chain", "description": "Correlation and MITRE ATT&CK mapping"},
        {"type": "data_access", "title": "Data Access Analysis", "description": "CRUD operations and sensitivity"},
        {"type": "network_activity", "title": "Network Activity", "description": "Traffic and exfiltration analysis"},
        {"type": "depth_assessment", "title": "Depth Assessment", "description": "4D penetration severity scoring"},
        {"type": "remediation", "title": "Remediation", "description": "Prioritized recommendations"},
        {"type": "chain_of_custody", "title": "Chain of Custody", "description": "Evidence integrity documentation"},
    ]


def list_available_styles() -> list[dict]:
    """List available writing styles."""
    return [
        {"id": "technical", "title": "Technical", "description": "Detailed technical language for analysts"},
        {"id": "executive", "title": "Executive", "description": "Business-focused language for leadership"},
        {"id": "regulatory", "title": "Regulatory", "description": "Compliance-focused for regulators"},
    ]
