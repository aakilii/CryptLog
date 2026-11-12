"""
Chat Service for Investigation Intake

Provides conversational interface for gathering investigation context.
AI asks clarifying questions until sufficient information is collected.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from operation_room.database import open_vault

# Oracle 26AI Integration - Session Memory
try:
    from operation_room.services.session_memory import get_session_memory, InvestigationPhase
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChatPhase(str, Enum):
    """Phases of the chat-driven investigation intake."""
    GREETING = "greeting"
    SCENARIO_GATHERING = "scenario_gathering"
    TIMELINE_CLARIFICATION = "timeline_clarification"
    SCOPE_DEFINITION = "scope_definition"
    ACTOR_IDENTIFICATION = "actor_identification"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    HYPOTHESIS_REVIEW = "hypothesis_review"
    READY_FOR_ANALYSIS = "ready_for_analysis"
    ANALYSIS_IN_PROGRESS = "analysis_in_progress"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"


class MessageRole(str, Enum):
    """Message sender roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ChatMessage:
    """A single message in the chat history."""
    message_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class InvestigationContext:
    """Accumulated context from chat conversation."""
    scenario: Optional[str] = None
    timeline_start: Optional[str] = None
    timeline_end: Optional[str] = None
    scope: Optional[str] = None
    actors_of_interest: List[str] = field(default_factory=list)
    systems_of_interest: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    incident_type: Optional[str] = None
    severity_estimate: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "timeline_start": self.timeline_start,
            "timeline_end": self.timeline_end,
            "scope": self.scope,
            "actors_of_interest": self.actors_of_interest,
            "systems_of_interest": self.systems_of_interest,
            "data_sources": self.data_sources,
            "incident_type": self.incident_type,
            "severity_estimate": self.severity_estimate,
            "additional_context": self.additional_context
        }
    
    def completeness_score(self) -> float:
        """Calculate how complete the context is (0.0-1.0)."""
        fields = [
            self.scenario is not None,
            self.timeline_start is not None or self.timeline_end is not None,
            self.scope is not None,
            len(self.actors_of_interest) > 0,
            len(self.systems_of_interest) > 0,
            self.incident_type is not None
        ]
        return sum(fields) / len(fields)
    
    def missing_fields(self) -> List[str]:
        """Return list of missing/incomplete fields."""
        missing = []
        if not self.scenario:
            missing.append("scenario")
        if not self.timeline_start and not self.timeline_end:
            missing.append("timeline")
        if not self.scope:
            missing.append("scope")
        if not self.actors_of_interest:
            missing.append("actors_of_interest")
        if not self.systems_of_interest:
            missing.append("systems_of_interest")
        if not self.incident_type:
            missing.append("incident_type")
        return missing


@dataclass  
class ChatSession:
    """A chat session for investigation intake."""
    session_id: str
    case_id: str
    investigation_id: Optional[str]
    phase: ChatPhase
    context: InvestigationContext
    messages: List[ChatMessage]
    hypotheses: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    execution_mode: Optional[str] = None  # autopilot, smart_recommendation, run_all
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            "phase": self.phase.value,
            "context": self.context.to_dict(),
            "messages": [m.to_dict() for m in self.messages],
            "hypotheses": self.hypotheses,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "execution_mode": self.execution_mode
        }


# Clarification question templates per phase
CLARIFICATION_QUESTIONS = {
    ChatPhase.SCENARIO_GATHERING: [
        "Can you describe what happened or what you suspect occurred?",
        "What triggered this investigation? Was there an alert, user report, or routine audit?",
        "Is this a suspected security incident, policy violation, or compliance audit?"
    ],
    ChatPhase.TIMELINE_CLARIFICATION: [
        "When did this incident potentially start? Do you have an approximate date/time?",
        "When was it first detected or reported?",
        "Is the incident ongoing or has it been contained?"
    ],
    ChatPhase.SCOPE_DEFINITION: [
        "Which systems or networks are potentially affected?",
        "Is this limited to a specific department, location, or the entire organization?",
        "Are there any systems we should prioritize or exclude from analysis?"
    ],
    ChatPhase.ACTOR_IDENTIFICATION: [
        "Are there any specific users, accounts, or IP addresses you suspect?",
        "Do you have a list of potential victims or compromised accounts?",
        "Are there any external entities (vendors, partners) involved?"
    ]
}

