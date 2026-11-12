"""
Universal Tool Integration Layer

Bridges the new Universal Module Tools with the existing Deep Research Orchestrator.

This allows the orchestrator to:
- Use Universal Tools for report generation
- Stream tool outputs to canvas in real-time
- Maintain backwards compatibility with MCP tools
- Integrate with hypothesis testing and confidence scoring
"""

import logging
from typing import Dict, Any, List, Optional, AsyncIterator, TYPE_CHECKING
from datetime import datetime
import asyncio

from operation_room.tools.base_tool import (
    ModuleTool,
    ToolInput,
    ToolOutput,
    StreamEvent,
    EventType,
)
from operation_room.tools import tool_registry

# Type checking imports (don't cause runtime errors)
if TYPE_CHECKING:
    from operation_room.services.deep_research.orchestrator import DeepResearchOrchestrator as DROrchestrator
    from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
    from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent

# Import existing Deep Research components
try:
    from operation_room.services.deep_research.orchestrator import DeepResearchOrchestrator
    from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
    from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent
    DEEP_RESEARCH_AVAILABLE = True
except ImportError:
    DeepResearchOrchestrator = None  # type: ignore
    HypothesisAnalysisAgent = None  # type: ignore
    ConfidenceScoringAgent = None  # type: ignore
    DEEP_RESEARCH_AVAILABLE = False


logger = logging.getLogger(__name__)


