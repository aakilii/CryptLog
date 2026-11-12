# Operation Room — Startup Guide

## Current Status: ✅ Running

### Servers Active

- **Backend (FastAPI):** http://localhost:8000
- **Frontend (Next.js):** http://localhost:3000  
- **API Documentation:** http://localhost:8000/docs

---

## Prerequisites

### 1. Node.js Version Issue **FIXED** ✅

**Problem:** System Node.js v12.22.9 is too old for Next.js (requires Node 14+)

**Solution:** Installed NVM (Node Version Manager) and Node v18.20.8

### 2. Python Environment **FIXED** ✅

**Problem:** No pip available for system python3

**Solution:** Created virtual environment in `backend/venv/`

---

## How to Start (Step-by-Step)

### Backend (FastAPI)

```bash
cd /media/sanjay/Windows-SSD/CISC/operation-room/backend

# Activate virtual environment
source venv/bin/activate

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [PID]
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Frontend (Next.js)

```bash
cd /media/sanjay/Windows-SSD/CISC/operation-room/frontend

# Load NVM
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Start development server
npm run dev
```

**Expected output:**
```
▲ Next.js 14.2.35
- Local:        http://localhost:3000

✓ Ready in 10.9s
```

---

## Quick Start Script

Create this file as `start.sh`:

```bash
#!/bin/bash

# Start backend
cd /media/sanjay/Windows-SSD/CISC/operation-room/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Wait for backend to start
sleep 3

# Start frontend
cd /media/sanjay/Windows-SSD/CISC/operation-room/frontend
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
npm run dev &
FRONTEND_PID=$!
echo "Frontend started (PID: $FRONTEND_PID)"

echo ""
echo "==================================="
echo "✅ Operation Room is running!"
echo "==================================="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To stop: kill $BACKEND_PID $FRONTEND_PID"
```

Make it executable:
```bash
chmod +x start.sh
./start.sh
```

---

## Errors Fixed

### 1. Node.js SyntaxError: Unexpected token '?'

**Error:**
```
SyntaxError: Unexpected token '?'
    at wrapSafe (internal/modules/cjs/loader.js:915:16)
```

**Root cause:** Node v12 doesn't support optional chaining operator (?.)

**Fix:** Installed Node v18.20.8 using NVM

**Verification:**
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
node --version  # Should show v18.20.8
```

### 2. pip not found

**Error:**
```
Command 'python' not found
pip3: command not found
python3 -m pip: No module named pip
```

**Fix:** Created Python virtual environment with venv

**Verification:**
```bash
cd backend
source venv/bin/activate
python --version   # Should show Python 3.10.12
pip --version      # Should work
```

### 3. Missing Python packages

**Fixed:** Installed all dependencies in virtual environment:
```
✅ fastapi, uvicorn, duckdb, pydantic
✅ langgraph, langchain, langchain-community
✅ python-docx (for DOCX export)
```

### 4. Pydantic warning (non-critical)

**Warning:**
```
Field "model_type" in RunDetectionRequest has conflict with protected namespace "model_"
```

**Status:** Non-critical warning. Doesn't affect functionality.

**Future fix:** Add to model config:
```python
model_config = {"protected_namespaces": ()}
```

---

## Verification Tests

### Backend Health Check

```bash
# Should return JSON error (no /health endpoint)
curl http://localhost:8000/health

# Should show OpenAPI docs HTML
curl http://localhost:8000/docs | head -5

# Test Report Studio API (will fail for non-existent case)
curl http://localhost:8000/api/cases/test/report-studio/insights/all
# Expected: {"detail":"No vault found for case test"}
```

### Frontend Health Check

```bash
# Should return HTML
curl http://localhost:3000 | head -5

# Should see title
curl -s http://localhost:3000 | grep -o "<title>.*</title>"
# Expected: <title>NFLIP — National Forensic Log Intelligence Platform</title>
```

### Process Check

```bash
ps aux | grep -E "uvicorn|next dev" | grep -v grep
```

Expected output:
```
sanjay   21528  ... uvicorn app.main:app --reload
sanjay   24275  ... node .../next/dist/bin/next dev
```

---

## Common Issues

### Issue: "Port 8000 already in use"

```bash
# Find process
lsof -i :8000

# Kill it
kill -9 <PID>
```

### Issue: "Port 3000 already in use"

```bash
# Find process
lsof -i :3000

# Kill it
kill -9 <PID>
```

### Issue: Frontend says "Module not found"

```bash
cd frontend
npm install  # Reinstall dependencies
```

### Issue: Backend import errors

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt  # Reinstall dependencies
```

---

## Development Notes

### LLM Configuration

Backend uses LLM for Writer Agent. Check configuration:

```bash
cat backend/.env
```

Expected settings:
```
LLM_PROVIDER=ollama          # or gemini
LLM_MODEL=qwen3              # Ollama model name
OLLAMA_URL=http://localhost:11434
```

**Important:** Writer Agent requires Ollama or Gemini to be running!

### Check Ollama Status

```bash
curl http://localhost:11434/api/version
```

If not running:
```bash
ollama serve
```

---

## Report Studio Access

Once both servers are running:

1. Go to http://localhost:3000
2. Create a new case or open existing case
3. Navigate to `/cases/{case_id}/report-studio`

**Features available:**
- 📋 Module insights sidebar (drag-drop evidence)
- 🤖 AI Writer Agent (generate sections)
- 📎 Citation manager
- 💡 Smart suggestions
- 📤 Export to PDF/DOCX/HTML

---

## Logs Location

```
Backend:  /tmp/copilot-detached-24-*.log
Frontend: /tmp/copilot-detached-18-*.log
```

View logs:
```bash
tail -f /tmp/copilot-detached-24-*.log  # Backend
tail -f /tmp/copilot-detached-18-*.log  # Frontend
```

---

## Dependencies Installed

### Backend (Python)
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
duckdb==1.1.0
pydantic==2.9.0
pydantic-settings==2.13.1  # Upgraded from 2.5.0
langgraph==1.1.3
langchain==1.2.13
langchain-community==0.4.1
python-docx==1.2.0
httpx, python-multipart, SQLAlchemy
```

### Frontend (Node.js)
```
next==14.2.35
react, react-dom
Various Next.js dependencies (see package.json)
```

---

## Next Steps

1. **Create a test case** with sample data
2. **Test Report Studio** end-to-end workflow
3. **Configure Ollama/Gemini** for AI writing
4. **Review architecture document:** `/docs/REPORT_STUDIO_ARCHITECTURE.md`

---

## Troubleshooting Contact

If you encounter issues:
1. Check logs in `/tmp/copilot-detached-*`
2. Verify Node version (must be 14+)
3. Verify Python venv is activated
4. Check if ports 3000/8000 are available

---

**Status:** ✅ Both servers running successfully  
**Last updated:** 2026-03-28  
**Node version:** v18.20.8  
**Python version:** 3.10.12
