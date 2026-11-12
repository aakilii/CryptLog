"""
Confidence Scoring Engine

Calculates confidence scores for investigation findings based on multiple factors:

1. Evidence Strength (0.4 weight)
   - Quality of the source data
   - Completeness of information
   - Direct vs circumstantial evidence

2. Source Reliability (0.3 weight)
   - Module reputation/accuracy
   - Data source trustworthiness
   - Collection method reliability

3. Corroboration Score (0.2 weight)
   - Multiple sources agreeing
   - Cross-module validation
   - Pattern consistency

4. Temporal Consistency (0.1 weight)
   - Timeline alignment
   - Sequence logic
   - Timing plausibility

Based on ODNI ICD 203 intelligence confidence framework adapted for digital forensics.

Confidence Levels:
- 0.9-1.0: VERY HIGH - Multiple strong sources, fully corroborated
- 0.7-0.89: HIGH - Strong evidence, good corroboration
- 0.5-0.69: MODERATE - Some evidence, partial corroboration
- 0.3-0.49: LOW - Weak evidence, minimal corroboration
- 0.0-0.29: VERY LOW - Speculative, no corroboration
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass

from operation_room.database import open_vault

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceFactors:
    """Individual factors that contribute to confidence score."""
    evidence_strength: float = 0.5  # 0.0-1.0
    source_reliability: float = 0.5  # 0.0-1.0
    corroboration_score: float = 0.5  # 0.0-1.0
    temporal_consistency: float = 0.5  # 0.0-1.0
    
    # Weights for each factor
    WEIGHTS = {
        'evidence_strength': 0.4,
        'source_reliability': 0.3,
        'corroboration_score': 0.2,
        'temporal_consistency': 0.1,
    }
    
    def calculate_overall(self) -> float:
        """Calculate weighted overall confidence score."""
        score = (
            self.evidence_strength * self.WEIGHTS['evidence_strength'] +
            self.source_reliability * self.WEIGHTS['source_reliability'] +
            self.corroboration_score * self.WEIGHTS['corroboration_score'] +
            self.temporal_consistency * self.WEIGHTS['temporal_consistency']
        )
        return round(min(1.0, max(0.0, score)), 3)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'evidence_strength': round(self.evidence_strength, 3),
            'source_reliability': round(self.source_reliability, 3),
            'corroboration_score': round(self.corroboration_score, 3),
            'temporal_consistency': round(self.temporal_consistency, 3),
            'overall_confidence': self.calculate_overall(),
            'confidence_level': self.get_confidence_level(),
        }
    
    def get_confidence_level(self) -> str:
        """Get textual confidence level."""
        score = self.calculate_overall()
        if score >= 0.9:
            return "VERY HIGH"
        elif score >= 0.7:
            return "HIGH"
        elif score >= 0.5:
            return "MODERATE"
        elif score >= 0.3:
            return "LOW"
        else:
            return "VERY LOW"


class ConfidenceScoringEngine:
    """Engine for calculating confidence scores for findings."""
    
    # Module reliability scores (based on detection accuracy)
    MODULE_RELIABILITY = {
        'timeline': 0.95,  # Timeline data is factual
        'crud': 0.90,      # CRUD events are recorded facts
        'network': 0.85,   # Network flows are recorded
        'anomaly': 0.75,   # ML-based, some false positives
        'depth': 0.70,     # Impact assessment is analytical
        'correlation': 0.65,  # Correlation can be coincidental
        'llm': 0.60,       # LLM generations need verification
        'manual': 0.95,    # Manual investigator input
    }
    
    def __init__(self, case_id: str):
        self.case_id = case_id
    
    def calculate_evidence_strength(
        self,
        finding_value: Any,
        finding_type: str,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Calculate evidence strength based on quality and completeness.
        
        Factors:
        - Completeness of data (all fields present)
        - Data type (direct evidence > circumstantial)
        - Specificity (specific values > vague)
        - Reproducibility (can be verified)
        """
        score = 0.5  # Base score
        
        # Type-based scoring
        type_scores = {
            'evidence': 0.8,      # Direct evidence
            'artifact': 0.75,     # Physical/digital artifacts
            'metric': 0.7,        # Measurable data
            'timeline': 0.7,      # Temporal facts
            'correlation': 0.6,   # Patterns
            'entity': 0.65,       # Identified entities
            'hypothesis': 0.5,    # Needs testing
            'conclusion': 0.7,    # Derived finding
        }
        score = type_scores.get(finding_type, 0.5)
        
        # Completeness check
        if isinstance(finding_value, dict):
            fields = len(finding_value)
            if fields >= 10:
                score += 0.15
            elif fields >= 5:
                score += 0.10
            elif fields >= 3:
                score += 0.05
        
        # Specificity check (has actual values, not placeholders)
        if isinstance(finding_value, dict):
            has_meaningful_data = any(
                v not in [None, "", [], {}, "unknown", "N/A"]
                for v in finding_value.values()
            )
            if has_meaningful_data:
                score += 0.05
        
        # Metadata presence (indicates thorough collection)
        if metadata and len(metadata) > 0:
            score += 0.05
        
        return min(1.0, score)
    
    def calculate_source_reliability(self, source_module: Optional[str]) -> float:
        """
        Calculate reliability based on data source.
        
        Factors:
        - Module type (factual > analytical)
        - Known accuracy rates
        - Collection method
        """
        if not source_module:
            return 0.5
        
        return self.MODULE_RELIABILITY.get(source_module.lower(), 0.5)
    
    def calculate_corroboration_score(
        self,
        finding_key: str,
        investigation_id: Optional[str] = None
    ) -> float:
        """
        Calculate corroboration by checking if other findings support this one.
        
        Factors:
        - Number of sources reporting similar data
        - Different modules agreeing
        - Related findings
        """
        from operation_room.services.findings_vault import get_findings_vault
        
        vault = get_findings_vault(self.case_id)
        
        # Get the finding
        finding = vault.get_finding(finding_key, investigation_id)
        if not finding:
            return 0.5
        
        score = 0.3  # Base (isolated finding)
        
        # Check for related findings
        all_findings = vault.get_all_findings(investigation_id)
        
        # Same module has multiple findings (consistency)
        if finding['source_module']:
            same_module_findings = [
                f for f in all_findings
                if f['source_module'] == finding['source_module']
                and f['finding_key'] != finding_key
            ]
            if len(same_module_findings) >= 5:
                score += 0.15
            elif len(same_module_findings) >= 2:
                score += 0.10
        
        # Different modules mention same entities/values (cross-validation)
        finding_val = finding['finding_value']
        if isinstance(finding_val, dict):
            # Extract key values to look for
            key_values = [
                str(v) for v in finding_val.values()
                if v and str(v) not in ['', 'None', 'unknown']
            ]
            
            cross_module_mentions = 0
            for other_finding in all_findings:
                if other_finding['finding_key'] == finding_key:
                    continue
                if other_finding['source_module'] == finding['source_module']:
                    continue
                
                other_val_str = str(other_finding['finding_value'])
                for key_val in key_values[:5]:  # Check first 5 values
                    if key_val in other_val_str:
                        cross_module_mentions += 1
                        break
            
            if cross_module_mentions >= 3:
                score += 0.30
            elif cross_module_mentions >= 2:
                score += 0.20
            elif cross_module_mentions >= 1:
                score += 0.10
        
        # High confidence findings nearby (context support)
        high_confidence_nearby = len([
            f for f in all_findings
            if f['confidence_score'] >= 0.8
            and f['finding_key'] != finding_key
        ])
        
        if high_confidence_nearby >= 10:
            score += 0.10
        elif high_confidence_nearby >= 5:
            score += 0.05
        
        return min(1.0, score)
    
    def calculate_temporal_consistency(
        self,
        finding_value: Any,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Calculate temporal consistency.
        
        Factors:
        - Timestamps are logical
        - Event sequence makes sense
        - Timing is plausible
        """
        score = 0.7  # Default (assume reasonable unless proven otherwise)
        
        # Check if finding has timestamp data
        timestamps_found = False
        
        if isinstance(finding_value, dict):
            for key in ['timestamp', 'created_at', 'time', 'datetime', 'event_time']:
                if key in finding_value and finding_value[key]:
                    timestamps_found = True
                    # Try to parse timestamp
                    try:
                        ts_val = finding_value[key]
                        if isinstance(ts_val, str):
                            # Check if it's a reasonable timestamp
                            if '2020' <= ts_val <= '2030':  # Rough sanity check
                                score = 0.85
                            elif '2015' <= ts_val <= '2035':
                                score = 0.75
                    except:
                        pass
        
        # If no timestamps, can't verify temporal consistency strongly
        if not timestamps_found:
            score = 0.6
        
        # Check metadata for collection time
        if metadata and 'collected_at' in metadata:
            score = min(score + 0.1, 1.0)
        
        return score
    
    def calculate_confidence(
        self,
        finding_key: str,
        finding_value: Any,
        finding_type: str,
        source_module: Optional[str] = None,
        metadata: Optional[Dict] = None,
        investigation_id: Optional[str] = None
    ) -> ConfidenceFactors:
        """
        Calculate complete confidence score for a finding.
        
        Returns ConfidenceFactors with breakdown and overall score.
        """
        factors = ConfidenceFactors(
            evidence_strength=self.calculate_evidence_strength(
                finding_value, finding_type, metadata
            ),
            source_reliability=self.calculate_source_reliability(source_module),
            corroboration_score=self.calculate_corroboration_score(
                finding_key, investigation_id
            ),
            temporal_consistency=self.calculate_temporal_consistency(
                finding_value, metadata
            ),
        )
        
        logger.info(
            f"Confidence for {finding_key}: {factors.calculate_overall():.3f} "
            f"({factors.get_confidence_level()})"
        )
        
        return factors
    
    def recalculate_all_confidences(self, investigation_id: Optional[str] = None):
        """
        Recalculate confidence scores for all findings.
        
        Useful when new findings are added that might corroborate existing ones.
        """
        from operation_room.services.findings_vault import get_findings_vault
        
        vault = get_findings_vault(self.case_id)
        findings = vault.get_all_findings(investigation_id)
        
        updated_count = 0
        for finding in findings:
            factors = self.calculate_confidence(
                finding_key=finding['finding_key'],
                finding_value=finding['finding_value'],
                finding_type=finding['finding_type'],
                source_module=finding['source_module'],
                metadata=finding['metadata'],
                investigation_id=investigation_id
            )
            
            new_confidence = factors.calculate_overall()
            
            # Update if changed significantly
            if abs(new_confidence - finding['confidence_score']) > 0.05:
                vault.update_confidence(
                    finding['finding_key'],
                    new_confidence,
                    investigation_id
                )
                updated_count += 1
        
        logger.info(f"Recalculated {updated_count} confidence scores")
        return updated_count


def get_confidence_engine(case_id: str) -> ConfidenceScoringEngine:
    """Get confidence scoring engine for a case."""
    return ConfidenceScoringEngine(case_id)
