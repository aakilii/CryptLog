# ORACLE 26AI OPEN-SOURCE IMPLEMENTATION PLAN
## Complete Multi-Phase Architecture for CISC Operation-Room
## Using 100% Open-Source Technologies

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [Current Architecture Analysis](#2-current-architecture-analysis)
3. [Design Decisions](#3-design-decisions)
4. [Database Schema Extensions](#4-database-schema-extensions)
5. [Complete 8-Phase Implementation Plan](#complete-8-phase-implementation-plan)
6. [Complete File Summary](#complete-file-summary)
7. [Timeline Summary](#timeline-summary)
8. [Expected Outcomes](#expected-outcomes)
9. [Testing Strategy](#testing-strategy)
10. [Implementation Checklist](#implementation-checklist)
11. [Risk Mitigation](#risk-mitigation)
12. [Next Steps](#next-steps)
13. [Appendix: Claude Opus 4.5 Prompt Reference](#appendix-claude-opus-45-prompt-reference)

---

## 1. EXECUTIVE SUMMARY

### Project Overview
This document provides a **complete implementation plan** to replicate Oracle 26AI capabilities using **100% open-source technologies**. The implementation will achieve the same benefits shown in the architecture analysis while maintaining full compatibility with the existing CISC Operation-Room system.

### Key Design Decisions (Based on User Requirements)
- **Implementation Scope:** All 9 memory systems - full implementation
- **Data Isolation:** Hybrid - shared templates/patterns, isolated evidence per case
- **Validation Strictness:** Advisory only - flag unsupported claims but don't block
- **Storage Strategy:** DuckDB for relational + ChromaDB for vectors (both together)

### Expected Improvements

| Feature | Oracle 26AI Capability | Open-Source Alternative | Expected Improvement |
|---------|----------------------|------------------------|---------------------|
| **Evidence Vault** | Relational + JSON columns | DuckDB + JSON schema validation | 35-55% better traceability |
| **Session Memory** | JSON docs + light vectors | ChromaDB embedded + TTL | 20-35% better context |
| **Long-term Memory** | VECTOR + metadata + hybrid | ChromaDB + sentence-transformers | 25-45% better hypothesis precision |
| **Procedural Memory** | JSON Relational Duality | DuckDB JSON + ChromaDB search | 35-55% better consistency |
| **Validation Memory** | Claim-evidence-contradiction | Custom graph tables + LLM extraction | 50-75% fewer unsupported claims |
| **Retrieval Quality** | Hybrid lexical+semantic + rerank | BM25 + ChromaDB + cross-encoder | 30-50% higher Precision@K |
| **Hypothesis Calibration** | Prior + posterior history | Bayesian tables + decay weighting | 20-40% better calibration |
| **Report Grounding** | Mandatory citation blocks | Citation extraction + verification | 40-65% hallucination reduction |
| **Learning Loop** | Feedback + outcome store | Outcome tables + monthly retraining | 15-30% quality lift |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CISC OPERATION-ROOM                               │
│                    Oracle 26AI Open-Source Implementation                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        APPLICATION LAYER                            │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │   │
│  │  │   FastAPI    │ │  LangGraph   │ │    Report    │ │   Studio   │ │   │
│  │  │   Routes     │ │   Agents     │ │   Builder    │ │     V4     │ │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────v───────────────────────────────────┐   │
│  │                         MEMORY LAYER (NEW)                           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐   │   │
│  │  │  Session   │ │ Long-term  │ │ Procedural │ │   Validation   │   │   │
│  │  │   Memory   │ │   Memory   │ │   Memory   │ │     Memory     │   │   │
│  │  │ (TTL-based)│ │(Cross-case)│ │(Templates) │ │(Claim-Evidence)│   │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────────┘   │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────┐   │   │
│  │  │ Hypothesis │ │  Learning  │ │  Retrieval │ │    Report      │   │   │
│  │  │Calibration │ │    Loop    │ │   Quality  │ │   Grounding    │   │   │
│  │  │ (Bayesian) │ │ (Feedback) │ │  (Hybrid)  │ │  (Citations)   │   │   │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────v───────────────────────────────────┐   │
│  │                         STORAGE LAYER                                │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────┐   ┌─────────────────────────────────┐  │   │
│  │  │     DuckDB (Per-Case)    │   │     ChromaDB (Shared+Isolated)  │  │   │
│  │  │  ┌───────────────────┐  │   │  ┌──────────────────────────┐   │  │   │
│  │  │  │ evidence_vault    │  │   │  │ evidence_vectors (case)  │   │  │   │
│  │  │  │ session_memory    │  │   │  │ session_vectors (case)   │   │  │   │
│  │  │  │ validation_claims │  │   │  │ claim_vectors (case)     │   │  │   │
│  │  │  │ evidence_links    │  │   │  │ hypothesis_vectors(case) │   │  │   │
│  │  │  │ provenance_log    │  │   │  └──────────────────────────┘   │  │   │
│  │  │  └───────────────────┘  │   │  ┌──────────────────────────┐   │  │   │
│  │  └─────────────────────────┘   │  │ longterm_vectors (GLOBAL)│   │  │   │
│  │                                │  │ template_vectors (GLOBAL)│   │  │   │
│  │  ┌─────────────────────────┐   │  │ calibration_data (GLOBAL)│   │  │   │
│  │  │  Global DuckDB (Shared) │   │  └──────────────────────────┘   │  │   │
│  │  │  ┌───────────────────┐  │   └─────────────────────────────────┘  │   │
│  │  │  │ hypothesis_history│  │                                        │   │
│  │  │  │ outcome_store     │  │                                        │   │
│  │  │  │ procedural_templates│ │                                        │   │
│  │  │  │ feedback_log      │  │                                        │   │
│  │  │  │ calibration_metrics│ │                                        │   │
│  │  │  └───────────────────┘  │                                        │   │
│  │  └─────────────────────────┘                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────v───────────────────────────────────┐   │
│  │                       EMBEDDING LAYER (NEW)                          │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │                   EmbeddingService                            │   │   │
│  │  │  • sentence-transformers (local, free, offline)               │   │   │
│  │  │  • all-MiniLM-L6-v2 (384 dims) OR all-mpnet-base-v2 (768)    │   │   │
│  │  │  • Future: OpenAI text-embedding-3-large (API, higher quality)│   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  │  ┌──────────────────────────────────────────────────────────────┐   │   │
│  │  │                   RetrievalPipeline                           │   │   │
│  │  │  • BM25 (rank-bm25) for lexical search                        │   │   │
│  │  │  • ChromaDB for semantic search                               │   │   │
│  │  │  • Cross-encoder reranking (ms-marco-MiniLM-L-6-v2)           │   │   │
│  │  │  • Reciprocal Rank Fusion for result merging                  │   │   │
│  │  └──────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────v───────────────────────────────────┐   │
│  │                         LLM LAYER (Existing)                         │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐ │   │
│  │  │ Gemini 2.5     │  │ Ollama/Qwen3   │  │   LLM Prompts (NEW)    │ │   │
│  │  │ Flash (API)    │  │ (Local)        │  │   • Claim extraction   │ │   │
│  │  │                │  │                │  │   • Contradiction check│ │   │
│  │  │                │  │                │  │   • Citation verify    │ │   │
│  │  └────────────────┘  └────────────────┘  └────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## TECHNOLOGY STACK

### Core Open-Source Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│ EMBEDDING MODEL (Local, Free, Offline)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│ sentence-transformers/all-MiniLM-L6-v2    (384 dimensions, fast)       │
│   OR                                                                    │
│ sentence-transformers/all-mpnet-base-v2   (768 dimensions, accurate)   │
│   Future: OpenAI text-embedding-3-large   (API-based, higher quality)  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│ VECTOR DATABASE (Embedded, Python-native)                               │
├─────────────────────────────────────────────────────────────────────────┤
│ ChromaDB 0.5+                                                           │
│   - Embedded mode (no separate server)                                  │
│   - Persistent storage to disk                                          │
│   - Metadata filtering                                                  │
│   - HNSW index for fast similarity search                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│ RELATIONAL DATABASE (Existing)                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ DuckDB (per-case storage)                                               │
│   - Extended with new tables for memory systems                         │
│   - JSON columns for flexible schema                                    │
│   - Full-text search for BM25                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│ LLM PROVIDERS (Existing + Enhanced)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ Gemini 2.5 Flash      (Primary LLM, via API)                            │
│ Ollama + Qwen3        (Local fallback)                                  │
│   New: Claim extraction prompts                                          │
│   New: Citation verification prompts                                     │
│   New: Contradiction detection prompts                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│ RETRIEVAL QUALITY (New Components)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ rank-bm25             (Lexical search library)                          │
│ sentence-transformers/cross-encoder/ms-marco-MiniLM-L-6-v2 (Reranker)  │
│   OR                                                                    │
│ LLM-based reranking   (More accurate but slower)                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Python Dependencies to Add

```python
# requirements.txt additions
chromadb>=0.5.0                          # Vector database
sentence-transformers>=2.2.0             # Local embeddings
rank-bm25>=0.2.2                          # BM25 lexical search
scikit-learn>=1.3.0                       # ML utilities (already have)
numpy>=1.24.0                             # Numerical (already have)
```

---

## 2. CURRENT ARCHITECTURE ANALYSIS

### 2.1 Existing Memory Systems (BEFORE Implementation)

| Memory Type | Current Implementation | Storage | Limitations |
|-------------|----------------------|---------|-------------|
| **Session Memory** | `chat_service.py` InvestigationContext | In-memory → DB | No vector search, lost on restart |
| **Conversation Memory** | `llm_service.py` Conversation class | In-memory (max 20) | Fixed window, no semantic retrieval |
| **Long-term Memory** | `findings_vault.py` FindingsVault | DuckDB JSON columns | No embeddings, keyword search only |
| **Evidence Memory** | `mcp/tools/evidence.py` EvidenceVault | DuckDB + SHA-256 | Good integrity, weak retrieval |
| **Hypothesis Memory** | `mcp/tools/hypothesis.py` HypothesisStore | In-memory dict | No persistence across sessions |
| **Procedural Memory** | Static templates in report_agent.py | Python dicts | No learning, no adaptation |
| **Validation Memory** | **NONE** | N/A | 🔴 Major gap - hallucination risk |

### 2.2 Critical Flaws Being Addressed

#### 🔴 **P0: No Validation Memory (Hallucination Risk)**
- AI generates narratives with no systematic claim verification
- No claim-evidence linkage tracking
- No contradiction detection
- Reports may contain unsupported statements

#### 🔴 **P0: No Long-term Learning**
- Every investigation starts from scratch
- No learning from past hypothesis outcomes
- No reviewer correction learning
- System never improves from experience

#### 🟠 **P1: Keyword-Only Retrieval**
- `findings_vault.py` uses exact match queries
- Relevant evidence missed
- No semantic similarity search

#### 🟠 **P1: No Session Continuity**
- `Conversation` class limited to 20 messages
- Lost on restart
- Long investigations lose early context

### 2.3 Files That Will Be Modified

**Tier 1: Core Infrastructure (Must Modify First)**

| File | Current Lines | Purpose | Modification |
|------|---------------|---------|--------------|
| `backend/app/database.py` | ~250 | DuckDB schema | Add 12 new tables |
| `backend/app/config.py` | ~100 | App configuration | Add embedding/vector config |
| `backend/app/main.py` | ~200 | FastAPI app | Initialize vector store |
| `backend/requirements.txt` | ~50 | Dependencies | Add chromadb, sentence-transformers |

**Tier 2: Evidence & Findings**

| File | Current Lines | Purpose | Modification |
|------|---------------|---------|--------------|
| `backend/app/services/findings_vault.py` | ~650 | Evidence storage | Add vector ops, relationships |
| `backend/app/services/evidence_service.py` | ~300 | Evidence handling | Add provenance tracking |
| `backend/app/models/evidence.py` | ~100 | Data models | Add relationship models |

**Tier 3: Agents & Intelligence**

| File | Current Lines | Purpose | Modification |
|------|---------------|---------|--------------|
| `backend/app/agents/hypothesis/hypothesis_agent.py` | ~1200 | Hypothesis generation | Use calibrated priors |
| `backend/app/agents/confidence/confidence_agent.py` | ~1400 | Confidence scoring | Use historical calibration |
| `backend/app/services/chat_service.py` | ~850 | Chat context | Integrate session memory |
| `backend/app/services/unified_orchestrator.py` | ~1000 | Investigation orchestration | Store outcomes for learning |

**Tier 4: Report Generation**

| File | Current Lines | Purpose | Modification |
|------|---------------|---------|--------------|
| `backend/app/services/writer_agent.py` | ~800 | Section writing | Add claim validation gate |
| `backend/app/services/auto_report_builder.py` | ~2200 | PDF generation | Add citation verification |
| `backend/app/services/deep_research/hypothesis_report_binder.py` | ~750 | Report binding | Add claim extraction |

**Tier 5: API Routes**

| File | Current Lines | Purpose | Modification |
|------|---------------|---------|--------------|
| `backend/app/routes/findings.py` | ~300 | Findings API | Add memory/search endpoints |
| `backend/app/routes/deep_research.py` | ~1500 | Deep research API | Add calibration endpoints |
| `backend/app/routes/studio_v4.py` | ~1300 | Studio API | Add feedback endpoints |

---

## 3. DESIGN DECISIONS

### 3.1 Data Isolation Strategy: HYBRID

Based on user requirement: **"Hybrid - shared templates, isolated evidence"**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA ISOLATION MODEL                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   CASE-ISOLATED (Per-Case DuckDB + Namespaced ChromaDB)                │
│   ├── evidence_vault          # Case-specific evidence                 │
│   ├── session_memory          # Case-specific conversation             │
│   ├── validation_claims       # Case-specific claims                   │
│   ├── claim_evidence_links    # Case-specific links                    │
│   ├── evidence_links          # Case-specific relationships            │
│   └── provenance_log          # Case-specific audit trail              │
│                                                                         │
│   GLOBALLY SHARED (Global DuckDB + Shared ChromaDB Collections)        │
│   ├── hypothesis_history      # All historical hypotheses              │
│   ├── outcome_store           # All investigation outcomes             │
│   ├── procedural_templates    # Approved report templates              │
│   ├── calibration_metrics     # Prior/posterior calibration            │
│   └── feedback_log            # All reviewer feedback                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Validation Strictness: ADVISORY

Based on user requirement: **"Advisory only - flag but don't block"**

```python
# Implementation approach
class ClaimValidationMode:
    ADVISORY = "advisory"       # Flag unsupported claims, allow export
    STRICT = "strict"           # Block export if unsupported claims exist
    CONFIGURABLE = "config"     # Per-report-type strictness
    
# Default: ADVISORY
CLAIM_VALIDATION_MODE = ClaimValidationMode.ADVISORY

# Behavior:
# 1. Extract all claims from report text using LLM
# 2. Attempt to link each claim to supporting evidence
# 3. Flag unsupported claims with visual indicators:
#    - Yellow warning icon in UI
#    - Annotation in exported PDF
#    - Summary in validation report
# 4. DO NOT block report export
# 5. Log for learning loop (track which unsupported claims get through)
```

### 3.3 Storage Strategy: DUCKDB + CHROMADB

Based on user requirement: **"Use both together (recommended)"**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STORAGE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   DuckDB (Relational)                    ChromaDB (Vector)              │
│   ├─ Per-Case Databases:                 ├─ Per-Case Collections:       │
│   │   cases/{case_id}/case.duckdb        │   case_{case_id}_evidence    │
│   │   ├─ evidence_vault                  │   case_{case_id}_session     │
│   │   ├─ session_memory                  │   case_{case_id}_claims      │
│   │   ├─ validation_claims               │   case_{case_id}_hypotheses  │
│   │   ├─ claim_evidence_links            │                              │
│   │   ├─ evidence_links                  ├─ Global Collections:         │
│   │   └─ provenance_log                  │   global_longterm            │
│   │                                      │   global_templates           │
│   ├─ Global Database:                    │   global_calibration         │
│   │   data/global.duckdb                 │                              │
│   │   ├─ hypothesis_history              │                              │
│   │   ├─ outcome_store                   │                              │
│   │   ├─ procedural_templates            │                              │
│   │   ├─ calibration_metrics             │                              │
│   │   └─ feedback_log                    │                              │
│   │                                      │                              │
│   Why DuckDB:                            │   Why ChromaDB:              │
│   ✓ SQL queries                          │   ✓ Vector similarity        │
│   ✓ JSON columns                         │   ✓ Semantic search          │
│   ✓ Foreign keys                         │   ✓ Metadata filtering       │
│   ✓ Per-case isolation                   │   ✓ HNSW fast search         │
│   ✓ Existing infrastructure              │   ✓ Embedded (no server)     │
│                                          │                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. DATABASE SCHEMA EXTENSIONS

### 4.1 Per-Case DuckDB Tables (Added to existing schema)

```sql
-- ============================================================================
-- EVIDENCE VAULT ENHANCEMENTS
-- ============================================================================

-- Evidence relationship tracking (supports/contradicts/extends)
CREATE TABLE IF NOT EXISTS evidence_links (
    link_id VARCHAR PRIMARY KEY,
    source_evidence_id VARCHAR NOT NULL,
    target_evidence_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL,  -- 'supports', 'contradicts', 'extends', 'references'
    confidence FLOAT DEFAULT 0.5,
    created_by VARCHAR,  -- 'system' | 'user' | 'agent'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    FOREIGN KEY (source_evidence_id) REFERENCES investigation_findings(finding_id),
    FOREIGN KEY (target_evidence_id) REFERENCES investigation_findings(finding_id)
);

-- Track which evidence has been embedded (for re-embedding on model change)
CREATE TABLE IF NOT EXISTS evidence_embeddings_registry (
    evidence_id VARCHAR PRIMARY KEY,
    embedding_version VARCHAR NOT NULL,  -- e.g., "MiniLM-v2.1"
    embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_id VARCHAR NOT NULL,  -- ChromaDB document ID
    text_hash VARCHAR NOT NULL,  -- Hash of embedded text (detect content changes)
    FOREIGN KEY (evidence_id) REFERENCES investigation_findings(finding_id)
);

-- Chain-of-custody extension for regulatory compliance
CREATE TABLE IF NOT EXISTS provenance_log (
    provenance_id VARCHAR PRIMARY KEY,
    evidence_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,  -- 'created', 'modified', 'accessed', 'exported', 'cited', 'linked'
    actor VARCHAR NOT NULL,  -- user_id or 'system' or 'agent:{agent_name}'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSON,  -- Event-specific details
    previous_hash VARCHAR,  -- Hash before change (for modifications)
    current_hash VARCHAR,   -- Hash after change
    ip_address VARCHAR,
    session_id VARCHAR,
    FOREIGN KEY (evidence_id) REFERENCES investigation_findings(finding_id)
);

-- ============================================================================
-- SESSION MEMORY (TTL-based, phase-aware)
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_memory (
    memory_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    phase VARCHAR NOT NULL,  -- 'intake', 'hypothesis', 'analysis', 'report', 'review'
    memory_type VARCHAR NOT NULL,  -- 'entity', 'decision', 'question', 'finding', 'context'
    content JSON NOT NULL,
    importance_score FLOAT DEFAULT 0.5,  -- For pruning when context too large
    ttl_expires TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_count INT DEFAULT 0,
    last_accessed TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_session_memory_phase ON session_memory(session_id, phase);
CREATE INDEX IF NOT EXISTS idx_session_memory_ttl ON session_memory(ttl_expires);

-- ============================================================================
-- VALIDATION MEMORY (Claim verification - ADVISORY mode)
-- ============================================================================

-- Atomic claims extracted from report text
CREATE TABLE IF NOT EXISTS validation_claims (
    claim_id VARCHAR PRIMARY KEY,
    section_id VARCHAR,
    claim_text TEXT NOT NULL,
    claim_type VARCHAR,  -- 'factual', 'inference', 'conclusion', 'recommendation'
    claim_importance VARCHAR DEFAULT 'medium',  -- 'critical', 'high', 'medium', 'low'
    verification_status VARCHAR DEFAULT 'pending',  -- 'pending', 'supported', 'unsupported', 'contradicted'
    support_score FLOAT,  -- 0-1 confidence that claim is supported
    evidence_count INT DEFAULT 0,  -- Number of supporting evidence pieces
    contradiction_count INT DEFAULT 0,  -- Number of contradicting pieces
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMP,
    verified_by VARCHAR  -- 'system' | 'user:{id}' | 'agent:{name}'
);

CREATE INDEX IF NOT EXISTS idx_claims_status ON validation_claims(verification_status);
CREATE INDEX IF NOT EXISTS idx_claims_section ON validation_claims(section_id);

-- Links between claims and evidence
CREATE TABLE IF NOT EXISTS claim_evidence_links (
    link_id VARCHAR PRIMARY KEY,
    claim_id VARCHAR NOT NULL,
    evidence_id VARCHAR NOT NULL,
    link_type VARCHAR NOT NULL,  -- 'supports', 'partially_supports', 'contradicts', 'neutral'
    relevance_score FLOAT DEFAULT 0.5,  -- 0-1 how relevant the evidence is
    explanation TEXT,  -- Why this evidence relates to the claim
    created_by VARCHAR,  -- 'system' | 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (claim_id) REFERENCES validation_claims(claim_id),
    FOREIGN KEY (evidence_id) REFERENCES investigation_findings(finding_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_links_claim ON claim_evidence_links(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_links_evidence ON claim_evidence_links(evidence_id);

-- Contradictions between claims (within same report)
CREATE TABLE IF NOT EXISTS claim_contradictions (
    contradiction_id VARCHAR PRIMARY KEY,
    claim_id_1 VARCHAR NOT NULL,
    claim_id_2 VARCHAR NOT NULL,
    contradiction_type VARCHAR,  -- 'direct', 'logical', 'temporal', 'scope'
    severity VARCHAR DEFAULT 'medium',  -- 'critical', 'high', 'medium', 'low'
    explanation TEXT,
    resolution_status VARCHAR DEFAULT 'unresolved',  -- 'unresolved', 'resolved', 'accepted'
    resolution_notes TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (claim_id_1) REFERENCES validation_claims(claim_id),
    FOREIGN KEY (claim_id_2) REFERENCES validation_claims(claim_id)
);
```

### 4.2 Global DuckDB Tables (Shared across all cases)

```sql
-- ============================================================================
-- FILE: data/global.duckdb
-- ============================================================================

-- ============================================================================
-- LONG-TERM MEMORY (Cross-investigation learning)
-- ============================================================================

-- Hypothesis history for calibrated priors
CREATE TABLE IF NOT EXISTS hypothesis_history (
    hypothesis_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    case_type VARCHAR,  -- 'insider_threat', 'data_breach', 'fraud', 'apt', 'malware', 'other'
    hypothesis_text TEXT NOT NULL,
    hypothesis_category VARCHAR,  -- 'data_exfiltration', 'privilege_escalation', 'lateral_movement', etc.
    initial_confidence FLOAT,
    final_confidence FLOAT,
    final_outcome VARCHAR,  -- 'accepted', 'rejected', 'modified', 'inconclusive'
    outcome_notes TEXT,
    key_evidence JSON,  -- List of evidence IDs that influenced outcome
    reviewer_id VARCHAR,
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome_at TIMESTAMP,
    embedding_version VARCHAR,
    embedding_id VARCHAR  -- ChromaDB ID in global_longterm collection
);

CREATE INDEX IF NOT EXISTS idx_hypothesis_category ON hypothesis_history(hypothesis_category);
CREATE INDEX IF NOT EXISTS idx_hypothesis_case_type ON hypothesis_history(case_type);
CREATE INDEX IF NOT EXISTS idx_hypothesis_outcome ON hypothesis_history(final_outcome);

-- Investigation outcomes for learning loop
CREATE TABLE IF NOT EXISTS outcome_store (
    outcome_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    case_type VARCHAR,
    outcome_type VARCHAR,  -- 'case_closed', 'escalated', 'false_positive', 'inconclusive'
    outcome_subtype VARCHAR,  -- More specific categorization
    
    -- Metrics for quality assessment
    metrics JSON,  -- {precision, recall, f1, review_time_minutes, edit_count, etc.}
    
    -- Reviewer feedback
    reviewer_id VARCHAR,
    reviewer_feedback TEXT,
    quality_score FLOAT,  -- Overall quality rating 0-1
    
    -- Learning signals
    improvement_areas JSON,  -- Areas identified for improvement
    successful_patterns JSON,  -- Patterns that worked well
    
    -- Court/external outcomes (when available)
    external_validation VARCHAR,  -- 'court_accepted', 'court_rejected', 'audit_passed', etc.
    external_notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_case_type ON outcome_store(case_type);
CREATE INDEX IF NOT EXISTS idx_outcome_type ON outcome_store(outcome_type);

-- ============================================================================
-- PROCEDURAL MEMORY (Templates and patterns)
-- ============================================================================

CREATE TABLE IF NOT EXISTS procedural_templates (
    template_id VARCHAR PRIMARY KEY,
    template_type VARCHAR NOT NULL,  -- 'section', 'full_report', 'style', 'prompt'
    template_name VARCHAR NOT NULL,
    audience VARCHAR NOT NULL,  -- 'technical', 'executive', 'legal', 'regulatory', 'general'
    case_type VARCHAR,  -- null = all types, otherwise specific type
    
    -- Template content
    content JSON NOT NULL,  -- The actual template structure
    
    -- Quality metrics (updated by feedback)
    quality_score FLOAT DEFAULT 0.5,
    usage_count INT DEFAULT 0,
    success_count INT DEFAULT 0,  -- Times used and approved
    
    -- Status
    approval_status VARCHAR DEFAULT 'pending',  -- 'pending', 'approved', 'deprecated'
    approved_by VARCHAR,
    approved_at TIMESTAMP,
    
    -- Lineage
    created_from_case VARCHAR,  -- Original case ID if extracted from real report
    parent_template_id VARCHAR,  -- If derived from another template
    
    -- Embedding for semantic search
    embedding_version VARCHAR,
    embedding_id VARCHAR,  -- ChromaDB ID in global_templates collection
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_templates_type ON procedural_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_templates_audience ON procedural_templates(audience);
CREATE INDEX IF NOT EXISTS idx_templates_quality ON procedural_templates(quality_score DESC);

-- ============================================================================
-- HYPOTHESIS CALIBRATION (Bayesian priors)
-- ============================================================================

CREATE TABLE IF NOT EXISTS calibration_metrics (
    calibration_id VARCHAR PRIMARY KEY,
    hypothesis_category VARCHAR NOT NULL,
    case_type VARCHAR,  -- null = all types
    
    -- Historical statistics
    total_count INT DEFAULT 0,
    accepted_count INT DEFAULT 0,
    rejected_count INT DEFAULT 0,
    modified_count INT DEFAULT 0,
    
    -- Calculated prior (updated periodically)
    calculated_prior FLOAT,
    prior_confidence FLOAT,  -- Confidence in the prior (based on sample size)
    
    -- Decay-weighted statistics (more recent = higher weight)
    weighted_acceptance_rate FLOAT,
    decay_half_life_days INT DEFAULT 365,
    
    -- Calibration accuracy tracking
    predicted_vs_actual JSON,  -- Calibration curve data
    brier_score FLOAT,  -- Calibration metric
    
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sample_period_start TIMESTAMP,
    sample_period_end TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_calibration_category ON calibration_metrics(hypothesis_category);

-- ============================================================================
-- LEARNING LOOP (Feedback collection)
-- ============================================================================

CREATE TABLE IF NOT EXISTS feedback_log (
    feedback_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    feedback_type VARCHAR NOT NULL,  -- 'reviewer_edit', 'approval', 'rejection', 'comment'
    
    -- What was changed
    target_type VARCHAR,  -- 'section', 'claim', 'hypothesis', 'evidence_link'
    target_id VARCHAR,
    
    -- Change details
    original_content TEXT,
    edited_content TEXT,
    change_summary TEXT,
    
    -- Feedback metadata
    reviewer_id VARCHAR NOT NULL,
    reviewer_role VARCHAR,  -- 'analyst', 'senior_analyst', 'manager', 'legal'
    severity VARCHAR,  -- 'critical', 'major', 'minor', 'style'
    
    -- Learning signals
    should_learn BOOLEAN DEFAULT TRUE,  -- Whether to include in training
    learning_applied BOOLEAN DEFAULT FALSE,
    learning_applied_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_log(feedback_type);
CREATE INDEX IF NOT EXISTS idx_feedback_target ON feedback_log(target_type, target_id);
```

---

## COMPLETE 8-PHASE IMPLEMENTATION PLAN

### PHASE 1: FOUNDATION - Embedding Service + ChromaDB Setup
**Duration: 3-4 days | Priority: CRITICAL**

#### Why This Phase First
Everything depends on vector embeddings. Without embeddings, we cannot implement:
- Session Memory (context vectors)
- Long-term Memory (hypothesis embeddings)
- Procedural Memory (template search)
- Retrieval Quality (semantic search)

#### What We Build

```
Phase 1 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ EmbeddingService (New)                                          │
├─────────────────────────────────────────────────────────────────┤
│ - embed_text(text) → List[float]                               │
│ - embed_batch(texts) → List[List[float]]                       │
│ - get_model_info() → EmbeddingModelInfo                        │
│ - Switch between local (sentence-transformers) and API (future)│
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│ VectorStoreManager (New)                                        │
├─────────────────────────────────────────────────────────────────┤
│ Collections:                                                    │
│   - evidence_vectors      (Evidence Vault embeddings)          │
│   - session_vectors       (Session Memory, TTL-based)          │
│   - longterm_vectors      (Hypothesis/Finding embeddings)      │
│   - procedural_vectors    (Template embeddings)                │
│   - claim_vectors         (Claim verification)                 │
│                                                                 │
│ Methods:                                                        │
│   - add_document(collection, id, text, metadata) → None        │
│   - search(collection, query, top_k, filters) → Results        │
│   - delete(collection, ids) → None                             │
│   - update_metadata(collection, id, metadata) → None           │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES TO CREATE:**

| File | Purpose | Estimated Lines |
|------|---------|-----------------|
| `backend/app/services/embedding_service.py` | Local embedding generation | 250 |
| `backend/app/services/vector_store.py` | ChromaDB wrapper | 400 |
| `backend/app/models/vector_types.py` | Pydantic models for vectors | 100 |

**FILES TO MODIFY:**

| File | Changes | Lines Changed |
|------|---------|---------------|
| `backend/requirements.txt` | Add chromadb, sentence-transformers, rank-bm25 | 5 |
| `backend/app/config.py` | Add embedding model config | 15 |
| `backend/app/__init__.py` | Initialize vector store on startup | 10 |

#### Claude Opus 4.5 Prompt (Phase 1 - Iteration 1)

```markdown
## TASK: Create Embedding Service for CISC Operation-Room

### Context
We are implementing Oracle 26AI-like capabilities using open-source tools. This is Phase 1: Foundation.

### Current Architecture
- Backend: FastAPI + DuckDB (per-case databases)
- LLM: Gemini 2.5 Flash + Ollama (local)
- Location: c:\CISC\operation-room\backend\app\

### Requirement
Create a robust embedding service using sentence-transformers that:
1. Loads a local embedding model (all-MiniLM-L6-v2 default, configurable)
2. Provides singleton access (don't reload model per request)
3. Handles batch embedding efficiently
4. Is async-compatible (run in executor to not block)
5. Has fallback for GPU/CPU detection

### Create These Files

**File 1: `backend/app/services/embedding_service.py`**
```python
# Key requirements:
# - Singleton pattern for model loading
# - Support: embed_text(str) -> List[float]
# - Support: embed_batch(List[str]) -> List[List[float]]
# - Handle model loading errors gracefully
# - Log model info on first load
# - Config from config.py
```

**File 2: `backend/app/models/vector_types.py`**
```python
# Pydantic models:
# - EmbeddingRequest
# - EmbeddingResponse
# - VectorSearchQuery
# - VectorSearchResult
```

### Modify These Files

**File: `backend/app/config.py`**
Add settings:
```python
# Embedding configuration
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # or all-mpnet-base-v2
EMBEDDING_DEVICE: str = "auto"  # auto | cpu | cuda
EMBEDDING_BATCH_SIZE: int = 32
```

### Testing Requirements
After creating files, verify with:
```python
from app.services.embedding_service import EmbeddingService
svc = EmbeddingService()
vec = svc.embed_text("test embedding")
assert len(vec) == 384  # MiniLM dimension
```

### Constraints
- Do NOT modify any existing service files yet
- Do NOT add API routes yet (Phase 7)
- Use existing logger from app (loguru or standard logging)
```

#### Claude Opus 4.5 Prompt (Phase 1 - Iteration 2)

```markdown
## TASK: Create ChromaDB Vector Store Manager

### Context
Phase 1, Iteration 2. Embedding service is now complete at:
`backend/app/services/embedding_service.py`

### Requirement
Create a vector store manager using ChromaDB that:
1. Initializes ChromaDB in embedded/persistent mode
2. Creates 5 collections on startup (evidence, session, longterm, procedural, claim)
3. Provides typed search with metadata filtering
4. Handles collection lifecycle (create if not exists)
5. Is async-compatible

### Create This File

**File: `backend/app/services/vector_store.py`**
```python
# Key requirements:
# - Initialize ChromaDB with persist_directory = "./data/vectordb"
# - Use EmbeddingService for all embeddings
# - Collections with metadata schema:
#   - evidence_vectors: {case_id, evidence_id, evidence_type, timestamp}
#   - session_vectors: {case_id, session_id, phase, ttl_expires}
#   - longterm_vectors: {case_id, type (hypothesis|finding|outcome), status}
#   - procedural_vectors: {template_id, category, quality_score}
#   - claim_vectors: {case_id, section_id, claim_id, verified}
#
# Methods:
# - add_document(collection: str, id: str, text: str, metadata: dict)
# - add_batch(collection: str, documents: List[VectorDocument])
# - search(collection: str, query: str, top_k: int, where: dict = None)
# - delete(collection: str, ids: List[str])
# - get_collection_stats(collection: str) -> CollectionStats
```

### Modify These Files

**File: `backend/app/config.py`**
```python
# Vector store configuration
VECTOR_STORE_PATH: str = "./data/vectordb"
VECTOR_STORE_RESET_ON_STARTUP: bool = False
```

**File: `backend/app/__init__.py` or `main.py`**
```python
# Initialize vector store on app startup
# @app.on_event("startup")
# async def init_vector_store():
#     from app.services.vector_store import VectorStoreManager
#     VectorStoreManager.initialize()
```

### Testing Requirements
```python
from app.services.vector_store import VectorStoreManager
vsm = VectorStoreManager()
vsm.add_document("evidence_vectors", "ev1", "User logged in from suspicious IP", {"case_id": "case1"})
results = vsm.search("evidence_vectors", "login IP address", top_k=3)
assert len(results) > 0
```

### Integration Points
After this phase, the vector store is ready for:
- Phase 2: Evidence Vault (evidence_vectors collection)
- Phase 3: Session Memory (session_vectors collection)
- Phase 4: Long-term Memory (longterm_vectors collection)
- Phase 5: Procedural Memory (procedural_vectors collection)
- Phase 6: Validation Memory (claim_vectors collection)
```

---

### PHASE 2: EVIDENCE VAULT ENHANCEMENT
**Duration: 3-4 days | Priority: HIGH**

#### Why This Phase
The Evidence Vault is the foundation of forensic integrity. Every other system depends on having traceable, verified evidence with:
- Hash integrity
- Chain-of-custody
- Semantic searchability
- Relationship tracking

#### What We Build

```
Phase 2 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Enhanced Evidence Vault                                         │
├─────────────────────────────────────────────────────────────────┤
│ Current (findings_vault.py):                                    │
│   - investigation_findings table                                │
│   - Basic CRUD operations                                       │
│   - SHA-256 hashing                                             │
│                                                                 │
│ Enhanced:                                                       │
│   - Vector embeddings in ChromaDB (evidence_vectors)            │
│   - Evidence relationship table (evidence_links)                │
│   - JSON schema versioning                                      │
│   - Hybrid search (keyword + semantic)                          │
│   - Provenance tracking                                         │
│   - Cryptographic audit trail                                   │
└─────────────────────────────────────────────────────────────────┘
```

#### Database Schema Extensions (DuckDB)

```sql
-- New table: evidence_links (relationship tracking)
CREATE TABLE IF NOT EXISTS evidence_links (
    link_id VARCHAR PRIMARY KEY,
    source_evidence_id VARCHAR NOT NULL,
    target_evidence_id VARCHAR NOT NULL,
    relationship_type VARCHAR NOT NULL,  -- 'supports', 'contradicts', 'extends', 'references'
    confidence FLOAT DEFAULT 0.5,
    created_by VARCHAR,  -- 'system' | 'user' | 'agent'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);

-- New table: evidence_embeddings_registry (track what's embedded)
CREATE TABLE IF NOT EXISTS evidence_embeddings_registry (
    evidence_id VARCHAR PRIMARY KEY,
    embedding_version VARCHAR NOT NULL,  -- e.g., "MiniLM-v2.1"
    embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_id VARCHAR NOT NULL,  -- ChromaDB document ID
    text_hash VARCHAR NOT NULL  -- Hash of embedded text (detect changes)
);

-- New table: evidence_provenance (chain-of-custody extension)
CREATE TABLE IF NOT EXISTS evidence_provenance (
    provenance_id VARCHAR PRIMARY KEY,
    evidence_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,  -- 'created', 'modified', 'accessed', 'exported', 'cited'
    actor VARCHAR NOT NULL,  -- user_id or 'system'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSON,
    previous_hash VARCHAR,  -- Hash before change
    current_hash VARCHAR   -- Hash after change
);
```

#### Files Involved

**FILES TO MODIFY:**

| File | Changes | Lines Changed |
|------|---------|---------------|
| `backend/app/database.py` | Add 3 new tables | 50 |
| `backend/app/services/findings_vault.py` | Add vector ops, relationships | 200 |
| `backend/app/services/evidence_service.py` | Add provenance tracking | 100 |
| `backend/app/models/evidence.py` | Add relationship models | 80 |
| `backend/app/routes/findings.py` | Add search/link endpoints | 100 |
| `backend/app/tools/vault_tool.py` | Add semantic search tool | 80 |

#### Claude Opus 4.5 Prompt (Phase 2 - Iteration 1)

```markdown
## TASK: Enhance Evidence Vault with Vector Search and Relationships

### Context
Phase 2 of Oracle 26AI implementation. Phase 1 (embedding + vector store) is complete.

### Current State
- `findings_vault.py` at `backend/app/services/findings_vault.py`
- Simple CRUD for `investigation_findings` table
- No semantic search
- No relationship tracking

### Requirements
1. Extend database schema in `database.py` with:
   - evidence_links table
   - evidence_embeddings_registry table
   - evidence_provenance table

2. Enhance `findings_vault.py` to:
   - Auto-embed evidence on insert (using VectorStoreManager)
   - Track embeddings in registry (detect stale embeddings)
   - Support hybrid search (BM25 + semantic)
   - Create/query evidence relationships

3. Add provenance tracking:
   - Log all evidence access/modification
   - Maintain hash chain for tamper detection

### Implementation Pattern

```python
# In findings_vault.py, after inserting finding:
async def add_finding(self, finding: Finding) -> str:
    # Existing: Insert to DuckDB
    finding_id = await self._insert_to_db(finding)
    
    # NEW: Embed and store vector
    from app.services.vector_store import VectorStoreManager
    vsm = VectorStoreManager()
    vsm.add_document(
        collection="evidence_vectors",
        id=finding_id,
        text=f"{finding.title}. {finding.description}. {finding.analysis}",
        metadata={
            "case_id": finding.case_id,
            "evidence_type": finding.category,
            "confidence": finding.confidence
        }
    )
    
    # NEW: Track embedding
    await self._register_embedding(finding_id, text_hash=...)
    
    # NEW: Record provenance
    await self._record_provenance(finding_id, "created", ...)
    
    return finding_id
```

### Testing
```python
# Add finding
vault = FindingsVault(case_id)
fid = await vault.add_finding(Finding(title="Suspicious login", ...))

# Semantic search
results = await vault.search_semantic("unauthorized access attempt", top_k=5)
assert len(results) > 0

# Create relationship
await vault.link_evidence(fid, other_fid, "supports")
links = await vault.get_evidence_links(fid)
assert len(links) == 1
```

### Constraints
- Maintain backward compatibility with existing FindingsVault API
- Do not break existing tests
- Use existing DuckDB connection pattern
```

#### Claude Opus 4.5 Prompt (Phase 2 - Iteration 2)

```markdown
## TASK: Add Hybrid Search (BM25 + Semantic) to Evidence Vault

### Context
Phase 2, Iteration 2. Vector embeddings now work. Need hybrid search.

### Requirements
Create BM25 index alongside vector search for optimal retrieval:

1. Create `backend/app/services/bm25_index.py`:
   - BM25 index per case
   - Index on evidence title + description + analysis
   - Persist to disk alongside case DB

2. Implement hybrid search in `findings_vault.py`:
   ```python
   async def search_hybrid(
       self, 
       query: str, 
       top_k: int = 10,
       alpha: float = 0.5,  # 0 = all BM25, 1 = all semantic
       filters: dict = None
   ) -> List[SearchResult]:
       # 1. BM25 search
       bm25_results = self.bm25_index.search(query, top_k * 2)
       
       # 2. Semantic search
       semantic_results = self.vector_store.search("evidence_vectors", query, top_k * 2)
       
       # 3. Reciprocal Rank Fusion
       fused = self._reciprocal_rank_fusion(bm25_results, semantic_results, alpha)
       
       # 4. Apply filters
       filtered = [r for r in fused if self._matches_filter(r, filters)]
       
       return filtered[:top_k]
   ```

3. Add reranking option (cross-encoder):
   ```python
   async def search_hybrid_reranked(
       self,
       query: str,
       top_k: int = 10,
       rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
   ) -> List[SearchResult]:
       # Get 3x candidates from hybrid search
       candidates = await self.search_hybrid(query, top_k * 3)
       
       # Rerank with cross-encoder
       reranked = self._rerank_with_cross_encoder(query, candidates, rerank_model)
       
       return reranked[:top_k]
   ```

### Testing
```python
# Add multiple findings
vault = FindingsVault(case_id)
await vault.add_finding(Finding(title="Login from Russia", ...))
await vault.add_finding(Finding(title="Data exfiltration to external IP", ...))
await vault.add_finding(Finding(title="Password changed by admin", ...))

# Hybrid search
results = await vault.search_hybrid("unauthorized foreign access")
assert "Russia" in results[0].title or "external" in results[0].title

# With reranking (higher quality, slower)
results = await vault.search_hybrid_reranked("data leak")
```
```

---

### PHASE 3: SESSION MEMORY
**Duration: 2-3 days | Priority: HIGH**

#### Why This Phase
Session memory enables:
- Conversation continuity within investigation
- Context preservation across chat turns
- Phase-aware context (different context for hypothesis vs report generation)
- Token waste reduction (send only relevant context)

#### What We Build

```
Phase 3 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Session Memory System                                           │
├─────────────────────────────────────────────────────────────────┤
│ Storage:                                                        │
│   - DuckDB: session_memory table (JSON context)                │
│   - ChromaDB: session_vectors collection (embeddings)          │
│                                                                 │
│ Components:                                                     │
│   - SessionMemoryService (new)                                 │
│   - Integrates with chat_service.py                            │
│   - TTL-based expiration                                       │
│   - Phase-bound context (hypothesis phase vs report phase)     │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/session_memory.py` | Session memory service | 400 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/database.py` | Add session_memory table | 20 |
| `backend/app/services/chat_service.py` | Integrate session memory | 100 |
| `backend/app/services/deep_research/models.py` | Add session context model | 50 |

#### Claude Opus 4.5 Prompt (Phase 3)

```markdown
## TASK: Implement Session Memory for Conversation Context

### Context
Phase 3 of Oracle 26AI implementation. Evidence vault with vectors is complete.

### Requirements
Create session memory that:
1. Stores conversation context (entities, hypotheses, open questions)
2. Has TTL-based expiration (configurable, default 2 hours)
3. Is phase-aware (different context for different investigation phases)
4. Retrieves relevant context via vector similarity
5. Reduces token waste by sending only relevant memories

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS session_memory (
    memory_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    phase VARCHAR NOT NULL,  -- 'intake', 'hypothesis', 'analysis', 'report'
    memory_type VARCHAR NOT NULL,  -- 'entity', 'decision', 'question', 'finding'
    content JSON NOT NULL,
    ttl_expires TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Create File: `backend/app/services/session_memory.py`

```python
class SessionMemoryService:
    """
    Session memory with TTL and phase-awareness.
    
    Usage:
        sms = SessionMemoryService(case_id)
        
        # Store memory
        sms.store("hypothesis", MemoryItem(
            type="decision",
            content={"decision": "Focus on data exfiltration hypothesis"}
        ))
        
        # Get relevant memories for context
        context = sms.get_relevant_context(
            query="What patterns indicate data theft?",
            phase="hypothesis",
            max_tokens=2000
        )
        
        # Clean expired memories
        sms.cleanup_expired()
    """
    
    def store(self, phase: str, item: MemoryItem) -> str
    def get_relevant_context(self, query: str, phase: str, max_tokens: int) -> str
    def get_all_for_phase(self, phase: str) -> List[MemoryItem]
    def transition_phase(self, from_phase: str, to_phase: str) -> None
    def cleanup_expired(self) -> int
```

### Integration with chat_service.py
```python
# In chat_service.py process_message():
async def process_message(self, case_id: str, message: str, phase: str):
    # Get relevant session context
    sms = SessionMemoryService(case_id)
    context = sms.get_relevant_context(message, phase, max_tokens=2000)
    
    # Build prompt with context
    prompt = f"""
    ## Relevant Context from This Investigation
    {context}
    
    ## Current Question
    {message}
    """
    
    # Call LLM
    response = await self.llm.generate(prompt)
    
    # Extract and store new memories
    new_memories = self._extract_memories(response)
    for mem in new_memories:
        sms.store(phase, mem)
    
    return response
```

### Testing
```python
sms = SessionMemoryService("case123")

# Store some memories
sms.store("hypothesis", MemoryItem(type="entity", content={"name": "John Smith", "role": "suspect"}))
sms.store("hypothesis", MemoryItem(type="decision", content={"decision": "Focus on email patterns"}))

# Get context
ctx = sms.get_relevant_context("What do we know about John?", "hypothesis", max_tokens=500)
assert "John Smith" in ctx

# Phase transition preserves key memories
sms.transition_phase("hypothesis", "analysis")
```
```

---

### PHASE 4: LONG-TERM MEMORY + HYPOTHESIS CALIBRATION
**Duration: 3-4 days | Priority: HIGH**

#### Why This Phase
Long-term memory enables:
- Learning from past investigations
- Calibrated hypothesis priors (based on historical outcomes)
- Cross-investigation knowledge transfer
- 25-45% better hypothesis precision

#### What We Build

```
Phase 4 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Long-term Memory + Hypothesis Calibration                       │
├─────────────────────────────────────────────────────────────────┤
│ Storage:                                                        │
│   - DuckDB: hypothesis_history, outcome_store                  │
│   - ChromaDB: longterm_vectors collection                      │
│                                                                 │
│ Components:                                                     │
│   - LongTermMemoryService (new)                                │
│   - HypothesisCalibrationService (new)                         │
│   - Integration with hypothesis_agent.py                       │
│   - Bayesian prior/posterior updates                           │
│   - Decay weighting for old data                               │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/longterm_memory.py` | Cross-investigation memory | 500 |
| `backend/app/services/hypothesis_calibration.py` | Bayesian prior calibration | 400 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/database.py` | Add hypothesis_history, outcome_store tables | 40 |
| `backend/app/agents/hypothesis/hypothesis_agent.py` | Use calibrated priors | 150 |
| `backend/app/services/unified_orchestrator.py` | Store outcomes for learning | 100 |
| `backend/app/services/deep_research/llm_hypothesis_generator.py` | Use historical priors | 100 |

#### Claude Opus 4.5 Prompt (Phase 4 - Iteration 1)

```markdown
## TASK: Implement Long-term Memory for Cross-Investigation Learning

### Context
Phase 4, Iteration 1. Session memory complete. Now building long-term memory.

### Requirements
Create long-term memory that:
1. Stores hypothesis outcomes (accepted/rejected/modified)
2. Stores findings that led to outcomes
3. Retrieves similar past hypotheses for new investigations
4. Applies decay weighting to old data (configurable half-life)
5. Updates embeddings quarterly (embedding drift mitigation)

### Database Schema
```sql
-- Hypothesis history across all investigations
CREATE TABLE IF NOT EXISTS hypothesis_history (
    hypothesis_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    case_type VARCHAR,  -- 'insider_threat', 'data_breach', etc.
    hypothesis_text TEXT NOT NULL,
    initial_confidence FLOAT,
    final_outcome VARCHAR,  -- 'accepted', 'rejected', 'modified', 'inconclusive'
    key_evidence JSON,  -- Evidence IDs that influenced outcome
    reviewer_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome_at TIMESTAMP,
    embedding_version VARCHAR,
    embedding_id VARCHAR  -- ChromaDB ID
);

-- Outcome store for learning loop
CREATE TABLE IF NOT EXISTS outcome_store (
    outcome_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    outcome_type VARCHAR,  -- 'case_closed', 'escalated', 'false_positive'
    metrics JSON,  -- {precision, recall, f1, review_time_minutes}
    reviewer_feedback TEXT,
    improvement_suggestions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Create File: `backend/app/services/longterm_memory.py`

```python
class LongTermMemoryService:
    """
    Long-term memory for cross-investigation learning.
    
    Usage:
        ltm = LongTermMemoryService()
        
        # Store hypothesis outcome
        ltm.record_hypothesis_outcome(
            hypothesis_id="h1",
            case_id="case1",
            hypothesis_text="Insider exfiltrated data via USB",
            outcome="accepted",
            key_evidence=["ev1", "ev2"]
        )
        
        # Get similar historical hypotheses
        similar = ltm.find_similar_hypotheses(
            "Data transfer to external device",
            case_type="insider_threat",
            top_k=5
        )
        
        # Get historical prior for hypothesis type
        prior = ltm.get_calibrated_prior("data_exfiltration")
    """
    
    def record_hypothesis_outcome(self, ...) -> None
    def record_case_outcome(self, case_id: str, outcome: CaseOutcome) -> None
    def find_similar_hypotheses(self, query: str, case_type: str, top_k: int) -> List[HistoricalHypothesis]
    def get_calibrated_prior(self, hypothesis_category: str, decay_days: int = 365) -> float
    def update_embeddings(self) -> int  # Re-embed all with current model
```

### Decay Weighting Implementation
```python
def get_calibrated_prior(self, category: str, decay_days: int = 365) -> float:
    """
    Calculate prior based on historical outcomes with decay.
    
    Formula: weight = exp(-age_days / half_life)
    Where half_life = decay_days / ln(2)
    """
    hypotheses = self._get_historical_hypotheses(category)
    
    weighted_accepted = 0
    weighted_total = 0
    half_life = decay_days / math.log(2)
    
    for h in hypotheses:
        age_days = (datetime.now() - h.outcome_at).days
        weight = math.exp(-age_days / half_life)
        
        weighted_total += weight
        if h.outcome == "accepted":
            weighted_accepted += weight
    
    if weighted_total == 0:
        return 0.5  # Default prior
    
    return weighted_accepted / weighted_total
```

### Testing
```python
ltm = LongTermMemoryService()

# Record some historical outcomes
ltm.record_hypothesis_outcome(
    hypothesis_id="h1", case_id="case1",
    hypothesis_text="User exfiltrated data via USB",
    outcome="accepted", key_evidence=["ev1"]
)
ltm.record_hypothesis_outcome(
    hypothesis_id="h2", case_id="case2",
    hypothesis_text="Data theft via email attachment",
    outcome="rejected", key_evidence=["ev2"]
)

# Get similar hypotheses for new investigation
similar = ltm.find_similar_hypotheses("Suspicious USB activity detected")
assert len(similar) > 0

# Get calibrated prior
prior = ltm.get_calibrated_prior("data_exfiltration")
assert 0 < prior < 1
```
```

#### Claude Opus 4.5 Prompt (Phase 4 - Iteration 2)

```markdown
## TASK: Implement Hypothesis Calibration Service

### Context
Phase 4, Iteration 2. Long-term memory complete. Now calibration.

### Requirements
Hypothesis calibration that:
1. Computes Bayesian priors from historical data
2. Updates posteriors based on evidence
3. Tracks calibration accuracy (predicted vs actual)
4. Monitors for calibration drift
5. Integrates with hypothesis_agent.py

### Create File: `backend/app/services/hypothesis_calibration.py`

```python
class HypothesisCalibrationService:
    """
    Bayesian hypothesis calibration from historical outcomes.
    
    Usage:
        hcs = HypothesisCalibrationService()
        
        # Get prior for new hypothesis
        prior = hcs.get_prior(
            hypothesis_category="data_exfiltration",
            case_type="insider_threat"
        )
        
        # Update with evidence
        posterior = hcs.update_posterior(
            prior=prior,
            evidence=[
                EvidenceFactor(factor="USB_activity", likelihood_ratio=3.5),
                EvidenceFactor(factor="after_hours_access", likelihood_ratio=2.0)
            ]
        )
        
        # Check calibration accuracy
        calibration = hcs.check_calibration()
        # Returns: {"90%_bucket": {"predicted": 0.90, "actual": 0.87}, ...}
    """
    
    def get_prior(self, hypothesis_category: str, case_type: str = None) -> float
    def update_posterior(self, prior: float, evidence: List[EvidenceFactor]) -> float
    def record_prediction(self, hypothesis_id: str, predicted_prob: float) -> None
    def record_actual_outcome(self, hypothesis_id: str, actual_outcome: bool) -> None
    def check_calibration(self) -> CalibrationReport
    def get_calibration_drift_alert(self) -> Optional[str]
```

### Integration with hypothesis_agent.py
```python
# In hypothesis_agent.py, modify hypothesis generation:
async def generate_hypotheses(self, scenario: str, evidence: List) -> List[Hypothesis]:
    # Get calibrated priors
    calibration = HypothesisCalibrationService()
    
    # Generate hypotheses with LLM
    raw_hypotheses = await self._llm_generate(scenario, evidence)
    
    # Apply calibrated priors
    for h in raw_hypotheses:
        historical_prior = calibration.get_prior(
            hypothesis_category=h.category,
            case_type=self.case_type
        )
        
        # Blend LLM confidence with historical prior
        h.confidence = self._blend_confidence(
            llm_confidence=h.confidence,
            historical_prior=historical_prior,
            evidence_strength=h.evidence_strength
        )
    
    return raw_hypotheses
```

### Testing
```python
hcs = HypothesisCalibrationService()

# Simulate historical data
for _ in range(100):
    # Record predictions
    hcs.record_prediction("h1", predicted_prob=0.8)
    hcs.record_actual_outcome("h1", actual_outcome=random.random() < 0.75)

# Check calibration
report = hcs.check_calibration()
# Should show some discrepancy between predicted ~0.8 and actual ~0.75
```
```

---

### PHASE 5: PROCEDURAL MEMORY
**Duration: 2-3 days | Priority: MEDIUM**

#### Why This Phase
Procedural memory enables:
- Learning approved report templates
- Consistent style across reports
- Quality-scored template retrieval
- 35-55% better report consistency

#### What We Build

```
Phase 5 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Procedural Memory System                                        │
├─────────────────────────────────────────────────────────────────┤
│ Storage:                                                        │
│   - DuckDB: procedural_templates table                         │
│   - ChromaDB: procedural_vectors collection                    │
│                                                                 │
│ Components:                                                     │
│   - ProceduralMemoryService (new)                              │
│   - Quality scoring for templates                               │
│   - Style extraction from approved reports                      │
│   - Audience profile matching                                   │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/procedural_memory.py` | Template learning | 400 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/database.py` | Add procedural_templates table | 25 |
| `backend/app/services/template_library.py` | Use procedural memory | 80 |
| `backend/app/services/auto_report_builder.py` | Retrieve templates dynamically | 100 |
| `backend/app/agents/integration_layer.py` | Use procedural templates | 80 |

#### Claude Opus 4.5 Prompt (Phase 5)

```markdown
## TASK: Implement Procedural Memory for Report Templates

### Requirements
Create procedural memory that:
1. Stores approved report templates with quality scores
2. Extracts style exemplars from approved reports
3. Retrieves templates by semantic similarity + quality
4. Tracks audience profiles (technical, executive, legal)
5. Only retrieves "gold corpus" (quality_score > 0.8)

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS procedural_templates (
    template_id VARCHAR PRIMARY KEY,
    template_type VARCHAR NOT NULL,  -- 'section', 'full_report', 'style'
    audience VARCHAR NOT NULL,  -- 'technical', 'executive', 'legal', 'general'
    content JSON NOT NULL,
    quality_score FLOAT DEFAULT 0.5,
    usage_count INT DEFAULT 0,
    approval_status VARCHAR DEFAULT 'pending',  -- 'pending', 'approved', 'deprecated'
    created_from_case VARCHAR,  -- Original case ID if extracted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by VARCHAR,
    approved_at TIMESTAMP
);
```

### Create File: `backend/app/services/procedural_memory.py`

```python
class ProceduralMemoryService:
    """
    Procedural memory for report templates and styles.
    
    Usage:
        pm = ProceduralMemoryService()
        
        # Extract template from approved report
        pm.learn_from_report(
            case_id="case1",
            report_content=report_json,
            audience="executive",
            quality_score=0.95
        )
        
        # Find relevant templates
        templates = pm.find_templates(
            context="Data breach summary for C-level",
            audience="executive",
            top_k=3
        )
        
        # Get style exemplar
        style = pm.get_style_exemplar("executive")
    """
    
    def learn_from_report(self, case_id: str, report: dict, audience: str, quality: float) -> str
    def find_templates(self, context: str, audience: str, top_k: int, min_quality: float = 0.8) -> List
    def get_style_exemplar(self, audience: str) -> StyleExemplar
    def update_quality_score(self, template_id: str, delta: float) -> None
    def deprecate_template(self, template_id: str, reason: str) -> None
```

### Quality Scoring
```python
# Quality score increases with:
# - Approval by senior reviewer (+0.1)
# - Successful court acceptance (+0.2)
# - Positive reviewer edits ratio (few edits = high quality)
# - Reuse in new reports (+0.05 per reuse)

# Quality score decreases with:
# - Heavy editing required (-0.1)
# - Rejection feedback (-0.15)
# - Age without reuse (decay)
```
```

---

### PHASE 6: VALIDATION MEMORY (CLAIM VERIFICATION)
**Duration: 3-4 days | Priority: HIGH**

#### Why This Phase
This is the **most impactful new capability**. Currently, there is NO system to verify that report claims are supported by evidence. This causes:
- Hallucinated claims in reports
- Unsupported conclusions
- Legal/compliance risk

Validation Memory provides:
- Claim extraction from report text
- Evidence linking per claim
- Contradiction detection
- 50-75% fewer unsupported claims

#### What We Build

```
Phase 6 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Validation Memory System (NEW)                                  │
├─────────────────────────────────────────────────────────────────┤
│ Storage:                                                        │
│   - DuckDB: validation_claims, claim_evidence_links,           │
│             claim_contradictions                                │
│   - ChromaDB: claim_vectors collection                         │
│                                                                 │
│ Components:                                                     │
│   - ClaimExtractor (LLM-based)                                 │
│   - ClaimValidator                                             │
│   - ContradictionDetector                                      │
│   - Verification gate (advisory mode)                          │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/claim_validator.py` | Full validation pipeline | 600 |
| `backend/app/services/claim_extractor.py` | LLM claim extraction | 300 |
| `backend/app/services/contradiction_detector.py` | Find contradictions | 250 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/database.py` | Add 3 validation tables | 50 |
| `backend/app/services/writer_agent.py` | Add verification gate | 100 |
| `backend/app/services/auto_report_builder.py` | Validate before export | 80 |
| `backend/app/services/deep_research/hypothesis_report_binder.py` | Claim extraction | 100 |
| `backend/app/routes/report_sections.py` | Add validation endpoint | 60 |

#### Claude Opus 4.5 Prompt (Phase 6 - Iteration 1)

```markdown
## TASK: Implement Claim Extraction and Validation Memory

### Context
Phase 6 - Most impactful new capability. No existing claim verification.

### Requirements
1. Extract atomic claims from report text using LLM
2. Link claims to supporting evidence
3. Detect unsupported claims (no evidence links)
4. Advisory mode: flag but don't block

### Database Schema
```sql
-- Atomic claims extracted from reports
CREATE TABLE IF NOT EXISTS validation_claims (
    claim_id VARCHAR PRIMARY KEY,
    case_id VARCHAR NOT NULL,
    section_id VARCHAR,
    claim_text TEXT NOT NULL,
    claim_type VARCHAR,  -- 'factual', 'inference', 'conclusion', 'recommendation'
    verification_status VARCHAR DEFAULT 'pending',  -- 'pending', 'supported', 'unsupported', 'contradicted'
    support_score FLOAT,  -- 0-1 confidence that claim is supported
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links between claims and evidence
CREATE TABLE IF NOT EXISTS claim_evidence_links (
    link_id VARCHAR PRIMARY KEY,
    claim_id VARCHAR NOT NULL,
    evidence_id VARCHAR NOT NULL,
    link_type VARCHAR NOT NULL,  -- 'supports', 'partially_supports', 'contradicts'
    confidence FLOAT DEFAULT 0.5,
    created_by VARCHAR,  -- 'system' | 'user'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Contradictions between claims
CREATE TABLE IF NOT EXISTS claim_contradictions (
    contradiction_id VARCHAR PRIMARY KEY,
    claim_id_1 VARCHAR NOT NULL,
    claim_id_2 VARCHAR NOT NULL,
    contradiction_type VARCHAR,  -- 'direct', 'logical', 'temporal'
    explanation TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Create File: `backend/app/services/claim_extractor.py`

```python
class ClaimExtractor:
    """
    Extract atomic claims from report text using LLM.
    
    Usage:
        ce = ClaimExtractor()
        claims = await ce.extract_claims(
            text="The attacker exfiltrated 500GB of data between 2-4 AM.",
            section_id="findings-1"
        )
        # Returns:
        # [
        #   Claim(text="An attacker exfiltrated data", type="factual"),
        #   Claim(text="The amount exfiltrated was 500GB", type="factual"),
        #   Claim(text="Exfiltration occurred between 2-4 AM", type="factual")
        # ]
    """
    
    EXTRACTION_PROMPT = '''
    Extract all atomic claims from this text. Each claim should be:
    - A single, verifiable statement
    - Self-contained (understandable without context)
    - Categorized as: factual, inference, conclusion, or recommendation
    
    Text:
    {text}
    
    Return JSON array:
    [
      {"text": "claim text", "type": "factual|inference|conclusion|recommendation"}
    ]
    '''
    
    async def extract_claims(self, text: str, section_id: str) -> List[Claim]
```

### Create File: `backend/app/services/claim_validator.py`

```python
class ClaimValidator:
    """
    Validate claims against evidence.
    
    Usage:
        cv = ClaimValidator(case_id)
        
        # Validate single claim
        result = await cv.validate_claim(claim)
        # Returns: ValidationResult(status='supported', evidence=['ev1'], score=0.85)
        
        # Validate entire report
        report = await cv.validate_report(report_json)
        # Returns: ReportValidation with all claims and their status
        
        # Get unsupported claims
        unsupported = cv.get_unsupported_claims()
    """
    
    async def validate_claim(self, claim: Claim) -> ValidationResult
    async def validate_report(self, report: dict) -> ReportValidation
    async def find_supporting_evidence(self, claim: Claim, top_k: int = 5) -> List[Evidence]
    def get_unsupported_claims(self) -> List[Claim]
    def get_validation_summary(self) -> ValidationSummary
```

### Testing
```python
# Extract claims
ce = ClaimExtractor()
claims = await ce.extract_claims(
    "User John Smith logged in 47 times from Russia. This is suspicious."
)
assert len(claims) >= 2

# Validate
cv = ClaimValidator("case1")
result = await cv.validate_claim(claims[0])
print(result.status)  # 'supported' or 'unsupported'
```
```

#### Claude Opus 4.5 Prompt (Phase 6 - Iteration 2)

```markdown
## TASK: Implement Contradiction Detection

### Context
Phase 6, Iteration 2. Claim extraction/validation complete. Now contradictions.

### Requirements
Detect contradictions:
1. Between claims in the same report
2. Between claims and evidence
3. Temporal contradictions (timeline inconsistencies)

### Create File: `backend/app/services/contradiction_detector.py`

```python
class ContradictionDetector:
    """
    Detect contradictions between claims.
    
    Usage:
        cd = ContradictionDetector(case_id)
        
        # Check for contradictions
        contradictions = await cd.find_contradictions(claims)
        
        # Types of contradictions:
        # - Direct: "User was in New York" vs "User was in London" (same time)
        # - Logical: "No data was accessed" vs "500GB exfiltrated"
        # - Temporal: Timeline inconsistencies
    """
    
    CONTRADICTION_PROMPT = '''
    Analyze these two claims for contradictions:
    
    Claim 1: {claim1}
    Claim 2: {claim2}
    
    Do they contradict each other? Consider:
    - Direct contradiction (opposite facts)
    - Logical contradiction (can't both be true)
    - Temporal contradiction (timeline conflict)
    
    Return JSON:
    {
      "contradicts": true/false,
      "type": "direct|logical|temporal|none",
      "explanation": "why they contradict"
    }
    '''
    
    async def find_contradictions(self, claims: List[Claim]) -> List[Contradiction]
    async def check_pair(self, claim1: Claim, claim2: Claim) -> Optional[Contradiction]
    async def check_against_evidence(self, claim: Claim) -> Optional[Contradiction]
```

### Integration with writer_agent.py
```python
# In writer_agent.py, after generating section:
async def generate_section(self, section_type: str, context: dict) -> Section:
    # Generate content
    content = await self._llm_generate(section_type, context)
    
    # Extract and validate claims (advisory mode)
    extractor = ClaimExtractor()
    claims = await extractor.extract_claims(content)
    
    validator = ClaimValidator(self.case_id)
    validation = await validator.validate_claims(claims)
    
    contradiction_detector = ContradictionDetector(self.case_id)
    contradictions = await contradiction_detector.find_contradictions(claims)
    
    # Flag issues but don't block (advisory mode)
    if validation.unsupported_count > 0:
        content = self._add_warning_annotations(content, validation.unsupported_claims)
    
    if contradictions:
        content = self._add_contradiction_warnings(content, contradictions)
    
    return Section(content=content, validation=validation)
```
```

---

### PHASE 7: RETRIEVAL QUALITY ENHANCEMENT
**Duration: 2-3 days | Priority: MEDIUM**

#### Why This Phase
Better retrieval means:
- More relevant evidence found
- Higher precision in hypothesis testing
- 30-50% higher Precision@K

#### What We Build

```
Phase 7 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Retrieval Quality System                                        │
├─────────────────────────────────────────────────────────────────┤
│ Components:                                                     │
│   - HybridRetriever (BM25 + semantic + rerank)                 │
│   - CrossEncoderReranker                                       │
│   - RetrievalQualityMetrics (MRR, NDCG, P@K)                  │
│   - Staged tuning with KPI gates                               │
│   - Fallback search for edge cases                             │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/hybrid_retriever.py` | BM25 + semantic + RRF | 400 |
| `backend/app/services/reranker.py` | Cross-encoder reranking | 200 |
| `backend/app/services/retrieval_quality.py` | Metrics + KPI gates | 250 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/agents/research/knowledge_base.py` | Use hybrid retriever | 100 |
| `backend/app/tools/vault_tool.py` | Enhanced search | 60 |
| `backend/app/services/findings_vault.py` | Use HybridRetriever | 50 |

#### Claude Opus 4.5 Prompt (Phase 7)

```markdown
## TASK: Implement Hybrid Retriever with Reranking

### Requirements
1. Combine BM25 (lexical) + semantic search
2. Reciprocal Rank Fusion for merging
3. Cross-encoder reranking for precision
4. Quality metrics (MRR, NDCG, P@K)

### Create File: `backend/app/services/hybrid_retriever.py`

```python
class HybridRetriever:
    """
    Hybrid search combining BM25 + semantic + reranking.
    
    Usage:
        hr = HybridRetriever(case_id)
        
        results = await hr.search(
            query="unauthorized data transfer",
            collection="evidence_vectors",
            top_k=10,
            alpha=0.5,  # Balance between BM25 and semantic
            rerank=True
        )
    """
    
    def __init__(self, case_id: str):
        self.bm25_index = BM25Index(case_id)
        self.vector_store = VectorStoreManager()
        self.reranker = CrossEncoderReranker()
    
    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 10,
        alpha: float = 0.5,  # 0 = all BM25, 1 = all semantic
        rerank: bool = True,
        rerank_top_n: int = 30
    ) -> List[SearchResult]:
        # 1. BM25 search (lexical)
        bm25_results = self.bm25_index.search(query, top_k=rerank_top_n)
        
        # 2. Semantic search
        semantic_results = self.vector_store.search(collection, query, top_k=rerank_top_n)
        
        # 3. Reciprocal Rank Fusion
        fused = self._reciprocal_rank_fusion(bm25_results, semantic_results, alpha)
        
        # 4. Rerank with cross-encoder
        if rerank:
            reranked = await self.reranker.rerank(query, fused[:rerank_top_n])
            return reranked[:top_k]
        
        return fused[:top_k]
    
    def _reciprocal_rank_fusion(
        self,
        results1: List,
        results2: List,
        alpha: float,
        k: int = 60  # RRF constant
    ) -> List:
        scores = {}
        
        for rank, r in enumerate(results1):
            scores[r.id] = scores.get(r.id, 0) + (1 - alpha) / (k + rank + 1)
        
        for rank, r in enumerate(results2):
            scores[r.id] = scores.get(r.id, 0) + alpha / (k + rank + 1)
        
        # Sort by fused score
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### Create File: `backend/app/services/reranker.py`

```python
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:
    """
    Rerank search results using cross-encoder.
    
    Cross-encoders are more accurate than bi-encoders because they
    see query+document together, but are slower (can't pre-compute).
    """
    
    MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Fast, good quality
    
    def __init__(self):
        self.model = CrossEncoder(self.MODEL)
    
    async def rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: int = None
    ) -> List[SearchResult]:
        # Prepare pairs
        pairs = [(query, c.text) for c in candidates]
        
        # Score all pairs
        scores = self.model.predict(pairs)
        
        # Sort by score
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        
        results = [c for c, s in scored]
        return results[:top_k] if top_k else results
```

### Testing
```python
hr = HybridRetriever("case1")

# Seed some evidence
vault = FindingsVault("case1")
await vault.add_finding(Finding(title="USB transfer at 2AM", ...))
await vault.add_finding(Finding(title="Email with attachment to external", ...))
await vault.add_finding(Finding(title="Normal login activity", ...))

# Search
results = await hr.search("data exfiltration method")
assert "USB" in results[0].title or "email" in results[0].title
```
```

---

### PHASE 8: LEARNING LOOP + API INTEGRATION
**Duration: 3-4 days | Priority: MEDIUM**

#### Why This Phase
Completes the feedback loop:
- Learn from reviewer edits
- Track court acceptance
- Monthly retraining of priors/templates
- 15-30% quality lift over time

#### What We Build

```
Phase 8 Architecture:
┌─────────────────────────────────────────────────────────────────┐
│ Learning Loop System                                            │
├─────────────────────────────────────────────────────────────────┤
│ Components:                                                     │
│   - LearningLoopService                                        │
│   - OutcomeAnalyzer                                            │
│   - FeedbackCollector                                          │
│   - Monthly retraining pipeline                                │
│   - API endpoints for all new features                         │
└─────────────────────────────────────────────────────────────────┘
```

#### Files Involved

**NEW FILES:**

| File | Purpose | Est. Lines |
|------|---------|------------|
| `backend/app/services/learning_loop.py` | Orchestrate learning | 350 |
| `backend/app/services/outcome_analyzer.py` | Analyze outcomes | 300 |
| `backend/app/services/feedback_collector.py` | Collect feedback | 200 |

**MODIFY:**

| File | Changes | Lines |
|------|---------|-------|
| `backend/app/routes/findings.py` | Add memory/search endpoints | 150 |
| `backend/app/routes/deep_research.py` | Add calibration endpoints | 100 |
| `backend/app/routes/studio_v4.py` | Add feedback endpoints | 100 |
| `backend/app/services/investigation_workflow.py` | Collect outcomes | 80 |

#### Claude Opus 4.5 Prompt (Phase 8)

```markdown
## TASK: Implement Learning Loop and API Integration

### Requirements
1. Collect feedback on reports (reviewer edits, court acceptance)
2. Analyze outcomes to identify improvement areas
3. Monthly retraining of templates, priors
4. API endpoints for all new features

### Create File: `backend/app/services/learning_loop.py`

```python
class LearningLoopService:
    """
    Orchestrate learning from feedback and outcomes.
    
    Usage:
        lls = LearningLoopService()
        
        # Record feedback
        lls.record_feedback(
            case_id="case1",
            feedback_type="reviewer_edit",
            section_id="findings-1",
            original_text="...",
            edited_text="...",
            reviewer_id="reviewer1"
        )
        
        # Record outcome
        lls.record_outcome(
            case_id="case1",
            outcome_type="court_accepted",
            metrics={"review_time_hours": 2.5}
        )
        
        # Trigger monthly retraining
        await lls.monthly_retrain()
    """
    
    async def record_feedback(self, case_id: str, feedback: Feedback) -> None
    async def record_outcome(self, case_id: str, outcome: Outcome) -> None
    async def monthly_retrain(self) -> RetrainReport
    async def get_improvement_suggestions(self, case_type: str) -> List[Suggestion]
```

### API Endpoints to Add

```python
# In routes/findings.py:

@router.post("/evidence/search/hybrid")
async def search_evidence_hybrid(
    case_id: str,
    query: str,
    top_k: int = 10,
    alpha: float = 0.5,
    rerank: bool = True
):
    """Hybrid search (BM25 + semantic + rerank)."""
    retriever = HybridRetriever(case_id)
    results = await retriever.search(query, "evidence_vectors", top_k, alpha, rerank)
    return {"results": results}

@router.post("/evidence/link")
async def link_evidence(
    case_id: str,
    source_id: str,
    target_id: str,
    relationship: str
):
    """Create relationship between evidence."""
    vault = FindingsVault(case_id)
    return await vault.link_evidence(source_id, target_id, relationship)

# In routes/deep_research.py:

@router.get("/calibration/priors/{hypothesis_category}")
async def get_calibrated_prior(hypothesis_category: str, case_type: str = None):
    """Get calibrated prior from historical data."""
    hcs = HypothesisCalibrationService()
    prior = hcs.get_prior(hypothesis_category, case_type)
    return {"prior": prior}

@router.get("/calibration/report")
async def get_calibration_report():
    """Get calibration accuracy report."""
    hcs = HypothesisCalibrationService()
    return hcs.check_calibration()

# In routes/studio_v4.py:

@router.post("/cases/{case_id}/feedback")
async def submit_feedback(case_id: str, feedback: FeedbackRequest):
    """Submit feedback on report."""
    lls = LearningLoopService()
    await lls.record_feedback(case_id, feedback)
    return {"status": "recorded"}

@router.post("/cases/{case_id}/validate-claims")
async def validate_report_claims(case_id: str, report_content: dict):
    """Validate all claims in report against evidence."""
    validator = ClaimValidator(case_id)
    result = await validator.validate_report(report_content)
    return result

# In routes/memory.py (NEW):

@router.get("/memory/session/{case_id}")
async def get_session_memory(case_id: str, phase: str = None):
    """Get session memory context."""
    sms = SessionMemoryService(case_id)
    if phase:
        return sms.get_all_for_phase(phase)
    return sms.get_all()

@router.get("/memory/longterm/similar")
async def find_similar_hypotheses(query: str, case_type: str = None, top_k: int = 5):
    """Find similar historical hypotheses."""
    ltm = LongTermMemoryService()
    return ltm.find_similar_hypotheses(query, case_type, top_k)

@router.get("/memory/templates")
async def get_templates(context: str, audience: str, top_k: int = 3):
    """Find relevant templates."""
    pm = ProceduralMemoryService()
    return pm.find_templates(context, audience, top_k)
```

### Testing
```python
# Full integration test
from app.services.learning_loop import LearningLoopService

lls = LearningLoopService()

# Simulate complete workflow
await lls.record_feedback("case1", Feedback(
    type="reviewer_edit",
    original="The attack was sophisticated",
    edited="The attack used known exploit CVE-2024-1234"
))

await lls.record_outcome("case1", Outcome(
    type="court_accepted",
    metrics={"review_time_hours": 2.5}
))

# Get suggestions
suggestions = await lls.get_improvement_suggestions("insider_threat")
print(suggestions)
```
```

---

## COMPLETE FILE SUMMARY

### NEW FILES TO CREATE (13 total)

| # | File | Phase | Lines |
|---|------|-------|-------|
| 1 | `backend/app/services/embedding_service.py` | 1 | 250 |
| 2 | `backend/app/services/vector_store.py` | 1 | 400 |
| 3 | `backend/app/models/vector_types.py` | 1 | 100 |
| 4 | `backend/app/services/bm25_index.py` | 2 | 200 |
| 5 | `backend/app/services/session_memory.py` | 3 | 400 |
| 6 | `backend/app/services/longterm_memory.py` | 4 | 500 |
| 7 | `backend/app/services/hypothesis_calibration.py` | 4 | 400 |
| 8 | `backend/app/services/procedural_memory.py` | 5 | 400 |
| 9 | `backend/app/services/claim_extractor.py` | 6 | 300 |
| 10 | `backend/app/services/claim_validator.py` | 6 | 600 |
| 11 | `backend/app/services/contradiction_detector.py` | 6 | 250 |
| 12 | `backend/app/services/hybrid_retriever.py` | 7 | 400 |
| 13 | `backend/app/services/reranker.py` | 7 | 200 |
| 14 | `backend/app/services/retrieval_quality.py` | 7 | 250 |
| 15 | `backend/app/services/learning_loop.py` | 8 | 350 |
| 16 | `backend/app/services/outcome_analyzer.py` | 8 | 300 |
| 17 | `backend/app/services/feedback_collector.py` | 8 | 200 |
| 18 | `backend/app/routes/memory.py` | 8 | 150 |

**Total new code: ~5,650 lines**

### FILES TO MODIFY (25 total)

| # | File | Phases | Est. Changes |
|---|------|--------|--------------|
| 1 | `backend/requirements.txt` | 1 | 5 lines |
| 2 | `backend/app/config.py` | 1,2 | 30 lines |
| 3 | `backend/app/database.py` | 2,3,4,5,6 | 150 lines |
| 4 | `backend/app/main.py` | 1 | 15 lines |
| 5 | `backend/app/services/findings_vault.py` | 2,7 | 250 lines |
| 6 | `backend/app/services/evidence_service.py` | 2 | 100 lines |
| 7 | `backend/app/models/evidence.py` | 2 | 80 lines |
| 8 | `backend/app/routes/findings.py` | 2,8 | 200 lines |
| 9 | `backend/app/tools/vault_tool.py` | 2,7 | 120 lines |
| 10 | `backend/app/services/chat_service.py` | 3 | 100 lines |
| 11 | `backend/app/services/deep_research/models.py` | 3 | 50 lines |
| 12 | `backend/app/agents/hypothesis/hypothesis_agent.py` | 4 | 150 lines |
| 13 | `backend/app/services/unified_orchestrator.py` | 4 | 100 lines |
| 14 | `backend/app/services/deep_research/llm_hypothesis_generator.py` | 4 | 100 lines |
| 15 | `backend/app/services/template_library.py` | 5 | 80 lines |
| 16 | `backend/app/services/auto_report_builder.py` | 5,6 | 180 lines |
| 17 | `backend/app/agents/integration_layer.py` | 5 | 80 lines |
| 18 | `backend/app/services/writer_agent.py` | 6 | 100 lines |
| 19 | `backend/app/services/deep_research/hypothesis_report_binder.py` | 6 | 100 lines |
| 20 | `backend/app/routes/report_sections.py` | 6 | 60 lines |
| 21 | `backend/app/agents/research/knowledge_base.py` | 7 | 100 lines |
| 22 | `backend/app/routes/deep_research.py` | 8 | 100 lines |
| 23 | `backend/app/routes/studio_v4.py` | 8 | 100 lines |
| 24 | `backend/app/services/investigation_workflow.py` | 8 | 80 lines |

**Total modifications: ~2,430 lines**

---

## DEPENDENCY INSTALLATION

Add to `backend/requirements.txt`:

```txt
# Oracle 26AI Open-Source Implementation
chromadb>=0.5.0                            # Vector database
sentence-transformers>=2.2.0               # Local embeddings
rank-bm25>=0.2.2                           # BM25 lexical search
# scikit-learn already present
# numpy already present
```

Install:
```bash
cd backend
pip install chromadb sentence-transformers rank-bm25
```

---

## TIMELINE SUMMARY

| Phase | Duration | Cumulative |
|-------|----------|------------|
| 1: Foundation | 3-4 days | Week 1 |
| 2: Evidence Vault | 3-4 days | Week 1-2 |
| 3: Session Memory | 2-3 days | Week 2 |
| 4: Long-term + Calibration | 3-4 days | Week 2-3 |
| 5: Procedural Memory | 2-3 days | Week 3 |
| 6: Validation Memory | 3-4 days | Week 3-4 |
| 7: Retrieval Quality | 2-3 days | Week 4 |
| 8: Learning Loop + APIs | 3-4 days | Week 4-5 |

**Total: ~22-29 days (5-6 weeks)**

---

## EXPECTED OUTCOMES

After implementation:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Evidence Traceability | 50% | 85%+ | +35-55% |
| Context Relevance | 60% | 80%+ | +20-35% |
| Token Waste | High | Low | -15-30% |
| Hypothesis Precision | 55% | 80%+ | +25-45% |
| Report Consistency | 60% | 95%+ | +35-55% |
| Unsupported Claims | 20%+ | <5% | -50-75% |
| Retrieval Precision@K | 0.5 | 0.75+ | +30-50% |
| Confidence Calibration | Poor | Good | +20-40% |
| Quarter-over-Quarter Quality | Flat | +15-30% | Continuous |

---

## TESTING STRATEGY

### 5.1 Unit Tests Per Phase

```
tests/
├── test_phase1_foundation/
│   ├── test_embedding_service.py      # Embedding generation
│   ├── test_vector_store.py           # ChromaDB operations
│   └── test_vector_types.py           # Pydantic models
│
├── test_phase2_evidence_vault/
│   ├── test_evidence_links.py         # Relationship tracking
│   ├── test_provenance_log.py         # Chain-of-custody
│   ├── test_bm25_index.py             # Lexical search
│   └── test_hybrid_search.py          # Combined search
│
├── test_phase3_session_memory/
│   ├── test_session_memory.py         # TTL and phase-awareness
│   ├── test_context_retrieval.py      # Relevant context
│   └── test_phase_transition.py       # Phase changes
│
├── test_phase4_longterm_calibration/
│   ├── test_longterm_memory.py        # Cross-investigation
│   ├── test_hypothesis_calibration.py # Bayesian priors
│   ├── test_decay_weighting.py        # Time-based decay
│   └── test_calibration_accuracy.py   # Predicted vs actual
│
├── test_phase5_procedural_memory/
│   ├── test_procedural_memory.py      # Template storage
│   ├── test_template_quality.py       # Quality scoring
│   └── test_template_search.py        # Semantic retrieval
│
├── test_phase6_validation_memory/
│   ├── test_claim_extractor.py        # LLM claim extraction
│   ├── test_claim_validator.py        # Evidence linking
│   ├── test_contradiction_detector.py # Contradiction finding
│   └── test_advisory_mode.py          # Non-blocking validation
│
├── test_phase7_retrieval_quality/
│   ├── test_hybrid_retriever.py       # BM25 + semantic
│   ├── test_reranker.py               # Cross-encoder
│   ├── test_rrf_fusion.py             # Reciprocal Rank Fusion
│   └── test_retrieval_metrics.py      # MRR, NDCG, P@K
│
└── test_phase8_learning_loop/
    ├── test_learning_loop.py          # Feedback collection
    ├── test_outcome_analyzer.py       # Outcome analysis
    ├── test_api_endpoints.py          # New API routes
    └── test_integration.py            # End-to-end flow
```

### 5.2 Integration Tests

```python
# tests/integration/test_full_pipeline.py

import pytest
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreManager
from app.services.findings_vault import FindingsVault
from app.services.session_memory import SessionMemoryService
from app.services.longterm_memory import LongTermMemoryService
from app.services.claim_validator import ClaimValidator
from app.services.hybrid_retriever import HybridRetriever
from app.services.learning_loop import LearningLoopService


class TestFullPipeline:
    """Integration tests for complete Oracle 26AI open-source implementation."""
    
    @pytest.fixture
    def case_id(self):
        return "test_case_001"
    
    @pytest.fixture
    async def setup_case(self, case_id):
        """Create test case with sample data."""
        vault = FindingsVault(case_id)
        
        # Add sample findings
        findings = [
            {"title": "Suspicious USB activity", "description": "Large file transfer to USB at 2AM", "category": "data_exfiltration"},
            {"title": "Email to external domain", "description": "User sent 500MB attachment to personal email", "category": "data_exfiltration"},
            {"title": "VPN login from Russia", "description": "User account accessed from unusual location", "category": "unauthorized_access"},
            {"title": "Admin password change", "description": "Domain admin password changed without ticket", "category": "privilege_abuse"},
        ]
        
        finding_ids = []
        for f in findings:
            fid = await vault.add_finding(f)
            finding_ids.append(fid)
        
        return finding_ids
    
    async def test_1_embedding_generation(self):
        """Test embedding service works."""
        embedding_svc = EmbeddingService()
        vec = embedding_svc.embed_text("test embedding for forensic evidence")
        
        assert len(vec) == 384  # MiniLM dimension
        assert all(isinstance(v, float) for v in vec)
    
    async def test_2_vector_store_operations(self, case_id, setup_case):
        """Test vector store CRUD."""
        vsm = VectorStoreManager()
        
        # Add document
        vsm.add_document(
            collection=f"case_{case_id}_evidence",
            id="test_doc_1",
            text="Suspicious network activity detected",
            metadata={"case_id": case_id, "type": "network"}
        )
        
        # Search
        results = vsm.search(
            collection=f"case_{case_id}_evidence",
            query="network anomaly",
            top_k=5
        )
        
        assert len(results) > 0
        
        # Delete
        vsm.delete(f"case_{case_id}_evidence", ["test_doc_1"])
    
    async def test_3_hybrid_retrieval(self, case_id, setup_case):
        """Test hybrid search (BM25 + semantic + rerank)."""
        retriever = HybridRetriever(case_id)
        
        results = await retriever.search(
            query="data theft external transfer",
            collection=f"case_{case_id}_evidence",
            top_k=3,
            alpha=0.5,
            rerank=True
        )
        
        assert len(results) > 0
        # USB or Email findings should rank high
        top_titles = [r.title.lower() for r in results[:2]]
        assert any("usb" in t or "email" in t for t in top_titles)
    
    async def test_4_session_memory(self, case_id):
        """Test session memory TTL and phase-awareness."""
        sms = SessionMemoryService(case_id)
        
        # Store in hypothesis phase
        sms.store("hypothesis", {
            "type": "entity",
            "content": {"name": "John Smith", "role": "suspect"}
        })
        
        # Retrieve context
        context = sms.get_relevant_context(
            query="What do we know about John?",
            phase="hypothesis",
            max_tokens=500
        )
        
        assert "John Smith" in context
        
        # Phase transition
        sms.transition_phase("hypothesis", "analysis")
    
    async def test_5_claim_validation_advisory(self, case_id, setup_case):
        """Test claim validation in advisory mode."""
        validator = ClaimValidator(case_id)
        
        # Test report text with claims
        report_text = """
        The investigation found that the suspect transferred 500MB of data via USB.
        The data exfiltration occurred at 2AM on March 15th.
        The suspect had authorized access to the data.
        """
        
        validation = await validator.validate_report({"content": report_text})
        
        # Should have claims extracted
        assert validation.total_claims > 0
        
        # Advisory mode: should NOT block
        assert validation.can_export == True
        
        # But should flag unsupported claims
        assert hasattr(validation, 'unsupported_claims')
    
    async def test_6_learning_loop_feedback(self, case_id):
        """Test feedback collection and outcome recording."""
        lls = LearningLoopService()
        
        # Record reviewer feedback
        await lls.record_feedback(
            case_id=case_id,
            feedback={
                "type": "reviewer_edit",
                "section_id": "findings-1",
                "original": "The attack was sophisticated",
                "edited": "The attack used CVE-2024-1234"
            }
        )
        
        # Record case outcome
        await lls.record_outcome(
            case_id=case_id,
            outcome={
                "type": "case_closed",
                "metrics": {"review_time_hours": 2.5, "edit_count": 3}
            }
        )
        
        # Get improvement suggestions
        suggestions = await lls.get_improvement_suggestions("insider_threat")
        assert isinstance(suggestions, list)
    
    async def test_7_hypothesis_calibration(self):
        """Test calibrated priors from historical data."""
        from app.services.hypothesis_calibration import HypothesisCalibrationService
        
        hcs = HypothesisCalibrationService()
        
        # Get prior for hypothesis category
        prior = hcs.get_prior(
            hypothesis_category="data_exfiltration",
            case_type="insider_threat"
        )
        
        assert 0.0 <= prior <= 1.0
    
    async def test_8_end_to_end_investigation(self, case_id, setup_case):
        """Full end-to-end test simulating complete investigation."""
        # Phase 1: Evidence ingestion (already done in setup)
        
        # Phase 2: Session context building
        sms = SessionMemoryService(case_id)
        sms.store("intake", {
            "type": "context",
            "content": {"scenario": "Suspected insider data theft"}
        })
        
        # Phase 3: Hypothesis retrieval with calibration
        from app.services.hypothesis_calibration import HypothesisCalibrationService
        hcs = HypothesisCalibrationService()
        ltm = LongTermMemoryService()
        
        similar = ltm.find_similar_hypotheses(
            "employee stealing data via USB",
            case_type="insider_threat",
            top_k=3
        )
        
        prior = hcs.get_prior("data_exfiltration", "insider_threat")
        
        # Phase 4: Evidence search
        retriever = HybridRetriever(case_id)
        evidence = await retriever.search(
            query="data transfer external",
            collection=f"case_{case_id}_evidence",
            top_k=5
        )
        
        # Phase 5: Report validation
        validator = ClaimValidator(case_id)
        report = {
            "content": f"Based on {len(evidence)} pieces of evidence, data was exfiltrated."
        }
        validation = await validator.validate_report(report)
        
        # Phase 6: Learning loop
        lls = LearningLoopService()
        await lls.record_outcome(
            case_id=case_id,
            outcome={"type": "case_closed", "metrics": {"success": True}}
        )
        
        # All phases should complete without error
        assert True
```

### 5.3 Performance Benchmarks

```python
# tests/benchmarks/test_performance.py

import time
import pytest
from app.services.embedding_service import EmbeddingService
from app.services.hybrid_retriever import HybridRetriever


class TestPerformance:
    """Performance benchmarks for memory systems."""
    
    async def test_embedding_throughput(self):
        """Embedding should process 100 texts in < 5 seconds."""
        svc = EmbeddingService()
        texts = [f"Sample forensic evidence text number {i}" for i in range(100)]
        
        start = time.time()
        embeddings = svc.embed_batch(texts)
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Embedding took {elapsed}s, expected < 5s"
        assert len(embeddings) == 100
    
    async def test_hybrid_search_latency(self, case_id_with_1000_docs):
        """Hybrid search should return in < 500ms for 1000 documents."""
        retriever = HybridRetriever(case_id_with_1000_docs)
        
        start = time.time()
        results = await retriever.search(
            query="unauthorized access attempt",
            collection=f"case_{case_id_with_1000_docs}_evidence",
            top_k=10
        )
        elapsed = time.time() - start
        
        assert elapsed < 0.5, f"Search took {elapsed}s, expected < 0.5s"
    
    async def test_claim_extraction_latency(self):
        """Claim extraction should complete in < 3s per section."""
        from app.services.claim_extractor import ClaimExtractor
        
        extractor = ClaimExtractor()
        section_text = """
        The investigation revealed multiple indicators of compromise.
        The attacker gained initial access through a phishing email.
        Subsequently, lateral movement was detected across 5 systems.
        Data exfiltration totaling 2.3GB occurred over 48 hours.
        The attack was attributed to APT29 based on TTPs.
        """
        
        start = time.time()
        claims = await extractor.extract_claims(section_text)
        elapsed = time.time() - start
        
        assert elapsed < 3.0, f"Extraction took {elapsed}s, expected < 3s"
        assert len(claims) >= 3
```

---

## IMPLEMENTATION CHECKLIST

### Pre-Implementation
- [ ] Review and approve this plan
- [ ] Ensure Python 3.10+ environment
- [ ] Verify sufficient disk space for ChromaDB (estimate: 10GB)
- [ ] Confirm GPU availability (optional, for faster embeddings)
- [ ] Back up existing database files

### Phase 1: Foundation
- [ ] Install dependencies: `pip install chromadb sentence-transformers rank-bm25`
- [ ] Create `embedding_service.py` with singleton pattern
- [ ] Create `vector_store.py` with ChromaDB wrapper
- [ ] Create `vector_types.py` Pydantic models
- [ ] Update `config.py` with embedding settings
- [ ] Add initialization to `main.py` startup
- [ ] Run Phase 1 tests: `pytest tests/test_phase1_foundation/`

### Phase 2: Evidence Vault
- [ ] Add tables to `database.py`: evidence_links, embeddings_registry, provenance_log
- [ ] Create `bm25_index.py` for lexical search
- [ ] Modify `findings_vault.py` for vector operations
- [ ] Modify `evidence_service.py` for provenance tracking
- [ ] Update `models/evidence.py` with new models
- [ ] Add endpoints to `routes/findings.py`
- [ ] Run Phase 2 tests: `pytest tests/test_phase2_evidence_vault/`

### Phase 3: Session Memory
- [ ] Add session_memory table to `database.py`
- [ ] Create `session_memory.py` service
- [ ] Integrate with `chat_service.py`
- [ ] Update `deep_research/models.py`
- [ ] Run Phase 3 tests: `pytest tests/test_phase3_session_memory/`

### Phase 4: Long-term Memory + Calibration
- [ ] Create global.duckdb with hypothesis_history, outcome_store tables
- [ ] Create `longterm_memory.py` service
- [ ] Create `hypothesis_calibration.py` service
- [ ] Integrate with `hypothesis_agent.py`
- [ ] Integrate with `unified_orchestrator.py`
- [ ] Run Phase 4 tests: `pytest tests/test_phase4_longterm_calibration/`

### Phase 5: Procedural Memory
- [ ] Add procedural_templates table to global.duckdb
- [ ] Create `procedural_memory.py` service
- [ ] Integrate with `template_library.py`
- [ ] Integrate with `auto_report_builder.py`
- [ ] Run Phase 5 tests: `pytest tests/test_phase5_procedural_memory/`

### Phase 6: Validation Memory
- [ ] Add validation_claims, claim_evidence_links, claim_contradictions tables
- [ ] Create `claim_extractor.py` with LLM prompts
- [ ] Create `claim_validator.py` for evidence linking
- [ ] Create `contradiction_detector.py`
- [ ] Integrate advisory gate in `writer_agent.py`
- [ ] Add endpoints to `routes/report_sections.py`
- [ ] Run Phase 6 tests: `pytest tests/test_phase6_validation_memory/`

### Phase 7: Retrieval Quality
- [ ] Create `hybrid_retriever.py` with RRF
- [ ] Create `reranker.py` with cross-encoder
- [ ] Create `retrieval_quality.py` metrics
- [ ] Integrate with `knowledge_base.py`
- [ ] Run Phase 7 tests: `pytest tests/test_phase7_retrieval_quality/`

### Phase 8: Learning Loop + APIs
- [ ] Add feedback_log, calibration_metrics tables
- [ ] Create `learning_loop.py` service
- [ ] Create `outcome_analyzer.py` service
- [ ] Create `routes/memory.py` with new endpoints
- [ ] Update all routes with new endpoints
- [ ] Run Phase 8 tests: `pytest tests/test_phase8_learning_loop/`

### Post-Implementation
- [ ] Run full integration tests: `pytest tests/integration/`
- [ ] Run performance benchmarks: `pytest tests/benchmarks/`
- [ ] Update API documentation
- [ ] Deploy to staging environment
- [ ] Conduct user acceptance testing
- [ ] Deploy to production

---

## RISK MITIGATION

| Risk | Impact | Mitigation |
|------|--------|------------|
| ChromaDB performance at scale | High | Add indexes, implement pagination, consider Qdrant migration path |
| Embedding model drift | Medium | Track embedding_version, quarterly re-embedding job |
| LLM claim extraction inconsistency | Medium | Add validation, fallback to rule-based for critical claims |
| Session memory TTL conflicts | Low | Implement conflict detection, user override option |
| Cross-encoder reranking latency | Low | Make reranking optional, cache frequent queries |
| Global database contention | Medium | Implement connection pooling, read replicas |

---

## NEXT STEPS

### Immediate Actions

1. **Confirm this plan** - Review all sections, ask clarifying questions
2. **Install dependencies** - Run pip install for Phase 1
3. **Start Phase 1** - Use the Claude Opus 4.5 prompts provided

### Phase Execution Pattern

For each phase, follow this pattern:

```
1. READ the Claude Opus 4.5 prompt for the phase
2. EXECUTE Iteration 1 (create core files)
3. TEST with provided test cases
4. EXECUTE Iteration 2 (integration + edge cases)
5. TEST full phase tests
6. VERIFY with integration tests
7. MOVE to next phase
```

### Ready to Start?

**Would you like me to begin Phase 1 implementation now?**

This will:
1. Create `embedding_service.py`
2. Create `vector_store.py`  
3. Create `vector_types.py`
4. Update `config.py`
5. Update `requirements.txt`
6. Initialize in `main.py`

---

## APPENDIX: CLAUDE OPUS 4.5 PROMPT REFERENCE

All Claude Opus 4.5 prompts are embedded in each phase section above. For quick reference:

| Phase | Prompt Location | Iterations |
|-------|-----------------|------------|
| 1: Foundation | Section 6.1 | 2 (Embedding + VectorStore) |
| 2: Evidence Vault | Section 6.2 | 2 (Schema + Hybrid Search) |
| 3: Session Memory | Section 6.3 | 1 (Complete service) |
| 4: Long-term + Calibration | Section 6.4 | 2 (LTM + Calibration) |
| 5: Procedural Memory | Section 6.5 | 1 (Complete service) |
| 6: Validation Memory | Section 6.6 | 2 (Extraction + Contradiction) |
| 7: Retrieval Quality | Section 6.7 | 1 (Complete pipeline) |
| 8: Learning Loop | Section 6.8 | 1 (Complete + APIs) |

---

*Document Version: 1.0*
*Created: April 2026*
*Last Updated: April 2026*
*Total Estimated Implementation: 5-6 weeks*
*Total New Code: ~5,650 lines*
*Total Modifications: ~2,430 lines*
