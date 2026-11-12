"""
Summary Synthesis Agent — LangGraph Pipeline for Automated Report Generation.

The Summary Synthesis Agent is the final stage of the multi-agent pipeline.
It aggregates findings from all preceding agents and generates comprehensive
forensic reports in multiple formats.

Pipeline Architecture:
─────────────────────────────────────────────────────────────────────────────────
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     SUMMARY SYNTHESIS PIPELINE                           │
   │                                                                          │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │ AGGREGATE│──▶│ GENERATE │──▶│  WRITE   │──▶│ GENERATE │             │
   │  │ FINDINGS │   │ STRUCTURE│   │NARRATIVES│   │EXECUTIVE │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   │                                                    │                    │
   │                                                    ▼                    │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │  OUTPUT  │◀──│ ADD COC  │◀──│ GENERATE │◀──│ COMPILE  │             │
   │  │ FORMATS  │   │ SECTION  │   │   RECS   │   │ SECTIONS │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   └──────────────────────────────────────────────────────────────────────────┘
─────────────────────────────────────────────────────────────────────────────────

Output Formats:
- Technical Report (Full forensic analysis)
- Executive Summary (C-suite briefing)
- Regulatory Report (GDPR/HIPAA compliance)
- Incident Timeline
- Evidence Inventory

Research Integration (20+ methodologies):
- NIST Cybersecurity Framework
- ISO 27001/27035 Incident Management
- SANS Incident Response Guidelines
- DoD Risk Management Framework

Author: NFLIP Development Team
Version: 1.0.0
"""

import json
import uuid
import logging
import hashlib
from datetime import datetime, timezone
from typing import TypedDict, Optional, Any, Dict, List, Literal
from dataclasses import dataclass, field
from enum import Enum

from langgraph.graph import StateGraph, END

from operation_room.agents.base import BaseAgent, BaseAgentState, AgentStatus, registry
from operation_room.services.llm_provider import get_llm
from operation_room.services.audit_service import record_coc_event
from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

class ReportType(str, Enum):
    """Available report types."""
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    REGULATORY = "regulatory"
    TIMELINE = "timeline"
    EVIDENCE = "evidence"


