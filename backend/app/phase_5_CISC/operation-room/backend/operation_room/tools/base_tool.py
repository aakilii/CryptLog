"""
Base Tool Framework for Universal Modules

Provides the abstract base class and data structures for creating
versatile, MCP-like tools from existing forensic analysis modules.

Design Principles:
1. Structured I/O: All inputs/outputs follow JSON schemas
2. Composable: Tools can be chained by orchestrators
3. Streamable: Support real-time updates for canvas rendering
4. Self-describing: Tools expose their capabilities and schemas
5. Evidence-linked: Outputs include evidence hashes for integrity
"""

import json
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import (
    TypedDict, Optional, Any, Dict, List, 
    Literal, Generator, Union, TypeVar, Generic
)
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class ToolCategory(str, Enum):
    """Categories of tools available."""
    ANALYSIS = "analysis"       # Timeline, Anomaly, etc.
    EVIDENCE = "evidence"       # Vault, Entity Aliasing
    GENERATION = "generation"   # Charts, Narratives
    UTILITY = "utility"         # Helpers, formatters


class VisualizationType(str, Enum):
    """Types of visualizations tools can generate."""
    AREA_CHART = "area-chart"
    BAR_CHART = "bar-chart"
    LINE_CHART = "line-chart"
    PIE_CHART = "pie-chart"
    RADAR_CHART = "radar-chart"
    SCATTER_CHART = "scatter-chart"
    HEATMAP = "heatmap"
    TIMELINE = "timeline"
    NETWORK_GRAPH = "network-graph"
    TABLE = "table"
    METRIC_CARD = "metric-card"
    SHAP_EXPLANATION = "shap-explanation"
    SANKEY = "sankey"


class FindingSeverity(str, Enum):
    """Severity levels for findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EventType(str, Enum):
    """Types of streaming events."""
    # Tool lifecycle
    TOOL_START = "tool_start"
    TOOL_COMPLETE = "tool_complete"
    
    # Progress
    PROGRESS = "progress"
    
    # Content
    TEXT_CHUNK = "text_chunk"
    FINDING = "finding"
    VISUALIZATION = "visualization"
    TABLE = "table"
    EVIDENCE = "evidence"
    
    # Investigation flow
    PHASE_START = "phase_start"
    PHASE_COMPLETE = "phase_complete"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    
    # Errors
    ERROR = "error"


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolCapability:
    """Describes a capability of a tool."""
    name: str                           # e.g., "get_events", "generate_chart"
    description: str                    # What this capability does
    input_schema: Dict[str, Any]        # JSON Schema for inputs
    output_schema: Dict[str, Any]       # JSON Schema for outputs
    visualization_types: List[VisualizationType] = field(default_factory=list)
    supports_streaming: bool = False


@dataclass
class ToolInput:
    """Standardized input for tool execution."""
    case_id: str
    capability: str                     # Which capability to invoke
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "capability": self.capability,
            "parameters": self.parameters,
            "context": self.context,
            "request_id": self.request_id,
        }


@dataclass
class ToolFinding:
    """A finding/insight produced by a tool."""
    finding_id: str
    title: str
    description: str
    severity: FindingSeverity
    confidence: float                   # 0.0 - 1.0
    evidence_refs: List[str] = field(default_factory=list)  # SHA-256 hashes
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence_refs": self.evidence_refs,
            "metadata": self.metadata,
        }


@dataclass
class ToolEvidence:
    """Evidence item referenced by a tool output."""
    evidence_id: str
    evidence_type: str                  # file, log, network, etc.
    description: str
    hash_value: str                     # SHA-256
    source: str                         # Where this evidence came from
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "description": self.description,
            "hash_value": self.hash_value,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ToolVisualization:
    """
    Chart/visualization configuration for canvas rendering.
    
    Compatible with Recharts (frontend) rendering.
    """
    viz_id: str
    viz_type: VisualizationType
    title: str
    description: str
    data: List[Dict[str, Any]]          # Chart data points
    config: Dict[str, Any] = field(default_factory=dict)  # Recharts config
    width: int = 672                    # Default full-width
    height: int = 300                   # Default height
    evidence_refs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "viz_id": self.viz_id,
            "viz_type": self.viz_type.value,
            "title": self.title,
            "description": self.description,
            "data": self.data,
            "config": self.config,
            "width": self.width,
            "height": self.height,
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class ToolOutput:
    """Standardized output from tool execution."""
    tool_id: str
    capability: str
    request_id: str
    success: bool
    
    # Core outputs
    narrative: str = ""                 # AI-generated summary text
    findings: List[ToolFinding] = field(default_factory=list)
    visualizations: List[ToolVisualization] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[ToolEvidence] = field(default_factory=list)
    
    # Metadata
    execution_time_ms: int = 0
    page_estimate: int = 1              # Estimated pages needed
    confidence_score: float = 0.0       # Overall confidence
    
    # Error handling
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    # Integrity
    output_hash: str = ""
    
    def __post_init__(self):
        if not self.output_hash:
            self.output_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of output for integrity."""
        content = {
            "narrative": self.narrative,
            "findings": [f.to_dict() for f in self.findings],
            "visualizations": [v.to_dict() for v in self.visualizations],
            "tables": self.tables,
        }
        content_str = json.dumps(content, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(content_str.encode()).hexdigest()}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "capability": self.capability,
            "request_id": self.request_id,
            "success": self.success,
            "narrative": self.narrative,
            "findings": [f.to_dict() for f in self.findings],
            "visualizations": [v.to_dict() for v in self.visualizations],
            "tables": self.tables,
            "evidence": [e.to_dict() for e in self.evidence],
            "execution_time_ms": self.execution_time_ms,
            "page_estimate": self.page_estimate,
            "confidence_score": self.confidence_score,
            "error": self.error,
            "error_details": self.error_details,
            "output_hash": self.output_hash,
        }


