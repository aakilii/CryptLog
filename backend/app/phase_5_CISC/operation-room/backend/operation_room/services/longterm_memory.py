"""
Long-term Memory & Hypothesis Calibration - Oracle 26AI Phase 4.

Persistent memory across investigations:
- Store hypothesis outcomes for calibration
- Track prediction accuracy over time
- Learn from past investigations
- Cross-case pattern recognition
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from operation_room.database import open_vault
from operation_room.services.vector_store import get_vector_store, CollectionType
from operation_room.services.embedding_service import get_embedding_service
from operation_room.config import settings

logger = logging.getLogger(__name__)


class HypothesisOutcome(str, Enum):
    """Outcome of a hypothesis after investigation."""
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    PENDING = "pending"


@dataclass
class HypothesisRecord:
    """Record of a hypothesis and its outcome."""
    hypothesis_id: str
    case_id: str
    hypothesis_text: str
    predicted_confidence: float
    outcome: HypothesisOutcome
    actual_confidence: Optional[float] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    category: str = "general"
    supporting_evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationMetrics:
    """Calibration metrics for prediction accuracy."""
    total_hypotheses: int
    confirmed: int
    rejected: int
    partial: int
    inconclusive: int
    mean_predicted_confidence: float
    mean_actual_confidence: float
    calibration_error: float  # |predicted - actual|
    brier_score: float  # Quadratic scoring
    by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class LongTermMemory:
    """
    Long-term memory service for hypothesis calibration.
    
    Features:
    - Store hypothesis predictions and outcomes
    - Track calibration over time
    - Learn from past case patterns
    - Cross-case similarity search
    """
    
    def __init__(self):
        """Initialize global long-term memory."""
        self._vector_store = get_vector_store()
        self._embedding_service = get_embedding_service()
        self._ensure_global_schema()
    
    def _ensure_global_schema(self) -> None:
        """Create global tables in shared database."""
        import duckdb
        
        db_path = Path(settings.GLOBAL_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = duckdb.connect(str(db_path))
        try:
            # Hypothesis history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hypothesis_history (
                    hypothesis_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    hypothesis_text TEXT NOT NULL,
                    predicted_confidence FLOAT NOT NULL,
                    outcome VARCHAR DEFAULT 'pending',
                    actual_confidence FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    category VARCHAR DEFAULT 'general',
                    supporting_evidence JSON,
                    metadata JSON
                )
            """)
            
            # Calibration metrics over time
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calibration_snapshots (
                    snapshot_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_hypotheses INTEGER,
                    confirmed INTEGER,
                    rejected INTEGER,
                    mean_predicted_confidence FLOAT,
                    mean_actual_confidence FLOAT,
                    calibration_error FLOAT,
                    brier_score FLOAT,
                    by_category JSON
                )
            """)
            
            # Pattern storage for cross-case learning
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    pattern_id VARCHAR PRIMARY KEY,
                    pattern_type VARCHAR NOT NULL,
                    description TEXT,
                    confidence FLOAT DEFAULT 0.5,
                    occurrence_count INTEGER DEFAULT 1,
                    case_ids JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hypothesis_case 
                ON hypothesis_history(case_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hypothesis_outcome 
                ON hypothesis_history(outcome)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pattern_type 
                ON learned_patterns(pattern_type)
            """)
            
        finally:
            conn.close()
    
    def _get_global_conn(self):
        """Get connection to global database."""
        import duckdb
        return duckdb.connect(str(settings.GLOBAL_DB_PATH))
    
    def record_hypothesis(
        self,
        case_id: str,
        hypothesis_text: str,
        predicted_confidence: float,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a new hypothesis for tracking.
        
        Args:
            case_id: Case ID
            hypothesis_text: The hypothesis statement
            predicted_confidence: Predicted confidence (0-1)
            category: Hypothesis category
            metadata: Additional metadata
            
        Returns:
            Hypothesis ID
        """
        hypothesis_id = f"hyp_{uuid.uuid4().hex[:12]}"
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                INSERT INTO hypothesis_history (
                    hypothesis_id, case_id, hypothesis_text, predicted_confidence,
                    category, metadata
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                hypothesis_id, case_id, hypothesis_text, predicted_confidence,
                category, json.dumps(metadata) if metadata else None
            ])
            
            # Add to vector store for similarity search
            try:
                self._vector_store.add_document(
                    collection_type=CollectionType.HYPOTHESIS,
                    content=hypothesis_text,
                    metadata={
                        'case_id': case_id,
                        'category': category,
                        'predicted_confidence': predicted_confidence
                    },
                    doc_id=hypothesis_id,
                    case_id=case_id
                )
            except Exception as e:
                logger.warning(f"Failed to add hypothesis to vector store: {e}")
            
        finally:
            conn.close()
        
        logger.info(f"Recorded hypothesis {hypothesis_id} with confidence {predicted_confidence}")
        return hypothesis_id
    
    def resolve_hypothesis(
        self,
        hypothesis_id: str,
        outcome: HypothesisOutcome,
        actual_confidence: Optional[float] = None,
        supporting_evidence: Optional[List[str]] = None
    ) -> bool:
        """
        Resolve a hypothesis with its outcome.
        
        Args:
            hypothesis_id: Hypothesis ID
            outcome: Outcome of the hypothesis
            actual_confidence: Actual confidence after investigation
            supporting_evidence: List of evidence IDs
            
        Returns:
            True if successful
        """
        # Determine actual confidence from outcome if not provided
        if actual_confidence is None:
            outcome_confidence = {
                HypothesisOutcome.CONFIRMED: 1.0,
                HypothesisOutcome.REJECTED: 0.0,
                HypothesisOutcome.PARTIAL: 0.5,
                HypothesisOutcome.INCONCLUSIVE: 0.5,
            }
            actual_confidence = outcome_confidence.get(outcome, 0.5)
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                UPDATE hypothesis_history
                SET outcome = ?,
                    actual_confidence = ?,
                    resolved_at = CURRENT_TIMESTAMP,
                    supporting_evidence = ?
                WHERE hypothesis_id = ?
            """, [
                outcome.value,
                actual_confidence,
                json.dumps(supporting_evidence) if supporting_evidence else None,
                hypothesis_id
            ])
            
        finally:
            conn.close()
        
        logger.info(f"Resolved hypothesis {hypothesis_id}: {outcome.value}")
        return True
    
    def get_calibration_metrics(
        self,
        case_id: Optional[str] = None,
        category: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> CalibrationMetrics:
        """
        Calculate calibration metrics.
        
        Args:
            case_id: Filter to specific case
            category: Filter to specific category
            since: Only include hypotheses since this time
            
        Returns:
            CalibrationMetrics object
        """
        conn = self._get_global_conn()
        try:
            conditions = ["outcome != 'pending'"]
            params = []
            
            if case_id:
                conditions.append("case_id = ?")
                params.append(case_id)
            if category:
                conditions.append("category = ?")
                params.append(category)
            if since:
                conditions.append("created_at >= ?")
                params.append(since)
            
            where_clause = " AND ".join(conditions)
            
            # Get basic stats
            stats = conn.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
                    SUM(CASE WHEN outcome = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN outcome = 'partial' THEN 1 ELSE 0 END) as partial,
                    SUM(CASE WHEN outcome = 'inconclusive' THEN 1 ELSE 0 END) as inconclusive,
                    AVG(predicted_confidence) as mean_predicted,
                    AVG(actual_confidence) as mean_actual
                FROM hypothesis_history
                WHERE {where_clause}
            """, params).fetchone()
            
            total = stats[0] or 0
            if total == 0:
                return CalibrationMetrics(
                    total_hypotheses=0,
                    confirmed=0,
                    rejected=0,
                    partial=0,
                    inconclusive=0,
                    mean_predicted_confidence=0.0,
                    mean_actual_confidence=0.0,
                    calibration_error=0.0,
                    brier_score=0.0
                )
            
            mean_predicted = stats[5] or 0.0
            mean_actual = stats[6] or 0.0
            
            # Calculate calibration error and Brier score
            calibration_data = conn.execute(f"""
                SELECT predicted_confidence, actual_confidence
                FROM hypothesis_history
                WHERE {where_clause} AND actual_confidence IS NOT NULL
            """, params).fetchall()
            
            if calibration_data:
                calibration_error = sum(
                    abs(r[0] - r[1]) for r in calibration_data
                ) / len(calibration_data)
                
                brier_score = sum(
                    (r[0] - r[1]) ** 2 for r in calibration_data
                ) / len(calibration_data)
            else:
                calibration_error = 0.0
                brier_score = 0.0
            
            # Get breakdown by category
            by_category_rows = conn.execute(f"""
                SELECT category, COUNT(*) as count,
                       AVG(predicted_confidence) as mean_pred,
                       AVG(actual_confidence) as mean_actual
                FROM hypothesis_history
                WHERE {where_clause}
                GROUP BY category
            """, params).fetchall()
            
            by_category = {
                r[0]: {
                    'count': r[1],
                    'mean_predicted': r[2] or 0.0,
                    'mean_actual': r[3] or 0.0
                }
                for r in by_category_rows
            }
            
            return CalibrationMetrics(
                total_hypotheses=total,
                confirmed=stats[1] or 0,
                rejected=stats[2] or 0,
                partial=stats[3] or 0,
                inconclusive=stats[4] or 0,
                mean_predicted_confidence=mean_predicted,
                mean_actual_confidence=mean_actual,
                calibration_error=calibration_error,
                brier_score=brier_score,
                by_category=by_category
            )
            
        finally:
            conn.close()
    
    def find_similar_hypotheses(
        self,
        hypothesis_text: str,
        n_results: int = 5,
        exclude_case_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar hypotheses from past investigations.
        
        Args:
            hypothesis_text: Hypothesis to match
            n_results: Maximum results
            exclude_case_id: Exclude hypotheses from this case
            
        Returns:
            List of similar hypotheses with outcomes
        """
        # Search in templates collection (global)
        try:
            results = self._vector_store.search(
                collection_type=CollectionType.TEMPLATES,
                query=hypothesis_text,
                n_results=n_results * 2  # Get more to filter
            )
        except:
            results = []
        
        # Get full records from DB
        conn = self._get_global_conn()
        try:
            similar = []
            for result in results:
                if exclude_case_id:
                    row = conn.execute("""
                        SELECT hypothesis_id, case_id, hypothesis_text, predicted_confidence,
                               outcome, actual_confidence, category
                        FROM hypothesis_history
                        WHERE hypothesis_id = ? AND case_id != ? AND outcome != 'pending'
                    """, [result.id, exclude_case_id]).fetchone()
                else:
                    row = conn.execute("""
                        SELECT hypothesis_id, case_id, hypothesis_text, predicted_confidence,
                               outcome, actual_confidence, category
                        FROM hypothesis_history
                        WHERE hypothesis_id = ? AND outcome != 'pending'
                    """, [result.id]).fetchone()
                
                if row:
                    similar.append({
                        'hypothesis_id': row[0],
                        'case_id': row[1],
                        'text': row[2],
                        'predicted_confidence': row[3],
                        'outcome': row[4],
                        'actual_confidence': row[5],
                        'category': row[6],
                        'similarity': result.score
                    })
            
            return similar[:n_results]
            
        finally:
            conn.close()
    
    def suggest_confidence_adjustment(
        self,
        hypothesis_text: str,
        initial_confidence: float,
        category: str = "general"
    ) -> Tuple[float, str]:
        """
        Suggest confidence adjustment based on historical calibration.
        
        Args:
            hypothesis_text: Hypothesis to check
            initial_confidence: Initial predicted confidence
            category: Hypothesis category
            
        Returns:
            Tuple of (suggested_confidence, explanation)
        """
        # Get calibration for this category
        metrics = self.get_calibration_metrics(category=category)
        
        if metrics.total_hypotheses < 10:
            # Not enough data for adjustment
            return initial_confidence, "Insufficient historical data for calibration"
        
        # Find similar hypotheses
        similar = self.find_similar_hypotheses(hypothesis_text, n_results=3)
        
        # Calculate adjustment
        adjustments = []
        explanations = []
        
        # Category-level calibration adjustment
        if metrics.calibration_error > 0.1:
            # Significant miscalibration
            direction = "down" if metrics.mean_predicted_confidence > metrics.mean_actual_confidence else "up"
            adjustment = metrics.mean_actual_confidence - metrics.mean_predicted_confidence
            adjustments.append(adjustment * 0.5)  # Partial correction
            explanations.append(f"Category '{category}' tends to be over-confident by {abs(adjustment):.2f}")
        
        # Similar hypothesis adjustment
        if similar:
            similar_outcomes = [s for s in similar if s['outcome'] in ('confirmed', 'rejected')]
            if similar_outcomes:
                avg_actual = sum(s['actual_confidence'] for s in similar_outcomes) / len(similar_outcomes)
                avg_predicted = sum(s['predicted_confidence'] for s in similar_outcomes) / len(similar_outcomes)
                if abs(avg_predicted - avg_actual) > 0.1:
                    adjustment = (avg_actual - avg_predicted) * 0.3
                    adjustments.append(adjustment)
                    explanations.append(f"Similar past hypotheses averaged {avg_actual:.2f} actual vs {avg_predicted:.2f} predicted")
        
        # Apply adjustments
        if adjustments:
            total_adjustment = sum(adjustments) / len(adjustments)
            suggested = max(0.0, min(1.0, initial_confidence + total_adjustment))
            explanation = "; ".join(explanations)
        else:
            suggested = initial_confidence
            explanation = "No significant calibration adjustment needed"
        
        return suggested, explanation
    
    def record_pattern(
        self,
        pattern_type: str,
        description: str,
        case_id: str,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record a learned pattern from investigation.
        
        Args:
            pattern_type: Type of pattern (behavior, network, temporal, etc.)
            description: Pattern description
            case_id: Case where pattern was found
            confidence: Pattern confidence
            metadata: Additional metadata
            
        Returns:
            Pattern ID
        """
        pattern_id = f"pat_{hashlib.sha256(description.encode()).hexdigest()[:12]}"
        
        conn = self._get_global_conn()
        try:
            # Check if pattern exists
            existing = conn.execute("""
                SELECT pattern_id, occurrence_count, case_ids
                FROM learned_patterns
                WHERE pattern_id = ?
            """, [pattern_id]).fetchone()
            
            if existing:
                # Update existing pattern
                case_ids = json.loads(existing[2]) if existing[2] else []
                if case_id not in case_ids:
                    case_ids.append(case_id)
                
                conn.execute("""
                    UPDATE learned_patterns
                    SET occurrence_count = occurrence_count + 1,
                        confidence = (confidence * occurrence_count + ?) / (occurrence_count + 1),
                        case_ids = ?,
                        last_seen = CURRENT_TIMESTAMP
                    WHERE pattern_id = ?
                """, [confidence, json.dumps(case_ids), pattern_id])
                
            else:
                # Insert new pattern
                conn.execute("""
                    INSERT INTO learned_patterns (
                        pattern_id, pattern_type, description, confidence,
                        case_ids, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    pattern_id, pattern_type, description, confidence,
                    json.dumps([case_id]), json.dumps(metadata) if metadata else None
                ])
            
        finally:
            conn.close()
        
        logger.debug(f"Recorded pattern {pattern_id}: {pattern_type}")
        return pattern_id
    
    def get_relevant_patterns(
        self,
        query: str,
        pattern_type: Optional[str] = None,
        min_occurrences: int = 2,
        n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get patterns relevant to a query.
        
        Args:
            query: Query text to match
            pattern_type: Filter to specific type
            min_occurrences: Minimum occurrences required
            n_results: Maximum results
            
        Returns:
            List of relevant patterns
        """
        conn = self._get_global_conn()
        try:
            conditions = ["occurrence_count >= ?"]
            params = [min_occurrences]
            
            if pattern_type:
                conditions.append("pattern_type = ?")
                params.append(pattern_type)
            
            where_clause = " AND ".join(conditions)
            
            # Simple text matching for now (could use vector search)
            rows = conn.execute(f"""
                SELECT pattern_id, pattern_type, description, confidence,
                       occurrence_count, case_ids, last_seen
                FROM learned_patterns
                WHERE {where_clause}
                ORDER BY confidence * occurrence_count DESC
                LIMIT ?
            """, params + [n_results]).fetchall()
            
            # Filter by text relevance
            query_lower = query.lower()
            patterns = []
            
            for r in rows:
                desc_lower = r[2].lower()
                # Simple keyword overlap
                overlap = len(set(query_lower.split()) & set(desc_lower.split()))
                if overlap > 0:
                    patterns.append({
                        'pattern_id': r[0],
                        'pattern_type': r[1],
                        'description': r[2],
                        'confidence': r[3],
                        'occurrence_count': r[4],
                        'case_ids': json.loads(r[5]) if r[5] else [],
                        'last_seen': r[6],
                        'relevance': overlap
                    })
            
            patterns.sort(key=lambda p: p['relevance'] * p['confidence'], reverse=True)
            return patterns[:n_results]
            
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get long-term memory statistics."""
        conn = self._get_global_conn()
        try:
            # Hypothesis stats
            hyp_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome != 'pending' THEN 1 ELSE 0 END) as resolved,
                    COUNT(DISTINCT case_id) as cases
                FROM hypothesis_history
            """).fetchone()
            
            # Pattern stats
            pattern_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(occurrence_count) as total_occurrences
                FROM learned_patterns
            """).fetchone()
            
            # Get calibration metrics
            metrics = self.get_calibration_metrics()
            
            return {
                'total_hypotheses': hyp_stats[0] or 0,
                'resolved_hypotheses': hyp_stats[1] or 0,
                'unique_cases': hyp_stats[2] or 0,
                'total_patterns': pattern_stats[0] or 0,
                'pattern_occurrences': pattern_stats[1] or 0,
                'calibration_error': metrics.calibration_error,
                'brier_score': metrics.brier_score
            }
            
        finally:
            conn.close()


# Singleton instance
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    """Get the long-term memory singleton."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory
