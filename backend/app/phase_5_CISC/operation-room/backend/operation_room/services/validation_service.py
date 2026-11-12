"""
Report Validation Service
========================
Fact checking, completeness analysis, and content verification for forensic reports.
"""

import hashlib
import re
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# Types & Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class ValidationSeverity(str, Enum):
    ERROR = "error"       # Must fix before export
    WARNING = "warning"   # Should fix
    INFO = "info"         # Suggestion only


class ValidationCategory(str, Enum):
    FACT = "fact"                 # Data accuracy
    CITATION = "citation"         # Evidence references
    COMPLETENESS = "completeness" # Coverage gaps
    CONSISTENCY = "consistency"   # Internal consistency
    FORMAT = "format"             # Formatting issues


class ValidationIssue(BaseModel):
    id: str
    category: ValidationCategory
    severity: ValidationSeverity
    title: str
    description: str
    location: Optional[str] = None  # Section or paragraph reference
    suggestion: Optional[str] = None
    evidence_ref: Optional[str] = None
    auto_fixable: bool = False


class ValidationResult(BaseModel):
    report_id: str
    case_id: str
    validated_at: str
    issues: List[ValidationIssue]
    summary: Dict[str, Any]
    integrity_hash: str
    is_valid: bool  # True if no ERROR-level issues


class CompletenessCheck(BaseModel):
    section: str
    is_present: bool
    word_count: int
    recommended_min: int
    coverage_score: float  # 0-1
    missing_elements: List[str]


class CompletenessResult(BaseModel):
    case_id: str
    checked_at: str
    sections: List[CompletenessCheck]
    overall_score: float  # 0-100
    required_sections_met: bool
    suggestions: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# Fact Checker Service
# ═══════════════════════════════════════════════════════════════════════════════

