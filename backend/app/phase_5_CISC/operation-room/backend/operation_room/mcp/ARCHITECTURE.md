# MCP Tool Infrastructure — Architecture Documentation

## Overview

The MCP (Model Context Protocol) infrastructure provides the foundation for the NFLIP Intelligent Forensic Investigation Agent. It enables AI agents to discover, invoke, and compose forensic analysis tools while maintaining evidence integrity through cryptographic hashing and Chain of Custody logging.

## Core Principle

```
┌─────────────────────────────────────────────────────────────────────┐
│   "AI DOES NOT GENERATE EVIDENCE — AI REASONS ABOUT EVIDENCE"       │
│                                                                      │
│   ✓ Every IP, MAC, timestamp comes FROM the logs                    │
│   ✓ AI generates SUMMARIES and NARRATIVES, not facts                │
│   ✓ Confidence scores are COMPUTED from module agreement            │
│   ✓ All evidence is TRACEABLE with SHA-256 hash verification        │
└─────────────────────────────────────────────────────────────────────┘
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INVESTIGATION AGENT (LLM)                         │
│               Claude/Gemini with ReAct Framework                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ JSON-RPC 2.0
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP SERVER                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Session Manager         │  Request Handler                  │    │
│  │  - Create/Close sessions │  - Parse JSON-RPC                 │    │
│  │  - Track investigation   │  - Route to handlers              │    │
│  │  - Timeout management    │  - Error handling                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       TOOL REGISTRY                                  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  Tool Discovery      │  Schema Generation  │  Invocation      │  │
│  │  - By category       │  - MCP format       │  - Validation    │  │
│  │  - By tag            │  - JSON Schema      │  - Execution     │  │
│  │  - By name           │  - Parameter types  │  - Stats         │  │
│  └───────────────────────────────────────────────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  ANALYSIS TOOLS │ │  EVIDENCE TOOLS │ │  REPORT TOOLS   │
│  - timeline.*   │ │  - query        │ │  - canvas.*     │
│  - anomaly.*    │ │  - snapshot     │ │  - narrative.*  │
│  - correlation.*│ │  - verify       │ │  - export.*     │
│  - crud.*       │ │  - card_create  │ │  - citation.*   │
│  - network.*    │ │                 │ │                 │
│  - depth.*      │ │                 │ │                 │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CHAIN OF CUSTODY                                  │
│  - Every tool call logged                                            │
│  - Parameters hashed (RFC 8785)                                      │
│  - Results hashed for verification                                   │
│  - Append-only audit trail                                           │
└─────────────────────────────────────────────────────────────────────┘
```

## Package Structure

```
app/mcp/
├── __init__.py          # Package exports (100+ symbols)
├── schemas.py           # Pydantic models (~1,000 lines)
│   ├── Enums            # Status, verdict, confidence levels
│   ├── Evidence         # SourceReference, EvidenceValue, EvidenceCard
│   ├── Investigation    # Context, objectives, clarifications
│   ├── Planning         # Steps, phases, dependencies
│   ├── Hypothesis       # ACH framework, verdicts
│   ├── Confidence       # ODNI ICD 203 scoring
│   └── Results          # Module-specific result types
│
├── registry.py          # Tool registration (~600 lines)
│   ├── ToolParameter    # Parameter metadata
│   ├── ToolMetadata     # Tool metadata
│   ├── RegisteredTool   # Wrapper with validation
│   └── ToolRegistry     # Singleton registry
│
├── decorators.py        # Tool decorators (~800 lines)
│   ├── @mcp_tool        # Core registration
│   ├── @requires_case   # Validation
│   ├── @with_coc_logging# Chain of custody
│   ├── @with_evidence_hash # Integrity
│   ├── @with_timeout    # Execution control
│   ├── @with_retry      # Resilience
│   └── @audit_trail     # Audit logging
│
├── server.py            # MCP server (~900 lines)
│   ├── JSONRPCRequest   # Protocol types
│   ├── MCPSession       # Session state
│   ├── SessionManager   # Session lifecycle
│   └── MCPServer        # Main server
│
├── tools/               # Tool implementations (Phase 2+)
│   └── __init__.py      # Will contain all tools
│
└── tests/
    ├── __init__.py
    └── test_mcp.py      # Comprehensive tests
```

## Key Components

### 1. Schemas (`schemas.py`)

Pydantic models for all MCP data structures with automatic hash computation:

