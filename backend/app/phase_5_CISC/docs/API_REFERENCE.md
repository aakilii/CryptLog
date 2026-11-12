# API Reference

## Complete REST API Documentation

Base URL: `http://localhost:8000`

---

## Table of Contents

1. [Investigation API](#investigation-api)
2. [Augment Studio API](#augment-studio-api)
3. [Universal Tools API](#universal-tools-api)
4. [Entity Alias API](#entity-alias-api)
5. [Cases API](#cases-api)
6. [Evidence API](#evidence-api)
7. [Studio V4 API](#studio-v4-api)
8. [Deep Research API](#deep-research-api)

---

## Investigation API

### Start Investigation

Starts an AI-powered investigation with real-time streaming.

```http
POST /api/investigation/start
Content-Type: application/json
Accept: text/event-stream
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "scenario": "Suspected ransomware attack on production servers...",
  "objectives": [
    "Identify initial access vector",
    "Determine affected systems",
    "Assess data exfiltration"
  ],
  "time_range": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-02T00:00:00Z"
  },
  "modules_to_run": ["timeline", "anomaly", "network", "correlation"],
  "initial_hypotheses": [
    "Phishing email compromise",
    "External RDP brute force",
    "Insider threat"
  ],
  "options": {
    "llm_provider": "gemini",
    "traversal_strategy": "bfs_then_dfs",
    "auto_answer_timeout": 60
  }
}
```

**Response:** Server-Sent Events stream

```
data: {"type": "phase_start", "phase": "intake", "timestamp": "..."}

data: {"type": "finding", "tool_id": "timeline", "data": {...}}

data: {"type": "hypothesis", "data": {"id": "h1", "statement": "...", "prior_confidence": 0.5}}

data: {"type": "visualization", "data": {"type": "chart", "chart_type": "timeline", ...}}

data: {"type": "confidence", "data": {"level": "MODERATE", "score": 0.72}}

data: {"type": "complete", "timestamp": "..."}
```

### Get Investigation Status

```http
GET /api/investigation/{investigation_id}/status
```

**Response:**
```json
{
  "investigation_id": "inv-123",
  "status": "running",
  "current_phase": "execution",
  "progress": 65,
  "started_at": "2024-01-15T10:00:00Z",
  "findings_count": 23,
  "hypotheses_tested": 3
}
```

### Stop Investigation

```http
POST /api/investigation/{investigation_id}/stop
```

**Response:**
```json
{
  "status": "stopped",
  "message": "Investigation stopped by user"
}
```

---

## Augment Studio API

### Generate Chart

```http
POST /api/augment/generate
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "chart_type": "pie",
  "title": "Event Distribution by Type",
  "data": [
    {"label": "Login", "value": 150},
    {"label": "Logout", "value": 120},
    {"label": "File Access", "value": 89}
  ],
  "options": {
    "colors": ["#3b82f6", "#10b981", "#f59e0b"],
    "show_legend": true,
    "show_labels": true
  }
}
```

**Response:**
```json
{
  "chart_id": "chart-abc123",
  "chart_type": "pie",
  "svg": "<svg>...</svg>",
  "data_hash": "sha256:..."
}
```

### Auto-Generate Chart

Let the system choose the best chart type.

```http
POST /api/augment/auto
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "data": [
    {"timestamp": "2024-01-01T00:00", "value": 10},
    {"timestamp": "2024-01-01T01:00", "value": 25},
    {"timestamp": "2024-01-01T02:00", "value": 15}
  ],
  "context": "Show activity trend over time"
}
```

**Response:**
```json
{
  "chart_id": "chart-xyz789",
  "recommended_type": "line",
  "reason": "Time series data detected",
  "svg": "<svg>...</svg>"
}
```

### Supported Chart Types

| Type | Description |
|------|-------------|
| `pie` | Categorical distribution |
| `bar` | Comparisons |
| `line` | Trends over time |
| `radar` | Multi-dimensional |
| `heatmap` | Density visualization |
| `scatter` | Correlation |

---

## Universal Tools API

### List Tools

```http
GET /api/tools
```

**Response:**
```json
{
  "tools": [
    {
      "tool_id": "timeline",
      "name": "Timeline Tool",
      "description": "Event timeline reconstruction",
      "capabilities": ["build_timeline", "find_clusters", "detect_gaps"]
    },
    {
      "tool_id": "anomaly",
      "name": "Anomaly Tool",
      "description": "Statistical anomaly detection",
      "capabilities": ["detect_anomalies", "score_events", "explain_shap"]
    }
  ]
}
```

### Get Tool Capabilities

```http
GET /api/tools/{tool_id}/capabilities
```

**Response:**
```json
{
  "tool_id": "timeline",
  "capabilities": [
    {
      "name": "build_timeline",
      "description": "Construct event timeline from logs",
      "parameters": {
        "start_time": {"type": "datetime", "required": false},
        "end_time": {"type": "datetime", "required": false},
        "entity_filter": {"type": "string", "required": false}
      }
    }
  ]
}
```

### Execute Tool

```http
POST /api/tools/{tool_id}/execute
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "capability": "build_timeline",
  "parameters": {
    "start_time": "2024-01-01T00:00:00Z",
    "end_time": "2024-01-02T00:00:00Z",
    "entity_filter": "192.168.1.*"
  }
}
```

**Response:**
```json
{
  "tool_id": "timeline",
  "capability": "build_timeline",
  "success": true,
  "findings": [
    {
      "type": "timeline_event",
      "timestamp": "2024-01-01T03:15:00Z",
      "event_type": "login",
      "entity": "user_admin",
      "details": {...}
    }
  ],
  "visualizations": [
    {
      "type": "timeline",
      "data": {...}
    }
  ],
  "summary": "Found 156 events spanning 24 hours"
}
```

---

## Entity Alias API

### Create Alias

```http
POST /api/aliases
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "original": "192.168.1.100",
  "alias": "server_db_primary",
  "entity_type": "ip_address",
  "metadata": {
    "department": "IT",
    "criticality": "high"
  }
}
```

**Response:**
```json
{
  "id": "alias-123",
  "original": "192.168.1.100",
  "alias": "server_db_primary",
  "entity_type": "ip_address",
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Resolve Alias

```http
GET /api/aliases/resolve?case_id=CASE-001&alias=server_db_primary
```

**Response:**
```json
{
  "alias": "server_db_primary",
  "original": "192.168.1.100",
  "entity_type": "ip_address"
}
```

### List Aliases

```http
GET /api/aliases?case_id=CASE-001
```

**Response:**
```json
{
  "aliases": [
    {
      "original": "192.168.1.100",
      "alias": "server_db_primary",
      "entity_type": "ip_address"
    },
    {
      "original": "john.smith@corp.com",
      "alias": "user_jsmith",
      "entity_type": "email"
    }
  ]
}
```

### Auto-Alias Entities

Automatically create aliases for all entities in text.

```http
POST /api/aliases/auto
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "text": "User 192.168.1.100 accessed file from 10.0.0.50..."
}
```

**Response:**
```json
{
  "entities_found": 2,
  "aliases_created": [
    {"original": "192.168.1.100", "alias": "host_internal_01"},
    {"original": "10.0.0.50", "alias": "host_internal_02"}
  ]
}
```

---

## Cases API

### Create Case

```http
POST /api/cases
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-2024-001",
  "title": "Ransomware Investigation",
  "description": "Suspected ransomware attack on production servers",
  "classification": "confidential",
  "assigned_to": "analyst@corp.com"
}
```

### Get Case

```http
GET /api/cases/{case_id}
```

### List Cases

```http
GET /api/cases?status=active&limit=20
```

### Upload Evidence

```http
POST /api/cases/{case_id}/evidence
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: Evidence file (logs, pcap, etc.)
- `description`: Description of evidence
- `source`: Source system name

**Response:**
```json
{
  "evidence_id": "evd-123",
  "filename": "auth.log",
  "hash": "sha256:abc123...",
  "size_bytes": 1048576,
  "uploaded_at": "2024-01-15T10:00:00Z"
}
```

---

## Evidence API

### Query Evidence

```http
POST /api/evidence/query
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "query": "SELECT * FROM timeline_events WHERE timestamp > '2024-01-01'",
  "limit": 100
}
```

### Verify Hash

```http
GET /api/evidence/{evidence_id}/verify
```

**Response:**
```json
{
  "evidence_id": "evd-123",
  "stored_hash": "sha256:abc123...",
  "computed_hash": "sha256:abc123...",
  "verified": true
}
```

---

## Studio V4 API

### Get Document

```http
GET /api/v4/studio/cases/{case_id}/docs/{doc_id}
```

**Response:**
```json
{
  "doc_id": "doc-123",
  "title": "Investigation Report",
  "ast": {
    "type": "v4-canvas",
    "version": "1.0",
    "pages": [...]
  },
  "created_at": "2024-01-15T10:00:00Z",
  "modified_at": "2024-01-15T12:30:00Z"
}
```

### Save Document

```http
PUT /api/v4/studio/cases/{case_id}/docs/{doc_id}
Content-Type: application/json
```

**Request Body:**
```json
{
  "title": "Investigation Report - Final",
  "ast": {
    "type": "v4-canvas",
    "version": "1.0",
    "pages": [...]
  },
  "change_summary": "Added findings from network analysis"
}
```

### Export PDF

```http
POST /api/v4/studio/cases/{case_id}/exports/pdf
Content-Type: application/json
```

**Request Body:**
```json
{
  "doc_id": "doc-123",
  "actor": "analyst@corp.com",
  "focus_mode": "Story",
  "cover_id": "cover-formal"
}
```

**Response:**
```json
{
  "filename": "CASE-001-report-20240115.pdf",
  "url": "/api/v4/studio/cases/CASE-001/exports/download/CASE-001-report-20240115.pdf",
  "content_hash": "sha256:..."
}
```

### Download Export

```http
GET /api/v4/studio/cases/{case_id}/exports/download/{filename}
```

### List Exports

```http
GET /api/v4/studio/cases/{case_id}/exports
```

---

## Deep Research API

### Start Deep Research

```http
POST /api/deep-research/start
Content-Type: application/json
```

**Request Body:**
```json
{
  "case_id": "CASE-001",
  "question": "What was the initial access vector?",
  "context": "Ransomware incident investigation",
  "depth": "comprehensive"
}
```

**Response:** SSE stream with research progress

### Get Research Session

```http
GET /api/deep-research/sessions/{session_id}
```

---

## Error Responses

All endpoints return standard error responses:

```json
{
  "detail": "Error message here",
  "error_code": "CASE_NOT_FOUND",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |

---

## Rate Limiting

| Endpoint Type | Limit |
|---------------|-------|
| Investigation | 10/hour |
| Tools | 100/minute |
| Exports | 20/hour |
| Standard | 1000/minute |

---

## Authentication

Currently no authentication required for local development.

For production, set `Authorization` header:
```http
Authorization: Bearer <token>
```

---

*API Reference Version: 1.0*
*Generated: April 2026*
