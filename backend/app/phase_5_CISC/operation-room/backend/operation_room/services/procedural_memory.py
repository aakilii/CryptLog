"""
Procedural Memory Service - Oracle 26AI Phase 5.

Template-based procedural knowledge:
- Store and retrieve analysis templates
- Workflow patterns for investigations
- Best practice procedures
- Dynamic template selection based on context
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from operation_room.services.vector_store import get_vector_store, CollectionType
from operation_room.services.embedding_service import get_embedding_service
from operation_room.config import settings

logger = logging.getLogger(__name__)


class TemplateType(str, Enum):
    """Types of procedural templates."""
    ANALYSIS = "analysis"        # Data analysis procedures
    INVESTIGATION = "investigation"  # Investigation workflows
    REPORT = "report"            # Report generation templates
    HYPOTHESIS = "hypothesis"    # Hypothesis formation guides
    VALIDATION = "validation"    # Evidence validation procedures
    RESPONSE = "response"        # Incident response playbooks


class TemplateScope(str, Enum):
    """Scope of template application."""
    GLOBAL = "global"           # Applies to all investigations
    CATEGORY = "category"       # Applies to category (insider threat, malware, etc.)
    CASE_TYPE = "case_type"     # Applies to specific case types


@dataclass
class ProcedureStep:
    """A single step in a procedure."""
    step_number: int
    action: str
    description: str
    expected_output: str = ""
    tools_required: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProceduralTemplate:
    """A complete procedural template."""
    template_id: str
    name: str
    template_type: TemplateType
    scope: TemplateScope
    description: str
    category: str = "general"
    steps: List[ProcedureStep] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    expected_duration_minutes: int = 30
    confidence_boost: float = 0.1  # Boost to confidence when template is followed
    success_rate: float = 0.0
    usage_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProceduralMemory:
    """
    Procedural memory service for investigation templates.
    
    Features:
    - Store and manage procedural templates
    - Semantic search for relevant procedures
    - Track template usage and success rates
    - Dynamic template recommendations
    """
    
    # Built-in templates for common scenarios
    BUILT_IN_TEMPLATES: List[Dict[str, Any]] = [
        {
            "template_id": "tpl_anomaly_investigation",
            "name": "Anomaly Investigation Procedure",
            "template_type": TemplateType.INVESTIGATION,
            "scope": TemplateScope.GLOBAL,
            "description": "Standard procedure for investigating detected anomalies",
            "category": "anomaly",
            "steps": [
                {"step_number": 1, "action": "Identify Anomaly Context", 
                 "description": "Determine the scope and context of the anomaly",
                 "expected_output": "Anomaly classification and severity assessment"},
                {"step_number": 2, "action": "Gather Related Events",
                 "description": "Collect all events within the anomaly window (±2 hours)",
                 "expected_output": "Timeline of related events"},
                {"step_number": 3, "action": "Identify Actors",
                 "description": "Identify all actors (users, systems) involved",
                 "expected_output": "Actor list with activity summary"},
                {"step_number": 4, "action": "Correlation Analysis",
                 "description": "Correlate anomaly with other data sources",
                 "expected_output": "Correlation findings"},
                {"step_number": 5, "action": "Form Hypothesis",
                 "description": "Develop hypothesis explaining the anomaly",
                 "expected_output": "Documented hypothesis with confidence score"},
            ],
            "expected_duration_minutes": 45,
            "confidence_boost": 0.15,
        },
        {
            "template_id": "tpl_insider_threat",
            "name": "Insider Threat Assessment",
            "template_type": TemplateType.INVESTIGATION,
            "scope": TemplateScope.CATEGORY,
            "description": "Procedure for assessing potential insider threat indicators",
            "category": "insider_threat",
            "steps": [
                {"step_number": 1, "action": "Behavioral Baseline",
                 "description": "Establish normal behavioral baseline for the actor",
                 "expected_output": "Baseline activity profile"},
                {"step_number": 2, "action": "Deviation Analysis",
                 "description": "Identify deviations from baseline behavior",
                 "expected_output": "List of behavioral deviations with severity"},
                {"step_number": 3, "action": "Access Pattern Review",
                 "description": "Review data access patterns and permissions",
                 "expected_output": "Access audit summary"},
                {"step_number": 4, "action": "Data Movement Tracking",
                 "description": "Track any unusual data movement or exfiltration attempts",
                 "expected_output": "Data flow analysis"},
                {"step_number": 5, "action": "Risk Scoring",
                 "description": "Calculate composite risk score",
                 "expected_output": "Risk score with contributing factors"},
            ],
            "expected_duration_minutes": 60,
            "confidence_boost": 0.2,
        },
        {
            "template_id": "tpl_network_analysis",
            "name": "Network Traffic Analysis",
            "template_type": TemplateType.ANALYSIS,
            "scope": TemplateScope.GLOBAL,
            "description": "Standard procedure for analyzing network traffic patterns",
            "category": "network",
            "steps": [
                {"step_number": 1, "action": "Traffic Volume Analysis",
                 "description": "Analyze traffic volumes by source/destination",
                 "expected_output": "Traffic volume summary"},
                {"step_number": 2, "action": "Protocol Distribution",
                 "description": "Review protocol usage and anomalies",
                 "expected_output": "Protocol analysis"},
                {"step_number": 3, "action": "Connection Patterns",
                 "description": "Identify unusual connection patterns",
                 "expected_output": "Connection pattern findings"},
                {"step_number": 4, "action": "External Communication",
                 "description": "Analyze external communication targets",
                 "expected_output": "External communication summary"},
            ],
            "expected_duration_minutes": 30,
            "confidence_boost": 0.1,
        },
        {
            "template_id": "tpl_report_executive",
            "name": "Executive Summary Report",
            "template_type": TemplateType.REPORT,
            "scope": TemplateScope.GLOBAL,
            "description": "Template for generating executive-level summaries",
            "category": "report",
            "steps": [
                {"step_number": 1, "action": "Key Findings Summary",
                 "description": "Summarize top 3-5 key findings",
                 "expected_output": "Bullet-point key findings"},
                {"step_number": 2, "action": "Risk Assessment",
                 "description": "Overall risk assessment with severity",
                 "expected_output": "Risk level and justification"},
                {"step_number": 3, "action": "Recommendations",
                 "description": "Prioritized action recommendations",
                 "expected_output": "Numbered recommendations"},
                {"step_number": 4, "action": "Timeline Summary",
                 "description": "High-level timeline of events",
                 "expected_output": "Visual timeline or table"},
            ],
            "expected_duration_minutes": 20,
            "confidence_boost": 0.05,
        },
        {
            "template_id": "tpl_hypothesis_validation",
            "name": "Hypothesis Validation Procedure",
            "template_type": TemplateType.VALIDATION,
            "scope": TemplateScope.GLOBAL,
            "description": "Standard procedure for validating investigation hypotheses",
            "category": "validation",
            "steps": [
                {"step_number": 1, "action": "Evidence Inventory",
                 "description": "List all evidence supporting or contradicting hypothesis",
                 "expected_output": "Evidence inventory table"},
                {"step_number": 2, "action": "Alternative Hypotheses",
                 "description": "Consider and document alternative explanations",
                 "expected_output": "Alternative hypothesis list"},
                {"step_number": 3, "action": "Evidence Gaps",
                 "description": "Identify gaps in evidence chain",
                 "expected_output": "Gap analysis"},
                {"step_number": 4, "action": "Confidence Assessment",
                 "description": "Assess confidence level with justification",
                 "expected_output": "Confidence score and rationale"},
            ],
            "expected_duration_minutes": 25,
            "confidence_boost": 0.15,
        },
    ]
    
    def __init__(self):
        """Initialize procedural memory."""
        self._vector_store = get_vector_store()
        self._embedding_service = get_embedding_service()
        self._ensure_global_schema()
        self._load_built_in_templates()
    
    def _ensure_global_schema(self) -> None:
        """Create global tables for templates."""
        import duckdb
        
        db_path = Path(settings.GLOBAL_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = duckdb.connect(str(db_path))
        try:
            # Templates table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS procedural_templates (
                    template_id VARCHAR PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    template_type VARCHAR NOT NULL,
                    scope VARCHAR NOT NULL,
                    description TEXT,
                    category VARCHAR DEFAULT 'general',
                    steps JSON,
                    prerequisites JSON,
                    expected_duration_minutes INTEGER DEFAULT 30,
                    confidence_boost FLOAT DEFAULT 0.1,
                    success_rate FLOAT DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON
                )
            """)
            
            # Template usage tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS template_usage (
                    usage_id VARCHAR PRIMARY KEY,
                    template_id VARCHAR NOT NULL,
                    case_id VARCHAR NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    success BOOLEAN,
                    steps_completed INTEGER DEFAULT 0,
                    feedback JSON
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_template_type 
                ON procedural_templates(template_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_template_category 
                ON procedural_templates(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_template 
                ON template_usage(template_id)
            """)
            
        finally:
            conn.close()
    
    def _get_global_conn(self):
        """Get connection to global database."""
        import duckdb
        return duckdb.connect(str(settings.GLOBAL_DB_PATH))
    
    def _load_built_in_templates(self) -> None:
        """Load built-in templates if not already present."""
        conn = self._get_global_conn()
        try:
            for template_data in self.BUILT_IN_TEMPLATES:
                existing = conn.execute("""
                    SELECT template_id FROM procedural_templates WHERE template_id = ?
                """, [template_data['template_id']]).fetchone()
                
                if not existing:
                    steps_json = json.dumps(template_data.get('steps', []))
                    
                    conn.execute("""
                        INSERT INTO procedural_templates (
                            template_id, name, template_type, scope, description,
                            category, steps, expected_duration_minutes, confidence_boost
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        template_data['template_id'],
                        template_data['name'],
                        template_data['template_type'].value if isinstance(template_data['template_type'], TemplateType) else template_data['template_type'],
                        template_data['scope'].value if isinstance(template_data['scope'], TemplateScope) else template_data['scope'],
                        template_data['description'],
                        template_data.get('category', 'general'),
                        steps_json,
                        template_data.get('expected_duration_minutes', 30),
                        template_data.get('confidence_boost', 0.1)
                    ])
                    
                    # Add to vector store
                    self._add_template_to_vector_store(template_data)
                    
            logger.info(f"Loaded {len(self.BUILT_IN_TEMPLATES)} built-in templates")
        finally:
            conn.close()
    
    def _add_template_to_vector_store(self, template_data: Dict[str, Any]) -> None:
        """Add template to vector store for semantic search."""
        try:
            # Create searchable content
            content = f"{template_data['name']}: {template_data['description']}"
            if template_data.get('steps'):
                step_texts = [s.get('action', '') + ": " + s.get('description', '') 
                             for s in template_data['steps']]
                content += " Steps: " + "; ".join(step_texts)
            
            self._vector_store.add_document(
                collection_type=CollectionType.TEMPLATES,
                content=content,
                metadata={
                    'template_type': template_data['template_type'].value if isinstance(template_data['template_type'], TemplateType) else template_data['template_type'],
                    'category': template_data.get('category', 'general'),
                    'scope': template_data['scope'].value if isinstance(template_data['scope'], TemplateScope) else template_data['scope']
                },
                doc_id=template_data['template_id']
            )
        except Exception as e:
            logger.warning(f"Failed to add template to vector store: {e}")
    
    def add_template(
        self,
        name: str,
        template_type: TemplateType,
        description: str,
        steps: List[Dict[str, Any]],
        scope: TemplateScope = TemplateScope.GLOBAL,
        category: str = "general",
        prerequisites: Optional[List[str]] = None,
        expected_duration_minutes: int = 30,
        confidence_boost: float = 0.1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a new procedural template.
        
        Args:
            name: Template name
            template_type: Type of template
            description: Template description
            steps: List of procedure steps
            scope: Application scope
            category: Category for filtering
            prerequisites: Required prerequisites
            expected_duration_minutes: Expected time to complete
            confidence_boost: Confidence boost when followed
            metadata: Additional metadata
            
        Returns:
            Template ID
        """
        template_id = f"tpl_{uuid.uuid4().hex[:12]}"
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                INSERT INTO procedural_templates (
                    template_id, name, template_type, scope, description, category,
                    steps, prerequisites, expected_duration_minutes, confidence_boost, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                template_id, name, template_type.value, scope.value, description, category,
                json.dumps(steps), json.dumps(prerequisites or []),
                expected_duration_minutes, confidence_boost,
                json.dumps(metadata) if metadata else None
            ])
            
            # Add to vector store
            self._add_template_to_vector_store({
                'template_id': template_id,
                'name': name,
                'template_type': template_type,
                'scope': scope,
                'description': description,
                'category': category,
                'steps': steps
            })
            
        finally:
            conn.close()
        
        logger.info(f"Added template {template_id}: {name}")
        return template_id
    
    def get_template(self, template_id: str) -> Optional[ProceduralTemplate]:
        """Get a template by ID."""
        conn = self._get_global_conn()
        try:
            row = conn.execute("""
                SELECT template_id, name, template_type, scope, description, category,
                       steps, prerequisites, expected_duration_minutes, confidence_boost,
                       success_rate, usage_count, created_at, updated_at, metadata
                FROM procedural_templates
                WHERE template_id = ?
            """, [template_id]).fetchone()
            
            if not row:
                return None
            
            steps_data = json.loads(row[6]) if row[6] else []
            steps = [
                ProcedureStep(
                    step_number=s.get('step_number', i+1),
                    action=s.get('action', ''),
                    description=s.get('description', ''),
                    expected_output=s.get('expected_output', ''),
                    tools_required=s.get('tools_required', []),
                    conditions=s.get('conditions', {})
                )
                for i, s in enumerate(steps_data)
            ]
            
            return ProceduralTemplate(
                template_id=row[0],
                name=row[1],
                template_type=TemplateType(row[2]),
                scope=TemplateScope(row[3]),
                description=row[4],
                category=row[5],
                steps=steps,
                prerequisites=json.loads(row[7]) if row[7] else [],
                expected_duration_minutes=row[8],
                confidence_boost=row[9],
                success_rate=row[10] or 0.0,
                usage_count=row[11] or 0,
                created_at=row[12],
                updated_at=row[13],
                metadata=json.loads(row[14]) if row[14] else {}
            )
        finally:
            conn.close()
    
    def find_templates(
        self,
        query: str,
        template_type: Optional[TemplateType] = None,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[ProceduralTemplate]:
        """
        Find relevant templates using semantic search.
        
        Args:
            query: Search query
            template_type: Filter by type
            category: Filter by category
            n_results: Maximum results
            
        Returns:
            List of matching templates
        """
        # Build metadata filter
        where_filter = {}
        if template_type:
            where_filter['template_type'] = template_type.value
        if category:
            where_filter['category'] = category
        
        # Semantic search
        try:
            results = self._vector_store.search(
                collection_type=CollectionType.TEMPLATES,
                query=query,
                n_results=n_results,
                where=where_filter if where_filter else None
            )
        except Exception as e:
            logger.warning(f"Template search failed: {e}")
            results = []
        
        # Get full templates
        templates = []
        for result in results:
            template = self.get_template(result.id)
            if template:
                templates.append(template)
        
        return templates
    
    def recommend_templates(
        self,
        context: str,
        current_phase: str = "discovery",
        case_category: Optional[str] = None
    ) -> List[Tuple[ProceduralTemplate, float]]:
        """
        Recommend templates based on investigation context.
        
        Args:
            context: Current investigation context
            current_phase: Current investigation phase
            case_category: Case category if known
            
        Returns:
            List of (template, relevance_score) tuples
        """
        # Map phases to template types
        phase_type_map = {
            "discovery": [TemplateType.ANALYSIS],
            "analysis": [TemplateType.ANALYSIS, TemplateType.INVESTIGATION],
            "correlation": [TemplateType.INVESTIGATION],
            "hypothesis": [TemplateType.HYPOTHESIS, TemplateType.VALIDATION],
            "validation": [TemplateType.VALIDATION],
            "reporting": [TemplateType.REPORT],
        }
        
        preferred_types = phase_type_map.get(current_phase, [])
        
        # Find templates matching context
        templates = self.find_templates(context, n_results=10)
        
        # Score and rank
        scored = []
        for template in templates:
            score = 0.5  # Base score
            
            # Boost for matching type
            if template.template_type in preferred_types:
                score += 0.2
            
            # Boost for matching category
            if case_category and template.category == case_category:
                score += 0.15
            
            # Boost for success rate
            if template.success_rate > 0.7:
                score += 0.1
            
            # Penalize unused templates slightly
            if template.usage_count == 0:
                score -= 0.05
            
            scored.append((template, min(1.0, score)))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored[:5]
    
    def start_template_usage(self, template_id: str, case_id: str) -> str:
        """
        Record start of template usage.
        
        Args:
            template_id: Template being used
            case_id: Case ID
            
        Returns:
            Usage ID
        """
        usage_id = f"use_{uuid.uuid4().hex[:12]}"
        
        conn = self._get_global_conn()
        try:
            conn.execute("""
                INSERT INTO template_usage (usage_id, template_id, case_id)
                VALUES (?, ?, ?)
            """, [usage_id, template_id, case_id])
            
            # Increment usage count
            conn.execute("""
                UPDATE procedural_templates
                SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE template_id = ?
            """, [template_id])
            
        finally:
            conn.close()
        
        return usage_id
    
    def complete_template_usage(
        self,
        usage_id: str,
        success: bool,
        steps_completed: int,
        feedback: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record completion of template usage.
        
        Args:
            usage_id: Usage ID from start_template_usage
            success: Whether the template helped
            steps_completed: Number of steps completed
            feedback: Optional feedback
        """
        conn = self._get_global_conn()
        try:
            conn.execute("""
                UPDATE template_usage
                SET completed_at = CURRENT_TIMESTAMP,
                    success = ?,
                    steps_completed = ?,
                    feedback = ?
                WHERE usage_id = ?
            """, [success, steps_completed, json.dumps(feedback) if feedback else None, usage_id])
            
            # Get template ID
            template_id = conn.execute("""
                SELECT template_id FROM template_usage WHERE usage_id = ?
            """, [usage_id]).fetchone()
            
            if template_id:
                # Update success rate
                stats = conn.execute("""
                    SELECT COUNT(*) as total, SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
                    FROM template_usage
                    WHERE template_id = ? AND completed_at IS NOT NULL
                """, [template_id[0]]).fetchone()
                
                if stats[0] > 0:
                    success_rate = stats[1] / stats[0]
                    conn.execute("""
                        UPDATE procedural_templates
                        SET success_rate = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE template_id = ?
                    """, [success_rate, template_id[0]])
            
        finally:
            conn.close()
    
    def list_templates(
        self,
        template_type: Optional[TemplateType] = None,
        category: Optional[str] = None
    ) -> List[ProceduralTemplate]:
        """List all templates with optional filtering."""
        conn = self._get_global_conn()
        try:
            conditions = []
            params = []
            
            if template_type:
                conditions.append("template_type = ?")
                params.append(template_type.value)
            if category:
                conditions.append("category = ?")
                params.append(category)
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            rows = conn.execute(f"""
                SELECT template_id FROM procedural_templates
                {where_clause}
                ORDER BY usage_count DESC, success_rate DESC
            """, params).fetchall()
            
            return [self.get_template(r[0]) for r in rows if r[0]]
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get procedural memory statistics."""
        conn = self._get_global_conn()
        try:
            # Template stats
            template_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(success_rate) as avg_success_rate,
                    SUM(usage_count) as total_usages
                FROM procedural_templates
            """).fetchone()
            
            # By type
            by_type = conn.execute("""
                SELECT template_type, COUNT(*) as count
                FROM procedural_templates
                GROUP BY template_type
            """).fetchall()
            
            return {
                'total_templates': template_stats[0] or 0,
                'average_success_rate': round(template_stats[1] or 0, 3),
                'total_usages': template_stats[2] or 0,
                'by_type': {r[0]: r[1] for r in by_type}
            }
        finally:
            conn.close()


# Singleton instance
_procedural_memory: Optional[ProceduralMemory] = None


def get_procedural_memory() -> ProceduralMemory:
    """Get the procedural memory singleton."""
    global _procedural_memory
    if _procedural_memory is None:
        _procedural_memory = ProceduralMemory()
    return _procedural_memory
