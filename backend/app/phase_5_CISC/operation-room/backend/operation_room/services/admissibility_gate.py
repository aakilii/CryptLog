"""
Admissibility Gate — Phase 6.

Court-readiness validator that enforces strict quality gates before
a report can be exported. Implements fail-closed policy with signed
investigator override for non-critical failures.

Checks:
1. Evidence integrity — all citations resolve to valid evidence keys
2. Citation density — minimum citations per section
3. Content hash verification — SHA-256 content integrity
4. Orphan detection — no dangling evidence references
5. Legal compliance — IT Act 2000 §65B metadata presence
6. Methodology disclosure — forensic methods documented
7. Confidence coverage — all sections have confidence scores
8. Chain of custody — CoC entries exist for this case
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from operation_room.services.canonical_contracts import (
    AdmissibilityResult,
    AdmissibilityVerdict,
    ConfidenceLevel,
    ReportManifest,
    ReportStatus,
    SectionContract,
    SectionStatus,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ADMISSIBILITY CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

class AdmissibilityGate:
    """
    Court-readiness validator for forensic reports.
    
    Usage:
        gate = AdmissibilityGate(case_id)
        result = gate.evaluate(manifest)
        
        if result.is_exportable():
            # Proceed to export
        elif result.override_allowed:
            result = gate.apply_override(result, "investigator_id", "Justification")
    """

    # Minimum citation density (1 per 300 words)
    MIN_CITATION_DENSITY = 1 / 300

    # Minimum sections that must pass
    MIN_PASS_RATIO = 0.7

    # Mandatory section keys that MUST be present and approved
    MANDATORY_SECTIONS = {
        "exec_summary", "case_overview", "key_findings",
        "chain_of_custody", "evidence_appendix",
    }

    def __init__(self, case_id: str):
        self.case_id = case_id

    def evaluate(self, manifest: ReportManifest) -> AdmissibilityResult:
        """
        Run all admissibility checks on the report manifest.
        
        Returns:
            AdmissibilityResult with per-check details
        """
        result = AdmissibilityResult()
        checks_run = 0

        # Check 1: All sections approved
        check = self._check_section_status(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 2: Mandatory sections present
        check = self._check_mandatory_sections(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 3: Evidence citation integrity
        check = self._check_citation_integrity(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 4: No orphan citations
        check = self._check_orphan_citations(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 5: Citation density
        check = self._check_citation_density(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 6: Content hash integrity
        check = self._check_content_hash(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 7: Confidence coverage
        check = self._check_confidence_coverage(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 8: Methodology section
        check = self._check_methodology(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 9: Chain of custody
        check = self._check_chain_of_custody(manifest)
        self._record_check(result, check)
        checks_run += 1

        # Check 10: India IT Act compliance metadata
        check = self._check_legal_metadata(manifest)
        self._record_check(result, check)
        checks_run += 1

        result.total_checks = checks_run

        # Determine overall verdict
        if result.checks_failed == 0:
            result.verdict = AdmissibilityVerdict.PASS
        elif any(f.get("severity") == "HARD" for f in result.failures):
            result.verdict = AdmissibilityVerdict.FAIL_HARD
            result.override_allowed = False
        elif result.checks_failed > 0:
            result.verdict = AdmissibilityVerdict.FAIL_SOFT
            result.override_allowed = True

        if result.checks_warned > 0 and result.checks_failed == 0:
            result.verdict = AdmissibilityVerdict.WARN

        logger.info(
            f"[AdmissibilityGate] Case {self.case_id}: "
            f"{result.verdict.value} — "
            f"{result.checks_passed}/{result.total_checks} passed, "
            f"{result.checks_failed} failed, "
            f"{result.checks_warned} warned"
        )

        return result

    def apply_override(
        self,
        result: AdmissibilityResult,
        overrider_id: str,
        justification: str,
    ) -> AdmissibilityResult:
        """
        Apply a signed investigator override to a soft-failed result.
        
        Args:
            result: The AdmissibilityResult to override
            overrider_id: ID of the investigator applying the override
            justification: Reason for override
            
        Returns:
            Updated AdmissibilityResult
        """
        if not result.override_allowed:
            raise ValueError(
                "Override not allowed for FAIL_HARD verdicts. "
                "Fix the issues and re-evaluate."
            )

        if result.verdict not in (AdmissibilityVerdict.FAIL_SOFT, AdmissibilityVerdict.WARN):
            raise ValueError(
                f"Override only applicable to FAIL_SOFT or WARN verdicts, "
                f"got {result.verdict.value}"
            )

        result.override_applied = True
        result.overrider_id = overrider_id
        result.override_justification = justification

        logger.info(
            f"[AdmissibilityGate] Override applied by {overrider_id}: {justification}"
        )

        return result

    # ─── Individual Checks ────────────────────────────────────────────────

    def _check_section_status(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that all sections are in APPROVED or SKIPPED status."""
        non_approved = [
            s.section_key for s in manifest.sections
            if s.status not in (SectionStatus.APPROVED, SectionStatus.SKIPPED)
        ]
        passed = len(non_approved) == 0
        return {
            "check": "section_status",
            "passed": passed,
            "severity": "HARD" if non_approved else None,
            "message": (
                "All sections approved" if passed
                else f"{len(non_approved)} sections not approved: {non_approved}"
            ),
        }

    def _check_mandatory_sections(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that all mandatory sections are present."""
        present_keys = {s.section_key for s in manifest.sections}
        missing = self.MANDATORY_SECTIONS - present_keys
        passed = len(missing) == 0
        return {
            "check": "mandatory_sections",
            "passed": passed,
            "severity": "HARD" if missing else None,
            "message": (
                "All mandatory sections present" if passed
                else f"Missing mandatory sections: {missing}"
            ),
        }

    def _check_citation_integrity(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that all citations reference valid evidence keys."""
        total_citations = 0
        invalid_citations = []

        for section in manifest.sections:
            for citation in section.citations:
                total_citations += 1
                if not citation.evidence_key_id:
                    invalid_citations.append({
                        "section": section.section_key,
                        "citation_id": citation.citation_id,
                        "issue": "Empty evidence key ID",
                    })

        passed = len(invalid_citations) == 0
        return {
            "check": "citation_integrity",
            "passed": passed,
            "severity": "SOFT" if invalid_citations else None,
            "message": (
                f"All {total_citations} citations valid" if passed
                else f"{len(invalid_citations)} invalid citations"
            ),
            "details": invalid_citations[:5],
        }

    def _check_orphan_citations(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check for orphan citations (references to non-existent evidence)."""
        total_orphans = sum(len(s.orphan_citations) for s in manifest.sections)
        orphan_details = [
            {"section": s.section_key, "orphans": s.orphan_citations}
            for s in manifest.sections
            if s.orphan_citations
        ]
        passed = total_orphans == 0
        return {
            "check": "orphan_citations",
            "passed": passed,
            "severity": "SOFT" if total_orphans else None,
            "message": (
                "No orphan citations" if passed
                else f"{total_orphans} orphan citations detected"
            ),
            "details": orphan_details,
        }

    def _check_citation_density(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check minimum citation density across sections."""
        low_density = []
        for section in manifest.sections:
            if section.word_count > 100:  # Only check substantial sections
                density = len(section.citations) / max(section.word_count, 1)
                if density < self.MIN_CITATION_DENSITY:
                    low_density.append({
                        "section": section.section_key,
                        "word_count": section.word_count,
                        "citations": len(section.citations),
                        "density": round(density, 5),
                    })

        passed = len(low_density) == 0
        return {
            "check": "citation_density",
            "passed": passed,
            "severity": None,  # Warning only
            "is_warning": True,
            "message": (
                "Citation density acceptable" if passed
                else f"{len(low_density)} sections below minimum citation density"
            ),
            "details": low_density,
        }

    def _check_content_hash(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Verify content hash integrity."""
        if not manifest.content_hash:
            return {
                "check": "content_hash",
                "passed": False,
                "severity": "SOFT",
                "message": "No content hash computed",
            }

        # Recompute and compare
        computed = manifest.compute_content_hash()
        passed = computed == manifest.content_hash
        return {
            "check": "content_hash",
            "passed": passed,
            "severity": "HARD" if not passed else None,
            "message": (
                f"Content hash verified: {computed[:16]}..." if passed
                else f"Hash mismatch: stored={manifest.content_hash[:16]}... computed={computed[:16]}..."
            ),
        }

    def _check_confidence_coverage(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that all sections have confidence scores."""
        no_confidence = [
            s.section_key for s in manifest.sections
            if s.confidence == 0.0 and s.status == SectionStatus.APPROVED
        ]
        passed = len(no_confidence) == 0
        return {
            "check": "confidence_coverage",
            "passed": passed,
            "severity": None,  # Warning only
            "is_warning": True,
            "message": (
                "All sections have confidence scores" if passed
                else f"{len(no_confidence)} sections without confidence scores"
            ),
        }

    def _check_methodology(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that methodology section exists and has content."""
        methodology = next(
            (s for s in manifest.sections if s.section_key == "methodology"),
            None,
        )
        if methodology and methodology.word_count > 50:
            return {
                "check": "methodology",
                "passed": True,
                "message": f"Methodology section present ({methodology.word_count} words)",
            }
        return {
            "check": "methodology",
            "passed": False,
            "severity": "SOFT",
            "message": "Methodology section missing or insufficient",
        }

    def _check_chain_of_custody(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check that chain-of-custody section exists."""
        coc = next(
            (s for s in manifest.sections if s.section_key == "chain_of_custody"),
            None,
        )
        if coc and coc.word_count > 20:
            return {
                "check": "chain_of_custody",
                "passed": True,
                "message": "Chain of custody section present",
            }
        
        # Also check if CoC entries exist in the database
        try:
            from operation_room.database import open_vault
            conn = open_vault(self.case_id)
            try:
                count = conn.execute(
                    "SELECT COUNT(*) FROM chain_of_custody WHERE case_id = ?",
                    [self.case_id],
                ).fetchone()[0]
                if count > 0:
                    return {
                        "check": "chain_of_custody",
                        "passed": True,
                        "is_warning": True,
                        "message": f"CoC section thin but {count} database entries exist",
                    }
            finally:
                conn.close()
        except Exception:
            pass

        return {
            "check": "chain_of_custody",
            "passed": False,
            "severity": "HARD",
            "message": "Chain of custody section missing — required for court admissibility",
        }

    def _check_legal_metadata(self, manifest: ReportManifest) -> Dict[str, Any]:
        """Check India IT Act 2000 compliance metadata."""
        meta = manifest.metadata
        has_it_act = meta.get("it_act_section_65b", False)
        has_classification = meta.get("classification", None) is not None
        has_examiner = meta.get("examining_officer", None) is not None

        issues = []
        if not has_it_act:
            issues.append("IT Act §65B certification not recorded")
        if not has_classification:
            issues.append("Report classification not specified")
        if not has_examiner:
            issues.append("Examining officer not identified")

        passed = len(issues) == 0
        return {
            "check": "legal_metadata",
            "passed": passed,
            "severity": None,  # Warning for now
            "is_warning": True,
            "message": (
                "Legal metadata complete" if passed
                else f"Legal metadata incomplete: {'; '.join(issues)}"
            ),
        }

    # ─── Internal Helpers ─────────────────────────────────────────────────

    def _record_check(self, result: AdmissibilityResult, check: Dict[str, Any]) -> None:
        """Record a check result."""
        if check.get("passed"):
            result.checks_passed += 1
        elif check.get("is_warning"):
            result.checks_warned += 1
            result.warnings.append(check)
        else:
            result.checks_failed += 1
            result.failures.append(check)
