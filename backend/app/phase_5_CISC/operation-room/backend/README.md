# NFLIP Backend — Forensic Investigation Platform

Enterprise-grade backend for the NFLIP (Next-generation Forensic/Legal Investigation Platform) system.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python -m uvicorn app.main:app --reload --port 8000
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          NFLIP Backend Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   Frontend   │───▶│   FastAPI    │───▶│   Services   │               │
│  │   (Next.js)  │◀───│   Routes     │◀───│   Layer      │               │
│  └──────────────┘    └──────────────┘    └──────────────┘               │
│                                                 │                        │
│                      ┌──────────────────────────┼───────────────────┐   │
│                      ▼                          ▼                   ▼   │
│               ┌────────────┐           ┌────────────┐        ┌────────┐ │
│               │  Oracle AI │           │   Report   │        │  Tools │ │
│               │   Memory   │           │   Studio   │        │  Layer │ │
│               └────────────┘           └────────────┘        └────────┘ │
│                      │                          │                        │
│                      ▼                          ▼                        │
│               ┌────────────┐           ┌────────────┐                   │
│               │  ChromaDB  │           │  DuckDB    │                   │
│               │  (Vectors) │           │  (Vault)   │                   │
│               └────────────┘           └────────────┘                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── database.py                # DuckDB connection management
│   │
│   ├── routes/                    # API route handlers (24 modules)
│   │   ├── cases.py               # Case management CRUD
│   │   ├── chat.py                # AI chat/clarification endpoints
│   │   ├── memory.py              # Oracle 26AI memory APIs (26 endpoints)
│   │   ├── studio_v4.py           # Report Studio canvas operations
│   │   ├── workflow.py            # Investigation orchestration
│   │   ├── correlation.py         # Entity correlation graphs
│   │   ├── timeline.py            # Timeline analysis
│   │   ├── anomaly.py             # Anomaly detection
│   │   └── ...                    # See full list below
│   │
│   ├── services/                  # Business logic layer (59 services)
│   │   │
│   │   │── # ═══ Oracle 26AI Memory Services ═══
│   │   ├── embedding_service.py   # Sentence-transformer embeddings
│   │   ├── vector_store.py        # ChromaDB vector database
│   │   ├── evidence_vault.py      # Evidence with vector search
│   │   ├── session_memory.py      # Phase-aware conversation memory
│   │   ├── longterm_memory.py     # Hypothesis calibration tracking
│   │   ├── procedural_memory.py   # Investigation templates
│   │   ├── validation_memory.py   # Claim extraction & validation
│   │   ├── hybrid_retriever.py    # BM25 + semantic + RRF reranking
│   │   ├── learning_loop.py       # Feedback & improvement metrics
│   │   │
│   │   │── # ═══ Core Services ═══
│   │   ├── chat_service.py        # AI-powered chat with memory
│   │   ├── unified_orchestrator.py# Investigation phase orchestration
│   │   ├── investigation_workflow.py # High-level workflow management
│   │   ├── report_studio_service.py  # Canvas document management
│   │   ├── auto_report_builder.py    # AI-generated report sections
│   │   │
│   │   │── # ═══ PDF & Export Services ═══
│   │   ├── reportlab_pdf_service.py  # ReportLab PDF generation
│   │   ├── chart_renderer.py         # Matplotlib chart rendering
│   │   ├── export_service.py         # Export orchestration
│   │   ├── export_manifest.py        # Cryptographic manifests
│   │   │
│   │   │── # ═══ Analysis Services ═══
│   │   ├── anomaly_service.py     # Anomaly detection algorithms
│   │   ├── correlation_service.py # Entity correlation
│   │   ├── timeline_service.py    # Timeline analysis
│   │   ├── network_service.py     # Network flow analysis
│   │   ├── depth_service.py       # Deep entity analysis
│   │   │
│   │   │── # ═══ LLM Services ═══
│   │   ├── llm_provider.py        # LLM abstraction (Ollama, Gemini)
│   │   ├── llm_service.py         # Enhanced LLM with conversation
│   │   ├── llm/                   # LLM service module
│   │   │   └── service.py         # Core LLM service
│   │   │
│   │   │── # ═══ Deep Research Module ═══
│   │   └── deep_research/         # 16 files for advanced research
│   │       ├── engine.py          # Thought engine
│   │       ├── plan_manager.py    # Research planning
│   │       ├── human_loop.py      # Human-in-the-loop
│   │       ├── report_builder.py  # Report assembly
│   │       └── ...
│   │
│   ├── agents/                    # AI agent implementations
│   │   ├── hypothesis/            # Hypothesis analysis agents
│   │   ├── confidence/            # Confidence scoring agents
│   │   ├── evidence/              # Evidence evaluation agents
│   │   ├── synthesis/             # Report synthesis agents
│   │   └── ...
│   │
│   ├── models/                    # Pydantic data models
│   │   ├── vector_types.py        # Vector/embedding models
│   │   └── ...
│   │
│   ├── tools/                     # Investigation tools
│   │   ├── network_tools.py       # Network analysis
│   │   ├── timeline_tools.py      # Timeline analysis
│   │   └── ...
│   │
│   └── utils/                     # Utility functions
│       ├── hashing.py             # SHA-256 hashing for CoC
│       └── ...
│
├── archive/                       # Archived development files
├── data/                          # Case data storage (DuckDB files)
├── requirements.txt               # Python dependencies
└── run.bat                        # Windows startup script
```

## API Endpoints (222 routes)

### Memory Services (`/api/memory/...`) — 26 endpoints
Oracle 26AI-style memory system using open-source alternatives:

| Category | Endpoints | Description |
|----------|-----------|-------------|
| Evidence Vault | 5 | Vector-embedded evidence storage & search |
| Session Memory | 3 | Phase-aware conversation context |
| Long-term Memory | 4 | Hypothesis calibration tracking |
| Procedural Memory | 3 | Investigation templates |
| Validation | 4 | Claim extraction & validation |
| Hybrid Retrieval | 1 | BM25 + semantic + RRF reranking |
| Learning Loop | 5 | Feedback collection & metrics |
| System | 1 | Overall memory statistics |

### Case Management (`/api/cases/...`) — 88 endpoints
Complete case lifecycle management including evidence, timeline, anomalies, etc.

### Report Studio (`/api/v4/...`) — 34 endpoints
Canvas-based report editing with drag-drop widgets, AI assistance, and PDF export.

### Investigation (`/api/investigations/...`) — 20 endpoints
Multi-phase investigation orchestration with AI-powered analysis.

### Agents (`/api/agents/...`) — 16 endpoints
AI agent execution for hypothesis testing, confidence scoring, etc.

## Technology Stack

### Core
- **FastAPI** — High-performance async web framework
- **DuckDB** — Embedded analytical database (per-case isolation)
- **Pydantic** — Data validation and settings management

### Oracle 26AI Alternatives (Open Source)
- **ChromaDB** — Vector database with HNSW indexing
- **sentence-transformers** — Local embeddings (`all-MiniLM-L6-v2`)
- **rank-bm25** — BM25Okapi for keyword search
- **cross-encoder** — `ms-marco-MiniLM-L-6-v2` for reranking

### PDF Generation
- **ReportLab** — Pure Python PDF generation (replaces Playwright)
- **Matplotlib** — High-quality chart rendering
- **svglib** — SVG to ReportLab conversion

### LLM Integration
- **Ollama** — Local LLM inference
- **Google Gemini** — Cloud LLM with key rotation
- **LangGraph** — Agent orchestration framework

## Key Features

### 1. Oracle 26AI Memory System
Open-source implementation of enterprise memory patterns:

```python
# Evidence with vector embeddings
from app.services.evidence_vault import get_evidence_vault
vault = get_evidence_vault(case_id)
vault.add_evidence(content, metadata, source)
results = vault.hybrid_search(query, limit=10)