# System prompts for AI clarification
SYSTEM_PROMPTS = {
    "clarification": """You are a digital forensics investigator conducting an intake interview.
Your goal is to gather enough information to begin a thorough investigation.

Current context gathered so far:
{context}

Missing information: {missing}

Ask ONE focused clarifying question to fill in the gaps. Be professional but conversational.
If the user provides information, acknowledge it and ask about the next missing piece.
Do not make assumptions - ask for specifics.

Respond with just your question, no preamble.""",

    "context_extraction": """You are analyzing a user's response to extract investigation context.

User message: {message}
Current context: {context}

Extract any relevant information and return a JSON object with these fields (only include fields that have new information):
{{
    "scenario": "description of what happened",
    "timeline_start": "ISO datetime or null",
    "timeline_end": "ISO datetime or null", 
    "scope": "description of affected scope",
    "actors_of_interest": ["list", "of", "actors"],
    "systems_of_interest": ["list", "of", "systems"],
    "incident_type": "data_breach|insider_threat|malware|unauthorized_access|policy_violation|other",
    "severity_estimate": "critical|high|medium|low|unknown"
}}

Return ONLY valid JSON, no explanation.""",

    "hypothesis_generation": """You are a senior forensic analyst generating investigation hypotheses.

Investigation Context:
{context}

Generate 3-5 testable hypotheses for this investigation. Include:
1. A null hypothesis (H0: no malicious activity occurred)
2. Alternative hypotheses ranked by likelihood

Return JSON:
{{
    "null_hypothesis": {{
        "id": "H0",
        "name": "No malicious activity",
        "description": "...",
        "evidence_needed": ["list of evidence types"],
        "confidence_threshold": 0.8
    }},
    "alternative_hypotheses": [
        {{
            "id": "H1",
            "name": "...",
            "description": "...",
            "evidence_needed": ["..."],
            "confidence_threshold": 0.7,
            "priority": "high|medium|low",
            "mitre_techniques": ["T1234", "T5678"]
        }}
    ]
}}

Return ONLY valid JSON."""
}


