# NFLIP Multi-Agent Report Automation System

## Architecture Documentation

### Overview

The Multi-Agent Report Automation System transforms the manual Report Studio workflow into an intelligent, automated pipeline. It generates comprehensive forensic reports from hypothesis scenarios using a hierarchical agent architecture backed by 120+ research methodologies.

```
                      ┌─────────────────────────────────┐
                      │      MASTER ORCHESTRATOR        │
                      │   (Task Decomposition &         │
                      │    Agent Coordination)          │
                      └─────────────────┬───────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
        ▼                               ▼                               ▼
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│    HYPOTHESIS     │       │     EVIDENCE      │       │      MODULE       │
│     ANALYSIS      │       │    COLLECTION     │       │    EVALUATORS     │
│      AGENT        │       │      AGENT        │       │    (6 Agents)     │
└─────────┬─────────┘       └─────────┬─────────┘       └─────────┬─────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                                      ▼
                      ┌─────────────────────────────────┐
                      │     CONFIDENCE SCORING          │
                      │          AGENT                  │
                      │   (Multi-Factor Analysis)       │
                      └─────────────────┬───────────────┘
                                        │
                                        ▼
                      ┌─────────────────────────────────┐
                      │     SUMMARY SYNTHESIS           │
                      │          AGENT                  │
                      │  (Report Generation + NLG)      │
                      └─────────────────────────────────┘
```

---

## Components

### 1. Master Orchestrator (`orchestrator/master_orchestrator.py`)
Central coordinator using LangGraph StateGraph:
- **Parse Node**: Decompose user request into atomic tasks
- **Schedule Node**: Determine task dependencies and execution order
- **Dispatch Node**: Route tasks to specialized agents
- **Aggregate Node**: Combine results from all agents
- **Validate Node**: Verify completeness and consistency
- **Output Node**: Format final response

### 2. Hypothesis Analysis Agent (`hypothesis/hypothesis_agent.py`)
Parses scenarios and generates testable hypotheses:
- **Entity Extraction**: Identifies actors, assets, indicators
- **Hypothesis Generation**: Creates competing explanations
- **Attack Vector Mapping**: Links to MITRE ATT&CK
- **Evidence Requirements**: Lists needed proof points
- **ACH Methodology**: Analysis of Competing Hypotheses

### 3. Evidence Collection Agent (`evidence/evidence_collector.py`)
Gathers evidence from all modules:
- **Module Interface**: Queries timeline, anomaly, correlation, etc.
- **Evidence Inventory**: Catalogs all findings
- **Cross-Reference**: Links evidence to hypotheses
- **Quality Assessment**: Evaluates evidence reliability

### 4. Module Evaluators (`evaluators/module_evaluators.py`)
Six specialized evaluators:
| Module | Evaluator | Focus |
|--------|-----------|-------|
| Timeline | TimelineEvaluator | Temporal patterns, gaps, sequences |
| Anomaly | AnomalyEvaluator | Detection quality, false positives |
| Correlation | CorrelationEvaluator | Cross-source validation |
| Network | NetworkEvaluator | Traffic analysis, indicators |
| Depth | DepthEvaluator | Root cause, attack chains |
| CRUD | CRUDEvaluator | Data access patterns |

### 5. Confidence Scoring Agent (`confidence/confidence_agent.py`)
Multi-factor Bayesian confidence scoring:

**Factors & Weights:**
| Factor | Weight | Description |
|--------|--------|-------------|
| Evidence Coverage | 0.25 | Completeness of evidence |
| Module Agreement | 0.20 | Cross-module consensus |
| Temporal Consistency | 0.15 | Timeline coherence |
| Cross Validation | 0.20 | External corroboration |
| Pattern Match | 0.10 | Known TTP alignment |
| Research Alignment | 0.10 | Methodology support |

**Confidence Levels (ODNI ICD 203):**
- Very High: ≥90%
- High: 75-90%
- Moderate: 50-75%
- Low: 25-50%
- Very Low: <25%

### 6. Summary Synthesis Agent (`synthesis/synthesis_agent.py`)
Generates comprehensive reports:
- **Executive Summary**: High-level findings
- **Technical Narrative**: Detailed analysis
- **Evidence Appendix**: Supporting data
- **Recommendations**: Remediation steps
- **Chain of Custody**: Audit trail

**Output Formats:**
- Technical Report (JSON structured)
- Executive Summary (Markdown)
- Regulatory Submission (Formal)