REPORT_TEMPLATES = {
    ReportType.TECHNICAL: {
        "title": "Technical Forensic Investigation Report",
        "sections": [
            {"key": "executive_summary", "title": "Executive Summary", "order": 1},
            {"key": "case_overview", "title": "Case Overview & Scope", "order": 2},
            {"key": "methodology", "title": "Investigation Methodology", "order": 3},
            {"key": "hypothesis_analysis", "title": "Hypothesis Analysis", "order": 4},
            {"key": "timeline_analysis", "title": "Event Timeline Analysis", "order": 5},
            {"key": "anomaly_findings", "title": "Anomaly Detection Findings", "order": 6},
            {"key": "attack_chain", "title": "Attack Chain & Correlation", "order": 7},
            {"key": "data_access", "title": "Data Access Analysis", "order": 8},
            {"key": "network_analysis", "title": "Network & Exfiltration Analysis", "order": 9},
            {"key": "impact_assessment", "title": "Impact Assessment", "order": 10},
            {"key": "confidence_analysis", "title": "Confidence Analysis", "order": 11},
            {"key": "recommendations", "title": "Recommendations", "order": 12},
            {"key": "chain_of_custody", "title": "Chain of Custody", "order": 13},
            {"key": "appendix", "title": "Technical Appendix", "order": 14}
        ]
    },
    ReportType.EXECUTIVE: {
        "title": "Executive Incident Summary",
        "sections": [
            {"key": "executive_summary", "title": "Executive Summary", "order": 1},
            {"key": "business_impact", "title": "Business Impact", "order": 2},
            {"key": "key_findings", "title": "Key Findings", "order": 3},
            {"key": "risk_assessment", "title": "Risk Assessment", "order": 4},
            {"key": "recommendations", "title": "Recommended Actions", "order": 5}
        ]
    },
    ReportType.REGULATORY: {
        "title": "Regulatory Compliance Incident Report",
        "sections": [
            {"key": "incident_summary", "title": "Incident Summary", "order": 1},
            {"key": "affected_data", "title": "Personal Data Affected", "order": 2},
            {"key": "notification_requirements", "title": "Notification Requirements", "order": 3},
            {"key": "timeline", "title": "Incident Timeline", "order": 4},
            {"key": "containment", "title": "Containment Measures", "order": 5},
            {"key": "remediation", "title": "Remediation Actions", "order": 6},
            {"key": "evidence_integrity", "title": "Evidence Integrity", "order": 7}
        ]
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHESIS DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReportSection:
    """A single section of the generated report."""
    section_key: str
    title: str
    content: str = ""
    subsections: List["ReportSection"] = field(default_factory=list)
    order: int = 0
    word_count: int = 0
    citations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_key": self.section_key,
            "title": self.title,
            "content": self.content,
            "subsections": [s.to_dict() for s in self.subsections],
            "order": self.order,
            "word_count": self.word_count,
            "citations": self.citations
        }


@dataclass
class GeneratedReport:
    """Complete generated report."""
    report_id: str = field(default_factory=lambda: f"RPT{uuid.uuid4().hex[:8].upper()}")
    report_type: ReportType = ReportType.TECHNICAL
    title: str = ""
    generated_at: str = field(default_factory=_now_iso)
    
    # Content
    sections: List[ReportSection] = field(default_factory=list)
    
    # Metadata
    case_id: str = ""
    run_id: str = ""
    total_word_count: int = 0
    confidence_level: str = ""
    
    # Output formats
    markdown: str = ""
    html: str = ""
    json_data: Dict[str, Any] = field(default_factory=dict)
    
    # Integrity
    hash_value: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "title": self.title,
            "generated_at": self.generated_at,
            "sections": [s.to_dict() for s in self.sections],
            "case_id": self.case_id,
            "run_id": self.run_id,
            "total_word_count": self.total_word_count,
            "confidence_level": self.confidence_level,
            "hash_value": self.hash_value
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHESIS STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class SynthesisState(TypedDict, total=False):
    """State schema for the synthesis pipeline."""
    # Input
    case_id: str
    run_id: str
    report_type: str
    llm_provider: str
    
    # Aggregated data from other agents
    hypothesis_results: Dict[str, Any]
    evidence_inventory: Dict[str, Any]
    module_results: Dict[str, Dict[str, Any]]
    confidence_results: Dict[str, Any]
    
    # Case metadata
    case_metadata: Dict[str, Any]
    
    # Generated content
    report_structure: Dict[str, Any]
    section_contents: Dict[str, str]
    executive_summary: str
    key_findings: List[str]
    recommendations: List[Dict[str, Any]]
    
    # Chain of custody
    coc_summary: Dict[str, Any]
    
    # Final report
    report: Dict[str, Any]
    markdown_output: str
    html_output: str
    
    # Output
    output: Dict[str, Any]
    
    # Metadata
    status: str
    hash_value: str
    coc_event_id: str
    error: Optional[str]
    reasoning_steps: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# LLM PROMPTS FOR REPORT GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

EXECUTIVE_SUMMARY_PROMPT = """Write a compelling executive summary for a forensic incident report.

CASE INFORMATION:
{case_info}

KEY FINDINGS:
{findings}

CONFIDENCE ASSESSMENT:
{confidence}

IMPACT SUMMARY:
{impact}

REQUIREMENTS:
- 3-4 paragraphs, professional tone
- Lead with the most critical finding
- Include: incident type, time range, systems affected, business impact
- Mention overall confidence level
- End with high-level remediation priority
- Non-technical language suitable for C-suite executives
- Use specific numbers and dates from the data

OUTPUT: Write the executive summary directly, no JSON formatting needed."""

KEY_FINDINGS_PROMPT = """Extract and prioritize the key findings from this forensic investigation.

HYPOTHESIS ANALYSIS:
{hypotheses}

EVIDENCE SUMMARY:
{evidence}

MODULE FINDINGS:
{modules}

CONFIDENCE SCORES:
{confidence}

REQUIREMENTS:
- Identify 5-7 most significant findings
- Rank by severity and confidence
- Each finding should be 1-2 sentences
- Include evidence references
- Link to MITRE ATT&CK where applicable

OUTPUT (JSON):
{{
    "findings": [
        {{
            "id": "F1",
            "finding": "Description of finding",
            "severity": "critical|high|medium|low",
            "confidence": 0.0-1.0,
            "evidence": ["evidence references"],
            "mitre_technique": "TXXXX if applicable"
        }}
    ]
}}"""

RECOMMENDATIONS_PROMPT = """Generate actionable recommendations based on the investigation findings.

FINDINGS:
{findings}

IMPACT ASSESSMENT:
{impact}

CURRENT SECURITY POSTURE:
{posture}

REQUIREMENTS:
- Generate 5-8 prioritized recommendations
- Include both immediate actions and long-term improvements
- Each recommendation should be specific and actionable
- Estimate effort level (low/medium/high)
- Map to security frameworks where applicable (NIST CSF, ISO 27001)

OUTPUT (JSON):
{{
    "recommendations": [
        {{
            "id": "R1",
            "category": "immediate|short_term|long_term",
            "recommendation": "Specific actionable recommendation",
            "rationale": "Why this is needed based on findings",
            "effort": "low|medium|high",
            "framework_mapping": "NIST CSF ID or ISO control"
        }}
    ]
}}"""

SECTION_PROMPT = """Write a detailed section for a forensic investigation report.

SECTION: {section_title}
SECTION TYPE: {section_key}

RELEVANT DATA:
{data}

REQUIREMENTS:
- Professional forensic writing style
- Include specific details, timestamps, and evidence references
- Use technical terminology appropriate for the audience
- Structure with clear paragraphs and logical flow
- Approximately {word_count} words

OUTPUT: Write the section content directly, formatted in Markdown."""


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE NODES
# ═══════════════════════════════════════════════════════════════════════════════

def aggregate_findings(state: SynthesisState) -> dict:
    """
    Node 1: Aggregate all findings from previous agents.
    """
    run_id = state.get("run_id", str(uuid.uuid4()))
    case_id = state.get("case_id", "")
    
    logger.info(f"[{run_id}] Aggregating findings for synthesis")
    
    # Load case metadata
    case_metadata = {}
    try:
        conn = open_vault(case_id)
        case_row = conn.execute(
            "SELECT case_id, title, description, status, created_at FROM cases WHERE case_id = ? LIMIT 1",
            [case_id]
        ).fetchone()
        if case_row:
            case_metadata = {
                "case_id": case_row[0],
                "title": case_row[1],
                "description": case_row[2],
                "status": case_row[3],
                "created_at": str(case_row[4]) if case_row[4] else None
            }
    except Exception as e:
        logger.warning(f"[{run_id}] Failed to load case metadata: {e}")
    
    return {
        "run_id": run_id,
        "case_metadata": case_metadata,
        "status": "aggregating",
        "reasoning_steps": [{
            "step": "aggregate_findings",
            "description": "Aggregated findings from all agents",
            "timestamp": _now_iso(),
            "details": {
                "has_hypotheses": bool(state.get("hypothesis_results")),
                "has_evidence": bool(state.get("evidence_inventory")),
                "has_modules": bool(state.get("module_results")),
                "has_confidence": bool(state.get("confidence_results"))
            }
        }]
    }


def generate_structure(state: SynthesisState) -> dict:
    """
    Node 2: Generate report structure based on type.
    """
    run_id = state["run_id"]
    report_type_str = state.get("report_type", "technical")
    
    logger.info(f"[{run_id}] Generating report structure")
    
    try:
        report_type = ReportType(report_type_str)
    except ValueError:
        report_type = ReportType.TECHNICAL
    
    template = REPORT_TEMPLATES.get(report_type, REPORT_TEMPLATES[ReportType.TECHNICAL])
    
    structure = {
        "report_type": report_type.value,
        "title": template["title"],
        "sections": template["sections"]
    }
    
    return {
        "report_structure": structure,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "generate_structure",
            "description": f"Generated {report_type.value} report structure with {len(template['sections'])} sections",
            "timestamp": _now_iso()
        }]
    }


async def write_key_findings(state: SynthesisState) -> dict:
    """
    Node 3: Generate key findings using LLM.
    """
    run_id = state["run_id"]
    llm_provider = state.get("llm_provider", "ollama")
    
    logger.info(f"[{run_id}] Generating key findings")
    
    key_findings = []
    
    try:
        llm = get_llm(provider=llm_provider)
        
        prompt = KEY_FINDINGS_PROMPT.format(
            hypotheses=json.dumps(state.get("hypothesis_results", {}), indent=2)[:2000],
            evidence=json.dumps(state.get("evidence_inventory", {}).get("statistics", {}), indent=2),
            modules=json.dumps(state.get("module_results", {}), indent=2)[:2000],
            confidence=json.dumps(state.get("confidence_results", {}), indent=2)[:1000]
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a senior forensic analyst writing an investigation report. Output valid JSON only.",
            temperature=0.3
        )
        
        # Parse response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            key_findings = result.get("findings", [])
            
    except Exception as e:
        logger.warning(f"[{run_id}] LLM key findings generation failed: {e}")
        
        # Generate default findings from available data
        confidence = state.get("confidence_results", {})
        hypothesis_confs = confidence.get("hypothesis_confidences", [])
        
        for i, h in enumerate(hypothesis_confs[:5]):
            key_findings.append({
                "id": f"F{i+1}",
                "finding": h.get("hypothesis_statement", "Finding"),
                "severity": "high" if h.get("overall_score", 0) > 0.7 else "medium",
                "confidence": h.get("overall_score", 0.5)
            })
    
    return {
        "key_findings": key_findings,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "write_key_findings",
            "description": f"Generated {len(key_findings)} key findings",
            "timestamp": _now_iso()
        }]
    }