class FactCheckerService:
    """
    Validates factual claims in report content against case data.
    Checks timestamps, counts, hashes, and references.
    """

    def __init__(self, case_id: str):
        self.case_id = case_id
        self._issues: List[ValidationIssue] = []

    async def validate_content(
        self,
        content: str,
        case_data: Dict[str, Any],
        citations: Optional[List[Dict[str, Any]]] = None
    ) -> ValidationResult:
        """
        Validate report content against case data.
        
        Args:
            content: Report text content
            case_data: Dictionary of case facts from modules
            citations: List of citations to verify
        
        Returns:
            ValidationResult with issues found
        """
        self._issues = []
        
        # Run validation checks
        await self._check_timestamps(content, case_data)
        await self._check_counts(content, case_data)
        await self._check_citations(content, citations or [])
        await self._check_hashes(content, case_data)
        await self._check_actor_references(content, case_data)
        
        # Generate summary
        error_count = len([i for i in self._issues if i.severity == ValidationSeverity.ERROR])
        warning_count = len([i for i in self._issues if i.severity == ValidationSeverity.WARNING])
        
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        return ValidationResult(
            report_id=f"RPT-{self.case_id[:8]}",
            case_id=self.case_id,
            validated_at=datetime.utcnow().isoformat(),
            issues=self._issues,
            summary={
                "total_issues": len(self._issues),
                "errors": error_count,
                "warnings": warning_count,
                "categories": self._categorize_issues(),
            },
            integrity_hash=content_hash,
            is_valid=error_count == 0
        )

    async def _check_timestamps(self, content: str, case_data: Dict[str, Any]):
        """Verify timestamps mentioned in content match case data."""
        # Extract timestamps from content
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{2}:\d{2}(?::\d{2})?\s*(?:UTC|EST|PST)?',
        ]
        
        mentioned_timestamps = []
        for pattern in timestamp_patterns:
            matches = re.findall(pattern, content)
            mentioned_timestamps.extend(matches)
        
        # Get valid timestamps from case data
        valid_timestamps = set()
        if "timeline" in case_data:
            for event in case_data.get("timeline", {}).get("events", []):
                if "timestamp" in event:
                    valid_timestamps.add(event["timestamp"][:19])
        
        # Check for invalid timestamps
        for ts in mentioned_timestamps[:10]:  # Limit checks
            normalized = ts[:19] if len(ts) > 19 else ts
            if normalized and len(valid_timestamps) > 0:
                # Fuzzy match - if no similar timestamp found, flag it
                if not any(normalized in vts or vts in normalized for vts in valid_timestamps):
                    self._issues.append(ValidationIssue(
                        id=f"TS-{len(self._issues)+1}",
                        category=ValidationCategory.FACT,
                        severity=ValidationSeverity.WARNING,
                        title="Unverified Timestamp",
                        description=f"Timestamp '{ts}' not found in case timeline data",
                        suggestion="Verify this timestamp against source evidence",
                        auto_fixable=False
                    ))

    async def _check_counts(self, content: str, case_data: Dict[str, Any]):
        """Verify numerical counts match case data."""
        # Extract numbers with context
        count_patterns = [
            (r'(\d+)\s*(?:events?|entries|records)', "events"),
            (r'(\d+)\s*anomal(?:y|ies)', "anomalies"),
            (r'(\d+)\s*(?:nodes?|entities)', "nodes"),
            (r'(\d+)\s*(?:connections?|edges?|relationships?)', "edges"),
        ]
        
        for pattern, data_key in count_patterns:
            matches = re.findall(pattern, content.lower())
            for match in matches[:5]:  # Limit checks
                mentioned_count = int(match)
                
                # Get actual count from case data
                actual_count = None
                if data_key == "events" and "timeline" in case_data:
                    actual_count = case_data["timeline"].get("total_events")
                elif data_key == "anomalies" and "anomaly" in case_data:
                    actual_count = case_data["anomaly"].get("total_anomalies")
                elif data_key == "nodes" and "correlation" in case_data:
                    actual_count = case_data["correlation"].get("node_count")
                elif data_key == "edges" and "correlation" in case_data:
                    actual_count = case_data["correlation"].get("edge_count")
                
                if actual_count is not None and abs(mentioned_count - actual_count) > 2:
                    self._issues.append(ValidationIssue(
                        id=f"CNT-{len(self._issues)+1}",
                        category=ValidationCategory.FACT,
                        severity=ValidationSeverity.ERROR if abs(mentioned_count - actual_count) > actual_count * 0.1 else ValidationSeverity.WARNING,
                        title=f"Count Mismatch: {data_key}",
                        description=f"Report mentions {mentioned_count} {data_key}, but data shows {actual_count}",
                        suggestion=f"Update to reflect actual count: {actual_count}",
                        auto_fixable=True
                    ))

    async def _check_citations(self, content: str, citations: List[Dict[str, Any]]):
        """Verify all citations are valid and referenced."""
        # Extract citation references from content
        citation_refs = re.findall(r'\[([A-Z]+-\w+-\d+)\]', content)
        
        # Check each referenced citation exists
        valid_refs = {c.get("id") or c.get("ref") for c in citations}
        
        for ref in set(citation_refs):
            if ref not in valid_refs:
                self._issues.append(ValidationIssue(
                    id=f"CIT-{len(self._issues)+1}",
                    category=ValidationCategory.CITATION,
                    severity=ValidationSeverity.ERROR,
                    title="Invalid Citation",
                    description=f"Citation [{ref}] not found in evidence references",
                    evidence_ref=ref,
                    auto_fixable=False
                ))
        
        # Check for citations that should be added
        if len(citation_refs) < 3 and len(content) > 500:
            self._issues.append(ValidationIssue(
                id=f"CIT-{len(self._issues)+1}",
                category=ValidationCategory.CITATION,
                severity=ValidationSeverity.INFO,
                title="Low Citation Count",
                description="Consider adding more evidence citations to strengthen the report",
                suggestion="Add references to specific evidence items",
                auto_fixable=False
            ))

    async def _check_hashes(self, content: str, case_data: Dict[str, Any]):
        """Verify any hash references are valid."""
        # Extract hash references
        hash_patterns = [
            r'sha256:([a-f0-9]{8,64})',
            r'SHA-256:\s*([a-f0-9]{8,64})',
            r'hash:\s*([a-f0-9]{8,64})',
        ]
        
        mentioned_hashes = []
        for pattern in hash_patterns:
            matches = re.findall(pattern, content.lower())
            mentioned_hashes.extend(matches)
        
        # Verify hashes exist in case data
        valid_hashes = set()
        for module_data in case_data.values():
            if isinstance(module_data, dict):
                if "hash" in module_data:
                    valid_hashes.add(module_data["hash"][:16].lower())
                if "content_hash" in module_data:
                    valid_hashes.add(module_data["content_hash"][:16].lower())
        
        for hash_val in mentioned_hashes:
            short_hash = hash_val[:16].lower()
            if valid_hashes and short_hash not in valid_hashes:
                self._issues.append(ValidationIssue(
                    id=f"HASH-{len(self._issues)+1}",
                    category=ValidationCategory.FACT,
                    severity=ValidationSeverity.ERROR,
                    title="Invalid Hash Reference",
                    description=f"Hash '{hash_val[:16]}...' not found in case evidence",
                    suggestion="Verify hash against source data",
                    auto_fixable=False
                ))

    async def _check_actor_references(self, content: str, case_data: Dict[str, Any]):
        """Verify actor/user references exist in case data."""
        # This is a simplified check - in production, would use NER
        if "anomaly" in case_data:
            known_actors = set()
            for anomaly in case_data.get("anomaly", {}).get("top_anomalies", []):
                if "actor" in anomaly:
                    known_actors.add(anomaly["actor"].lower())
            
            # Check for email-like patterns that aren't in known actors
            email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
            mentioned_emails = re.findall(email_pattern, content.lower())
            
            for email in set(mentioned_emails):
                if known_actors and email not in known_actors:
                    self._issues.append(ValidationIssue(
                        id=f"ACT-{len(self._issues)+1}",
                        category=ValidationCategory.FACT,
                        severity=ValidationSeverity.WARNING,
                        title="Unknown Actor Reference",
                        description=f"Actor '{email}' not found in case data",
                        suggestion="Verify this actor exists in the case evidence",
                        auto_fixable=False
                    ))

    def _categorize_issues(self) -> Dict[str, int]:
        """Count issues by category."""
        counts = {}
        for issue in self._issues:
            cat = issue.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts


# ═══════════════════════════════════════════════════════════════════════════════
# Completeness Analyzer Service
# ═══════════════════════════════════════════════════════════════════════════════

class CompletenessAnalyzerService:
    """
    Analyzes report completeness against required sections and coverage.
    """

    # Required sections with minimum word counts
    SECTION_REQUIREMENTS = {
        "executive_summary": {"min_words": 100, "required": True, "aliases": ["summary", "overview", "abstract"]},
        "timeline": {"min_words": 150, "required": True, "aliases": ["chronology", "event timeline", "sequence of events"]},
        "anomaly_findings": {"min_words": 100, "required": False, "aliases": ["anomalies", "suspicious activity", "behavioral anomalies"]},
        "impact_assessment": {"min_words": 75, "required": True, "aliases": ["impact", "severity", "business impact", "damage assessment"]},
        "remediation": {"min_words": 50, "required": True, "aliases": ["recommendations", "mitigation", "action items", "next steps"]},
        "chain_of_custody": {"min_words": 50, "required": True, "aliases": ["evidence handling", "custody log", "evidence chain"]},
    }

    def __init__(self, case_id: str):
        self.case_id = case_id

    async def analyze_completeness(
        self,
        content: str,
        available_modules: List[str],
        report_type: str = "incident"
    ) -> CompletenessResult:
        """
        Analyze report completeness.
        
        Args:
            content: Full report content
            available_modules: List of modules with data
            report_type: Type of report for requirements
        
        Returns:
            CompletenessResult with section analysis
        """
        sections: List[CompletenessCheck] = []
        suggestions: List[str] = []
        
        # Parse content into sections (simplified)
        content_lower = content.lower()
        
        for section_name, requirements in self.SECTION_REQUIREMENTS.items():
            # Check if section is present
            is_present = any(
                alias in content_lower 
                for alias in [section_name.replace("_", " ")] + requirements.get("aliases", [])
            )
            
            # Estimate word count for section (simplified)
            section_words = self._estimate_section_words(content, section_name, requirements.get("aliases", []))
            
            # Calculate coverage score
            min_words = requirements["min_words"]
            coverage = min(1.0, section_words / min_words) if min_words > 0 else 1.0
            
            # Determine missing elements
            missing = []
            if not is_present:
                missing.append(f"Section '{section_name.replace('_', ' ')}' not found")
            elif section_words < min_words:
                missing.append(f"Section needs {min_words - section_words} more words")
            
            sections.append(CompletenessCheck(
                section=section_name,
                is_present=is_present,
                word_count=section_words,
                recommended_min=min_words,
                coverage_score=coverage,
                missing_elements=missing
            ))
            
            # Generate suggestions
            if requirements["required"] and not is_present:
                suggestions.append(f"Add {section_name.replace('_', ' ')} section (required)")
            elif is_present and section_words < min_words * 0.5:
                suggestions.append(f"Expand {section_name.replace('_', ' ')} section - currently too brief")
        
        # Check module coverage
        module_section_map = {
            "timeline": "timeline",
            "anomaly": "anomaly_findings",
            "depth": "impact_assessment",
        }
        
        for module, section in module_section_map.items():
            if module in available_modules:
                section_check = next((s for s in sections if s.section == section), None)
                if section_check and not section_check.is_present:
                    suggestions.append(f"Include {section.replace('_', ' ')} - {module} data available")
        
        # Calculate overall score
        required_sections = [s for s in sections if self.SECTION_REQUIREMENTS[s.section]["required"]]
        required_met = all(s.is_present and s.coverage_score >= 0.5 for s in required_sections)
        
        total_coverage = sum(s.coverage_score for s in sections) / len(sections) if sections else 0
        overall_score = total_coverage * 100
        
        return CompletenessResult(
            case_id=self.case_id,
            checked_at=datetime.utcnow().isoformat(),
            sections=sections,
            overall_score=round(overall_score, 1),
            required_sections_met=required_met,
            suggestions=suggestions
        )

    def _estimate_section_words(self, content: str, section_name: str, aliases: List[str]) -> int:
        """Estimate word count for a section (simplified)."""
        content_lower = content.lower()
        
        # Find section start
        section_start = -1
        for alias in [section_name.replace("_", " ")] + aliases:
            pos = content_lower.find(alias)
            if pos != -1 and (section_start == -1 or pos < section_start):
                section_start = pos
        
        if section_start == -1:
            return 0
        
        # Find section end (next header or end of content)
        section_end = len(content)
        header_patterns = ["executive summary", "timeline", "anomaly", "impact", "remediation", "chain of custody", "conclusion"]
        
        for pattern in header_patterns:
            if pattern != section_name.replace("_", " "):
                pos = content_lower.find(pattern, section_start + 50)
                if pos != -1 and pos < section_end:
                    section_end = pos
        
        # Count words in section
        section_text = content[section_start:section_end]
        return len(section_text.split())


