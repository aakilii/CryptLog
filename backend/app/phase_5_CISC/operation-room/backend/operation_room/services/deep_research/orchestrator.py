"""
Deep Research Orchestrator.

Main orchestrator that combines all components:
- LLM Service for generation
- ThoughtEngine for chain-of-thought
- PlanManager for investigation planning
- HumanLoopManager for user interaction
- ReportBuilder for report generation
- Analysis modules for evidence processing
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio
import logging
import json

from .models import ThoughtTree, ThoughtNode, ThoughtType, ThoughtStatus
from .engine import ThoughtEngine
from .plan_models import InvestigationPlan, PlanPhase, PlanStep, PlanStatus
from .plan_manager import PlanManager, get_plan_manager
from .human_loop import HumanLoopManager, QuestionPriority, get_hil_manager
from .report_builder import ReportBuilder, ReportStructure, get_report_builder


logger = logging.getLogger(__name__)


class OrchestrationPhase(str, Enum):
    """Orchestration phases."""
    INTAKE = "intake"
    CLARIFICATION = "clarification"
    PLANNING = "planning"
    APPROVAL = "approval"
    EXECUTION = "execution"
    SYNTHESIS = "synthesis"
    REPORTING = "reporting"
    COMPLETE = "complete"


@dataclass
class InvestigationContext:
    """Context for an investigation."""
    investigation_id: str = ""
    case_id: str = ""
    
    # Input
    scenario: str = ""
    objectives: List[str] = field(default_factory=list)
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    suspected_entities: List[str] = field(default_factory=list)
    victim_systems: List[str] = field(default_factory=list)
    mode: str = "focused"
    
    # State
    phase: OrchestrationPhase = OrchestrationPhase.INTAKE
    
    # Components
    thought_tree_id: Optional[str] = None
    plan_id: Optional[str] = None
    report_structure_id: Optional[str] = None
    
    # Results
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    
    # Timing
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "case_id": self.case_id,
            "scenario": self.scenario,
            "objectives": self.objectives,
            "time_range_start": self.time_range_start,
            "time_range_end": self.time_range_end,
            "suspected_entities": self.suspected_entities,
            "victim_systems": self.victim_systems,
            "mode": self.mode,
            "phase": self.phase.value,
            "thought_tree_id": self.thought_tree_id,
            "plan_id": self.plan_id,
            "report_structure_id": self.report_structure_id,
            "hypotheses": self.hypotheses,
            "findings": self.findings,
            "evidence_refs": self.evidence_refs,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class DeepResearchOrchestrator:
    """
    Main orchestrator for deep research investigations.
    
    Workflow:
    1. Intake: Parse scenario, extract entities
    2. Clarification: Ask questions, gather requirements
    3. Planning: Generate investigation plan
    4. Approval: Get user approval on plan
    5. Execution: Run analysis modules, test hypotheses
    6. Synthesis: Combine findings, compute confidence
    7. Reporting: Generate report with evidence
    """
    
    def __init__(
        self,
        llm_service: Optional[Any] = None,
        thought_engine: Optional[ThoughtEngine] = None,
        plan_manager: Optional[PlanManager] = None,
        hil_manager: Optional[HumanLoopManager] = None,
        report_builder: Optional[ReportBuilder] = None,
    ):
        """Initialize the orchestrator."""
        self._llm_service = llm_service
        self._thought_engine = thought_engine or ThoughtEngine(llm_service)
        self._plan_manager = plan_manager or get_plan_manager()
        self._hil_manager = hil_manager or get_hil_manager()
        self._report_builder = report_builder or get_report_builder()
        
        self._contexts: Dict[str, InvestigationContext] = {}
    
    @property
    def llm_service(self):
        """Get LLM service."""
        if self._llm_service is None:
            from operation_room.services.llm import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service
    
    async def start_investigation(
        self,
        case_id: str,
        scenario: str,
        objectives: Optional[List[str]] = None,
        mode: str = "focused",
        **kwargs,
    ) -> InvestigationContext:
        """
        Start a new investigation.
        
        Args:
            case_id: Case ID
            scenario: Scenario description
            objectives: Investigation objectives
            mode: Investigation mode (focused, brute_force, hybrid)
            **kwargs: Additional context
            
        Returns:
            Investigation context
        """
        import uuid
        
        # Create context
        context = InvestigationContext(
            investigation_id=str(uuid.uuid4()),
            case_id=case_id,
            scenario=scenario,
            objectives=objectives or [],
            mode=mode,
            **{k: v for k, v in kwargs.items() if hasattr(InvestigationContext, k)},
        )
        
        self._contexts[context.investigation_id] = context
        
        # Create thought tree
        tree = self._thought_engine.create_tree(context.investigation_id)
        context.thought_tree_id = tree.id
        
        # Initial thought - analyzing scenario
        await self._thought_engine.create_thought(
            tree=tree,
            title="Analyzing investigation scenario",
            thought_type=ThoughtType.PLANNING,
            initial_content=f"Processing scenario: {scenario[:200]}...",
        )
        
        logger.info(f"Started investigation {context.investigation_id}")
        
        return context
    
    def get_context(self, investigation_id: str) -> Optional[InvestigationContext]:
        """Get investigation context."""
        return self._contexts.get(investigation_id)

    def get_thought_tree(self, tree_id: str) -> Optional[ThoughtTree]:
        """Get thought tree from shared thought engine state."""
        return self._thought_engine.get_tree(tree_id)
    
    async def run_phase_intake(
        self,
        investigation_id: str,
    ) -> Dict[str, Any]:
        """
        Run intake phase - analyze scenario.
        
        Extracts:
        - Entities (devices, users, systems)
        - Actions (transfers, access, modifications)
        - Channels (USB, email, network)
        - Objectives (what to prove/disprove)
        """
        context = self._contexts.get(investigation_id)
        if not context:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if not context.thought_tree_id:
            raise ValueError("Thought tree ID missing")
        
        tree = self._thought_engine.get_tree(context.thought_tree_id)
        if not tree:
            raise ValueError("Thought tree not found")
        
        # Parse scenario
        parse_thought = await self._thought_engine.create_thought(
            tree=tree,
            title="Parsing scenario entities",
            thought_type=ThoughtType.ANALYSIS,
        )
        
        from operation_room.services.llm import Message
        
        prompt = f"""Analyze this forensic investigation scenario and extract structured information:

