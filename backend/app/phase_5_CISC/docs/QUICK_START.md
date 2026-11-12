# NFLIP Quick Start Guide

## Get Up and Running in 5 Minutes

---

## 1. Prerequisites

Ensure you have:
- Python 3.10+
- Node.js 18+
- Git

## 2. Clone & Install

```bash
# Clone the repository
git clone <repo-url>
cd CISC

# Install backend dependencies
cd operation-room/backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
npm install
```

## 3. Configure LLM Provider

Choose one:

**Option A: Ollama (Local, Free)**
```bash
# Install Ollama from https://ollama.ai
ollama pull qwen3:8b
ollama serve
```

**Option B: Google Gemini (Cloud)**
```bash
# Set API key in environment
export GEMINI_API_KEY=your_api_key_here
```

## 4. Start the Application

**Terminal 1 - Backend:**
```bash
cd operation-room/backend
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd operation-room/frontend
npm run dev
```

## 5. Access the Application

Open your browser to: **http://localhost:3000**

---

## Your First Investigation

### Step 1: Create a Case
1. Click "New Case" on the dashboard
2. Enter a Case ID (e.g., `CASE-2024-001`)
3. Add a title and description
4. Click "Create"

### Step 2: Upload Evidence
1. Open the case
2. Go to "Vault" tab
3. Click "Upload Evidence"
4. Select log files (JSON, CSV, EVTX, etc.)

### Step 3: Open Report Studio
1. Click "Report Studio V4" button
2. The canvas workspace opens

### Step 4: Start AI Investigation
1. Click the purple **"AI Investigate"** button (top-right)
2. Enter your scenario:
   ```
   Suspected ransomware attack on database server.
   Multiple users reported locked files around 3am.
   Network logs show unusual outbound traffic to 
   Eastern European IP addresses.
   ```
3. Select modules to run (default: all)
4. Click **"Start Investigation"**

### Step 5: Watch the Magic
- Progress bar shows investigation status
- Findings appear on canvas in real-time
- Charts and visualizations auto-generate

### Step 6: Review & Export
1. Click **"Export"** when investigation completes
2. Preview your report
3. Select format (PDF recommended)
4. Download

---

## Quick Reference

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Ctrl+S | Save |
| Ctrl+E | Export |
| Ctrl+\ | Toggle AI Panel |

### Focus Modes
| Mode | Use For |
|------|---------|
| Story | Executive reports |
| Review | Internal analysis |
| Redact | External sharing |

### Investigation Phases
1. INTAKE → Parse scenario
2. HYPOTHESIS → Generate theories
3. PLANNING → Create steps
4. EXECUTION → Run analysis
5. TESTING → Test hypotheses
6. CONFIDENCE → Score certainty
7. REPORTING → Generate output

---

## Need Help?

- **API Docs**: http://localhost:8000/docs
- **User Guide**: `docs/USER_GUIDE.md`
- **Developer Docs**: `docs/DEVELOPER_GUIDE.md`

---

*Happy Investigating!* 🔍
