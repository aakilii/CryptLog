# NLP Agent — Setup, Hosting & Full Integration Guide

**Applies to:** NFLIP Operation Room · Backend (`operation-room/backend`)  
**Current state:** `app/services/nlp_agent.py` is a **mock** that returns synthetic events.  
This guide shows you how to replace it with a real, permanently-running NLP service.

---

## Table of Contents

1. [What the NLP Agent Does in This App](#1-what-the-nlp-agent-does-in-this-app)
2. [Architecture Overview](#2-architecture-overview)
3. [Choosing Your LLM Backend](#3-choosing-your-llm-backend)
4. [Option A — Local LLM via Ollama (Recommended for Dev)](#4-option-a--local-llm-via-ollama-recommended-for-dev)
5. [Option B — Google Gemini API (Recommended for Production)](#5-option-b--google-gemini-api-recommended-for-production)
6. [Building the Real NLP Microservice](#6-building-the-real-nlp-microservice)
7. [Wiring It Into the Application](#7-wiring-it-into-the-application)
8. [Environment Variables Reference](#8-environment-variables-reference)
9. [Running Everything Together](#9-running-everything-together)
10. [Keeping It Running Full-Time (Windows Service)](#10-keeping-it-running-full-time-windows-service)
11. [Testing the Integration End-to-End](#11-testing-the-integration-end-to-end)

---

## 1. What the NLP Agent Does in This App

The NLP agent sits at the **very first step of the forensic pipeline**. When an investigator clicks
**"Import Evidence"** on a case, the backend calls `query_nlp_agent()` in:

```
operation-room/backend/app/services/nlp_agent.py
```

That function is responsible for **fetching and normalising raw logs** from a data source (SIEM,
file upload, external API) and returning them as a structured list of events:

```python
[
  {
    "event_id":      "uuid",
    "source_type":   "AUTH",          # AUTH | VPN | FW | DB | APP | EPP | FILE
    "timestamp":     "2025-06-01T23:15:00+00:00",
    "source_system": "dc01",
    "actor":         "jdoe",
    "action":        "LOGIN_FAILED",
    "target":        "/auth/login",
    "detail":        { "source_ip": "203.0.113.77", ... }
  },
  ...
]
```

After this call returns, the backend automatically:
- Hashes the entire batch (SHA-256)
- Inserts events into the **immutable `raw_events` DuckDB table**
- Writes a Chain-of-Custody entry

The NLP layer's job is to translate raw, heterogeneous log formats (CSV, JSON, syslog) into
the uniform schema above using an LLM to handle ambiguous fields, varying timestamps, and
non-standard action names.

**The only file you need to change** to go from mock to real is `nlp_agent.py`.

---

## 2. Architecture Overview

```
[ Browser / Frontend ]
        |
        | POST /api/cases/{case_id}/evidence/import
        v
[ FastAPI Backend (port 8000) ]
  └── evidence_service.py
        └── nlp_agent.py  ◄── THIS IS THE INTEGRATION POINT
              |
              | POST http://localhost:9000/query
              v
      [ NLP Microservice (port 9000) ]
        ├── Parses raw log text / CSV / JSON
        ├── Calls LLM to normalise fields
        └── Returns structured event list
              |
              | (uses one of these LLM backends)
              ├── Ollama  (http://localhost:11434)  ← local, free
              └── Gemini API (api.generativeai.google) ← cloud, paid
```

---

## 3. Choosing Your LLM Backend

| | **Ollama (Local)** | **Gemini API (Cloud)** |
|---|---|---|
| Cost | Free | Pay-per-token (~$0.001/1K tokens) |
| Privacy | All data stays on your machine | Data sent to Google |
| Setup | Install Ollama + pull a model | Get an API key |
| Speed | Depends on GPU/CPU | Fast (Google servers) |
| Best for | Development, air-gapped envs | Production, demos |
| Model quality | Good (qwen3, llama3) | Excellent (gemini-1.5-pro) |

Pick one and follow the matching section below.

---

## 4. Option A — Local LLM via Ollama (Recommended for Dev)

### Step 1 — Install Ollama

Download and install from [https://ollama.com/download](https://ollama.com/download).

On Windows, run the `.exe` installer. Ollama will run as a background service automatically on
startup after installation.

Verify it is running:
```powershell
curl http://localhost:11434/api/tags
```

### Step 2 — Pull a Model

The app is pre-configured for `qwen3` (good balance of speed and reasoning):
```powershell
ollama pull qwen3
```

For higher quality at the cost of speed:
```powershell
ollama pull llama3.1:8b
```

For the fastest (lower quality, good for demos on weak hardware):
```powershell
ollama pull llama3.2:3b
```

### Step 3 — Configure the Backend

Create `operation-room/backend/.env` (if it does not exist):
```env
OPROOM_LLM_PROVIDER=ollama
OPROOM_LLM_MODEL=qwen3
OPROOM_OLLAMA_URL=http://localhost:11434
OPROOM_NLP_AGENT_URL=http://localhost:9000
```

Ollama is now ready. Continue to [Section 6](#6-building-the-real-nlp-microservice) to build
the NLP microservice that uses it.

---

## 5. Option B — Google Gemini API (Recommended for Production)

### Step 1 — Get a Gemini API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API Key** → copy the key

### Step 2 — Install the Gemini SDK

Inside the backend virtual environment:
```powershell
cd operation-room/backend
venv\Scripts\activate
pip install google-generativeai
```

Add it to `requirements.txt`:
```
google-generativeai>=0.7.0
```

### Step 3 — Configure the Backend

Create `operation-room/backend/.env`:
```env
OPROOM_LLM_PROVIDER=gemini
OPROOM_LLM_MODEL=gemini-1.5-flash
OPROOM_GEMINI_API_KEY=YOUR_API_KEY_HERE
OPROOM_NLP_AGENT_URL=http://localhost:9000
```

Use `gemini-1.5-flash` for speed and cost, `gemini-1.5-pro` for the highest quality.

---

## 6. Building the Real NLP Microservice

The NLP agent runs as a **separate FastAPI microservice on port 9000**. Create the following
file at `operation-room/backend/nlp_service/main.py`:

```python
"""
Real NLP Query Agent Microservice — port 9000
Translates raw log text into structured NFLIP events using an LLM.
"""
import os, json, re
from fastapi import FastAPI
from pydantic import BaseModel

# ── Choose LLM backend based on env ─────────────────────────────────────
LLM_PROVIDER = os.getenv("OPROOM_LLM_PROVIDER", "ollama")
LLM_MODEL    = os.getenv("OPROOM_LLM_MODEL", "qwen3")
OLLAMA_URL   = os.getenv("OPROOM_OLLAMA_URL", "http://localhost:11434")
GEMINI_KEY   = os.getenv("OPROOM_GEMINI_API_KEY", "")

app = FastAPI(title="NFLIP NLP Agent", version="1.0.0")


class QueryRequest(BaseModel):
    source_type: str
    time_start: str
    time_end: str
    target_actors: list[str] = []
    target_systems: list[str] = []
    query_text: str = ""
    raw_logs: str = ""          # raw CSV / JSON / syslog text (optional)


SYSTEM_PROMPT = """You are a forensic log normalisation engine.
Given raw log text or a description of what to fetch, return a JSON array of events.
Each event MUST have these exact fields:
  event_id, source_type, timestamp (ISO-8601 UTC), source_system,
  actor, action, target, detail (object with source_ip, destination_ip, bytes).

Return ONLY the JSON array. No explanation. No markdown fences."""


def call_ollama(prompt: str) -> str:
    import httpx
    resp = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(LLM_MODEL)
    resp = model.generate_content(prompt)
    return resp.text


def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "gemini":
        return call_gemini(prompt)
    return call_ollama(prompt)


def extract_json(text: str) -> list[dict]:
    """Pull the first JSON array out of LLM response text."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return []


@app.post("/query")
async def query(req: QueryRequest) -> list[dict]:
    user_prompt = f"""
Source type: {req.source_type}
Time window: {req.time_start} to {req.time_end}
Target actors: {req.target_actors or 'all'}
Target systems: {req.target_systems or 'all'}
Query: {req.query_text or 'Generate realistic forensic log events for this source'}

Raw logs (if any):
{req.raw_logs or '(none — generate synthetic events that match the source type)'}

Generate 30-60 realistic events as a JSON array.
"""
    raw = call_llm(SYSTEM_PROMPT + "\n\n" + user_prompt)
    return extract_json(raw)


@app.get("/health")
def health():
    return {"status": "ok", "provider": LLM_PROVIDER, "model": LLM_MODEL}
```

---

## 7. Wiring It Into the Application

### Step 1 — Update `nlp_agent.py` to Call the Real Service

Replace the entire body of `query_nlp_agent()` in
`operation-room/backend/app/services/nlp_agent.py`:

```python
import httpx
from app.config import settings

async def query_nlp_agent(
    source_type: str,
    time_start: str,
    time_end: str,
    target_actors: list[str] | None = None,
    target_systems: list[str] | None = None,
    query_text: str = "",
) -> list[dict]:
    """Call the real NLP microservice to fetch and normalise log events."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{settings.NLP_AGENT_URL}/query",
            json={
                "source_type":    source_type,
                "time_start":     time_start,
                "time_end":       time_end,
                "target_actors":  target_actors or [],
                "target_systems": target_systems or [],
                "query_text":     query_text,
            },
        )
        resp.raise_for_status()
        return resp.json()
```

The `settings.NLP_AGENT_URL` defaults to `http://localhost:9000` and is set via
`OPROOM_NLP_AGENT_URL` in your `.env` file.

### Step 2 — Install the NLP Service Dependencies

```powershell
cd operation-room/backend
venv\Scripts\activate
pip install fastapi uvicorn httpx
# If using Gemini:
pip install google-generativeai
```

---

## 8. Environment Variables Reference

All variables use the prefix `OPROOM_` and are loaded from `operation-room/backend/.env`.

| Variable | Default | Description |
|---|---|---|
| `OPROOM_NLP_AGENT_URL` | `http://localhost:9000` | URL of the NLP microservice |
| `OPROOM_LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `OPROOM_LLM_MODEL` | `qwen3` | Model name (e.g. `llama3.1:8b`, `gemini-1.5-flash`) |
| `OPROOM_OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OPROOM_GEMINI_API_KEY` | _(empty)_ | Your Google Gemini API key |

**Full `.env` example (Ollama):**
```env
OPROOM_LLM_PROVIDER=ollama
OPROOM_LLM_MODEL=qwen3
OPROOM_OLLAMA_URL=http://localhost:11434
OPROOM_NLP_AGENT_URL=http://localhost:9000
```

**Full `.env` example (Gemini):**
```env
OPROOM_LLM_PROVIDER=gemini
OPROOM_LLM_MODEL=gemini-1.5-flash
OPROOM_GEMINI_API_KEY=AIzaSy...your_key_here
OPROOM_NLP_AGENT_URL=http://localhost:9000
```

---

## 9. Running Everything Together

You need **three processes** running simultaneously. Open three PowerShell terminals:

### Terminal 1 — Ollama (if using local LLM)
```powershell
ollama serve
```
> Skip this if Ollama is already running as a Windows service (it usually auto-starts).

### Terminal 2 — NLP Microservice (port 9000)
```powershell
cd "s:/CSIC_FINALS/phase_5_CISC/operation-room/backend"
venv\Scripts\activate
$env:OPROOM_LLM_PROVIDER = "ollama"
$env:OPROOM_LLM_MODEL    = "qwen3"
python -m uvicorn nlp_service.main:app --port 9000 --reload
```

### Terminal 3 — Main FastAPI Backend (port 8000)
```powershell
cd "s:/CSIC_FINALS/phase_5_CISC/operation-room/backend"
venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

### Terminal 4 — Next.js Frontend (port 3001)
```powershell
cd "s:/CSIC_FINALS/phase_5_CISC/operation-room/frontend"
$env:PORT = 3001
npm run dev
```

Verify the NLP service is alive:
```powershell
curl http://localhost:9000/health
# Expected: {"status":"ok","provider":"ollama","model":"qwen3"}
```

---

## 10. Keeping It Running Full-Time (Windows Service)

To have the NLP microservice start automatically with Windows and stay running permanently,
use the **NSSM** (Non-Sucking Service Manager) tool.

### Step 1 — Download NSSM
Download from [https://nssm.cc/download](https://nssm.cc/download) and place `nssm.exe`
somewhere on your PATH (e.g. `C:\Windows\System32\`).

### Step 2 — Create the NLP Service
Run PowerShell as Administrator:
```powershell
nssm install NFLIP-NLP-Agent `
  "s:\CSIC_FINALS\phase_5_CISC\operation-room\backend\venv\Scripts\python.exe" `
  "-m uvicorn nlp_service.main:app --port 9000"
```

Set the working directory:
```powershell
nssm set NFLIP-NLP-Agent AppDirectory "s:\CSIC_FINALS\phase_5_CISC\operation-room\backend"
```

Set environment variables:
```powershell
nssm set NFLIP-NLP-Agent AppEnvironmentExtra `
  "OPROOM_LLM_PROVIDER=ollama" `
  "OPROOM_LLM_MODEL=qwen3" `
  "OPROOM_OLLAMA_URL=http://localhost:11434"
```

Start the service:
```powershell
nssm start NFLIP-NLP-Agent
```

The service will now survive reboots. Check status with:
```powershell
nssm status NFLIP-NLP-Agent
```

### Step 3 — Create the Main Backend Service (Optional)
Repeat the same steps for the main backend on port 8000:
```powershell
nssm install NFLIP-Backend `
  "s:\CSIC_FINALS\phase_5_CISC\operation-room\backend\venv\Scripts\python.exe" `
  "-m uvicorn app.main:app --port 8000"

nssm set NFLIP-Backend AppDirectory "s:\CSIC_FINALS\phase_5_CISC\operation-room\backend"
nssm start NFLIP-Backend
```

---

## 11. Testing the Integration End-to-End

### Quick API test (PowerShell)
```powershell
# 1. Hit the NLP service directly
$body = @{
  source_type    = "AUTH"
  time_start     = "2025-06-01T00:00:00Z"
  time_end       = "2025-06-15T23:59:59Z"
  target_actors  = @("jdoe")
  target_systems = @("dc01")
  query_text     = "Find all failed logins"
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "http://localhost:9000/query" `
  -ContentType "application/json" -Body $body

# 2. Trigger a real evidence import through the main backend
$import = @{
  source_type    = "AUTH"
  time_start     = "2025-06-01T00:00:00Z"
  time_end       = "2025-06-15T23:59:59Z"
  target_actors  = @("jdoe")
  target_systems = @("dc01")
  query_text     = "All authentication events for jdoe"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://localhost:8000/api/cases/CASE-FORENSIC-001/evidence/import" `
  -ContentType "application/json" -Body $import
```

A successful import returns a response like:
```json
{
  "hash_id": "...",
  "case_id": "CASE-FORENSIC-001",
  "artefact_name": "AUTH_import_...",
  "record_count": 47,
  "hash_value": "sha256:..."
}
```

### UI Test
1. Open [http://localhost:3001/cases/CASE-FORENSIC-001](http://localhost:3001/cases/CASE-FORENSIC-001)
2. Navigate to **Evidence** tab
3. Click **Import Evidence** → select a log source → click Import
4. If the NLP agent is wired correctly, real LLM-normalised events will appear instead of the
   previous mock data

---

## Summary Checklist

- [ ] Chose LLM backend: Ollama (local) or Gemini (cloud)
- [ ] Installed Ollama **or** obtained a Gemini API key
- [ ] Created `operation-room/backend/.env` with the correct env vars
- [ ] Created `operation-room/backend/nlp_service/main.py` (the microservice)
- [ ] Updated `query_nlp_agent()` in `nlp_agent.py` to use `httpx` instead of returning mock data
- [ ] Started all 3+ processes (Ollama / NLP service / FastAPI backend / Next.js frontend)
- [ ] Verified `/health` returns `{"status":"ok"}` on port 9000
- [ ] Ran an end-to-end evidence import and confirmed real events in the UI
- [ ] (Optional) Installed NSSM Windows services for permanent uptime