class ChatService:
    """Service for managing investigation chat sessions."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._ensure_tables()
        
        # Oracle 26AI: Initialize session memory for semantic context
        self._session_memory_instances: Dict[str, Any] = {}
    
    def _get_session_memory(self, session_id: str):
        """Get or create SessionMemory instance for a session."""
        if not MEMORY_AVAILABLE:
            return None
        if session_id not in self._session_memory_instances:
            self._session_memory_instances[session_id] = get_session_memory(self.case_id, session_id)
        return self._session_memory_instances[session_id]
    
    def _ensure_tables(self):
        """Ensure chat tables exist in the case vault."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    investigation_id VARCHAR,
                    phase VARCHAR NOT NULL,
                    context_json JSON,
                    hypotheses_json JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id VARCHAR PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    role VARCHAR NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session 
                ON chat_messages(session_id, timestamp)
            """)
        finally:
            conn.close()
    
    def start_session(self, investigation_id: Optional[str] = None) -> ChatSession:
        """Start a new chat session for investigation intake."""
        session_id = f"chat-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        
        session = ChatSession(
            session_id=session_id,
            case_id=self.case_id,
            investigation_id=investigation_id,
            phase=ChatPhase.GREETING,
            context=InvestigationContext(),
            messages=[],
            hypotheses=[],
            created_at=now,
            updated_at=now
        )
        
        # Add greeting message
        greeting = ChatMessage(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.ASSISTANT,
            content="Hello! I'm your forensic investigation assistant. I'll help you set up and conduct a thorough investigation. Let's start by understanding what happened. Can you describe the incident or suspicious activity you're investigating?",
            timestamp=now,
            metadata={"phase": ChatPhase.GREETING.value}
        )
        session.messages.append(greeting)
        session.phase = ChatPhase.SCENARIO_GATHERING
        
        # Save to database
        self._save_session(session)
        
        # Oracle 26AI: Store greeting in session memory for semantic retrieval
        memory = self._get_session_memory(session_id)
        if memory:
            try:
                memory.add_turn(
                    role="assistant",
                    content=greeting.content,
                    phase=InvestigationPhase.DISCOVERY,
                    metadata={"chat_phase": ChatPhase.GREETING.value, "is_greeting": True}
                )
            except Exception as e:
                logger.warning(f"Failed to store greeting in memory: {e}")
        
        logger.info(f"Started chat session {session_id} for case {self.case_id}")
        return session
    
    def _save_session(self, session: ChatSession):
        """Save session to database."""
        import json
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO chat_sessions 
                (session_id, case_id, investigation_id, phase, context_json, hypotheses_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                session.session_id,
                session.case_id,
                session.investigation_id,
                session.phase.value,
                json.dumps(session.context.to_dict()),
                json.dumps(session.hypotheses),
                session.created_at.isoformat(),
                session.updated_at.isoformat()
            ])
            
            # Save messages
            for msg in session.messages:
                conn.execute("""
                    INSERT OR REPLACE INTO chat_messages
                    (message_id, session_id, role, content, metadata_json, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    msg.message_id,
                    session.session_id,
                    msg.role.value,
                    msg.content,
                    json.dumps(msg.metadata),
                    msg.timestamp.isoformat()
                ])
        finally:
            conn.close()
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Retrieve a chat session by ID."""
        import json
        conn = open_vault(self.case_id)
        try:
            row = conn.execute("""
                SELECT session_id, case_id, investigation_id, phase, 
                       context_json, hypotheses_json, created_at, updated_at
                FROM chat_sessions WHERE session_id = ?
            """, [session_id]).fetchone()
            
            if not row:
                return None
            
            # Load messages
            msg_rows = conn.execute("""
                SELECT message_id, role, content, metadata_json, timestamp
                FROM chat_messages WHERE session_id = ?
                ORDER BY timestamp
            """, [session_id]).fetchall()
            
            messages = [
                ChatMessage(
                    message_id=m[0],
                    role=MessageRole(m[1]),
                    content=m[2],
                    timestamp=datetime.fromisoformat(m[4]) if isinstance(m[4], str) else m[4],
                    metadata=json.loads(m[3]) if m[3] else {}
                )
                for m in msg_rows
            ]
            
            context_dict = json.loads(row[4]) if row[4] else {}
            context = InvestigationContext(
                scenario=context_dict.get("scenario"),
                timeline_start=context_dict.get("timeline_start"),
                timeline_end=context_dict.get("timeline_end"),
                scope=context_dict.get("scope"),
                actors_of_interest=context_dict.get("actors_of_interest", []),
                systems_of_interest=context_dict.get("systems_of_interest", []),
                data_sources=context_dict.get("data_sources", []),
                incident_type=context_dict.get("incident_type"),
                severity_estimate=context_dict.get("severity_estimate"),
                additional_context=context_dict.get("additional_context", {})
            )
            
            return ChatSession(
                session_id=row[0],
                case_id=row[1],
                investigation_id=row[2],
                phase=ChatPhase(row[3]),
                context=context,
                messages=messages,
                hypotheses=json.loads(row[5]) if row[5] else [],
                created_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
                updated_at=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7]
            )
        finally:
            conn.close()
    
    async def process_message(
        self, 
        session_id: str, 
        user_message: str,
        llm_service=None
    ) -> Dict[str, Any]:
        """
        Process a user message and generate AI response.
        
        Returns dict with:
        - response: AI response message
        - phase: current phase
        - context: updated context
        - needs_input: whether more user input is needed
        - hypotheses: list of hypotheses (if generated)
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        now = datetime.utcnow()
        
        # Oracle 26AI: Get semantic context from past turns
        memory = self._get_session_memory(session_id)
        past_context = []
        if memory:
            try:
                # Map ChatPhase to InvestigationPhase
                phase_map = {
                    ChatPhase.GREETING: InvestigationPhase.DISCOVERY,
                    ChatPhase.SCENARIO_GATHERING: InvestigationPhase.DISCOVERY,
                    ChatPhase.TIMELINE_CLARIFICATION: InvestigationPhase.ANALYSIS,
                    ChatPhase.SCOPE_DEFINITION: InvestigationPhase.ANALYSIS,
                    ChatPhase.ACTOR_IDENTIFICATION: InvestigationPhase.ANALYSIS,
                    ChatPhase.HYPOTHESIS_GENERATION: InvestigationPhase.HYPOTHESIS,
                    ChatPhase.HYPOTHESIS_REVIEW: InvestigationPhase.HYPOTHESIS,
                    ChatPhase.READY_FOR_ANALYSIS: InvestigationPhase.VALIDATION,
                    ChatPhase.ANALYSIS_IN_PROGRESS: InvestigationPhase.VALIDATION,
                    ChatPhase.REPORT_GENERATION: InvestigationPhase.REPORTING,
                    ChatPhase.COMPLETED: InvestigationPhase.REVIEW,
                }
                inv_phase = phase_map.get(session.phase, InvestigationPhase.DISCOVERY)
                past_context = memory.get_context_for_query(user_message, max_tokens=2000)
                logger.debug(f"Retrieved {len(past_context)} past turns for context")
            except Exception as e:
                logger.warning(f"Failed to retrieve memory context: {e}")
        
        # Add user message
        user_msg = ChatMessage(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.USER,
            content=user_message,
            timestamp=now,
            metadata={"phase": session.phase.value}
        )
        session.messages.append(user_msg)
        
        # Oracle 26AI: Store user message in memory
        if memory:
            try:
                memory.add_turn(
                    role="user",
                    content=user_message,
                    phase=inv_phase,
                    metadata={"chat_phase": session.phase.value}
                )
            except Exception as e:
                logger.warning(f"Failed to store user message in memory: {e}")
        
        # Extract context from user message (enhanced with past context)
        session.context = await self._extract_context(session, user_message, llm_service, past_context)
        
        # Determine next phase based on completeness
        completeness = session.context.completeness_score()
        missing = session.context.missing_fields()
        
        response_content = ""
        needs_input = True
        
        if completeness >= 0.7 and session.phase != ChatPhase.HYPOTHESIS_REVIEW:
            # Enough context - generate hypotheses
            if session.phase != ChatPhase.HYPOTHESIS_GENERATION:
                session.phase = ChatPhase.HYPOTHESIS_GENERATION
                session.hypotheses = await self._generate_hypotheses(session, llm_service)
                session.phase = ChatPhase.HYPOTHESIS_REVIEW
                
                # Format hypotheses for display
                hyp_text = self._format_hypotheses(session.hypotheses)
                response_content = f"""Based on what you've told me, I've gathered the following context:

**Scenario:** {session.context.scenario}
**Timeline:** {session.context.timeline_start or 'Not specified'} to {session.context.timeline_end or 'Not specified'}
**Scope:** {session.context.scope or 'Full investigation'}
**Actors of Interest:** {', '.join(session.context.actors_of_interest) or 'None identified'}
**Systems:** {', '.join(session.context.systems_of_interest) or 'All systems'}
**Incident Type:** {session.context.incident_type or 'Unknown'}

I've generated the following hypotheses to investigate:

{hyp_text}

Would you like to:
1. **Approve** these hypotheses and proceed to analysis
2. **Modify** any hypothesis
3. **Add** your own hypothesis
4. **Provide more context** before proceeding

Please respond with your choice or additional information."""
        
        elif session.phase == ChatPhase.HYPOTHESIS_REVIEW:
            # Check if user approves hypotheses
            lower_msg = user_message.lower()
            if any(word in lower_msg for word in ['approve', 'proceed', 'yes', 'continue', 'start analysis', 'looks good', 'ok', 'okay']):
                session.phase = ChatPhase.READY_FOR_ANALYSIS
                needs_input = False
                response_content = """Excellent! I'll now begin the investigation analysis.

I'll run the following modules:
• **Timeline Analysis** - Reconstruct sequence of events
• **Anomaly Detection** - Identify statistical outliers
• **Network Analysis** - Check for data exfiltration
• **CRUD Analysis** - Analyze data access patterns
• **Depth Analysis** - Assess impact scope
• **Correlation** - Link events across systems

This may take a few minutes. I'll provide updates as each module completes."""
            elif any(word in lower_msg for word in ['add', 'another hypothesis', 'my own']):
                response_content = "Please describe your additional hypothesis. Include what you suspect happened and what evidence would support or refute it."
            elif any(word in lower_msg for word in ['modify', 'change', 'edit']):
                response_content = "Which hypothesis would you like to modify? Please specify the hypothesis number (H0, H1, H2, etc.) and describe the changes."
            else:
                # Treat as additional context or hypothesis
                if 'hypothesis' in lower_msg or 'suspect' in lower_msg or 'h1' in lower_msg or 'h2' in lower_msg:
                    # User is adding/modifying hypothesis
                    new_hyp = {
                        "id": f"H{len(session.hypotheses)}",
                        "name": "User-provided hypothesis",
                        "description": user_message,
                        "evidence_needed": [],
                        "confidence_threshold": 0.6,
                        "priority": "high",
                        "source": "user"
                    }
                    session.hypotheses.append(new_hyp)
                    response_content = f"""I've added your hypothesis as {new_hyp['id']}:
"{user_message}"

Current hypotheses:
{self._format_hypotheses(session.hypotheses)}

Would you like to approve and proceed, or make more changes?"""
                else:
                    response_content = "I'm not sure what you'd like to do. Please respond with:\n- **Approve** to proceed with analysis\n- **Add** to add your own hypothesis\n- **Modify** to change an existing hypothesis"
        
        else:
            # Still gathering context - ask clarifying question
            response_content = await self._generate_clarification(session, missing, llm_service)
            
            # Update phase based on what's missing
            if "scenario" in missing:
                session.phase = ChatPhase.SCENARIO_GATHERING
            elif "timeline" in missing:
                session.phase = ChatPhase.TIMELINE_CLARIFICATION
            elif "scope" in missing or "systems_of_interest" in missing:
                session.phase = ChatPhase.SCOPE_DEFINITION
            elif "actors_of_interest" in missing:
                session.phase = ChatPhase.ACTOR_IDENTIFICATION
        
        # Add assistant response
        assistant_msg = ChatMessage(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.ASSISTANT,
            content=response_content,
            timestamp=datetime.utcnow(),
            metadata={"phase": session.phase.value}
        )
        session.messages.append(assistant_msg)
        session.updated_at = datetime.utcnow()
        
        # Oracle 26AI: Store assistant response in memory
        if memory:
            try:
                memory.add_turn(
                    role="assistant",
                    content=response_content,
                    phase=inv_phase,
                    metadata={"chat_phase": session.phase.value}
                )
            except Exception as e:
                logger.warning(f"Failed to store assistant message in memory: {e}")
        
        # Save session
        self._save_session(session)
        
        # Generate suggested prompts based on phase
        suggested_prompts = self._get_suggested_prompts(session.phase, session.context)
        
        return {
            "response": response_content,
            "phase": session.phase.value,
            "context": session.context.to_dict(),
            "context_completeness": session.context.completeness_score(),
            "extracted_context": session.context.to_dict(),
            "completeness": session.context.completeness_score(),
            "needs_input": needs_input,
            "hypotheses": session.hypotheses if session.hypotheses else None,
            "suggested_prompts": suggested_prompts,
            "ready_for_analysis": session.phase == ChatPhase.READY_FOR_ANALYSIS
        }
    
    def _get_suggested_prompts(self, phase: ChatPhase, context: InvestigationContext) -> List[str]:
        """Get suggested prompts based on current phase."""
        prompts_by_phase = {
            ChatPhase.SCENARIO_GATHERING: [
                "There was a potential data breach involving...",
                "I suspect unauthorized access to...",
                "We detected suspicious activity when..."
            ],
            ChatPhase.TIMELINE_CLARIFICATION: [
                "The incident started around...",
                "We first noticed this on...",
                "The suspicious activity occurred between..."
            ],
            ChatPhase.SCOPE_DEFINITION: [
                "The affected systems include...",
                "This impacts the following departments...",
                "Only the production environment is affected..."
            ],
            ChatPhase.ACTOR_IDENTIFICATION: [
                "The suspected users are...",
                "The affected accounts include...",
                "We believe the following employees are involved..."
            ],
            ChatPhase.HYPOTHESIS_REVIEW: [
                "Approve all hypotheses",
                "I want to add my own hypothesis",
                "Modify hypothesis H1"
            ],
            ChatPhase.READY_FOR_ANALYSIS: [
                "Start analysis",
                "Use autopilot mode",
                "Let me review the modules first"
            ]
        }
        return prompts_by_phase.get(phase, [])
    
    async def _extract_context(
        self, 
        session: ChatSession, 
        message: str,
        llm_service=None,
        past_context: List[Any] = None
    ) -> InvestigationContext:
        """Extract investigation context from user message using LLM.
        
        Args:
            session: Current chat session
            message: User message to extract context from
            llm_service: Optional LLM service for AI extraction
            past_context: Oracle 26AI - semantically similar past turns for context
        """
        import json
        
        context = session.context
        
        if llm_service:
            try:
                # Build enhanced context with memory (Oracle 26AI)
                memory_context = ""
                if past_context:
                    memory_context = "\n\n--- Relevant Past Context ---\n"
                    for turn in past_context[:5]:  # Top 5 relevant turns
                        if hasattr(turn, 'content'):
                            memory_context += f"[{turn.role}]: {turn.content[:200]}...\n"
                
                prompt = SYSTEM_PROMPTS["context_extraction"].format(
                    message=message,
                    context=json.dumps(context.to_dict())
                )
                
                # Append memory context if available
                if memory_context:
                    prompt += memory_context
                
                response = await llm_service.generate(prompt)
                
                # Parse JSON response
                extracted = json.loads(response)
                
                # Update context with extracted info
                if extracted.get("scenario"):
                    context.scenario = extracted["scenario"]
                if extracted.get("timeline_start"):
                    context.timeline_start = extracted["timeline_start"]
                if extracted.get("timeline_end"):
                    context.timeline_end = extracted["timeline_end"]
                if extracted.get("scope"):
                    context.scope = extracted["scope"]
                if extracted.get("actors_of_interest"):
                    context.actors_of_interest.extend(extracted["actors_of_interest"])
                    context.actors_of_interest = list(set(context.actors_of_interest))
                if extracted.get("systems_of_interest"):
                    context.systems_of_interest.extend(extracted["systems_of_interest"])
                    context.systems_of_interest = list(set(context.systems_of_interest))
                if extracted.get("incident_type"):
                    context.incident_type = extracted["incident_type"]
                if extracted.get("severity_estimate"):
                    context.severity_estimate = extracted["severity_estimate"]
                    
            except Exception as e:
                logger.warning(f"LLM context extraction failed: {e}, using rule-based extraction")
                context = self._rule_based_extraction(context, message)
        else:
            context = self._rule_based_extraction(context, message)
        
        return context
    
    def _rule_based_extraction(self, context: InvestigationContext, message: str) -> InvestigationContext:
        """Simple rule-based context extraction as fallback."""
        lower = message.lower()
        
        # If no scenario yet, use the message as scenario
        if not context.scenario and len(message) > 20:
            context.scenario = message
        
        # Extract incident types
        type_keywords = {
            "data_breach": ["breach", "leak", "exposed", "stolen data"],
            "insider_threat": ["insider", "employee", "internal", "terminated", "resigned", "former employee"],
            "malware": ["malware", "virus", "ransomware", "trojan"],
            "unauthorized_access": ["unauthorized", "hacked", "compromised", "break-in"],
            "policy_violation": ["policy", "violation", "compliance", "audit"]
        }
        for itype, keywords in type_keywords.items():
            if any(kw in lower for kw in keywords):
                context.incident_type = itype
                break
        
        # Extract severity hints
        if any(word in lower for word in ["critical", "urgent", "severe", "emergency"]):
            context.severity_estimate = "critical"
        elif any(word in lower for word in ["high", "serious", "significant"]):
            context.severity_estimate = "high"
        
        import re
        
        # Extract dates - various formats
        # Format: April 1-6, 2026 or April 1, 2026
        date_patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:-\d{1,2})?,?\s+\d{4}',
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY or M/D/YY
            r'\d{4}-\d{2}-\d{2}',  # ISO format YYYY-MM-DD
            r'\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, lower)
            if matches:
                # Use the first date as timeline_start
                if not context.timeline_start:
                    context.timeline_start = matches[0] if isinstance(matches[0], str) else matches[0][0]
                if len(matches) > 1 and not context.timeline_end:
                    context.timeline_end = matches[1] if isinstance(matches[1], str) else matches[1][0]
                break
        
        # Extract "between X and Y" pattern
        between_match = re.search(r'between\s+(.+?)\s+(?:and|to|-)\s+(.+?)(?:\.|,|$)', lower)
        if between_match:
            if not context.timeline_start:
                context.timeline_start = between_match.group(1)
            if not context.timeline_end:
                context.timeline_end = between_match.group(2)
        
        # Extract potential actors (simple pattern matching)
        # Email patterns
        emails = re.findall(r'[\w\.-]+@[\w\.-]+', message)
        context.actors_of_interest.extend(emails)
        
        # Username patterns (word before "user" or "account")
        user_patterns = re.findall(r'(\w+)(?:\s+user|\s+account)', lower)
        context.actors_of_interest.extend(user_patterns)
        
        # Named person patterns - "John Doe", "named X"
        named_patterns = re.findall(r'named\s+(\w+(?:\s+\w+)?)', message, re.IGNORECASE)
        context.actors_of_interest.extend(named_patterns)
        
        # Extract system/resource names after "access to" or "server" keywords
        system_patterns = re.findall(r'(?:access\s+to|server|database|system)[^\w]*(\w+(?:\s+\w+)?)', lower)
        context.systems_of_interest.extend(system_patterns)
        
        # Extract scope hints
        if not context.scope:
            if "organization" in lower or "company" in lower:
                context.scope = "organization-wide"
            elif "department" in lower:
                context.scope = "department"
            elif "customer" in lower:
                context.scope = "customer data"
        
        # Deduplicate
        context.actors_of_interest = list(set(context.actors_of_interest))
        context.systems_of_interest = list(set(context.systems_of_interest))
        
        return context
    
    async def _generate_hypotheses(
        self, 
        session: ChatSession,
        llm_service=None
    ) -> List[Dict[str, Any]]:
        """Generate investigation hypotheses using LLM."""
        import json
        
        if llm_service:
            try:
                prompt = SYSTEM_PROMPTS["hypothesis_generation"].format(
                    context=json.dumps(session.context.to_dict())
                )
                
                response = await llm_service.generate(prompt)
                result = json.loads(response)
                
                hypotheses = []
                if result.get("null_hypothesis"):
                    hypotheses.append(result["null_hypothesis"])
                if result.get("alternative_hypotheses"):
                    hypotheses.extend(result["alternative_hypotheses"])
                
                return hypotheses
                
            except Exception as e:
                logger.warning(f"LLM hypothesis generation failed: {e}, using templates")
        
        # Fallback: Template-based hypotheses
        return self._template_hypotheses(session.context)
    
    def _template_hypotheses(self, context: InvestigationContext) -> List[Dict[str, Any]]:
        """Generate template-based hypotheses as fallback."""
        hypotheses = [
            {
                "id": "H0",
                "name": "No malicious activity",
                "description": "The observed events are normal business operations or false positives.",
                "evidence_needed": ["normal_patterns", "authorized_access", "business_justification"],
                "confidence_threshold": 0.8,
                "priority": "low"
            }
        ]
        
        # Add hypotheses based on incident type
        if context.incident_type == "insider_threat":
            hypotheses.extend([
                {
                    "id": "H1",
                    "name": "Malicious insider data theft",
                    "description": f"One or more actors ({', '.join(context.actors_of_interest) or 'unknown'}) intentionally exfiltrated sensitive data.",
                    "evidence_needed": ["large_data_transfers", "after_hours_access", "unauthorized_file_access"],
                    "confidence_threshold": 0.7,
                    "priority": "high",
                    "mitre_techniques": ["T1567", "T1048"]
                },
                {
                    "id": "H2",
                    "name": "Negligent data handling",
                    "description": "Data exposure occurred through carelessness rather than malicious intent.",
                    "evidence_needed": ["policy_violations", "unencrypted_transfers", "public_sharing"],
                    "confidence_threshold": 0.6,
                    "priority": "medium"
                }
            ])
        elif context.incident_type == "unauthorized_access":
            hypotheses.extend([
                {
                    "id": "H1",
                    "name": "Compromised credentials",
                    "description": "An attacker gained access using stolen or guessed credentials.",
                    "evidence_needed": ["failed_logins", "unusual_login_location", "credential_stuffing"],
                    "confidence_threshold": 0.7,
                    "priority": "high",
                    "mitre_techniques": ["T1078", "T1110"]
                },
                {
                    "id": "H2",
                    "name": "Privilege escalation",
                    "description": "An authorized user escalated privileges beyond their role.",
                    "evidence_needed": ["permission_changes", "admin_access", "policy_bypass"],
                    "confidence_threshold": 0.6,
                    "priority": "high",
                    "mitre_techniques": ["T1068", "T1548"]
                }
            ])
        else:
            # Generic hypotheses
            hypotheses.extend([
                {
                    "id": "H1",
                    "name": "Security incident occurred",
                    "description": f"A security incident matching the described scenario occurred: {context.scenario or 'Unknown'}",
                    "evidence_needed": ["anomalous_activity", "timeline_correlation", "affected_assets"],
                    "confidence_threshold": 0.7,
                    "priority": "high"
                },
                {
                    "id": "H2",
                    "name": "Partial compromise",
                    "description": "Limited unauthorized activity occurred but was contained.",
                    "evidence_needed": ["limited_access", "contained_scope", "early_detection"],
                    "confidence_threshold": 0.6,
                    "priority": "medium"
                }
            ])
        
        return hypotheses
    
    async def _generate_clarification(
        self, 
        session: ChatSession, 
        missing: List[str],
        llm_service=None
    ) -> str:
        """Generate a clarifying question using LLM or templates."""
        import json
        
        if llm_service:
            try:
                prompt = SYSTEM_PROMPTS["clarification"].format(
                    context=json.dumps(session.context.to_dict()),
                    missing=", ".join(missing)
                )
                return await llm_service.generate(prompt)
            except Exception as e:
                logger.warning(f"LLM clarification failed: {e}, using templates")
        
        # Fallback to template questions
        if "scenario" in missing:
            return CLARIFICATION_QUESTIONS[ChatPhase.SCENARIO_GATHERING][0]
        elif "timeline" in missing:
            return CLARIFICATION_QUESTIONS[ChatPhase.TIMELINE_CLARIFICATION][0]
        elif "scope" in missing or "systems_of_interest" in missing:
            return CLARIFICATION_QUESTIONS[ChatPhase.SCOPE_DEFINITION][0]
        elif "actors_of_interest" in missing:
            return CLARIFICATION_QUESTIONS[ChatPhase.ACTOR_IDENTIFICATION][0]
        else:
            return "Is there any other information that might be relevant to this investigation?"
    
    def _format_hypotheses(self, hypotheses: List[Dict[str, Any]]) -> str:
        """Format hypotheses for display."""
        lines = []
        for h in hypotheses:
            priority = h.get("priority", "medium")
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority, "⚪")
            lines.append(f"**{h['id']}: {h['name']}** {priority_emoji}")
            lines.append(f"   {h['description']}")
            if h.get("evidence_needed"):
                lines.append(f"   Evidence needed: {', '.join(h['evidence_needed'])}")
            lines.append("")
        return "\n".join(lines)
    
    def approve_hypotheses(self, session_id: str) -> ChatSession:
        """Mark hypotheses as approved and ready for analysis."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session.phase = ChatPhase.READY_FOR_ANALYSIS
        session.updated_at = datetime.utcnow()
        self._save_session(session)
        return session
    
    # =========================================================================
    # ASYNC API METHODS (for routes)
    # =========================================================================
    
    async def create_session(self, investigation_id: Optional[str] = None) -> ChatSession:
        """Create a new chat session (async wrapper)."""
        return self.start_session(investigation_id)
    
    async def save_session(self, session: ChatSession):
        """Save session (async wrapper)."""
        self._save_session(session)
    
    async def generate_welcome_message(self, session: ChatSession) -> Dict[str, Any]:
        """Generate welcome message for new session."""
        return {
            "message": """Hello! I'm your forensic investigation assistant. I'll help you set up and conduct a thorough investigation.

