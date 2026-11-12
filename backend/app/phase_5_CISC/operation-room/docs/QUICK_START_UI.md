# QUICK START: Building the AI Assistant UI

**Goal:** Get the AI-powered chat interface working end-to-end

---

## ✅ Backend is Ready

You already have:
- ✅ Deep Research API endpoints (`/api/deep-research/*`)
- ✅ WebSocket support (needs small addition for streaming)
- ✅ LLM hypothesis generation
- ✅ Report version control
- ✅ Progress tracking

**What's Missing:**
- ❌ WebSocket streaming endpoint for real-time updates
- ❌ Frontend UI components

---

## 🚀 Implementation Steps

### Step 1: Use the Existing WebSocket Endpoints (Backend)

**File:** `app/routes/deep_research.py`

Deep Research already exposes WebSocket endpoints. Use the canonical route and keep the alias for backward compatibility:

```python
@router.websocket("/investigations/{investigation_id}/ws")
async def websocket_endpoint(websocket: WebSocket, investigation_id: str):
  await _run_websocket_session(websocket, investigation_id)


@router.websocket("/ws/{investigation_id}")
async def websocket_investigation_stream(websocket: WebSocket, investigation_id: str):
  # Backward-compatible alias
  await _run_websocket_session(websocket, investigation_id)
```

Expected outcomes:
- Both routes support the same message types (`answer_question`, `approve_plan`, `send_message`, `modify_plan`).
- Progress events are emitted as `progress_update`.
- Connections are tracked by `client_id` and cleaned up on disconnect.

### Step 2: Create Frontend Components

**Directory Structure:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── ai-panel/
│   │   │   ├── AIPanel.tsx              ← Main panel container
│   │   │   ├── TabBar.tsx               ← Tab navigation
│   │   │   ├── tabs/
│   │   │   │   ├── ChatTab.tsx          ← Chat interface
│   │   │   │   ├── ProgressTab.tsx      ← Progress view
│   │   │   │   ├── PlanTab.tsx          ← Plan editor
│   │   │   │   ├── EvidenceTab.tsx      ← Evidence browser
│   │   │   │   ├── FindingsTab.tsx      ← Findings summary
│   │   │   │   ├── ReportTab.tsx        ← Report status
│   │   │   │   └── HistoryTab.tsx       ← Version history
│   │   │   └── messages/
│   │   │       ├── ChatMessage.tsx      ← Chat bubble
│   │   │       ├── QuestionCard.tsx     ← Question UI
│   │   │       ├── HypothesisCard.tsx   ← Hypothesis card
│   │   │       └── ProgressUpdate.tsx   ← Progress message
│   │   └── canvas/
│   │       └── ReportCanvas.tsx         ← Existing canvas (integrate)
│   ├── hooks/
│   │   ├── useInvestigation.ts          ← Investigation state
│   │   ├── useWebSocket.ts              ← WebSocket connection
│   │   └── useAIChat.ts                 ← Chat message handling
│   ├── stores/
│   │   └── investigationStore.ts        ← Zustand store
│   └── types/
│       └── investigation.ts             ← TypeScript types
```

### Step 3: Install Dependencies

```bash
npm install zustand framer-motion react-markdown
```

### Step 4: Create Investigation Store

**File:** `frontend/src/stores/investigationStore.ts`

```typescript
import create from 'zustand';

interface InvestigationState {
  investigationId: string | null;
  phase: string;
  progress: number;
  chatMessages: Message[];
  plan: InvestigationPlan | null;
  findings: Finding[];
  evidence: Evidence[];
  
  // Actions
  setInvestigationId: (id: string) => void;
  addChatMessage: (message: Message) => void;
  updateProgress: (progress: number, phase: string) => void;
  setPlan: (plan: InvestigationPlan) => void;
  addFinding: (finding: Finding) => void;
  addEvidence: (evidence: Evidence) => void;
}

export const useInvestigationStore = create<InvestigationState>((set) => ({
  investigationId: null,
  phase: 'idle',
  progress: 0,
  chatMessages: [],
  plan: null,
  findings: [],
  evidence: [],
  
  setInvestigationId: (id) => set({ investigationId: id }),
  
  addChatMessage: (message) => set((state) => ({
    chatMessages: [...state.chatMessages, message]
  })),
  
  updateProgress: (progress, phase) => set({ progress, phase }),
  
  setPlan: (plan) => set({ plan }),
  
  addFinding: (finding) => set((state) => ({
    findings: [...state.findings, finding]
  })),
  
  addEvidence: (evidence) => set((state) => ({
    evidence: [...state.evidence, evidence]
  })),
}));
```

### Step 5: Create WebSocket Hook

**File:** `frontend/src/hooks/useWebSocket.ts`

```typescript
import { useEffect } from 'react';
import { useInvestigationStore } from '../stores/investigationStore';