@dataclass
class StreamEvent:
    """Event emitted during streaming execution."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        event_name = self.event_type.value if isinstance(self.event_type, EventType) else self.event_type
        return f"event: {event_name}\ndata: {json.dumps(self.data)}\n\n"


# ═══════════════════════════════════════════════════════════════════════════════
# BASE TOOL CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ModuleTool(ABC):
    """
    Abstract base class for universal module tools.
    
    All forensic analysis modules should inherit from this class
    to provide a standardized interface for:
    - Schema discovery
    - Capability enumeration
    - Structured execution
    - Streaming updates
    - Visualization generation
    
    Example Implementation:
    
        class TimelineTool(ModuleTool):
            @property
            def tool_id(self) -> str:
                return "timeline"
            
            @property
            def tool_name(self) -> str:
                return "Timeline Analysis"
            
            def get_capabilities(self) -> List[ToolCapability]:
                return [
                    ToolCapability(
                        name="get_events",
                        description="Retrieve timeline events",
                        input_schema={"type": "object", ...},
                        output_schema={"type": "array", ...},
                    ),
                    ...
                ]
            
            async def execute(self, input: ToolInput) -> ToolOutput:
                # Implementation
                ...
    """
    
    def __init__(self):
        self._logger = logging.getLogger(f"tool.{self.tool_id}")
    
    # ─── Abstract Properties ─────────────────────────────────────────────────
    
    @property
    @abstractmethod
    def tool_id(self) -> str:
        """Unique identifier for this tool."""
        ...
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Human-readable name."""
        ...
    
    @property
    def tool_version(self) -> str:
        """Semantic version."""
        return "1.0.0"
    
    @property
    def tool_category(self) -> ToolCategory:
        """Category of this tool."""
        return ToolCategory.ANALYSIS
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description of tool capabilities."""
        ...
    
    # ─── Abstract Methods ────────────────────────────────────────────────────
    
    @abstractmethod
    def get_capabilities(self) -> List[ToolCapability]:
        """
        Return list of capabilities this tool provides.
        
        Each capability represents a specific function the tool can perform.
        """
        ...
    
    @abstractmethod
    async def execute(self, input: ToolInput) -> ToolOutput:
        """
        Execute the tool with given input.
        
        Args:
            input: Structured input with case_id, capability, and parameters
            
        Returns:
            ToolOutput with findings, visualizations, and narrative
        """
        ...
    
    # ─── Optional Methods (can be overridden) ────────────────────────────────
    
    async def stream(self, input: ToolInput) -> Generator[StreamEvent, None, None]:
        """
        Stream execution results for real-time updates.
        
        Override this method to provide streaming support.
        Default implementation wraps execute() in single event.
        """
        yield StreamEvent(
            event_type="start",
            data={"tool_id": self.tool_id, "capability": input.capability}
        )
        
        output = await self.execute(input)
        
        yield StreamEvent(
            event_type="complete",
            data=output.to_dict()
        )
    
    def generate_visualization(
        self,
        data: List[Dict[str, Any]],
        viz_type: VisualizationType,
        title: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> ToolVisualization:
        """
        Generate a visualization configuration.
        
        Override for custom visualization logic.
        """
        return ToolVisualization(
            viz_id=f"{self.tool_id}-viz-{uuid.uuid4().hex[:8]}",
            viz_type=viz_type,
            title=title,
            description=f"Generated by {self.tool_name}",
            data=data,
            config=config or {},
        )
    
    def get_narrative_prompt(self, capability: str, data: Dict[str, Any]) -> str:
        """
        Get LLM prompt for generating narrative text.
        
        Override to customize narrative generation.
        """
        return f"""
You are a forensic analyst writing a report section for {self.tool_name}.

Based on the following data, write a clear, professional narrative:

{json.dumps(data, indent=2, default=str)}

