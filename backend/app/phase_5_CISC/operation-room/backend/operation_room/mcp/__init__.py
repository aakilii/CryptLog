"""
MCP (Model Context Protocol) — Tool infrastructure for AI agents.

This package provides the complete MCP infrastructure for the NFLIP
Intelligent Forensic Investigation Agent. It enables AI agents to:

- Discover available analysis tools
- Invoke tools with validated parameters
- Maintain evidence integrity with hashing
- Track all operations via Chain of Custody
- Manage investigation sessions

Package Structure:
    schemas.py      - Pydantic models for all data structures
    registry.py     - Tool registration and discovery
    decorators.py   - Tool definition decorators
    server.py       - MCP server implementation
    tools/          - Individual tool implementations (Phase 2+)

Core Principle:
    "AI DOES NOT GENERATE EVIDENCE — AI REASONS ABOUT EVIDENCE"
    
    All factual data (IPs, MACs, timestamps, user IDs) comes directly
    from logs with cryptographic hash verification. AI generates
    summaries and narratives based on this verified evidence.

Quick Start:
    from operation_room.mcp import mcp_tool, ToolCategory, registry, get_server
    
    # Define a tool
    @mcp_tool(
        name="analysis.timeline.build",
        category=ToolCategory.ANALYSIS,
        description="Build unified timeline from evidence"
    )
    async def build_timeline(case_id: str, ...) -> TimelineResult:
        # Implementation
        ...
    
    # Start server
    server = get_server()
    await server.start()
    
    # Call tool via server
    result = await server.call_tool("analysis.timeline.build", {"case_id": "case-123"})

Integration with FastAPI:
    from fastapi import FastAPI
    from operation_room.mcp import create_mcp_router, MCPServer
    
    app = FastAPI()
    mcp_server = MCPServer()
    app.include_router(create_mcp_router(mcp_server), prefix="/mcp")

Author: NFLIP Development Team
Version: 1.0.0
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

from .schemas import (
    # Enums
    InvestigationStatus,
    PhaseStatus,
    HypothesisVerdict,
    ConfidenceLevel,
    EvidenceType,
    ModuleName,
    TraversalStrategy,
    ClarificationPriority,
    
    # Base Models
    MCPBaseModel,
    HashedModel,
    TimestampedModel,
    
    # Evidence
    SourceReference,
    EvidenceValue,
    EvidenceCard,
    EvidenceInventory,
    
    # Investigation
    TimeRange,
    EntityReference,
    ClarificationQuestion,
    InvestigationObjective,
    InvestigationContext,
    
    # Planning
    PlanStep,
    InvestigationPlan,
    
    # Hypothesis
    EvidenceRequirement,
    Hypothesis,
    HypothesisTree,
    
    # Confidence
    ConfidenceFactor,
    ConfidenceAssessment,
    
    # Module Results
    ModuleExecutionResult,
    TimelineResult,
    AnomalyResult,
    CorrelationResult,
    CRUDResult,
    NetworkResult,
    DepthResult,
    
    # Report
    Citation,
    ReportSection,
    ReportMetadata,
    ReportStructure,
    
    # Tool I/O
    MCPToolResult,
    InvestigationStartInput,
    InvestigationStartOutput,
    
    # Summary
    SummaryCard,
)

# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

from .registry import (
    ToolCategory,
    ToolAccessLevel,
    ToolParameter,
    ToolMetadata,
    ToolExecutionContext,
    ToolExecutionResult,
    RegisteredTool,
    ToolRegistry,
    registry,
    get_registry,
)

# ═══════════════════════════════════════════════════════════════════════════════
# DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

from .decorators import (
    # Core
    mcp_tool,
    
    # Validation
    requires_case,
    requires_investigation,
    validate_params,
    
    # Chain of Custody
    CoCActionType,
    CoCEntry,
    with_coc_logging,
    
    # Evidence
    with_evidence_hash,
    verify_evidence_hash,
    
    # Execution
    with_timeout,
    with_retry,
    
    # Audit
    AuditEntry,
    audit_trail,
    get_audit_trail,
    
    # Composition
    compose_decorators,
    
    # Presets
    analysis_tool,
    evidence_tool,
    hypothesis_tool,
    report_tool,
)

# ═══════════════════════════════════════════════════════════════════════════════
# SERVER
# ═══════════════════════════════════════════════════════════════════════════════

from .server import (
    # Constants
    MCP_PROTOCOL_VERSION,
    MCP_IMPLEMENTATION_NAME,
    MCP_IMPLEMENTATION_VERSION,
    
    # JSON-RPC
    JSONRPCErrorCode,
    JSONRPCRequest,
    JSONRPCError,
    JSONRPCResponse,
    
    # MCP Types
    MCPCapabilities,
    MCPServerInfo,
    MCPInitializeResult,
    MCPTool,
    MCPToolsListResult,
    MCPToolCallResult,
    
    # Session
    MCPSession,
    SessionManager,
    
    # Server
    MCPServer,
    create_mcp_router,
    get_server,
    set_server,
)


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION INFO
# ═══════════════════════════════════════════════════════════════════════════════

__version__ = "1.0.0"
__author__ = "NFLIP Development Team"
__license__ = "Proprietary"


# ═══════════════════════════════════════════════════════════════════════════════
# ALL EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Version
    "__version__",
    
    # Schemas - Enums
    "InvestigationStatus",
    "PhaseStatus",
    "HypothesisVerdict",
    "ConfidenceLevel",
    "EvidenceType",
    "ModuleName",
    "TraversalStrategy",
    "ClarificationPriority",
    
    # Schemas - Base
    "MCPBaseModel",
    "HashedModel",
    "TimestampedModel",
    
    # Schemas - Evidence
    "SourceReference",
    "EvidenceValue",
    "EvidenceCard",
    "EvidenceInventory",
    
    # Schemas - Investigation
    "TimeRange",
    "EntityReference",
    "ClarificationQuestion",
    "InvestigationObjective",
    "InvestigationContext",
    
    # Schemas - Planning
    "PlanStep",
    "InvestigationPlan",
    
    # Schemas - Hypothesis
    "EvidenceRequirement",
    "Hypothesis",
    "HypothesisTree",
    
    # Schemas - Confidence
    "ConfidenceFactor",
    "ConfidenceAssessment",
    
    # Schemas - Results
    "ModuleExecutionResult",
    "TimelineResult",
    "AnomalyResult",
    "CorrelationResult",
    "CRUDResult",
    "NetworkResult",
    "DepthResult",
    
    # Schemas - Report
    "Citation",
    "ReportSection",
    "ReportMetadata",
    "ReportStructure",
    
    # Schemas - Tool I/O
    "MCPToolResult",
    "InvestigationStartInput",
    "InvestigationStartOutput",
    
    # Schemas - Summary
    "SummaryCard",
    
    # Registry
    "ToolCategory",
    "ToolAccessLevel",
    "ToolParameter",
    "ToolMetadata",
    "ToolExecutionContext",
    "ToolExecutionResult",
    "RegisteredTool",
    "ToolRegistry",
    "registry",
    "get_registry",
    
    # Decorators - Core
    "mcp_tool",
    
    # Decorators - Validation
    "requires_case",
    "requires_investigation",
    "validate_params",
    
    # Decorators - CoC
    "CoCActionType",
    "CoCEntry",
    "with_coc_logging",
    
    # Decorators - Evidence
    "with_evidence_hash",
    "verify_evidence_hash",
    
    # Decorators - Execution
    "with_timeout",
    "with_retry",
    
    # Decorators - Audit
    "AuditEntry",
    "audit_trail",
    "get_audit_trail",
    
    # Decorators - Composition
    "compose_decorators",
    
    # Decorators - Presets
    "analysis_tool",
    "evidence_tool",
    "hypothesis_tool",
    "report_tool",
    
    # Server - Constants
    "MCP_PROTOCOL_VERSION",
    "MCP_IMPLEMENTATION_NAME",
    "MCP_IMPLEMENTATION_VERSION",
    
    # Server - JSON-RPC
    "JSONRPCErrorCode",
    "JSONRPCRequest",
    "JSONRPCError",
    "JSONRPCResponse",
    
    # Server - MCP Types
    "MCPCapabilities",
    "MCPServerInfo",
    "MCPInitializeResult",
    "MCPTool",
    "MCPToolsListResult",
    "MCPToolCallResult",
    
    # Server - Session
    "MCPSession",
    "SessionManager",
    
    # Server - Main
    "MCPServer",
    "create_mcp_router",
    "get_server",
    "set_server",
]
