"""
Investigation Plan Data Models.

Defines data structures for:
- Investigation plans with phases
- Plan steps and sub-steps
- Hypothesis tracking
- Plan approval workflow
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class PlanStatus(str, Enum):
    """Status of a plan or phase."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of plan steps."""
    ANALYSIS = "analysis"           # Run analysis module
    QUERY = "query"                 # Query evidence
    HYPOTHESIS_TEST = "hypothesis"  # Test hypothesis
    SYNTHESIS = "synthesis"         # Combine findings
    REPORT = "report"               # Write to report
    CLARIFICATION = "clarification" # Ask user
    MANUAL = "manual"               # Manual action needed
    VERIFICATION = "verification"   # Verify previous step


@dataclass
class PlanStep:
    """A single step in a plan phase."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Content
    title: str = ""
    description: str = ""
    step_type: StepType = StepType.ANALYSIS
    
    # Configuration
    module: Optional[str] = None  # Which module to use
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Step IDs
    
    # Status
    status: PlanStatus = PlanStatus.DRAFT
    progress: float = 0.0
    
    # Results
    output: Optional[Dict[str, Any]] = None
    evidence_refs: List[str] = field(default_factory=list)
    error: Optional[str] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Ordering
    order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "step_type": self.step_type.value,
            "module": self.module,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "progress": self.progress,
            "output": self.output,
            "evidence_refs": self.evidence_refs,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order": self.order,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        """Create from dictionary."""
        step = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            step_type=StepType(data.get("step_type", "analysis")),
            module=data.get("module"),
            parameters=data.get("parameters", {}),
            depends_on=data.get("depends_on", []),
            status=PlanStatus(data.get("status", "draft")),
            progress=data.get("progress", 0.0),
            output=data.get("output"),
            evidence_refs=data.get("evidence_refs", []),
            error=data.get("error"),
            order=data.get("order", 0),
        )
        if data.get("created_at"):
            step.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            step.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            step.completed_at = datetime.fromisoformat(data["completed_at"])
        return step


@dataclass
class PlanPhase:
    """A phase in the investigation plan."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Content
    title: str = ""
    description: str = ""
    objective: str = ""
    
    # Steps
    steps: List[PlanStep] = field(default_factory=list)
    
    # Hypotheses to test in this phase
    hypothesis_ids: List[str] = field(default_factory=list)
    
    # Status
    status: PlanStatus = PlanStatus.DRAFT
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Phase IDs
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Ordering
    order: int = 0
    
    @property
    def progress(self) -> float:
        """Calculate phase progress from steps."""
        if not self.steps:
            return 0.0
        return sum(s.progress for s in self.steps) / len(self.steps)
    
    @property
    def is_ready(self) -> bool:
        """Check if phase is ready to execute."""
        return self.status == PlanStatus.APPROVED
    
    def get_next_step(self) -> Optional[PlanStep]:
        """Get next executable step."""
        for step in sorted(self.steps, key=lambda s: s.order):
            if step.status in [PlanStatus.DRAFT, PlanStatus.APPROVED]:
                # Check dependencies
                deps_complete = all(
                    any(s.id == dep and s.status == PlanStatus.COMPLETED for s in self.steps)
                    for dep in step.depends_on
                )
                if deps_complete:
                    return step
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "objective": self.objective,
            "steps": [s.to_dict() for s in self.steps],
            "hypothesis_ids": self.hypothesis_ids,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "order": self.order,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanPhase":
        """Create from dictionary."""
        phase = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            objective=data.get("objective", ""),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            hypothesis_ids=data.get("hypothesis_ids", []),
            status=PlanStatus(data.get("status", "draft")),
            depends_on=data.get("depends_on", []),
            order=data.get("order", 0),
        )
        if data.get("created_at"):
            phase.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            phase.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            phase.completed_at = datetime.fromisoformat(data["completed_at"])
        return phase


