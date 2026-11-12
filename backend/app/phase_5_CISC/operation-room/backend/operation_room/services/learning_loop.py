"""
Learning Loop Service - Oracle 26AI Phase 8.

Feedback collection and continuous improvement:
- User feedback on results
- Automatic calibration updates
- Retrieval quality tracking
- System improvement metrics
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from operation_room.config import settings

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of user feedback."""
    RETRIEVAL = "retrieval"      # Feedback on search results
    HYPOTHESIS = "hypothesis"    # Feedback on hypothesis accuracy
    REPORT = "report"            # Feedback on generated report
    VALIDATION = "validation"    # Feedback on validation results
    GENERAL = "general"          # General feedback


class FeedbackSentiment(str, Enum):
    """Sentiment of feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class FeedbackEntry:
    """A feedback entry from the user."""
    feedback_id: str
    case_id: str
    feedback_type: FeedbackType
    sentiment: FeedbackSentiment
    target_id: Optional[str]  # ID of what was being evaluated
    rating: Optional[int]  # 1-5 rating if applicable
    comment: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LearningMetrics:
    """System learning metrics."""
    total_feedback: int
    positive_ratio: float
    retrieval_precision: float
    hypothesis_accuracy: float
    report_quality: float
    improvement_trend: float  # Positive = improving


class LearningLoop:
    """
    Learning loop for continuous improvement.
    
    Collects feedback and tracks system performance
    to enable calibration and improvement over time.
    """
    
    def __init__(self):
        """Initialize learning loop."""
        self._ensure_global_schema()
    
    def _ensure_global_schema(self) -> None:
        """Create global tables for learning."""
        import duckdb
        
        db_path = Path(settings.GLOBAL_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = duckdb.connect(str(db_path))
        try:
            # Feedback table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    feedback_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR,
                    feedback_type VARCHAR NOT NULL,
                    sentiment VARCHAR NOT NULL,
                    target_id VARCHAR,
                    rating INTEGER,
                    comment TEXT,
                    context JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Learning metrics snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learning_metrics (
                    snapshot_id VARCHAR PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_feedback INTEGER,
                    positive_ratio FLOAT,
                    retrieval_precision FLOAT,
                    hypothesis_accuracy FLOAT,
                    report_quality FLOAT,
                    improvement_trend FLOAT,
                    details JSON
                )
            """)
            
            # Improvement actions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS improvement_actions (
                    action_id VARCHAR PRIMARY KEY,
                    action_type VARCHAR NOT NULL,
                    description TEXT,
                    trigger_condition TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    impact JSON
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type 
                ON user_feedback(feedback_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_case 
                ON user_feedback(case_id)
            """)
            
        finally:
            conn.close()
    
    def _get_global_conn(self):
        """Get connection to global database."""
        import duckdb
        return duckdb.connect(str(settings.GLOBAL_DB_PATH))
    
    def record_feedback(
        self,
        feedback_type: FeedbackType,
        sentiment: FeedbackSentiment,
        case_id: Optional[str] = None,
        target_id: Optional[str] = None,
        rating: Optional[int] = None,
        comment: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record user feedback.
        
        Args:
            feedback_type: Type of feedback
            sentiment: Positive/negative/neutral
            case_id: Optional case ID
            target_id: ID of what was being evaluated
            rating: Optional 1-5 rating
            comment: Text comment
            context: Additional context
            
        Returns:
            Feedback ID
        """
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                INSERT INTO user_feedback (
                    feedback_id, case_id, feedback_type, sentiment,
                    target_id, rating, comment, context
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                feedback_id, case_id, feedback_type.value, sentiment.value,
                target_id, rating, comment,
                json.dumps(context) if context else None
            ])
            
        finally:
            conn.close()
        
        logger.info(f"Recorded {sentiment.value} feedback: {feedback_type.value}")
        
        # Trigger learning check
        self._check_learning_triggers()
        
        return feedback_id
    
    def record_retrieval_feedback(
        self,
        case_id: str,
        query: str,
        results: List[Dict[str, Any]],
        relevant_ids: List[str],
        irrelevant_ids: List[str]
    ) -> str:
        """
        Record feedback on retrieval results.
        
        Args:
            case_id: Case ID
            query: Search query
            results: Retrieved results
            relevant_ids: IDs user marked as relevant
            irrelevant_ids: IDs user marked as irrelevant
            
        Returns:
            Feedback ID
        """
        # Calculate implicit sentiment
        total_marked = len(relevant_ids) + len(irrelevant_ids)
        if total_marked == 0:
            sentiment = FeedbackSentiment.NEUTRAL
        elif len(relevant_ids) > len(irrelevant_ids):
            sentiment = FeedbackSentiment.POSITIVE
        else:
            sentiment = FeedbackSentiment.NEGATIVE
        
        # Calculate precision
        precision = len(relevant_ids) / len(results) if results else 0.0
        
        return self.record_feedback(
            feedback_type=FeedbackType.RETRIEVAL,
            sentiment=sentiment,
            case_id=case_id,
            context={
                'query': query,
                'total_results': len(results),
                'relevant_count': len(relevant_ids),
                'irrelevant_count': len(irrelevant_ids),
                'precision': precision,
                'relevant_ids': relevant_ids,
                'irrelevant_ids': irrelevant_ids
            }
        )
    
    def record_hypothesis_feedback(
        self,
        case_id: str,
        hypothesis_id: str,
        was_correct: bool,
        confidence_was_appropriate: bool = True
    ) -> str:
        """
        Record feedback on hypothesis accuracy.
        
        Args:
            case_id: Case ID
            hypothesis_id: Hypothesis ID
            was_correct: Whether hypothesis was correct
            confidence_was_appropriate: Whether confidence matched outcome
            
        Returns:
            Feedback ID
        """
        sentiment = FeedbackSentiment.POSITIVE if was_correct else FeedbackSentiment.NEGATIVE
        
        return self.record_feedback(
            feedback_type=FeedbackType.HYPOTHESIS,
            sentiment=sentiment,
            case_id=case_id,
            target_id=hypothesis_id,
            context={
                'was_correct': was_correct,
                'confidence_appropriate': confidence_was_appropriate
            }
        )
    
    def record_report_feedback(
        self,
        case_id: str,
        doc_id: str,
        rating: int,
        comment: str = "",
        issues: Optional[List[str]] = None
    ) -> str:
        """
        Record feedback on generated report.
        
        Args:
            case_id: Case ID
            doc_id: Document ID
            rating: 1-5 rating
            comment: Text feedback
            issues: List of specific issues
            
        Returns:
            Feedback ID
        """
        sentiment = (
            FeedbackSentiment.POSITIVE if rating >= 4
            else FeedbackSentiment.NEGATIVE if rating <= 2
            else FeedbackSentiment.NEUTRAL
        )
        
        return self.record_feedback(
            feedback_type=FeedbackType.REPORT,
            sentiment=sentiment,
            case_id=case_id,
            target_id=doc_id,
            rating=rating,
            comment=comment,
            context={
                'issues': issues or []
            }
        )
    
    def _check_learning_triggers(self) -> None:
        """Check if learning actions should be triggered."""
        conn = self._get_global_conn()
        try:
            # Get recent feedback stats
            recent = conn.execute("""
                SELECT feedback_type, sentiment, COUNT(*) as count
                FROM user_feedback
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
                GROUP BY feedback_type, sentiment
            """).fetchall()
            
            # Check for negative trend
            type_sentiments = {}
            for row in recent:
                ftype = row[0]
                if ftype not in type_sentiments:
                    type_sentiments[ftype] = {'positive': 0, 'negative': 0, 'neutral': 0}
                type_sentiments[ftype][row[1]] = row[2]
            
            for ftype, counts in type_sentiments.items():
                total = sum(counts.values())
                if total >= 10:  # Need minimum sample
                    negative_ratio = counts['negative'] / total
                    if negative_ratio > 0.4:
                        # Too many negative feedback - log improvement need
                        logger.warning(f"High negative feedback ratio for {ftype}: {negative_ratio:.2f}")
                        self._record_improvement_need(ftype, negative_ratio)
            
        finally:
            conn.close()
    
    def _record_improvement_need(self, area: str, negative_ratio: float) -> None:
        """Record that an area needs improvement."""
        conn = self._get_global_conn()
        try:
            action_id = f"imp_{uuid.uuid4().hex[:12]}"
            
            conn.execute("""
                INSERT INTO improvement_actions (
                    action_id, action_type, description, trigger_condition
                ) VALUES (?, ?, ?, ?)
            """, [
                action_id,
                'calibration_needed',
                f"High negative feedback in {area}",
                f"negative_ratio={negative_ratio:.2f}"
            ])
            
        finally:
            conn.close()
    
    def get_learning_metrics(self, days: int = 30) -> LearningMetrics:
        """
        Calculate learning metrics.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Learning metrics
        """
        conn = self._get_global_conn()
        try:
            # Total feedback and sentiment distribution
            feedback_stats = conn.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                    SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative
                FROM user_feedback
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """).fetchone()
            
            total = feedback_stats[0] or 0
            positive = feedback_stats[1] or 0
            positive_ratio = positive / total if total > 0 else 0.5
            
            # Retrieval precision
            retrieval_fb = conn.execute(f"""
                SELECT context
                FROM user_feedback
                WHERE feedback_type = 'retrieval'
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """).fetchall()
            
            if retrieval_fb:
                precisions = []
                for row in retrieval_fb:
                    if row[0]:
                        ctx = json.loads(row[0])
                        if 'precision' in ctx:
                            precisions.append(ctx['precision'])
                retrieval_precision = sum(precisions) / len(precisions) if precisions else 0.5
            else:
                retrieval_precision = 0.5
            
            # Hypothesis accuracy
            hypothesis_fb = conn.execute(f"""
                SELECT context
                FROM user_feedback
                WHERE feedback_type = 'hypothesis'
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """).fetchall()
            
            if hypothesis_fb:
                correct = sum(
                    1 for row in hypothesis_fb
                    if row[0] and json.loads(row[0]).get('was_correct', False)
                )
                hypothesis_accuracy = correct / len(hypothesis_fb)
            else:
                hypothesis_accuracy = 0.5
            
            # Report quality
            report_fb = conn.execute(f"""
                SELECT AVG(rating)
                FROM user_feedback
                WHERE feedback_type = 'report'
                AND rating IS NOT NULL
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
            """).fetchone()
            
            report_quality = (report_fb[0] or 3.0) / 5.0  # Normalize to 0-1
            
            # Improvement trend (compare first half to second half of period)
            half_days = days // 2
            first_half = conn.execute(f"""
                SELECT SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) * 1.0 / COUNT(*)
                FROM user_feedback
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'
                AND created_at < CURRENT_TIMESTAMP - INTERVAL '{half_days} days'
            """).fetchone()
            
            second_half = conn.execute(f"""
                SELECT SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) * 1.0 / COUNT(*)
                FROM user_feedback
                WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '{half_days} days'
            """).fetchone()
            
            first_ratio = first_half[0] or 0.5
            second_ratio = second_half[0] or 0.5
            improvement_trend = second_ratio - first_ratio
            
            return LearningMetrics(
                total_feedback=total,
                positive_ratio=positive_ratio,
                retrieval_precision=retrieval_precision,
                hypothesis_accuracy=hypothesis_accuracy,
                report_quality=report_quality,
                improvement_trend=improvement_trend
            )
            
        finally:
            conn.close()
    
    def save_metrics_snapshot(self) -> str:
        """Save current metrics as a snapshot."""
        metrics = self.get_learning_metrics()
        snapshot_id = f"snap_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                INSERT INTO learning_metrics (
                    snapshot_id, total_feedback, positive_ratio,
                    retrieval_precision, hypothesis_accuracy,
                    report_quality, improvement_trend
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                snapshot_id,
                metrics.total_feedback,
                metrics.positive_ratio,
                metrics.retrieval_precision,
                metrics.hypothesis_accuracy,
                metrics.report_quality,
                metrics.improvement_trend
            ])
            
        finally:
            conn.close()
        
        logger.info(f"Saved learning metrics snapshot: {snapshot_id}")
        return snapshot_id
    
    def get_improvement_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get recommendations for system improvement.
        
        Returns:
            List of improvement recommendations
        """
        metrics = self.get_learning_metrics()
        recommendations = []
        
        # Check retrieval quality
        if metrics.retrieval_precision < 0.6:
            recommendations.append({
                'area': 'retrieval',
                'priority': 'high',
                'recommendation': 'Retrieval precision is low. Consider:',
                'actions': [
                    'Review embedding model quality',
                    'Adjust BM25/semantic weight balance',
                    'Enable or tune reranking',
                    'Review evidence indexing coverage'
                ],
                'current_metric': metrics.retrieval_precision
            })
        
        # Check hypothesis accuracy
        if metrics.hypothesis_accuracy < 0.5:
            recommendations.append({
                'area': 'hypothesis',
                'priority': 'medium',
                'recommendation': 'Hypothesis accuracy needs improvement:',
                'actions': [
                    'Apply calibration adjustments',
                    'Review similar past hypotheses',
                    'Strengthen evidence requirements'
                ],
                'current_metric': metrics.hypothesis_accuracy
            })
        
        # Check report quality
        if metrics.report_quality < 0.6:
            recommendations.append({
                'area': 'report',
                'priority': 'medium',
                'recommendation': 'Report quality is below target:',
                'actions': [
                    'Review claim validation coverage',
                    'Improve evidence citation',
                    'Enhance template selection'
                ],
                'current_metric': metrics.report_quality
            })
        
        # Check overall trend
        if metrics.improvement_trend < -0.1:
            recommendations.append({
                'area': 'overall',
                'priority': 'high',
                'recommendation': 'System quality is declining:',
                'actions': [
                    'Review recent feedback for patterns',
                    'Check for data quality issues',
                    'Consider model retraining'
                ],
                'current_metric': metrics.improvement_trend
            })
        
        return recommendations
    
    def get_stats(self) -> Dict[str, Any]:
        """Get learning loop statistics."""
        metrics = self.get_learning_metrics()
        
        conn = self._get_global_conn()
        try:
            # Total feedback by type
            by_type = conn.execute("""
                SELECT feedback_type, COUNT(*) as count
                FROM user_feedback
                GROUP BY feedback_type
            """).fetchall()
            
            # Recent improvement actions
            recent_actions = conn.execute("""
                SELECT action_type, COUNT(*) as count
                FROM improvement_actions
                WHERE applied_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
                GROUP BY action_type
            """).fetchall()
            
            return {
                'total_feedback': metrics.total_feedback,
                'positive_ratio': round(metrics.positive_ratio, 3),
                'retrieval_precision': round(metrics.retrieval_precision, 3),
                'hypothesis_accuracy': round(metrics.hypothesis_accuracy, 3),
                'report_quality': round(metrics.report_quality, 3),
                'improvement_trend': round(metrics.improvement_trend, 3),
                'by_type': {r[0]: r[1] for r in by_type},
                'recent_improvements': {r[0]: r[1] for r in recent_actions},
                'recommendations': self.get_improvement_recommendations()
            }
            
        finally:
            conn.close()


# Singleton instance
_learning_loop: Optional[LearningLoop] = None


def get_learning_loop() -> LearningLoop:
    """Get the learning loop singleton."""
    global _learning_loop
    if _learning_loop is None:
        _learning_loop = LearningLoop()
    return _learning_loop