async def write_executive_summary(state: SynthesisState) -> dict:
    """
    Node 4: Generate executive summary using LLM.
    """
    run_id = state["run_id"]
    llm_provider = state.get("llm_provider", "ollama")
    case_metadata = state.get("case_metadata", {})
    key_findings = state.get("key_findings", [])
    confidence = state.get("confidence_results", {})
    
    logger.info(f"[{run_id}] Generating executive summary")
    
    executive_summary = ""
    
    try:
        llm = get_llm(provider=llm_provider)
        
        # Format findings for prompt
        findings_text = "\n".join([f"- {f.get('finding', '')} (Severity: {f.get('severity', 'unknown')})" 
                                   for f in key_findings[:5]])
        
        # Format impact from module results
        depth_result = state.get("module_results", {}).get("depth", {})
        impact_text = f"""
- Overall Risk Score: {depth_result.get('overall_score', 'N/A')}
- Account Depth: {depth_result.get('account_depth', 'N/A')}
- System Depth: {depth_result.get('system_depth', 'N/A')}
- Data Depth: {depth_result.get('data_depth', 'N/A')}
"""
        
        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            case_info=json.dumps(case_metadata, indent=2),
            findings=findings_text,
            confidence=f"Overall confidence: {confidence.get('overall_case_confidence', 0.5):.1%}",
            impact=impact_text
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a senior forensic analyst writing an executive summary for C-suite leadership.",
            temperature=0.4
        )
        
        executive_summary = response.strip()
        
    except Exception as e:
        logger.warning(f"[{run_id}] LLM executive summary generation failed: {e}")
        
        # Generate default summary
        executive_summary = f"""
## Executive Summary

This report presents the findings of a forensic investigation conducted on case {case_metadata.get('title', 'Unknown')}.

**Key Findings:**
{chr(10).join(['- ' + f.get('finding', '') for f in key_findings[:3]])}

**Confidence Assessment:**
The overall investigation confidence is {confidence.get('overall_confidence_level', 'moderate')}.

**Recommended Actions:**
Immediate containment and remediation actions are recommended based on the findings outlined in this report.
"""
    
    return {
        "executive_summary": executive_summary,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "write_executive_summary",
            "description": f"Generated executive summary ({len(executive_summary.split())} words)",
            "timestamp": _now_iso()
        }]
    }