```python
class EvidenceValue(HashedModel):
    """ACTUAL value from logs, NEVER AI-generated."""
    evidence_id: str
    evidence_type: EvidenceType
    field_name: str           # e.g., "src_ip"
    value: Any                # e.g., "192.168.1.100"
    source: SourceReference   # Traceable to log row
    
    @computed_field
    def content_hash(self) -> str:
        # SHA-256 of canonical JSON (RFC 8785)
        return f"sha256:{hash}"
```

### 2. Registry (`registry.py`)

Singleton registry for tool management:

```python
# Register a tool
@registry.tool(
    name="analysis.timeline.build",
    category=ToolCategory.ANALYSIS,
    description="Build unified timeline"
)
async def build_timeline(case_id: str, ...) -> TimelineResult:
    ...

# Discover tools
tools = registry.list_tools(category=ToolCategory.ANALYSIS)

# Invoke tool
result = await registry.invoke("analysis.timeline.build", params, context)
```

### 3. Decorators (`decorators.py`)

Composable decorators for tool enhancement:

```python
@analysis_tool(
    name="analysis.timeline.build",
    description="Build unified timeline"
)
# Automatically includes:
#   - @mcp_tool registration
#   - @with_coc_logging
#   - @with_evidence_hash
#   - @audit_trail
async def build_timeline(...):
    ...
```

### 4. Server (`server.py`)

JSON-RPC 2.0 compliant MCP server:

```python
server = MCPServer()
await server.start()

# Handle request
response = await server.handle_request(request_json, session_id)

# Or use with FastAPI
router = create_mcp_router(server)
app.include_router(router, prefix="/mcp")
```

## Protocol Flow

### Tool Discovery

```
Client                          Server
  |                               |
  |--- tools/list --------------->|
  |                               |
  |<-- {tools: [                  |
  |       {name: "timeline.build",|
  |        inputSchema: {...}}    |
  |     ]}                        |
  |                               |
```

### Tool Invocation

```
Client                          Server
  |                               |
  |--- tools/call --------------->|
  |    {name: "timeline.build",   |
  |     arguments: {case_id: X}}  |
  |                               |
  |                   ┌───────────┤
  |                   │ Validate  │
  |                   │ Execute   │
  |                   │ Hash      │
  |                   │ Log CoC   │
  |                   └───────────┤
  |                               |
  |<-- {content: [...],           |
  |     evidence_hash: "sha256:..."|
  |    }                          |
  |                               |
```

## Confidence Scoring (ODNI ICD 203)

```
Level        │ Probability │ Interpretation
─────────────┼─────────────┼─────────────────────────────────
Very High    │ ≥90%        │ Near certain, multiple sources
High         │ 75-90%      │ Strong evidence, few gaps
Moderate     │ 50-75%      │ Mixed evidence, some gaps
Low          │ 25-50%      │ Limited evidence, significant gaps
Very Low     │ <25%        │ Speculative, contradictory
```

Computed from 6 factors:
1. **Evidence Coverage** - How complete is the evidence?
2. **Module Agreement** - Do different modules agree?
3. **Temporal Consistency** - Is the timeline coherent?
4. **Cross Validation** - External corroboration?
5. **Pattern Match** - Matches known attack patterns?
6. **Research Alignment** - Aligns with methodologies?

## Evidence Integrity

Every piece of evidence has:

1. **Source Reference** - Pointer to original log row
2. **Content Hash** - SHA-256 of canonical JSON
3. **CoC Event** - Audit trail entry
4. **Evidence Card** - Immutable snapshot

```python
# Verify evidence hasn't been tampered
match, computed = verify_evidence_hash(evidence, expected_hash)
assert match, "Evidence integrity violated!"
```

## Next Steps (Phase 2+)

Phase 2: Investigation Control Tools
- `investigation.start`
- `investigation.clarify`
- `investigation.plan_update`

Phase 3: Analysis Tool Wrappers
- `analysis.timeline.*`
- `analysis.anomaly.*`
- `analysis.correlation.*`
- `analysis.crud.*`
- `analysis.network.*`
- `analysis.depth.*`

Phase 4: Evidence & Hypothesis Tools
- `evidence.query`
- `evidence.snapshot`
- `hypothesis.create`
- `hypothesis.test`
- `confidence.compute`

Phase 5: Report Generation Tools
- `report.canvas.*`
- `report.narrative.*`
- `report.export.*`

## Testing

Run tests:
```bash
cd operation-room/backend
pytest app/mcp/tests/test_mcp.py -v
```

Quick verification:
```python
from app.mcp import MCPServer, registry
server = MCPServer()
print(f"Tools registered: {len(registry.list_tools())}")
```

---

**Version**: 1.0.0  
**Phase**: 1 - MCP Tool Infrastructure (COMPLETE)  
**Author**: NFLIP Development Team
