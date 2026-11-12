# NFLIP Deep Research Investigation Assistant - Implementation Plan

## Project Overview

Building a **ChatGPT DeepResearch-style Investigation Assistant** with:
- ✅ Both streaming text + structured tree for chain-of-thought
- ✅ Multiple human-in-loop interaction patterns
- ✅ PDF and DOCX reference document support
- ✅ Full plan editing (phases + steps + hypotheses)
- ✅ Hybrid report building (structure → fill)
- ✅ Switchable LLM (Gemini + Ollama Qwen3)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DEEP RESEARCH INVESTIGATION ASSISTANT                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│   FRONTEND (React) │     │  BACKEND (FastAPI) │     │   LLM PROVIDERS    │
├────────────────────┤     ├────────────────────┤     ├────────────────────┤
│ DeepResearchPanel  │◄───►│ /api/deep-research │◄───►│ Gemini API         │
│ ├─ ThoughtStream   │ SSE │ ├─ /start          │     │ Ollama (Qwen3)     │
│ ├─ PlanEditor      │     │ ├─ /stream         │     └────────────────────┘
│ ├─ ApprovalGate    │     │ ├─ /approve        │
│ └─ ProgressTree    │     │ ├─ /pause          │     ┌────────────────────┐
│                    │     │ └─ /resume         │     │   EVIDENCE VAULT   │
│ HumanLoopModal     │◄───►│                    │◄───►│ DuckDB + SHA-256   │
│ ├─ QuestionPopup   │ WS  │ /api/human-loop    │     └────────────────────┘
│ ├─ SidePanel       │     │ ├─ /ask            │
│ └─ NotificationQ   │     │ ├─ /answer         │     ┌────────────────────┐
│                    │     │ └─ /queue          │     │   REPORT STUDIO    │
│ ReportBuilder      │◄───►│                    │◄───►│ Canvas + Export    │
│ ├─ StructurePlanner│     │ /api/report-build  │     └────────────────────┘
│ ├─ SectionWriter   │     │ ├─ /structure      │
│ ├─ AlignmentCheck  │     │ ├─ /write-section  │
│ └─ TOCGenerator    │     │ └─ /verify         │
└────────────────────┘     └────────────────────┘
```

---

## Phase 1: LLM Provider Abstraction (Foundation)

### 1.1 Switchable LLM Service

Create unified LLM interface supporting Gemini and Ollama:

```python
# app/services/llm/provider.py

class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str: ...
    
    @abstractmethod
    async def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def generate_json(self, prompt: str, schema: dict, **kwargs) -> dict: ...

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        ...

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b"):
        ...

class LLMService:
    """Unified LLM service with provider switching."""
    
    def __init__(self):
        self.providers = {
            "gemini": GeminiProvider(os.getenv("GEMINI_API_KEY")),
            "ollama": OllamaProvider()
        }
        self.active_provider = os.getenv("LLM_PROVIDER", "ollama")
    
    def switch_provider(self, provider: str):
        self.active_provider = provider
    
    async def generate(self, prompt: str, **kwargs) -> str:
        return await self.providers[self.active_provider].generate(prompt, **kwargs)
    
    async def generate_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        async for chunk in self.providers[self.active_provider].generate_stream(prompt, **kwargs):
            yield chunk
```

### 1.2 Configuration

```python
# app/config.py additions

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # "gemini" or "ollama"
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:8b")
```

---

## Phase 2: Deep Research Chain-of-Thought System

### 2.1 Thought Stream Backend

```python
# app/services/deep_research/thought_engine.py

@dataclass
class ThoughtNode:
    id: str
    parent_id: Optional[str]
    type: Literal["reasoning", "action", "finding", "question", "decision"]
    title: str
    content: str
    status: Literal["thinking", "complete", "error"]
    timestamp: datetime
    metadata: Dict[str, Any]

class ThoughtEngine:
    """Manages chain-of-thought with streaming."""
    
    def __init__(self, investigation_id: str, llm: LLMService):
        self.investigation_id = investigation_id
        self.llm = llm
        self.thought_tree: Dict[str, ThoughtNode] = {}
        self.subscribers: List[Callable] = []
    
    async def think(self, prompt: str, parent_id: Optional[str] = None) -> AsyncIterator[ThoughtNode]:
        """Generate thought with streaming output."""
        thought_id = f"thought-{uuid4().hex[:8]}"
        
        # Emit "thinking" state
        node = ThoughtNode(
            id=thought_id,
            parent_id=parent_id,
            type="reasoning",
            title="Analyzing...",
            content="",
            status="thinking",
            timestamp=datetime.utcnow(),
            metadata={}
        )
        yield node
        
        # Stream LLM response
        full_content = ""
        async for chunk in self.llm.generate_stream(prompt):
            full_content += chunk
            node.content = full_content
            yield node
        
        # Complete
        node.status = "complete"
        node.title = self._extract_title(full_content)
        self.thought_tree[thought_id] = node
        yield node
```

### 2.2 SSE Streaming Endpoint

```python
# app/routes/deep_research.py

@router.get("/api/deep-research/{investigation_id}/stream")
async def stream_thoughts(investigation_id: str):
    """SSE endpoint for thought streaming."""
    
    async def event_generator():
        engine = get_thought_engine(investigation_id)
        
        async for thought in engine.run_investigation():
            yield {
                "event": "thought",
                "data": json.dumps(thought.dict())
            }
        
        yield {"event": "complete", "data": "{}"}
    
    return EventSourceResponse(event_generator())
```

### 2.3 Frontend Thought Components

```typescript
// components/deep-research/ThoughtStream.tsx

interface ThoughtStreamProps {
  investigationId: string;
  onThoughtComplete: (thought: ThoughtNode) => void;
}