export function useWebSocket(investigationId: string | null) {
  const { addChatMessage, updateProgress, addFinding, addEvidence } = useInvestigationStore();
  
  useEffect(() => {
    if (!investigationId) return;

    const pageProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const configuredApi = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/api\/?$/, '');
    const wsBase = configuredApi.startsWith('http')
      ? configuredApi.replace(/^http/, 'ws')
      : `${pageProtocol}//${configuredApi}`;
    const socket = new WebSocket(
      `${wsBase.replace(/\/$/, '')}/deep-research/investigations/${investigationId}/ws`
    );

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'chat_message') {
        addChatMessage({
          id: data.id || `msg-${Date.now()}`,
          sender: data.sender,
          content: data.content,
          type: data.message_type || 'text',
          timestamp: data.timestamp,
          metadata: data.metadata,
        });
      }

      if (data.type === 'progress_update') {
        updateProgress(data.progress, data.phase);
      }

      if (data.type === 'finding' || data.type === 'finding_discovered') {
        addFinding(data.finding || data);
      }

      if (data.type === 'evidence' || data.type === 'evidence_found') {
        addEvidence(data.evidence || data);
      }
    };
    
    return () => {
      socket.close();
    };
  }, [investigationId]);
}
```

### Step 6: Create Chat Component

**File:** `frontend/src/components/ai-panel/tabs/ChatTab.tsx`

```typescript
import React, { useState } from 'react';
import { useInvestigationStore } from '../../../stores/investigationStore';
import ChatMessage from '../messages/ChatMessage';

export default function ChatTab() {
  const { chatMessages, investigationId } = useInvestigationStore();
  const [inputValue, setInputValue] = useState('');
  
  const sendMessage = async () => {
    if (!inputValue.trim()) return;
    
    // Add user message to chat
    useInvestigationStore.getState().addChatMessage({
      id: `user-${Date.now()}`,
      sender: 'user',
      content: inputValue,
      type: 'text',
      timestamp: new Date().toISOString(),
    });
    
    // Send to backend
    await fetch(`/api/deep-research/investigations/${investigationId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: inputValue })
    });
    
    setInputValue('');
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
      </div>
      
      {/* Input */}
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type your message or answer..."
            className="flex-1 px-4 py-2 border rounded-lg"
          />
          <button
            onClick={sendMessage}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

### Step 7: Create Message Components

**File:** `frontend/src/components/ai-panel/messages/ChatMessage.tsx`

```typescript
import React from 'react';
import QuestionCard from './QuestionCard';
import HypothesisCard from './HypothesisCard';
import ProgressUpdate from './ProgressUpdate';

export default function ChatMessage({ message }) {
  // Different rendering based on message type
  if (message.type === 'question') {
    return <QuestionCard message={message} />;
  }
  
  if (message.type === 'hypothesis') {
    return <HypothesisCard message={message} />;
  }
  
  if (message.type === 'progress') {
    return <ProgressUpdate message={message} />;
  }
  
  // Default text message
  return (
    <div className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] rounded-lg p-4 ${
        message.sender === 'user'
          ? 'bg-blue-600 text-white'
          : 'bg-gray-100 text-gray-900'
      }`}>
        {message.sender === 'ai' && <div className="text-sm font-semibold mb-1">🤖 AI Assistant</div>}
        <div className="whitespace-pre-wrap">{message.content}</div>
        <div className="text-xs mt-2 opacity-70">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
```

**File:** `frontend/src/components/ai-panel/messages/QuestionCard.tsx`

```typescript
import React, { useState } from 'react';

export default function QuestionCard({ message }) {
  const [selectedChoice, setSelectedChoice] = useState(null);
  const [customAnswer, setCustomAnswer] = useState('');
  
  const handleAnswer = async () => {
    const answer = selectedChoice || customAnswer;
    
    await fetch(`/api/deep-research/investigations/${investigationId}/questions/${message.id}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer })
    });
  };
  
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
      <div className="text-sm font-semibold text-blue-900 mb-2">
        🔍 Question {message.metadata.priority === 'high' ? '(HIGH PRIORITY)' : ''}
      </div>
      
      <div className="text-gray-900 mb-4">{message.content}</div>
      
      {message.metadata.choices && (
        <div className="space-y-2 mb-4">
          {message.metadata.choices.map((choice, i) => (
            <label key={i} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name={`question-${message.id}`}
                value={choice}
                checked={selectedChoice === choice}
                onChange={() => setSelectedChoice(choice)}
                className="w-4 h-4"
              />
              <span>{choice}</span>
            </label>
          ))}
        </div>
      )}
      
      {message.metadata.allowFreeform && (
        <input
          type="text"
          value={customAnswer}
          onChange={(e) => setCustomAnswer(e.target.value)}
          placeholder="Or type your own answer..."
          className="w-full px-3 py-2 border rounded mb-4"
        />
      )}
      
      <div className="flex gap-2">
        <button
          onClick={handleAnswer}
          disabled={!selectedChoice && !customAnswer}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Answer
        </button>
        <button className="px-4 py-2 border rounded hover:bg-gray-50">
          Skip for now
        </button>
      </div>
    </div>
  );
}
```

### Step 8: Integrate into Report Studio

**File:** `frontend/src/pages/ReportStudio.tsx`

```typescript
import React, { useState } from 'react';
import { useInvestigationStore } from '../stores/investigationStore';
import { useWebSocket } from '../hooks/useWebSocket';
import AIPanel from '../components/ai-panel/AIPanel';
import ReportCanvas from '../components/canvas/ReportCanvas';

