"""
MCP Tool Schemas — Pydantic models for Model Context Protocol tools.

This module defines all data structures used by MCP tools:
- Investigation lifecycle schemas
- Evidence reference schemas  
- Analysis result schemas
- Hypothesis and confidence schemas
- Report generation schemas

Design Principles:
- All evidence values (IP, MAC, timestamps) are NEVER generated
- Every piece of data has a traceable source reference
- Hashes ensure integrity verification
- Schemas support both MCP serialization and internal use

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Literal, Optional, Set, Tuple, Union, TypeVar, Generic
)

from pydantic import (
    BaseModel, Field, field_validator, model_validator,
    ConfigDict, computed_field
)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class InvestigationStatus(str, Enum):
    """Status of an investigation."""
    INITIALIZING = "initializing"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, Enum):
    """Status of an investigation phase."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"


class HypothesisVerdict(str, Enum):
    """Verdict for a hypothesis."""
    UNTESTED = "untested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"
    PARTIALLY_CONFIRMED = "partially_confirmed"


class ConfidenceLevel(str, Enum):
    """ODNI ICD 203 confidence levels."""
    VERY_HIGH = "very_high"  # >90%
    HIGH = "high"            # 75-90%
    MODERATE = "moderate"    # 50-75%
    LOW = "low"              # 25-50%
    VERY_LOW = "very_low"    # <25%
    
    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Convert numeric score to confidence level."""
        if score >= 0.90:
            return cls.VERY_HIGH
        elif score >= 0.75:
            return cls.HIGH
        elif score >= 0.50:
            return cls.MODERATE
        elif score >= 0.25:
            return cls.LOW
        else:
            return cls.VERY_LOW


class EvidenceType(str, Enum):
    """Types of evidence."""
    LOG_EVENT = "log_event"
    FILE_ARTIFACT = "file_artifact"
    NETWORK_FLOW = "network_flow"
    MEMORY_ARTIFACT = "memory_artifact"
    REGISTRY_KEY = "registry_key"
    PROCESS_TRACE = "process_trace"
    USER_ACTIVITY = "user_activity"
    SYSTEM_EVENT = "system_event"
    EMAIL = "email"
    USB_DEVICE = "usb_device"
    BLUETOOTH = "bluetooth"
    COMPUTED_RESULT = "computed_result"


class ModuleName(str, Enum):
    """Available analysis modules."""
    TIMELINE = "timeline"
    ANOMALY = "anomaly"
    CORRELATION = "correlation"
    CRUD = "crud"
    NETWORK = "network"
    DEPTH = "depth"
    CASE = "case"


class TraversalStrategy(str, Enum):
    """Investigation traversal strategy."""
    BFS = "bfs"  # Breadth-first: comprehensive scan
    DFS = "dfs"  # Depth-first: focused dive
    HYBRID = "hybrid"  # BFS then DFS on high-confidence


class ClarificationPriority(str, Enum):
    """Priority of clarification questions."""
    BLOCKING = "blocking"  # Must answer before proceeding
    HIGH = "high"          # Important but can proceed with defaults
    MEDIUM = "medium"      # Nice to have
    LOW = "low"            # Optional context


# ═══════════════════════════════════════════════════════════════════════════════
# BASE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class MCPBaseModel(BaseModel):
    """Base model for all MCP schemas."""
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        json_schema_extra={
            "additionalProperties": False
        }
    )


class HashedModel(MCPBaseModel):
    """Model with automatic hash computation."""
    
    @computed_field
    @property
    def content_hash(self) -> str:
        """Compute SHA-256 hash of model content (excluding hash field)."""
        # Exclude content_hash from hashing to avoid recursion
        data = self.model_dump(exclude={'content_hash'}, mode='json')
        # Use canonical JSON (sorted keys) for deterministic hashing
        canonical = json.dumps(data, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


class TimestampedModel(MCPBaseModel):
    """Model with timestamp tracking."""
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE REFERENCE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class SourceReference(MCPBaseModel):
    """Reference to original data source."""
    source_type: str = Field(..., description="Type of source (e.g., 'windows_event', 'sysmon')")
    source_file: Optional[str] = Field(None, description="Original file path if applicable")
    source_table: str = Field(..., description="DuckDB table name")
    row_id: Optional[str] = Field(None, description="Specific row ID")
    row_ids: Optional[List[str]] = Field(None, description="Multiple row IDs")
    query_hash: Optional[str] = Field(None, description="Hash of query that produced this")
    
    @model_validator(mode='after')
    def validate_row_reference(self):
        """Ensure at least one row reference exists."""
        if self.row_id is None and self.row_ids is None:
            raise ValueError("Either row_id or row_ids must be provided")
        return self


class EvidenceValue(HashedModel):
    """
    A single piece of evidence extracted from logs.
    
    CRITICAL: This contains ACTUAL values from logs, NOT AI-generated.
    The value field contains the real data (IP, MAC, timestamp, etc.)
    """
    evidence_id: str = Field(
        default_factory=lambda: f"ev-{uuid.uuid4().hex[:12]}",
        description="Unique evidence identifier"
    )
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    field_name: str = Field(..., description="Name of the field (e.g., 'src_ip', 'user_id')")
    value: Any = Field(..., description="Actual value from logs - NEVER AI-generated")
    value_type: str = Field(..., description="Python type of value (str, int, datetime, etc.)")
    source: SourceReference = Field(..., description="Reference to source data")
    timestamp: Optional[datetime] = Field(None, description="When this evidence was recorded")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    
    @field_validator('value')
    @classmethod
    def validate_value_not_empty(cls, v):
        """Ensure value is not empty."""
        if v is None:
            raise ValueError("Evidence value cannot be None")
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("Evidence value cannot be empty string")
        return v


class EvidenceCard(HashedModel, TimestampedModel):
    """
    An evidence card containing multiple related evidence values.
    
    Evidence cards are IMMUTABLE snapshots - once created, the data
    is frozen even if more logs are added to the case.
    """
    card_id: str = Field(
        default_factory=lambda: f"card-{uuid.uuid4().hex[:12]}",
        description="Unique card identifier"
    )
    title: str = Field(..., description="Human-readable title")
    description: Optional[str] = Field(None, description="Description of evidence")
    case_id: str = Field(..., description="Parent case ID")
    evidence_values: List[EvidenceValue] = Field(
        default_factory=list,
        description="List of evidence values"
    )
    module_source: Optional[ModuleName] = Field(None, description="Module that produced this")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    artifact_path: Optional[str] = Field(None, description="Path to frozen artifact file")
    
    @computed_field
    @property
    def evidence_count(self) -> int:
        """Number of evidence values in this card."""
        return len(self.evidence_values)


class EvidenceInventory(MCPBaseModel):
    """Complete inventory of evidence for a case."""
    case_id: str
    cards: List[EvidenceCard] = Field(default_factory=list)
    total_evidence_count: int = 0
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_module: Dict[str, int] = Field(default_factory=dict)
    integrity_hash: Optional[str] = Field(None, description="Hash of entire inventory")


# ═══════════════════════════════════════════════════════════════════════════════
# INVESTIGATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class TimeRange(MCPBaseModel):
    """Time range for investigation scope."""
    start: datetime = Field(..., description="Start of time range")
    end: datetime = Field(..., description="End of time range")
    timezone: str = Field(default="UTC", description="Timezone")
    
    @model_validator(mode='after')
    def validate_range(self):
        """Ensure start is before end."""
        if self.start >= self.end:
            raise ValueError("Start time must be before end time")
        return self


class EntityReference(MCPBaseModel):
    """Reference to an entity (user, system, IP, etc.)."""
    entity_type: str = Field(..., description="Type: user, system, ip, file, etc.")
    entity_value: str = Field(..., description="The actual value")
    role: Literal["suspect", "victim", "witness", "unknown"] = Field(
        default="unknown",
        description="Role in investigation"
    )
    aliases: List[str] = Field(default_factory=list, description="Alternative names/values")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ClarificationQuestion(MCPBaseModel):
    """A clarification question for the investigator."""
    question_id: str = Field(
        default_factory=lambda: f"q-{uuid.uuid4().hex[:8]}",
        description="Unique question ID"
    )
    question: str = Field(..., description="The question text")
    context: Optional[str] = Field(None, description="Why this question is being asked")
    priority: ClarificationPriority = Field(
        default=ClarificationPriority.HIGH,
        description="Question priority"
    )
    options: Optional[List[str]] = Field(None, description="Multiple choice options")
    default_value: Optional[str] = Field(None, description="Default if not answered")
    validation_pattern: Optional[str] = Field(None, description="Regex for validation")
    answered: bool = Field(default=False, description="Whether answered")
    answer: Optional[str] = Field(None, description="The answer provided")


class InvestigationObjective(MCPBaseModel):
    """An objective for the investigation."""
    objective_id: str = Field(
        default_factory=lambda: f"obj-{uuid.uuid4().hex[:8]}"
    )
    description: str = Field(..., description="What we're trying to prove/disprove")
    priority: int = Field(default=1, ge=1, le=10, description="Priority 1-10")
    related_hypotheses: List[str] = Field(
        default_factory=list,
        description="Hypothesis IDs related to this objective"
    )
    completion_criteria: Optional[str] = Field(
        None,
        description="How to know when objective is met"
    )
    status: PhaseStatus = Field(default=PhaseStatus.PENDING)


class InvestigationContext(HashedModel, TimestampedModel):
    """
    Complete context for an investigation session.
    
    This is the master state object that tracks everything about
    an investigation from intake to completion.
    """
    investigation_id: str = Field(
        default_factory=lambda: f"inv-{uuid.uuid4().hex[:12]}",
        description="Unique investigation identifier"
    )
    case_id: str = Field(..., description="Target case ID")
    status: InvestigationStatus = Field(
        default=InvestigationStatus.INITIALIZING,
        description="Current status"
    )
    
    # Scenario & Objectives
    scenario: str = Field(..., description="Original scenario description")
    objectives: List[InvestigationObjective] = Field(
        default_factory=list,
        description="Investigation objectives"
    )
    
    # Scope
    time_range: Optional[TimeRange] = Field(None, description="Time scope")
    entities: List[EntityReference] = Field(
        default_factory=list,
        description="Entities involved"
    )
    
    # Data Sources
    available_sources: List[str] = Field(
        default_factory=list,
        description="Log sources available in the case"
    )
    selected_sources: List[str] = Field(
        default_factory=list,
        description="Sources selected for analysis"
    )
    
    # Investigation Mode
    mode: Literal["brute_force", "focused", "hybrid"] = Field(
        default="hybrid",
        description="Investigation approach"
    )
    traversal_strategy: TraversalStrategy = Field(
        default=TraversalStrategy.HYBRID,
        description="How to traverse hypothesis tree"
    )
    
    # Clarifications
    clarification_questions: List[ClarificationQuestion] = Field(
        default_factory=list,
        description="Questions asked/to ask"
    )
    
    # Metadata
    investigator_id: Optional[str] = Field(None, description="Who started this")
    llm_provider: str = Field(default="gemini", description="LLM to use")


# ═══════════════════════════════════════════════════════════════════════════════
# PLANNING SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class PlanStep(MCPBaseModel):
    """A single step in an investigation plan."""
    step_id: str = Field(
        default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}"
    )
    phase: str = Field(..., description="Phase name (e.g., 'Phase 1: Timeline')")
    step_number: str = Field(..., description="Step number (e.g., '1.1', '2.3')")
    title: str = Field(..., description="Step title")
    description: str = Field(..., description="What this step does")
    
    # Execution details
    tool_name: Optional[str] = Field(None, description="MCP tool to invoke")
    tool_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the tool"
    )
    
    # Dependencies
    depends_on: List[str] = Field(
        default_factory=list,
        description="Step IDs this depends on"
    )
    
    # Success criteria
    success_criteria: Optional[str] = Field(
        None,
        description="How to know step succeeded"
    )
    expected_output: Optional[str] = Field(
        None,
        description="What output to expect"
    )
    
    # Status tracking
    status: PhaseStatus = Field(default=PhaseStatus.PENDING)
    output: Optional[Dict[str, Any]] = Field(None, description="Actual output")
    error: Optional[str] = Field(None, description="Error if failed")
    started_at: Optional[datetime] = Field(None)
    completed_at: Optional[datetime] = Field(None)
    
    # User interaction
    requires_approval: bool = Field(
        default=False,
        description="Does user need to approve before execution?"
    )
    approved: bool = Field(default=False)
    user_notes: Optional[str] = Field(None, description="User's notes/edits")


class InvestigationPlan(HashedModel, TimestampedModel):
    """
    Complete investigation plan with all phases and steps.
    
    This is interactive - user can view, edit, approve, and
    modify the plan before and during execution.
    """
    plan_id: str = Field(
        default_factory=lambda: f"plan-{uuid.uuid4().hex[:12]}"
    )
    investigation_id: str = Field(..., description="Parent investigation")
    title: str = Field(default="Investigation Plan")
    
    # Structure
    phases: List[str] = Field(
        default_factory=list,
        description="Ordered list of phase names"
    )
    steps: List[PlanStep] = Field(
        default_factory=list,
        description="All steps in order"
    )
    
    # Progress
    current_phase: Optional[str] = Field(None, description="Currently executing phase")
    current_step: Optional[str] = Field(None, description="Currently executing step")
    progress_percent: float = Field(default=0.0, ge=0, le=100)
    
    # Status
    status: PhaseStatus = Field(default=PhaseStatus.PENDING)
    approved_by_user: bool = Field(default=False)
    
    @computed_field
    @property
    def total_steps(self) -> int:
        return len(self.steps)
    
    @computed_field
    @property
    def completed_steps(self) -> int:
        return len([s for s in self.steps if s.status == PhaseStatus.COMPLETED])


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceRequirement(MCPBaseModel):
    """An evidence requirement for a hypothesis."""
    requirement_id: str = Field(
        default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}"
    )
    description: str = Field(..., description="What evidence is needed")
    evidence_type: EvidenceType = Field(..., description="Type of evidence")
    required_fields: List[str] = Field(
        default_factory=list,
        description="Fields that must be present"
    )
    modules: List[ModuleName] = Field(
        default_factory=list,
        description="Modules that can provide this"
    )
    is_critical: bool = Field(
        default=False,
        description="Is this required for confirmation?"
    )
    satisfied: bool = Field(default=False)
    satisfying_evidence: Optional[str] = Field(
        None,
        description="Evidence card ID that satisfies this"
    )


class Hypothesis(HashedModel, TimestampedModel):
    """
    A hypothesis to test against evidence.
    
    Key principle: Start with NULL hypothesis (baseline: FALSE).
    Only confirm when sufficient evidence with high confidence.
    """
    hypothesis_id: str = Field(
        default_factory=lambda: f"hyp-{uuid.uuid4().hex[:12]}"
    )
    investigation_id: str = Field(..., description="Parent investigation")
    
    # Definition
    code: str = Field(..., description="Short code like H1, H2, H0")
    statement: str = Field(..., description="The hypothesis statement")
    is_null_hypothesis: bool = Field(
        default=False,
        description="Is this the null/baseline hypothesis?"
    )
    baseline_assumption: Literal["true", "false"] = Field(
        default="false",
        description="Start by assuming true or false? (Usually false)"
    )
    
    # Requirements
    evidence_requirements: List[EvidenceRequirement] = Field(
        default_factory=list,
        description="What evidence is needed"
    )
    
    # Related
    parent_hypothesis: Optional[str] = Field(
        None,
        description="Parent hypothesis if this is a sub-hypothesis"
    )
    alternative_to: List[str] = Field(
        default_factory=list,
        description="Hypothesis IDs this is alternative to"
    )
    mitre_techniques: List[str] = Field(
        default_factory=list,
        description="Related MITRE ATT&CK techniques"
    )
    
    # Testing results
    verdict: HypothesisVerdict = Field(default=HypothesisVerdict.UNTESTED)
    confidence_score: Optional[float] = Field(
        None, ge=0, le=1,
        description="Confidence in verdict (0-1)"
    )
    confidence_level: Optional[ConfidenceLevel] = Field(None)
    
    # Evidence
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence card IDs that support"
    )
    contradicting_evidence: List[str] = Field(
        default_factory=list,
        description="Evidence card IDs that contradict"
    )
    
    # Reasoning
    reasoning: Optional[str] = Field(
        None,
        description="AI-generated reasoning (based on evidence, not facts)"
    )


class HypothesisTree(MCPBaseModel):
    """
    Tree structure of all hypotheses for an investigation.
    """
    investigation_id: str
    null_hypothesis: Optional[str] = Field(
        None,
        description="ID of the null hypothesis (H0)"
    )
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    
    # Testing progress
    tested_count: int = 0
    confirmed_count: int = 0
    rejected_count: int = 0
    inconclusive_count: int = 0
    
    @computed_field
    @property
    def total_count(self) -> int:
        return len(self.hypotheses)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceFactor(MCPBaseModel):
    """A single factor in confidence calculation."""
    factor_name: str = Field(..., description="Name of the factor")
    weight: float = Field(..., ge=0, le=1, description="Weight in calculation")
    score: float = Field(..., ge=0, le=1, description="Score for this factor")
    reasoning: str = Field(..., description="Why this score")
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="Evidence supporting this assessment"
    )
    
    @computed_field
    @property
    def weighted_score(self) -> float:
        return self.weight * self.score


class ConfidenceAssessment(HashedModel, TimestampedModel):
    """
    Multi-factor confidence assessment.
    
    Based on ODNI ICD 203 standards and Bayesian reasoning.
    """
    assessment_id: str = Field(
        default_factory=lambda: f"conf-{uuid.uuid4().hex[:12]}"
    )
    target_type: Literal["hypothesis", "finding", "report"] = Field(
        ..., description="What is being assessed"
    )
    target_id: str = Field(..., description="ID of the target")
    
    # Factors
    factors: List[ConfidenceFactor] = Field(
        default_factory=list,
        description="Individual factors"
    )
    
    # Standard factors (if applicable)
    evidence_coverage: Optional[float] = Field(
        None, ge=0, le=1,
        description="How complete is the evidence?"
    )
    module_agreement: Optional[float] = Field(
        None, ge=0, le=1,
        description="Do modules agree?"
    )
    temporal_consistency: Optional[float] = Field(
        None, ge=0, le=1,
        description="Is timeline coherent?"
    )
    cross_validation: Optional[float] = Field(
        None, ge=0, le=1,
        description="External corroboration?"
    )
    pattern_match: Optional[float] = Field(
        None, ge=0, le=1,
        description="Matches known patterns?"
    )
    research_alignment: Optional[float] = Field(
        None, ge=0, le=1,
        description="Aligns with methodologies?"
    )
    
    # Results
    overall_score: float = Field(..., ge=0, le=1)
    confidence_level: ConfidenceLevel
    
    # Caveats
    caveats: List[str] = Field(
        default_factory=list,
        description="Important caveats/limitations"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Key assumptions made"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE RESULT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class ModuleExecutionResult(HashedModel, TimestampedModel):
    """Result from executing an analysis module."""
    execution_id: str = Field(
        default_factory=lambda: f"exec-{uuid.uuid4().hex[:12]}"
    )
    module: ModuleName
    case_id: str
    investigation_id: Optional[str] = None
    
    # Status
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0
    
    # Results
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics"
    )
    key_findings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Key findings (actual data, not AI-generated)"
    )
    evidence_cards: List[str] = Field(
        default_factory=list,
        description="Evidence card IDs created"
    )
    
    # Data references
    output_tables: List[str] = Field(
        default_factory=list,
        description="DuckDB tables with results"
    )
    row_count: int = 0
    
    # Chain of custody
    coc_event_id: Optional[str] = Field(
        None,
        description="CoC event recording this execution"
    )


class TimelineResult(ModuleExecutionResult):
    """Specific result from timeline module."""
    total_events: int = 0
    unique_sources: int = 0
    unique_actors: int = 0
    time_span_hours: float = 0
    severity_breakdown: Dict[str, int] = Field(default_factory=dict)
    peak_activity: Optional[Dict[str, Any]] = None
    anchor_events: List[Dict[str, Any]] = Field(default_factory=list)


class AnomalyResult(ModuleExecutionResult):
    """Specific result from anomaly module."""
    algorithm: str = "IsolationForest"
    total_scored: int = 0
    anomaly_count: int = 0
    threshold: float = 0.65
    avg_score: float = 0
    top_anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    actor_distribution: List[Dict[str, Any]] = Field(default_factory=list)


class CorrelationResult(ModuleExecutionResult):
    """Specific result from correlation module."""
    node_count: int = 0
    edge_count: int = 0
    mitre_tactics: List[str] = Field(default_factory=list)
    high_severity_entities: List[Dict[str, Any]] = Field(default_factory=list)
    attack_chain: Optional[Dict[str, Any]] = None


class CRUDResult(ModuleExecutionResult):
    """Specific result from CRUD module."""
    total_events: int = 0
    high_risk_count: int = 0
    crud_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    sensitivity_breakdown: Dict[str, int] = Field(default_factory=dict)
    high_risk_events: List[Dict[str, Any]] = Field(default_factory=list)


class NetworkResult(ModuleExecutionResult):
    """Specific result from network module."""
    flow_count: int = 0
    suspicious_count: int = 0
    exfil_candidate_count: int = 0
    bytes_outbound: int = 0
    protocol_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    exfil_candidates: List[Dict[str, Any]] = Field(default_factory=list)


class DepthResult(ModuleExecutionResult):
    """Specific result from depth module."""
    account_score: float = 0
    system_score: float = 0
    data_score: float = 0
    control_score: float = 0
    overall_severity: float = 0
    severity_label: str = "UNKNOWN"
    business_impact: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class Citation(MCPBaseModel):
    """A citation to evidence in a report."""
    citation_id: str = Field(
        default_factory=lambda: f"cite-{uuid.uuid4().hex[:8]}"
    )
    evidence_card_id: str = Field(..., description="Evidence card being cited")
    evidence_hash: str = Field(..., description="Hash of evidence at citation time")
    context: str = Field(..., description="Text context around citation")
    page_number: Optional[int] = Field(None)
    element_id: Optional[str] = Field(None)


class ReportSection(MCPBaseModel):
    """A section of a report."""
    section_id: str = Field(
        default_factory=lambda: f"sec-{uuid.uuid4().hex[:8]}"
    )
    title: str
    section_type: str = Field(..., description="executive_summary, methodology, findings, etc.")
    content: str = Field(default="", description="Section content (may include AI narrative)")
    order: int = Field(default=0, description="Order in report")
    
    # Evidence
    evidence_cards: List[str] = Field(
        default_factory=list,
        description="Evidence cards referenced"
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Citations in this section"
    )
    
    # Widgets
    widgets: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chart/table widget definitions"
    )
    
    # Status
    is_generated: bool = Field(default=False, description="Was content AI-generated?")
    is_reviewed: bool = Field(default=False, description="Has investigator reviewed?")


class ReportMetadata(MCPBaseModel):
    """Metadata for a report."""
    report_id: str = Field(
        default_factory=lambda: f"rpt-{uuid.uuid4().hex[:12]}"
    )
    investigation_id: str
    case_id: str
    title: str
    report_type: Literal["technical", "executive", "regulatory"] = "technical"
    
    # Dates
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # Authors
    investigator_id: Optional[str] = None
    reviewed_by: Optional[str] = None
    
    # Status
    status: Literal["draft", "review", "final"] = "draft"
    page_count: int = 0
    word_count: int = 0


class ReportStructure(HashedModel):
    """Complete structure of a report."""
    metadata: ReportMetadata
    sections: List[ReportSection] = Field(default_factory=list)
    
    # Evidence summary
    total_citations: int = 0
    evidence_cards_used: List[str] = Field(default_factory=list)
    
    # Integrity
    all_citations_valid: bool = True
    integrity_verified: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL INPUT/OUTPUT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class MCPToolResult(MCPBaseModel):
    """Standard result from any MCP tool."""
    success: bool = Field(..., description="Did the tool succeed?")
    tool_name: str = Field(..., description="Name of the tool that ran")
    execution_id: str = Field(
        default_factory=lambda: f"texec-{uuid.uuid4().hex[:12]}"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Results
    data: Optional[Dict[str, Any]] = Field(None, description="Tool output data")
    evidence_hash: Optional[str] = Field(
        None,
        description="Hash of evidence produced (if any)"
    )
    evidence_cards_created: List[str] = Field(
        default_factory=list,
        description="Evidence cards created by this tool"
    )
    
    # Chain of custody
    coc_event_id: Optional[str] = Field(
        None,
        description="CoC event ID for this execution"
    )
    
    # Error handling
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code")
    
    # Next actions
    suggested_next_tools: List[str] = Field(
        default_factory=list,
        description="Recommended next tools to run"
    )
    requires_clarification: bool = Field(
        default=False,
        description="Does this need user input?"
    )
    clarification_questions: List[ClarificationQuestion] = Field(
        default_factory=list
    )


class InvestigationStartInput(MCPBaseModel):
    """Input for starting an investigation."""
    case_id: str = Field(..., description="Target case ID")
    scenario: str = Field(..., description="Investigation scenario description")
    objectives: Optional[List[str]] = Field(None, description="Specific objectives")
    time_range: Optional[TimeRange] = Field(None, description="Time scope")
    suspected_entities: Optional[List[EntityReference]] = Field(
        None, description="Known suspects"
    )
    victim_entities: Optional[List[EntityReference]] = Field(
        None, description="Known victims"
    )
    mode: Literal["brute_force", "focused", "hybrid"] = Field(
        default="hybrid", description="Investigation approach"
    )
    llm_provider: str = Field(default="gemini")


class InvestigationStartOutput(MCPToolResult):
    """Output from starting an investigation."""
    investigation_id: str
    status: InvestigationStatus
    extracted_entities: List[EntityReference] = Field(default_factory=list)
    available_sources: List[str] = Field(default_factory=list)
    preliminary_plan: Optional[InvestigationPlan] = None


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY CARD SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class SummaryCard(HashedModel, TimestampedModel):
    """
    A summary card showing key findings for a branch of investigation.
    
    Summary cards aggregate findings and provide quick overview
    without having to read full details.
    """
    card_id: str = Field(
        default_factory=lambda: f"sum-{uuid.uuid4().hex[:12]}"
    )
    investigation_id: str
    title: str
    card_type: Literal["phase", "hypothesis", "module", "finding", "final"] = "finding"
    
    # Content
    summary_text: str = Field(..., description="Brief summary (AI-generated from evidence)")
    key_facts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Key facts (from evidence, not AI-generated)"
    )
    
    # Evidence
    evidence_cards: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = Field(None, ge=0, le=1)
    confidence_level: Optional[ConfidenceLevel] = None
    
    # Status
    status: Literal["in_progress", "complete", "needs_review"] = "in_progress"
    
    # Visual
    icon: Optional[str] = Field(None, description="Icon for display")
    color: Optional[str] = Field(None, description="Color coding")


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Enums
    "InvestigationStatus",
    "PhaseStatus",
    "HypothesisVerdict",
    "ConfidenceLevel",
    "EvidenceType",
    "ModuleName",
    "TraversalStrategy",
    "ClarificationPriority",
    
    # Base
    "MCPBaseModel",
    "HashedModel",
    "TimestampedModel",
    
    # Evidence
    "SourceReference",
    "EvidenceValue",
    "EvidenceCard",
    "EvidenceInventory",
    
    # Investigation
    "TimeRange",
    "EntityReference",
    "ClarificationQuestion",
    "InvestigationObjective",
    "InvestigationContext",
    
    # Planning
    "PlanStep",
    "InvestigationPlan",
    
    # Hypothesis
    "EvidenceRequirement",
    "Hypothesis",
    "HypothesisTree",
    
    # Confidence
    "ConfidenceFactor",
    "ConfidenceAssessment",
    
    # Module Results
    "ModuleExecutionResult",
    "TimelineResult",
    "AnomalyResult",
    "CorrelationResult",
    "CRUDResult",
    "NetworkResult",
    "DepthResult",
    
    # Report
    "Citation",
    "ReportSection",
    "ReportMetadata",
    "ReportStructure",
    
    # Tool I/O
    "MCPToolResult",
    "InvestigationStartInput",
    "InvestigationStartOutput",
    
    # Summary
    "SummaryCard",
]
