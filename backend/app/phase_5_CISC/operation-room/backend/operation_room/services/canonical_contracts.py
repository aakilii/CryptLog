"""
Canonical Pipeline Contracts — Phase 1.

Deterministic data-transfer objects (DTOs) and enumerations that enforce
strict type safety across the entire court-ready forensic pipeline.

Every service in the pipeline communicates through these contracts,
ensuring no ad-hoc dictionaries leak between phases and all state
transitions are auditable.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class ReportStatus(str, Enum):
    """Deterministic state machine for report lifecycle."""
    DRAFT = "DRAFT"
    TEMPLATE_SELECTED = "TEMPLATE_SELECTED"
    DATA_GATHERING = "DATA_GATHERING"
    EVIDENCE_BINDING = "EVIDENCE_BINDING"
    SECTION_GENERATION = "SECTION_GENERATION"
    SECTION_REVIEW = "SECTION_REVIEW"
    ASSEMBLY = "ASSEMBLY"
    ADMISSIBILITY_CHECK = "ADMISSIBILITY_CHECK"
    ADMISSIBILITY_FAILED = "ADMISSIBILITY_FAILED"
    ADMISSIBILITY_OVERRIDE = "ADMISSIBILITY_OVERRIDE"
    EXPORT_PENDING = "EXPORT_PENDING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @classmethod
    def valid_transitions(cls) -> Dict["ReportStatus", List["ReportStatus"]]:
        """Return the set of legal state transitions."""
        return {
            cls.DRAFT: [cls.TEMPLATE_SELECTED, cls.CANCELLED],
            cls.TEMPLATE_SELECTED: [cls.DATA_GATHERING, cls.DRAFT, cls.CANCELLED],
            cls.DATA_GATHERING: [cls.EVIDENCE_BINDING, cls.FAILED, cls.CANCELLED],
            cls.EVIDENCE_BINDING: [cls.SECTION_GENERATION, cls.FAILED, cls.CANCELLED],
            cls.SECTION_GENERATION: [cls.SECTION_REVIEW, cls.ASSEMBLY, cls.FAILED, cls.CANCELLED],
            cls.SECTION_REVIEW: [cls.ASSEMBLY, cls.SECTION_GENERATION, cls.CANCELLED],
            cls.ASSEMBLY: [cls.ADMISSIBILITY_CHECK, cls.FAILED, cls.CANCELLED],
            cls.ADMISSIBILITY_CHECK: [cls.EXPORT_PENDING, cls.ADMISSIBILITY_FAILED, cls.FAILED],
            cls.ADMISSIBILITY_FAILED: [cls.ADMISSIBILITY_OVERRIDE, cls.DRAFT, cls.CANCELLED],
            cls.ADMISSIBILITY_OVERRIDE: [cls.EXPORT_PENDING, cls.CANCELLED],
            cls.EXPORT_PENDING: [cls.EXPORTING, cls.CANCELLED],
            cls.EXPORTING: [cls.COMPLETED, cls.FAILED],
            cls.COMPLETED: [],
            cls.FAILED: [cls.DRAFT],
            cls.CANCELLED: [cls.DRAFT],
        }

    def can_transition_to(self, target: "ReportStatus") -> bool:
        return target in self.valid_transitions().get(self, [])


class SectionStatus(str, Enum):
    """Status of an individual report section."""
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    BINDING_EVIDENCE = "BINDING_EVIDENCE"
    BOUND = "BOUND"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AdmissibilityVerdict(str, Enum):
    """Result of an admissibility gate check."""
    PASS = "PASS"
    WARN = "WARN"
    FAIL_SOFT = "FAIL_SOFT"   # Non-critical, overrideable
    FAIL_HARD = "FAIL_HARD"   # Critical, blocks export


class EvidenceCitationType(str, Enum):
    """Types of inline evidence citations."""
    DIRECT = "DIRECT"         # Direct quote from evidence
    SUMMARY = "SUMMARY"       # Summarised finding
    METRIC = "METRIC"         # Numeric value from analysis
    CHART_REF = "CHART_REF"   # Reference to a chart/visualisation
    TABLE_REF = "TABLE_REF"   # Reference to a data table
    COC_REF = "COC_REF"       # Chain-of-custody reference


class ConfidenceLevel(str, Enum):
    """ODNI ICD-203 confidence levels for court reporting."""
    VERY_HIGH = "VERY_HIGH"   # >90%
    HIGH = "HIGH"             # 75-90%
    MODERATE = "MODERATE"     # 50-75%
    LOW = "LOW"               # 25-50%
    VERY_LOW = "VERY_LOW"     # <25%

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.90:
            return cls.VERY_HIGH
        if score >= 0.75:
            return cls.HIGH
        if score >= 0.50:
            return cls.MODERATE
        if score >= 0.25:
            return cls.LOW
        return cls.VERY_LOW


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TRANSFER OBJECTS
# ═══════════════════════════════════════════════════════════════════════════════

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str = "RPT") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@dataclass
class EvidenceCitation:
    """An inline citation binding an assertion to evidence."""
    citation_id: str = field(default_factory=lambda: _new_id("CIT"))
    evidence_key_id: str = ""
    citation_type: EvidenceCitationType = EvidenceCitationType.DIRECT
    source_module: str = ""
    confidence: float = 0.0
    assertion_text: str = ""          # The claim being made
    evidence_summary: str = ""        # AI-safe summary of the evidence
    page_ref: Optional[int] = None    # Page number in final report
    section_ref: Optional[str] = None # Section key

    def to_inline_tag(self) -> str:
        """Generate the inline citation tag for embedding in text."""
        return f"[EVD:{self.evidence_key_id}|{self.citation_type.value}|{self.confidence:.2f}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "evidence_key_id": self.evidence_key_id,
            "citation_type": self.citation_type.value,
            "source_module": self.source_module,
            "confidence": self.confidence,
            "assertion_text": self.assertion_text,
            "evidence_summary": self.evidence_summary,
            "page_ref": self.page_ref,
            "section_ref": self.section_ref,
        }


@dataclass
class SectionContract:
    """Contract for a single report section."""
    section_id: str = field(default_factory=lambda: _new_id("SEC"))
    section_key: str = ""
    section_title: str = ""
    sort_order: int = 0
    status: SectionStatus = SectionStatus.PENDING
    content: str = ""
    content_hash: str = ""
    citations: List[EvidenceCitation] = field(default_factory=list)
    chart_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    is_ai_generated: bool = False
    generator_model: str = ""
    dependencies: List[str] = field(default_factory=list)  # section_keys this depends on
    word_count: int = 0
    evidence_key_count: int = 0
    orphan_citations: List[str] = field(default_factory=list)
    generated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None

    def compute_hash(self) -> str:
        """Compute SHA-256 of section content for integrity."""
        self.content_hash = hashlib.sha256(
            self.content.encode("utf-8")
        ).hexdigest()
        return self.content_hash

    def update_metrics(self) -> None:
        """Recompute derived metrics."""
        self.word_count = len(self.content.split()) if self.content else 0
        self.evidence_key_count = len(self.citations)
        self.confidence_level = ConfidenceLevel.from_score(self.confidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_key": self.section_key,
            "section_title": self.section_title,
            "sort_order": self.sort_order,
            "status": self.status.value,
            "content": self.content,
            "content_hash": self.content_hash,
            "citations": [c.to_dict() for c in self.citations],
            "chart_ids": self.chart_ids,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "is_ai_generated": self.is_ai_generated,
            "generator_model": self.generator_model,
            "word_count": self.word_count,
            "evidence_key_count": self.evidence_key_count,
            "orphan_citations": self.orphan_citations,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


@dataclass
class AdmissibilityResult:
    """Result of an admissibility gate check."""
    gate_id: str = field(default_factory=lambda: _new_id("GATE"))
    verdict: AdmissibilityVerdict = AdmissibilityVerdict.PASS
    checks_passed: int = 0
    checks_failed: int = 0
    checks_warned: int = 0
    total_checks: int = 0
    failures: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    override_allowed: bool = False
    override_applied: bool = False
    overrider_id: Optional[str] = None
    override_justification: Optional[str] = None
    checked_at: datetime = field(default_factory=_utcnow)

    def is_exportable(self) -> bool:
        """Whether the report can proceed to export."""
        if self.verdict in (AdmissibilityVerdict.PASS, AdmissibilityVerdict.WARN):
            return True
        if self.verdict == AdmissibilityVerdict.FAIL_SOFT and self.override_applied:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "verdict": self.verdict.value,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "checks_warned": self.checks_warned,
            "total_checks": self.total_checks,
            "failures": self.failures,
            "warnings": self.warnings,
            "override_allowed": self.override_allowed,
            "override_applied": self.override_applied,
            "overrider_id": self.overrider_id,
            "override_justification": self.override_justification,
            "is_exportable": self.is_exportable(),
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class ReportManifest:
    """Complete manifest for a canonical report."""
    report_id: str = field(default_factory=lambda: _new_id("RPT"))
    case_id: str = ""
    investigation_id: Optional[str] = None
    template_key: str = "technical"
    title: str = ""
    status: ReportStatus = ReportStatus.DRAFT
    sections: List[SectionContract] = field(default_factory=list)
    admissibility: Optional[AdmissibilityResult] = None
    total_evidence_keys: int = 0
    total_citations: int = 0
    total_orphan_citations: int = 0
    overall_confidence: float = 0.0
    overall_confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    content_hash: str = ""
    export_hash: Optional[str] = None
    export_format: Optional[str] = None
    export_path: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    completed_at: Optional[datetime] = None
    generation_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, target: ReportStatus) -> None:
        """Enforce deterministic state transitions."""
        if not self.status.can_transition_to(target):
            raise ValueError(
                f"Invalid state transition: {self.status.value} → {target.value}. "
                f"Allowed: {[s.value for s in ReportStatus.valid_transitions().get(self.status, [])]}"
            )
        self.status = target
        self.updated_at = _utcnow()

    def compute_content_hash(self) -> str:
        """Compute SHA-256 hash of all section content."""
        combined = "".join(s.content for s in self.sections)
        self.content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return self.content_hash

    def update_rollup_metrics(self) -> None:
        """Recompute all roll-up metrics from sections."""
        self.total_citations = sum(len(s.citations) for s in self.sections)
        self.total_orphan_citations = sum(len(s.orphan_citations) for s in self.sections)
        self.total_evidence_keys = len(set(
            c.evidence_key_id for s in self.sections for c in s.citations
        ))
        if self.sections:
            self.overall_confidence = sum(s.confidence for s in self.sections) / len(self.sections)
        else:
            self.overall_confidence = 0.0
        self.overall_confidence_level = ConfidenceLevel.from_score(self.overall_confidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            "template_key": self.template_key,
            "title": self.title,
            "status": self.status.value,
            "sections": [s.to_dict() for s in self.sections],
            "admissibility": self.admissibility.to_dict() if self.admissibility else None,
            "total_evidence_keys": self.total_evidence_keys,
            "total_citations": self.total_citations,
            "total_orphan_citations": self.total_orphan_citations,
            "overall_confidence": self.overall_confidence,
            "overall_confidence_level": self.overall_confidence_level.value,
            "content_hash": self.content_hash,
            "export_hash": self.export_hash,
            "export_format": self.export_format,
            "export_path": self.export_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "generation_time_ms": self.generation_time_ms,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class PipelineCheckpoint:
    """Checkpoint for pipeline resumability."""
    checkpoint_id: str = field(default_factory=lambda: _new_id("CKPT"))
    report_id: str = ""
    case_id: str = ""
    current_status: ReportStatus = ReportStatus.DRAFT
    completed_sections: List[str] = field(default_factory=list)  # section_keys
    pending_sections: List[str] = field(default_factory=list)
    failed_sections: List[str] = field(default_factory=list)
    evidence_keys_bound: List[str] = field(default_factory=list)
    manifest_snapshot: Optional[str] = None  # JSON string of ReportManifest
    created_at: datetime = field(default_factory=_utcnow)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "report_id": self.report_id,
            "case_id": self.case_id,
            "current_status": self.current_status.value,
            "completed_sections": self.completed_sections,
            "pending_sections": self.pending_sections,
            "failed_sections": self.failed_sections,
            "evidence_keys_bound": self.evidence_keys_bound,
            "created_at": self.created_at.isoformat(),
            "error": self.error,
        }
