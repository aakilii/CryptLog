"""
Validation Memory Service - Oracle 26AI Phase 6.

Claim extraction and evidence validation:
- Extract claims from report text
- Link claims to supporting evidence
- Detect contradictions
- Advisory validation (flag but don't block)
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from operation_room.database import open_vault
from operation_room.services.vector_store import get_vector_store, CollectionType
from operation_room.services.embedding_service import get_embedding_service
from operation_room.services.evidence_vault import get_evidence_vault, EvidenceVault

logger = logging.getLogger(__name__)


class ClaimType(str, Enum):
    """Types of claims that can be extracted."""
    FACTUAL = "factual"          # Statement of fact
    TEMPORAL = "temporal"        # Time-based claim
    QUANTITATIVE = "quantitative"  # Numerical claim
    CAUSAL = "causal"            # Cause-effect relationship
    COMPARATIVE = "comparative"  # Comparison claim
    ATTRIBUTIVE = "attributive"  # Attribution to actor


class ValidationStatus(str, Enum):
    """Validation status of a claim."""
    PENDING = "pending"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    PARTIAL = "partial"


class ContradictionSeverity(str, Enum):
    """Severity of detected contradictions."""
    LOW = "low"        # Minor inconsistency
    MEDIUM = "medium"  # Notable contradiction
    HIGH = "high"      # Critical contradiction


@dataclass
class ExtractedClaim:
    """A claim extracted from report text."""
    claim_id: str
    text: str
    claim_type: ClaimType
    source_section: str
    source_text: str  # Original text containing the claim
    confidence: float = 0.0
    validation_status: ValidationStatus = ValidationStatus.PENDING
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ClaimValidationResult:
    """Result of validating a claim."""
    claim_id: str
    status: ValidationStatus
    confidence: float
    supporting_evidence: List[Dict[str, Any]]
    contradicting_evidence: List[Dict[str, Any]]
    explanation: str


@dataclass
class Contradiction:
    """A detected contradiction between claims or evidence."""
    contradiction_id: str
    claim_id_1: str
    claim_id_2: Optional[str]  # May be None if contradiction is with evidence
    evidence_id: Optional[str]
    severity: ContradictionSeverity
    description: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimExtractor:
    """
    Extracts claims from report text.
    
    Uses pattern matching and semantic analysis to identify
    verifiable claims in report sections.
    """
    
    # Patterns for different claim types
    CLAIM_PATTERNS = {
        ClaimType.TEMPORAL: [
            r"(?:on|at|during|between|from|after|before)\s+(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2})",
            r"(?:occurred|happened|detected|observed)\s+(?:on|at)\s+",
        ],
        ClaimType.QUANTITATIVE: [
            r"\d+(?:\.\d+)?\s*(?:percent|%|times|events|records|bytes|MB|GB|connections)",
            r"(?:total|sum|count|average|mean|median)\s+(?:of\s+)?\d+",
        ],
        ClaimType.CAUSAL: [
            r"(?:caused|resulted|led to|because|due to|therefore)",
            r"(?:indicates|suggests|demonstrates|proves|shows)\s+(?:that)?",
        ],
        ClaimType.ATTRIBUTIVE: [
            r"(?:user|actor|account|system|IP)\s+[\w\d.-]+\s+(?:performed|executed|accessed)",
            r"(?:was\s+)?(?:performed|executed|initiated)\s+by",
        ],
    }
    
    def extract_claims(
        self,
        text: str,
        section_name: str = "unknown"
    ) -> List[ExtractedClaim]:
        """
        Extract claims from text.
        
        Args:
            text: Text to extract claims from
            section_name: Name of the section
            
        Returns:
            List of extracted claims
        """
        claims = []
        
        # Split into sentences
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
            
            # Detect claim types
            claim_types = self._detect_claim_types(sentence)
            
            if claim_types:
                claim_id = f"claim_{hashlib.sha256(sentence.encode()).hexdigest()[:12]}"
                
                # Use primary claim type
                primary_type = claim_types[0] if claim_types else ClaimType.FACTUAL
                
                claims.append(ExtractedClaim(
                    claim_id=claim_id,
                    text=sentence,
                    claim_type=primary_type,
                    source_section=section_name,
                    source_text=sentence,
                    metadata={'detected_types': [t.value for t in claim_types]}
                ))
        
        return claims
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting (could be enhanced with NLP)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s]
    
    def _detect_claim_types(self, sentence: str) -> List[ClaimType]:
        """Detect claim types in a sentence."""
        detected = []
        sentence_lower = sentence.lower()
        
        for claim_type, patterns in self.CLAIM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, sentence_lower):
                    detected.append(claim_type)
                    break
        
        # Default to factual if sentence makes an assertion
        if not detected and self._is_assertion(sentence):
            detected.append(ClaimType.FACTUAL)
        
        return detected
    
    def _is_assertion(self, sentence: str) -> bool:
        """Check if sentence makes an assertion."""
        # Simple heuristics
        assertion_indicators = [
            r'\bis\b', r'\bwas\b', r'\bwere\b', r'\bare\b',
            r'\bhas\b', r'\bhave\b', r'\bhad\b',
            r'\bshows?\b', r'\bindicates?\b', r'\bconfirms?\b',
            r'\bevidence\b', r'\bfindings?\b', r'\bresults?\b'
        ]
        
        sentence_lower = sentence.lower()
        return any(re.search(p, sentence_lower) for p in assertion_indicators)


class ClaimValidator:
    """
    Validates claims against evidence.
    
    Searches for supporting and contradicting evidence
    for each claim.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._evidence_vault = get_evidence_vault(case_id)
        self._embedding_service = get_embedding_service()
    
    def validate_claim(
        self,
        claim: ExtractedClaim,
        n_evidence: int = 5,
        support_threshold: float = 0.6,
        contradict_threshold: float = 0.4
    ) -> ClaimValidationResult:
        """
        Validate a single claim against evidence.
        
        Args:
            claim: Claim to validate
            n_evidence: Number of evidence items to search
            support_threshold: Similarity threshold for support
            contradict_threshold: Threshold below which may contradict
            
        Returns:
            Validation result
        """
        # Search for related evidence
        search_results = self._evidence_vault.search_hybrid(
            query=claim.text,
            n_results=n_evidence * 2,
            semantic_weight=0.7,
            keyword_weight=0.3
        )
        
        supporting = []
        contradicting = []
        
        for result in search_results:
            evidence = self._evidence_vault.get_evidence(result.evidence_id)
            if not evidence:
                continue
            
            # Analyze relationship
            relationship = self._analyze_relationship(claim.text, evidence.content)
            
            evidence_info = {
                'evidence_id': result.evidence_id,
                'content': evidence.content[:200],
                'type': evidence.evidence_type,
                'source': evidence.source,
                'similarity': result.combined_score,
                'relationship': relationship
            }
            
            if result.combined_score >= support_threshold and relationship in ('supports', 'related'):
                supporting.append(evidence_info)
            elif relationship == 'contradicts':
                contradicting.append(evidence_info)
        
        # Determine status
        if contradicting:
            status = ValidationStatus.CONTRADICTED
            confidence = 0.3
            explanation = f"Found {len(contradicting)} contradicting evidence items"
        elif supporting:
            if len(supporting) >= 2:
                status = ValidationStatus.SUPPORTED
                confidence = min(0.95, 0.5 + 0.15 * len(supporting))
            else:
                status = ValidationStatus.PARTIAL
                confidence = 0.6
            explanation = f"Found {len(supporting)} supporting evidence items"
        else:
            status = ValidationStatus.UNSUPPORTED
            confidence = 0.2
            explanation = "No supporting evidence found"
        
        return ClaimValidationResult(
            claim_id=claim.claim_id,
            status=status,
            confidence=confidence,
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            explanation=explanation
        )
    
    def _analyze_relationship(self, claim_text: str, evidence_text: str) -> str:
        """
        Analyze relationship between claim and evidence.
        
        Returns: 'supports', 'contradicts', or 'related'
        """
        # Simple heuristic-based analysis
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()
        
        # Check for negation patterns
        negation_indicators = ['not', 'never', 'no ', 'didn\'t', 'wasn\'t', 'weren\'t', 'isn\'t']
        
        claim_has_negation = any(neg in claim_lower for neg in negation_indicators)
        evidence_has_negation = any(neg in evidence_lower for neg in negation_indicators)
        
        # If one has negation and other doesn't, might contradict
        if claim_has_negation != evidence_has_negation:
            # Check if they share key terms
            claim_words = set(claim_lower.split())
            evidence_words = set(evidence_lower.split())
            overlap = claim_words & evidence_words
            
            if len(overlap) > 3:
                return 'contradicts'
        
        return 'supports'