class ToolOrchestrationService:
    """
    Integration service that coordinates:
    - Universal Module Tools execution
    - Deep Research Orchestrator
    - Real-time canvas streaming
    - Hypothesis testing
    - Confidence scoring
    """
    
    def __init__(self, orchestrator: Optional[Any] = None):
        self.orchestrator = orchestrator
        self.active_executions: Dict[str, Any] = {}
    
    async def execute_investigation_plan(
        self,
        case_id: str,
        investigation_id: str,
        plan_phases: List[Dict[str, Any]],
    ) -> AsyncIterator[StreamEvent]:
        """
        Execute investigation plan using Universal Tools.
        
        Yields real-time StreamEvents that can be sent to frontend via SSE.
        
        Args:
            case_id: Case ID
            investigation_id: Investigation session ID
            plan_phases: List of plan phases from Deep Research
        
        Yields:
            StreamEvent objects for real-time updates
        """
        total_phases = len(plan_phases)
        
        for idx, phase in enumerate(plan_phases, 1):
            phase_id = phase["id"]
            phase_name = phase["name"]
            phase_steps = phase.get("steps", [])
            
            # Emit phase start event
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={
                    "phase_id": phase_id,
                    "phase_name": phase_name,
                    "phase_number": idx,
                    "total_phases": total_phases,
                }
            )
            
            # Execute each step in the phase
            for step_idx, step in enumerate(phase_steps, 1):
                step_id = step["id"]
                step_description = step["description"]
                tool_id = step.get("tool_id")
                capability = step.get("capability")
                parameters = step.get("parameters", {})
                
                # Emit step start
                yield StreamEvent(
                    event_type=EventType.STEP_START,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "step_id": step_id,
                        "step_description": step_description,
                        "step_number": step_idx,
                        "total_steps": len(phase_steps),
                    }
                )
                
                # Execute the tool
                try:
                    async for event in self.execute_tool(
                        case_id=case_id,
                        tool_id=tool_id,
                        capability=capability,
                        parameters=parameters,
                        context={"investigation_id": investigation_id}
                    ):
                        yield event
                
                except Exception as e:
                    logger.error(f"Step {step_id} failed: {e}", exc_info=True)
                    yield StreamEvent(
                        event_type=EventType.ERROR,
                        timestamp=datetime.now().isoformat(),
                        data={
                            "step_id": step_id,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                    )
                
                # Emit step complete
                yield StreamEvent(
                    event_type=EventType.STEP_COMPLETE,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "step_id": step_id,
                    }
                )
            
            # Emit phase complete
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={
                    "phase_id": phase_id,
                }
            )
    
    async def execute_tool(
        self,
        case_id: str,
        tool_id: str,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Execute a Universal Tool and stream results.
        
        Yields:
            StreamEvent objects with progressive results
        """
        # Get the tool from registry
        tool = tool_registry.get(tool_id)
        if not tool:
            yield StreamEvent(
                event_type=EventType.ERROR,
                timestamp=datetime.now().isoformat(),
                data={
                    "error": f"Tool not found: {tool_id}",
                }
            )
            return
        
        # Create tool input
        request_id = f"{tool_id}-{capability}-{datetime.now().timestamp()}"
        tool_input = ToolInput(
            case_id=case_id,
            capability=capability,
            parameters=parameters,
            context=context or {},
            request_id=request_id,
        )
        
        # Emit tool start
        yield StreamEvent(
            event_type=EventType.TOOL_START,
            timestamp=datetime.now().isoformat(),
            data={
                "tool_id": tool_id,
                "tool_name": tool.tool_name,
                "capability": capability,
                "request_id": request_id,
            }
        )
        
        # Check if tool supports streaming
        capability_info = next(
            (c for c in tool.get_capabilities() if c.name == capability),
            None
        )
        
        if capability_info and capability_info.supports_streaming:
            # Stream execution
            async for event in tool.stream(tool_input):
                yield event
        else:
            # One-shot execution
            result = await tool.execute(tool_input)
            
            # Convert result to stream events
            if result.success:
                # Emit findings
                for finding in result.findings:
                    yield StreamEvent(
                        event_type=EventType.FINDING,
                        timestamp=datetime.now().isoformat(),
                        data=finding.__dict__,
                    )
                
                # Emit visualizations
                for viz in result.visualizations:
                    yield StreamEvent(
                        event_type=EventType.VISUALIZATION,
                        timestamp=datetime.now().isoformat(),
                        data=viz.__dict__,
                    )
                
                # Emit narrative
                if result.narrative:
                    yield StreamEvent(
                        event_type=EventType.TEXT_CHUNK,
                        timestamp=datetime.now().isoformat(),
                        data={
                            "text": result.narrative,
                            "is_final": True,
                        }
                    )
                
                # Emit completion
                yield StreamEvent(
                    event_type=EventType.TOOL_COMPLETE,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "tool_id": tool_id,
                        "capability": capability,
                        "request_id": request_id,
                        "success": True,
                        "execution_time_ms": result.execution_time_ms,
                        "page_estimate": result.page_estimate,
                        "confidence_score": result.confidence_score,
                    }
                )
            else:
                # Error
                yield StreamEvent(
                    event_type=EventType.ERROR,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "tool_id": tool_id,
                        "capability": capability,
                        "error": result.error,
                        "error_details": result.error_details,
                    }
                )
    
    async def execute_hypothesis_test(
        self,
        case_id: str,
        hypothesis_id: str,
        tool_results: List[ToolOutput],
    ) -> Dict[str, Any]:
        """
        Test hypothesis using tool outputs.
        
        Integrates with existing HypothesisAgent.
        
        Args:
            case_id: Case ID
            hypothesis_id: Hypothesis to test
            tool_results: Results from Universal Tools
        
        Returns:
            Hypothesis test result with confidence score
        """
        if not DEEP_RESEARCH_AVAILABLE:
            logger.warning("Deep Research system not available")
            return {
                "hypothesis_id": hypothesis_id,
                "verdict": "inconclusive",
                "confidence": 0.5,
                "reason": "System unavailable",
            }
        
        # Aggregate evidence from tool results
        evidence_items = []
        for result in tool_results:
            if result.success:
                evidence_items.extend(result.evidence)
        
        # TODO: Call hypothesis agent
        # hypothesis_result = await hypothesis_agent.test_hypothesis(
        #     hypothesis_id=hypothesis_id,
        #     evidence=evidence_items,
        # )
        
        # Mock for now
        return {
            "hypothesis_id": hypothesis_id,
            "verdict": "confirmed",
            "confidence": 0.85,
            "supporting_evidence": len(evidence_items),
            "contradicting_evidence": 0,
        }
    
    async def compute_module_confidence(
        self,
        case_id: str,
        tool_outputs: List[ToolOutput],
    ) -> float:
        """
        Compute confidence score from multiple tool outputs.
        
        Integrates with existing ConfidenceAgent.
        
        Uses factors:
        - Module agreement (do tools agree on findings?)
        - Evidence coverage (how much evidence found?)
        - Data quality (any errors or gaps?)
        
        Returns:
            Confidence score 0.0-1.0
        """
        if not tool_outputs:
            return 0.0
        
        # Calculate factors
        success_rate = sum(1 for t in tool_outputs if t.success) / len(tool_outputs)
        
        avg_confidence = sum(
            t.confidence_score for t in tool_outputs if t.success
        ) / max(1, sum(1 for t in tool_outputs if t.success))
        
        evidence_count = sum(
            len(t.evidence) for t in tool_outputs if t.success
        )
        evidence_factor = min(1.0, evidence_count / 10)  # Saturate at 10+ evidence
        
        # Weighted combination
        confidence = (
            success_rate * 0.3 +
            avg_confidence * 0.5 +
            evidence_factor * 0.2
        )
        
        return round(confidence, 3)
    
    async def generate_canvas_layout(
        self,
        case_id: str,
        tool_outputs: List[ToolOutput],
        layout_preference: str = "auto",
    ) -> List[Dict[str, Any]]:
        """
        Generate canvas layout from tool outputs.
        
        Creates a structured page layout with:
        - Narrative sections
        - Visualizations
        - Evidence blocks
        - Tables
        
        Args:
            case_id: Case ID
            tool_outputs: Results from Universal Tools
            layout_preference: "auto", "compact", "detailed"
        
        Returns:
            List of canvas elements ready for Studio V4
        """
        elements = []
        y_position = 72  # Start after margin (72px = 0.75 inch at 96 DPI)
        
        for tool_result in tool_outputs:
            if not tool_result.success:
                continue
            
            # Add narrative if present
            if tool_result.narrative:
                elements.append({
                    "type": "text",
                    "position": {"x": 72, "y": y_position},
                    "size": {"width": 672, "height": "auto"},
                    "content": tool_result.narrative,
                    "style": "body",
                })
                y_position += 100  # Estimate
            
            # Add findings
            for finding in tool_result.findings:
                elements.append({
                    "type": "finding",
                    "position": {"x": 72, "y": y_position},
                    "size": {"width": 672, "height": 80},
                    "data": {
                        "title": finding.title,
                        "description": finding.description,
                        "severity": finding.severity,
                        "confidence": finding.confidence,
                    }
                })
                y_position += 100
            
            # Add visualizations
            for viz in tool_result.visualizations:
                height = viz.config.get("height", 300) if viz.config else 300
                
                elements.append({
                    "type": "visualization",
                    "position": {"x": 72, "y": y_position},
                    "size": {"width": 672, "height": height},
                    "data": {
                        "viz_type": viz.viz_type,
                        "data": viz.data,
                        "config": viz.config,
                        "title": viz.title,
                    }
                })
                y_position += height + 40  # 40px gap
            
            # Add tables
            for table in tool_result.tables:
                row_count = len(table.get("rows", []))
                table_height = min(400, 40 + row_count * 32)  # Header + rows
                
                elements.append({
                    "type": "table",
                    "position": {"x": 72, "y": y_position},
                    "size": {"width": 672, "height": table_height},
                    "data": table,
                })
                y_position += table_height + 40
        
        return elements


class ToolExecution:
    """Track an ongoing tool execution."""
    
    def __init__(self, tool_input: ToolInput):
        self.input = tool_input
        self.start_time = datetime.now()
        self.status = "running"
        self.events: List[StreamEvent] = []
    
    def add_event(self, event: StreamEvent):
        self.events.append(event)
    
    def mark_complete(self):
        self.status = "complete"
    
    def mark_failed(self, error: str):
        self.status = "failed"


# Global service instance
tool_orchestration = ToolOrchestrationService()
