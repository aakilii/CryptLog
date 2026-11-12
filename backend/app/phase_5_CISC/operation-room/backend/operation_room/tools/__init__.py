"""
Universal Module Tools Framework

This module provides a standardized interface for all forensic analysis
modules to operate as versatile, MCP-like tools that can be:
- Called independently with structured inputs
- Composed by the Report Orchestrator
- Used for chart/visualization generation
- Streamed for real-time canvas updates

Tool Categories:
- Analysis Tools: Timeline, Anomaly, Correlation, Network, CRUD, Depth
- Evidence Tools: Vault, Entity Aliasing
- Generation Tools: Chart Generator, Narrative Writer

Each tool provides:
- get_schema(): JSON schema for inputs/outputs
- get_capabilities(): What the tool can produce
- execute(): Main execution with structured output
- stream(): Generator for streaming updates
- generate_visualization(): Create chart configs
"""

from .base_tool import (
    ModuleTool,
    ToolInput,
    ToolOutput,
    ToolCapability,
    ToolVisualization,
    ToolFinding,
    ToolEvidence,
    ToolRegistry,
    tool_registry,
    ToolCategory,
    VisualizationType,
    FindingSeverity,
    StreamEvent,
    EventType,
)

from .orchestration import (
    ToolOrchestrationService,
    tool_orchestration,
)

# Import tool implementations to auto-register
_tools_available = {}

try:
    from .timeline_tool import TimelineTool
    _tools_available["timeline"] = True
except ImportError:
    _tools_available["timeline"] = False

try:
    from .anomaly_tool import AnomalyTool
    _tools_available["anomaly"] = True
except ImportError:
    _tools_available["anomaly"] = False

try:
    from .correlation_tool import CorrelationTool
    _tools_available["correlation"] = True
except ImportError:
    _tools_available["correlation"] = False

try:
    from .network_tool import NetworkTool
    _tools_available["network"] = True
except ImportError:
    _tools_available["network"] = False

try:
    from .crud_tool import CRUDTool
    _tools_available["crud"] = True
except ImportError:
    _tools_available["crud"] = False

try:
    from .depth_tool import DepthTool
    _tools_available["depth"] = True
except ImportError:
    _tools_available["depth"] = False

try:
    from .vault_tool import VaultTool
    _tools_available["vault"] = True
except ImportError:
    _tools_available["vault"] = False

__all__ = [
    "ModuleTool",
    "ToolInput",
    "ToolOutput",
    "ToolCapability",
    "ToolVisualization",
    "ToolFinding",
    "ToolEvidence",
    "ToolRegistry",
    "tool_registry",
    "ToolCategory",
    "VisualizationType",
    "FindingSeverity",
    "StreamEvent",
    "EventType",
    "ToolOrchestrationService",
    "tool_orchestration",
    # Tool implementations
    "TimelineTool",
    "AnomalyTool",
    "CorrelationTool",
    "NetworkTool",
    "CRUDTool",
    "DepthTool",
    "VaultTool",
    # Availability info
    "_tools_available",
]
