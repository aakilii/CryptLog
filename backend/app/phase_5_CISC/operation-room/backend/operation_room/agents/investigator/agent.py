"""
Investigation Agent Core
========================

The main investigation agent that orchestrates forensic analysis through MCP tools.

Key Design Principles:
1. AI NEVER generates evidence values (IPs, MACs, timestamps)
2. AI generates SUMMARIES and NARRATIVES from real evidence
3. All findings are TRACEABLE through Evidence Vault
4. Human investigator IN THE LOOP at decision points
5. Confidence scores COMPUTED from module agreement

Workflow:
1. Receive scenario and metadata
2. Ask clarification questions (via MCP tools)
3. Generate investigation plan
4. Execute analysis phases (BFS/DFS on hypothesis tree)
5. Accumulate evidence in vault
6. Generate report with citations

Author: NFLIP Development Team
Version: 1.0.0
"""

import asyncio
import uuid
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

# LLM Integration
try:
    import google.generativeai as genai
except ModuleNotFoundError:
    genai = None
import os

# MCP Tools imports
from operation_room.mcp.tools.investigation import (
    start_investigation,
    get_investigation_context,
    list_investigations,
)
from operation_room.mcp.tools.clarification import (
    list_clarification_questions,
    answer_clarification,
)
from operation_room.mcp.tools.planning import (
    generate_investigation_plan,
    get_investigation_plan,
    execute_plan_step,
)
from operation_room.mcp.tools.hypothesis import (
    generate_hypotheses,
    test_hypotheses,
    get_hypothesis_tree,
)
from operation_room.mcp.tools.evidence import (
    EvidenceVault,
    query_evidence,
    cite_evidence,
    create_evidence_snapshot,
)
from operation_room.mcp.tools.analysis import (
    detect_anomalies,
    build_correlation,
    analyze_crud,
    analyze_network,
    analyze_depth,
    run_full_analysis,
)
from operation_room.mcp.tools.report import (
    create_report_document,
    add_canvas_page,
    add_evidence_block,
    generate_narrative,
    insert_narrative_to_canvas,
    validate_report,
    export_report,
)
from operation_room.mcp.tools.llm import (
    generate_text,
    get_config as get_llm_config,
)
from operation_room.mcp.schemas import MCPToolResult


# =============================================================================
# AGENT STATE MANAGEMENT
# =============================================================================

class AgentPhase(str, Enum):
    """Current phase of the investigation agent."""
    IDLE = "idle"
    INTAKE = "intake"
    CLARIFICATION = "clarification"
    PLANNING = "planning"
    ANALYSIS = "analysis"
    HYPOTHESIS_TESTING = "hypothesis_testing"
    EVIDENCE_GATHERING = "evidence_gathering"
    REPORT_GENERATION = "report_generation"
    REVIEW = "review"
    COMPLETE = "complete"
    ERROR = "error"


class AgentMode(str, Enum):
    """Agent operation mode."""
    AUTONOMOUS = "autonomous"  # Agent decides next steps
    SUPERVISED = "supervised"  # Agent asks before major actions
    MANUAL = "manual"          # Agent only assists, human drives


@dataclass
class AgentConfig:
    """Configuration for the investigation agent."""
    mode: AgentMode = AgentMode.SUPERVISED
    max_hypotheses: int = 50
    max_analysis_depth: int = 5
    confidence_threshold: float = 0.7
    require_human_approval: bool = True
    auto_generate_report: bool = False
    llm_model: str = "gemini-1.5-flash"
    llm_temperature: float = 0.3
    verbose: bool = True


@dataclass
class AgentState:
    """Current state of the investigation agent."""
    # Identity
    agent_id: str = field(default_factory=lambda: f"agent-{uuid.uuid4().hex[:8]}")
    
    # Current context
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    phase: AgentPhase = AgentPhase.IDLE
    
    # Plan tracking
    plan_id: Optional[str] = None
    current_plan_phase: int = 0
    total_plan_phases: int = 0
    
    # Hypothesis tracking
    hypothesis_tree_root: Optional[str] = None
    current_hypothesis_id: Optional[str] = None
    tested_hypotheses: Set[str] = field(default_factory=set)
    confirmed_hypotheses: Set[str] = field(default_factory=set)
    
    # Evidence tracking
    evidence_snapshot_id: Optional[str] = None
    evidence_count: int = 0
    citation_count: int = 0
    
    # Report tracking
    report_doc_id: Optional[str] = None
    
    # Progress
    messages: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