# ═══════════════════════════════════════════════════════════════════════════════
# Consistency Checker Service
# ═══════════════════════════════════════════════════════════════════════════════

class ConsistencyCheckerService:
    """
    Checks internal consistency of report content.
    """

    def __init__(self, case_id: str):
        self.case_id = case_id

    async def check_consistency(self, content: str) -> List[ValidationIssue]:
        """Check for internal inconsistencies."""
        issues: List[ValidationIssue] = []
        
        # Check for conflicting numbers
        issues.extend(await self._check_number_consistency(content))
        
        # Check for tense consistency
        issues.extend(await self._check_tense_consistency(content))
        
        return issues

    async def _check_number_consistency(self, content: str) -> List[ValidationIssue]:
        """Check that the same metric isn't reported with different values."""
        issues = []
        
        # Find all number-context pairs
        patterns = [
            (r'(\d+)\s*anomalies', "anomalies"),
            (r'(\d+)\s*events', "events"),
            (r'(\d+)\s*actors', "actors"),
        ]
        
        for pattern, metric in patterns:
            matches = re.findall(pattern, content.lower())
            unique_values = set(int(m) for m in matches)
            
            if len(unique_values) > 1:
                issues.append(ValidationIssue(
                    id=f"CON-{len(issues)+1}",
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    title=f"Inconsistent {metric.title()} Count",
                    description=f"Report mentions different {metric} counts: {', '.join(str(v) for v in unique_values)}",
                    suggestion="Ensure all mentions of this metric use the same value",
                    auto_fixable=False
                ))
        
        return issues

    async def _check_tense_consistency(self, content: str) -> List[ValidationIssue]:
        """Check for tense consistency (simplified)."""
        # This is a simplified check - production would use NLP
        past_indicators = len(re.findall(r'\b(was|were|had|occurred|detected|found)\b', content.lower()))
        present_indicators = len(re.findall(r'\b(is|are|has|occurs|detects|finds)\b', content.lower()))
        
        issues = []
        if past_indicators > 10 and present_indicators > 10:
            ratio = min(past_indicators, present_indicators) / max(past_indicators, present_indicators)
            if ratio > 0.4:  # Significant mix
                issues.append(ValidationIssue(
                    id="CON-TENSE-1",
                    category=ValidationCategory.CONSISTENCY,
                    severity=ValidationSeverity.INFO,
                    title="Mixed Tense Usage",
                    description="Report mixes past and present tense. Consider using consistent tense throughout.",
                    suggestion="Forensic reports typically use past tense for findings",
                    auto_fixable=False
                ))
        
        return issues