class ContradictionDetector:
    """
    Detects contradictions between claims and evidence.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._embedding_service = get_embedding_service()
    
    def detect_contradictions(
        self,
        claims: List[ExtractedClaim]
    ) -> List[Contradiction]:
        """
        Detect contradictions between claims.
        
        Args:
            claims: List of claims to check
            
        Returns:
            List of detected contradictions
        """
        contradictions = []
        
        # Compare each pair of claims
        for i, claim1 in enumerate(claims):
            for claim2 in claims[i+1:]:
                # Skip if different types (less likely to contradict)
                if claim1.claim_type != claim2.claim_type:
                    continue
                
                # Check for contradiction
                is_contradiction, severity, description = self._check_contradiction(
                    claim1, claim2
                )
                
                if is_contradiction:
                    contradictions.append(Contradiction(
                        contradiction_id=f"contra_{uuid.uuid4().hex[:12]}",
                        claim_id_1=claim1.claim_id,
                        claim_id_2=claim2.claim_id,
                        evidence_id=None,
                        severity=severity,
                        description=description
                    ))
        
        return contradictions
    
    def _check_contradiction(
        self,
        claim1: ExtractedClaim,
        claim2: ExtractedClaim
    ) -> Tuple[bool, ContradictionSeverity, str]:
        """
        Check if two claims contradict each other.
        
        Returns: (is_contradiction, severity, description)
        """
        text1 = claim1.text.lower()
        text2 = claim2.text.lower()
        
        # Check for temporal contradictions
        if claim1.claim_type == ClaimType.TEMPORAL:
            times1 = self._extract_times(text1)
            times2 = self._extract_times(text2)
            
            if times1 and times2:
                # Check if same event has different times
                if self._same_subject(text1, text2) and times1 != times2:
                    return True, ContradictionSeverity.HIGH, f"Temporal inconsistency: {times1} vs {times2}"
        
        # Check for quantitative contradictions
        if claim1.claim_type == ClaimType.QUANTITATIVE:
            nums1 = self._extract_numbers(text1)
            nums2 = self._extract_numbers(text2)
            
            if nums1 and nums2 and self._same_subject(text1, text2):
                if nums1[0] != nums2[0]:
                    return True, ContradictionSeverity.MEDIUM, f"Quantitative inconsistency: {nums1[0]} vs {nums2[0]}"
        
        # Check for negation contradictions
        if self._is_negation_pair(text1, text2):
            return True, ContradictionSeverity.HIGH, "Direct contradiction (negation)"
        
        return False, ContradictionSeverity.LOW, ""
    
    def _extract_times(self, text: str) -> List[str]:
        """Extract time references from text."""
        patterns = [
            r'\d{4}[-/]\d{2}[-/]\d{2}',
            r'\d{2}:\d{2}(?::\d{2})?',
        ]
        times = []
        for pattern in patterns:
            times.extend(re.findall(pattern, text))
        return times
    
    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numbers from text."""
        numbers = re.findall(r'\d+(?:\.\d+)?', text)
        return [float(n) for n in numbers]
    
    def _same_subject(self, text1: str, text2: str) -> bool:
        """Check if two texts discuss the same subject."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        # Simple overlap check
        overlap = words1 & words2
        return len(overlap) >= 3
    
    def _is_negation_pair(self, text1: str, text2: str) -> bool:
        """Check if one text is negation of the other."""
        negations = [
            ('was', 'was not'), ('were', 'were not'),
            ('did', 'did not'), ('has', 'has not'),
            ('is', 'is not'), ('are', 'are not'),
        ]
        
        for pos, neg in negations:
            if (pos in text1 and neg in text2) or (neg in text1 and pos in text2):
                # Check subject overlap
                if self._same_subject(text1, text2):
                    return True
        
        return False


class ValidationMemory:
    """
    Complete validation memory system.
    
    Combines claim extraction, validation, and contradiction
    detection into a unified service.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.extractor = ClaimExtractor()
        self.validator = ClaimValidator(case_id)
        self.contradiction_detector = ContradictionDetector(case_id)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create validation tables."""
        conn = open_vault(self.case_id)
        try:
            # Claims table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_claims (
                    claim_id VARCHAR PRIMARY KEY,
                    text TEXT NOT NULL,
                    claim_type VARCHAR NOT NULL,
                    source_section VARCHAR,
                    source_text TEXT,
                    validation_status VARCHAR DEFAULT 'pending',
                    confidence FLOAT DEFAULT 0.0,
                    supporting_evidence JSON,
                    contradicting_evidence JSON,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    validated_at TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Claim-evidence links
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claim_evidence_links (
                    link_id VARCHAR PRIMARY KEY,
                    claim_id VARCHAR NOT NULL,
                    evidence_id VARCHAR NOT NULL,
                    link_type VARCHAR NOT NULL,
                    similarity FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Contradictions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS claim_contradictions (
                    contradiction_id VARCHAR PRIMARY KEY,
                    claim_id_1 VARCHAR NOT NULL,
                    claim_id_2 VARCHAR,
                    evidence_id VARCHAR,
                    severity VARCHAR NOT NULL,
                    description TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claims_status 
                ON validation_claims(validation_status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_claim_links 
                ON claim_evidence_links(claim_id)
            """)
            
        finally:
            conn.close()
    
    def extract_and_validate_section(
        self,
        section_text: str,
        section_name: str
    ) -> Dict[str, Any]:
        """
        Extract claims from a section and validate them.
        
        Args:
            section_text: Text of the section
            section_name: Name of the section
            
        Returns:
            Validation report for the section
        """
        # Extract claims
        claims = self.extractor.extract_claims(section_text, section_name)
        
        # Validate each claim
        validation_results = []
        for claim in claims:
            result = self.validator.validate_claim(claim)
            
            # Update claim with validation
            claim.validation_status = result.status
            claim.confidence = result.confidence
            claim.supporting_evidence = [e['evidence_id'] for e in result.supporting_evidence]
            claim.contradicting_evidence = [e['evidence_id'] for e in result.contradicting_evidence]
            
            # Save to database
            self._save_claim(claim)
            
            validation_results.append({
                'claim': {
                    'id': claim.claim_id,
                    'text': claim.text,
                    'type': claim.claim_type.value
                },
                'validation': {
                    'status': result.status.value,
                    'confidence': result.confidence,
                    'explanation': result.explanation
                },
                'evidence': {
                    'supporting': result.supporting_evidence[:3],
                    'contradicting': result.contradicting_evidence
                }
            })
        
        # Detect contradictions
        contradictions = self.contradiction_detector.detect_contradictions(claims)
        for contradiction in contradictions:
            self._save_contradiction(contradiction)
        
        return {
            'section': section_name,
            'total_claims': len(claims),
            'supported': sum(1 for r in validation_results if r['validation']['status'] == 'supported'),
            'unsupported': sum(1 for r in validation_results if r['validation']['status'] == 'unsupported'),
            'contradicted': sum(1 for r in validation_results if r['validation']['status'] == 'contradicted'),
            'contradictions_found': len(contradictions),
            'claims': validation_results,
            'contradictions': [
                {
                    'id': c.contradiction_id,
                    'severity': c.severity.value,
                    'description': c.description
                }
                for c in contradictions
            ]
        }
    
    def _save_claim(self, claim: ExtractedClaim) -> None:
        """Save claim to database."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO validation_claims (
                    claim_id, text, claim_type, source_section, source_text,
                    validation_status, confidence, supporting_evidence,
                    contradicting_evidence, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(claim_id) DO UPDATE SET
                    validation_status = excluded.validation_status,
                    confidence = excluded.confidence,
                    supporting_evidence = excluded.supporting_evidence,
                    contradicting_evidence = excluded.contradicting_evidence,
                    validated_at = CURRENT_TIMESTAMP
            """, [
                claim.claim_id, claim.text, claim.claim_type.value,
                claim.source_section, claim.source_text,
                claim.validation_status.value, claim.confidence,
                json.dumps(claim.supporting_evidence),
                json.dumps(claim.contradicting_evidence),
                json.dumps(claim.metadata)
            ])
        finally:
            conn.close()
    
    def _save_contradiction(self, contradiction: Contradiction) -> None:
        """Save contradiction to database."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO claim_contradictions (
                    contradiction_id, claim_id_1, claim_id_2, evidence_id,
                    severity, description
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(contradiction_id) DO NOTHING
            """, [
                contradiction.contradiction_id,
                contradiction.claim_id_1,
                contradiction.claim_id_2,
                contradiction.evidence_id,
                contradiction.severity.value,
                contradiction.description
            ])
        finally:
            conn.close()
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get overall validation summary for the case."""
        conn = open_vault(self.case_id)
        try:
            # Claim stats
            claim_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN validation_status = 'supported' THEN 1 ELSE 0 END) as supported,
                    SUM(CASE WHEN validation_status = 'unsupported' THEN 1 ELSE 0 END) as unsupported,
                    SUM(CASE WHEN validation_status = 'contradicted' THEN 1 ELSE 0 END) as contradicted,
                    AVG(confidence) as avg_confidence
                FROM validation_claims
            """).fetchone()
            
            # Contradiction stats
            contradiction_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high,
                    SUM(CASE WHEN severity = 'medium' THEN 1 ELSE 0 END) as medium,
                    SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved
                FROM claim_contradictions
            """).fetchone()
            
            # By section
            by_section = conn.execute("""
                SELECT source_section, validation_status, COUNT(*) as count
                FROM validation_claims
                GROUP BY source_section, validation_status
            """).fetchall()
            
            section_breakdown = {}
            for row in by_section:
                section = row[0] or 'unknown'
                if section not in section_breakdown:
                    section_breakdown[section] = {}
                section_breakdown[section][row[1]] = row[2]
            
            total_claims = claim_stats[0] or 0
            supported = claim_stats[1] or 0
            
            return {
                'total_claims': total_claims,
                'supported': supported,
                'unsupported': claim_stats[2] or 0,
                'contradicted': claim_stats[3] or 0,
                'average_confidence': round(claim_stats[4] or 0, 3),
                'support_rate': round(supported / total_claims, 3) if total_claims > 0 else 0,
                'contradictions': {
                    'total': contradiction_stats[0] or 0,
                    'high_severity': contradiction_stats[1] or 0,
                    'medium_severity': contradiction_stats[2] or 0,
                    'resolved': contradiction_stats[3] or 0
                },
                'by_section': section_breakdown
            }
        finally:
            conn.close()
    
    def get_unsupported_claims(self) -> List[Dict[str, Any]]:
        """Get list of unsupported claims (for advisory warnings)."""
        conn = open_vault(self.case_id)
        try:
            rows = conn.execute("""
                SELECT claim_id, text, claim_type, source_section, confidence
                FROM validation_claims
                WHERE validation_status IN ('unsupported', 'contradicted')
                ORDER BY confidence ASC
            """).fetchall()
            
            return [
                {
                    'claim_id': r[0],
                    'text': r[1],
                    'type': r[2],
                    'section': r[3],
                    'confidence': r[4]
                }
                for r in rows
            ]
        finally:
            conn.close()
    
    def get_unresolved_contradictions(self) -> List[Dict[str, Any]]:
        """Get unresolved contradictions."""
        conn = open_vault(self.case_id)
        try:
            rows = conn.execute("""
                SELECT c.contradiction_id, c.severity, c.description,
                       c1.text as claim1_text, c2.text as claim2_text
                FROM claim_contradictions c
                JOIN validation_claims c1 ON c.claim_id_1 = c1.claim_id
                LEFT JOIN validation_claims c2 ON c.claim_id_2 = c2.claim_id
                WHERE c.resolved = FALSE
                ORDER BY 
                    CASE c.severity 
                        WHEN 'high' THEN 1 
                        WHEN 'medium' THEN 2 
                        ELSE 3 
                    END
            """).fetchall()
            
            return [
                {
                    'contradiction_id': r[0],
                    'severity': r[1],
                    'description': r[2],
                    'claim1': r[3],
                    'claim2': r[4]
                }
                for r in rows
            ]
        finally:
            conn.close()
    
    def resolve_contradiction(self, contradiction_id: str) -> bool:
        """Mark a contradiction as resolved."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                UPDATE claim_contradictions
                SET resolved = TRUE
                WHERE contradiction_id = ?
            """, [contradiction_id])
            return True
        finally:
            conn.close()


# Global registry
_validation_memories: Dict[str, ValidationMemory] = {}


def get_validation_memory(case_id: str) -> ValidationMemory:
    """Get or create validation memory for a case."""
    if case_id not in _validation_memories:
        _validation_memories[case_id] = ValidationMemory(case_id)
    return _validation_memories[case_id]
