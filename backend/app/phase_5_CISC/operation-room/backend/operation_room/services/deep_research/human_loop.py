"""
Human-in-Loop Question Models and Manager.

Implements:
- HumanQuestion: Question data model with priority levels
- HumanLoopManager: Question queue management
- WebSocket notification support
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
import asyncio
import uuid
import logging
import json


logger = logging.getLogger(__name__)


class QuestionPriority(str, Enum):
    """Priority levels for human questions."""
    BLOCKING = "blocking"  # Must answer to proceed
    HIGH = "high"          # Should answer soon
    MEDIUM = "medium"      # Can wait
    LOW = "low"            # Optional, can skip


class QuestionStatus(str, Enum):
    """Status of a question."""
    PENDING = "pending"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    EXPIRED = "expired"


class QuestionType(str, Enum):
    """Types of questions."""
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"
    SELECTION = "selection"
    INPUT = "input"
    APPROVAL = "approval"


@dataclass
class HumanQuestion:
    """A question for human input."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Content
    question: str = ""
    context: str = ""
    options: Optional[List[str]] = None  # For selection type
    default_answer: Optional[str] = None
    
    # Classification
    question_type: QuestionType = QuestionType.CLARIFICATION
    priority: QuestionPriority = QuestionPriority.MEDIUM
    
    # Status
    status: QuestionStatus = QuestionStatus.PENDING
    answer: Optional[str] = None
    
    # Association
    investigation_id: str = ""
    thought_id: Optional[str] = None  # Associated thought node
    phase_id: Optional[str] = None    # Associated plan phase
    step_id: Optional[str] = None     # Associated plan step
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_pending(self) -> bool:
        """Check if question is still pending."""
        return self.status == QuestionStatus.PENDING
    
    @property
    def is_blocking(self) -> bool:
        """Check if question is blocking."""
        return self.priority == QuestionPriority.BLOCKING
    
    @property
    def is_expired(self) -> bool:
        """Check if question has expired."""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
    
    def set_answer(self, answer: str) -> None:
        """Set the answer."""
        self.answer = answer
        self.status = QuestionStatus.ANSWERED
        self.answered_at = datetime.now()
    
    def skip(self) -> None:
        """Skip the question."""
        self.status = QuestionStatus.SKIPPED
        self.answered_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "question": self.question,
            "context": self.context,
            "options": self.options,
            "default_answer": self.default_answer,
            "question_type": self.question_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "answer": self.answer,
            "investigation_id": self.investigation_id,
            "thought_id": self.thought_id,
            "phase_id": self.phase_id,
            "step_id": self.step_id,
            "created_at": self.created_at.isoformat(),
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanQuestion":
        """Create from dictionary."""
        question = cls(
            id=data.get("id", str(uuid.uuid4())),
            question=data.get("question", ""),
            context=data.get("context", ""),
            options=data.get("options"),
            default_answer=data.get("default_answer"),
            question_type=QuestionType(data.get("question_type", "clarification")),
            priority=QuestionPriority(data.get("priority", "medium")),
            status=QuestionStatus(data.get("status", "pending")),
            answer=data.get("answer"),
            investigation_id=data.get("investigation_id", ""),
            thought_id=data.get("thought_id"),
            phase_id=data.get("phase_id"),
            step_id=data.get("step_id"),
            metadata=data.get("metadata", {}),
        )
        if data.get("created_at"):
            question.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("answered_at"):
            question.answered_at = datetime.fromisoformat(data["answered_at"])
        if data.get("expires_at"):
            question.expires_at = datetime.fromisoformat(data["expires_at"])
        return question


