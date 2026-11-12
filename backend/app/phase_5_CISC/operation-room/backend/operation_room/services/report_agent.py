"""
Report Writer Agent — LangGraph Pipeline.

5-node pipeline:
  1. gather_context     — Collect all module summaries + chart data
  2. generate_sections  — LLM generates each report section
  3. assemble_report    — Merge sections into ordered markdown
  4. generate_remediation — LLM: remediation + executive summary
  5. store_and_audit    — Persist draft + hash + CoC

Reuses: llm_provider, hashing, audit_service, studio_service.
"""

import json
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import StateGraph, END

from operation_room.database import open_vault
from operation_room.utils.hashing import hash_records
from operation_room.services.audit_service import record_coc_event

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Report Templates ──────────────────────────────────────
TEMPLATES = {
    "technical": {
        "title": "Technical Incident Report",
        "sections": [
            {"key": "exec_summary",    "title": "Executive Summary",           "sort_order": 1},
            {"key": "case_overview",   "title": "Case Overview & Scope",       "sort_order": 2},
            {"key": "timeline",        "title": "Event Timeline Analysis",     "sort_order": 3},
            {"key": "anomalies",       "title": "Anomaly Detection Findings",  "sort_order": 4},
            {"key": "attack_chain",    "title": "Attack Chain & Correlation",  "sort_order": 5},
            {"key": "data_access",     "title": "CRUD & Data Access Analysis", "sort_order": 6},
            {"key": "network",         "title": "Network & Exfiltration",      "sort_order": 7},
            {"key": "depth_impact",    "title": "Depth & Impact Assessment",   "sort_order": 8},
            {"key": "remediation",     "title": "Remediation & Recommendations", "sort_order": 9},
            {"key": "chain_of_custody","title": "Chain of Custody & Integrity","sort_order": 10},
        ],
    },
    "executive": {
        "title": "Executive Incident Summary",
        "sections": [
            {"key": "exec_summary",    "title": "Executive Summary",           "sort_order": 1},
            {"key": "impact",          "title": "Business Impact",             "sort_order": 2},
            {"key": "key_findings",    "title": "Key Findings",               "sort_order": 3},
            {"key": "remediation",     "title": "Recommended Actions",        "sort_order": 4},
        ],
    },
    "regulatory": {
        "title": "Regulatory Compliance Report",
        "sections": [
            {"key": "exec_summary",    "title": "Summary of Incident",        "sort_order": 1},
            {"key": "data_access",     "title": "Personal Data Affected",     "sort_order": 2},
            {"key": "timeline",        "title": "Incident Timeline",          "sort_order": 3},
            {"key": "depth_impact",    "title": "Impact Assessment",          "sort_order": 4},
            {"key": "remediation",     "title": "Containment & Remediation",  "sort_order": 5},
            {"key": "chain_of_custody","title": "Evidence Integrity",         "sort_order": 6},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
# State Schema
# ═══════════════════════════════════════════════════════════════

class ReportState(TypedDict, total=False):
    case_id: str
    report_id: str
    template: str
    llm_provider: str
    chart_ids: list[str]

    # Gathered context
    case_meta: dict
    module_summaries: dict
    section_specs: list[dict]

    # Generated content
    sections: list[dict]
    full_markdown: str
    remediation: list[dict]
    executive_summary: str

    hash_value: str
    status: str
    error: str


# ═══════════════════════════════════════════════════════════════
# Node 1: Gather Context
# ═══════════════════════════════════════════════════════════════

def gather_context(state: ReportState) -> dict:
    """Collect summaries from all modules."""
    case_id = state["case_id"]
    report_id = state.get("report_id", str(uuid.uuid4()))
    template_key = state.get("template", "technical")
    template = TEMPLATES.get(template_key, TEMPLATES["technical"])
    conn = open_vault(case_id)

    try:
        summaries = {}

        # Case metadata
        case_row = conn.execute("""
            SELECT case_id, title, description, status, created_at
            FROM cases WHERE case_id = ? LIMIT 1
        """, [case_id]).fetchone()
        case_meta = {}
        if case_row:
            case_meta = {"case_id": case_row[0], "title": case_row[1],
                         "description": case_row[2], "status": case_row[3],
                         "created_at": str(case_row[4]) if case_row[4] else ""}

        # Timeline summary
        tl = conn.execute("SELECT COUNT(*), MIN(normalised_ts), MAX(normalised_ts) FROM unified_timeline WHERE case_id=?", [case_id]).fetchone()
        summaries["timeline"] = {"total_events": tl[0] or 0, "first_event": str(tl[1] or ""), "last_event": str(tl[2] or "")}

        # Anomaly summary
        try:
            anom = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END), AVG(anomaly_score)
                FROM anomaly_scores WHERE run_id = (SELECT run_id FROM anomaly_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
            """, [case_id]).fetchone()
            summaries["anomaly"] = {"total_scored": anom[0] or 0, "anomalies_found": int(anom[1] or 0), "avg_score": round(float(anom[2] or 0), 3)}
        except Exception:
            summaries["anomaly"] = {"total_scored": 0}

        # Correlation summary
        try:
            corr_run = conn.execute("SELECT run_id, total_nodes, total_edges FROM correlation_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1", [case_id]).fetchone()
            if corr_run:
                narr = conn.execute("SELECT narrative_text, mitre_tactics, recommendations FROM rca_narratives WHERE run_id=? LIMIT 1", [corr_run[0]]).fetchone()
                summaries["correlation"] = {
                    "total_nodes": corr_run[1], "total_edges": corr_run[2],
                    "narrative": (narr[0] or "")[:2000] if narr else "",
                    "mitre_tactics": json.loads(narr[1]) if narr and narr[1] else [],
                    "recommendations": json.loads(narr[2]) if narr and narr[2] else [],
                }
        except Exception:
            summaries["correlation"] = {}

        # CRUD summary
        try:
            crud = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_high_risk THEN 1 ELSE 0 END), SUM(volume_bytes)
                FROM crud_events WHERE run_id = (SELECT run_id FROM crud_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1)
            """, [case_id]).fetchone()
            summaries["crud"] = {"total_events": crud[0] or 0, "high_risk": int(crud[1] or 0), "total_bytes": int(crud[2] or 0)}
        except Exception:
            summaries["crud"] = {}

        # Network summary
        try:
            net = conn.execute("""
                SELECT total_flows, suspicious_count, exfil_candidates, total_bytes_out
                FROM network_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1
            """, [case_id]).fetchone()
            summaries["network"] = {"total_flows": net[0] or 0, "suspicious": net[1] or 0, "exfil_candidates": net[2] or 0, "bytes_out": int(net[3] or 0)} if net else {}
        except Exception:
            summaries["network"] = {}

        # Depth summary
        try:
            depth = conn.execute("""
                SELECT account_depth, system_depth, data_depth, control_depth, overall_severity, severity_label
                FROM depth_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1
            """, [case_id]).fetchone()
            if depth:
                summaries["depth"] = {
                    "account": float(depth[0] or 0), "system": float(depth[1] or 0),
                    "data": float(depth[2] or 0), "control": float(depth[3] or 0),
                    "overall": float(depth[4] or 0), "label": depth[5],
                }
        except Exception:
            summaries["depth"] = {}

        # Impact narrative
        try:
            imp = conn.execute("""
                SELECT narrative_text, executive_summary, remediation
                FROM impact_narratives WHERE run_id = (SELECT run_id FROM depth_runs WHERE case_id=? AND status='COMPLETED' ORDER BY completed_at DESC LIMIT 1) LIMIT 1
            """, [case_id]).fetchone()
            if imp:
                summaries["impact_narrative"] = (imp[0] or "")[:2000]
                summaries["impact_exec"] = imp[1] or ""
                summaries["impact_remediation"] = json.loads(imp[2]) if imp[2] else []
        except Exception:
            pass

        # CoC entries
        try:
            coc = conn.execute("""
                SELECT coc_event_id, actor, action, target_artefact, hash_after, event_ts
                FROM chain_of_custody WHERE case_id=? ORDER BY event_ts DESC LIMIT 20
            """, [case_id]).fetchall()
            summaries["chain_of_custody"] = [{"id": r[0], "actor": r[1], "action": r[2],
                                               "target": r[3], "hash": r[4], "ts": str(r[5])} for r in coc]
        except Exception:
            summaries["chain_of_custody"] = []

        # Register report draft
        conn.execute("""
            INSERT INTO report_drafts (report_id, case_id, template, title, status, llm_provider, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'GENERATING', ?, ?, ?)
        """, [report_id, case_id, template_key, template["title"],
              state.get("llm_provider", "ollama"), _now_iso(), _now_iso()])

        logger.info(f"[ReportAgent] Gathered context: {len(summaries)} module summaries")
        return {
            "report_id": report_id,
            "case_meta": case_meta,
            "module_summaries": summaries,
            "section_specs": template["sections"],
            "status": "context_gathered",
        }
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Node 2: Generate Sections (LLM)
# ═══════════════════════════════════════════════════════════════

def _build_section_prompt(section_key: str, section_title: str,
                          case_meta: dict, summaries: dict) -> str:
    """Build prompt for a specific report section."""
    context = f"Case: {case_meta.get('title', 'N/A')} ({case_meta.get('case_id', 'N/A')})\n"

    if section_key == "exec_summary":
        context += f"""
Timeline: {summaries.get('timeline', {}).get('total_events', 0)} events from {summaries.get('timeline', {}).get('first_event', '?')} to {summaries.get('timeline', {}).get('last_event', '?')}
Anomalies: {summaries.get('anomaly', {}).get('anomalies_found', 0)} detected
Correlation: {summaries.get('correlation', {}).get('total_nodes', 0)} entities, MITRE: {', '.join(summaries.get('correlation', {}).get('mitre_tactics', [])[:5])}
CRUD: {summaries.get('crud', {}).get('total_events', 0)} operations, {summaries.get('crud', {}).get('high_risk', 0)} high-risk
Network: {summaries.get('network', {}).get('total_flows', 0)} flows, {summaries.get('network', {}).get('exfil_candidates', 0)} exfil candidates
Depth: {summaries.get('depth', {}).get('overall', 0)}/10 severity ({summaries.get('depth', {}).get('label', '?')})

Write a concise 3-4 paragraph executive summary covering: what happened, how deep the penetration was, what data was at risk, and key recommendations."""

    elif section_key == "timeline":
        context += f"""
Total events: {summaries.get('timeline', {}).get('total_events', 0)}
Time range: {summaries.get('timeline', {}).get('first_event', '?')} to {summaries.get('timeline', {}).get('last_event', '?')}

Describe the event timeline sequence, noting key inflection points and phases of the attack."""

    elif section_key == "anomalies":
        context += f"""
Scored events: {summaries.get('anomaly', {}).get('total_scored', 0)}
Anomalies found: {summaries.get('anomaly', {}).get('anomalies_found', 0)}
Average score: {summaries.get('anomaly', {}).get('avg_score', 0)}

Summarise what the anomaly detection found: unusual patterns, off-hours activity, statistical outliers."""

    elif section_key in ("attack_chain", "key_findings"):
        narr = summaries.get("correlation", {}).get("narrative", "")
        context += f"""
Entities: {summaries.get('correlation', {}).get('total_nodes', 0)}
Connections: {summaries.get('correlation', {}).get('total_edges', 0)}
MITRE Tactics: {', '.join(summaries.get('correlation', {}).get('mitre_tactics', []))}
Correlation narrative excerpt: {narr[:1500]}

Describe the attack chain, how entities are linked, and the critical path from entry to impact."""

    elif section_key == "data_access":
        context += f"""
CRUD events: {summaries.get('crud', {}).get('total_events', 0)}
High-risk operations: {summaries.get('crud', {}).get('high_risk', 0)}
Total data volume: {summaries.get('crud', {}).get('total_bytes', 0)} bytes

Analyse data access patterns: what was read/modified/deleted, sensitivity levels, which actors accessed what."""

    elif section_key == "network":
        context += f"""
Flows: {summaries.get('network', {}).get('total_flows', 0)}
Suspicious: {summaries.get('network', {}).get('suspicious', 0)}
Exfiltration candidates: {summaries.get('network', {}).get('exfil_candidates', 0)}
Bytes outbound: {summaries.get('network', {}).get('bytes_out', 0)}

Describe network activity: suspicious flows, external destinations, potential data exfiltration."""

    elif section_key in ("depth_impact", "impact"):
        context += f"""
Account depth: {summaries.get('depth', {}).get('account', 0)}/10
System depth: {summaries.get('depth', {}).get('system', 0)}/10
Data depth: {summaries.get('depth', {}).get('data', 0)}/10
Control depth: {summaries.get('depth', {}).get('control', 0)}/10
Overall: {summaries.get('depth', {}).get('overall', 0)}/10 ({summaries.get('depth', {}).get('label', '?')})
Impact narrative: {summaries.get('impact_narrative', '')[:1000]}

Summarise the depth assessment across all four dimensions and overall business impact."""

    elif section_key == "remediation":
        recs = summaries.get("correlation", {}).get("recommendations", [])
        imp_recs = summaries.get("impact_remediation", [])
        context += f"""
Correlation recommendations: {json.dumps(recs[:5])}
Impact remediation: {json.dumps(imp_recs[:5]) if imp_recs else '[]'}

List prioritised remediation actions: immediate containment, short-term fixes, long-term hardening."""

    elif section_key == "chain_of_custody":
        coc = summaries.get("chain_of_custody", [])
        context += f"""
Chain-of-custody entries: {len(coc)}
Recent entries: {json.dumps(coc[:10])}

Summarise forensic integrity: what was hashed, how evidence was preserved, audit trail entries."""

    elif section_key == "case_overview":
        context += f"""
Description: {case_meta.get('description', 'N/A')}
Status: {case_meta.get('status', 'N/A')}
Created: {case_meta.get('created_at', 'N/A')}

Describe the case scope: what systems were investigated, time range, log sources ingested."""

    return context


def generate_sections(state: ReportState) -> dict:
    """Call LLM to generate each report section."""
    section_specs = state.get("section_specs", [])
    case_meta = state.get("case_meta", {})
    summaries = state.get("module_summaries", {})
    llm_provider = state.get("llm_provider", "ollama")

    SYSTEM_MSG = """You are a senior digital forensics report writer. Generate the requested report section using the provided data.
Write in professional, third-person tone. Use markdown formatting. Be specific with numbers and evidence.
Keep sections concise but comprehensive. Reference specific entities, timestamps and metrics when available."""

    sections = []
    for spec in section_specs:
        prompt = _build_section_prompt(spec["key"], spec["title"], case_meta, summaries)
        content = ""
        try:
            from operation_room.services.llm_provider import get_llm
            llm = get_llm(llm_provider)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        content = pool.submit(asyncio.run,
                            llm.generate(f"Generate the '{spec['title']}' section:\n\n{prompt}",
                                         system=SYSTEM_MSG, temperature=0.3, max_tokens=1500)).result()
                else:
                    content = loop.run_until_complete(
                        llm.generate(f"Generate the '{spec['title']}' section:\n\n{prompt}",
                                     system=SYSTEM_MSG, temperature=0.3, max_tokens=1500))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                content = loop.run_until_complete(
                    llm.generate(f"Generate the '{spec['title']}' section:\n\n{prompt}",
                                 system=SYSTEM_MSG, temperature=0.3, max_tokens=1500))
                loop.close()
        except Exception as e:
            logger.error(f"[ReportAgent] LLM failed for {spec['key']}: {e}")
            content = _fallback_section(spec["key"], spec["title"], summaries)

        if not content or "[LLM Error]" in content:
            content = _fallback_section(spec["key"], spec["title"], summaries)

        sections.append({
            "section_key": spec["key"],
            "section_title": spec["title"],
            "content": content,
            "sort_order": spec["sort_order"],
            "is_ai_generated": True,
        })

    logger.info(f"[ReportAgent] Generated {len(sections)} sections")
    return {"sections": sections, "status": "sections_generated"}


def _fallback_section(key, title, summaries):
    """Generate section without LLM."""
    lines = [f"## {title}\n"]
    if key == "exec_summary":
        depth = summaries.get("depth", {})
        lines.append(f"This incident achieved an overall severity of **{depth.get('overall', 0)}/10** "
                     f"({depth.get('label', 'N/A')}). A total of "
                     f"{summaries.get('timeline', {}).get('total_events', 0)} events were analysed, "
                     f"with {summaries.get('anomaly', {}).get('anomalies_found', 0)} anomalies detected.")
    elif key == "timeline":
        tl = summaries.get("timeline", {})
        lines.append(f"**{tl.get('total_events', 0)}** events analysed from "
                     f"{tl.get('first_event', '?')} to {tl.get('last_event', '?')}.")
    elif key == "data_access":
        crud = summaries.get("crud", {})
        lines.append(f"**{crud.get('total_events', 0)}** CRUD operations, "
                     f"**{crud.get('high_risk', 0)}** flagged as high risk.")
    elif key == "network":
        net = summaries.get("network", {})
        lines.append(f"**{net.get('total_flows', 0)}** network flows analysed, "
                     f"**{net.get('exfil_candidates', 0)}** exfiltration candidates identified.")
    elif key == "remediation":
        recs = summaries.get("correlation", {}).get("recommendations", [])
        for r in recs[:5]:
            lines.append(f"- {r}")
    elif key == "chain_of_custody":
        coc = summaries.get("chain_of_custody", [])
        lines.append(f"**{len(coc)}** chain-of-custody entries recorded.")
    else:
        lines.append(f"*Section data available — run with LLM for AI-generated content.*")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Node 3: Assemble Report
# ═══════════════════════════════════════════════════════════════

def assemble_report(state: ReportState) -> dict:
    """Merge sections into ordered markdown document."""
    sections = sorted(state.get("sections", []), key=lambda s: s.get("sort_order", 0))
    template_key = state.get("template", "technical")
    template = TEMPLATES.get(template_key, TEMPLATES["technical"])
    case_meta = state.get("case_meta", {})

    lines = [
        f"# {template['title']}",
        f"\n**Case:** {case_meta.get('title', 'N/A')} ({case_meta.get('case_id', 'N/A')})",
        f"**Generated:** {_now_iso()[:19]}",
        f"**Template:** {template_key.title()}",
        f"**Classification:** CONFIDENTIAL\n",
        "---\n",
    ]

    for s in sections:
        lines.append(f"## {s['section_title']}\n")
        lines.append(s.get("content", "*No content*"))
        lines.append("\n---\n")

    full_md = "\n".join(lines)
    logger.info(f"[ReportAgent] Assembled report: {len(full_md)} chars, {len(sections)} sections")
    return {"full_markdown": full_md, "status": "assembled"}


# ═══════════════════════════════════════════════════════════════
# Node 4: Generate Remediation Summary
# ═══════════════════════════════════════════════════════════════

def generate_remediation(state: ReportState) -> dict:
    """Build executive summary and remediation from existing data."""
    summaries = state.get("module_summaries", {})
    depth = summaries.get("depth", {})

    exec_summary = (f"Overall severity: {depth.get('overall', 0)}/10 ({depth.get('label', 'N/A')}). "
                    f"Account depth {depth.get('account', 0)}/10, System depth {depth.get('system', 0)}/10, "
                    f"Data depth {depth.get('data', 0)}/10, Control depth {depth.get('control', 0)}/10. "
                    f"{summaries.get('anomaly', {}).get('anomalies_found', 0)} anomalies detected across "
                    f"{summaries.get('timeline', {}).get('total_events', 0)} events.")

    recs = summaries.get("correlation", {}).get("recommendations", [])
    imp_recs = summaries.get("impact_remediation", [])
    remediation = []
    for r in (imp_recs if imp_recs else []):
        if isinstance(r, dict):
            remediation.append(r)
        else:
            remediation.append({"priority": "MEDIUM", "action": str(r)})
    for r in recs:
        remediation.append({"priority": "MEDIUM", "action": str(r)})

    return {"executive_summary": exec_summary, "remediation": remediation[:10], "status": "remediation_generated"}


# ═══════════════════════════════════════════════════════════════
# Node 5: Store & Audit
# ═══════════════════════════════════════════════════════════════

def store_and_audit(state: ReportState) -> dict:
    case_id = state["case_id"]
    report_id = state["report_id"]
    conn = open_vault(case_id)
    try:
        now = _now_iso()

        # Store sections
        conn.execute("DELETE FROM report_sections WHERE report_id=?", [report_id])
        for s in state.get("sections", []):
            sec_hash = hash_records([{"key": s["section_key"], "content": (s.get("content", ""))[:200]}])
            conn.execute("""
                INSERT INTO report_sections (section_id, report_id, case_id, section_key, section_title,
                    content, chart_ids, sort_order, is_ai_generated, hash_value, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [str(uuid.uuid4()), report_id, case_id, s["section_key"], s["section_title"],
                  s.get("content", ""), json.dumps(s.get("chart_ids", [])),
                  s.get("sort_order", 0), s.get("is_ai_generated", False), sec_hash, now])

        # Hash full report
        report_hash = hash_records([{"report_id": report_id, "markdown": (state.get("full_markdown", ""))[:500]}])

        # Update draft
        conn.execute("""
            UPDATE report_drafts
            SET status='COMPLETED', sections_json=?, metadata_json=?, hash_value=?, updated_at=?
            WHERE report_id=?
        """, [
            json.dumps([s["section_key"] for s in state.get("sections", [])]),
            json.dumps({"executive_summary": state.get("executive_summary", ""),
                        "template": state.get("template", "technical")}),
            report_hash, now, report_id,
        ])

        # CoC
        coc_id = record_coc_event(
            case_id=case_id, actor="report_agent",
            action="REPORT_GENERATED",
            target_artefact=f"report:{report_id}",
            justification="AI-generated forensic report",
            hash_after=report_hash,
            details={"report_id": report_id, "sections": len(state.get("sections", [])),
                     "template": state.get("template", "technical")},
        )

        logger.info(f"[ReportAgent] Stored report {report_id}, CoC={coc_id}")
        return {"hash_value": report_hash, "status": "completed"}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Build LangGraph
# ═══════════════════════════════════════════════════════════════

def build_report_graph() -> StateGraph:
    graph = StateGraph(ReportState)
    graph.add_node("gather_context", gather_context)
    graph.add_node("generate_sections", generate_sections)
    graph.add_node("assemble_report", assemble_report)
    graph.add_node("generate_remediation", generate_remediation)
    graph.add_node("store_and_audit", store_and_audit)

    graph.set_entry_point("gather_context")
    graph.add_edge("gather_context", "generate_sections")
    graph.add_edge("generate_sections", "assemble_report")
    graph.add_edge("assemble_report", "generate_remediation")
    graph.add_edge("generate_remediation", "store_and_audit")
    graph.add_edge("store_and_audit", END)

    return graph.compile()


_compiled = None


def get_report_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_report_graph()
    return _compiled


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def generate_report(case_id: str, template: str = "technical",
                    llm_provider: str = "ollama", chart_ids: list = None) -> dict:
    report_id = str(uuid.uuid4())
    initial: ReportState = {
        "case_id": case_id, "report_id": report_id,
        "template": template, "llm_provider": llm_provider,
        "chart_ids": chart_ids or [],
    }
    graph = get_report_graph()
    try:
        result = graph.invoke(initial)
        return {
            "report_id": report_id, "status": "completed",
            "template": template,
            "sections_count": len(result.get("sections", [])),
            "executive_summary": result.get("executive_summary", ""),
            "markdown_preview": (result.get("full_markdown", ""))[:1000],
        }
    except Exception as e:
        logger.error(f"[ReportAgent] Pipeline failed: {e}", exc_info=True)
        try:
            conn = open_vault(case_id)
            conn.execute("UPDATE report_drafts SET status='FAILED', updated_at=? WHERE report_id=?", [_now_iso(), report_id])
            conn.close()
        except Exception:
            pass
        return {"error": str(e), "report_id": report_id, "status": "FAILED"}


def get_report(case_id: str, report_id: str = None) -> dict:
    conn = open_vault(case_id)
    try:
        if not report_id:
            latest = conn.execute("SELECT report_id FROM report_drafts WHERE case_id=? AND status='COMPLETED' ORDER BY updated_at DESC LIMIT 1", [case_id]).fetchone()
            report_id = latest[0] if latest else None
        if not report_id:
            return {"error": "No completed reports"}

        draft = conn.execute("""
            SELECT report_id, template, title, status, metadata_json, hash_value, created_at, updated_at
            FROM report_drafts WHERE report_id=?
        """, [report_id]).fetchone()
        if not draft:
            return {"error": "Report not found"}

        sections = conn.execute("""
            SELECT section_id, section_key, section_title, content, chart_ids, sort_order, is_ai_generated
            FROM report_sections WHERE report_id=? ORDER BY sort_order ASC
        """, [report_id]).fetchall()

        sec_list = []
        for s in sections:
            sec_list.append({
                "section_id": s[0], "section_key": s[1], "section_title": s[2],
                "content": s[3], "chart_ids": json.loads(s[4]) if s[4] else [],
                "sort_order": s[5], "is_ai_generated": bool(s[6]),
            })

        meta = {}
        try:
            meta = json.loads(draft[4]) if draft[4] else {}
        except Exception:
            pass

        return {
            "report_id": draft[0], "template": draft[1], "title": draft[2],
            "status": draft[3], "metadata": meta, "hash_value": draft[5],
            "created_at": str(draft[6]) if draft[6] else None,
            "updated_at": str(draft[7]) if draft[7] else None,
            "sections": sec_list,
        }
    finally:
        conn.close()


def get_report_markdown(case_id: str, report_id: str = None) -> str:
    """Reconstruct full markdown from sections."""
    report = get_report(case_id, report_id)
    if report.get("error"):
        return f"# Error\n\n{report['error']}"

    lines = [
        f"# {report.get('title', 'Forensic Report')}",
        f"\n**Case:** {case_id}",
        f"**Generated:** {report.get('created_at', '')}",
        f"**Template:** {report.get('template', 'technical').title()}",
        f"**Hash:** `{report.get('hash_value', '')}`\n",
        "---\n",
    ]
    for s in report.get("sections", []):
        lines.append(f"## {s['section_title']}\n")
        lines.append(s.get("content", "*No content*"))
        lines.append("\n---\n")

    return "\n".join(lines)


def list_reports(case_id: str) -> list[dict]:
    conn = open_vault(case_id)
    try:
        rows = conn.execute("""
            SELECT report_id, template, title, status, hash_value, created_at, updated_at
            FROM report_drafts WHERE case_id=? ORDER BY updated_at DESC
        """, [case_id]).fetchall()
        return [{"report_id": r[0], "template": r[1], "title": r[2], "status": r[3],
                 "hash_value": r[4], "created_at": str(r[5]) if r[5] else None,
                 "updated_at": str(r[6]) if r[6] else None} for r in rows]
    finally:
        conn.close()


def update_section(case_id: str, report_id: str, section_key: str, content: str) -> dict:
    """Manually update a section's content."""
    conn = open_vault(case_id)
    try:
        sec = conn.execute("SELECT section_id FROM report_sections WHERE report_id=? AND section_key=?",
                           [report_id, section_key]).fetchone()
        if not sec:
            return {"error": "Section not found"}

        new_hash = hash_records([{"key": section_key, "content": content[:200]}])
        conn.execute("""
            UPDATE report_sections SET content=?, is_ai_generated=FALSE, hash_value=?, created_at=?
            WHERE section_id=?
        """, [content, new_hash, _now_iso(), sec[0]])

        record_coc_event(case_id=case_id, actor="investigator", action="SECTION_EDITED",
                         target_artefact=f"section:{sec[0]}", justification=f"Manual edit to {section_key}",
                         hash_after=new_hash)

        return {"section_key": section_key, "updated": True, "hash_value": new_hash}
    finally:
        conn.close()


def list_templates() -> list[dict]:
    return [{"id": k, "title": v["title"], "sections": len(v["sections"])} for k, v in TEMPLATES.items()]
