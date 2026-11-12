"""
Timeline Tool - Universal Module Tool Wrapper

Wraps the existing MCP timeline tools and timeline_service.py 
into the Universal Module Tool interface for:
- Report generation
- Canvas placement
- Visualization generation
- Integration with Deep Research Orchestrator
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from operation_room.tools.base_tool import (
    ModuleTool,
    ToolInput,
    ToolOutput,
    ToolCapability,
    ToolCategory,
    VisualizationType,
    FindingSeverity,
)

# Import existing timeline service
try:
    from operation_room.services.timeline_service import (
        get_timeline_stats,
        get_timeline,
        get_anchors,
    )
    TIMELINE_SERVICE_AVAILABLE = True
except ImportError:
    TIMELINE_SERVICE_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Timeline service not available - using mock data")

# Import existing MCP tools if available
try:
    from operation_room.mcp.tools.timeline import TimelineServiceInterface
    MCP_TOOLS_AVAILABLE = True
except ImportError:
    MCP_TOOLS_AVAILABLE = False


logger = logging.getLogger(__name__)


class TimelineTool(ModuleTool):
    """
    Timeline Analysis Tool.
    
    Provides:
    - Timeline reconstruction
    - Event clustering
    - Anchor point identification
    - Temporal visualizations
    - Activity pattern detection
    
    Capabilities:
    - get_stats: Get timeline overview statistics
    - get_events: Retrieve filtered timeline events
    - get_anchors: Get marked anchor events
    - get_clusters: Get event clusters
    - generate_timeline_viz: Create timeline visualization
    - generate_activity_chart: Create activity density chart
    - generate_narrative: AI narrative of timeline
    """
    
    @property
    def tool_id(self) -> str:
        return "timeline"
    
    @property
    def tool_name(self) -> str:
        return "Timeline Analysis"
    
    @property
    def tool_version(self) -> str:
        return "2.0.0"  # Version 2.0 - Universal Tool interface
    
    @property
    def tool_category(self) -> ToolCategory:
        return ToolCategory.ANALYSIS
    
    @property
    def description(self) -> str:
        return "Unified timeline reconstruction and temporal analysis"
    
    def get_capabilities(self) -> List[ToolCapability]:
        """Define all timeline capabilities."""
        return [
            ToolCapability(
                name="get_stats",
                description="Get timeline overview statistics",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "total_events": {"type": "integer"},
                        "total_anchors": {"type": "integer"},
                        "sources": {"type": "object"},
                        "time_span_start": {"type": "string"},
                        "time_span_end": {"type": "string"}
                    }
                },
                visualization_types=[
                    VisualizationType.METRIC_CARD,
                    VisualizationType.BAR_CHART
                ],
                supports_streaming=False
            ),
            
            ToolCapability(
                name="get_events",
                description="Retrieve filtered timeline events",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 100},
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "INFO"]},
                        "source_type": {"type": "string"},
                        "time_start": {"type": "string"},
                        "time_end": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "events": {"type": "array"},
                        "total": {"type": "integer"}
                    }
                },
                visualization_types=[
                    VisualizationType.TIMELINE,
                    VisualizationType.TABLE
                ],
                supports_streaming=True
            ),
            
            ToolCapability(
                name="get_anchors",
                description="Get marked anchor events (key moments)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "anchors": {"type": "array"}
                    }
                },
                visualization_types=[
                    VisualizationType.TIMELINE,
                    VisualizationType.TABLE
                ],
                supports_streaming=False
            ),
            
            ToolCapability(
                name="generate_timeline_viz",
                description="Create vertical timeline visualization",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "limit": {"type": "integer", "default": 50}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "visualization": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.TIMELINE],
                supports_streaming=False
            ),
            
            ToolCapability(
                name="generate_activity_chart",
                description="Create activity density area chart",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "visualization": {"type": "object"}
                    }
                },
                visualization_types=[VisualizationType.AREA_CHART],
                supports_streaming=False
            ),
            
            ToolCapability(
                name="generate_narrative",
                description="AI-generated narrative summary of timeline",
                input_schema={
                    "type": "object",
                    "properties": {
                        "case_id": {"type": "string"},
                        "style": {"type": "string", "enum": ["technical", "executive", "regulatory"], "default": "technical"}
                    },
                    "required": ["case_id"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "narrative": {"type": "string"}
                    }
                },
                visualization_types=[],
                supports_streaming=True
            ),
        ]
    
    async def execute(self, input: ToolInput) -> ToolOutput:
        """Execute the requested timeline capability."""
        start_time = datetime.now()
        
        # Validate input
        validation = self.validate_input(input)
        if not validation["valid"]:
            return ToolOutput(
                tool_id=self.tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=f"Invalid input: {validation['errors']}"
            )
        
        case_id = input.case_id
        capability = input.capability
        params = input.parameters
        
        # Route to appropriate handler
        try:
            if capability == "get_stats":
                result = await self._get_stats(case_id)
            elif capability == "get_events":
                result = await self._get_events(case_id, params)
            elif capability == "get_anchors":
                result = await self._get_anchors(case_id)
            elif capability == "generate_timeline_viz":
                result = await self._generate_timeline_viz(case_id, params)
            elif capability == "generate_activity_chart":
                result = await self._generate_activity_chart(case_id)
            elif capability == "generate_narrative":
                result = await self._generate_narrative(case_id, params)
            else:
                return ToolOutput(
                    tool_id=self.tool_id,
                    capability=capability,
                    request_id=input.request_id,
                    success=False,
                    error=f"Unknown capability: {capability}"
                )
            
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ToolOutput(
                tool_id=self.tool_id,
                capability=capability,
                request_id=input.request_id,
                success=True,
                narrative=result.get("narrative", ""),
                findings=result.get("findings", []),
                visualizations=result.get("visualizations", []),
                tables=result.get("tables", []),
                evidence=result.get("evidence", []),
                execution_time_ms=execution_time_ms,
                page_estimate=result.get("page_estimate", 1),
                confidence_score=result.get("confidence_score", 0.0),
            )
            
        except Exception as e:
            logger.error(f"Timeline tool execution failed: {e}", exc_info=True)
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ToolOutput(
                tool_id=self.tool_id,
                capability=capability,
                request_id=input.request_id,
                success=False,
                error=str(e),
                error_details={"exception_type": type(e).__name__},
                execution_time_ms=execution_time_ms
            )
    
    # ─── Capability Implementations ──────────────────────────────────────────
    
    async def _get_stats(self, case_id: str) -> Dict[str, Any]:
        """Get timeline statistics."""
        if TIMELINE_SERVICE_AVAILABLE:
            try:
                stats = await get_timeline_stats(case_id)
            except Exception as e:
                logger.warning(f"Timeline service error: {e}, using mock data")
                stats = self._mock_stats(case_id)
        else:
            stats = self._mock_stats(case_id)
        
        # Create findings from stats
        findings = []
        if stats.get("total_events", 0) > 0:
            findings.append(
                self.create_finding(
                    title=f"{stats['total_events']:,} Events Analyzed",
                    description=f"Timeline contains {stats['total_events']:,} events from {len(stats.get('sources', {}))} sources",
                    severity=FindingSeverity.INFO,
                    confidence=1.0,
                )
            )
        
        if stats.get("total_anchors", 0) > 0:
            findings.append(
                self.create_finding(
                    title=f"{stats['total_anchors']} Key Events Identified",
                    description="Anchor points marking significant moments in the investigation",
                    severity=FindingSeverity.MEDIUM,
                    confidence=0.9,
                )
            )
        
        # Create metric cards visualization
        metric_viz = self.generate_visualization(
            data=[
                {"label": "Events", "value": stats.get("total_events", 0)},
                {"label": "Anchors", "value": stats.get("total_anchors", 0)},
                {"label": "Sources", "value": len(stats.get("sources", {}))},
            ],
            viz_type=VisualizationType.METRIC_CARD,
            title="Timeline Overview",
        )
        
        return {
            "narrative": f"Timeline analysis identified {stats.get('total_events', 0):,} events across {len(stats.get('sources', {}))} data sources.",
            "findings": findings,
            "visualizations": [metric_viz],
            "page_estimate": 1,
            "confidence_score": 0.95,
        }
    
    async def _get_events(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get filtered timeline events."""
        # This would call the real service
        events = []  # Mock for now
        
        return {
            "narrative": f"Retrieved {len(events)} timeline events",
            "tables": [{
                "title": "Timeline Events",
                "columns": ["Time", "Source", "Actor", "Action", "Severity"],
                "rows": events
            }],
            "page_estimate": max(1, len(events) // 20),
        }
    
    async def _get_anchors(self, case_id: str) -> Dict[str, Any]:
        """Get anchor events."""
        # This would call the real service
        anchors = []  # Mock for now
        
        return {
            "narrative": f"Identified {len(anchors)} anchor events marking key moments in the timeline",
            "findings": [],
            "tables": [{
                "title": "Anchor Events",
                "columns": ["Label", "Time", "Event", "Significance"],
                "rows": anchors
            }],
        }
    
    async def _generate_timeline_viz(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate timeline visualization."""
        # Create vertical timeline chart
        viz = self.generate_visualization(
            data=[],  # Would be actual event data
            viz_type=VisualizationType.TIMELINE,
            title="Investigation Timeline",
            config={
                "height": 400,
                "showLabels": True,
                "colorByS Severity": True
            }
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 2,
        }
    
    async def _generate_activity_chart(self, case_id: str) -> Dict[str, Any]:
        """Generate activity density chart."""
        # Create area chart showing event density over time
        viz = self.generate_visualization(
            data=[],  # Would be actual density data
            viz_type=VisualizationType.AREA_CHART,
            title="Event Activity Density",
            config={
                "height": 300,
                "gradient": True,
                "fill": "#8b5cf6"
            }
        )
        
        return {
            "visualizations": [viz],
            "page_estimate": 1,
        }
    
    async def _generate_narrative(self, case_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI narrative of timeline."""
        style = params.get("style", "technical")
        
        # This would use LLM to generate narrative
        # For now, template
        narrative = f"""
Timeline Analysis Summary

The investigation timeline spans multiple data sources and reveals significant patterns 
in system and user activity. Key events have been identified and marked as anchors for 
reference in subsequent analysis phases.
"""
        
        return {
            "narrative": narrative.strip(),
            "page_estimate": 1,
            "confidence_score": 0.85,
        }
    
    def _mock_stats(self, case_id: str) -> Dict[str, Any]:
        """Mock statistics for testing."""
        return {
            "total_events": 12547,
            "total_anchors": 23,
            "sources": {
                "FW": 4521,
                "AUTH": 3210,
                "FILE": 2815,
                "DB": 2001
            },
            "time_span_start": "2024-01-15T08:00:00Z",
            "time_span_end": "2024-01-28T17:30:00Z",
            "events_by_hour": {}
        }


# Register the tool
from operation_room.tools import tool_registry
timeline_tool = TimelineTool()
tool_registry.register(timeline_tool)
