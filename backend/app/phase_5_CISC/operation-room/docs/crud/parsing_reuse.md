# Shared Parsers & Code Reuse Guide

> How existing utilities are shared across modules and how to add new log format parsers.

## Shared Utilities

| Utility | File | Used By |
|---------|------|---------|
| `hash_records(records)` | `utils/hashing.py` | Case Init, Timeline, Anomaly, Correlation, CRUD |
| `record_coc_event(...)` | `services/audit_service.py` | Case Init, Evidence, Timeline, Anomaly, Correlation, CRUD |
| `get_llm(provider)` | `services/llm_provider.py` | Correlation, CRUD (via AI summary) |
| `open_vault(case_id)` | `database.py` | Every module |
| `_parse_detail(detail)` | Pattern used in anomaly/correlation/crud agents | All analysis modules |

## Code Reuse Pattern

All 3 analysis agents (`anomaly_agent.py`, `correlation_agent.py`, `crud_agent.py`) follow the identical pattern:

```python
# 1. State schema (TypedDict)
class AgentState(TypedDict, total=False):
    case_id: str
    run_id: str
    ...

# 2. Node functions
def load_data(state: AgentState) -> dict:
    conn = open_vault(state["case_id"])
    # ... read from DuckDB
    return {"data": ..., "status": "loaded"}

# 3. Store + CoC (final node)
def store_and_audit(state: AgentState) -> dict:
    hash_value = hash_records(records)        # ← reused
    coc_id = record_coc_event(...)            # ← reused
    return {"hash_value": hash_value, "status": "completed"}

# 4. Build graph + compile
graph = StateGraph(AgentState)
graph.add_node("load_data", load_data)
# ... add nodes and edges
compiled = graph.compile()

# 5. Public API
def run_analysis(case_id: str, **kwargs) -> dict:
    result = compiled.invoke({"case_id": case_id, **kwargs})
    return result
```

## Adding a New Log Format Parser

To add support for a new log format (e.g., AWS CloudTrail):

### Step 1: Add action mappings in `crud_agent.py`

```python
CRUD_MAP.update({
    "CreateUser":       "CREATE",
    "GetObject":        "READ",
    "PutObject":        "CREATE",
    "DeleteObject":     "DELETE",
    "UpdateTrail":      "UPDATE",
})
```

### Step 2: Add sensitivity rules

```python
SENSITIVITY_RULES.append(
    {"pattern": "s3://production", "level": "CRITICAL", "reason": "Production S3 bucket"}
)
```

### Step 3: Add source type in `nlp_agent.py`

```python
_ACTIONS_BY_SOURCE["CLOUDTRAIL"] = [
    "CreateUser", "GetObject", "PutObject", "DeleteObject", ...
]
```

No core logic changes needed — the classification and pattern detection work on any action.

## Future: Plugin Registry

```python
from abc import ABC, abstractmethod

class LogParser(ABC):
    @abstractmethod
    def classify_crud(self, action: str) -> str: ...
    @abstractmethod
    def classify_sensitivity(self, target: str) -> tuple[str, str]: ...
    @abstractmethod
    def extract_metrics(self, event: dict) -> dict: ...

_registry: dict[str, LogParser] = {}

def register_parser(source_type: str, parser: LogParser):
    _registry[source_type] = parser

def get_parser(source_type: str) -> LogParser:
    return _registry.get(source_type, DefaultParser())
```
