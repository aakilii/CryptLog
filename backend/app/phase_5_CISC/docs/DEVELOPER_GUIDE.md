# NFLIP Developer Guide

## Architecture & Technical Reference

---

## Table of Contents

1. [VS Code AI Productivity Setup](#vs-code-ai-productivity-setup)
2. [Architecture Overview](#architecture-overview)
3. [Project Structure](#project-structure)
4. [Backend Development](#backend-development)
5. [Frontend Development](#frontend-development)
6. [Adding New Modules](#adding-new-modules)
7. [Creating Custom Agents](#creating-custom-agents)
8. [API Development](#api-development)
9. [Testing](#testing)
10. [Deployment](#deployment)

---

## VS Code AI Productivity Setup

To get the absolute most out of this project and the new VS Code features, you should use GitHub Copilot as a **Project-Aware Automated Coding Agent**. Your workspace is pre-configured with industry-leading VS Code features (Agents, Skills, MCP, Prompts).

### 1. Model Context Protocol (MCP) Integration
**What it is:** MCP allows VS Code and Copilot to talk directly to your local backend.
**How to use it:** 
* Run the task `mcp: smoke` via `Ctrl+Shift+B` to start the connection.
* In Chat, ask Copilot: *"Ask the backend MCP if the demo scenario generated properly."*

### 2. Custom Domain Agents (@ Mentions)
**What it is:** Keep code architecture strictly separated.
**How to use it:** Prefix requests with an agent, e.g., `@or-backend implement a new GET /api/cases route` or `@or-frontend fix the overflow error in DocumentCanvas.tsx`.

### 3. Reusable Workspace Skills
**What it is:** Located in `.github/skills/`, these are step-by-step recipes for highly complex tasks.
**How to use it:** Say in chat: *"Execute the `operation-room-dev-loop` skill on `app/services/correlation_agent.py`"*.

### 4. Custom Prompt Templates
**What it is:** Standardized prompt templates like `backend-fix.prompt.md`.
**How to use it:** Attach the prompt file in chat (using `#`) and say *"Apply this prompt to `app/routes/investigation.py`."*

### 5. Automated Build & Verification Tasks
**What it is:** Command-line scripts wired directly into VS Code `tasks.json`.
**How to use it:** Press `Ctrl+Shift+B`, select `verify: all` to run tests and linters in sequence.

---

## Architecture Overview

### System Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Next.js)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ Report      │    │ Case        │    │ Dashboard   │              │
│  │ Studio V4   │    │ Management  │    │             │              │
│  └──────┬──────┘    └─────────────┘    └─────────────┘              │
│         │                                                            │
│  ┌──────▼──────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ useInvesti- │    │ useCanvas-  │    │ Zustand     │              │
│  │ gationStream│    │ Stream      │    │ Store       │              │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘              │
│         │                  │                                         │
└─────────┼──────────────────┼─────────────────────────────────────────┘
          │ SSE              │
          ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          BACKEND (FastAPI)                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      ROUTES (API Layer)                        │ │
│  ├────────────────────────────────────────────────────────────────┤ │
│  │ /investigation  │ /augment  │ /tools  │ /aliases  │ /studio   │ │
│  └────────┬────────┴─────┬─────┴────┬────┴─────┬─────┴─────┬─────┘ │
│           │              │          │          │           │        │
│  ┌────────▼────────────────────────────────────────────────────────┐│
│  │                    SERVICES (Business Logic)                    ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │  UnifiedOrchestrator │ AugmentStudio │ EntityAliasService       ││
│  │  DeepResearchOrch.   │ ExportService │ AuditService             ││
│  └────────┬────────────────────────────────────────────────────────┘│
│           │                                                         │
│  ┌────────▼────────────────────────────────────────────────────────┐│
│  │                       AGENTS (AI Layer)                         ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │  PipelineExecutor    │ HypothesisAgent │ ConfidenceAgent        ││
│  │  DeepResearchOrch.   │ EvidenceAgent   │ SynthesisAgent         ││
│  └────────┬────────────────────────────────────────────────────────┘│
│           │                                                         │
│  ┌────────▼────────────────────────────────────────────────────────┐│
│  │                     TOOLS (Module Layer)                        ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │  TimelineTool  │ AnomalyTool  │ CorrelationTool │ NetworkTool   ││
│  │  CRUDTool      │ DepthTool    │ VaultTool       │               ││
│  └────────┬────────────────────────────────────────────────────────┘│
│           │                                                         │
│  ┌────────▼────────────────────────────────────────────────────────┐│
│  │                     DATABASE (DuckDB)                           ││
│  ├─────────────────────────────────────────────────────────────────┤│
│  │  cases/{case_id}/vault.duckdb                                   ││
│  │  - timeline_events, anomaly_scores, correlations                ││
│  │  - network_flows, crud_operations, evidence                     ││
│  └─────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **AI Doesn't Generate Evidence** - AI reasons about evidence from logs
2. **Cryptographic Integrity** - SHA-256 hashing for all artifacts
3. **Human-in-the-Loop** - User confirmation at key decision points
4. **SSE Streaming** - Real-time updates to frontend
5. **Modular Architecture** - Pluggable tools and agents

---

## Project Structure

```
CISC/
├── operation-room/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── agents/           # AI Agents
│   │   │   │   ├── integration_layer.py  # PipelineExecutor
│   │   │   │   ├── hypothesis_agent.py
│   │   │   │   ├── confidence_agent.py
│   │   │   │   └── deep_research/
│   │   │   │       └── orchestrator.py
│   │   │   │
│   │   │   ├── services/         # Business Logic
│   │   │   │   ├── unified_orchestrator.py
│   │   │   │   ├── augment_studio.py
│   │   │   │   ├── entity_alias_service.py
│   │   │   │   └── export_service.py
│   │   │   │
│   │   │   ├── tools/            # Universal Module Tools
│   │   │   │   ├── base_tool.py
│   │   │   │   ├── timeline_tool.py
│   │   │   │   ├── anomaly_tool.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── routes/           # API Routes
│   │   │   │   ├── investigation.py
│   │   │   │   ├── augment.py
│   │   │   │   ├── tools.py
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── mcp/              # MCP Tools (LLM Interface)
│   │   │   │   └── tools/
│   │   │   │
│   │   │   └── main.py           # FastAPI App
│   │   │
│   │   └── requirements.txt
│   │
│   └── frontend/
│       ├── src/
│       │   ├── app/              # Next.js App Router
│       │   │   └── (studio)/
│       │   │       └── cases/[id]/studio-v4/
│       │   │
│       │   ├── components/
│       │   │   └── studio-v4/    # Report Studio V4
│       │   │       ├── TopBar.tsx
│       │   │       ├── CanvaLayout.tsx
│       │   │       ├── dialogs/
│       │   │       │   ├── InvestigationConfigDialog.tsx
│       │   │       │   └── ReportPreviewPanel.tsx
│       │   │       ├── hooks/
│       │   │       │   └── useCanvasStream.ts
│       │   │       └── store/
│       │   │           └── useStudioStore.ts
│       │   │
│       │   └── hooks/
│       │       └── useInvestigationStream.ts
│       │
│       └── package.json
│
└── docs/
    ├── USER_GUIDE.md
    ├── QUICK_START.md
    └── DEVELOPER_GUIDE.md
```

---

## Backend Development

### Adding a New Route

```python
# app/routes/my_feature.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/my-feature", tags=["My Feature"])

class MyRequest(BaseModel):
    case_id: str
    parameter: str

@router.post("/execute")
async def execute_feature(req: MyRequest):
    """Execute my feature."""
    result = await process_feature(req.case_id, req.parameter)
    return {"status": "success", "result": result}
```

Register in `app/main.py`:
```python
from app.routes import my_feature
app.include_router(my_feature.router)
```

### Creating SSE Endpoints

```python
from fastapi.responses import StreamingResponse
import asyncio
import json

@router.post("/stream")
async def stream_data(req: MyRequest):
    async def event_generator():
        for i in range(10):
            data = {"progress": i * 10, "message": f"Step {i}"}
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Database Access (DuckDB)

```python
from app.database import open_vault

def query_evidence(case_id: str, query: str):
    conn = open_vault(case_id)
    try:
        result = conn.execute(query).fetchall()
        return result
    finally:
        conn.close()
```

---

## Frontend Development

### Creating a New Hook

```typescript
// src/hooks/useMyFeature.ts
import { useState, useCallback } from 'react';

export function useMyFeature() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const execute = useCallback(async (params: MyParams) => {
    setLoading(true);
    try {
      const res = await fetch('/api/my-feature/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      const result = await res.json();
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, loading, execute };
}
```

### Consuming SSE Streams

```typescript
// src/hooks/useMyStream.ts
export function useMyStream() {
  const [progress, setProgress] = useState(0);

  const start = useCallback(async (params: MyParams) => {
    const response = await fetch('/api/my-feature/stream', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(params),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data:')) {
          const data = JSON.parse(line.slice(5));
          setProgress(data.progress);
        }
      }
    }
  }, []);

  return { progress, start };
}
```

### Adding to Zustand Store

```typescript
// In store/useStudioStore.ts

// Add to interface
interface StudioStore {
  // ... existing
  myFeatureData: MyData | null;
  setMyFeatureData: (data: MyData) => void;
}

// Add to implementation
myFeatureData: null,
setMyFeatureData: (data) => set({ myFeatureData: data }),
```

---

## Adding New Modules

### Step 1: Create the Tool

```python
# app/tools/my_module_tool.py
from app.tools.base_tool import ModuleTool, ToolInput, ToolOutput
from typing import List, Dict, Any

class MyModuleTool(ModuleTool):
    """My custom analysis module."""
    
    tool_id = "my_module"
    name = "My Module"
    description = "Performs custom analysis"
    capabilities = [
        "analyze_data",
        "generate_report",
        "detect_patterns",
    ]
    
    async def execute(self, input: ToolInput) -> ToolOutput:
        capability = input.capability
        params = input.parameters
        
        if capability == "analyze_data":
            result = await self._analyze_data(params)
        elif capability == "generate_report":
            result = await self._generate_report(params)
        else:
            raise ValueError(f"Unknown capability: {capability}")
        
        return ToolOutput(
            tool_id=self.tool_id,
            capability=capability,
            success=True,
            findings=result.get("findings", []),
            visualizations=result.get("visualizations", []),
            summary=result.get("summary", ""),
        )
    
    async def _analyze_data(self, params: Dict[str, Any]) -> Dict:
        # Your analysis logic here
        return {
            "findings": [...],
            "summary": "Analysis complete"
        }
```

### Step 2: Register the Tool

```python
# app/tools/__init__.py
from .my_module_tool import MyModuleTool

# In base_tool.py or a registry
TOOL_REGISTRY = {
    "timeline": TimelineTool(),
    "anomaly": AnomalyTool(),
    "my_module": MyModuleTool(),  # Add here
    # ...
}
```

### Step 3: Add Frontend Panel

```typescript
// components/studio-v4/panels/MyModulePanel.tsx
export function MyModulePanel({ caseId, onInsertComponent }) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    fetch(`/api/tools/my_module/capabilities`)
      .then(r => r.json())
      .then(setData);
  }, []);
  
  return (
    <div>
      <PanelHeader title="My Module" />
      <PanelContent>
        {data?.capabilities.map(cap => (
          <DraggableComponent
            key={cap}
            componentId={cap}
            onInsert={() => onInsertComponent(cap)}
          />
        ))}
      </PanelContent>
    </div>
  );
}
```

---

## Creating Custom Agents

### Agent Structure

```python
# app/agents/my_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, AsyncGenerator

class BaseAgent(ABC):
    """Base class for all agents."""
    
    @abstractmethod
    async def process(
        self, 
        context: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process input and yield results."""
        pass

class MyAgent(BaseAgent):
    """Custom agent for specific analysis."""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    async def process(self, context: Dict[str, Any]):
        # Step 1: Prepare
        yield {"type": "status", "message": "Starting analysis"}
        
        # Step 2: Analyze
        results = await self._analyze(context)
        yield {"type": "finding", "data": results}
        
        # Step 3: Summarize
        summary = await self._summarize(results)
        yield {"type": "summary", "data": summary}
    
    async def _analyze(self, context):
        if self.llm:
            prompt = f"Analyze this: {context}"
            return await self.llm.generate(prompt)
        return {"manual_analysis": "No LLM available"}
```

### Integrating with Pipeline

```python
# In services/unified_orchestrator.py

async def _run_custom_agent(self, context):
    agent = MyAgent(llm_client=self.llm)
    
    async for event in agent.process(context):
        yield {
            "type": "finding",
            "phase": "custom_analysis",
            "data": event,
            "timestamp": datetime.now().isoformat(),
        }
```

---

## API Development

### Pydantic Models

```python
# app/models/my_models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class AnalysisType(str, Enum):
    QUICK = "quick"
    DEEP = "deep"
    COMPREHENSIVE = "comprehensive"

class AnalysisRequest(BaseModel):
    case_id: str = Field(..., description="Case identifier")
    analysis_type: AnalysisType = Field(default=AnalysisType.QUICK)
    parameters: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "CASE-001",
                "analysis_type": "deep",
                "parameters": {"depth": 3}
            }
        }

class AnalysisResponse(BaseModel):
    status: str
    findings: List[dict]
    confidence: float
```

### Error Handling

```python
from fastapi import HTTPException

@router.post("/analyze")
async def analyze(req: AnalysisRequest):
    try:
        result = await run_analysis(req)
        return result
    except CaseNotFoundError:
        raise HTTPException(404, "Case not found")
    except AnalysisError as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")
```

---

## Testing

### Backend Tests

```python
# tests/test_investigation.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_start_investigation():
    response = client.post("/api/investigation/start", json={
        "case_id": "TEST-001",
        "scenario": "Test scenario",
        "modules_to_run": ["timeline"]
    })
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_tool_execution():
    from app.tools import TimelineTool
    tool = TimelineTool()
    result = await tool.execute(ToolInput(
        case_id="TEST-001",
        capability="build_timeline",
        parameters={}
    ))
    assert result.success
```

### Frontend Tests

```typescript
// __tests__/useInvestigationStream.test.ts
import { renderHook, act } from '@testing-library/react';
import { useInvestigationStream } from '@/hooks/useInvestigationStream';

describe('useInvestigationStream', () => {
  it('starts investigation', async () => {
    const { result } = renderHook(() => useInvestigationStream());
    
    await act(async () => {
      await result.current.startInvestigation({
        caseId: 'TEST-001',
        scenario: 'Test',
      });
    });
    
    expect(result.current.isRunning).toBe(true);
  });
});
```

### Running Tests

```bash
# Backend
cd operation-room/backend
pytest tests/ -v

# Frontend
cd operation-room/frontend
npm test
```

---

## Deployment

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./operation-room/backend
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data

  frontend:
    build: ./operation-room/frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

### Environment Variables

```bash
# .env
# LLM Configuration
GEMINI_API_KEY=your_key_here
OLLAMA_HOST=http://localhost:11434

# Database
DATA_DIR=/app/data

# CORS
CORS_ORIGINS=http://localhost:3000,https://your-domain.com

# Logging
LOG_LEVEL=INFO
```

### Production Checklist

- [ ] Set secure CORS origins
- [ ] Enable HTTPS
- [ ] Configure rate limiting
- [ ] Set up log aggregation
- [ ] Enable health checks
- [ ] Configure backup for DuckDB files
- [ ] Set up monitoring (Prometheus/Grafana)

---

## Contributing

### Code Style

- Python: Black + isort + flake8
- TypeScript: ESLint + Prettier
- Commits: Conventional Commits

### Pull Request Process

1. Fork the repository
2. Create feature branch (`git checkout -b feature/my-feature`)
3. Write tests
4. Update documentation
5. Submit PR

### Release Process

```bash
# Version bump
npm version patch  # or minor/major

# Tag release
git tag -a v1.0.0 -m "Release 1.0.0"
git push origin v1.0.0
```

---

*Developer Guide Version: 1.0*
*Last Updated: April 2026*