export default function ReportStudio() {
  const { investigationId } = useInvestigationStore();
  const [panelWidth, setPanelWidth] = useState(40); // 40% default
  const [panelVisible, setPanelVisible] = useState(true);
  
  // Connect to WebSocket
  useWebSocket(investigationId);
  
  return (
    <div className="flex h-screen">
      {/* Canvas Area */}
      <div
        className="bg-white overflow-auto"
        style={{ width: panelVisible ? `${100 - panelWidth}%` : '100%' }}
      >
        <ReportCanvas />
      </div>
      
      {/* AI Panel */}
      {panelVisible && (
        <div
          className="border-l bg-gray-50"
          style={{ width: `${panelWidth}%` }}
        >
          <AIPanel
            onResize={(newWidth) => setPanelWidth(newWidth)}
            onClose={() => setPanelVisible(false)}
          />
        </div>
      )}
      
      {/* Show button when panel hidden */}
      {!panelVisible && (
        <button
          onClick={() => setPanelVisible(true)}
          className="fixed right-0 top-1/2 -translate-y-1/2 bg-blue-600 text-white px-2 py-4 rounded-l-lg"
        >
          &lt; Show AI Assistant
        </button>
      )}
    </div>
  );
}
```

---

## 🧪 Testing the Integration

### 1. Start Backend
```bash
cd C:\CISC\operation-room\backend
python -m uvicorn app.main:app --port 8000 --reload
```

### 2. Start Frontend
```bash
cd C:\CISC\operation-room\frontend
npm run dev
```

### 3. Test Basic Flow

1. **Navigate to Report Studio**
   - http://localhost:3000/report-studio

2. **Send Initial Scenario**
   - Type in chat: "Investigate USB data exfiltration"
   - AI should respond with clarifying questions

3. **Answer Questions**
   - Select from multiple choice
   - AI should generate investigation plan

4. **View Plan**
   - Switch to "Plan" tab
   - Should show hypotheses and phases
   - Click "Approve & Execute"

5. **Watch Progress**
   - Switch to "Progress" tab
   - Should see live updates as AI works

6. **View Results**
   - Switch to "Findings" tab
   - Should see confirmed/rejected hypotheses
   - Switch to "Evidence" tab
   - Should see collected evidence

7. **Check Report**
   - Canvas should show report being written in real-time
   - Switch to "Report" tab for progress

### Verification Commands

Backend import and route smoke test:

```powershell
Set-Location operation-room/backend
$env:PYTHONPATH='.'
c:/CISC/.venv/Scripts/python.exe -m pytest tests/test_deep_research.py::test_api_routes_import -q
```

Frontend type check:

```powershell
Set-Location operation-room/frontend
npx tsc --noEmit
```

---

## 📚 Next Steps

After basic chat works:

1. **Add Progress Tab** - Real-time timeline view
2. **Add Plan Editor** - Drag-and-drop hypothesis editing
3. **Add Evidence Browser** - Filterable evidence list
4. **Add Findings Summary** - Hypothesis results
5. **Add Report Tab** - Report writing progress
6. **Add History Tab** - Version control UI

---

## 🐛 Troubleshooting

**WebSocket not connecting:**
- Check CORS settings in backend
- Verify `/deep-research/investigations/{investigation_id}/ws` is registered (legacy alias: `/deep-research/ws/{investigation_id}`)
- Check browser console for errors

**Messages not appearing:**
- Check WebSocket event names match
- Verify store updates are triggering re-renders
- Check React DevTools for state changes

**Real-time updates lag:**
- Reduce WebSocket send frequency
- Implement message batching
- Add debouncing to UI updates

---

*Quick Start Guide - AI Assistant UI*  
*NFLIP Deep Research Investigation Assistant*