# =============================================================================
# INVESTIGATION AGENT
# =============================================================================

class InvestigationAgent:
    """
    Main investigation agent that orchestrates forensic analysis.
    
    This agent:
    1. Manages investigation lifecycle through MCP tools
    2. Executes analysis phases with hypothesis-driven approach
    3. Accumulates evidence in the vault
    4. Generates reports with proper citations
    
    Usage:
        agent = InvestigationAgent(config)
        await agent.start_investigation(scenario, case_id)
        await agent.run()  # Autonomous or supervised execution
        report = await agent.generate_report()
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize the investigation agent."""
        self.config = config or AgentConfig()
        self.state = AgentState()
        self._llm_client: Optional[Any] = None
        self._callbacks: Dict[str, List[Callable]] = {
            "on_phase_change": [],
            "on_message": [],
            "on_error": [],
            "on_decision_point": [],
            "on_evidence_found": [],
            "on_hypothesis_tested": [],
        }
        
    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================
    
    async def initialize(self) -> bool:
        """Initialize the agent and LLM connection."""
        try:
            # Configure LLM
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if api_key and genai is not None:
                genai.configure(api_key=api_key)
                self._llm_client = genai.GenerativeModel(self.config.llm_model)
                self._log("LLM initialized", {"model": self.config.llm_model})
            elif api_key and genai is None:
                self._log("Gemini SDK not installed - using mock mode", level="warning")
            else:
                self._log("LLM not available - using mock mode", level="warning")
            
            self.state.started_at = datetime.now(timezone.utc)
            return True
            
        except Exception as e:
            self._log(f"Initialization failed: {e}", level="error")
            return False
    
    async def start_investigation(
        self,
        scenario: str,
        case_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MCPToolResult:
        """
        Start a new investigation from a scenario.
        
        Args:
            scenario: Natural language description of the investigation scenario
            case_id: Case identifier
            metadata: Optional metadata (time range, suspects, systems, etc.)
            
        Returns:
            MCPToolResult with investigation details
        """
        self._set_phase(AgentPhase.INTAKE)
        
        # Build investigation parameters
        meta = metadata or {}
        
        # Build objectives from metadata if provided
        objectives = meta.get("objectives", [])
        
        # Map agent mode to investigation mode
        # AgentMode (autonomous/interactive/manual) != Investigation mode (brute_force/focused/hybrid)
        investigation_mode = meta.get("investigation_mode", "focused")
        
        # Start investigation via MCP tool
        result = await start_investigation(
            case_id=case_id,
            scenario=scenario,
            objectives=objectives if objectives else None,
            mode=investigation_mode  # Use investigation mode, not agent mode
        )
        
        # Handle both dict returns and MCPToolResult objects
        if isinstance(result, dict):
            success = result.get("success", True) and "investigation_id" in result
            investigation_id = result.get("investigation_id")
            error = result.get("error")
        else:
            success = result.success
            investigation_id = result.data.get("investigation_id") if result.data else None
            error = result.error
        
        if success:
            self.state.case_id = case_id
            self.state.investigation_id = investigation_id
            self._set_phase(AgentPhase.CLARIFICATION)
            self._log("Investigation started", {
                "investigation_id": self.state.investigation_id,
                "case_id": case_id
            })
            # Wrap dict result as MCPToolResult for consistency
            if isinstance(result, dict):
                from operation_room.mcp.registry import MCPToolResult
                result = MCPToolResult(
                    success=True,
                    tool_name="investigation.start",
                    data=result
                )
        else:
            self._log(f"Failed to start investigation: {error}", level="error")
            self._set_phase(AgentPhase.ERROR)
            if isinstance(result, dict):
                from operation_room.mcp.registry import MCPToolResult
                result = MCPToolResult(
                    success=False,
                    tool_name="investigation.start",
                    error=error
                )
            
        return result
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current agent and investigation status."""
        return {
            "agent_id": self.state.agent_id,
            "phase": self.state.phase.value,
            "case_id": self.state.case_id,
            "investigation_id": self.state.investigation_id,
            "plan_id": self.state.plan_id,
            "current_plan_phase": self.state.current_plan_phase,
            "total_plan_phases": self.state.total_plan_phases,
            "tested_hypotheses": len(self.state.tested_hypotheses),
            "confirmed_hypotheses": len(self.state.confirmed_hypotheses),
            "evidence_count": self.state.evidence_count,
            "citation_count": self.state.citation_count,
            "report_doc_id": self.state.report_doc_id,
            "started_at": self.state.started_at.isoformat() if self.state.started_at else None,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None,
            "errors": len(self.state.errors)
        }
    
    # =========================================================================
    # CLARIFICATION WORKFLOW
    # =========================================================================
    
    async def get_pending_clarifications(self) -> List[Dict[str, Any]]:
        """Get any pending clarification questions."""
        if not self.state.investigation_id:
            return []
            
        result = await list_clarification_questions(self.state.investigation_id)
        if result.success:
            questions = result.data.get("questions", [])
            pending = [q for q in questions if q.get("status") == "pending"]
            return pending
        return []
    
    async def submit_clarification(
        self,
        question_id: str,
        answer_text: str
    ) -> MCPToolResult:
        """Submit answer to a clarification question."""
        result = await answer_clarification(
            investigation_id=self.state.investigation_id,
            question_id=question_id,
            answer=answer_text
        )
        
        if result.success and result.data.get("ready_to_proceed"):
            self._set_phase(AgentPhase.PLANNING)
            
        return result
    
    async def auto_answer_clarifications(
        self,
        answers: Dict[str, str]
    ) -> bool:
        """
        Automatically answer clarification questions from provided answers.
        
        Args:
            answers: Dict mapping question topics/keywords to answers
            
        Returns:
            True if all questions answered and ready to proceed
        """
        pending = await self.get_pending_clarifications()
        
        for question in pending:
            q_id = question.get("question_id")
            q_text = question.get("question", "").lower()
            
            # Find matching answer
            answer = None
            for key, value in answers.items():
                if key.lower() in q_text:
                    answer = value
                    break
            
            if answer:
                await self.submit_clarification(q_id, answer)
            else:
                self._log(f"No answer for question: {q_text[:50]}...", level="warning")
        
        # Check if ready
        pending = await self.get_pending_clarifications()
        return len(pending) == 0
    
    # =========================================================================
    # PLANNING
    # =========================================================================
    
    async def generate_plan(self) -> MCPToolResult:
        """Generate investigation plan from scenario analysis."""
        self._set_phase(AgentPhase.PLANNING)
        
        result = await generate_investigation_plan(self.state.investigation_id)
        
        if result.success:
            self.state.plan_id = result.data.get("plan_id")
            self.state.total_plan_phases = len(result.data.get("phases", []))
            self._log("Plan generated", {
                "plan_id": self.state.plan_id,
                "phases": self.state.total_plan_phases
            })
        else:
            self._log(f"Plan generation failed: {result.error}", level="error")
            
        return result
    
    async def get_plan(self) -> Optional[Dict[str, Any]]:
        """Get current investigation plan."""
        if not self.state.investigation_id:
            return None
            
        result = await get_investigation_plan(self.state.investigation_id)
        if result.success:
            return result.data
        return None
    
    # =========================================================================
    # ANALYSIS EXECUTION
    # =========================================================================
    
    async def run_analysis_phase(
        self,
        phase_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> MCPToolResult:
        """
        Run a specific analysis phase.
        
        Args:
            phase_type: Type of analysis (timeline, anomaly, correlation, etc.)
            parameters: Optional analysis parameters
            
        Returns:
            MCPToolResult with analysis results
        """
        self._set_phase(AgentPhase.ANALYSIS)
        
        params = parameters or {}
        case_id = self.state.case_id
        
        # Map phase type to analysis function
        analysis_map = {
            "timeline": lambda: run_full_analysis(
                case_id=case_id
            ),
            "anomaly": lambda: detect_anomalies(
                case_id=case_id,
                focus_actors=params.get("focus_actors")
            ),
            "correlation": lambda: build_correlation(
                case_id=case_id,
                seed_events=params.get("seed_events")
            ),
            "crud": lambda: analyze_crud(
                case_id=case_id,
                focus_tables=params.get("focus_tables")
            ),
            "network": lambda: analyze_network(
                case_id=case_id,
                focus_ips=params.get("focus_ips")
            ),
            "depth": lambda: analyze_depth(
                case_id=case_id
            ),
        }
        
        if phase_type not in analysis_map:
            return MCPToolResult(
                success=False,
                tool_name="agent.run_analysis",
                error=f"Unknown analysis type: {phase_type}"
            )
        
        result = await analysis_map[phase_type]()
        
        if result.success:
            # Track evidence added
            evidence_added = result.data.get("evidence_vaulted", 0)
            self.state.evidence_count += evidence_added
            
            self._log(f"Analysis complete: {phase_type}", {
                "evidence_added": evidence_added,
                "severity": result.data.get("severity", "unknown")
            })
            
            # Fire callbacks
            await self._fire_callback("on_evidence_found", {
                "phase": phase_type,
                "count": evidence_added
            })
            
        return result
    
    async def run_all_analyses(self) -> Dict[str, MCPToolResult]:
        """
        Run all analysis phases in sequence.
        
        Returns:
            Dict mapping phase names to their results
        """
        phases = ["timeline", "anomaly", "correlation", "crud", "network", "depth"]
        results = {}
        
        for phase in phases:
            self._log(f"Running analysis: {phase}")
            results[phase] = await self.run_analysis_phase(phase)
            
            # Update plan phase status
            if self.state.investigation_id and self.state.plan_id:
                await execute_plan_step(
                    investigation_id=self.state.investigation_id,
                    step_index=self.state.current_plan_phase
                )
            
            self.state.current_plan_phase += 1
        
        self._set_phase(AgentPhase.HYPOTHESIS_TESTING)
        return results
    
    # =========================================================================
    # HYPOTHESIS TESTING
    # =========================================================================
    
    async def generate_hypotheses_for_scenario(self) -> MCPToolResult:
        """Generate hypotheses based on investigation scenario."""
        result = await generate_hypotheses(self.state.investigation_id)
        
        if result.success:
            hypothesis_count = result.data.get("hypothesis_count", 0)
            self._log(f"Generated {hypothesis_count} hypotheses")
            
        return result
    
    async def test_hypothesis_by_id(
        self,
        hypothesis_id: str,
        evidence_ids: Optional[List[str]] = None
    ) -> MCPToolResult:
        """Test a specific hypothesis against evidence."""
        result = await test_hypotheses(
            investigation_id=self.state.investigation_id,
            hypothesis_ids=[hypothesis_id]
        )
        
        if result.success:
            self.state.tested_hypotheses.add(hypothesis_id)
            
            tested = result.data.get("tested", [])
            if tested and tested[0].get("verdict") == "confirmed":
                self.state.confirmed_hypotheses.add(hypothesis_id)
                
            await self._fire_callback("on_hypothesis_tested", {
                "hypothesis_id": hypothesis_id,
                "verdict": tested[0].get("verdict") if tested else "unknown",
                "confidence": tested[0].get("confidence_score", 0) if tested else 0
            })
            
        return result
    
    async def test_all_hypotheses(self) -> Dict[str, MCPToolResult]:
        """Test all generated hypotheses."""
        self._set_phase(AgentPhase.HYPOTHESIS_TESTING)
        
        # Get all hypotheses
        result = await get_hypothesis_tree(self.state.investigation_id)
        if not result.success:
            return {}
            
        hypotheses = result.data.get("hypotheses", [])
        results = {}
        
        for hyp in hypotheses:
            hyp_id = hyp.get("hypothesis_id")
            if hyp_id and hyp.get("verdict") == "untested":
                results[hyp_id] = await self.test_hypothesis_by_id(hyp_id)
                
        return results
    
    # =========================================================================
    # EVIDENCE MANAGEMENT
    # =========================================================================
    
    async def query_vault(
        self,
        evidence_type: Optional[str] = None,
        min_severity: Optional[float] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Query the evidence vault."""
        result = await query_evidence(
            evidence_type=evidence_type,
            min_severity=min_severity,
            limit=limit
        )
        
        if result.success:
            return result.data.get("items", [])
        return []
    
    async def create_snapshot(self) -> Optional[str]:
        """Create a snapshot of current evidence state."""
        result = await create_evidence_snapshot()
        
        if result.success:
            self.state.evidence_snapshot_id = result.data.get("snapshot_id")
            return self.state.evidence_snapshot_id
        return None
    
    # =========================================================================
    # REPORT GENERATION
    # =========================================================================
    
    async def generate_report(
        self,
        title: Optional[str] = None,
        include_sections: Optional[List[str]] = None
    ) -> MCPToolResult:
        """
        Generate investigation report.
        
        This creates a complete report with:
        - Executive summary
        - Timeline narrative
        - Anomaly findings
        - Hypothesis analysis
        - Evidence inventory
        - Recommendations
        
        All evidence values come from the vault, not AI generation.
        """
        self._set_phase(AgentPhase.REPORT_GENERATION)
        
        # Default title
        if not title:
            title = f"Forensic Investigation Report - Case {self.state.case_id}"
        
        # Create document
        doc_result = await create_report_document(
            case_id=self.state.case_id,
            title=title,
            template="investigation"
        )
        
        if not doc_result.success:
            return doc_result
            
        doc_id = doc_result.data.get("doc_id")
        self.state.report_doc_id = doc_id
        
        # Define sections
        sections = include_sections or [
            "executive_summary",
            "case_overview", 
            "timeline_narrative",
            "anomaly_findings",
            "hypothesis_analysis",
            "recommendations",
            "evidence_inventory"
        ]
        
        # Generate each section
        for section_type in sections:
            # Add page
            page_result = await add_canvas_page(
                doc_id=doc_id,
                section_type=section_type
            )
            
            if not page_result.success:
                continue
                
            page_id = page_result.data.get("page_id")
            
            # Build context from evidence
            evidence = await self.query_vault(limit=100)
            context = {
                "case_id": self.state.case_id,
                "investigation_id": self.state.investigation_id,
                "evidence_count": len(evidence),
                "evidence_samples": evidence[:10],
                "tested_hypotheses": len(self.state.tested_hypotheses),
                "confirmed_hypotheses": len(self.state.confirmed_hypotheses),
            }
            
            # Generate narrative
            narrative_result = await generate_narrative(
                section_type=section_type,
                context=context,
                style="technical",
                evidence_ids=[e.get("id") for e in evidence[:5]],
                max_words=500
            )
            
            if narrative_result.success:
                narrative_id = narrative_result.data.get("narrative_id")
                
                # Insert into canvas
                await insert_narrative_to_canvas(
                    doc_id=doc_id,
                    page_id=page_id,
                    narrative_id=narrative_id
                )
                
                # Add evidence blocks for key findings
                for ev in evidence[:3]:
                    await add_evidence_block(
                        doc_id=doc_id,
                        page_id=page_id,
                        evidence_id=ev.get("id"),
                        display_type="finding"
                    )
        
        # Validate report
        validation = await validate_report(doc_id)
        
        self._log("Report generated", {
            "doc_id": doc_id,
            "sections": len(sections),
            "valid": validation.data.get("valid") if validation.success else False
        })
        
        return MCPToolResult(
            success=True,
            tool_name="agent.generate_report",
            data={
                "doc_id": doc_id,
                "title": title,
                "sections": sections,
                "validation": validation.data if validation.success else None
            }
        )
    
    async def export_report(
        self,
        format: str = "pdf"
    ) -> MCPToolResult:
        """Export the generated report."""
        if not self.state.report_doc_id:
            return MCPToolResult(
                success=False,
                tool_name="agent.export_report",
                error="No report generated yet"
            )
            
        return await export_report(
            doc_id=self.state.report_doc_id,
            format=format
        )
    
    # =========================================================================
    # AUTONOMOUS EXECUTION
    # =========================================================================
    
    async def run(
        self,
        clarification_answers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Run the complete investigation workflow.
        
        In supervised mode, this will pause at decision points.
        In autonomous mode, it runs to completion.
        
        Args:
            clarification_answers: Pre-provided answers for clarification questions
            
        Returns:
            Dict with investigation results
        """
        # Initialize
        if not await self.initialize():
            return {"success": False, "error": "Initialization failed"}
        
        results = {
            "success": True,
            "phases_completed": [],
            "evidence_count": 0,
            "hypotheses_tested": 0,
            "report_doc_id": None
        }
        
        try:
            # Phase 1: Handle clarifications
            if self.state.phase == AgentPhase.CLARIFICATION:
                if clarification_answers:
                    await self.auto_answer_clarifications(clarification_answers)
                else:
                    pending = await self.get_pending_clarifications()
                    if pending and self.config.mode == AgentMode.SUPERVISED:
                        return {
                            "success": True,
                            "status": "awaiting_clarification",
                            "pending_questions": pending
                        }
            
            # Phase 2: Generate plan
            if self.state.phase == AgentPhase.CLARIFICATION:
                self._set_phase(AgentPhase.PLANNING)
                
            plan_result = await self.generate_plan()
            if not plan_result.success:
                results["success"] = False
                results["error"] = "Planning failed"
                return results
            results["phases_completed"].append("planning")
            
            # Phase 3: Run analyses
            analysis_results = await self.run_all_analyses()
            results["phases_completed"].append("analysis")
            results["analysis_results"] = {
                k: v.success for k, v in analysis_results.items()
            }
            
            # Phase 4: Generate and test hypotheses
            await self.generate_hypotheses_for_scenario()
            await self.test_all_hypotheses()
            results["phases_completed"].append("hypothesis_testing")
            results["hypotheses_tested"] = len(self.state.tested_hypotheses)
            
            # Phase 5: Create evidence snapshot
            await self.create_snapshot()
            results["evidence_count"] = self.state.evidence_count
            results["phases_completed"].append("evidence_gathering")
            
            # Phase 6: Generate report
            if self.config.auto_generate_report or self.config.mode == AgentMode.AUTONOMOUS:
                report_result = await self.generate_report()
                if report_result.success:
                    results["report_doc_id"] = report_result.data.get("doc_id")
                    results["phases_completed"].append("report_generation")
            
            self._set_phase(AgentPhase.COMPLETE)
            
        except Exception as e:
            self._log(f"Execution error: {e}", level="error")
            self._set_phase(AgentPhase.ERROR)
            results["success"] = False
            results["error"] = str(e)
        
        return results
    
    # =========================================================================
    # CALLBACKS & LOGGING
    # =========================================================================
    
    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for an event."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    async def _fire_callback(self, event: str, data: Any) -> None:
        """Fire registered callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                self._log(f"Callback error for {event}: {e}", level="error")
    
    def _set_phase(self, phase: AgentPhase) -> None:
        """Update agent phase and fire callback."""
        old_phase = self.state.phase
        self.state.phase = phase
        self.state.last_activity = datetime.now(timezone.utc)
        
        asyncio.create_task(self._fire_callback("on_phase_change", {
            "old_phase": old_phase.value,
            "new_phase": phase.value
        }))
    
    def _log(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        level: str = "info"
    ) -> None:
        """Log a message."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "data": data or {}
        }
        
        self.state.messages.append(entry)
        
        if level == "error":
            self.state.errors.append(entry)
        
        if self.config.verbose:
            prefix = "✓" if level == "info" else "⚠" if level == "warning" else "✗"
            print(f"{prefix} [{self.state.phase.value}] {message}")
        
        asyncio.create_task(self._fire_callback("on_message", entry))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

async def create_investigation_agent(
    scenario: str,
    case_id: str,
    config: Optional[AgentConfig] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> InvestigationAgent:
    """
    Factory function to create and initialize an investigation agent.
    
    Args:
        scenario: Investigation scenario description
        case_id: Case identifier
        config: Optional agent configuration
        metadata: Optional investigation metadata
        
    Returns:
        Initialized InvestigationAgent ready to run
    """
    agent = InvestigationAgent(config)
    await agent.initialize()
    await agent.start_investigation(scenario, case_id, metadata)
    return agent