# Session memory with phase awareness
from app.services.session_memory import get_session_memory
memory = get_session_memory(case_id)
memory.add_turn(role="user", content=msg, phase="hypothesis_testing")
context = memory.get_relevant_context(query, limit=5)

# Hypothesis calibration
from app.services.longterm_memory import get_long_term_memory
ltm = get_long_term_memory()
ltm.record_hypothesis(hypothesis, confidence)
ltm.resolve_hypothesis(id, outcome="confirmed")
calibration = ltm.get_calibration_metrics()
```

### 2. ReportLab PDF Engine
Direct PDF generation without browser dependency:

```python
from app.services.reportlab_pdf_service import ReportLabPDFService
service = ReportLabPDFService(case_id, doc_id, focus_mode=False)
pdf_bytes = service.convert_canvas_to_pdf(ast_data)
```

### 3. Multi-Phase Investigation
Orchestrated investigation workflow:

```
INTAKE → CLARIFICATION → PLANNING → APPROVAL → EXECUTION 
    → HYPOTHESIS_TESTING → CONFIDENCE_SCORING → SYNTHESIS → REPORTING
```

### 4. Chain of Custody
Cryptographic integrity for forensic evidence:
- SHA-256 hashing of all evidence
- Audit trail with timestamps
- Export manifests with verification hashes

## Configuration

Create `.env` file:

```env
# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
GEMINI_API_KEYS=key1,key2,key3

# Database
DATA_DIR=./data

# ChromaDB
CHROMA_PERSIST_DIR=./data/chromadb

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

## Development

### Running Tests
```bash
python -m pytest tests/ -v
```

### Type Checking
```bash
python -m mypy app/ --ignore-missing-imports
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

Proprietary — CISC Internal Use Only