To get started, please describe the incident or suspicious activity you're investigating. The more detail you can provide, the better I can help.

For example, you might tell me about:
• What triggered this investigation (alert, report, audit finding)
• What you suspect happened
• Any specific users, systems, or timeframes involved""",
            "prompts": [
                "I'm investigating a potential data breach...",
                "We noticed suspicious login activity...",
                "There's been unauthorized file access...",
                "I need to investigate a terminated employee's activity..."
            ]
        }
    
    async def get_message_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get message history for a session."""
        import json
        conn = open_vault(self.case_id)
        try:
            rows = conn.execute("""
                SELECT message_id, role, content, metadata_json, timestamp
                FROM chat_messages 
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, [session_id, limit]).fetchall()
            
            messages = []
            for row in reversed(rows):  # Reverse to get chronological order
                messages.append({
                    "message_id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                    "timestamp": row[4].isoformat() if hasattr(row[4], 'isoformat') else row[4]
                })
            
            return messages
        finally:
            conn.close()
    
    async def list_sessions(self, active_only: bool = True) -> List[ChatSession]:
        """List all chat sessions for this case."""
        import json
        conn = open_vault(self.case_id)
        try:
            if active_only:
                rows = conn.execute("""
                    SELECT session_id, case_id, investigation_id, phase, 
                           context_json, hypotheses_json, created_at, updated_at
                    FROM chat_sessions 
                    WHERE case_id = ? AND phase != 'completed'
                    ORDER BY updated_at DESC
                """, [self.case_id]).fetchall()
            else:
                rows = conn.execute("""
                    SELECT session_id, case_id, investigation_id, phase, 
                           context_json, hypotheses_json, created_at, updated_at
                    FROM chat_sessions 
                    WHERE case_id = ?
                    ORDER BY updated_at DESC
                """, [self.case_id]).fetchall()
            
            sessions = []
            for row in rows:
                context_dict = json.loads(row[4]) if row[4] else {}
                context = InvestigationContext(
                    scenario=context_dict.get("scenario"),
                    timeline_start=context_dict.get("timeline_start"),
                    timeline_end=context_dict.get("timeline_end"),
                    scope=context_dict.get("scope"),
                    actors_of_interest=context_dict.get("actors_of_interest", []),
                    systems_of_interest=context_dict.get("systems_of_interest", []),
                    data_sources=context_dict.get("data_sources", []),
                    incident_type=context_dict.get("incident_type"),
                    severity_estimate=context_dict.get("severity_estimate"),
                    additional_context=context_dict.get("additional_context", {})
                )
                
                sessions.append(ChatSession(
                    session_id=row[0],
                    case_id=row[1],
                    investigation_id=row[2],
                    phase=ChatPhase(row[3]),
                    context=context,
                    messages=[],  # Don't load messages in list view
                    hypotheses=json.loads(row[5]) if row[5] else [],
                    created_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
                    updated_at=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7]
                ))
            
            return sessions
        finally:
            conn.close()


def get_chat_service(case_id: str) -> ChatService:
    """Factory function to get a ChatService instance."""
    return ChatService(case_id)