Guidelines:
- Be concise but thorough
- Use professional forensic language
- Reference specific data points
- Highlight critical findings
- Maintain objectivity
"""
    
    # ─── Utility Methods ─────────────────────────────────────────────────────
    
    def get_schema(self) -> Dict[str, Any]:
        """Get complete JSON schema for this tool."""
        capabilities = self.get_capabilities()
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "version": self.tool_version,
            "category": self.tool_category.value,
            "description": self.description,
            "capabilities": [
                {
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                    "output_schema": cap.output_schema,
                    "visualization_types": [v.value for v in cap.visualization_types],
                    "supports_streaming": cap.supports_streaming,
                }
                for cap in capabilities
            ],
        }
    
    def get_capability(self, name: str) -> Optional[ToolCapability]:
        """Get a specific capability by name."""
        for cap in self.get_capabilities():
            if cap.name == name:
                return cap
        return None
    
    def supports_capability(self, name: str) -> bool:
        """Check if this tool supports a capability."""
        return self.get_capability(name) is not None
    
    def supports_visualization(self, viz_type: VisualizationType) -> bool:
        """Check if this tool can generate a visualization type."""
        for cap in self.get_capabilities():
            if viz_type in cap.visualization_types:
                return True
        return False
    
    def validate_input(self, input: ToolInput) -> Dict[str, Any]:
        """
        Validate input against capability schema.
        
        Returns: {"valid": bool, "errors": list[str]}
        """
        capability = self.get_capability(input.capability)
        if not capability:
            return {
                "valid": False,
                "errors": [f"Unknown capability: {input.capability}"]
            }
        
        # Basic validation - can be extended with jsonschema
        if not input.case_id:
            return {
                "valid": False,
                "errors": ["case_id is required"]
            }
        
        return {"valid": True, "errors": []}
    
    def create_finding(
        self,
        title: str,
        description: str,
        severity: FindingSeverity,
        confidence: float,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ToolFinding:
        """Helper to create a ToolFinding."""
        return ToolFinding(
            finding_id=f"{self.tool_id}-finding-{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            severity=severity,
            confidence=confidence,
            evidence_refs=evidence_refs or [],
            metadata=metadata or {},
        )
    
    def create_evidence(
        self,
        evidence_type: str,
        description: str,
        content: Any,
        source: str,
        timestamp: Optional[str] = None,
    ) -> ToolEvidence:
        """Helper to create a ToolEvidence with computed hash."""
        content_str = json.dumps(content, sort_keys=True, default=str)
        hash_value = f"sha256:{hashlib.sha256(content_str.encode()).hexdigest()}"
        
        return ToolEvidence(
            evidence_id=f"{self.tool_id}-evidence-{uuid.uuid4().hex[:8]}",
            evidence_type=evidence_type,
            description=description,
            hash_value=hash_value,
            source=source,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        )
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.tool_id}>"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    Central registry for all available tools.
    
    Provides:
    - Tool registration and discovery
    - Schema aggregation
    - Capability search
    """
    
    _instance = None
    _tools: Dict[str, ModuleTool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance
    
    def register(self, tool: ModuleTool) -> None:
        """Register a tool instance."""
        self._tools[tool.tool_id] = tool
        logger.info(f"Registered tool: {tool.tool_id} ({tool.tool_name})")
    
    def unregister(self, tool_id: str) -> None:
        """Unregister a tool."""
        if tool_id in self._tools:
            del self._tools[tool_id]
            logger.info(f"Unregistered tool: {tool_id}")
    
    def get(self, tool_id: str) -> Optional[ModuleTool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)
    
    def get_all(self) -> List[ModuleTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_by_category(self, category: ToolCategory) -> List[ModuleTool]:
        """Get tools by category."""
        return [t for t in self._tools.values() if t.tool_category == category]
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools with their schemas."""
        return [tool.get_schema() for tool in self._tools.values()]
    
    def find_by_capability(self, capability_name: str) -> List[ModuleTool]:
        """Find tools that support a specific capability."""
        return [
            tool for tool in self._tools.values()
            if tool.supports_capability(capability_name)
        ]
    
    def find_by_visualization(self, viz_type: VisualizationType) -> List[ModuleTool]:
        """Find tools that can generate a specific visualization type."""
        return [
            tool for tool in self._tools.values()
            if tool.supports_visualization(viz_type)
        ]
    
    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        """Get aggregated list of all capabilities across tools."""
        capabilities = []
        for tool in self._tools.values():
            for cap in tool.get_capabilities():
                capabilities.append({
                    "tool_id": tool.tool_id,
                    "tool_name": tool.tool_name,
                    "capability": cap.name,
                    "description": cap.description,
                    "visualization_types": [v.value for v in cap.visualization_types],
                    "supports_streaming": cap.supports_streaming,
                })
        return capabilities
    
    async def execute(self, tool_id: str, input: ToolInput) -> ToolOutput:
        """Execute a tool by ID."""
        tool = self.get(tool_id)
        if not tool:
            return ToolOutput(
                tool_id=tool_id,
                capability=input.capability,
                request_id=input.request_id,
                success=False,
                error=f"Tool not found: {tool_id}",
            )
        
        return await tool.execute(input)


# Singleton instance
tool_registry = ToolRegistry()