@dataclass
class InvestigationPlan:
    """Complete investigation plan."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    
    # Content
    title: str = ""
    description: str = ""
    scenario_summary: str = ""
    objectives: List[str] = field(default_factory=list)
    
    # Phases
    phases: List[PlanPhase] = field(default_factory=list)
    
    # Global hypotheses
    null_hypothesis: str = ""  # Default: "The suspected activity did NOT occur"
    alternative_hypotheses: List[str] = field(default_factory=list)
    
    # Status
    status: PlanStatus = PlanStatus.DRAFT
    
    # User edits
    user_modifications: List[Dict[str, Any]] = field(default_factory=list)
    
    # Approval
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Version for optimistic locking
    version: int = 1
    
    @property
    def progress(self) -> float:
        """Calculate overall plan progress."""
        if not self.phases:
            return 0.0
        return sum(p.progress for p in self.phases) / len(self.phases)
    
    @property
    def current_phase(self) -> Optional[PlanPhase]:
        """Get current executing phase."""
        for phase in sorted(self.phases, key=lambda p: p.order):
            if phase.status == PlanStatus.IN_PROGRESS:
                return phase
        return None
    
    @property
    def next_phase(self) -> Optional[PlanPhase]:
        """Get next phase to execute."""
        for phase in sorted(self.phases, key=lambda p: p.order):
            if phase.status in [PlanStatus.DRAFT, PlanStatus.APPROVED]:
                # Check dependencies
                deps_complete = all(
                    any(p.id == dep and p.status == PlanStatus.COMPLETED for p in self.phases)
                    for dep in phase.depends_on
                )
                if deps_complete:
                    return phase
        return None
    
    def get_phase(self, phase_id: str) -> Optional[PlanPhase]:
        """Get phase by ID."""
        for phase in self.phases:
            if phase.id == phase_id:
                return phase
        return None
    
    def add_phase(self, phase: PlanPhase) -> None:
        """Add a phase to the plan."""
        phase.order = len(self.phases)
        self.phases.append(phase)
        self.updated_at = datetime.now()
        self.version += 1
    
    def remove_phase(self, phase_id: str) -> bool:
        """Remove a phase."""
        for i, phase in enumerate(self.phases):
            if phase.id == phase_id:
                self.phases.pop(i)
                self._reorder_phases()
                self.updated_at = datetime.now()
                self.version += 1
                return True
        return False
    
    def reorder_phase(self, phase_id: str, new_order: int) -> bool:
        """Reorder a phase."""
        phase = self.get_phase(phase_id)
        if not phase:
            return False
        
        old_order = phase.order
        if old_order == new_order:
            return True
        
        # Shift other phases
        for p in self.phases:
            if old_order < new_order:
                if old_order < p.order <= new_order:
                    p.order -= 1
            else:
                if new_order <= p.order < old_order:
                    p.order += 1
        
        phase.order = new_order
        self.updated_at = datetime.now()
        self.version += 1
        return True
    
    def _reorder_phases(self) -> None:
        """Reorder phases after removal."""
        for i, phase in enumerate(sorted(self.phases, key=lambda p: p.order)):
            phase.order = i
    
    def approve(self, approver: str) -> None:
        """Approve the plan for execution."""
        self.status = PlanStatus.APPROVED
        self.approved_by = approver
        self.approved_at = datetime.now()
        
        # Approve all phases
        for phase in self.phases:
            if phase.status == PlanStatus.DRAFT:
                phase.status = PlanStatus.APPROVED
            for step in phase.steps:
                if step.status == PlanStatus.DRAFT:
                    step.status = PlanStatus.APPROVED
        
        self.updated_at = datetime.now()
        self.version += 1
    
    def record_modification(
        self,
        modification_type: str,
        details: Dict[str, Any],
        user: Optional[str] = None,
    ) -> None:
        """Record a user modification."""
        self.user_modifications.append({
            "type": modification_type,
            "details": details,
            "user": user,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
        self.version += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "title": self.title,
            "description": self.description,
            "scenario_summary": self.scenario_summary,
            "objectives": self.objectives,
            "phases": [p.to_dict() for p in self.phases],
            "null_hypothesis": self.null_hypothesis,
            "alternative_hypotheses": self.alternative_hypotheses,
            "status": self.status.value,
            "user_modifications": self.user_modifications,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "version": self.version,
            "progress": self.progress,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InvestigationPlan":
        """Create from dictionary."""
        plan = cls(
            id=data.get("id", str(uuid.uuid4())),
            investigation_id=data.get("investigation_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            scenario_summary=data.get("scenario_summary", ""),
            objectives=data.get("objectives", []),
            phases=[PlanPhase.from_dict(p) for p in data.get("phases", [])],
            null_hypothesis=data.get("null_hypothesis", ""),
            alternative_hypotheses=data.get("alternative_hypotheses", []),
            status=PlanStatus(data.get("status", "draft")),
            user_modifications=data.get("user_modifications", []),
            approved_by=data.get("approved_by"),
            version=data.get("version", 1),
        )
        if data.get("approved_at"):
            plan.approved_at = datetime.fromisoformat(data["approved_at"])
        if data.get("created_at"):
            plan.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            plan.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("started_at"):
            plan.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            plan.completed_at = datetime.fromisoformat(data["completed_at"])
        return plan
    
    def get_summary(self) -> Dict[str, Any]:
        """Get plan summary statistics."""
        total_steps = sum(len(p.steps) for p in self.phases)
        completed_steps = sum(
            1 for p in self.phases for s in p.steps
            if s.status == PlanStatus.COMPLETED
        )
        
        return {
            "total_phases": len(self.phases),
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "progress": self.progress,
            "status": self.status.value,
            "hypotheses": len(self.alternative_hypotheses) + 1,  # +1 for null
        }