### 7. Research Knowledge Base (`research/knowledge_base.py`)
120+ indexed methodologies across 12 categories:

| Category | Count | Key Methodologies |
|----------|-------|-------------------|
| Digital Forensics | 12 | CFRS, NIST 800-86, EnCase |
| Network Forensics | 10 | PCAP Analysis, NetFlow, Zeek |
| Malware Analysis | 11 | Cuckoo, YARA, Binary Ninja |
| Memory Forensics | 10 | Volatility, Rekall, LIME |
| Timeline Analysis | 8 | Super Timeline, MACB |
| Evidence Handling | 7 | Chain of Custody, SHA-256 |
| Machine Learning | 15 | Isolation Forest, SHAP |
| Confidence Quantification | 12 | ACH, Bayesian, Monte Carlo |
| Threat Intelligence | 12 | STIX/TAXII, MISP, OpenCTI |
| Incident Response | 8 | PICERL, SANS 6-Step |
| Log Analysis | 8 | Splunk, ELK, LogRhythm |
| Cloud Forensics | 7 | AWS CloudTrail, Azure |

---

## Integration Layer (`integration_layer.py`)

### Pipeline Executor
Coordinates the full report generation flow:
```
Initialization → Hypothesis Analysis → Evidence Collection → 
Module Evaluation → Confidence Scoring → Summary Synthesis → Finalization
```

### Message Broker
Pub/sub communication between agents:
- Topics for agent-to-agent messaging
- Async queue processing
- Handler registration

### Result Aggregator
- Merges evidence from multiple sources
- Combines confidence scores
- Resolves conflicts between outputs

### Retry Handler
- Exponential backoff retry logic
- Configurable max retries and delays

---

## API Endpoints (`routes/agents.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/agents/generate-report` | POST | Full automated report generation |
| `/agents/report-status/{run_id}` | GET | Check generation status |
| `/agents/analyze-hypothesis` | POST | Hypothesis analysis only |
| `/agents/score-confidence` | POST | Confidence scoring only |
| `/agents/agents` | GET | List registered agents |
| `/agents/agents/{id}` | GET | Agent status |
| `/agents/research/search` | POST | Search knowledge base |
| `/agents/research/statistics` | GET | Knowledge base stats |
| `/agents/research/recommendations` | POST | Get methodology recommendations |

---

## File Structure

```
app/agents/
├── __init__.py                 # Main exports
├── base.py                     # BaseAgent, Registry, Message types
├── integration_layer.py        # Pipeline execution, messaging
│
├── orchestrator/
│   ├── __init__.py
│   └── master_orchestrator.py  # Central coordinator
│
├── hypothesis/
│   ├── __init__.py
│   └── hypothesis_agent.py     # Scenario analysis
│
├── evidence/
│   ├── __init__.py
│   └── evidence_collector.py   # Evidence gathering
│
├── confidence/
│   ├── __init__.py
│   └── confidence_agent.py     # Bayesian scoring
│
├── synthesis/
│   ├── __init__.py
│   └── synthesis_agent.py      # Report generation
│
├── evaluators/
│   ├── __init__.py
│   └── module_evaluators.py    # 6 module evaluators
│
└── research/
    ├── __init__.py
    └── knowledge_base.py       # 120+ methodologies

routes/
└── agents.py                   # FastAPI endpoints
```

---

## Usage Example

```python
from app.agents import PipelineExecutor

# Initialize executor
executor = PipelineExecutor(llm_provider="ollama")

# Run full pipeline
context = await executor.execute(
    case_id="CASE-2024-001",
    scenario="Suspected data exfiltration via unauthorized cloud storage...",
    report_type="technical"
)

# Access results
print(f"Hypotheses: {len(context.hypotheses)}")
print(f"Evidence items: {len(context.evidence_inventory.get('evidence', []))}")
print(f"Overall confidence: {context.confidence_scores.get('overall_confidence')}")
print(f"Report sections: {list(context.final_report.keys())}")
```

---

## Design Principles

1. **Modularity**: Each agent is self-contained and independently testable
2. **Extensibility**: New agents/evaluators easily added via registry
3. **Research-Backed**: All analysis grounded in 120+ methodologies
4. **Transparent Confidence**: Multi-factor scoring with explainable weights
5. **Audit Trail**: Full chain of custody for legal defensibility
6. **LLM-Agnostic**: Supports Ollama and Gemini backends
7. **Async-First**: Built for concurrent execution with asyncio

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024 | Initial multi-agent architecture |

---

*Generated by NFLIP Development Team*
