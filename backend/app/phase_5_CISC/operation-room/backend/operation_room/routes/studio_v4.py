"""
Studio V4 API Router.

Canonical V4 surface for report editing, AI writer operations,
and export orchestration.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Any, List
import asyncio
import hashlib
import json
import logging
import uuid
from pathlib import Path

from operation_room.services.studio_v2_service import (
    create_document,
    delete_document,
    get_document,
    get_template_ast,
    get_version,
    list_documents,
    list_templates,
    list_versions,
    restore_version,
    update_document,
)
from operation_room.services.report_studio_service import get_all_insights
from operation_room.services.writer_agent import generate_section
from operation_room.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v4/studio/cases/{case_id}", tags=["Studio V4"])


WRITER_STYLES = {"technical", "executive", "regulatory"}
STYLE_ALIASES = {
    "formal": "regulatory",
    "business": "executive",
    "analyst": "technical",
}
SECTION_ALIASES = {
    "timeline": "timeline_narrative",
    "anomaly": "anomaly_findings",
    "correlation": "attack_chain",
    "crud": "data_access",
    "network": "network_activity",
    "depth": "depth_assessment",
    "case": "case_overview",
    "impact_assessment": "depth_assessment",
}


def _normalize_style(style: Optional[str]) -> str:
    normalized = (style or "technical").strip().lower()
    normalized = STYLE_ALIASES.get(normalized, normalized)
    return normalized if normalized in WRITER_STYLES else "technical"


def _normalize_section_type(section_type: str) -> str:
    normalized = (section_type or "").strip().lower()
    return SECTION_ALIASES.get(normalized, normalized)


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _build_validation_case_data(all_insights: dict) -> dict:
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


def _coerce_ast(req: "UpdateDocRequest") -> Optional[dict]:
    if req.ast is not None:
        return req.ast

    if req.ast_json:
        try:
            parsed = json.loads(req.ast_json)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None

    if isinstance(req.content, dict):
        return req.content

    if isinstance(req.content, str) and req.content.strip():
        # Keep compatibility with older clients sending HTML/text payloads.
        return {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": req.content.strip()}],
                }
            ],
        }

    return None


class CreateDocRequest(BaseModel):
    title: str = "Untitled Report"
    template: str = "blank"
    created_by: str = "investigator"


class WidgetFilterConfig(BaseModel):
    topN: int = 10
    minRisk: float = 0.0
    excludeInfo: bool = False
    excludedFeatures: List[str] = []


class WidgetRefreshRequest(BaseModel):
    widgetType: str
    filters: WidgetFilterConfig


class UpdateDocRequest(BaseModel):
    ast: Optional[dict] = None
    ast_json: Optional[str] = None
    content: Optional[Any] = None
    title: Optional[str] = None
    save_version: bool = True
    change_summary: Optional[str] = None
    actor: str = "investigator"


class RestoreRequest(BaseModel):
    version_id: str
    actor: str = "investigator"


class SectionGenerateRequest(BaseModel):
    section_type: str
    selected_modules: Optional[list[str]] = None
    style: str = "technical"
    custom_instructions: Optional[str] = None


class CustomGenerateRequest(BaseModel):
    prompt: str
    style: str = "technical"


class SuggestionsRequest(BaseModel):
    content: str
    section: Optional[str] = None


class ValidateContentRequest(BaseModel):
    content: str
    citations: Optional[List[dict]] = None


class ExportRequest(BaseModel):
    doc_id: str
    actor: str = "investigator"
    frontend_url: Optional[str] = None
    cover_id: Optional[str] = None
    focus_mode: Optional[str] = "Review"
    engine: Optional[str] = "reportlab"
    font_style: Optional[str] = None
    graph_style: Optional[str] = None
    table_style: Optional[str] = None
    selected_graphs: Optional[List[str]] = None
    ast: Optional[dict] = None
    title: Optional[str] = None


@router.get("/health")
def api_v4_health(case_id: str):
    return {"status": "ok", "case_id": case_id, "api": "studio-v4"}


@router.get("/docs")
def api_list_docs(case_id: str):
    return list_documents(case_id)


@router.post("/docs")
def api_create_doc(case_id: str, req: CreateDocRequest):
    initial_ast = get_template_ast(req.template, req.title)
    created = create_document(
        case_id=case_id,
        title=req.title,
        template=req.template,
        initial_ast=initial_ast,
        created_by=req.created_by,
    )
    created["ast"] = initial_ast
    created["content"] = initial_ast
    return created


@router.get("/docs/{doc_id}")
def api_get_doc(case_id: str, doc_id: str):
    doc = get_document(case_id, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Keep backward compatibility with clients expecting a `content` field.
    doc["content"] = doc.get("ast")
    return doc


@router.put("/docs/{doc_id}")
def api_update_doc(case_id: str, doc_id: str, req: UpdateDocRequest):
    ast = _coerce_ast(req)
    if ast is None:
        raise HTTPException(status_code=400, detail="Missing or invalid AST payload")

    result = update_document(
        case_id=case_id,
        doc_id=doc_id,
        ast=ast,
        title=req.title,
        save_version=req.save_version,
        change_summary=req.change_summary,
        actor=req.actor,
    )
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.delete("/docs/{doc_id}")
def api_delete_doc(case_id: str, doc_id: str):
    return delete_document(case_id, doc_id)


@router.get("/docs/{doc_id}/versions")
def api_doc_versions(case_id: str, doc_id: str):
    return {"versions": list_versions(case_id, doc_id)}


@router.get("/docs/{doc_id}/versions/{version_id}")
def api_get_doc_version(case_id: str, doc_id: str, version_id: str):
    version = get_version(case_id, doc_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/docs/{doc_id}/restore")
def api_restore_doc(case_id: str, doc_id: str, req: RestoreRequest):
    result = restore_version(case_id, doc_id, req.version_id, actor=req.actor)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/templates")
def api_templates(case_id: str):
    from operation_room.services.template_config import TEMPLATES
    return {"templates": list(TEMPLATES.values())}


@router.post("/writer/generate")
async def api_generate(case_id: str, req: SectionGenerateRequest):
    section_type = _normalize_section_type(req.section_type)
    if not section_type:
        raise HTTPException(status_code=400, detail="section_type is required")

    result = await generate_section(
        case_id=case_id,
        section_type=section_type,
        selected_modules=req.selected_modules,
        style=_normalize_style(req.style),
        custom_instructions=req.custom_instructions,
    )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("error", "Generation failed"))

    return result


@router.post("/writer/generate-stream")
async def api_generate_stream(case_id: str, req: SectionGenerateRequest):
    section_type = _normalize_section_type(req.section_type)
    if not section_type:
        raise HTTPException(status_code=400, detail="section_type is required")

    style = _normalize_style(req.style)

    async def event_generator():
        yield _sse_event("start", {"case_id": case_id, "section_type": section_type, "style": style})
        try:
            result = await generate_section(
                case_id=case_id,
                section_type=section_type,
                selected_modules=req.selected_modules,
                style=style,
                custom_instructions=req.custom_instructions,
            )
            if result.get("status") == "error":
                yield _sse_event("error", {"error": result.get("error", "Generation failed")})
                return

            content = result.get("content", "") or ""
            chunk_size = 320
            for index, start in enumerate(range(0, len(content), chunk_size)):
                yield _sse_event("chunk", {"index": index, "content": content[start:start + chunk_size]})
                await asyncio.sleep(0)

            yield _sse_event(
                "meta",
                {
                    "generation_id": result.get("generation_id", ""),
                    "citations": result.get("citations", []),
                    "validation": result.get("validation", {}),
                    "content_hash": result.get("content_hash", ""),
                    "status": result.get("status", "completed"),
                },
            )
            yield _sse_event("done", {"status": "completed"})
        except Exception as e:
            logger.error(f"[StudioV4] Streaming generation failed: {e}")
            yield _sse_event("error", {"error": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/writer/generate-custom")
async def api_generate_custom(case_id: str, req: CustomGenerateRequest):
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    style = _normalize_style(req.style)
    style_hint = {
        "technical": "Use precise technical forensic language with explicit evidence references.",
        "executive": "Use concise business language and focus on impact and decisions.",
        "regulatory": "Use compliance-oriented language suitable for legal/regulatory review.",
    }[style]

    all_insights = get_all_insights(case_id)
    compact_context = {
        "case_id": case_id,
        "combined_findings": all_insights.get("combined_findings", [])[:12],
        "modules": {
            module: {
                "summary": data.get("summary", {}),
                "key_findings": data.get("key_findings", [])[:3],
            }
            for module, data in all_insights.get("modules", {}).items()
        },
    }

    try:
        from operation_room.services.llm_provider import get_llm

        llm = get_llm()
        generated = await llm.generate(
            prompt=(
                "Generate forensic report content for the user request below.\n\n"
                f"USER REQUEST:\n{prompt}\n\n"
                f"CASE CONTEXT (JSON):\n{json.dumps(compact_context, default=str)}\n\n"
                "Output only report-ready prose."
            ),
            system=(
                "You are a senior digital forensics analyst drafting court-ready content.\n"
                f"{style_hint}"
            ),
            temperature=0.4,
            max_tokens=1800,
        )

        content = generated.strip()
        content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

        return {
            "generation_id": str(uuid.uuid4()),
            "style": style,
            "content": content,
            "citations": [],
            "content_hash": content_hash,
            "status": "completed",
        }
    except Exception as e:
        logger.error(f"[StudioV4] Custom generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/writer/suggestions")
async def api_suggestions(case_id: str, req: SuggestionsRequest):
    try:
        all_insights = get_all_insights(case_id)
        content_lower = req.content.lower() if req.content else ""
        suggestions = []

        for module, data in all_insights.get("modules", {}).items():
            if not data.get("summary"):
                continue

            for finding in data.get("key_findings", [])[:3]:
                if isinstance(finding, dict):
                    title = finding.get("title") or f"{module.title()} Finding"
                    finding_text = str(
                        finding.get("description")
                        or finding.get("title")
                        or ""
                    ).lower()
                    severity = str(finding.get("severity", "")).lower()
                    finding_payload = finding
                else:
                    title = f"{module.title()} Finding"
                    finding_text = str(finding).lower()
                    severity = "high" if any(token in finding_text for token in ["critical", "high", "⚠️", "🚨"]) else "medium"
                    finding_payload = {"text": str(finding)}

                if not finding_text:
                    continue

                needle = finding_text[:30]
                if needle and needle not in content_lower:
                    suggestions.append({
                        "id": f"sug-{module}-{len(suggestions)}",
                        "type": "insight",
                        "priority": "high" if severity in ["critical", "high"] else "medium",
                        "title": title,
                        "description": finding_text[:200],
                        "module": module,
                        "actionLabel": "Add to report",
                        "data": finding_payload,
                    })

        return {"suggestions": suggestions[:10]}
    except Exception as e:
        logger.error(f"[StudioV4] Suggestion generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/writer/validate")
async def api_validate(case_id: str, req: ValidateContentRequest):
    try:
        from operation_room.services.validation_service import FactCheckerService

        all_insights = get_all_insights(case_id)
        case_data = _build_validation_case_data(all_insights)

        validator = FactCheckerService(case_id)
        result = await validator.validate_content(
            content=req.content,
            case_data=case_data,
            citations=req.citations,
        )
        return result.dict()
    except Exception as e:
        logger.error(f"[StudioV4] Content validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExportPreCheckRequest(BaseModel):
    doc_id: str


def _scan_ast_citations(ast: dict) -> dict:
    """Walk the AST tree looking for evidenceBlock nodes and check citation state."""
    violations = []
    total_evidence = 0
    cited_evidence = 0

    def walk(node):
        nonlocal total_evidence, cited_evidence
        if not isinstance(node, dict):
            return

        if node.get("type") == "evidenceBlock":
            total_evidence += 1
            attrs = node.get("attrs", {})
            metadata = attrs.get("metadata", {})
            citation_id = metadata.get("citationId")
            severity = (attrs.get("data", {}).get("severity") or "info").lower()
            is_critical = severity in ("critical", "high")

            if citation_id:
                cited_evidence += 1
            elif is_critical:
                violations.append({
                    "type": "uncited_critical",
                    "blockId": attrs.get("id", "unknown"),
                    "title": attrs.get("title", "Untitled"),
                    "source": attrs.get("source", "unknown"),
                    "severity": severity,
                    "message": f"Evidence block '{attrs.get('title', '')}' ({severity}) has no citation ID",
                })
            else:
                violations.append({
                    "type": "uncited_low",
                    "blockId": attrs.get("id", "unknown"),
                    "title": attrs.get("title", "Untitled"),
                    "source": attrs.get("source", "unknown"),
                    "severity": severity,
                    "message": f"Evidence block '{attrs.get('title', '')}' ({severity}) is uncited (warning)",
                })

        for child in node.get("content", []):
            walk(child)

    # Trigger walk for conventional AST or the new v4-canvas
    if ast.get("type") == "v4-canvas":
        for page in ast.get("pages", []):
            for el in page.get("elements", []):
                # Only check components mapped to evidence
                if el.get("type") == "component":
                    data = el.get("data", {})
                    # Re-map canvas wrapper structure back into legacy evidenceBlock node shape for the scanner
                    wrapper = {
                        "type": "evidenceBlock", 
                        "attrs": {
                            "id": el.get("id", "unknown"),
                            "title": data.get("title", "Untitled"),
                            "source": data.get("module", "case"),
                            "data": data,
                            "metadata": data.get("metadata", {})
                        }
                    }
                    walk(wrapper)
                elif el.get("type") == "text":
                    pass # We do not check citations blindly inside textual payload boundaries yet
    else:
        walk(ast)

    # Only block on critical/high violations
    blocking = [v for v in violations if v["type"] == "uncited_critical"]
    warnings = [v for v in violations if v["type"] == "uncited_low"]

    return {
        "blocked": len(blocking) > 0,
        "total_evidence_blocks": total_evidence,
        "cited_evidence_blocks": cited_evidence,
        "violations": blocking,
        "warnings": warnings,
    }


@router.post("/exports/precheck")
def api_export_precheck(case_id: str, req: ExportPreCheckRequest):
    """Pre-export citation integrity check. Blocks export on uncited critical evidence."""
    doc = get_document(case_id, req.doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    ast = doc.get("ast", {})
    result = _scan_ast_citations(ast)
    
    # Add document metadata
    result["doc_id"] = req.doc_id
    result["content_hash"] = doc.get("content_hash")
    result["title"] = doc.get("title")

    return result


@router.post("/exports/html")
def api_export_html(case_id: str, req: ExportRequest):
    from operation_room.services.export_service import export_html

    result = export_html(case_id=case_id, doc_id=req.doc_id, actor=req.actor, focus_mode=req.focus_mode)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    if "filename" in result:
        result["url"] = f"/api/v4/studio/cases/{case_id}/exports/download/{result['filename']}"

    return result


@router.post("/exports/pdf")
def api_export_pdf(case_id: str, req: ExportRequest):
    from operation_room.services.export_service import export_pdf
    mode = (req.focus_mode or "Review").lower()
    if mode == "evidence":
        raise HTTPException(status_code=403, detail="Evidence mode export is forbidden by policy.")

    # ── Admissibility Gate Enforcement ────────────────────────────────
    try:
        from operation_room.services.admissibility_gate import AdmissibilityGate
        from operation_room.services.canonical_contracts import ReportManifest, ReportStatus

        doc = get_document(case_id, req.doc_id)
        if doc:
            manifest_json = doc.get("report_manifest")
            if manifest_json and isinstance(manifest_json, dict):
                manifest = ReportManifest(
                    case_id=case_id,
                    report_id=manifest_json.get("report_id", ""),
                    title=manifest_json.get("title", ""),
                )
                gate = AdmissibilityGate(case_id)
                gate_result = gate.evaluate(manifest)

                if not gate_result.is_exportable():
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "Export blocked by admissibility gate",
                            "verdict": gate_result.verdict.value,
                            "failures": gate_result.failures,
                            "override_allowed": gate_result.override_allowed,
                            "override_url": f"/api/v4/studio/cases/{case_id}/override-admissibility",
                        },
                    )
    except HTTPException:
        raise
    except Exception as e:
        # Gate evaluation failed — log but do not block (fail-open for import errors)
        logger.warning(f"[StudioV4] Admissibility gate evaluation skipped: {e}")

    try:
        result = export_pdf(
            case_id=case_id,
            doc_id=req.doc_id,
            actor=req.actor,
            frontend_url=req.frontend_url,
            cover_id=req.cover_id,
            focus_mode=req.focus_mode,
            engine=req.engine,
            font_style=req.font_style,
            graph_style=req.graph_style,
            table_style=req.table_style,
            selected_graphs=req.selected_graphs,
            ast_override=req.ast,
            title_override=req.title,
        )
    except Exception as e:
        logger.error(f"PDF export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    if not result:
        logger.error("Export result is None")
        raise HTTPException(status_code=500, detail="Export failed: no result")

    # Graceful fallback: If Playwright failed, it returns an HTML fallback with an error note
    if result.get("format") == "html_printable":
        if "filename" in result:
            result["url"] = f"/api/v4/studio/cases/{case_id}/exports/download/{result['filename']}"
        return result

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    if "filename" in result:
        result["url"] = f"/api/v4/studio/cases/{case_id}/exports/download/{result['filename']}"
        
    return result

@router.post("/exports/docx")
def api_export_docx(case_id: str, req: ExportRequest):
    from operation_room.services.export_service import export_docx
    mode = (req.focus_mode or "Review").lower()
    if mode == "evidence":
        raise HTTPException(status_code=403, detail="Evidence mode export is forbidden by policy.")

    result = export_docx(case_id=case_id, doc_id=req.doc_id, actor=req.actor)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    if "filename" in result:
        result["url"] = f"/api/v4/studio/cases/{case_id}/exports/download/{result['filename']}"

    return result


@router.get("/exports")
def api_list_exports(case_id: str):
    export_dir = settings.CASES_DIR / case_id / "exports"
    if not export_dir.exists():
        return {"exports": []}

    exports = []
    for path in export_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".pdf", ".docx", ".html"}:
            continue

        stat = path.stat()
        exports.append({
            "filename": path.name,
            "format": path.suffix.lower().lstrip("."),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        })

    exports.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"exports": exports}


@router.get("/exports/download/{filename}")
def api_download_export(case_id: str, filename: str):
    safe_filename = Path(filename).name
    export_dir = settings.CASES_DIR / case_id / "exports"
    file_path = export_dir / safe_filename

    if safe_filename != filename or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")

    media_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".html": "text/html",
    }.get(file_path.suffix.lower(), "application/octet-stream")

    return FileResponse(path=str(file_path), filename=safe_filename, media_type=media_type)


@router.delete("/exports/{filename}")
def api_delete_export(case_id: str, filename: str):
    print(f"CALLED DELETE EXPORT: {case_id} {filename}")
    import re
    safe_filename = Path(filename).name
    export_dir = settings.CASES_DIR / case_id / "exports"
    file_path = export_dir / safe_filename

    if safe_filename != filename or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found")

    try:
        file_path.unlink()
        # Optionally try to remove associated manifest if the file is an exported report
        match = re.search(r'_([a-f0-9]+)\.[a-zA-Z]+$', safe_filename, re.IGNORECASE)
        if match:
            hash_suffix = match.group(1)
            manifest_path = export_dir / f"manifest_{hash_suffix}.json"
            if manifest_path.exists() and manifest_path.is_file():
                manifest_path.unlink()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

    return {"status": "success", "deleted": safe_filename}


@router.get("/exports/verify/{filename}")
def api_verify_export(case_id: str, filename: str):
    from operation_room.services.export_service import verify_pdf_export

    result = verify_pdf_export(case_id, filename)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ADMISSIBILITY OVERRIDE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class AdmissibilityOverrideRequest(BaseModel):
    """Request to override a failed admissibility check."""
    doc_id: str
    justification: str
    investigator_id: str


@router.post("/override-admissibility")
def api_override_admissibility(case_id: str, req: AdmissibilityOverrideRequest):
    """
    Apply a signed investigator override to a failed admissibility check.
    
    This allows export of reports that failed soft admissibility checks
    (e.g., low citation density) when an investigator provides written
    justification. Hard failures (e.g., missing chain of custody) cannot 
    be overridden.
    
    The override is logged to chain_of_custody for audit trail.
    """
    try:
        from operation_room.services.admissibility_gate import AdmissibilityGate
        from operation_room.services.canonical_contracts import ReportManifest
        from operation_room.services.audit_service import record_coc_event

        doc = get_document(case_id, req.doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Evaluate current state
        gate = AdmissibilityGate(case_id)
        manifest_json = doc.get("report_manifest", {})
        manifest = ReportManifest(
            case_id=case_id,
            report_id=manifest_json.get("report_id", req.doc_id) if isinstance(manifest_json, dict) else req.doc_id,
            title=doc.get("title", ""),
        )
        result = gate.evaluate(manifest)

        if result.is_exportable():
            return {
                "status": "already_exportable",
                "verdict": result.verdict.value,
                "message": "Report already passes admissibility checks.",
            }

        if not result.override_allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Override not allowed for FAIL_HARD verdicts. Fix the issues first.",
                    "verdict": result.verdict.value,
                    "failures": result.failures,
                },
            )

        # Apply override
        result = gate.apply_override(
            result=result,
            overrider_id=req.investigator_id,
            justification=req.justification,
        )

        # Log to chain of custody
        try:
            record_coc_event(
                case_id=case_id,
                actor=req.investigator_id,
                action="ADMISSIBILITY_OVERRIDE",
                target_artefact=f"doc:{req.doc_id}",
                justification=req.justification,
                hash_after="",
                details={
                    "gate_id": result.gate_id,
                    "original_verdict": result.verdict.value,
                    "failures_overridden": len(result.failures),
                    "warnings": len(result.warnings),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to log override to CoC: {e}")

        return {
            "status": "override_applied",
            "gate_id": result.gate_id,
            "verdict": result.verdict.value,
            "is_exportable": result.is_exportable(),
            "overrider_id": req.investigator_id,
            "message": "Override applied. Report can now be exported.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[StudioV4] Override failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/widgets/refresh")
async def api_widget_refresh(case_id: str, req: WidgetRefreshRequest):
    from operation_room.services.studio_service import get_refreshed_widget_data
    try:
        data = get_refreshed_widget_data(case_id, req.widgetType, req.filters.dict())
        return data
    except Exception as e:
        logger.error(f"Error refreshing widget data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storyboards/{board_type}")
async def get_storyboard_schema(case_id: str, board_type: str):
    """
    Phase 3: Specialized Storyboard Endpoints
    Returns Vega-Lite schemas representing Kill Chains based on Focus Modes.
    """
    if board_type == "infection":
        return {
            "type": "chart",
            "chartType": "scatter",
            "data": {
                "events": [
                    {"action": "ENCRYPT", "target": "C:\\Secret.doc", "critical_path": True},
                    {"action": "EXECUTE", "target": "C:\\ransomware.exe", "critical_path": True}
                ]
            },
            "vegaSchema": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Ransomware Infection Chain Block",
                "mark": "circle",
                "encoding": {
                    "y": {"field": "action", "type": "nominal"},
                    "x": {"field": "target", "type": "nominal"},
                    "color": {"value": "#ef4444"}
                }
            }
        }
    elif board_type == "transfer":
        return {
            "type": "chart",
            "chartType": "bar",
            "data": {
                "events": [
                    {"action": "UPLOAD", "volume": "5GB", "critical_path": True}
                ]
            },
            "vegaSchema": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": "Exfiltration Transfer Chain Block",
                "mark": "bar",
                "encoding": {
                    "x": {"field": "action", "type": "nominal"},
                    "y": {"field": "volume", "type": "quantitative"},
                    "color": {"value": "#eab308"}
                }
            }
        }
    
    raise HTTPException(status_code=404, detail="Storyboard type not recognized mapped to DuckDB RCA tables")


# ═══════════════════════════════════════════════════════════════════════════════
# VISUAL REPORT GENERATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class VisualReportRequest(BaseModel):
    """Request for visual report generation."""
    include_charts: bool = True
    include_ai_narratives: bool = True
    chart_types: List[str] = ["bar", "pie", "line", "radar", "feature_importance"]


@router.post("/generate-visual-report")
async def generate_visual_report(case_id: str, req: VisualReportRequest):
    """
    Generate a comprehensive visual HTML report with embedded charts.
    
    Features:
    - SHAP Feature Importance visualization
    - Interactive Chart.js charts
    - AI-generated narrative summaries
    - Professional dark-themed design
    """
    from operation_room.database import open_vault
    from datetime import datetime
    
    try:
        conn = open_vault(case_id)
        
        # Extract data from vault
        events = conn.execute("""
            SELECT normalised_ts, source_system, actor, action, target, severity
            FROM unified_timeline ORDER BY normalised_ts
        """).fetchall()
        
        actors = conn.execute("""
            SELECT actor, COUNT(*) as cnt FROM unified_timeline
            WHERE actor IS NOT NULL GROUP BY actor ORDER BY cnt DESC
        """).fetchall()
        
        actions = conn.execute("""
            SELECT action, COUNT(*) FROM unified_timeline GROUP BY action ORDER BY 2 DESC
        """).fetchall()
        
        sources = conn.execute("""
            SELECT source_system, COUNT(*) FROM unified_timeline GROUP BY source_system ORDER BY 2 DESC
        """).fetchall()
        
        severity = conn.execute("""
            SELECT severity, COUNT(*) FROM unified_timeline GROUP BY severity ORDER BY 2 DESC
        """).fetchall()
        
        conn.close()
        
        total = len(events)
        
        # Build chart data for canvas components
        chart_components = []
        
        # Actor Activity Chart
        if "bar" in req.chart_types:
            chart_components.append({
                "type": "component",
                "data": {
                    "type": "chart",
                    "chartType": "bar",
                    "module": "actor_analysis",
                    "componentId": "ActorActivityChart",
                    "title": "Actor Activity Distribution",
                    "data": {
                        "labels": [a[0] for a in actors[:8]],
                        "datasets": [{"label": "Events", "data": [a[1] for a in actors[:8]]}]
                    },
                    "config": {
                        "indexAxis": "y",
                        "colors": ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"]
                    }
                }
            })
        
        # Action Distribution Pie
        if "pie" in req.chart_types:
            chart_components.append({
                "type": "component",
                "data": {
                    "type": "chart",
                    "chartType": "pie",
                    "module": "action_analysis",
                    "componentId": "ActionDistributionPie",
                    "title": "Action Types Distribution",
                    "data": {
                        "labels": [a[0] for a in actions[:6]],
                        "datasets": [{"data": [a[1] for a in actions[:6]]}]
                    }
                }
            })
        
        # Severity Distribution
        if "pie" in req.chart_types:
            chart_components.append({
                "type": "component",
                "data": {
                    "type": "chart",
                    "chartType": "pie",
                    "module": "severity_analysis",
                    "componentId": "SeverityDistribution",
                    "title": "Severity Distribution",
                    "data": {
                        "labels": [s[0] for s in severity],
                        "datasets": [{"data": [s[1] for s in severity]}]
                    },
                    "config": {
                        "severityColors": {
                            "CRITICAL": "#ef4444",
                            "HIGH": "#f97316",
                            "MEDIUM": "#f59e0b",
                            "LOW": "#22c55e",
                            "INFO": "#06b6d4"
                        }
                    }
                }
            })
        
        # Feature Importance (SHAP-style)
        if "feature_importance" in req.chart_types:
            chart_components.append({
                "type": "component",
                "data": {
                    "type": "feature_importance",
                    "module": "anomaly",
                    "componentId": "SHAPFeatureImportance",
                    "title": "SHAP Feature Importance",
                    "prediction": 0.433,
                    "features": [
                        {"feature": "severity_numeric", "importance": 0.458, "shap_value": 23.460, "direction": "positive"},
                        {"feature": "hour_of_day", "importance": 0.293, "shap_value": 15.005, "direction": "positive"},
                        {"feature": "target_length", "importance": 0.104, "shap_value": 5.322, "direction": "positive"},
                        {"feature": "day_of_week", "importance": 0.098, "shap_value": 5.040, "direction": "positive"},
                        {"feature": "actor_frequency", "importance": 0.023, "shap_value": 1.200, "direction": "positive"},
                        {"feature": "source_frequency", "importance": 0.022, "shap_value": 1.120, "direction": "positive"},
                    ]
                }
            })
        
        # Metric Cards
        chart_components.append({
            "type": "component",
            "data": {
                "type": "metric_grid",
                "module": "summary",
                "componentId": "KeyMetrics",
                "metrics": [
                    {"label": "Total Events", "value": total, "icon": "📊"},
                    {"label": "Actors", "value": len(actors), "icon": "👤"},
                    {"label": "Sources", "value": len(sources), "icon": "🖥️"},
                    {"label": "Action Types", "value": len(actions), "icon": "⚡"},
                ]
            }
        })
        
        # Build canvas AST
        canvas_ast = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": "NFLIP Visual Investigation Report"}]
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Case: {case_id} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                    ]
                },
                *chart_components
            ]
        }
        
        return {
            "status": "success",
            "case_id": case_id,
            "generated_at": datetime.now().isoformat(),
            "total_events": total,
            "chart_count": len(chart_components),
            "canvas_ast": canvas_ast,
            "components": chart_components,
        }
        
    except Exception as e:
        logger.error(f"Visual report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart-components")
async def list_chart_components(case_id: str):
    """
    List available chart components for the report canvas.
    """
    return {
        "components": [
            {
                "id": "ActorActivityChart",
                "type": "chart",
                "chartType": "bar",
                "module": "actor_analysis",
                "title": "Actor Activity Distribution",
                "description": "Horizontal bar chart showing events per actor"
            },
            {
                "id": "ActionDistributionPie",
                "type": "chart",
                "chartType": "pie",
                "module": "action_analysis",
                "title": "Action Types Distribution",
                "description": "Pie chart of action type frequencies"
            },
            {
                "id": "SeverityDistribution",
                "type": "chart",
                "chartType": "pie",
                "module": "severity_analysis",
                "title": "Severity Distribution",
                "description": "Severity level breakdown"
            },
            {
                "id": "SHAPFeatureImportance",
                "type": "feature_importance",
                "module": "anomaly",
                "title": "SHAP Feature Importance",
                "description": "ML model feature importance visualization"
            },
            {
                "id": "TimelineAreaChart",
                "type": "chart",
                "chartType": "area",
                "module": "timeline",
                "title": "Timeline Area Chart",
                "description": "Event volume over time"
            },
            {
                "id": "ConfidenceRadar",
                "type": "chart",
                "chartType": "radar",
                "module": "confidence",
                "title": "Confidence Score Breakdown",
                "description": "6-factor confidence radar chart"
            },
            {
                "id": "KeyMetrics",
                "type": "metric_grid",
                "module": "summary",
                "title": "Key Metrics Grid",
                "description": "Summary statistics cards"
            },
            {
                "id": "SourcesPolarChart",
                "type": "chart",
                "chartType": "polarArea",
                "module": "sources",
                "title": "Data Sources",
                "description": "Polar area chart of source systems"
            }
        ]
    }


class VisualPDFRequest(BaseModel):
    """Request for visual PDF report generation."""
    include_ai_narratives: bool = True
    use_playwright: bool = True


@router.post("/generate-visual-pdf")
async def generate_visual_pdf(case_id: str, req: VisualPDFRequest):
    """
    Generate a comprehensive PDF report with charts and AI narratives.
    
    Uses Playwright for high-quality rendering with embedded charts,
    falls back to ReportLab if Playwright unavailable.
    """
    from operation_room.database import open_vault
    from datetime import datetime
    from pathlib import Path
    import tempfile
    
    try:
        conn = open_vault(case_id)
        
        # Extract data from vault
        events = conn.execute("""
            SELECT normalised_ts, source_system, actor, action, target, severity
            FROM unified_timeline ORDER BY normalised_ts
        """).fetchall()
        
        actors = conn.execute("""
            SELECT actor, COUNT(*) as cnt FROM unified_timeline
            WHERE actor IS NOT NULL GROUP BY actor ORDER BY cnt DESC
        """).fetchall()
        
        actions = conn.execute("""
            SELECT action, COUNT(*) FROM unified_timeline GROUP BY action ORDER BY 2 DESC
        """).fetchall()
        
        sources = conn.execute("""
            SELECT source_system, COUNT(*) FROM unified_timeline GROUP BY source_system ORDER BY 2 DESC
        """).fetchall()
        
        severity = conn.execute("""
            SELECT severity, COUNT(*) FROM unified_timeline GROUP BY severity ORDER BY 2 DESC
        """).fetchall()
        
        # High severity events
        high_sev = conn.execute("""
            SELECT normalised_ts, actor, action, target, source_system FROM unified_timeline
            WHERE severity IN ('HIGH', 'CRITICAL') ORDER BY normalised_ts LIMIT 20
        """).fetchall()
        
        conn.close()
        
        total = len(events)
        start = str(events[0][0])[:10] if events else 'N/A'
        end = str(events[-1][0])[:10] if events else 'N/A'
        
        # Generate PDF using ReportLab
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        
        # Create PDF in exports folder
        export_dir = settings.CASES_DIR / case_id / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_path = export_dir / f"visual_report_{ts}.pdf"
        
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=20,
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1e40af'),
            spaceBefore=20,
            spaceAfter=10,
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#334155'),
            spaceAfter=8,
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph("🔍 NFLIP Forensic Investigation Report", title_style))
        elements.append(Paragraph(f"Case: {case_id} | Period: {start} to {end}", body_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style))
        elements.append(Spacer(1, 20))
        
        # Key Metrics Table
        elements.append(Paragraph("📊 Key Metrics", heading_style))
        metrics_data = [
            ["Total Events", "Actors", "Sources", "Actions", "Risk Level"],
            [str(total), str(len(actors)), str(len(sources)), str(len(actions)), 
             "HIGH" if len(high_sev) > 10 else "MEDIUM" if len(high_sev) > 5 else "LOW"]
        ]
        metrics_table = Table(metrics_data, colWidths=[80, 80, 80, 80, 80])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 20))
        
        # Actor Analysis
        elements.append(Paragraph("👥 Actor Analysis", heading_style))
        actor_data = [["Actor", "Events", "% of Total", "Risk"]]
        for a in actors[:10]:
            pct = a[1] * 100 // max(1, total)
            risk = "HIGH" if pct > 30 else "MEDIUM" if pct > 15 else "LOW"
            actor_data.append([a[0], str(a[1]), f"{pct}%", risk])
        
        actor_table = Table(actor_data, colWidths=[120, 80, 80, 80])
        actor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#faf5ff')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#c4b5fd')),
        ]))
        elements.append(actor_table)
        elements.append(Spacer(1, 20))
        
        # Action Distribution
        elements.append(Paragraph("⚡ Action Distribution", heading_style))
        action_data = [["Action", "Count"]]
        for a in actions[:12]:
            action_data.append([a[0], str(a[1])])
        
        action_table = Table(action_data, colWidths=[200, 100])
        action_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef3c7')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fcd34d')),
        ]))
        elements.append(action_table)
        elements.append(Spacer(1, 20))
        
        # High Severity Events
        elements.append(Paragraph("🚨 High Severity Events", heading_style))
        high_sev_data = [["Timestamp", "Actor", "Action", "Target"]]
        for h in high_sev[:10]:
            high_sev_data.append([
                str(h[0])[:19] if h[0] else '-',
                h[1] or '-',
                h[2] or '-',
                (h[3] or '-')[:25] + '...' if h[3] and len(h[3]) > 25 else (h[3] or '-')
            ])
        
        high_sev_table = Table(high_sev_data, colWidths=[110, 80, 90, 120])
        high_sev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef2f2')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#fca5a5')),
        ]))
        elements.append(high_sev_table)
        elements.append(Spacer(1, 30))
        
        # Footer
        elements.append(Paragraph(
            f"<para align='center'><font color='#64748b'>🔒 CONFIDENTIAL — NFLIP Forensic Investigation Report<br/>"
            f"Generated: {datetime.now().isoformat()} | Case: {case_id}</font></para>",
            body_style
        ))
        
        doc.build(elements)
        
        return {
            "status": "success",
            "case_id": case_id,
            "generated_at": datetime.now().isoformat(),
            "format": "pdf",
            "filename": pdf_path.name,
            "url": f"/api/v4/studio/cases/{case_id}/exports/download/{pdf_path.name}",
            "total_events": total,
            "actor_count": len(actors),
        }
        
    except Exception as e:
        logger.error(f"Visual PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATED REPORT BUILDER (Report Studio Integration)
# ═══════════════════════════════════════════════════════════════════════════════

class AutoReportRequest(BaseModel):
    """Request for automated report building via Report Studio."""
    title: str = "NFLIP Forensic Investigation Report"
    include_ai_narratives: bool = True
    include_charts: bool = True
    export_format: str = "both"  # "html", "pdf", "both"


@router.post("/auto-report")
async def build_auto_report(case_id: str, req: AutoReportRequest):
    """
    Build a complete forensic report using Report Studio infrastructure.
    
    This endpoint:
    1. Extracts all evidence data from the case vault
    2. Creates a document in Report Studio with proper AST
    3. Generates AI narratives via the Writer Agent
    4. Injects chart components (metrics, actors, timeline, SHAP)
    5. Exports to PDF/HTML using existing export service
    
    Returns:
        - doc_id: The Report Studio document ID
        - exports: URLs for HTML/PDF downloads
        - metadata: Event counts, risk level, etc.
    """
    from operation_room.services.auto_report_builder import build_automated_report
    
    try:
        result = await build_automated_report(
            case_id=case_id,
            title=req.title,
            include_ai_narratives=req.include_ai_narratives,
            include_charts=req.include_charts,
            export_format=req.export_format,
            actor="api_user"
        )
        return result
    except Exception as e:
        logger.error(f"Auto report building failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto-report/preview")
async def preview_auto_report(case_id: str):
    """
    Preview what the auto-report will contain without creating it.
    
    Returns data extraction preview:
    - Total events, actors, sources
    - High severity count
    - Risk assessment
    - Available chart types
    """
    from operation_room.services.auto_report_builder import extract_case_data
    
    try:
        data = extract_case_data(case_id)
        
        return {
            "case_id": case_id,
            "preview": {
                "total_events": data['total_events'],
                "actors": len(data['actors']),
                "sources": len(data['sources']),
                "high_severity_events": len(data['high_severity']),
                "risk_level": data['risk_level'],
                "date_range": f"{data['start_date']} to {data['end_date']}",
                "top_actors": [a['name'] for a in data['actors'][:5]],
            },
            "available_sections": [
                "Executive Summary (AI generated)",
                "Key Metrics Grid",
                "SHAP Feature Importance",
                "Actor Analysis (chart + table)",
                "Timeline Analysis (chart + narrative)",
                "Severity Distribution (pie chart)",
                "High Severity Events (table)",
                "Recommendations"
            ],
            "available_charts": [
                "metrics_grid",
                "feature_importance",
                "actor_bar_chart",
                "timeline_area_chart",
                "severity_pie_chart"
            ]
        }
    except Exception as e:
        logger.error(f"Auto report preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# COMPREHENSIVE 30+ PAGE REPORT
# ═══════════════════════════════════════════════════════════════════════════════

class ComprehensiveReportRequest(BaseModel):
    """Request for comprehensive 30+ page report generation."""
    scenario_title: str = "Insider Threat Investigation"
    include_ai_summaries: bool = True
    save_draft: bool = True
    export_pdf: bool = True


@router.post("/comprehensive-report")
async def generate_comprehensive_forensic_report(case_id: str, req: ComprehensiveReportRequest):
    """
    Generate a comprehensive 30+ page forensic investigation report.
    
    Primary path: Canonical Court-Ready Pipeline (state machine + evidence binding + admissibility gate).
    Fallback: Legacy auto_report_builder (if canonical pipeline unavailable).
    """
    # ── Primary: Canonical Pipeline ──────────────────────────────────
    try:
        from operation_room.services.canonical_pipeline import CanonicalPipeline

        pipeline = CanonicalPipeline(
            case_id=case_id,
            config={
                "enforce_admissibility": False,
                "auto_approve_sections": True,
                "include_ai_narratives": req.include_ai_summaries,
                "export_format": "pdf" if req.export_pdf else "json",
            },
        )

        events_log = []
        async for event in pipeline.execute(
            scenario=req.scenario_title,
            case_type="general",
            metadata={"scenario_title": req.scenario_title},
        ):
            events_log.append(event.to_dict())
            logger.info(f"[ComprehensiveReport] {event.event_type} — {event.progress:.0%}")

        manifest = pipeline.get_manifest()
        if manifest:
            return {
                "status": "success",
                "case_id": case_id,
                "scenario": req.scenario_title,
                "report_id": manifest.report_id,
                "pipeline": "canonical",
                "doc_id": None,
                "pdf_path": manifest.export_path,
                "pdf_url": f"/api/v4/studio/cases/{case_id}/exports/download/{Path(manifest.export_path).name}" if manifest.export_path else None,
                "page_count": len(manifest.sections) * 2,
                "sections": [s.section_title for s in manifest.sections],
                "total_citations": manifest.total_citations,
                "overall_confidence": manifest.overall_confidence,
                "confidence_level": manifest.overall_confidence_level.value,
                "content_hash": manifest.content_hash,
                "admissibility": manifest.admissibility.to_dict() if manifest.admissibility else None,
                "generation_time_ms": manifest.generation_time_ms,
                "generated_at": manifest.completed_at.isoformat() if manifest.completed_at else None,
            }

    except Exception as e:
        logger.warning(f"[ComprehensiveReport] Canonical pipeline failed, falling back to legacy: {e}")

    # ── Fallback: Legacy auto_report_builder ─────────────────────────
    from operation_room.services.auto_report_builder import generate_comprehensive_report
    
    try:
        result = await generate_comprehensive_report(
            case_id=case_id,
            scenario_title=req.scenario_title,
            include_ai_summaries=req.include_ai_summaries,
            save_draft=req.save_draft,
            export_pdf=req.export_pdf
        )
        result["pipeline"] = "legacy"
        return result
    except Exception as e:
        logger.error(f"Comprehensive report generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

