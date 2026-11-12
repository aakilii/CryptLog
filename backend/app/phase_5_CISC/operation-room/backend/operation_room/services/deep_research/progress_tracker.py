"""
Progress Tracker for Deep Research Investigations.

Provides:
- Real-time progress estimation
- Phase timing
- Step-level tracking
- WebSocket-compatible events
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import logging


logger = logging.getLogger(__name__)


class ProgressStatus(str, Enum):
    """Status of a progress item."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProgressStep:
    """A step in the progress tracker."""
    id: str
    name: str
    phase: str
    order: int
    status: ProgressStatus = ProgressStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    
    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return int((end - self.started_at).total_seconds() * 1000)
    
    @property
    def is_complete(self) -> bool:
        return self.status in [ProgressStatus.COMPLETED, ProgressStatus.FAILED, ProgressStatus.SKIPPED]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase,
            "order": self.order,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


@dataclass
class PhaseProgress:
    """Progress for a phase."""
    id: str
    name: str
    order: int
    steps: List[ProgressStep] = field(default_factory=list)
    status: ProgressStatus = ProgressStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def progress(self) -> float:
        """Get completion percentage (0-1)."""
        if not self.steps:
            return 1.0 if self.status == ProgressStatus.COMPLETED else 0.0
        completed = sum(1 for s in self.steps if s.is_complete)
        return completed / len(self.steps)
    
    @property
    def duration_ms(self) -> int:
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return int((end - self.started_at).total_seconds() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "order": self.order,
            "status": self.status.value,
            "progress": self.progress,
            "steps": [s.to_dict() for s in self.steps],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


class ProgressTracker:
    """
    Tracks investigation progress with real-time updates.
    
    Features:
    - Phase and step tracking
    - Time estimation
    - Event emission for WebSocket
    """
    
    # Default phase configuration
    DEFAULT_PHASES = [
        ("intake", "Scenario Intake", [
            ("parse_scenario", "Parse scenario"),
            ("extract_entities", "Extract entities"),
            ("identify_objectives", "Identify objectives"),
        ]),
        ("clarification", "Clarification", [
            ("generate_questions", "Generate questions"),
            ("wait_answers", "Wait for answers"),
            ("validate_context", "Validate context"),
        ]),
        ("planning", "Planning", [
            ("analyze_scope", "Analyze scope"),
            ("generate_hypotheses", "Generate hypotheses"),
            ("create_phases", "Create phases"),
            ("assign_modules", "Assign modules"),
        ]),
        ("approval", "Approval", [
            ("present_plan", "Present plan"),
            ("wait_approval", "Wait for approval"),
        ]),
        ("execution", "Execution", [
            ("run_timeline", "Timeline analysis"),
            ("run_anomaly", "Anomaly detection"),
            ("run_correlation", "Correlation analysis"),
            ("run_crud", "CRUD analysis"),
            ("run_network", "Network analysis"),
            ("evaluate_hypotheses", "Evaluate hypotheses"),
        ]),
        ("synthesis", "Synthesis", [
            ("collect_evidence", "Collect evidence"),
            ("compute_confidence", "Compute confidence"),
            ("generate_findings", "Generate findings"),
        ]),
        ("reporting", "Report Generation", [
            ("create_structure", "Create structure"),
            ("fill_sections", "Fill sections"),
            ("generate_toc", "Generate TOC"),
            ("finalize_report", "Finalize report"),
        ]),
    ]
    
    def __init__(self, investigation_id: str):
        """Initialize tracker."""
        self.investigation_id = investigation_id
        self.phases: Dict[str, PhaseProgress] = {}
        self.phase_order: List[str] = []
        self.current_phase: Optional[str] = None
        self.current_step: Optional[str] = None
        
        # Event callbacks
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Timing
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Initialize phases
        self._init_phases()
    
    def _init_phases(self) -> None:
        """Initialize default phases."""
        for i, (phase_id, phase_name, steps) in enumerate(self.DEFAULT_PHASES):
            phase = PhaseProgress(
                id=phase_id,
                name=phase_name,
                order=i,
            )
            
            for j, (step_id, step_name) in enumerate(steps):
                phase.steps.append(ProgressStep(
                    id=f"{phase_id}_{step_id}",
                    name=step_name,
                    phase=phase_id,
                    order=j,
                ))
            
            self.phases[phase_id] = phase
            self.phase_order.append(phase_id)
    
    def on_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register progress callback."""
        self._callbacks.append(callback)
    
    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit progress event."""
        event = {
            "type": event_type,
            "investigation_id": self.investigation_id,
            "timestamp": datetime.now().isoformat(),
            **data,
        }
        
        for callback in self._callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    def start(self) -> None:
        """Start tracking."""
        self.started_at = datetime.now()
        self._emit("investigation_started", {
            "phases": [p.to_dict() for p in self.phases.values()],
        })
    
    def start_phase(self, phase_id: str) -> None:
        """Start a phase."""
        if phase_id not in self.phases:
            return
        
        phase = self.phases[phase_id]
        phase.status = ProgressStatus.RUNNING
        phase.started_at = datetime.now()
        self.current_phase = phase_id
        
        self._emit("phase_started", {
            "phase_id": phase_id,
            "phase_name": phase.name,
        })
    
    def complete_phase(self, phase_id: str, error: Optional[str] = None) -> None:
        """Complete a phase."""
        if phase_id not in self.phases:
            return
        
        phase = self.phases[phase_id]
        phase.completed_at = datetime.now()
        phase.status = ProgressStatus.FAILED if error else ProgressStatus.COMPLETED
        
        self._emit("phase_completed", {
            "phase_id": phase_id,
            "phase_name": phase.name,
            "duration_ms": phase.duration_ms,
            "error": error,
        })
    
    def start_step(self, step_id: str) -> None:
        """Start a step."""
        for phase in self.phases.values():
            for step in phase.steps:
                if step.id == step_id:
                    step.status = ProgressStatus.RUNNING
                    step.started_at = datetime.now()
                    self.current_step = step_id
                    
                    self._emit("step_started", {
                        "step_id": step_id,
                        "step_name": step.name,
                        "phase_id": phase.id,
                    })
                    return
    
    def complete_step(
        self,
        step_id: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Complete a step."""
        for phase in self.phases.values():
            for step in phase.steps:
                if step.id == step_id:
                    step.completed_at = datetime.now()
                    step.status = ProgressStatus.FAILED if error else ProgressStatus.COMPLETED
                    step.output = output
                    step.error = error
                    
                    self._emit("step_completed", {
                        "step_id": step_id,
                        "step_name": step.name,
                        "phase_id": phase.id,
                        "duration_ms": step.duration_ms,
                        "error": error,
                    })
                    return
    
    def skip_step(self, step_id: str, reason: str = "") -> None:
        """Skip a step."""
        for phase in self.phases.values():
            for step in phase.steps:
                if step.id == step_id:
                    step.status = ProgressStatus.SKIPPED
                    step.completed_at = datetime.now()
                    step.error = reason or "Skipped"
                    
                    self._emit("step_skipped", {
                        "step_id": step_id,
                        "reason": reason,
                    })
                    return
    
    def complete(self, error: Optional[str] = None) -> None:
        """Complete investigation."""
        self.completed_at = datetime.now()
        
        self._emit("investigation_completed", {
            "duration_ms": self.total_duration_ms,
            "progress": self.overall_progress,
            "error": error,
        })
    
    @property
    def overall_progress(self) -> float:
        """Get overall progress (0-1)."""
        if not self.phases:
            return 0.0
        
        total = sum(p.progress for p in self.phases.values())
        return total / len(self.phases)
    
    @property
    def total_duration_ms(self) -> int:
        """Get total duration."""
        if not self.started_at:
            return 0
        end = self.completed_at or datetime.now()
        return int((end - self.started_at).total_seconds() * 1000)
    
    def estimate_remaining(self) -> int:
        """Estimate remaining time in ms based on completed work."""
        if not self.started_at:
            return 0
        
        elapsed = self.total_duration_ms
        progress = self.overall_progress
        
        if progress <= 0:
            return 0
        
        # Estimate total based on current progress
        estimated_total = elapsed / progress
        return max(0, int(estimated_total - elapsed))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            "investigation_id": self.investigation_id,
            "overall_progress": self.overall_progress,
            "current_phase": self.current_phase,
            "current_step": self.current_step,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.total_duration_ms,
            "estimated_remaining_ms": self.estimate_remaining(),
            "phases": {
                pid: p.to_dict() for pid, p in self.phases.items()
            },
        }


# Global tracker registry
_trackers: Dict[str, ProgressTracker] = {}


def get_tracker(investigation_id: str) -> ProgressTracker:
    """Get or create a progress tracker."""
    if investigation_id not in _trackers:
        _trackers[investigation_id] = ProgressTracker(investigation_id)
    return _trackers[investigation_id]


def remove_tracker(investigation_id: str) -> None:
    """Remove a tracker."""
    _trackers.pop(investigation_id, None)
