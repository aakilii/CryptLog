"""
Section Generation Pipeline - Intelligent Report Generation Phase 5.

Orchestrates section-by-section report generation with:
- Per-section hypothesis evaluation
- Chart decision engine
- Evidence integration from vault
- Position tracking
- Verification checkpoints
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from operation_room.services.report_evidence_service import (
    get_report_evidence_service,
    RedactionMode,
    AccessPurpose,
    EvidenceKey
)
from operation_room.services.report_learning_service import get_report_learning_service
from operation_room.services.scenario_analyzer import ScenarioContext
from operation_room.services.llm_service import get_llm
from operation_room.database import open_vault, get_vault_path
from operation_room.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class SectionStatus(str, Enum):
    """Status of a section in generation."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"
    FAILED = "failed"


class ChartType(str, Enum):
    """Standard chart types for reports."""
    TIMELINE = "timeline"
    BAR = "bar"
    PIE = "pie"
    LINE = "line"
    NETWORK = "network"
    HEATMAP = "heatmap"
    TABLE = "table"
    TREE = "tree"
    FLOW = "flow"
    SANKEY = "sankey"


@dataclass
class Hypothesis:
    """A hypothesis for a section."""
    hypothesis_id: str
    section_id: str
    statement: str
    evidence_keys: List[str]           # Keys supporting this hypothesis
    confidence: float = 0.5
    status: str = "proposed"           # proposed, supported, refuted, inconclusive
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "section_id": self.section_id,
            "statement": self.statement,
            "evidence_keys": self.evidence_keys,
            "confidence": self.confidence,
            "status": self.status,
            "reasoning": self.reasoning
        }


@dataclass
class ChartDecision:
    """Decision about what chart to use."""
    decision_id: str
    section_id: str
    chart_type: ChartType
    title: str
    data_source: str                   # Where the data comes from
    evidence_keys: List[str]           # Evidence keys used
    config: Dict[str, Any] = field(default_factory=dict)
    position_hint: int = 0             # Suggested position in section
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "section_id": self.section_id,
            "chart_type": self.chart_type.value,
            "title": self.title,
            "data_source": self.data_source,
            "evidence_keys": self.evidence_keys,
            "config": self.config,
            "position_hint": self.position_hint,
            "reasoning": self.reasoning
        }


@dataclass
class SectionContent:
    """Generated content for a section."""
    section_id: str
    title: str
    level: int
    
    # Content elements
    text_blocks: List[Dict[str, Any]] = field(default_factory=list)
    charts: List[ChartDecision] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    
    # Hypotheses
    hypotheses: List[Hypothesis] = field(default_factory=list)
    
    # Evidence references
    evidence_keys: List[str] = field(default_factory=list)
    
    # Position tracking
    start_position: int = 0
    end_position: int = 0
    estimated_height: int = 0          # In PDF units
    
    # Status
    status: SectionStatus = SectionStatus.PENDING
    
    # Metadata
    generated_at: Optional[datetime] = None
    verified: bool = False
    verification_notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "level": self.level,
            "text_blocks": self.text_blocks,
            "charts": [c.to_dict() for c in self.charts],
            "tables": self.tables,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "evidence_keys": self.evidence_keys,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "estimated_height": self.estimated_height,
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "verified": self.verified,
            "verification_notes": self.verification_notes
        }


