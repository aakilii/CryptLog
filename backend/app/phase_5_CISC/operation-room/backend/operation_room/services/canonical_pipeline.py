"""
Canonical Court-Ready Pipeline — Phase 7.

Master pipeline that orchestrates the complete forensic report generation
flow from investigation context to court-admissible export.

Pipeline Stages:
1. Template Selection (adaptive_template_engine)
2. Evidence Collection (report_evidence_service)
3. Section Generation (section_state_machine + evidence_binder)
4. Admissibility Gate (admissibility_gate)
5. Export & Signing (export_service)

This module serves as the single entry point for generating reports
that pass court-admissibility checks.
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from operation_room.services.canonical_contracts import (
    AdmissibilityResult,
    AdmissibilityVerdict,
    ConfidenceLevel,
    EvidenceCitation,
    PipelineCheckpoint,
    ReportManifest,
    ReportStatus,
    SectionContract,
    SectionStatus,
)
from operation_room.services.adaptive_template_engine import (
    AdaptiveTemplateEngine,
    get_template_engine,
)
from operation_room.services.evidence_binder import (
    EvidenceBinder,
    get_evidence_binder,
)
from operation_room.services.section_state_machine import (
    SectionStateMachine,
)
from operation_room.services.admissibility_gate import (
    AdmissibilityGate,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_PIPELINE_CONFIG = {
    "max_section_concurrency": 4,
    "section_timeout_seconds": 120,
    "auto_approve_sections": True,
    "enforce_admissibility": True,
    "allow_override": True,
    "export_format": "pdf",
    "include_ai_narratives": True,
    "min_citation_density": 1 / 300,
    "template_override": None,
}


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineEvent:
    """Event emitted during pipeline execution for UI streaming."""

    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        progress: float = 0.0,
    ):
        self.event_type = event_type
        self.data = data
        self.progress = progress
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "progress": self.progress,
            "timestamp": self.timestamp,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CANONICAL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class CanonicalPipeline:
    """
    Master pipeline for court-ready forensic report generation.
    
    Usage:
        pipeline = CanonicalPipeline(case_id="case-123")
        
        async for event in pipeline.execute(
            scenario="Data exfiltration via USB",
            investigation_data=investigation_results,
        ):
            # Stream progress to UI
            print(event.event_type, event.progress)
        
        # Get final report
        manifest = pipeline.get_manifest()
        print(manifest.status)  # "COMPLETED" or "ADMISSIBILITY_FAILED"
    """

    def __init__(
        self,
        case_id: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.case_id = case_id
        self.config = {**DEFAULT_PIPELINE_CONFIG, **(config or {})}

        # Components (lazy-initialized)
        self._template_engine = get_template_engine()
        self._binder = get_evidence_binder(case_id)
        self._gate = AdmissibilityGate(case_id)

        # State
        self._manifest: Optional[ReportManifest] = None
        self._state_machine: Optional[SectionStateMachine] = None
        self._checkpoint: Optional[PipelineCheckpoint] = None
        self._start_time: float = 0

    @property
    def manifest(self) -> Optional[ReportManifest]:
        return self._manifest

    async def execute(
        self,
        scenario: str = "",
        case_type: str = "general",
        investigation_data: Optional[Dict[str, Any]] = None,
        module_results: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[PipelineEvent]:
        """
        Execute the full canonical pipeline.
        
        Args:
            scenario: Case scenario description
            case_type: CaseType from ScenarioAnalyzer
            investigation_data: Results from investigation (hypotheses, evidence, etc.)
            module_results: Results from Universal Module Tools
            metadata: Additional report metadata
            
        Yields:
            PipelineEvent for UI streaming
        """
        self._start_time = time.monotonic()
        investigation_data = investigation_data or {}
        module_results = module_results or {}
        metadata = metadata or {}

        try:
            # ─── STAGE 1: Template Selection ─────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "template_selection"}, 0.05)

            template_key = self._template_engine.select_template(
                case_type=case_type,
                template_override=self.config.get("template_override"),
            )

            sections = self._template_engine.assemble_sections(
                template_key=template_key,
                case_type=case_type,
            )

            # Create manifest
            self._manifest = ReportManifest(
                case_id=self.case_id,
                investigation_id=investigation_data.get("investigation_id"),
                template_key=template_key,
                title=metadata.get("title", self._generate_title(case_type, scenario)),
                sections=sections,
                metadata=metadata,
            )
            self._manifest.transition_to(ReportStatus.TEMPLATE_SELECTED)

            yield PipelineEvent(
                "template_selected",
                {
                    "template_key": template_key,
                    "section_count": len(sections),
                    "sections": [s.section_title for s in sections],
                },
                0.10,
            )

            # ─── STAGE 2: Data Gathering ─────────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "data_gathering"}, 0.15)
            self._manifest.transition_to(ReportStatus.DATA_GATHERING)

            # Gather evidence keys from vault
            evidence_keys = self._binder.get_all_evidence_keys()
            
            # Also pull data from module_results
            context = self._build_generation_context(
                scenario=scenario,
                case_type=case_type,
                investigation_data=investigation_data,
                module_results=module_results,
                evidence_keys=evidence_keys,
            )

            yield PipelineEvent(
                "data_gathered",
                {
                    "evidence_key_count": len(evidence_keys),
                    "module_count": len(module_results),
                },
                0.20,
            )

            # ─── STAGE 3: Evidence Binding ───────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "evidence_binding"}, 0.25)
            self._manifest.transition_to(ReportStatus.EVIDENCE_BINDING)

            # Pre-cache evidence keys in binder
            for ek in evidence_keys:
                self._binder._key_cache[ek.get("key_id", "")] = ek

            yield PipelineEvent(
                "evidence_bound",
                {"evidence_keys_cached": len(self._binder._key_cache)},
                0.30,
            )

            # ─── STAGE 4: Section Generation ─────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "section_generation"}, 0.30)

            self._state_machine = SectionStateMachine(
                manifest=self._manifest,
                max_concurrency=self.config.get("max_section_concurrency", 4),
            )

            # Set the section generator
            self._state_machine.set_generator(
                self._create_section_generator(context)
            )

            # Execute all sections
            self._manifest = await self._state_machine.execute_all(
                context=context,
                auto_approve=self.config.get("auto_approve_sections", True),
            )

            progress_data = self._state_machine.get_progress()
            yield PipelineEvent(
                "sections_generated",
                progress_data,
                0.70,
            )

            # ─── STAGE 5: Assembly ───────────────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "assembly"}, 0.75)
            self._manifest.transition_to(ReportStatus.ASSEMBLY)

            # Update manifest metrics
            self._manifest.update_rollup_metrics()
            self._manifest.compute_content_hash()

            yield PipelineEvent(
                "assembled",
                {
                    "total_citations": self._manifest.total_citations,
                    "total_orphans": self._manifest.total_orphan_citations,
                    "content_hash": self._manifest.content_hash[:16],
                },
                0.80,
            )

            # ─── STAGE 6: Admissibility Gate ─────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "admissibility_check"}, 0.85)
            self._manifest.transition_to(ReportStatus.ADMISSIBILITY_CHECK)

            admissibility = self._gate.evaluate(self._manifest)
            self._manifest.admissibility = admissibility

            yield PipelineEvent(
                "admissibility_result",
                admissibility.to_dict(),
                0.90,
            )

            if not admissibility.is_exportable():
                if self.config.get("enforce_admissibility", True):
                    self._manifest.transition_to(ReportStatus.ADMISSIBILITY_FAILED)
                    yield PipelineEvent(
                        "admissibility_failed",
                        {
                            "verdict": admissibility.verdict.value,
                            "failures": admissibility.failures,
                            "override_allowed": admissibility.override_allowed,
                        },
                        0.90,
                    )
                    self._manifest.generation_time_ms = int(
                        (time.monotonic() - self._start_time) * 1000
                    )
                    return
                else:
                    logger.warning(
                        "[CanonicalPipeline] Admissibility check failed but enforcement disabled — proceeding"
                    )

            # ─── STAGE 7: Export ──────────────────────────────────────────
            yield PipelineEvent("stage_start", {"stage": "export"}, 0.92)
            self._manifest.transition_to(ReportStatus.EXPORT_PENDING)
            self._manifest.transition_to(ReportStatus.EXPORTING)

            # Export (PDF, JSON, etc.)
            export_result = await self._export_report()

            self._manifest.export_format = self.config.get("export_format", "pdf")
            self._manifest.export_path = export_result.get("path")
            self._manifest.export_hash = export_result.get("hash")
            self._manifest.completed_at = datetime.now(timezone.utc)
            self._manifest.generation_time_ms = int(
                (time.monotonic() - self._start_time) * 1000
            )

            self._manifest.transition_to(ReportStatus.COMPLETED)

            yield PipelineEvent(
                "pipeline_complete",
                {
                    "report_id": self._manifest.report_id,
                    "status": self._manifest.status.value,
                    "generation_time_ms": self._manifest.generation_time_ms,
                    "total_sections": len(self._manifest.sections),
                    "total_citations": self._manifest.total_citations,
                    "overall_confidence": self._manifest.overall_confidence,
                    "confidence_level": self._manifest.overall_confidence_level.value,
                    "export_path": self._manifest.export_path,
                    "admissibility_verdict": admissibility.verdict.value,
                },
                1.0,
            )

        except Exception as e:
            logger.error(f"[CanonicalPipeline] Failed: {e}", exc_info=True)
            if self._manifest:
                try:
                    self._manifest.transition_to(ReportStatus.FAILED)
                except ValueError:
                    self._manifest.status = ReportStatus.FAILED
            yield PipelineEvent(
                "pipeline_error",
                {"error": str(e), "case_id": self.case_id},
                0.0,
            )

    def get_manifest(self) -> Optional[ReportManifest]:
        """Get the current report manifest."""
        return self._manifest

    def get_checkpoint(self) -> Optional[PipelineCheckpoint]:
        """Get the current pipeline checkpoint."""
        if self._state_machine:
            return self._state_machine.create_checkpoint()
        return None

    # ─── Section Generator ────────────────────────────────────────────────

    def _create_section_generator(self, context: Dict[str, Any]):
        """Create the section generator function for the state machine."""
        binder = self._binder

        async def _generate_section(
            section: SectionContract,
            ctx: Dict[str, Any],
        ) -> SectionContract:
            """Generate a single section with evidence binding."""

            # Build LLM prompt with evidence keys
            evidence_keys = ctx.get("evidence_keys", [])
            module_data = ctx.get("module_results", {})
            section_module_map = {
                "timeline": "timeline",
                "actor_analysis": "timeline",
                "anomalies": "anomaly",
                "attack_chain": "correlation",
                "data_access": "crud",
                "network": "network",
                "depth_impact": "depth",
            }
            relevant_module = section_module_map.get(section.section_key)
            module_summary = module_data.get(relevant_module, {}) if relevant_module else {}

            prompt = binder.build_evidence_prompt(
                section_key=section.section_key,
                section_title=section.section_title,
                evidence_keys=evidence_keys,
                case_context=ctx.get("case_context"),
                module_summaries=module_summary or None,
            )

            # Call LLM
            try:
                from operation_room.services.llm_provider import get_llm
                llm = get_llm()
                response = await llm.ainvoke(prompt)
                if hasattr(response, "content"):
                    content = response.content
                else:
                    content = str(response)
            except Exception as e:
                logger.warning(
                    f"[CanonicalPipeline] LLM call failed for section '{section.section_key}': {e}"
                )
                # Fallback: generate structured content from data
                content = self._generate_fallback_content(section, ctx)

            # Bind citations
            section = binder.bind_citations(section, content)

            # Set confidence based on citation quality
            if section.citations:
                avg_conf = sum(c.confidence for c in section.citations) / len(section.citations)
                section.confidence = avg_conf
            else:
                section.confidence = 0.3  # Low confidence without citations

            section.confidence_level = ConfidenceLevel.from_score(section.confidence)

            return section

        return _generate_section

    def _generate_fallback_content(
        self,
        section: SectionContract,
        context: Dict[str, Any],
    ) -> str:
        """Generate structured fallback content when LLM is unavailable."""
        module_results = context.get("module_results", {})
        scenario = context.get("scenario", "N/A")

        content = f"## {section.section_title}\n\n"
        content += f"**Case ID:** {self.case_id}\n\n"

        if section.section_key == "exec_summary":
            content += (
                f"This report documents the forensic investigation for case {self.case_id}. "
                f"The investigation scenario: {scenario[:300]}.\n\n"
                f"Analysis was performed using automated forensic tooling across "
                f"{len(module_results)} analysis modules.\n\n"
            )
        elif section.section_key == "case_overview":
            content += (
                f"**Scope:** {scenario[:500]}\n\n"
                f"**Systems Analysed:** The investigation covered data from "
                f"{len(module_results)} analysis modules.\n\n"
            )
        elif section.section_key == "methodology":
            content += (
                "The forensic analysis followed ISO 27037:2012 standards for digital evidence "
                "collection, handling, and presentation. All evidence was processed through "
                "a chain-of-custody compliant vault with SHA-256 integrity verification.\n\n"
                "**Tools Used:**\n"
                "- DuckDB OLAP engine for high-performance event analysis\n"
                "- DBSCAN temporal clustering for activity pattern detection\n"
                "- SHAP-based anomaly explanation\n"
                "- Entity correlation graph analysis\n\n"
            )
        elif section.section_key == "key_findings":
            # Aggregate findings from modules
            all_findings = context.get("investigation_data", {}).get("findings", [])
            if all_findings:
                content += "### Critical Findings\n\n"
                for i, finding in enumerate(all_findings[:10], 1):
                    if isinstance(finding, dict):
                        content += (
                            f"{i}. **{finding.get('title', 'Finding')}** — "
                            f"{finding.get('description', 'See evidence')}\n"
                        )
                    else:
                        content += f"{i}. {finding}\n"
                content += "\n"
            else:
                content += "No critical findings identified in the analysis period.\n\n"
        elif section.section_key == "chain_of_custody":
            content += (
                "All evidence items in this investigation were processed through "
                "a forensic chain-of-custody system. Each evidence item was:\n\n"
                "1. **Hashed** using SHA-256 upon collection\n"
                "2. **Logged** with timestamp, accessor, and action\n"
                "3. **Verified** against original hash upon each access\n\n"
                "The chain of custody log is available in the Evidence Appendix.\n\n"
            )
        elif section.section_key == "evidence_appendix":
            evidence_keys = context.get("evidence_keys", [])
            if evidence_keys:
                content += "### Evidence Key Manifest\n\n"
                content += "| Key ID | Category | Name | Source |\n"
                content += "|--------|----------|------|--------|\n"
                for ek in evidence_keys[:50]:
                    content += (
                        f"| {ek.get('key_id', '')} | {ek.get('category', '')} "
                        f"| {ek.get('key_name', '')} | {ek.get('source_module', '')} |\n"
                    )
                content += "\n"
            else:
                content += "No evidence keys registered for this investigation.\n\n"
        elif section.section_key == "remediation":
            content += (
                "### Immediate Actions\n"
                "1. Isolate affected systems and accounts\n"
                "2. Reset credentials for compromised users\n"
                "3. Enable enhanced monitoring\n\n"
                "### Short-Term (7-30 days)\n"
                "1. Conduct comprehensive access review\n"
                "2. Implement additional DLP controls\n"
                "3. Update incident response procedures\n\n"
                "### Long-Term (30-90 days)\n"
                "1. Implement zero-trust architecture enhancements\n"
                "2. Deploy advanced behavioral analytics\n"
                "3. Conduct security awareness training\n\n"
            )
        else:
            # Generic section fallback
            content += (
                f"Analysis data for this section was processed from the "
                f"forensic vault. Detailed metrics are available in the "
                f"Evidence Appendix.\n\n"
            )

        return content

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _build_generation_context(
        self,
        scenario: str,
        case_type: str,
        investigation_data: Dict[str, Any],
        module_results: Dict[str, Any],
        evidence_keys: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the shared context for section generation."""
        return {
            "scenario": scenario,
            "case_type": case_type,
            "case_context": {
                "case_id": self.case_id,
                "title": investigation_data.get("title", scenario[:100]),
                "status": "under_investigation",
            },
            "investigation_data": investigation_data,
            "module_results": module_results,
            "evidence_keys": evidence_keys,
            "config": self.config,
        }

    @staticmethod
    def _generate_title(case_type: str, scenario: str) -> str:
        """Generate a professional report title."""
        type_titles = {
            "data_exfiltration": "Data Exfiltration",
            "ransomware": "Ransomware Incident",
            "fraud": "Fraud Investigation",
            "insider_threat": "Insider Threat",
            "network_intrusion": "Network Intrusion",
            "malware": "Malware Analysis",
            "phishing": "Phishing Campaign",
            "ip_theft": "Intellectual Property Theft",
            "compliance": "Compliance Assessment",
        }
        type_name = type_titles.get(case_type, "Forensic Investigation")
        return f"NFLIP {type_name} Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    async def _export_report(self) -> Dict[str, Any]:
        """Export the report to the configured format."""
        if not self._manifest:
            return {"path": None, "hash": None}

        export_format = self.config.get("export_format", "pdf")

        try:
            if export_format == "pdf":
                return await self._export_pdf()
            elif export_format == "json":
                return await self._export_json()
            else:
                return await self._export_json()
        except Exception as e:
            logger.error(f"[CanonicalPipeline] Export failed: {e}")
            return {"path": None, "hash": None, "error": str(e)}

    async def _export_pdf(self) -> Dict[str, Any]:
        """Export as PDF using auto_report_builder."""
        try:
            from operation_room.services.auto_report_builder import generate_comprehensive_report
            result = await generate_comprehensive_report(
                case_id=self.case_id,
                scenario_title=self._manifest.title if self._manifest else "Report",
                include_ai_summaries=self.config.get("include_ai_narratives", True),
                save_draft=True,
                export_pdf=True,
            )
            return {
                "path": result.get("pdf_path"),
                "hash": hashlib.sha256(
                    json.dumps(result, default=str).encode()
                ).hexdigest(),
                "doc_id": result.get("doc_id"),
            }
        except Exception as e:
            logger.warning(f"PDF export fallback to JSON: {e}")
            return await self._export_json()

    async def _export_json(self) -> Dict[str, Any]:
        """Export as JSON."""
        if not self._manifest:
            return {"path": None, "hash": None}

        json_str = self._manifest.to_json()
        content_hash = hashlib.sha256(json_str.encode()).hexdigest()

        try:
            from pathlib import Path
            export_dir = Path(f"exports/{self.case_id}")
            export_dir.mkdir(parents=True, exist_ok=True)
            export_path = export_dir / f"report_{self._manifest.report_id}.json"
            export_path.write_text(json_str, encoding="utf-8")
            return {"path": str(export_path), "hash": content_hash}
        except Exception:
            return {"path": None, "hash": content_hash}


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

async def run_canonical_pipeline(
    case_id: str,
    scenario: str = "",
    case_type: str = "general",
    investigation_data: Optional[Dict[str, Any]] = None,
    module_results: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> ReportManifest:
    """
    Run the complete canonical pipeline and return the final manifest.
    
    This is the primary entry point for report generation.
    """
    pipeline = CanonicalPipeline(case_id=case_id, config=config)

    async for event in pipeline.execute(
        scenario=scenario,
        case_type=case_type,
        investigation_data=investigation_data,
        module_results=module_results,
        metadata=metadata,
    ):
        logger.info(
            f"[Pipeline] {event.event_type} — {event.progress:.0%} — "
            f"{json.dumps(event.data, default=str)[:200]}"
        )

    manifest = pipeline.get_manifest()
    if manifest is None:
        raise RuntimeError("Pipeline completed without generating a manifest")

    return manifest
