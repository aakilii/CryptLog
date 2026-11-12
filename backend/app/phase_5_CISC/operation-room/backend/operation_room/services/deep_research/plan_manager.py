"""
Plan Manager Service.

Manages investigation plans with:
- Plan CRUD operations
- User command processing
- Approval workflow
- State persistence
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
import json
import logging
import uuid

from .plan_models import (
    InvestigationPlan,
    PlanPhase,
    PlanStep,
    PlanStatus,
    StepType,
)


logger = logging.getLogger(__name__)


@dataclass
class PlanCommand:
    """A command to modify the plan."""
    command_type: str
    target_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    user: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class PlanManager:
    """
    Manages investigation plan lifecycle.
    
    Features:
    - Create and update plans
    - Process user commands (add, remove, reorder)
    - Handle approval workflow
    - Track modifications
    """
    
    def __init__(self):
        """Initialize the plan manager."""
        self._plans: Dict[str, InvestigationPlan] = {}
        self._approval_callbacks: List[Callable] = []
    
    def create_plan(
        self,
        investigation_id: str,
        title: str = "",
        scenario_summary: str = "",
        objectives: Optional[List[str]] = None,
    ) -> InvestigationPlan:
        """
        Create a new investigation plan.
        
        Args:
            investigation_id: Associated investigation ID
            title: Plan title
            scenario_summary: Summary of the scenario
            objectives: List of investigation objectives
            
        Returns:
            Created plan
        """
        plan = InvestigationPlan(
            investigation_id=investigation_id,
            title=title or "Investigation Plan",
            scenario_summary=scenario_summary,
            objectives=objectives or [],
            null_hypothesis="The suspected activity did NOT occur",
        )
        
        self._plans[plan.id] = plan
        logger.info(f"Created plan {plan.id} for investigation {investigation_id}")
        
        return plan
    
    def get_plan(self, plan_id: str) -> Optional[InvestigationPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)
    
    def get_plan_by_investigation(self, investigation_id: str) -> Optional[InvestigationPlan]:
        """Get plan for an investigation."""
        for plan in self._plans.values():
            if plan.investigation_id == investigation_id:
                return plan
        return None
    
    def update_plan(
        self,
        plan_id: str,
        updates: Dict[str, Any],
        user: Optional[str] = None,
    ) -> InvestigationPlan:
        """
        Update plan attributes.
        
        Args:
            plan_id: Plan ID
            updates: Dictionary of updates
            user: User making the update
            
        Returns:
            Updated plan
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        
        plan.record_modification("update", updates, user)
        
        return plan
    
    def process_command(
        self,
        plan_id: str,
        command: PlanCommand,
    ) -> InvestigationPlan:
        """
        Process a user command on the plan.
        
        Supported commands:
        - add_phase: Add a new phase
        - remove_phase: Remove a phase
        - reorder_phase: Change phase order
        - add_step: Add step to phase
        - remove_step: Remove step from phase
        - edit_step: Modify step
        - add_hypothesis: Add alternative hypothesis
        - remove_hypothesis: Remove hypothesis
        
        Args:
            plan_id: Plan ID
            command: Command to process
            
        Returns:
            Updated plan
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        handler = getattr(self, f"_handle_{command.command_type}", None)
        if not handler:
            raise ValueError(f"Unknown command: {command.command_type}")
        
        handler(plan, command)
        plan.record_modification(command.command_type, command.data, command.user)
        
        return plan
    
    def _handle_add_phase(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Add a new phase."""
        phase = PlanPhase(
            title=command.data.get("title", "New Phase"),
            description=command.data.get("description", ""),
            objective=command.data.get("objective", ""),
        )
        
        # Add steps if provided
        for step_data in command.data.get("steps", []):
            step = PlanStep(
                title=step_data.get("title", ""),
                description=step_data.get("description", ""),
                step_type=StepType(step_data.get("step_type", "analysis")),
                module=step_data.get("module"),
                parameters=step_data.get("parameters", {}),
            )
            phase.steps.append(step)
        
        plan.add_phase(phase)
    
    def _handle_remove_phase(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Remove a phase."""
        phase_id = command.target_id or command.data.get("phase_id")
        if not phase_id:
            raise ValueError("phase_id required")
        
        if not plan.remove_phase(phase_id):
            raise ValueError(f"Phase not found: {phase_id}")
    
    def _handle_reorder_phase(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Reorder a phase."""
        phase_id = command.target_id or command.data.get("phase_id")
        new_order = command.data.get("new_order")
        
        if phase_id is None or new_order is None:
            raise ValueError("phase_id and new_order required")
        
        if not plan.reorder_phase(phase_id, new_order):
            raise ValueError(f"Failed to reorder phase: {phase_id}")
    
    def _handle_add_step(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Add a step to a phase."""
        phase_id = command.data.get("phase_id")
        phase = plan.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase not found: {phase_id}")
        
        step = PlanStep(
            title=command.data.get("title", "New Step"),
            description=command.data.get("description", ""),
            step_type=StepType(command.data.get("step_type", "analysis")),
            module=command.data.get("module"),
            parameters=command.data.get("parameters", {}),
            order=len(phase.steps),
        )
        
        phase.steps.append(step)
    
    def _handle_remove_step(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Remove a step from a phase."""
        phase_id = command.data.get("phase_id")
        step_id = command.data.get("step_id")
        
        phase = plan.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase not found: {phase_id}")
        
        phase.steps = [s for s in phase.steps if s.id != step_id]
    
    def _handle_edit_step(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Edit a step."""
        phase_id = command.data.get("phase_id")
        step_id = command.data.get("step_id")
        updates = command.data.get("updates", {})
        
        phase = plan.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase not found: {phase_id}")
        
        for step in phase.steps:
            if step.id == step_id:
                for key, value in updates.items():
                    if hasattr(step, key):
                        setattr(step, key, value)
                break
    
    def _handle_add_hypothesis(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Add an alternative hypothesis."""
        hypothesis = command.data.get("hypothesis")
        if hypothesis and hypothesis not in plan.alternative_hypotheses:
            plan.alternative_hypotheses.append(hypothesis)
    
    def _handle_remove_hypothesis(self, plan: InvestigationPlan, command: PlanCommand) -> None:
        """Remove a hypothesis."""
        hypothesis = command.data.get("hypothesis")
        if hypothesis in plan.alternative_hypotheses:
            plan.alternative_hypotheses.remove(hypothesis)
    
    # Approval Workflow
    
    def submit_for_approval(self, plan_id: str) -> InvestigationPlan:
        """Submit plan for approval."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        plan.status = PlanStatus.PENDING_APPROVAL
        plan.updated_at = datetime.now()
        
        logger.info(f"Plan {plan_id} submitted for approval")
        
        return plan
    
    def approve_plan(
        self,
        plan_id: str,
        approver: str = "investigator",
        comments: Optional[str] = None,
    ) -> InvestigationPlan:
        """
        Approve a plan for execution.
        
        Args:
            plan_id: Plan ID
            approver: Name/ID of approver
            comments: Optional approval comments
            
        Returns:
            Approved plan
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        plan.approve(approver)
        
        if comments:
            plan.record_modification("approval_comment", {"comments": comments}, approver)
        
        # Notify callbacks
        for callback in self._approval_callbacks:
            try:
                callback(plan)
            except Exception as e:
                logger.error(f"Approval callback error: {e}")
        
        logger.info(f"Plan {plan_id} approved by {approver}")
        
        return plan
    
    def reject_plan(
        self,
        plan_id: str,
        rejector: str,
        reason: str,
    ) -> InvestigationPlan:
        """
        Reject a plan.
        
        Args:
            plan_id: Plan ID
            rejector: Name/ID of rejector
            reason: Rejection reason
            
        Returns:
            Rejected plan (back to draft)
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        plan.status = PlanStatus.DRAFT
        plan.record_modification("rejection", {"reason": reason}, rejector)
        
        logger.info(f"Plan {plan_id} rejected by {rejector}: {reason}")
        
        return plan
    
    def on_approval(self, callback: Callable[[InvestigationPlan], None]) -> None:
        """Register approval callback."""
        self._approval_callbacks.append(callback)
    
    # Execution
    
    def start_execution(self, plan_id: str) -> InvestigationPlan:
        """Start plan execution."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        if plan.status != PlanStatus.APPROVED:
            raise ValueError("Plan must be approved before execution")
        
        plan.status = PlanStatus.IN_PROGRESS
        plan.started_at = datetime.now()
        
        # Start first phase
        if plan.phases:
            plan.phases[0].status = PlanStatus.IN_PROGRESS
            plan.phases[0].started_at = datetime.now()
        
        logger.info(f"Started execution of plan {plan_id}")
        
        return plan
    
    def complete_step(
        self,
        plan_id: str,
        phase_id: str,
        step_id: str,
        output: Optional[Dict[str, Any]] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> PlanStep:
        """
        Mark a step as complete.
        
        Args:
            plan_id: Plan ID
            phase_id: Phase ID
            step_id: Step ID
            output: Step output data
            evidence_refs: Evidence references
            
        Returns:
            Completed step
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        phase = plan.get_phase(phase_id)
        if not phase:
            raise ValueError(f"Phase not found: {phase_id}")
        
        step = None
        for s in phase.steps:
            if s.id == step_id:
                step = s
                break
        
        if not step:
            raise ValueError(f"Step not found: {step_id}")
        
        step.status = PlanStatus.COMPLETED
        step.completed_at = datetime.now()
        step.progress = 1.0
        step.output = output
        step.evidence_refs = evidence_refs or []
        
        # Check if phase is complete
        if all(s.status == PlanStatus.COMPLETED for s in phase.steps):
            phase.status = PlanStatus.COMPLETED
            phase.completed_at = datetime.now()
            
            # Start next phase
            next_phase = plan.next_phase
            if next_phase:
                next_phase.status = PlanStatus.IN_PROGRESS
                next_phase.started_at = datetime.now()
        
        # Check if plan is complete
        if all(p.status == PlanStatus.COMPLETED for p in plan.phases):
            plan.status = PlanStatus.COMPLETED
            plan.completed_at = datetime.now()
        
        return step
    
    # Serialization
    
    def save_plan(self, plan_id: str, path: str) -> None:
        """Save plan to file."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        with open(path, "w") as f:
            json.dump(plan.to_dict(), f, indent=2, default=str)
    
    def load_plan(self, path: str) -> InvestigationPlan:
        """Load plan from file."""
        with open(path, "r") as f:
            data = json.load(f)
        
        plan = InvestigationPlan.from_dict(data)
        self._plans[plan.id] = plan
        
        return plan


# Global instance
_plan_manager: Optional[PlanManager] = None


def get_plan_manager() -> PlanManager:
    """Get the global plan manager instance."""
    global _plan_manager
    if _plan_manager is None:
        _plan_manager = PlanManager()
    return _plan_manager