SCENARIO:
{context.scenario}

OBJECTIVES:
{json.dumps(context.objectives)}

Extract and provide JSON with:
{{
    "entities": {{
        "devices": ["list of devices mentioned"],
        "users": ["list of users/actors"],
        "systems": ["list of systems/applications"]
    }},
    "actions": ["list of actions to investigate"],
    "channels": ["communication/transfer channels mentioned"],
    "time_indicators": ["any time references"],
    "key_objectives": ["main investigation goals"],
    "missing_information": ["what's unclear or missing"]
}}"""
        
        response = await self.llm_service.generate([
            Message(role="system", content="You are a forensic analyst parsing investigation scenarios."),
            Message(role="user", content=prompt),
        ])
        
        # Parse response
        try:
            # Extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            parsed = json.loads(content.strip())
        except json.JSONDecodeError:
            parsed = {"error": "Failed to parse scenario", "raw": response.content}
        
        parse_thought.complete(result="Scenario parsed successfully")
        
        context.phase = OrchestrationPhase.CLARIFICATION
        
        return {
            "investigation_id": investigation_id,
            "phase": "intake",
            "parsed_scenario": parsed,
            "next_phase": "clarification",
        }
    
    async def run_phase_clarification(
        self,
        investigation_id: str,
    ) -> Dict[str, Any]:
        """
        Run clarification phase - ask necessary questions.
        """
        context = self._contexts.get(investigation_id)
        if not context:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if not context.thought_tree_id:
            raise ValueError("Thought tree ID missing")
        
        tree = self._thought_engine.get_tree(context.thought_tree_id)
        if not tree:
            raise ValueError("Thought tree not found")
        
        # Create clarification thought
        clarify_thought = await self._thought_engine.create_thought(
            tree=tree,
            title="Identifying clarification needs",
            thought_type=ThoughtType.CLARIFICATION,
        )
        
        # Generate clarification questions based on scenario
        from operation_room.services.llm import Message
        
        prompt = f"""Based on this scenario, generate clarification questions:

SCENARIO: {context.scenario}

Generate 3-5 questions to clarify:
1. What log sources are available
2. Time range of interest
3. Specific entities to focus on
4. Classification level of data
5. Any constraints