class HumanLoopManager:
    """
    Manages human-in-loop questions.
    
    Features:
    - Question queue by investigation
    - Priority ordering
    - Async waiting for answers
    - WebSocket notifications
    """
    
    def __init__(self):
        """Initialize the manager."""
        self._questions: Dict[str, HumanQuestion] = {}
        self._by_investigation: Dict[str, List[str]] = {}
        self._answer_events: Dict[str, asyncio.Event] = {}
        self._notification_callbacks: List[Callable] = []
    
    def create_question(
        self,
        question: str,
        investigation_id: str,
        priority: QuestionPriority = QuestionPriority.MEDIUM,
        question_type: QuestionType = QuestionType.CLARIFICATION,
        context: str = "",
        options: Optional[List[str]] = None,
        thought_id: Optional[str] = None,
        phase_id: Optional[str] = None,
        step_id: Optional[str] = None,
        **kwargs,
    ) -> HumanQuestion:
        """
        Create a new question.
        
        Args:
            question: Question text
            investigation_id: Associated investigation
            priority: Question priority
            question_type: Type of question
            context: Additional context
            options: Options for selection questions
            thought_id: Associated thought
            phase_id: Associated phase
            step_id: Associated step
            
        Returns:
            Created question
        """
        q = HumanQuestion(
            question=question,
            investigation_id=investigation_id,
            priority=priority,
            question_type=question_type,
            context=context,
            options=options,
            thought_id=thought_id,
            phase_id=phase_id,
            step_id=step_id,
            **kwargs,
        )
        
        self._questions[q.id] = q
        
        # Index by investigation
        if investigation_id not in self._by_investigation:
            self._by_investigation[investigation_id] = []
        self._by_investigation[investigation_id].append(q.id)
        
        # Create answer event
        self._answer_events[q.id] = asyncio.Event()
        
        # Notify callbacks
        self._notify("question_created", q)
        
        logger.info(f"Created question {q.id} for investigation {investigation_id}")
        
        return q
    
    def get_question(self, question_id: str) -> Optional[HumanQuestion]:
        """Get a question by ID."""
        return self._questions.get(question_id)
    
    def get_pending_questions(
        self,
        investigation_id: str,
        priority: Optional[QuestionPriority] = None,
    ) -> List[HumanQuestion]:
        """
        Get pending questions for an investigation.
        
        Args:
            investigation_id: Investigation ID
            priority: Optional filter by priority
            
        Returns:
            List of pending questions, sorted by priority
        """
        question_ids = self._by_investigation.get(investigation_id, [])
        questions = []
        
        for qid in question_ids:
            q = self._questions.get(qid)
            if q and q.is_pending:
                if priority is None or q.priority == priority:
                    questions.append(q)
        
        # Sort by priority (blocking first)
        priority_order = {
            QuestionPriority.BLOCKING: 0,
            QuestionPriority.HIGH: 1,
            QuestionPriority.MEDIUM: 2,
            QuestionPriority.LOW: 3,
        }
        
        return sorted(questions, key=lambda q: priority_order.get(q.priority, 3))
    
    def has_blocking_questions(self, investigation_id: str) -> bool:
        """Check if investigation has blocking questions."""
        questions = self.get_pending_questions(investigation_id)
        return any(q.is_blocking for q in questions)
    
    def answer_question(
        self,
        question_id: str,
        answer: str,
    ) -> HumanQuestion:
        """
        Answer a question.
        
        Args:
            question_id: Question ID
            answer: Answer text
            
        Returns:
            Answered question
        """
        q = self._questions.get(question_id)
        if not q:
            raise ValueError(f"Question not found: {question_id}")
        
        if not q.is_pending:
            raise ValueError(f"Question already answered: {question_id}")
        
        q.set_answer(answer)
        
        # Signal waiting tasks
        if question_id in self._answer_events:
            self._answer_events[question_id].set()
        
        # Notify
        self._notify("question_answered", q)
        
        logger.info(f"Answered question {question_id}")
        
        return q
    
    def skip_question(self, question_id: str) -> HumanQuestion:
        """
        Skip a question (if not blocking).
        
        Args:
            question_id: Question ID
            
        Returns:
            Skipped question
        """
        q = self._questions.get(question_id)
        if not q:
            raise ValueError(f"Question not found: {question_id}")
        
        if q.is_blocking:
            raise ValueError("Cannot skip blocking question")
        
        q.skip()
        
        # Signal waiting tasks
        if question_id in self._answer_events:
            self._answer_events[question_id].set()
        
        self._notify("question_skipped", q)
        
        return q
    
    async def wait_for_answer(
        self,
        question_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """
        Wait for a question to be answered.
        
        Args:
            question_id: Question ID
            timeout: Optional timeout in seconds
            
        Returns:
            Answer or None if timed out/skipped
        """
        q = self._questions.get(question_id)
        if not q:
            raise ValueError(f"Question not found: {question_id}")
        
        if not q.is_pending:
            return q.answer
        
        event = self._answer_events.get(question_id)
        if not event:
            return None
        
        try:
            if timeout:
                await asyncio.wait_for(event.wait(), timeout)
            else:
                await event.wait()
            
            # Return answer (may be None if skipped)
            return self._questions[question_id].answer
            
        except asyncio.TimeoutError:
            logger.warning(f"Question {question_id} timed out")
            return None
    
    async def ask_and_wait(
        self,
        question: str,
        investigation_id: str,
        **kwargs,
    ) -> Optional[str]:
        """
        Create a question and wait for answer.
        
        Args:
            question: Question text
            investigation_id: Investigation ID
            **kwargs: Additional question parameters
            
        Returns:
            Answer or None
        """
        q = self.create_question(
            question=question,
            investigation_id=investigation_id,
            **kwargs,
        )
        
        return await self.wait_for_answer(q.id)
    
    def on_notification(self, callback: Callable) -> None:
        """Register notification callback."""
        self._notification_callbacks.append(callback)
    
    def _notify(self, event_type: str, question: HumanQuestion) -> None:
        """Notify all callbacks."""
        for callback in self._notification_callbacks:
            try:
                callback(event_type, question)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")
    
    async def stream_questions(
        self,
        investigation_id: str,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream question events for an investigation.
        
        Yields:
            Event dictionaries
        """
        queue: asyncio.Queue = asyncio.Queue()
        
        def callback(event_type: str, question: HumanQuestion):
            if question.investigation_id == investigation_id:
                queue.put_nowait({
                    "event_type": event_type,
                    "question": question.to_dict(),
                })
        
        self.on_notification(callback)
        
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._notification_callbacks.remove(callback)


# Global instance
_hil_manager: Optional[HumanLoopManager] = None


def get_hil_manager() -> HumanLoopManager:
    """Get the global human-in-loop manager."""
    global _hil_manager
    if _hil_manager is None:
        _hil_manager = HumanLoopManager()
    return _hil_manager
