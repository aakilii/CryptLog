"""
Planning Tools — Investigation plan generation and execution.

This module provides tools for investigation planning:
- investigation.plan: Generate investigation plan from context
- investigation.plan.update: Update plan steps
- investigation.plan.execute: Execute plan steps

Plans are OpenClaw-style with:
- Detailed phases and steps
- Module assignments
- Success criteria
- User approval workflow

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..schemas import (
    InvestigationContext,
    InvestigationStatus,
    InvestigationPlan,
    PlanStep,
    PhaseStatus,
    ModuleName,
    TraversalStrategy,
    Hypothesis,
    HypothesisVerdict,
)
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN STORE
# ═══════════════════════════════════════════════════════════════════════════════

class PlanStore:
    """In-memory store for investigation plans."""
    
    _plans: Dict[str, InvestigationPlan] = {}
    
    @classmethod
    def save(cls, plan: InvestigationPlan) -> None:
        """Save a plan."""
        cls._plans[plan.plan_id] = plan
    
    @classmethod
    def get(cls, plan_id: str) -> Optional[InvestigationPlan]:
        """Get a plan by ID."""
        return cls._plans.get(plan_id)
    
    @classmethod
    def get_by_investigation(cls, investigation_id: str) -> Optional[InvestigationPlan]:
        """Get plan for an investigation."""
        for plan in cls._plans.values():
            if plan.investigation_id == investigation_id:
                return plan
        return None
    
    @classmethod
    def delete(cls, plan_id: str) -> bool:
        """Delete a plan."""
        if plan_id in cls._plans:
            del cls._plans[plan_id]
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class PlanGenerator:
    """
    Generates investigation plans based on context.
    
    Plans follow the BFS-first approach:
    1. Initial reconnaissance across all sources
    2. Build unified timeline
    3. Anomaly detection
    4. Correlation analysis
    5. Deep dive on high-confidence findings
    6. Report generation
    """
    
    # Phase definitions
    PHASES = [
        {
            "name": "Phase 1: Initial Reconnaissance",
            "description": "Gather overview of available data and establish baseline",
            "modules": [ModuleName.CASE],
            "required": True
        },
        {
            "name": "Phase 2: Timeline Construction",
            "description": "Build unified timeline across all evidence sources",
            "modules": [ModuleName.TIMELINE],
            "required": True
        },
        {
            "name": "Phase 3: Anomaly Detection",
            "description": "Identify anomalous activities and outliers",
            "modules": [ModuleName.ANOMALY],
            "required": True
        },
        {
            "name": "Phase 4: Correlation Analysis",
            "description": "Correlate events across sources and build attack chains",
            "modules": [ModuleName.CORRELATION],
            "required": True
        },
        {
            "name": "Phase 5: Data Flow Analysis",
            "description": "Track data access, modifications, and transfers",
            "modules": [ModuleName.CRUD, ModuleName.NETWORK],
            "required": True
        },
        {
            "name": "Phase 6: Impact Assessment",
            "description": "Assess depth and business impact of incident",
            "modules": [ModuleName.DEPTH],
            "required": True
        },
        {
            "name": "Phase 7: Hypothesis Testing",
            "description": "Test specific hypotheses based on findings",
            "modules": [],
            "required": True
        },
        {
            "name": "Phase 8: Report Generation",
            "description": "Generate comprehensive investigation report",
            "modules": [],
            "required": True
        }
    ]
    
    def __init__(self, investigation: InvestigationContext):
        self.investigation = investigation
    
    def generate_plan(self) -> InvestigationPlan:
        """Generate a complete investigation plan."""
        steps = []
        step_counter = {}
        
        for phase in self.PHASES:
            phase_name = phase["name"]
            step_counter[phase_name] = 0
            
            # Generate steps for this phase
            phase_steps = self._generate_phase_steps(phase, step_counter)
            steps.extend(phase_steps)
        
        # Create plan
        plan = InvestigationPlan(
            investigation_id=self.investigation.investigation_id,
            title=f"Investigation Plan: {self.investigation.scenario[:50]}...",
            phases=[p["name"] for p in self.PHASES],
            steps=steps,
            status=PhaseStatus.PENDING
        )
        
        return plan
    
    def _generate_phase_steps(
        self,
        phase: Dict[str, Any],
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate steps for a specific phase."""
        phase_name = phase["name"]
        phase_num = phase_name.split(":")[0].replace("Phase ", "")
        steps = []
        
        if "Phase 1" in phase_name:
            steps = self._generate_recon_steps(phase_name, phase_num, counter)
        elif "Phase 2" in phase_name:
            steps = self._generate_timeline_steps(phase_name, phase_num, counter)
        elif "Phase 3" in phase_name:
            steps = self._generate_anomaly_steps(phase_name, phase_num, counter)
        elif "Phase 4" in phase_name:
            steps = self._generate_correlation_steps(phase_name, phase_num, counter)
        elif "Phase 5" in phase_name:
            steps = self._generate_dataflow_steps(phase_name, phase_num, counter)
        elif "Phase 6" in phase_name:
            steps = self._generate_impact_steps(phase_name, phase_num, counter)
        elif "Phase 7" in phase_name:
            steps = self._generate_hypothesis_steps(phase_name, phase_num, counter)
        elif "Phase 8" in phase_name:
            steps = self._generate_report_steps(phase_name, phase_num, counter)
        
        return steps
    
    def _next_step_num(self, phase_name: str, counter: Dict[str, int]) -> str:
        """Get next step number for a phase."""
        counter[phase_name] = counter.get(phase_name, 0) + 1
        phase_num = phase_name.split(":")[0].replace("Phase ", "")
        return f"{phase_num}.{counter[phase_name]}"
    
    def _generate_recon_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate reconnaissance phase steps."""
        steps = []
        
        # Step: Get case overview
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Get Case Overview",
            description="Retrieve case metadata, uploaded files, and available log sources",
            tool_name="analysis.case.overview",
            tool_params={"case_id": self.investigation.case_id},
            success_criteria="Case metadata retrieved with list of available sources",
            expected_output="Case summary with file list and source types"
        ))
        
        # Step: Validate data sources
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Validate Data Sources",
            description="Verify selected data sources have sufficient data for analysis",
            tool_name="investigation.sources",
            tool_params={
                "case_id": self.investigation.case_id,
                "action": "validate"
            },
            depends_on=[steps[-1].step_id],
            success_criteria="All selected sources have records",
            requires_approval=True
        ))
        
        # Step: Establish time bounds
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Establish Time Bounds",
            description="Determine actual time range covered by evidence",
            tool_name="analysis.timeline.bounds",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id],
            success_criteria="Time bounds established with data coverage percentage"
        ))
        
        return steps
    
    def _generate_timeline_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate timeline phase steps."""
        steps = []
        
        # Step: Build unified timeline
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Build Unified Timeline",
            description="Create unified timeline from all selected sources with normalized timestamps",
            tool_name="analysis.timeline.build",
            tool_params={
                "case_id": self.investigation.case_id,
                "sources": self.investigation.selected_sources
            },
            success_criteria="Timeline created with >80% time coverage",
            expected_output="Timeline with event count and severity distribution"
        ))
        
        # Step: Identify anchor events
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Identify Anchor Events",
            description="Find significant events that serve as investigation anchors",
            tool_name="analysis.timeline.anchors",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id],
            success_criteria="At least 3 anchor events identified"
        ))
        
        # Step: Map entity activity
        if any(e.entity_type == "user" or e.role == "suspect" for e in self.investigation.entities):
            steps.append(PlanStep(
                phase=phase_name,
                step_number=self._next_step_num(phase_name, counter),
                title="Map Entity Activity",
                description="Map timeline activity for entities of interest",
                tool_name="analysis.timeline.entity",
                tool_params={
                    "case_id": self.investigation.case_id,
                    "entities": [e.entity_value for e in self.investigation.entities if e.role in ["suspect", "unknown"]]
                },
                depends_on=[steps[-1].step_id]
            ))
        
        return steps
    
    def _generate_anomaly_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate anomaly detection phase steps."""
        steps = []
        
        # Step: Run anomaly detection
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Run Anomaly Detection",
            description="Apply isolation forest and statistical methods to detect anomalies",
            tool_name="analysis.anomaly.detect",
            tool_params={
                "case_id": self.investigation.case_id,
                "algorithm": "isolation_forest",
                "threshold": 0.65
            },
            success_criteria="Anomaly scores computed for all events"
        ))
        
        # Step: Classify anomalies
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Classify Anomalies",
            description="Classify detected anomalies by type and severity",
            tool_name="analysis.anomaly.classify",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id],
            success_criteria="Anomalies classified with severity levels"
        ))
        
        # Step: Review high-severity anomalies
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Review High-Severity Anomalies",
            description="Present high-severity anomalies for investigator review",
            tool_name="analysis.anomaly.review",
            tool_params={"case_id": self.investigation.case_id, "min_severity": "high"},
            depends_on=[steps[-1].step_id],
            requires_approval=True
        ))
        
        return steps
    
    def _generate_correlation_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate correlation phase steps."""
        steps = []
        
        # Step: Build correlation graph
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Build Correlation Graph",
            description="Create entity relationship graph with weighted edges",
            tool_name="analysis.correlation.graph",
            tool_params={"case_id": self.investigation.case_id},
            success_criteria="Graph built with nodes and edges"
        ))
        
        # Step: Detect attack patterns
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Detect Attack Patterns",
            description="Match events against MITRE ATT&CK patterns",
            tool_name="analysis.correlation.mitre",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id],
            success_criteria="MITRE techniques identified"
        ))
        
        # Step: Build attack chain
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Build Attack Chain",
            description="Construct potential attack chain from correlated events",
            tool_name="analysis.correlation.chain",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id],
            requires_approval=True
        ))
        
        return steps
    
    def _generate_dataflow_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate data flow analysis phase steps."""
        steps = []
        
        # Step: Analyze CRUD operations
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Analyze CRUD Operations",
            description="Track create, read, update, delete operations on files",
            tool_name="analysis.crud.analyze",
            tool_params={"case_id": self.investigation.case_id},
            success_criteria="CRUD events classified with sensitivity levels"
        ))
        
        # Step: Identify sensitive data access
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Identify Sensitive Data Access",
            description="Flag access to files marked as confidential/sensitive",
            tool_name="analysis.crud.sensitive",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id]
        ))
        
        # Step: Analyze network flows
        if "network" in self.investigation.selected_sources or "sysmon" in self.investigation.selected_sources:
            steps.append(PlanStep(
                phase=phase_name,
                step_number=self._next_step_num(phase_name, counter),
                title="Analyze Network Flows",
                description="Track network connections and data transfers",
                tool_name="analysis.network.flows",
                tool_params={"case_id": self.investigation.case_id},
                success_criteria="Network flows mapped with volume metrics"
            ))
        
        # Step: Detect exfiltration
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Detect Potential Exfiltration",
            description="Identify potential data exfiltration based on flow analysis",
            tool_name="analysis.network.exfil",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id] if len(steps) > 1 else [],
            requires_approval=True
        ))
        
        return steps
    
    def _generate_impact_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate impact assessment phase steps."""
        steps = []
        
        # Step: Compute depth scores
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Compute Depth Scores",
            description="Calculate account, system, data, and control depth scores",
            tool_name="analysis.depth.compute",
            tool_params={"case_id": self.investigation.case_id},
            success_criteria="All depth dimensions scored"
        ))
        
        # Step: Assess business impact
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Assess Business Impact",
            description="Evaluate potential business impact based on depth analysis",
            tool_name="analysis.depth.impact",
            tool_params={"case_id": self.investigation.case_id},
            depends_on=[steps[-1].step_id]
        ))
        
        return steps
    
    def _generate_hypothesis_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate hypothesis testing phase steps."""
        steps = []
        
        # Step: Generate hypotheses
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Generate Hypotheses",
            description="Create hypotheses based on investigation objectives and findings",
            tool_name="hypothesis.generate",
            tool_params={
                "investigation_id": self.investigation.investigation_id,
                "objectives": [o.description for o in self.investigation.objectives]
            },
            success_criteria="Hypotheses generated with evidence requirements",
            requires_approval=True
        ))
        
        # Step: Test hypotheses
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Test Hypotheses",
            description="Test each hypothesis against collected evidence",
            tool_name="hypothesis.test",
            tool_params={"investigation_id": self.investigation.investigation_id},
            depends_on=[steps[-1].step_id],
            success_criteria="All hypotheses tested with verdicts"
        ))
        
        # Step: Compute confidence scores
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Compute Confidence Scores",
            description="Calculate confidence scores for each hypothesis verdict",
            tool_name="confidence.compute",
            tool_params={"investigation_id": self.investigation.investigation_id},
            depends_on=[steps[-1].step_id]
        ))
        
        return steps
    
    def _generate_report_steps(
        self,
        phase_name: str,
        phase_num: str,
        counter: Dict[str, int]
    ) -> List[PlanStep]:
        """Generate report phase steps."""
        steps = []
        
        # Step: Generate executive summary
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Generate Executive Summary",
            description="Create high-level summary of findings for executives",
            tool_name="report.narrative.executive",
            tool_params={"investigation_id": self.investigation.investigation_id},
            success_criteria="Executive summary generated"
        ))
        
        # Step: Build evidence appendix
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Build Evidence Appendix",
            description="Compile all evidence with citations and hashes",
            tool_name="report.evidence.appendix",
            tool_params={"investigation_id": self.investigation.investigation_id},
            success_criteria="All evidence cited with verification hashes"
        ))
        
        # Step: Generate full report
        steps.append(PlanStep(
            phase=phase_name,
            step_number=self._next_step_num(phase_name, counter),
            title="Generate Full Report",
            description="Compile complete investigation report",
            tool_name="report.generate",
            tool_params={"investigation_id": self.investigation.investigation_id},
            depends_on=[steps[-2].step_id, steps[-1].step_id],
            success_criteria="Complete report generated",
            requires_approval=True
        ))
        
        return steps


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

class PlanExecutor:
    """
    Executes investigation plan steps.
    """
    
    def __init__(self, plan: InvestigationPlan):
        self.plan = plan
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute (dependencies satisfied)."""
        ready = []
        
        for step in self.plan.steps:
            if step.status != PhaseStatus.PENDING:
                continue
            
            # Check dependencies
            deps_satisfied = True
            for dep_id in step.depends_on:
                dep_step = self._find_step(dep_id)
                if dep_step and dep_step.status != PhaseStatus.COMPLETED:
                    deps_satisfied = False
                    break
            
            if deps_satisfied:
                ready.append(step)
        
        return ready
    
    def _find_step(self, step_id: str) -> Optional[PlanStep]:
        """Find a step by ID."""
        for step in self.plan.steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_next_step(self) -> Optional[PlanStep]:
        """Get next step to execute."""
        ready = self.get_ready_steps()
        
        # Prioritize steps that don't require approval
        for step in ready:
            if not step.requires_approval or step.approved:
                return step
        
        # If all ready steps require approval, return first one
        return ready[0] if ready else None
    
    def mark_step_started(self, step_id: str) -> bool:
        """Mark a step as in progress."""
        step = self._find_step(step_id)
        if step:
            step.status = PhaseStatus.IN_PROGRESS
            step.started_at = datetime.now(timezone.utc)
            self._update_plan_progress()
            return True
        return False
    
    def mark_step_completed(
        self,
        step_id: str,
        output: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark a step as completed."""
        step = self._find_step(step_id)
        if step:
            step.status = PhaseStatus.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.output = output
            self._update_plan_progress()
            return True
        return False
    
    def mark_step_failed(
        self,
        step_id: str,
        error: str
    ) -> bool:
        """Mark a step as failed."""
        step = self._find_step(step_id)
        if step:
            step.status = PhaseStatus.FAILED
            step.completed_at = datetime.now(timezone.utc)
            step.error = error
            self._update_plan_progress()
            return True
        return False
    
    def approve_step(self, step_id: str, user_notes: Optional[str] = None) -> bool:
        """Approve a step for execution."""
        step = self._find_step(step_id)
        if step:
            step.approved = True
            step.user_notes = user_notes
            return True
        return False
    
    def _update_plan_progress(self) -> None:
        """Update plan progress percentage."""
        if not self.plan.steps:
            self.plan.progress_percent = 0
            return
        
        completed = sum(1 for s in self.plan.steps if s.status == PhaseStatus.COMPLETED)
        self.plan.progress_percent = (completed / len(self.plan.steps)) * 100
        
        # Update current phase/step
        for step in self.plan.steps:
            if step.status == PhaseStatus.IN_PROGRESS:
                self.plan.current_phase = step.phase
                self.plan.current_step = step.step_id
                break
        
        # Update plan status
        if all(s.status == PhaseStatus.COMPLETED for s in self.plan.steps):
            self.plan.status = PhaseStatus.COMPLETED
        elif any(s.status == PhaseStatus.IN_PROGRESS for s in self.plan.steps):
            self.plan.status = PhaseStatus.IN_PROGRESS
        elif any(s.status == PhaseStatus.FAILED for s in self.plan.steps):
            self.plan.status = PhaseStatus.FAILED


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="investigation.plan",
    category=ToolCategory.INVESTIGATION,
    description="Generate an investigation plan based on the investigation context. Creates phased plan with detailed steps.",
    requires_case_id=False,
    tags={"investigation", "plan", "generate"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="INVESTIGATION_PLAN_GENERATE")
async def generate_investigation_plan(
    investigation_id: str,
    regenerate: bool = False,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Generate investigation plan.
    
    Args:
        investigation_id: Investigation to plan
        regenerate: Whether to regenerate if plan exists
    
    Returns:
        Generated plan with phases and steps
    """
    # Get investigation
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    # Check if plan exists
    existing = PlanStore.get_by_investigation(investigation_id)
    if existing and not regenerate:
        return {
            "success": True,
            "plan_id": existing.plan_id,
            "already_exists": True,
            "plan": _plan_to_dict(existing)
        }
    
    # Check investigation status
    if inv.status == InvestigationStatus.AWAITING_CLARIFICATION:
        return {
            "success": False,
            "error": "Investigation has pending clarification questions",
            "status": enum_value(inv.status)
        }
    
    # Generate plan
    generator = PlanGenerator(inv)
    plan = generator.generate_plan()
    
    # Save plan
    PlanStore.save(plan)
    
    # Update investigation status
    inv.status = InvestigationStatus.PLANNING
    InvestigationStore.save(inv)
    
    logger.info(f"Generated plan {plan.plan_id} with {len(plan.steps)} steps")
    
    return {
        "success": True,
        "plan_id": plan.plan_id,
        "plan": _plan_to_dict(plan),
        "summary": {
            "phase_count": len(plan.phases),
            "step_count": len(plan.steps),
            "approval_required": len([s for s in plan.steps if s.requires_approval])
        },
        "next_action": "Review plan and use investigation.plan.approve to approve steps"
    }


@mcp_tool(
    name="investigation.plan.get",
    category=ToolCategory.INVESTIGATION,
    description="Get current investigation plan.",
    requires_case_id=False,
    tags={"investigation", "plan", "get"}
)
async def get_investigation_plan(
    plan_id: Optional[str] = None,
    investigation_id: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get investigation plan.
    
    Args:
        plan_id: Plan ID (preferred)
        investigation_id: Investigation ID (fallback)
    
    Returns:
        Plan details
    """
    plan = None
    
    if plan_id:
        plan = PlanStore.get(plan_id)
    elif investigation_id:
        plan = PlanStore.get_by_investigation(investigation_id)
    
    if not plan:
        return {"success": False, "error": "Plan not found"}
    
    executor = PlanExecutor(plan)
    ready_steps = executor.get_ready_steps()
    
    return {
        "success": True,
        "plan": _plan_to_dict(plan),
        "execution_status": {
            "progress_percent": plan.progress_percent,
            "current_phase": plan.current_phase,
            "current_step": plan.current_step,
            "ready_steps": [s.step_id for s in ready_steps],
            "pending_approvals": [s.step_id for s in plan.steps if s.requires_approval and not s.approved]
        }
    }


@mcp_tool(
    name="investigation.plan.approve",
    category=ToolCategory.INVESTIGATION,
    description="Approve plan steps for execution.",
    requires_case_id=False,
    tags={"investigation", "plan", "approve"}
)
@audit_trail(operation="INVESTIGATION_PLAN_APPROVE")
async def approve_plan_steps(
    plan_id: str,
    step_ids: List[str],
    approve_all: bool = False,
    user_notes: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Approve plan steps for execution.
    
    Args:
        plan_id: Plan ID
        step_ids: List of step IDs to approve
        approve_all: Approve all pending steps
        user_notes: Optional notes from investigator
    
    Returns:
        Approval result
    """
    plan = PlanStore.get(plan_id)
    if not plan:
        return {"success": False, "error": f"Plan not found: {plan_id}"}
    
    executor = PlanExecutor(plan)
    approved = []
    
    if approve_all:
        step_ids = [s.step_id for s in plan.steps if s.requires_approval and not s.approved]
    
    for step_id in step_ids:
        if executor.approve_step(step_id, user_notes):
            approved.append(step_id)
    
    PlanStore.save(plan)
    
    # Check if plan can now proceed
    ready = executor.get_ready_steps()
    
    return {
        "success": True,
        "approved_steps": approved,
        "ready_to_execute": [s.step_id for s in ready],
        "next_action": "Use investigation.plan.execute to run ready steps"
    }


@mcp_tool(
    name="investigation.plan.execute",
    category=ToolCategory.INVESTIGATION,
    description="Execute the next ready step in the plan.",
    requires_case_id=False,
    tags={"investigation", "plan", "execute"}
)
@with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
@audit_trail(operation="INVESTIGATION_PLAN_EXECUTE")
async def execute_plan_step(
    plan_id: str,
    step_id: Optional[str] = None,
    auto_approve: bool = False,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Execute a plan step.
    
    Args:
        plan_id: Plan ID
        step_id: Specific step to execute (or auto-select next)
        auto_approve: Automatically approve if required
    
    Returns:
        Execution result
    """
    plan = PlanStore.get(plan_id)
    if not plan:
        return {"success": False, "error": f"Plan not found: {plan_id}"}
    
    executor = PlanExecutor(plan)
    
    # Find step to execute
    step = None
    if step_id:
        for s in plan.steps:
            if s.step_id == step_id:
                step = s
                break
        if not step:
            return {"success": False, "error": f"Step not found: {step_id}"}
    else:
        step = executor.get_next_step()
        if not step:
            return {
                "success": False,
                "error": "No steps ready for execution",
                "pending_approvals": [s.step_id for s in plan.steps if s.requires_approval and not s.approved]
            }
    
    # Check approval
    if step.requires_approval and not step.approved:
        if auto_approve:
            executor.approve_step(step.step_id)
        else:
            return {
                "success": False,
                "error": f"Step {step.step_id} requires approval",
                "step": step.model_dump()
            }
    
    # Mark as started
    executor.mark_step_started(step.step_id)
    PlanStore.save(plan)
    
    # Execute the tool (in production, this would actually call the tool)
    # For now, we simulate execution
    logger.info(f"Executing step {step.step_id}: {step.title}")
    
    # Simulate result
    result = {
        "executed": True,
        "tool_name": step.tool_name,
        "params": step.tool_params,
        "message": f"Step {step.step_number} executed (simulation)"
    }
    
    # Mark as completed
    executor.mark_step_completed(step.step_id, result)
    PlanStore.save(plan)
    
    # Get next steps
    next_ready = executor.get_ready_steps()
    
    return {
        "success": True,
        "step_id": step.step_id,
        "step_number": step.step_number,
        "title": step.title,
        "result": result,
        "plan_progress": plan.progress_percent,
        "next_ready_steps": [s.step_id for s in next_ready],
        "plan_status": enum_value(plan.status)
    }


def _plan_to_dict(plan: InvestigationPlan) -> Dict[str, Any]:
    """Convert plan to dictionary."""
    return {
        "plan_id": plan.plan_id,
        "investigation_id": plan.investigation_id,
        "title": plan.title,
        "status": enum_value(plan.status),
        "progress_percent": plan.progress_percent,
        "phases": plan.phases,
        "steps": [
            {
                "step_id": s.step_id,
                "phase": s.phase,
                "step_number": s.step_number,
                "title": s.title,
                "description": s.description,
                "tool_name": s.tool_name,
                "status": enum_value(s.status),
                "requires_approval": s.requires_approval,
                "approved": s.approved,
                "depends_on": s.depends_on,
                "success_criteria": s.success_criteria
            }
            for s in plan.steps
        ],
        "total_steps": plan.total_steps,
        "completed_steps": plan.completed_steps
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "PlanStore",
    "PlanGenerator",
    "PlanExecutor",
    "generate_investigation_plan",
    "get_investigation_plan",
    "approve_plan_steps",
    "execute_plan_step",
]