async def generate_recommendations(state: SynthesisState) -> dict:
    """
    Node 5: Generate recommendations using LLM.
    """
    run_id = state["run_id"]
    llm_provider = state.get("llm_provider", "ollama")
    key_findings = state.get("key_findings", [])
    
    logger.info(f"[{run_id}] Generating recommendations")
    
    recommendations = []
    
    try:
        llm = get_llm(provider=llm_provider)
        
        prompt = RECOMMENDATIONS_PROMPT.format(
            findings=json.dumps(key_findings, indent=2),
            impact=json.dumps(state.get("module_results", {}).get("depth", {}), indent=2)[:1500],
            posture="Current security posture based on investigation findings"
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a cybersecurity consultant providing actionable recommendations. Output valid JSON only.",
            temperature=0.3
        )
        
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            recommendations = result.get("recommendations", [])
            
    except Exception as e:
        logger.warning(f"[{run_id}] LLM recommendations generation failed: {e}")
        
        # Default recommendations
        recommendations = [
            {
                "id": "R1",
                "category": "immediate",
                "recommendation": "Isolate affected systems to prevent further compromise",
                "rationale": "Contains the incident and prevents lateral movement",
                "effort": "low",
                "framework_mapping": "NIST CSF RS.MI-1"
            },
            {
                "id": "R2",
                "category": "immediate",
                "recommendation": "Reset credentials for affected accounts",
                "rationale": "Prevents continued unauthorized access",
                "effort": "medium",
                "framework_mapping": "NIST CSF PR.AC-1"
            },
            {
                "id": "R3",
                "category": "short_term",
                "recommendation": "Implement enhanced monitoring on affected systems",
                "rationale": "Enables detection of similar future incidents",
                "effort": "medium",
                "framework_mapping": "NIST CSF DE.CM-1"
            }
        ]
    
    return {
        "recommendations": recommendations,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "generate_recommendations",
            "description": f"Generated {len(recommendations)} recommendations",
            "timestamp": _now_iso()
        }]
    }


async def compile_sections(state: SynthesisState) -> dict:
    """
    Node 6: Compile all report sections.
    """
    run_id = state["run_id"]
    llm_provider = state.get("llm_provider", "ollama")
    structure = state.get("report_structure", {})
    
    logger.info(f"[{run_id}] Compiling report sections")
    
    section_contents = {}
    
    # Pre-fill sections with available data
    section_contents["executive_summary"] = state.get("executive_summary", "")
    
    # Key findings section
    key_findings = state.get("key_findings", [])
    findings_content = "## Key Findings\n\n"
    for f in key_findings:
        findings_content += f"### {f.get('id', 'F')}: {f.get('finding', '')}\n"
        findings_content += f"- **Severity:** {f.get('severity', 'unknown').title()}\n"
        findings_content += f"- **Confidence:** {f.get('confidence', 0):.0%}\n\n"
    section_contents["key_findings"] = findings_content
    
    # Recommendations section
    recommendations = state.get("recommendations", [])
    recs_content = "## Recommendations\n\n"
    for r in recommendations:
        category = r.get("category", "").replace("_", " ").title()
        recs_content += f"### {r.get('id', 'R')}: {r.get('recommendation', '')}\n"
        recs_content += f"- **Category:** {category}\n"
        recs_content += f"- **Rationale:** {r.get('rationale', '')}\n"
        recs_content += f"- **Effort:** {r.get('effort', 'unknown').title()}\n"
        if r.get("framework_mapping"):
            recs_content += f"- **Framework:** {r.get('framework_mapping')}\n"
        recs_content += "\n"
    section_contents["recommendations"] = recs_content
    
    # Case overview
    case_metadata = state.get("case_metadata", {})
    evidence_inv = state.get("evidence_inventory", {})
    section_contents["case_overview"] = f"""## Case Overview

**Case ID:** {case_metadata.get('case_id', 'N/A')}
**Title:** {case_metadata.get('title', 'N/A')}
**Status:** {case_metadata.get('status', 'N/A')}
**Created:** {case_metadata.get('created_at', 'N/A')}

### Investigation Scope

{case_metadata.get('description', 'No description available.')}

### Evidence Summary

- **Total Evidence Items:** {evidence_inv.get('statistics', {}).get('total_evidence', 0)}
- **Time Range:** {evidence_inv.get('statistics', {}).get('time_range', {}).get('earliest', 'N/A')} to {evidence_inv.get('statistics', {}).get('time_range', {}).get('latest', 'N/A')}
- **Sources:** {', '.join(evidence_inv.get('available_modules', []))}
"""
    
    # Hypothesis analysis
    hypothesis_results = state.get("hypothesis_results", {})
    hypotheses = hypothesis_results.get("hypotheses", [])
    hyp_content = "## Hypothesis Analysis\n\n"
    for h in hypotheses[:5]:
        hyp_content += f"### {h.get('hypothesis_id', '')}: {h.get('statement', '')}\n"
        hyp_content += f"- **Type:** {h.get('hypothesis_type', 'unknown')}\n"
        hyp_content += f"- **Priority:** {h.get('priority', 'N/A')}\n\n"
    section_contents["hypothesis_analysis"] = hyp_content
    
    # Confidence analysis
    confidence_results = state.get("confidence_results", {})
    conf_content = f"""## Confidence Analysis

**Overall Case Confidence:** {confidence_results.get('overall_case_confidence', 0):.1%}
**Confidence Level:** {confidence_results.get('overall_confidence_level', 'moderate').title()}

### Hypothesis Confidence Breakdown

"""
    for hc in confidence_results.get("hypothesis_confidences", [])[:5]:
        conf_content += f"- **{hc.get('hypothesis_id', '')}:** {hc.get('overall_score', 0):.1%} ({hc.get('confidence_level', 'moderate')})\n"
    
    section_contents["confidence_analysis"] = conf_content
    
    # Impact assessment from depth module
    depth_result = state.get("module_results", {}).get("depth", {})
    section_contents["impact_assessment"] = f"""## Impact Assessment

### Blast Radius Analysis

- **Account Depth:** {depth_result.get('account_depth', 'N/A')}
- **System Depth:** {depth_result.get('system_depth', 'N/A')}
- **Data Depth:** {depth_result.get('data_depth', 'N/A')}
- **Control Depth:** {depth_result.get('control_depth', 'N/A')}
- **Overall Score:** {depth_result.get('overall_score', 'N/A')}

{depth_result.get('impact_narrative', 'Impact narrative not available.')}
"""
    
    return {
        "section_contents": section_contents,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "compile_sections",
            "description": f"Compiled {len(section_contents)} report sections",
            "timestamp": _now_iso()
        }]
    }