export function ThoughtStream({ investigationId, onThoughtComplete }: ThoughtStreamProps) {
  const [thoughts, setThoughts] = useState<ThoughtNode[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  
  useEffect(() => {
    const eventSource = new EventSource(
      `/api/deep-research/${investigationId}/stream`
    );
    
    eventSource.addEventListener('thought', (e) => {
      const thought = JSON.parse(e.data);
      setThoughts(prev => {
        const existing = prev.findIndex(t => t.id === thought.id);
        if (existing >= 0) {
          const updated = [...prev];
          updated[existing] = thought;
          return updated;
        }
        return [...prev, thought];
      });
      
      if (thought.status === 'complete') {
        onThoughtComplete(thought);
      }
    });
    
    return () => eventSource.close();
  }, [investigationId]);
  
  return (
    <div className="thought-stream">
      {thoughts.map(thought => (
        <ThoughtCard key={thought.id} thought={thought} />
      ))}
    </div>
  );
}
```

```typescript
// components/deep-research/ThoughtTree.tsx

export function ThoughtTree({ thoughts }: { thoughts: ThoughtNode[] }) {
  const treeData = buildTree(thoughts);
  
  return (
    <div className="thought-tree">
      {treeData.map(node => (
        <TreeNode key={node.id} node={node} depth={0} />
      ))}
    </div>
  );
}

function TreeNode({ node, depth }: { node: TreeNodeData; depth: number }) {
  const [expanded, setExpanded] = useState(true);
  
  return (
    <div className="tree-node" style={{ marginLeft: depth * 20 }}>
      <div className="node-header" onClick={() => setExpanded(!expanded)}>
        <span className={`status-icon ${node.status}`}>
          {node.status === 'thinking' ? '🔄' : node.status === 'complete' ? '✅' : '❌'}
        </span>
        <span className="node-title">{node.title}</span>
        {node.children.length > 0 && (
          <span className="expand-icon">{expanded ? '▼' : '▶'}</span>
        )}
      </div>
      
      {expanded && (
        <>
          <div className="node-content">{node.content}</div>
          {node.children.map(child => (
            <TreeNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </>
      )}
    </div>
  );
}
```

---

## Phase 3: Interactive Plan Editor

### 3.1 Plan Data Model

```python
# app/models/investigation_plan.py

class PlanStep(BaseModel):
    id: str
    title: str
    description: str
    type: Literal["analysis", "query", "hypothesis", "report", "manual"]
    module: Optional[str]  # anomaly, correlation, crud, network, depth, timeline
    status: Literal["pending", "running", "complete", "skipped", "failed"]
    estimated_duration: Optional[int]  # minutes
    dependencies: List[str]  # step IDs
    outputs: List[str]  # evidence IDs created
    user_notes: Optional[str]

class PlanPhase(BaseModel):
    id: str
    title: str
    description: str
    order: int
    steps: List[PlanStep]
    status: Literal["pending", "running", "complete", "skipped"]
    requires_approval: bool
    user_modified: bool

class InvestigationPlan(BaseModel):
    id: str
    investigation_id: str
    version: int
    phases: List[PlanPhase]
    hypotheses: List[HypothesisConfig]
    status: Literal["draft", "approved", "executing", "paused", "complete"]
    created_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    user_commands: List[str]  # User modifications
```

### 3.2 Plan Editor API

```python
# app/routes/plan_editor.py

@router.get("/api/plans/{investigation_id}")
async def get_plan(investigation_id: str) -> InvestigationPlan:
    """Get current investigation plan."""
    ...

@router.put("/api/plans/{investigation_id}/phases/{phase_id}")
async def update_phase(investigation_id: str, phase_id: str, update: PhaseUpdate):
    """Update a phase (reorder, modify, add steps)."""
    ...

@router.post("/api/plans/{investigation_id}/phases/{phase_id}/steps")
async def add_step(investigation_id: str, phase_id: str, step: PlanStep):
    """Add a step to a phase."""
    ...

@router.delete("/api/plans/{investigation_id}/phases/{phase_id}/steps/{step_id}")
async def remove_step(investigation_id: str, phase_id: str, step_id: str):
    """Remove a step from a phase."""
    ...

@router.post("/api/plans/{investigation_id}/reorder")
async def reorder_phases(investigation_id: str, order: List[str]):
    """Reorder phases by ID list."""
    ...

@router.post("/api/plans/{investigation_id}/command")
async def add_user_command(investigation_id: str, command: str):
    """Add user command and regenerate affected parts."""
    ...

@router.post("/api/plans/{investigation_id}/approve")
async def approve_plan(investigation_id: str, approver: str):
    """Approve plan for execution."""
    ...
```

### 3.3 Plan Editor Frontend

```typescript
// components/plan-editor/PlanEditor.tsx

export function PlanEditor({ investigationId }: { investigationId: string }) {
  const [plan, setPlan] = useState<InvestigationPlan | null>(null);
  const [userCommand, setUserCommand] = useState("");
  
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor)
  );
  
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (active.id !== over?.id) {
      const oldIndex = plan.phases.findIndex(p => p.id === active.id);
      const newIndex = plan.phases.findIndex(p => p.id === over.id);
      
      const newOrder = arrayMove(plan.phases, oldIndex, newIndex).map(p => p.id);
      await reorderPhases(investigationId, newOrder);
    }
  };
  
  const handleAddCommand = async () => {
    await addUserCommand(investigationId, userCommand);
    setUserCommand("");
    // Plan will be regenerated
  };
  
  return (
    <div className="plan-editor">
      <div className="plan-header">
        <h2>Investigation Plan</h2>
        <span className={`status-badge ${plan?.status}`}>{plan?.status}</span>
      </div>
      
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <SortableContext items={plan?.phases.map(p => p.id) || []}>
          {plan?.phases.map(phase => (
            <PhaseCard key={phase.id} phase={phase} />
          ))}
        </SortableContext>
      </DndContext>
      
      <div className="add-phase">
        <button onClick={() => addPhase(investigationId)}>+ Add Phase</button>
      </div>
      
      <div className="user-command">
        <input
          value={userCommand}
          onChange={e => setUserCommand(e.target.value)}
          placeholder="Add instruction (e.g., 'Focus on after-hours activity')"
        />
        <button onClick={handleAddCommand}>Apply</button>
      </div>
      
      {plan?.status === 'draft' && (
        <div className="approval-section">
          <button className="approve-btn" onClick={() => approvePlan(investigationId)}>
            ✓ Approve & Execute Plan
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## Phase 4: Human-in-Loop System

### 4.1 Question Types & Delivery Modes

```python
# app/models/human_loop.py

class QuestionPriority(str, Enum):
    BLOCKING = "blocking"      # Must answer to continue
    HIGH = "high"              # Important, shows modal
    MEDIUM = "medium"          # Shows in side panel
    LOW = "low"                # Shows in notification queue

class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    FREE_TEXT = "free_text"
    CONFIRMATION = "confirmation"
    FILE_UPLOAD = "file_upload"
    ENTITY_SELECTION = "entity_selection"

class HumanQuestion(BaseModel):
    id: str
    investigation_id: str
    phase_id: Optional[str]
    step_id: Optional[str]
    
    priority: QuestionPriority
    type: QuestionType
    
    title: str
    description: str
    context: Optional[str]  # What AI was doing when it needed help
    
    options: Optional[List[QuestionOption]]  # For choice questions
    default_answer: Optional[str]
    timeout_seconds: Optional[int]
    timeout_action: Literal["use_default", "skip", "fail"]
    
    asked_at: datetime
    answered_at: Optional[datetime]
    answer: Optional[Any]
    answered_by: Optional[str]
    
class QuestionOption(BaseModel):
    id: str
    label: str
    description: Optional[str]
    metadata: Optional[Dict[str, Any]]
```

### 4.2 Question Manager

```python
# app/services/human_loop/manager.py

class HumanLoopManager:
    """Manages human-in-loop questions with multiple delivery modes."""
    
    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.pending_questions: Dict[str, HumanQuestion] = {}
        self.websocket_connections: List[WebSocket] = []
        self.paused = False
    
    async def ask(
        self,
        title: str,
        description: str,
        priority: QuestionPriority,
        question_type: QuestionType,
        options: Optional[List[QuestionOption]] = None,
        default_answer: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        context: Optional[str] = None
    ) -> Any:
        """Ask a question and wait for answer."""
        
        question = HumanQuestion(
            id=f"q-{uuid4().hex[:8]}",
            investigation_id=self.investigation_id,
            priority=priority,
            type=question_type,
            title=title,
            description=description,
            context=context,
            options=options,
            default_answer=default_answer,
            timeout_seconds=timeout_seconds,
            timeout_action="use_default" if default_answer else "skip",
            asked_at=datetime.utcnow()
        )
        
        self.pending_questions[question.id] = question
        
        # Notify via WebSocket
        await self._broadcast_question(question)
        
        # If blocking, pause and wait
        if priority == QuestionPriority.BLOCKING:
            self.paused = True
            answer = await self._wait_for_answer(question)
            self.paused = False
            return answer
        
        # For non-blocking, return immediately with default
        return default_answer
    
    async def answer(self, question_id: str, answer: Any, answered_by: str):
        """Submit answer to a question."""
        question = self.pending_questions.get(question_id)
        if question:
            question.answer = answer
            question.answered_at = datetime.utcnow()
            question.answered_by = answered_by
            
            # Store in database
            await self._save_answer(question)
            
            # Notify waiters
            await self._notify_answer(question)
    
    async def _broadcast_question(self, question: HumanQuestion):
        """Send question to all connected clients."""
        message = {
            "type": "question",
            "data": question.dict()
        }
        for ws in self.websocket_connections:
            await ws.send_json(message)
```

### 4.3 WebSocket Endpoint

```python
# app/routes/human_loop.py

@router.websocket("/api/human-loop/{investigation_id}/ws")
async def human_loop_websocket(websocket: WebSocket, investigation_id: str):
    """WebSocket for real-time question delivery."""
    await websocket.accept()
    
    manager = get_human_loop_manager(investigation_id)
    manager.websocket_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "answer":
                await manager.answer(
                    question_id=data["question_id"],
                    answer=data["answer"],
                    answered_by=data.get("user", "anonymous")
                )
            
            elif data["type"] == "skip":
                await manager.skip(data["question_id"])
    
    except WebSocketDisconnect:
        manager.websocket_connections.remove(websocket)

@router.get("/api/human-loop/{investigation_id}/pending")
async def get_pending_questions(investigation_id: str) -> List[HumanQuestion]:
    """Get all pending questions for an investigation."""
    manager = get_human_loop_manager(investigation_id)
    return list(manager.pending_questions.values())

@router.post("/api/human-loop/{investigation_id}/answer/{question_id}")
async def answer_question(
    investigation_id: str,
    question_id: str,
    answer: AnswerRequest
):
    """Answer a question via REST API."""
    manager = get_human_loop_manager(investigation_id)
    await manager.answer(question_id, answer.value, answer.user)
```

### 4.4 Frontend Question Components

```typescript
// components/human-loop/HumanLoopProvider.tsx

export function HumanLoopProvider({ investigationId, children }) {
  const [questions, setQuestions] = useState<HumanQuestion[]>([]);
  const [blockingQuestion, setBlockingQuestion] = useState<HumanQuestion | null>(null);
  
  useEffect(() => {
    const ws = new WebSocket(`/api/human-loop/${investigationId}/ws`);
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'question') {
        const question = message.data;
        
        if (question.priority === 'blocking') {
          setBlockingQuestion(question);
        } else {
          setQuestions(prev => [...prev, question]);
        }
      }
    };
    
    return () => ws.close();
  }, [investigationId]);
  
  return (
    <HumanLoopContext.Provider value={{ questions, blockingQuestion }}>
      {children}
      
      {/* Blocking modal */}
      {blockingQuestion && (
        <BlockingQuestionModal question={blockingQuestion} />
      )}
      
      {/* Side panel for high/medium priority */}
      <QuestionSidePanel questions={questions.filter(q => 
        q.priority === 'high' || q.priority === 'medium'
      )} />
      
      {/* Notification queue for low priority */}
      <NotificationQueue questions={questions.filter(q => 
        q.priority === 'low'
      )} />
    </HumanLoopContext.Provider>
  );
}
```

```typescript
// components/human-loop/BlockingQuestionModal.tsx

export function BlockingQuestionModal({ question }: { question: HumanQuestion }) {
  const [answer, setAnswer] = useState<any>(null);
  const { submitAnswer } = useHumanLoop();
  
  return (
    <div className="modal-overlay">
      <div className="blocking-question-modal">
        <div className="modal-header">
          <span className="blocking-icon">🛑</span>
          <h2>Investigation Paused - Input Required</h2>
        </div>
        
        <div className="modal-body">
          <h3>{question.title}</h3>
          <p>{question.description}</p>
          
          {question.context && (
            <div className="context-box">
              <strong>Context:</strong> {question.context}
            </div>
          )}
          
          {question.type === 'single_choice' && (
            <RadioGroup
              options={question.options}
              value={answer}
              onChange={setAnswer}
            />
          )}
          
          {question.type === 'multiple_choice' && (
            <CheckboxGroup
              options={question.options}
              value={answer || []}
              onChange={setAnswer}
            />
          )}
          
          {question.type === 'free_text' && (
            <textarea
              value={answer || ''}
              onChange={e => setAnswer(e.target.value)}
              placeholder="Enter your response..."
            />
          )}
          
          {question.type === 'confirmation' && (
            <div className="confirmation-buttons">
              <button onClick={() => setAnswer(true)}>Yes</button>
              <button onClick={() => setAnswer(false)}>No</button>
            </div>
          )}
        </div>
        
        <div className="modal-footer">
          {question.default_answer && (
            <button 
              className="skip-btn"
              onClick={() => submitAnswer(question.id, question.default_answer)}
            >
              Skip (use default)
            </button>
          )}
          <button 
            className="submit-btn"
            onClick={() => submitAnswer(question.id, answer)}
            disabled={answer === null}
          >
            Submit Answer
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## Phase 5: Reference Document Support

### 5.1 Document Parser

```python
# app/services/document_parser/parser.py

from PyPDF2 import PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTFigure, LTChar
from docx import Document as DocxDocument
from docx.shared import Pt, Mm

class DocumentElement(BaseModel):
    id: str
    type: Literal["heading", "paragraph", "image", "table", "chart", "unknown"]
    page: int
    x: float  # mm from left
    y: float  # mm from top
    width: float  # mm
    height: float  # mm
    content: Optional[str]
    style: Optional[Dict[str, Any]]
    level: Optional[int]  # For headings

class ParsedDocument(BaseModel):
    filename: str
    format: Literal["pdf", "docx"]
    total_pages: int
    page_size: Tuple[float, float]  # width, height in mm
    elements: List[DocumentElement]
    toc: List[TOCEntry]
    styles: Dict[str, Any]

class DocumentParser:
    """Parse PDF and DOCX documents to extract layout."""
    
    async def parse(self, file_path: str) -> ParsedDocument:
        if file_path.endswith('.pdf'):
            return await self._parse_pdf(file_path)
        elif file_path.endswith('.docx'):
            return await self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported format: {file_path}")
    
    async def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """Extract layout from PDF using pdfminer."""
        elements = []
        
        for page_num, page_layout in enumerate(extract_pages(file_path)):
            page_width = page_layout.width
            page_height = page_layout.height
            
            for element in page_layout:
                if isinstance(element, LTTextBox):
                    # Convert PDF coords (bottom-left origin) to mm (top-left origin)
                    x_mm = element.x0 * 25.4 / 72  # points to mm
                    y_mm = (page_height - element.y1) * 25.4 / 72
                    width_mm = (element.x1 - element.x0) * 25.4 / 72
                    height_mm = (element.y1 - element.y0) * 25.4 / 72
                    
                    text = element.get_text().strip()
                    element_type = self._classify_text(text, height_mm)
                    
                    elements.append(DocumentElement(
                        id=f"el-{page_num}-{len(elements)}",
                        type=element_type,
                        page=page_num,
                        x=x_mm,
                        y=y_mm,
                        width=width_mm,
                        height=height_mm,
                        content=text,
                        level=self._detect_heading_level(text, height_mm)
                    ))
        
        return ParsedDocument(
            filename=file_path,
            format="pdf",
            total_pages=page_num + 1,
            page_size=(page_width * 25.4 / 72, page_height * 25.4 / 72),
            elements=elements,
            toc=self._extract_toc(elements),
            styles=self._extract_styles(elements)
        )
    
    async def _parse_docx(self, file_path: str) -> ParsedDocument:
        """Extract layout from DOCX."""
        doc = DocxDocument(file_path)
        elements = []
        
        # DOCX is flow-based, estimate positions
        current_y = 20  # Start after top margin (mm)
        
        for para in doc.paragraphs:
            if not para.text.strip():
                continue
            
            # Estimate height based on font size
            font_size = para.style.font.size
            height_mm = (font_size.pt if font_size else 12) * 0.35  # Approximate
            
            element_type = "heading" if para.style.name.startswith("Heading") else "paragraph"
            level = int(para.style.name[-1]) if element_type == "heading" and para.style.name[-1].isdigit() else None
            
            elements.append(DocumentElement(
                id=f"el-{len(elements)}",
                type=element_type,
                page=0,  # DOCX doesn't have fixed pages until rendered
                x=25,  # Standard left margin
                y=current_y,
                width=160,  # A4 width minus margins
                height=height_mm,
                content=para.text,
                level=level
            ))
            
            current_y += height_mm + 5  # Line spacing
        
        return ParsedDocument(
            filename=file_path,
            format="docx",
            total_pages=1,  # Estimate
            page_size=(210, 297),  # A4
            elements=elements,
            toc=self._extract_toc(elements),
            styles=self._extract_styles(elements)
        )
```

### 5.2 Alignment Verification

```python
# app/services/document_parser/alignment.py

class AlignmentDiff(BaseModel):
    element_id: str
    property: str
    reference_value: float
    current_value: float
    difference: float
    severity: Literal["ok", "minor", "major"]

class AlignmentVerifier:
    """Compare current document layout against reference."""
    
    def __init__(self, tolerance_mm: float = 2.0):
        self.tolerance_mm = tolerance_mm
    
    def compare(
        self,
        reference: ParsedDocument,
        current: List[CanvasElement]
    ) -> List[AlignmentDiff]:
        """Compare layouts and return differences."""
        diffs = []
        
        # Match elements by type and approximate position
        for ref_el in reference.elements:
            matched = self._find_matching_element(ref_el, current)
            
            if matched:
                # Check x position
                if abs(ref_el.x - matched.x) > self.tolerance_mm:
                    diffs.append(AlignmentDiff(
                        element_id=matched.id,
                        property="x",
                        reference_value=ref_el.x,
                        current_value=matched.x,
                        difference=matched.x - ref_el.x,
                        severity=self._classify_severity(abs(matched.x - ref_el.x))
                    ))
                
                # Check y position
                if abs(ref_el.y - matched.y) > self.tolerance_mm:
                    diffs.append(AlignmentDiff(
                        element_id=matched.id,
                        property="y",
                        reference_value=ref_el.y,
                        current_value=matched.y,
                        difference=matched.y - ref_el.y,
                        severity=self._classify_severity(abs(matched.y - ref_el.y))
                    ))
                
                # Check width
                if abs(ref_el.width - matched.width) > self.tolerance_mm:
                    diffs.append(AlignmentDiff(
                        element_id=matched.id,
                        property="width",
                        reference_value=ref_el.width,
                        current_value=matched.width,
                        difference=matched.width - ref_el.width,
                        severity=self._classify_severity(abs(matched.width - ref_el.width))
                    ))
        
        return diffs
    
    def auto_align(
        self,
        reference: ParsedDocument,
        current: List[CanvasElement]
    ) -> List[CanvasElement]:
        """Adjust current elements to match reference layout."""
        aligned = []
        
        for el in current:
            ref_match = self._find_reference_match(el, reference.elements)
            
            if ref_match:
                aligned.append(CanvasElement(
                    **el.dict(),
                    x=ref_match.x,
                    y=ref_match.y,
                    width=ref_match.width,
                    height=ref_match.height
                ))
            else:
                aligned.append(el)
        
        return aligned
```

---

## Phase 6: Hybrid Report Builder

### 6.1 Report Structure Manager

```python
# app/services/report_builder/structure.py

class ReportSection(BaseModel):
    id: str
    type: Literal["cover", "toc", "executive", "narrative", "findings", "evidence", "appendix"]
    title: str
    order: int
    status: Literal["pending", "generating", "complete", "error"]
    page_start: Optional[int]
    page_count: Optional[int]
    content: Optional[str]
    evidence_refs: List[str]
    subsections: List["ReportSection"]
    requires_evidence: bool
    auto_generated: bool

class ReportStructure(BaseModel):
    id: str
    investigation_id: str
    template: str
    sections: List[ReportSection]
    toc: List[TOCEntry]
    total_pages: int
    status: Literal["planning", "generating", "review", "complete"]

class ReportStructureManager:
    """Manages hybrid report building - structure first, then fill."""
    
    def __init__(self, investigation_id: str, llm: LLMService):
        self.investigation_id = investigation_id
        self.llm = llm
        self.structure: Optional[ReportStructure] = None
    
    async def plan_structure(self, findings: List[Finding], template: str) -> ReportStructure:
        """Phase 1: Plan the report structure based on findings."""
        
        # Use LLM to determine optimal section ordering
        prompt = f"""
        Based on these investigation findings, plan a forensic report structure:
        
        Findings:
        {json.dumps([f.dict() for f in findings], indent=2)}
        
        Template: {template}
        
        Return a JSON structure with sections, each containing:
        - id, type, title, order, requires_evidence, subsections
        """
        
        structure_json = await self.llm.generate_json(prompt, ReportStructure.schema())
        self.structure = ReportStructure(**structure_json)
        
        # Calculate initial page estimates
        self._estimate_pages()
        
        # Generate TOC skeleton
        self._generate_toc_skeleton()
        
        return self.structure
    
    async def generate_section(self, section_id: str) -> ReportSection:
        """Phase 2: Generate content for a specific section."""
        section = self._find_section(section_id)
        
        if not section:
            raise ValueError(f"Section not found: {section_id}")
        
        section.status = "generating"
        
        # Gather evidence for this section
        evidence = await self._gather_evidence_for_section(section)
        
        # Generate narrative using LLM
        content = await self._generate_narrative(section, evidence)
        
        section.content = content
        section.evidence_refs = [e.id for e in evidence]
        section.status = "complete"
        
        # Update page counts
        self._recalculate_pages()
        
        # Update TOC
        self._update_toc()
        
        return section
    
    async def insert_section(self, after_section_id: str, new_section: ReportSection):
        """Handle dynamic section insertion."""
        # Find position
        position = self._find_section_position(after_section_id)
        
        # Insert
        self.structure.sections.insert(position + 1, new_section)
        
        # Renumber
        self._renumber_sections()
        
        # Recalculate pages
        self._recalculate_pages()
        
        # Update TOC
        self._update_toc()
    
    def _recalculate_pages(self):
        """Recalculate page numbers after content changes."""
        current_page = 1
        
        for section in self.structure.sections:
            section.page_start = current_page
            
            if section.content:
                # Estimate pages based on content length
                chars_per_page = 3000  # Approximate
                section.page_count = max(1, len(section.content) // chars_per_page)
            else:
                section.page_count = 1  # Placeholder
            
            current_page += section.page_count
        
        self.structure.total_pages = current_page - 1
    
    def _update_toc(self):
        """Regenerate table of contents."""
        self.structure.toc = []
        
        for section in self.structure.sections:
            if section.type not in ["cover", "toc"]:
                self.structure.toc.append(TOCEntry(
                    title=section.title,
                    page=section.page_start,
                    level=1
                ))
                
                for subsection in section.subsections:
                    self.structure.toc.append(TOCEntry(
                        title=subsection.title,
                        page=subsection.page_start or section.page_start,
                        level=2
                    ))
```

### 6.2 Report Builder API

```python
# app/routes/report_builder.py

@router.post("/api/report-build/{investigation_id}/structure")
async def plan_report_structure(
    investigation_id: str,
    request: StructurePlanRequest
) -> ReportStructure:
    """Plan report structure based on findings."""
    manager = get_report_structure_manager(investigation_id)
    return await manager.plan_structure(request.findings, request.template)

@router.post("/api/report-build/{investigation_id}/sections/{section_id}/generate")
async def generate_section(
    investigation_id: str,
    section_id: str
):
    """Generate content for a section."""
    manager = get_report_structure_manager(investigation_id)
    return await manager.generate_section(section_id)

@router.post("/api/report-build/{investigation_id}/sections/insert")
async def insert_section(
    investigation_id: str,
    request: InsertSectionRequest
):
    """Insert a new section."""
    manager = get_report_structure_manager(investigation_id)
    await manager.insert_section(request.after_section_id, request.section)
    return manager.structure

@router.get("/api/report-build/{investigation_id}/toc")
async def get_toc(investigation_id: str) -> List[TOCEntry]:
    """Get current table of contents."""
    manager = get_report_structure_manager(investigation_id)
    return manager.structure.toc if manager.structure else []

@router.post("/api/report-build/{investigation_id}/verify-alignment")
async def verify_alignment(
    investigation_id: str,
    reference_doc: UploadFile
) -> List[AlignmentDiff]:
    """Verify alignment against reference document."""
    parser = DocumentParser()
    reference = await parser.parse(reference_doc.filename)
    
    manager = get_report_structure_manager(investigation_id)
    current_elements = manager.get_canvas_elements()
    
    verifier = AlignmentVerifier()
    return verifier.compare(reference, current_elements)
```

### 6.3 Report Builder Frontend

```typescript
// components/report-builder/ReportBuilder.tsx

export function ReportBuilder({ investigationId }: { investigationId: string }) {
  const [structure, setStructure] = useState<ReportStructure | null>(null);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [preview, setPreview] = useState<boolean>(false);
  
  return (
    <div className="report-builder">
      <div className="builder-sidebar">
        <h3>Report Structure</h3>
        
        <div className="structure-tree">
          {structure?.sections.map(section => (
            <SectionItem
              key={section.id}
              section={section}
              isActive={activeSection === section.id}
              onClick={() => setActiveSection(section.id)}
            />
          ))}
        </div>
        
        <button onClick={() => insertSection()}>+ Add Section</button>
        
        <div className="toc-preview">
          <h4>Table of Contents</h4>
          <TOCPreview entries={structure?.toc || []} />
        </div>
      </div>
      
      <div className="builder-main">
        {activeSection && (
          <SectionEditor
            section={structure?.sections.find(s => s.id === activeSection)}
            onGenerate={() => generateSection(activeSection)}
            onSave={updateSection}
          />
        )}
      </div>
      
      <div className="builder-footer">
        <span>Total Pages: {structure?.total_pages || 0}</span>
        <button onClick={() => setPreview(true)}>Preview</button>
        <button onClick={() => verifyAlignment()}>Verify Alignment</button>
        <button onClick={() => finalizeReport()}>Finalize</button>
      </div>
      
      {preview && (
        <ReportPreviewModal
          structure={structure}
          onClose={() => setPreview(false)}
        />
      )}
    </div>
  );
}
```

---

## Phase 7: Integration - Deep Research Orchestrator

### 7.1 Main Orchestrator

```python
# app/services/deep_research/orchestrator.py

class DeepResearchOrchestrator:
    """Main orchestrator combining all components."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.llm = LLMService()
        self.investigation_id: Optional[str] = None
        
        # Components
        self.thought_engine: Optional[ThoughtEngine] = None
        self.plan_manager: Optional[PlanManager] = None
        self.human_loop: Optional[HumanLoopManager] = None
        self.report_builder: Optional[ReportStructureManager] = None
        
        # State
        self.status = "idle"
        self.current_phase: Optional[str] = None
        self.evidence_collected: List[str] = []
    
    async def start_investigation(
        self,
        scenario: str,
        metadata: Dict[str, Any]
    ) -> AsyncIterator[ThoughtNode]:
        """Start a new deep research investigation."""
        
        # Initialize components
        self.investigation_id = f"inv-{uuid4().hex[:12]}"
        self.thought_engine = ThoughtEngine(self.investigation_id, self.llm)
        self.human_loop = HumanLoopManager(self.investigation_id)
        self.plan_manager = PlanManager(self.investigation_id, self.llm)
        
        self.status = "analyzing"
        
        # Phase 1: Analyze scenario
        async for thought in self._analyze_scenario(scenario, metadata):
            yield thought
        
        # Phase 2: Generate plan
        async for thought in self._generate_plan():
            yield thought
        
        # Wait for plan approval
        self.status = "awaiting_approval"
        yield ThoughtNode(
            id="approval-gate",
            type="decision",
            title="Plan Ready for Review",
            content="Review and approve the investigation plan to continue.",
            status="complete"
        )
    
    async def execute_approved_plan(self) -> AsyncIterator[ThoughtNode]:
        """Execute the approved investigation plan."""
        
        if self.plan_manager.plan.status != "approved":
            raise ValueError("Plan must be approved before execution")
        
        self.status = "executing"
        
        for phase in self.plan_manager.plan.phases:
            self.current_phase = phase.id
            
            # Execute phase
            async for thought in self._execute_phase(phase):
                yield thought
            
            # Check if human input needed
            if self.human_loop.has_pending_questions():
                self.status = "paused"
                yield ThoughtNode(
                    id=f"pause-{phase.id}",
                    type="question",
                    title="Human Input Required",
                    content="Waiting for answers to continue.",
                    status="thinking"
                )
                
                # Wait for answers
                await self.human_loop.wait_for_all_answers()
                self.status = "executing"
        
        # Build report
        async for thought in self._build_report():
            yield thought
        
        self.status = "complete"
    
    async def _execute_phase(self, phase: PlanPhase) -> AsyncIterator[ThoughtNode]:
        """Execute a single phase with hypothesis testing."""
        
        yield ThoughtNode(
            id=f"phase-start-{phase.id}",
            type="action",
            title=f"Starting Phase: {phase.title}",
            content=phase.description,
            status="thinking"
        )
        
        for step in phase.steps:
            # Execute step
            async for thought in self._execute_step(step):
                yield thought
            
            # Store evidence
            evidence_ids = await self._store_step_evidence(step)
            self.evidence_collected.extend(evidence_ids)
        
        # Generate phase summary
        summary = await self._generate_phase_summary(phase)
        
        yield ThoughtNode(
            id=f"phase-complete-{phase.id}",
            type="finding",
            title=f"Phase Complete: {phase.title}",
            content=summary,
            status="complete"
        )
    
    async def _execute_step(self, step: PlanStep) -> AsyncIterator[ThoughtNode]:
        """Execute a single step using appropriate module."""
        
        yield ThoughtNode(
            id=f"step-{step.id}",
            type="action",
            title=step.title,
            content=f"Executing: {step.description}",
            status="thinking"
        )
        
        # Construct hypothesis for this step
        hypothesis = await self._construct_hypothesis(step)
        
        yield ThoughtNode(
            id=f"hypothesis-{step.id}",
            type="reasoning",
            title=f"Hypothesis: {hypothesis.description}",
            content=f"Testing: {hypothesis.description}",
            status="thinking"
        )
        
        # Execute module analysis
        if step.module:
            result = await self._run_module(step.module, step)
            
            # Store in evidence vault
            evidence_id = await EvidenceVault.add(result)
            step.outputs.append(evidence_id)
            
            # Test hypothesis
            verdict = await self._test_hypothesis(hypothesis, result)
            
            yield ThoughtNode(
                id=f"verdict-{step.id}",
                type="finding",
                title=f"Verdict: {verdict.status}",
                content=f"Confidence: {verdict.confidence:.0%}\n{verdict.reasoning}",
                status="complete"
            )
        
        # Check if we need human input
        if self._needs_clarification(step, result):
            question = await self.human_loop.ask(
                title=f"Clarification needed for {step.title}",
                description=self._generate_clarification_question(step, result),
                priority=QuestionPriority.MEDIUM,
                question_type=QuestionType.SINGLE_CHOICE,
                options=self._generate_options(step, result)
            )
            
            # Incorporate answer
            await self._incorporate_answer(step, question)
        
        step.status = "complete"
        
        yield ThoughtNode(
            id=f"step-complete-{step.id}",
            type="action",
            title=f"Step Complete: {step.title}",
            content=self._summarize_step(step),
            status="complete"
        )
```

### 7.2 API Routes

```python
# app/routes/deep_research.py

@router.post("/api/deep-research/start")
async def start_deep_research(request: StartRequest):
    """Start a new deep research investigation."""
    orchestrator = DeepResearchOrchestrator(request.case_id)
    
    # Start in background, stream via SSE
    task_id = await start_background_task(
        orchestrator.start_investigation,
        request.scenario,
        request.metadata
    )
    
    return {"investigation_id": orchestrator.investigation_id, "task_id": task_id}

@router.get("/api/deep-research/{investigation_id}/stream")
async def stream_thoughts(investigation_id: str):
    """Stream investigation thoughts via SSE."""
    orchestrator = get_orchestrator(investigation_id)
    
    async def event_generator():
        async for thought in orchestrator.get_thought_stream():
            yield {
                "event": "thought",
                "data": json.dumps(thought.dict())
            }
    
    return EventSourceResponse(event_generator())

@router.post("/api/deep-research/{investigation_id}/approve-plan")
async def approve_plan(investigation_id: str, approver: str):
    """Approve the investigation plan."""
    orchestrator = get_orchestrator(investigation_id)
    await orchestrator.plan_manager.approve(approver)
    return {"status": "approved"}

@router.post("/api/deep-research/{investigation_id}/execute")
async def execute_plan(investigation_id: str):
    """Execute the approved plan."""
    orchestrator = get_orchestrator(investigation_id)
    
    task_id = await start_background_task(
        orchestrator.execute_approved_plan
    )
    
    return {"task_id": task_id}

@router.post("/api/deep-research/{investigation_id}/pause")
async def pause_investigation(investigation_id: str):
    """Pause the investigation."""
    orchestrator = get_orchestrator(investigation_id)
    orchestrator.pause()
    return {"status": "paused"}

@router.post("/api/deep-research/{investigation_id}/resume")
async def resume_investigation(investigation_id: str):
    """Resume the investigation."""
    orchestrator = get_orchestrator(investigation_id)
    orchestrator.resume()
    return {"status": "resumed"}

@router.get("/api/deep-research/{investigation_id}/status")
async def get_status(investigation_id: str):
    """Get current investigation status."""
    orchestrator = get_orchestrator(investigation_id)
    return {
        "status": orchestrator.status,
        "current_phase": orchestrator.current_phase,
        "evidence_count": len(orchestrator.evidence_collected),
        "plan_status": orchestrator.plan_manager.plan.status if orchestrator.plan_manager else None
    }

@router.get("/api/llm/providers")
async def list_providers():
    """List available LLM providers."""
    return {
        "providers": ["gemini", "ollama"],
        "active": LLMService().active_provider
    }

@router.post("/api/llm/switch")
async def switch_provider(request: SwitchProviderRequest):
    """Switch active LLM provider."""
    llm = LLMService()
    llm.switch_provider(request.provider)
    return {"active": llm.active_provider}
```

---

## Implementation Todos

### Phase 1: LLM Abstraction (Day 1-2)
- [ ] llm-provider-base: Create LLMProvider abstract base class
- [ ] llm-gemini: Implement GeminiProvider with streaming
- [ ] llm-ollama: Implement OllamaProvider with streaming  
- [ ] llm-service: Create unified LLMService with switching
- [ ] llm-config: Add configuration for both providers
- [ ] llm-tests: Test provider switching and streaming

### Phase 2: Chain-of-Thought (Day 3-5)
- [ ] thought-model: Create ThoughtNode data model
- [ ] thought-engine: Implement ThoughtEngine with streaming
- [ ] thought-sse: Create SSE endpoint for thought streaming
- [ ] thought-stream-ui: Build ThoughtStream React component
- [ ] thought-tree-ui: Build ThoughtTree React component
- [ ] thought-tests: Integration tests for thought system

### Phase 3: Plan Editor (Day 6-8)
- [ ] plan-model: Create InvestigationPlan data model
- [ ] plan-api: Create plan CRUD and reorder endpoints
- [ ] plan-commands: Implement user command processing
- [ ] plan-approval: Add approval workflow
- [ ] plan-editor-ui: Build PlanEditor React component
- [ ] plan-dnd: Add drag-drop reordering
- [ ] plan-tests: Test plan modification flows

### Phase 4: Human-in-Loop (Day 9-11)
- [ ] hil-model: Create HumanQuestion data model
- [ ] hil-manager: Implement HumanLoopManager
- [ ] hil-websocket: Create WebSocket endpoint
- [ ] hil-modal-ui: Build BlockingQuestionModal
- [ ] hil-panel-ui: Build QuestionSidePanel
- [ ] hil-notify-ui: Build NotificationQueue
- [ ] hil-tests: Test question delivery and answering

### Phase 5: Document Parser (Day 12-14)
- [ ] parser-pdf: Implement PDF layout parser
- [ ] parser-docx: Implement DOCX layout parser
- [ ] parser-model: Create ParsedDocument model
- [ ] align-verify: Implement AlignmentVerifier
- [ ] align-auto: Implement auto-align correction
- [ ] parser-api: Create parser API endpoints
- [ ] parser-ui: Build reference document UI
- [ ] parser-tests: Test parsing and alignment

### Phase 6: Report Builder (Day 15-18)
- [ ] report-structure: Create ReportStructure model
- [ ] report-manager: Implement ReportStructureManager
- [ ] report-hybrid: Implement hybrid build (structure → fill)
- [ ] report-toc: Implement auto-TOC generation
- [ ] report-reflow: Implement page reflow on changes
- [ ] report-api: Create report builder API
- [ ] report-builder-ui: Build ReportBuilder component
- [ ] report-tests: Test report building flows

### Phase 7: Integration (Day 19-22)
- [ ] orchestrator: Create DeepResearchOrchestrator
- [ ] integration-api: Create main API routes
- [ ] integration-ui: Build main DeepResearch page
- [ ] e2e-flow: End-to-end investigation flow
- [ ] e2e-tests: Full integration tests
- [ ] docs: Documentation and usage guide

---

## File Structure

```
operation-room/backend/
├── app/
│   ├── services/
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py          # LLMProvider ABC
│   │   │   ├── gemini.py            # GeminiProvider
│   │   │   ├── ollama.py            # OllamaProvider
│   │   │   └── service.py           # LLMService
│   │   │
│   │   ├── deep_research/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py      # Main orchestrator
│   │   │   ├── thought_engine.py    # Chain-of-thought
│   │   │   └── plan_manager.py      # Plan management
│   │   │
│   │   ├── human_loop/
│   │   │   ├── __init__.py
│   │   │   ├── manager.py           # Question manager
│   │   │   └── models.py            # Question models
│   │   │
│   │   ├── document_parser/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py            # PDF/DOCX parser
│   │   │   └── alignment.py         # Alignment verification
│   │   │
│   │   └── report_builder/
│   │       ├── __init__.py
│   │       ├── structure.py         # Structure manager
│   │       └── generator.py         # Content generator
│   │
│   └── routes/
│       ├── deep_research.py         # Deep research API
│       ├── plan_editor.py           # Plan editing API
│       ├── human_loop.py            # Human-in-loop API
│       └── report_builder.py        # Report builder API

operation-room/frontend/src/
├── components/
│   ├── deep-research/
│   │   ├── DeepResearchPage.tsx     # Main page
│   │   ├── ThoughtStream.tsx        # Streaming thoughts
│   │   ├── ThoughtTree.tsx          # Tree view
│   │   └── ProgressIndicator.tsx    # Progress UI
│   │
│   ├── plan-editor/
│   │   ├── PlanEditor.tsx           # Plan editor
│   │   ├── PhaseCard.tsx            # Phase display
│   │   ├── StepItem.tsx             # Step item
│   │   └── ApprovalGate.tsx         # Approval UI
│   │
│   ├── human-loop/
│   │   ├── HumanLoopProvider.tsx    # Context provider
│   │   ├── BlockingQuestionModal.tsx
│   │   ├── QuestionSidePanel.tsx
│   │   └── NotificationQueue.tsx
│   │
│   └── report-builder/
│       ├── ReportBuilder.tsx        # Main builder
│       ├── StructureTree.tsx        # Section tree
│       ├── SectionEditor.tsx        # Section editing
│       ├── TOCPreview.tsx           # TOC display
│       └── AlignmentChecker.tsx     # Alignment UI
```

---

## Environment Configuration

```bash
# .env file

# LLM Configuration
LLM_PROVIDER=ollama                    # "gemini" or "ollama"
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# Investigation settings
MAX_THINKING_TIME=300                  # seconds
HUMAN_LOOP_TIMEOUT=600                 # seconds
AUTO_SAVE_INTERVAL=30                  # seconds

# Report settings
DEFAULT_TEMPLATE=technical
PAGE_SIZE=A4
MARGIN_MM=20
```

---

## Quick Start

```bash
# 1. Start Ollama (if using local LLM)
ollama serve
ollama pull qwen3:8b

# 2. Set environment
export LLM_PROVIDER=ollama
export GEMINI_API_KEY=your-key  # if using Gemini

# 3. Start backend
cd operation-room/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 4. Start frontend
cd operation-room/frontend
npm install
npm run dev

# 5. Access
open http://localhost:3000/deep-research
```

---

## Next Steps

1. **Start with Phase 1** (LLM Abstraction) - Foundation for all AI features
2. **Then Phase 2** (Chain-of-Thought) - Core user experience
3. **Continue sequentially** through remaining phases
4. **Integration testing** after each phase

Ready to begin implementation?