Return as JSON: {{"questions": [{{"question": "...", "options": ["opt1", "opt2"] or null, "priority": "blocking|high|medium|low"}}]}}"""
        
        response = await self.llm_service.generate([
            Message(role="user", content=prompt),
        ])
        
        # Parse and create questions
        questions = []
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            parsed = json.loads(content.strip())
            
            for q_data in parsed.get("questions", []):
                q = self._hil_manager.create_question(
                    question=q_data.get("question", ""),
                    investigation_id=investigation_id,
                    priority=QuestionPriority(q_data.get("priority", "medium")),
                    options=q_data.get("options"),
                    thought_id=clarify_thought.id,
                )
                questions.append(q.to_dict())
        except Exception as e:
            logger.error(f"Failed to create questions: {e}")
        
        clarify_thought.complete(result=f"Created {len(questions)} clarification questions")
        
        return {
            "investigation_id": investigation_id,
            "phase": "clarification",
            "questions": questions,
            "has_blocking": self._hil_manager.has_blocking_questions(investigation_id),
        }
    
    async def run_phase_planning(
        self,
        investigation_id: str,
    ) -> Dict[str, Any]:
        """
        Run planning phase - create investigation plan.
        """
        context = self._contexts.get(investigation_id)
        if not context:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if not context.thought_tree_id:
            raise ValueError("Thought tree ID missing")
        
        tree = self._thought_engine.get_tree(context.thought_tree_id)
        if not tree:
            raise ValueError("Thought tree not found")
        
        # Create planning thought
        plan_thought = await self._thought_engine.create_thought(
            tree=tree,
            title="Generating investigation plan",
            thought_type=ThoughtType.PLANNING,
        )
        
        # Create plan
        plan = self._plan_manager.create_plan(
            investigation_id=investigation_id,
            title=f"Investigation Plan - Case {context.case_id}",
            scenario_summary=context.scenario[:500],
            objectives=context.objectives,
        )
        
        context.plan_id = plan.id
        
        # Add default phases based on mode
        if context.mode == "focused":
            phases = [
                ("Data Ingestion", "Ingest and normalize log data"),
                ("Timeline Construction", "Build unified timeline"),
                ("Hypothesis Testing", "Test investigation hypotheses"),
                ("Synthesis", "Combine findings and conclusions"),
            ]
        else:  # brute_force or hybrid
            phases = [
                ("Data Ingestion", "Ingest and normalize all log data"),
                ("Comprehensive Timeline", "Build complete timeline"),
                ("Anomaly Detection", "Identify anomalies"),
                ("Entity Correlation", "Correlate entities"),
                ("Hypothesis Testing", "Test all hypotheses"),
                ("Deep Dive", "Deep analysis of findings"),
                ("Synthesis", "Final conclusions"),
            ]
        
        for title, objective in phases:
            self._plan_manager.process_command(plan.id, PlanCommand(
                command_type="add_phase",
                data={"title": title, "objective": objective},
            ))
        
        # Add hypotheses
        self._plan_manager.process_command(plan.id, PlanCommand(
            command_type="add_hypothesis",
            data={"hypothesis": "Data exfiltration via USB"},
        ))
        self._plan_manager.process_command(plan.id, PlanCommand(
            command_type="add_hypothesis",
            data={"hypothesis": "Data exfiltration via email"},
        ))
        
        plan_thought.complete(result=f"Created plan with {len(plan.phases)} phases")
        context.phase = OrchestrationPhase.APPROVAL
        
        return {
            "investigation_id": investigation_id,
            "phase": "planning",
            "plan": plan.to_dict(),
        }
    
    async def run_phase_execution(
        self,
        investigation_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run execution phase - execute plan steps.
        
        Yields progress events.
        """
        context = self._contexts.get(investigation_id)
        if not context:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if not context.plan_id:
            raise ValueError("Plan ID missing")
        
        plan = self._plan_manager.get_plan(context.plan_id)
        if not plan:
            raise ValueError("Plan not found")

        if not context.thought_tree_id:
            raise ValueError("Thought tree ID missing")
        
        tree = self._thought_engine.get_tree(context.thought_tree_id)
        if not tree:
            raise ValueError("Thought tree not found")
        
        # Start execution
        self._plan_manager.start_execution(plan.id)
        context.phase = OrchestrationPhase.EXECUTION
        
        yield {
            "event": "execution_started",
            "investigation_id": investigation_id,
        }
        
        # Execute each phase
        for phase in sorted(plan.phases, key=lambda p: p.order):
            phase_thought = await self._thought_engine.create_thought(
                tree=tree,
                title=f"Executing: {phase.title}",
                thought_type=ThoughtType.ANALYSIS,
            )
            
            yield {
                "event": "phase_started",
                "phase_id": phase.id,
                "phase_title": phase.title,
            }
            
            # Execute each step
            for step in sorted(phase.steps, key=lambda s: s.order):
                yield {
                    "event": "step_started",
                    "step_id": step.id,
                    "step_title": step.title,
                }
                
                # Simulate step execution
                # In real implementation, would call actual analysis modules
                await asyncio.sleep(0.5)
                
                # Mark step complete
                self._plan_manager.complete_step(
                    plan.id, phase.id, step.id,
                    output={"status": "completed"},
                )
                
                yield {
                    "event": "step_completed",
                    "step_id": step.id,
                }
            
            phase_thought.complete(result=f"Phase {phase.title} completed")
            
            yield {
                "event": "phase_completed",
                "phase_id": phase.id,
            }
        
        context.phase = OrchestrationPhase.SYNTHESIS
        
        yield {
            "event": "execution_completed",
            "investigation_id": investigation_id,
        }
    
    async def run_phase_reporting(
        self,
        investigation_id: str,
    ) -> Dict[str, Any]:
        """
        Run reporting phase - generate report.
        """
        context = self._contexts.get(investigation_id)
        if not context:
            raise ValueError(f"Investigation not found: {investigation_id}")

        if not context.thought_tree_id:
            raise ValueError("Thought tree ID missing")
        
        tree = self._thought_engine.get_tree(context.thought_tree_id)
        if not tree:
            raise ValueError("Thought tree not found")
        
        # Create report structure
        report_thought = await self._thought_engine.create_thought(
            tree=tree,
            title="Generating report structure",
            thought_type=ThoughtType.SYNTHESIS,
        )
        
        structure = self._report_builder.create_structure(
            investigation_id=investigation_id,
            title=f"Forensic Investigation Report - Case {context.case_id}",
            template="detailed",
        )
        
        context.report_structure_id = structure.id
        
        report_thought.complete(
            result=f"Created report structure with {len(structure.sections)} sections"
        )
        
        context.phase = OrchestrationPhase.COMPLETE
        context.completed_at = datetime.now()
        
        return {
            "investigation_id": investigation_id,
            "phase": "reporting",
            "report_structure": structure.to_dict(),
        }
    
    async def run_full_investigation(
        self,
        case_id: str,
        scenario: str,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run a full investigation from start to finish.
        
        Yields progress events throughout the process.
        """
        # Start
        context = await self.start_investigation(case_id, scenario, **kwargs)
        
        yield {
            "event": "investigation_started",
            "investigation_id": context.investigation_id,
        }
        
        # Intake
        intake_result = await self.run_phase_intake(context.investigation_id)
        yield {"event": "phase_complete", "phase": "intake", "result": intake_result}
        
        # Clarification
        clarify_result = await self.run_phase_clarification(context.investigation_id)
        yield {"event": "phase_complete", "phase": "clarification", "result": clarify_result}
        
        # Wait for blocking questions
        if clarify_result.get("has_blocking"):
            yield {"event": "waiting_for_answers", "questions": clarify_result["questions"]}
            # In real impl, would wait for answers
        
        # Planning
        plan_result = await self.run_phase_planning(context.investigation_id)
        yield {"event": "phase_complete", "phase": "planning", "result": plan_result}
        
        # Wait for approval
        yield {"event": "waiting_for_approval", "plan_id": context.plan_id}
        # In real impl, would wait for approval
        
        # Auto-approve for demo
        if context.plan_id:
            plan = self._plan_manager.get_plan(context.plan_id)
        else:
            plan = None

        if plan:
            self._plan_manager.approve_plan(plan.id, "auto")
        
        # Execution
        async for event in self.run_phase_execution(context.investigation_id):
            yield event
        
        # Reporting
        report_result = await self.run_phase_reporting(context.investigation_id)
        yield {"event": "phase_complete", "phase": "reporting", "result": report_result}
        
        # Complete
        yield {
            "event": "investigation_complete",
            "investigation_id": context.investigation_id,
            "context": context.to_dict(),
        }
    
    def get_status(self, investigation_id: str) -> Dict[str, Any]:
        """Get investigation status."""
        context = self._contexts.get(investigation_id)
        if not context:
            return {"error": "Investigation not found"}
        
        plan = None
        if context.plan_id:
            plan = self._plan_manager.get_plan(context.plan_id)
        
        tree = None
        if context.thought_tree_id:
            tree = self._thought_engine.get_tree(context.thought_tree_id)
        
        return {
            "investigation_id": investigation_id,
            "phase": context.phase.value,
            "plan_status": plan.status.value if plan else None,
            "plan_progress": plan.progress if plan else 0,
            "thought_count": len(tree.nodes) if tree else 0,
            "pending_questions": len(self._hil_manager.get_pending_questions(investigation_id)),
            "started_at": context.started_at.isoformat(),
            "completed_at": context.completed_at.isoformat() if context.completed_at else None,
        }


# Global instance
_orchestrator: Optional[DeepResearchOrchestrator] = None


def get_orchestrator() -> DeepResearchOrchestrator:
    """Get the global orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = DeepResearchOrchestrator()
    return _orchestrator


# Import helper for PlanCommand
from .plan_manager import PlanCommand
