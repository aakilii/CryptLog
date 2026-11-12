"""
Evidence Binder — Phase 3.

Inline evidence-key citation engine that binds AI assertions to evidence.

The binder:
1. Injects evidence keys into LLM prompts (key-only mode)
2. Parses [EVD:key_id] citations from LLM output
3. Hydrates citations with full evidence values for final report
4. Detects orphan citations (references to non-existent evidence)
5. Validates citation density (minimum citations per section)
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from operation_room.services.canonical_contracts import (
    EvidenceCitation,
    EvidenceCitationType,
    SectionContract,
    SectionStatus,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CITATION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# Pattern: [EVD:EVD-XXXXXXXX|TYPE|0.85]
CITATION_PATTERN = re.compile(
    r'\[EVD:(?P<key_id>[A-Z0-9\-]+)'
    r'(?:\|(?P<type>[A-Z_]+))?'
    r'(?:\|(?P<confidence>[0-9.]+))?\]'
)

# Simplified pattern: [EVD:EVD-XXXXXXXX]
SIMPLE_CITATION_PATTERN = re.compile(
    r'\[EVD:(?P<key_id>[A-Z0-9\-]+)\]'
)

# LLM reference pattern: [EVIDENCE:key_id:category:name]
LLM_REFERENCE_PATTERN = re.compile(
    r'\[EVIDENCE:(?P<key_id>[A-Z0-9\-]+):(?P<category>[a-z_]+):(?P<name>[^\]]+)\]'
)


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE BINDER
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceBinder:
    """
    Binds AI-generated text to evidence keys from ReportEvidenceService.
    
    Usage:
        binder = EvidenceBinder(case_id)
        
        # 1. Build prompt with evidence keys
        prompt = binder.build_evidence_prompt(section_key, evidence_keys)
        
        # 2. Send prompt to LLM, get response with [EVD:] citations
        response = await llm.generate(prompt)
        
        # 3. Parse and validate citations
        section = binder.bind_citations(section_contract, response)
        
        # 4. Hydrate for final report
        hydrated = binder.hydrate_section(section)
    """

    # Minimum citation density: at least 1 citation per 200 words
    MIN_CITATION_DENSITY = 1 / 200

    def __init__(self, case_id: str):
        self.case_id = case_id
        self._evidence_service = None
        self._key_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def evidence_service(self):
        if self._evidence_service is None:
            try:
                from operation_room.services.report_evidence_service import get_report_evidence_service
                self._evidence_service = get_report_evidence_service(self.case_id)
            except Exception as e:
                logger.warning(f"Evidence service unavailable: {e}")
        return self._evidence_service

    def build_evidence_prompt(
        self,
        section_key: str,
        section_title: str,
        evidence_keys: List[Dict[str, Any]],
        case_context: Optional[Dict[str, Any]] = None,
        module_summaries: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build an LLM prompt that includes evidence key references.
        
        The prompt instructs the LLM to cite evidence using [EVD:key_id] tags
        instead of inventing data.
        
        Args:
            section_key: Section identifier
            section_title: Human-readable section title
            evidence_keys: List of evidence key dicts (key_id, key_name, summary)
            case_context: Case metadata
            module_summaries: Analysis module summaries
            
        Returns:
            Formatted prompt string
        """
        # Build evidence manifest for LLM
        evidence_manifest = []
        for ek in evidence_keys:
            key_id = ek.get("key_id", "")
            key_name = ek.get("key_name", "")
            summary = ek.get("summary", "")
            category = ek.get("category", "")
            evidence_manifest.append(
                f"  - {key_id} ({category}/{key_name}): {summary}"
            )
            # Cache for later
            self._key_cache[key_id] = ek

        manifest_text = "\n".join(evidence_manifest) if evidence_manifest else "  (No evidence keys available)"

        case_text = ""
        if case_context:
            case_text = f"""
Case Information:
- Case ID: {case_context.get('case_id', 'N/A')}
- Title: {case_context.get('title', 'N/A')}
- Status: {case_context.get('status', 'N/A')}
"""

        summary_text = ""
        if module_summaries:
            summary_text = f"\nModule Analysis Data:\n{json.dumps(module_summaries, indent=2, default=str)[:3000]}\n"

        prompt = f"""You are a senior forensic investigator writing the "{section_title}" section of a court-admissible forensic investigation report.

CRITICAL RULES — COURT ADMISSIBILITY:
1. EVERY factual assertion MUST be supported by an evidence citation.
2. Use the format [EVD:KEY_ID] to cite evidence. Example: "The suspect accessed the file at 14:32 UTC [EVD:EVD-A1B2C3D4]."
3. NEVER fabricate IP addresses, timestamps, file names, or user IDs.
4. If the evidence is insufficient, state: "Evidence insufficient to determine [aspect]."
5. Use ODNI ICD-203 confidence language (High/Moderate/Low confidence).
6. Write in professional, third-person forensic tone.
7. Include specific metrics and numbers from the evidence keys.
{case_text}
Available Evidence Keys:
{manifest_text}
{summary_text}
Write the "{section_title}" section now. Use markdown formatting.
Cite evidence using [EVD:KEY_ID] tags throughout your analysis.
Every paragraph should contain at least one evidence citation.
"""
        return prompt

    def bind_citations(
        self,
        section: SectionContract,
        llm_response: str,
    ) -> SectionContract:
        """
        Parse [EVD:] citations from LLM response and bind to section.
        
        Args:
            section: SectionContract to update
            llm_response: Raw LLM output containing [EVD:] tags
            
        Returns:
            Updated SectionContract with citations and orphan detection
        """
        section.content = llm_response
        section.status = SectionStatus.BINDING_EVIDENCE

        # Parse all citation patterns
        citations = []
        orphans = []
        seen_keys = set()

        # Full pattern: [EVD:key_id|TYPE|confidence]
        for match in CITATION_PATTERN.finditer(llm_response):
            key_id = match.group("key_id")
            cite_type = match.group("type") or "DIRECT"
            confidence = float(match.group("confidence") or "0.5")

            if key_id in self._key_cache:
                cached = self._key_cache[key_id]
                citation = EvidenceCitation(
                    evidence_key_id=key_id,
                    citation_type=self._parse_citation_type(cite_type),
                    source_module=cached.get("source_module", ""),
                    confidence=confidence,
                    assertion_text=self._extract_assertion_context(llm_response, match.start()),
                    evidence_summary=cached.get("summary", ""),
                    section_ref=section.section_key,
                )
                citations.append(citation)
                seen_keys.add(key_id)
            else:
                orphans.append(key_id)

        # Also handle simple [EVD:key_id] pattern
        for match in SIMPLE_CITATION_PATTERN.finditer(llm_response):
            key_id = match.group("key_id")
            if key_id not in seen_keys:
                if key_id in self._key_cache:
                    cached = self._key_cache[key_id]
                    citation = EvidenceCitation(
                        evidence_key_id=key_id,
                        citation_type=EvidenceCitationType.DIRECT,
                        source_module=cached.get("source_module", ""),
                        confidence=0.5,
                        assertion_text=self._extract_assertion_context(llm_response, match.start()),
                        evidence_summary=cached.get("summary", ""),
                        section_ref=section.section_key,
                    )
                    citations.append(citation)
                    seen_keys.add(key_id)
                elif key_id not in orphans:
                    orphans.append(key_id)

        section.citations = citations
        section.orphan_citations = orphans
        section.is_ai_generated = True
        section.generated_at = datetime.now(timezone.utc)
        section.update_metrics()
        section.compute_hash()

        # Validate citation density
        word_count = section.word_count
        citation_count = len(citations)
        if word_count > 0 and citation_count / word_count < self.MIN_CITATION_DENSITY:
            logger.warning(
                f"[EvidenceBinder] Section '{section.section_key}' has low citation density: "
                f"{citation_count} citations / {word_count} words "
                f"(minimum: {self.MIN_CITATION_DENSITY:.4f})"
            )

        if orphans:
            logger.warning(
                f"[EvidenceBinder] Section '{section.section_key}' has {len(orphans)} orphan citations: {orphans}"
            )

        section.status = SectionStatus.BOUND
        return section

    def hydrate_section(
        self,
        section: SectionContract,
        user_id: str = "system",
    ) -> str:
        """
        Replace [EVD:key_id] tags with full evidence values for final output.
        
        Args:
            section: Bound SectionContract
            user_id: User requesting hydration (for audit trail)
            
        Returns:
            Hydrated content with evidence values
        """
        content = section.content
        if not self.evidence_service:
            return content

        def _replace_citation(match: re.Match) -> str:
            key_id = match.group("key_id")
            try:
                value = self.evidence_service.get_for_report(
                    key_id=key_id,
                    user_id=user_id,
                )
                if value:
                    return value
            except Exception as e:
                logger.warning(f"Failed to hydrate evidence {key_id}: {e}")
            return f"[Evidence: {key_id}]"

        # Replace full pattern
        content = CITATION_PATTERN.sub(_replace_citation, content)
        # Replace simple pattern
        content = SIMPLE_CITATION_PATTERN.sub(_replace_citation, content)

        return content

    def get_evidence_keys_for_section(
        self,
        section_key: str,
    ) -> List[Dict[str, Any]]:
        """
        Get relevant evidence keys for a section from the evidence service.
        
        Args:
            section_key: Section key to match
            
        Returns:
            List of evidence key dicts
        """
        if not self.evidence_service:
            return []

        try:
            keys = self.evidence_service.get_keys_by_section(section_key)
            return [k.to_dict() for k in keys]
        except Exception as e:
            logger.warning(f"Failed to get evidence keys for section '{section_key}': {e}")
            return []

    def get_all_evidence_keys(self) -> List[Dict[str, Any]]:
        """Get all evidence keys for the case."""
        if not self.evidence_service:
            return []

        try:
            keys = self.evidence_service.get_all_keys()
            result = [k.to_dict() for k in keys]
            # Cache them all
            for k in result:
                self._key_cache[k["key_id"]] = k
            return result
        except Exception as e:
            logger.warning(f"Failed to get evidence keys: {e}")
            return []

    def validate_section_citations(
        self,
        section: SectionContract,
    ) -> Dict[str, Any]:
        """
        Validate citations in a section for court admissibility.
        
        Returns validation report with pass/fail status.
        """
        results = {
            "section_key": section.section_key,
            "total_citations": len(section.citations),
            "orphan_citations": len(section.orphan_citations),
            "word_count": section.word_count,
            "citation_density": 0.0,
            "checks": [],
            "passed": True,
        }

        # Check 1: Has any citations
        has_citations = len(section.citations) > 0
        results["checks"].append({
            "check": "has_citations",
            "passed": has_citations,
            "message": f"{len(section.citations)} citations found" if has_citations else "No citations found",
        })
        if not has_citations:
            results["passed"] = False

        # Check 2: No orphan citations
        no_orphans = len(section.orphan_citations) == 0
        results["checks"].append({
            "check": "no_orphans",
            "passed": no_orphans,
            "message": f"No orphan citations" if no_orphans else f"{len(section.orphan_citations)} orphan citations: {section.orphan_citations}",
        })
        if not no_orphans:
            results["passed"] = False

        # Check 3: Citation density
        if section.word_count > 0:
            density = len(section.citations) / section.word_count
            results["citation_density"] = density
            density_ok = density >= self.MIN_CITATION_DENSITY
            results["checks"].append({
                "check": "citation_density",
                "passed": density_ok,
                "message": f"Density: {density:.4f} (min: {self.MIN_CITATION_DENSITY:.4f})",
            })
            if not density_ok:
                results["passed"] = False

        # Check 4: Content hash exists
        has_hash = bool(section.content_hash)
        results["checks"].append({
            "check": "content_hash",
            "passed": has_hash,
            "message": f"Hash: {section.content_hash[:16]}..." if has_hash else "No content hash",
        })

        return results

    # ─── Internal Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_citation_type(type_str: str) -> EvidenceCitationType:
        """Parse citation type string to enum."""
        try:
            return EvidenceCitationType(type_str.upper())
        except (ValueError, AttributeError):
            return EvidenceCitationType.DIRECT

    @staticmethod
    def _extract_assertion_context(text: str, citation_pos: int, window: int = 120) -> str:
        """Extract the surrounding text context for a citation."""
        start = max(0, citation_pos - window)
        # Find sentence boundary
        sentence_start = text.rfind(".", start, citation_pos)
        if sentence_start == -1:
            sentence_start = start
        else:
            sentence_start += 1

        end = min(len(text), citation_pos + window)
        sentence_end = text.find(".", citation_pos, end)
        if sentence_end == -1:
            sentence_end = end
        else:
            sentence_end += 1

        return text[sentence_start:sentence_end].strip()


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_binders: Dict[str, EvidenceBinder] = {}


def get_evidence_binder(case_id: str) -> EvidenceBinder:
    global _binders
    if case_id not in _binders:
        _binders[case_id] = EvidenceBinder(case_id)
    return _binders[case_id]