@dataclass
class GenerationPlan:
    """Plan for generating a full report."""
    plan_id: str
    case_id: str
    scenario_session_id: str
    sections: List[SectionContent]
    
    # Progress tracking
    current_section_idx: int = 0
    total_sections: int = 0
    
    # Mode
    auto_pilot: bool = False
    human_approval_required: bool = True
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "case_id": self.case_id,
            "scenario_session_id": self.scenario_session_id,
            "sections": [s.to_dict() for s in self.sections],
            "current_section_idx": self.current_section_idx,
            "total_sections": self.total_sections,
            "auto_pilot": self.auto_pilot,
            "human_approval_required": self.human_approval_required,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CHART DECISION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ChartDecisionEngine:
    """
    Decides what charts to generate for each section.
    
    Uses:
    - Section content/topic analysis
    - Evidence type analysis  
    - Learned patterns from previous reports
    """
    
    # Chart recommendations based on content patterns
    CONTENT_CHART_MAP = {
        "timeline": [ChartType.TIMELINE, ChartType.LINE],
        "transfer": [ChartType.SANKEY, ChartType.FLOW],
        "distribution": [ChartType.PIE, ChartType.BAR],
        "comparison": [ChartType.BAR, ChartType.TABLE],
        "network": [ChartType.NETWORK, ChartType.TREE],
        "trend": [ChartType.LINE, ChartType.TIMELINE],
        "frequency": [ChartType.BAR, ChartType.HEATMAP],
        "hierarchy": [ChartType.TREE, ChartType.FLOW],
        "summary": [ChartType.TABLE, ChartType.PIE],
    }
    
    # Keywords that suggest chart types
    CHART_KEYWORDS = {
        ChartType.TIMELINE: ["timeline", "chronology", "sequence", "when", "date", "time"],
        ChartType.BAR: ["count", "frequency", "comparison", "volume", "amount"],
        ChartType.PIE: ["distribution", "percentage", "breakdown", "share", "portion"],
        ChartType.LINE: ["trend", "over time", "progression", "change"],
        ChartType.NETWORK: ["connection", "relationship", "network", "communication"],
        ChartType.HEATMAP: ["intensity", "density", "activity", "pattern"],
        ChartType.TABLE: ["details", "list", "summary", "records"],
        ChartType.FLOW: ["flow", "process", "transfer", "movement"],
        ChartType.SANKEY: ["flow", "transfer", "movement", "allocation"],
    }
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._learning_service = get_report_learning_service()
    
    def decide_charts(
        self,
        section_title: str,
        section_content: str,
        evidence_keys: List[EvidenceKey],
        learned_suggestions: Optional[List[str]] = None
    ) -> List[ChartDecision]:
        """
        Decide what charts to include in a section.
        
        Args:
            section_title: Title of the section
            section_content: Text content of the section
            evidence_keys: Available evidence keys
            learned_suggestions: Chart suggestions from learning system
            
        Returns:
            List of chart decisions
        """
        decisions = []
        combined_text = f"{section_title} {section_content}".lower()
        
        # Score each chart type based on keywords
        chart_scores: Dict[ChartType, float] = {}
        
        for chart_type, keywords in self.CHART_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > 0:
                chart_scores[chart_type] = score
        
        # Add learned suggestions with bonus score
        if learned_suggestions:
            for suggestion in learned_suggestions:
                try:
                    ct = ChartType(suggestion)
                    chart_scores[ct] = chart_scores.get(ct, 0) + 2
                except ValueError:
                    pass
        
        # Evidence-based boosting
        for key in evidence_keys:
            if key.category == "timeline":
                chart_scores[ChartType.TIMELINE] = chart_scores.get(ChartType.TIMELINE, 0) + 1.5
            elif key.category == "network":
                chart_scores[ChartType.NETWORK] = chart_scores.get(ChartType.NETWORK, 0) + 1.5
            elif key.category == "transfer":
                chart_scores[ChartType.SANKEY] = chart_scores.get(ChartType.SANKEY, 0) + 1.5
        
        # Select top charts (max 3 per section)
        sorted_charts = sorted(chart_scores.items(), key=lambda x: -x[1])[:3]
        
        for idx, (chart_type, score) in enumerate(sorted_charts):
            if score >= 1:  # Minimum threshold
                decision = ChartDecision(
                    decision_id=f"CHT-{uuid.uuid4().hex[:6].upper()}",
                    section_id="",  # Set by caller
                    chart_type=chart_type,
                    title=self._generate_chart_title(section_title, chart_type),
                    data_source=self._determine_data_source(chart_type, evidence_keys),
                    evidence_keys=[k.key_id for k in evidence_keys[:5]],
                    position_hint=idx,
                    reasoning=f"Score: {score:.1f} based on content analysis"
                )
                decisions.append(decision)
        
        return decisions
    
    def _generate_chart_title(self, section_title: str, chart_type: ChartType) -> str:
        """Generate a title for the chart."""
        templates = {
            ChartType.TIMELINE: f"{section_title} - Event Timeline",
            ChartType.BAR: f"{section_title} - Distribution",
            ChartType.PIE: f"{section_title} - Breakdown",
            ChartType.LINE: f"{section_title} - Trend Analysis",
            ChartType.NETWORK: f"{section_title} - Network Graph",
            ChartType.HEATMAP: f"{section_title} - Activity Heatmap",
            ChartType.TABLE: f"{section_title} - Summary",
            ChartType.FLOW: f"{section_title} - Process Flow",
            ChartType.SANKEY: f"{section_title} - Data Flow",
        }
        return templates.get(chart_type, f"{section_title} - Visualization")
    
    def _determine_data_source(
        self,
        chart_type: ChartType,
        evidence_keys: List[EvidenceKey]
    ) -> str:
        """Determine where chart data should come from."""
        # Map chart types to preferred evidence categories
        category_preferences = {
            ChartType.TIMELINE: ["timeline", "event", "log"],
            ChartType.NETWORK: ["network", "connection", "ip"],
            ChartType.BAR: ["count", "frequency", "summary"],
            ChartType.PIE: ["distribution", "category", "type"],
            ChartType.SANKEY: ["transfer", "flow", "connection"],
        }
        
        prefs = category_preferences.get(chart_type, [])
        
        for key in evidence_keys:
            if key.category in prefs:
                return f"evidence:{key.key_id}"
        
        # Default to aggregated findings
        return "module:aggregated_findings"


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisGenerator:
    """
    Generates and evaluates hypotheses for report sections.
    
    Uses evidence keys (not values) for AI-safe processing.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._evidence_service = get_report_evidence_service(case_id)
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM."""
        if self._llm is None:
            try:
                self._llm = get_llm()
            except Exception as e:
                logger.warning(f"LLM not available: {e}")
        return self._llm
    
    def generate_hypotheses(
        self,
        section_title: str,
        section_topic: str,
        scenario_context: Dict[str, Any],
        evidence_keys: List[EvidenceKey]
    ) -> List[Hypothesis]:
        """
        Generate hypotheses for a section.
        
        Args:
            section_title: Title of the section
            section_topic: Topic/content focus
            scenario_context: Context from scenario analysis
            evidence_keys: Available evidence (keys only)
            
        Returns:
            List of hypotheses
        """
        hypotheses = []
        
        # Build AI-safe evidence references
        evidence_refs = [k.to_ai_reference() for k in evidence_keys]
        
        # Generate hypotheses based on section type
        if "timeline" in section_title.lower() or "chronology" in section_title.lower():
            hypotheses.extend(self._timeline_hypotheses(evidence_keys))
        
        if "transfer" in section_title.lower() or "exfiltration" in section_title.lower():
            hypotheses.extend(self._transfer_hypotheses(evidence_keys, scenario_context))
        
        if "network" in section_title.lower() or "connection" in section_title.lower():
            hypotheses.extend(self._network_hypotheses(evidence_keys))
        
        if "user" in section_title.lower() or "suspect" in section_title.lower():
            hypotheses.extend(self._user_hypotheses(evidence_keys, scenario_context))
        
        # Generic hypothesis if nothing specific
        if not hypotheses:
            hypotheses.append(Hypothesis(
                hypothesis_id=f"HYP-{uuid.uuid4().hex[:6].upper()}",
                section_id="",
                statement=f"Evidence supports the conclusions in {section_title}",
                evidence_keys=[k.key_id for k in evidence_keys[:5]],
                confidence=0.5,
                status="proposed"
            ))
        
        return hypotheses
    
    def _timeline_hypotheses(self, evidence_keys: List[EvidenceKey]) -> List[Hypothesis]:
        """Generate timeline-related hypotheses."""
        hypotheses = []
        
        timeline_keys = [k for k in evidence_keys if k.category in ["timeline", "event", "log"]]
        
        if timeline_keys:
            hypotheses.append(Hypothesis(
                hypothesis_id=f"HYP-{uuid.uuid4().hex[:6].upper()}",
                section_id="",
                statement="The events follow a clear chronological sequence indicating planned activity",
                evidence_keys=[k.key_id for k in timeline_keys[:5]],
                confidence=0.6,
                status="proposed",
                reasoning="Based on timeline evidence patterns"
            ))
        
        return hypotheses
    
    def _transfer_hypotheses(
        self,
        evidence_keys: List[EvidenceKey],
        scenario_context: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Generate data transfer hypotheses."""
        hypotheses = []
        
        transfer_keys = [k for k in evidence_keys if k.category in ["transfer", "file", "usb"]]
        
        channels = scenario_context.get("transfer_channels", [])
        
        if transfer_keys and channels:
            hypotheses.append(Hypothesis(
                hypothesis_id=f"HYP-{uuid.uuid4().hex[:6].upper()}",
                section_id="",
                statement=f"Data was transferred using multiple channels: {', '.join(channels)}",
                evidence_keys=[k.key_id for k in transfer_keys[:5]],
                confidence=0.7,
                status="proposed",
                reasoning="Multiple transfer channels detected in evidence"
            ))
        
        return hypotheses
    
    def _network_hypotheses(self, evidence_keys: List[EvidenceKey]) -> List[Hypothesis]:
        """Generate network-related hypotheses."""
        hypotheses = []
        
        network_keys = [k for k in evidence_keys if k.category in ["network", "ip", "connection"]]
        
        if network_keys:
            hypotheses.append(Hypothesis(
                hypothesis_id=f"HYP-{uuid.uuid4().hex[:6].upper()}",
                section_id="",
                statement="Network connections reveal communication patterns between devices",
                evidence_keys=[k.key_id for k in network_keys[:5]],
                confidence=0.6,
                status="proposed",
                reasoning="Network evidence indicates device communication"
            ))
        
        return hypotheses
    
    def _user_hypotheses(
        self,
        evidence_keys: List[EvidenceKey],
        scenario_context: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Generate user/suspect-related hypotheses."""
        hypotheses = []
        
        user_keys = [k for k in evidence_keys if k.category in ["user", "suspect", "activity"]]
        suspects = scenario_context.get("suspects", [])
        
        if user_keys and suspects:
            hypotheses.append(Hypothesis(
                hypothesis_id=f"HYP-{uuid.uuid4().hex[:6].upper()}",
                section_id="",
                statement="User activity patterns correlate with the incident timeline",
                evidence_keys=[k.key_id for k in user_keys[:5]],
                confidence=0.6,
                status="proposed",
                reasoning="User evidence aligns with scenario suspects"
            ))
        
        return hypotheses
    
    def evaluate_hypothesis(
        self,
        hypothesis: Hypothesis,
        additional_evidence: List[EvidenceKey]
    ) -> Hypothesis:
        """
        Evaluate a hypothesis against evidence.
        
        Updates confidence and status based on evidence.
        """
        supporting = 0
        contradicting = 0
        
        for key in additional_evidence:
            # Simple heuristic - check if evidence category aligns
            if any(cat in hypothesis.statement.lower() for cat in [key.category]):
                supporting += 1
            # Could add more sophisticated evaluation with LLM
        
        total = supporting + contradicting + len(hypothesis.evidence_keys)
        
        if total > 0:
            hypothesis.confidence = min(0.9, (supporting + len(hypothesis.evidence_keys)) / total)
        
        if hypothesis.confidence >= 0.7:
            hypothesis.status = "supported"
        elif hypothesis.confidence <= 0.3:
            hypothesis.status = "refuted"
        else:
            hypothesis.status = "inconclusive"
        
        hypothesis.reasoning = f"Evaluated with {supporting} supporting, {contradicting} contradicting evidence"
        
        return hypothesis


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION GENERATION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class SectionGenerationPipeline:
    """
    Orchestrates section-by-section report generation.
    
    Flow:
    1. Create generation plan from structure recommendation
    2. For each section:
       a. Gather evidence keys
       b. Generate hypotheses
       c. Decide on charts
       d. Generate text content
       e. Verify alignment
       f. Get approval (human or auto-pilot)
    3. Track positions and maintain consistency
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._evidence_service = get_report_evidence_service(case_id)
        self._learning_service = get_report_learning_service()
        self._chart_engine = ChartDecisionEngine(case_id)
        self._hypothesis_gen = HypothesisGenerator(case_id)
        self._plans: Dict[str, GenerationPlan] = {}
        state_dir = settings.DATA_DIR / "deep_research_state"
        state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = state_dir / f"generation_plans_{case_id}.json"
        self._load_plans()

    def _load_plans(self) -> None:
        """Load persisted generation plans for this case."""
        if not self._state_file.exists():
            return

        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load generation plans for %s: %s", self.case_id, exc)
            return

        raw_plans = payload.get("plans") if isinstance(payload, dict) else None
        if not isinstance(raw_plans, list):
            return

        restored: Dict[str, GenerationPlan] = {}
        for item in raw_plans:
            if not isinstance(item, dict):
                continue
            try:
                plan = self._plan_from_dict(item)
                restored[plan.plan_id] = plan
            except Exception as exc:
                logger.warning("Skipping invalid generation plan during restore: %s", exc)

        self._plans = restored

    def _persist_plans(self) -> None:
        """Persist generation plans for restart safety."""
        try:
            payload = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "case_id": self.case_id,
                "plans": [plan.to_dict() for plan in self._plans.values()],
            }
            self._state_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to persist generation plans for %s: %s", self.case_id, exc)

    def _plan_from_dict(self, data: Dict[str, Any]) -> GenerationPlan:
        """Hydrate a GenerationPlan from serialized data."""
        def _parse_dt(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None

        sections: List[SectionContent] = []
        for section_data in data.get("sections", []):
            if not isinstance(section_data, dict):
                continue

            hypotheses: List[Hypothesis] = []
            for hyp_data in section_data.get("hypotheses", []):
                if not isinstance(hyp_data, dict):
                    continue
                hypotheses.append(
                    Hypothesis(
                        hypothesis_id=str(hyp_data.get("hypothesis_id", "")),
                        section_id=str(hyp_data.get("section_id", "")),
                        statement=str(hyp_data.get("statement", "")),
                        evidence_keys=[str(item) for item in hyp_data.get("evidence_keys", [])],
                        confidence=float(hyp_data.get("confidence", 0.5)),
                        status=str(hyp_data.get("status", "proposed")),
                        reasoning=str(hyp_data.get("reasoning", "")),
                    )
                )

            charts: List[ChartDecision] = []
            for chart_data in section_data.get("charts", []):
                if not isinstance(chart_data, dict):
                    continue

                config_value = chart_data.get("config")
                config: Dict[str, Any] = cast(Dict[str, Any], config_value) if isinstance(config_value, dict) else {}

                raw_type = str(chart_data.get("chart_type", ChartType.BAR.value))
                try:
                    chart_type = ChartType(raw_type)
                except ValueError:
                    chart_type = ChartType.BAR

                charts.append(
                    ChartDecision(
                        decision_id=str(chart_data.get("decision_id", "")),
                        section_id=str(chart_data.get("section_id", "")),
                        chart_type=chart_type,
                        title=str(chart_data.get("title", "")),
                        data_source=str(chart_data.get("data_source", "")),
                        evidence_keys=[str(item) for item in chart_data.get("evidence_keys", [])],
                        config=config,
                        position_hint=int(chart_data.get("position_hint", 0)),
                        reasoning=str(chart_data.get("reasoning", "")),
                    )
                )

            raw_status = str(section_data.get("status", SectionStatus.PENDING.value))
            try:
                section_status = SectionStatus(raw_status)
            except ValueError:
                section_status = SectionStatus.PENDING

            sections.append(
                SectionContent(
                    section_id=str(section_data.get("section_id", "")),
                    title=str(section_data.get("title", "Untitled")),
                    level=int(section_data.get("level", 2)),
                    text_blocks=cast(List[Dict[str, Any]], section_data.get("text_blocks")) if isinstance(section_data.get("text_blocks"), list) else [],
                    charts=charts,
                    tables=cast(List[Dict[str, Any]], section_data.get("tables")) if isinstance(section_data.get("tables"), list) else [],
                    hypotheses=hypotheses,
                    evidence_keys=[str(item) for item in section_data.get("evidence_keys", [])],
                    start_position=int(section_data.get("start_position", 0)),
                    end_position=int(section_data.get("end_position", 0)),
                    estimated_height=int(section_data.get("estimated_height", 0)),
                    status=section_status,
                    generated_at=_parse_dt(section_data.get("generated_at")),
                    verified=bool(section_data.get("verified", False)),
                    verification_notes=str(section_data.get("verification_notes", "")),
                )
            )

        return GenerationPlan(
            plan_id=str(data.get("plan_id", "")),
            case_id=str(data.get("case_id", self.case_id)),
            scenario_session_id=str(data.get("scenario_session_id", "")),
            sections=sections,
            current_section_idx=int(data.get("current_section_idx", 0)),
            total_sections=int(data.get("total_sections", len(sections))),
            auto_pilot=bool(data.get("auto_pilot", False)),
            human_approval_required=bool(data.get("human_approval_required", True)),
            created_at=_parse_dt(data.get("created_at")) or datetime.now(timezone.utc),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
        )
    
    def create_plan(
        self,
        scenario_session_id: str,
        structure_sections: List[Dict[str, Any]],
        auto_pilot: bool = False
    ) -> GenerationPlan:
        """
        Create a generation plan from structure recommendation.
        
        Args:
            scenario_session_id: ID from scenario analysis
            structure_sections: Sections from structure recommendation
            auto_pilot: Whether to auto-approve sections
            
        Returns:
            Generation plan
        """
        plan_id = f"PLN-{uuid.uuid4().hex[:8].upper()}"
        
        sections = []
        for idx, sec in enumerate(structure_sections):
            section = SectionContent(
                section_id=f"SEC-{uuid.uuid4().hex[:6].upper()}",
                title=sec.get("title", f"Section {idx + 1}"),
                level=sec.get("level", 2),
                status=SectionStatus.PENDING
            )
            sections.append(section)
        
        plan = GenerationPlan(
            plan_id=plan_id,
            case_id=self.case_id,
            scenario_session_id=scenario_session_id,
            sections=sections,
            total_sections=len(sections),
            auto_pilot=auto_pilot,
            human_approval_required=not auto_pilot
        )
        
        self._plans[plan_id] = plan
        self._persist_plans()
        
        logger.info(f"Created generation plan {plan_id} with {len(sections)} sections")
        
        return plan
    
    def get_plan(self, plan_id: str) -> Optional[GenerationPlan]:
        """Get a generation plan by ID."""
        return self._plans.get(plan_id)
    
    def generate_section(
        self,
        plan_id: str,
        section_idx: int,
        scenario_context: Dict[str, Any]
    ) -> SectionContent:
        """
        Generate content for a single section.
        
        Args:
            plan_id: Generation plan ID
            section_idx: Index of section to generate
            scenario_context: Context from scenario analysis
            
        Returns:
            Generated section content
        """
        plan = self._plans.get(plan_id)
        if not plan or section_idx >= len(plan.sections):
            raise ValueError(f"Invalid plan or section index")
        
        section = plan.sections[section_idx]
        section.status = SectionStatus.ANALYZING
        
        # 1. Gather evidence keys for this section
        evidence_keys = self._evidence_service.get_keys_by_section(section.section_id)
        
        # If no section-specific evidence, get by category based on title
        if not evidence_keys:
            category = self._infer_category(section.title)
            if category:
                evidence_keys = self._evidence_service.get_keys_by_category(category)
        
        section.evidence_keys = [k.key_id for k in evidence_keys]
        
        # 2. Generate hypotheses
        section.status = SectionStatus.GENERATING
        hypotheses = self._hypothesis_gen.generate_hypotheses(
            section_title=section.title,
            section_topic=section.title,  # Could be expanded
            scenario_context=scenario_context,
            evidence_keys=evidence_keys
        )
        
        for h in hypotheses:
            h.section_id = section.section_id
        section.hypotheses = hypotheses
        
        # 3. Decide on charts
        learned_suggestions = []
        charts = self._chart_engine.decide_charts(
            section_title=section.title,
            section_content="",  # No content yet
            evidence_keys=evidence_keys,
            learned_suggestions=learned_suggestions
        )
        
        for c in charts:
            c.section_id = section.section_id
        section.charts = charts
        
        # 4. Generate text blocks
        section.text_blocks = self._generate_text_blocks(
            section=section,
            evidence_keys=evidence_keys,
            hypotheses=hypotheses,
            scenario_context=scenario_context
        )
        
        # 5. Calculate estimated height
        section.estimated_height = self._estimate_height(section)
        
        # 6. Update timestamps
        section.generated_at = datetime.now(timezone.utc)
        section.status = SectionStatus.REVIEW
        self._persist_plans()
        
        logger.info(f"Generated section {section.section_id}: {section.title}")
        
        return section
    
    def _infer_category(self, title: str) -> Optional[str]:
        """Infer evidence category from section title."""
        title_lower = title.lower()
        
        mappings = {
            "timeline": "timeline",
            "chronology": "timeline",
            "network": "network",
            "transfer": "transfer",
            "exfiltration": "transfer",
            "user": "user",
            "suspect": "suspect",
            "device": "device",
            "file": "file",
            "email": "email",
            "usb": "usb",
            "bluetooth": "bluetooth",
        }
        
        for keyword, category in mappings.items():
            if keyword in title_lower:
                return category
        
        return None
    
    def _generate_text_blocks(
        self,
        section: SectionContent,
        evidence_keys: List[EvidenceKey],
        hypotheses: List[Hypothesis],
        scenario_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate text blocks for the section."""
        blocks = []
        
        # Introduction block
        intro = {
            "type": "paragraph",
            "content": f"This section analyzes {section.title.lower()} based on the forensic evidence collected.",
            "position": 0
        }
        blocks.append(intro)
        
        # Hypothesis summary block
        if hypotheses:
            hyp_text = "Key findings and hypotheses:\n"
            for h in hypotheses:
                hyp_text += f"• {h.statement} (Confidence: {h.confidence:.0%})\n"
            
            blocks.append({
                "type": "paragraph",
                "content": hyp_text,
                "position": 1
            })
        
        # Evidence summary block
        if evidence_keys:
            ev_text = f"This analysis is supported by {len(evidence_keys)} pieces of evidence."
            blocks.append({
                "type": "paragraph",
                "content": ev_text,
                "position": 2
            })
        
        return blocks
    
    def _estimate_height(self, section: SectionContent) -> int:
        """Estimate section height in PDF units."""
        height = 50  # Title
        
        for block in section.text_blocks:
            content = block.get("content", "")
            lines = len(content) // 80 + content.count('\n') + 1
            height += lines * 20  # Line height
        
        for chart in section.charts:
            height += 300  # Chart height
        
        for table in section.tables:
            rows = len(table.get("rows", []))
            height += 30 + rows * 25  # Header + rows
        
        return height
    
    def approve_section(
        self,
        plan_id: str,
        section_idx: int,
        approved: bool,
        notes: str = ""
    ) -> SectionContent:
        """
        Approve or reject a generated section.
        
        Args:
            plan_id: Generation plan ID
            section_idx: Index of section
            approved: Whether to approve
            notes: Verification notes
            
        Returns:
            Updated section
        """
        plan = self._plans.get(plan_id)
        if not plan or section_idx >= len(plan.sections):
            raise ValueError(f"Invalid plan or section index")
        
        section = plan.sections[section_idx]
        
        if approved:
            section.status = SectionStatus.APPROVED
            section.verified = True
            section.verification_notes = notes or "Approved"
            
            # Update plan progress
            plan.current_section_idx = section_idx + 1
        else:
            section.status = SectionStatus.FAILED
            section.verification_notes = notes or "Rejected - needs revision"

        self._persist_plans()
        
        return section
    
    def get_progress(self, plan_id: str) -> Dict[str, Any]:
        """Get generation progress for a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {"error": "Plan not found"}
        
        approved = sum(1 for s in plan.sections if s.status == SectionStatus.APPROVED)
        pending = sum(1 for s in plan.sections if s.status == SectionStatus.PENDING)
        in_progress = sum(1 for s in plan.sections 
                         if s.status in [SectionStatus.ANALYZING, SectionStatus.GENERATING, SectionStatus.REVIEW])
        
        return {
            "plan_id": plan_id,
            "total_sections": plan.total_sections,
            "current_section_idx": plan.current_section_idx,
            "approved": approved,
            "pending": pending,
            "in_progress": in_progress,
            "progress_pct": approved / plan.total_sections * 100 if plan.total_sections > 0 else 0,
            "auto_pilot": plan.auto_pilot
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_generation_pipelines: Dict[str, SectionGenerationPipeline] = {}


def get_generation_pipeline(case_id: str) -> SectionGenerationPipeline:
    """Get or create SectionGenerationPipeline for a case."""
    global _generation_pipelines
    if case_id not in _generation_pipelines:
        _generation_pipelines[case_id] = SectionGenerationPipeline(case_id)
    return _generation_pipelines[case_id]