def add_chain_of_custody(state: SynthesisState) -> dict:
    """
    Node 7: Add chain of custody section.
    """
    run_id = state["run_id"]
    case_id = state.get("case_id", "")
    
    logger.info(f"[{run_id}] Adding chain of custody section")
    
    coc_summary = {}
    coc_content = "## Chain of Custody\n\n"
    
    try:
        conn = open_vault(case_id)
        
        # Get CoC events
        events = conn.execute("""
            SELECT event_id, event_type, actor, description, data_hash, created_at
            FROM chain_of_custody
            WHERE case_id = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, [case_id]).fetchall()
        
        coc_summary = {
            "total_events": len(events),
            "event_types": list(set(e[1] for e in events if e[1])),
            "actors": list(set(e[2] for e in events if e[2]))
        }
        
        coc_content += f"""This section documents the integrity of evidence handling throughout the investigation.

**Total Chain of Custody Events:** {len(events)}
**Unique Actors:** {len(coc_summary['actors'])}

### Recent Events

| Time | Type | Actor | Description |
|------|------|-------|-------------|
"""
        for e in events[:10]:
            coc_content += f"| {e[5]} | {e[1]} | {e[2]} | {e[3][:50]}... |\n"
        
        coc_content += "\n*Full chain of custody log available in the case vault.*\n"
        
    except Exception as e:
        logger.warning(f"[{run_id}] Failed to load CoC: {e}")
        coc_content += "Chain of custody information not available.\n"
    
    section_contents = state.get("section_contents", {})
    section_contents["chain_of_custody"] = coc_content
    
    return {
        "coc_summary": coc_summary,
        "section_contents": section_contents,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "add_chain_of_custody",
            "description": f"Added chain of custody with {coc_summary.get('total_events', 0)} events",
            "timestamp": _now_iso()
        }]
    }


def generate_outputs(state: SynthesisState) -> dict:
    """
    Node 8: Generate final output formats (Markdown, HTML, JSON).
    """
    run_id = state["run_id"]
    structure = state.get("report_structure", {})
    section_contents = state.get("section_contents", {})
    
    logger.info(f"[{run_id}] Generating output formats")
    
    # Build markdown
    markdown_parts = []
    markdown_parts.append(f"# {structure.get('title', 'Forensic Investigation Report')}\n")
    markdown_parts.append(f"**Generated:** {_now_iso()}\n")
    markdown_parts.append(f"**Case ID:** {state.get('case_id', 'N/A')}\n")
    markdown_parts.append(f"**Report ID:** {state.get('run_id', 'N/A')}\n")
    markdown_parts.append("\n---\n\n")
    
    # Add sections in order
    sections_list = structure.get("sections", [])
    for section in sorted(sections_list, key=lambda s: s.get("order", 99)):
        key = section.get("key", "")
        content = section_contents.get(key, "")
        if content:
            markdown_parts.append(content)
            markdown_parts.append("\n\n")
    
    markdown_output = "\n".join(markdown_parts)
    
    # Build simple HTML
    html_output = f"""<!DOCTYPE html>
<html>
<head>
    <title>{structure.get('title', 'Forensic Investigation Report')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1e3a8a; }}
        h2 {{ color: #1e40af; border-bottom: 2px solid #dbeafe; padding-bottom: 8px; }}
        h3 {{ color: #1d4ed8; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f1f5f9; }}
    </style>
</head>
<body>
{_markdown_to_html(markdown_output)}
</body>
</html>"""
    
    # Build report object
    report = GeneratedReport(
        report_type=ReportType(structure.get("report_type", "technical")),
        title=structure.get("title", ""),
        case_id=state.get("case_id", ""),
        run_id=run_id,
        confidence_level=state.get("confidence_results", {}).get("overall_confidence_level", ""),
        markdown=markdown_output,
        html=html_output,
        total_word_count=len(markdown_output.split())
    )
    
    # Build sections
    for section in sections_list:
        key = section.get("key", "")
        content = section_contents.get(key, "")
        report.sections.append(ReportSection(
            section_key=key,
            title=section.get("title", ""),
            content=content,
            order=section.get("order", 0),
            word_count=len(content.split())
        ))
    
    return {
        "report": report.to_dict(),
        "markdown_output": markdown_output,
        "html_output": html_output,
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "generate_outputs",
            "description": f"Generated {report.total_word_count} word report in multiple formats",
            "timestamp": _now_iso()
        }]
    }


def _markdown_to_html(markdown: str) -> str:
    """Simple markdown to HTML conversion."""
    import re
    
    html = markdown
    
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    
    # Paragraphs
    html = re.sub(r'\n\n', r'</p><p>', html)
    html = f"<p>{html}</p>"
    
    return html


def finalize_output(state: SynthesisState) -> dict:
    """
    Node 9: Finalize output and record CoC.
    """
    run_id = state["run_id"]
    case_id = state.get("case_id", "")
    
    logger.info(f"[{run_id}] Finalizing synthesis output")
    
    output = {
        "case_id": case_id,
        "run_id": run_id,
        "generated_at": _now_iso(),
        "report": state.get("report", {}),
        "markdown": state.get("markdown_output", ""),
        "html": state.get("html_output", ""),
        "key_findings": state.get("key_findings", []),
        "recommendations": state.get("recommendations", []),
        "confidence": state.get("confidence_results", {}),
        "coc_summary": state.get("coc_summary", {}),
        "reasoning_trace": state.get("reasoning_steps", [])
    }
    
    # Compute hash
    hash_value = f"sha256:{hashlib.sha256(json.dumps(output, sort_keys=True).encode()).hexdigest()}"
    
    # Record CoC
    try:
        conn = open_vault(case_id)
        coc_event_id = record_coc_event(
            conn=conn,
            case_id=case_id,
            event_type="REPORT_SYNTHESIS_COMPLETED",
            actor="summary_synthesis_agent",
            description=f"Generated {state.get('report', {}).get('report_type', 'technical')} report",
            data_hash=hash_value
        )
    except Exception as e:
        logger.warning(f"[{run_id}] Failed to record CoC: {e}")
        coc_event_id = None
    
    return {
        "output": output,
        "hash_value": hash_value,
        "coc_event_id": coc_event_id,
        "status": "completed"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD LANGGRAPH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def build_synthesis_graph() -> StateGraph:
    """Build the LangGraph state machine for summary synthesis."""
    workflow = StateGraph(SynthesisState)
    
    # Add nodes
    workflow.add_node("aggregate_findings", aggregate_findings)
    workflow.add_node("generate_structure", generate_structure)
    workflow.add_node("write_key_findings", write_key_findings)
    workflow.add_node("write_executive_summary", write_executive_summary)
    workflow.add_node("generate_recommendations", generate_recommendations)
    workflow.add_node("compile_sections", compile_sections)
    workflow.add_node("add_chain_of_custody", add_chain_of_custody)
    workflow.add_node("generate_outputs", generate_outputs)
    workflow.add_node("finalize_output", finalize_output)
    
    # Add edges
    workflow.set_entry_point("aggregate_findings")
    workflow.add_edge("aggregate_findings", "generate_structure")
    workflow.add_edge("generate_structure", "write_key_findings")
    workflow.add_edge("write_key_findings", "write_executive_summary")
    workflow.add_edge("write_executive_summary", "generate_recommendations")
    workflow.add_edge("generate_recommendations", "compile_sections")
    workflow.add_edge("compile_sections", "add_chain_of_custody")
    workflow.add_edge("add_chain_of_custody", "generate_outputs")
    workflow.add_edge("generate_outputs", "finalize_output")
    workflow.add_edge("finalize_output", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY SYNTHESIS AGENT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class SummarySynthesisAgent(BaseAgent):
    """
    Summary Synthesis Agent.
    
    Generates comprehensive forensic reports from aggregated findings.
    """
    
    def __init__(self, llm_provider: str = "ollama"):
        super().__init__(llm_provider=llm_provider)
        self._graph = build_synthesis_graph()
    
    @property
    def agent_id(self) -> str:
        return "summary_synthesis_agent"
    
    @property
    def agent_name(self) -> str:
        return "Summary Synthesis Agent"
    
    @property
    def agent_description(self) -> str:
        return "Generates comprehensive forensic reports from aggregated findings"
    
    @property
    def dependencies(self) -> List[str]:
        return ["confidence_scoring_agent"]
    
    async def execute(self, state: BaseAgentState) -> BaseAgentState:
        """Execute the synthesis pipeline."""
        input_data = state.get("input_data", {})
        
        synthesis_state: SynthesisState = {
            "case_id": input_data.get("case_id", state.get("case_id", "")),
            "run_id": state.get("run_id", str(uuid.uuid4())),
            "report_type": input_data.get("report_type", "technical"),
            "llm_provider": input_data.get("llm_provider", self.llm_provider),
            "hypothesis_results": input_data.get("hypothesis_results", {}),
            "evidence_inventory": input_data.get("evidence_inventory", {}),
            "module_results": input_data.get("module_results", {}),
            "confidence_results": input_data.get("confidence_results", {})
        }
        
        result = await self._graph.ainvoke(synthesis_state)
        
        state["output_data"] = result.get("output", {})
        
        return state
    
    async def synthesize(
        self,
        case_id: str,
        report_type: str = "technical",
        hypothesis_results: Dict[str, Any] = None,
        evidence_inventory: Dict[str, Any] = None,
        module_results: Dict[str, Dict[str, Any]] = None,
        confidence_results: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to synthesize a report.
        """
        state: BaseAgentState = {
            "run_id": str(uuid.uuid4()),
            "case_id": case_id,
            "input_data": {
                "case_id": case_id,
                "report_type": report_type,
                "hypothesis_results": hypothesis_results or {},
                "evidence_inventory": evidence_inventory or {},
                "module_results": module_results or {},
                "confidence_results": confidence_results or {}
            }
        }
        
        result = await self.run(state)
        return result.get("output_data", {})


# Register with global registry
registry.register(SummarySynthesisAgent())
