"""
Chain-of-Thought Engine.

Generates and manages chain-of-thought reasoning with:
- Streaming output (both text and tree updates)
- Integration with LLM service
- Evidence-grounded reasoning
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)
import logging
import json

from .models import ThoughtNode, ThoughtTree, ThoughtType, ThoughtStatus


logger = logging.getLogger(__name__)


@dataclass
class ThoughtStreamEvent:
    """An event in the thought stream."""
    event_type: str  # "thought_start", "thought_content", "thought_complete", "tree_update"
    thought_id: str
    content: str = ""
    data: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.data is None:
            self.data = {}
    
    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        data = {
            "event_type": self.event_type,
            "thought_id": self.thought_id,
            "content": self.content,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }
        return f"data: {json.dumps(data)}\n\n"


class ThoughtEngine:
    """
    Engine for generating chain-of-thought reasoning.
    
    Features:
    - Streaming thought generation
    - Tree structure management
    - LLM integration
    - Evidence tracking
    """
    
    def __init__(
        self,
        llm_service: Optional[Any] = None,
    ):
        """
        Initialize the thought engine.
        
        Args:
            llm_service: LLM service for generation (uses global if None)
        """
        self._llm_service = llm_service
        self._trees: Dict[str, ThoughtTree] = {}
        self._event_callbacks: List[Callable[[ThoughtStreamEvent], None]] = []
    
    @property
    def llm_service(self):
        """Get LLM service (lazy load)."""
        if self._llm_service is None:
            from operation_room.services.llm import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service
    
    def create_tree(self, investigation_id: str) -> ThoughtTree:
        """Create a new thought tree for an investigation."""
        tree = ThoughtTree(investigation_id=investigation_id)
        self._trees[tree.id] = tree
        return tree
    
    def get_tree(self, tree_id: str) -> Optional[ThoughtTree]:
        """Get a thought tree by ID."""
        return self._trees.get(tree_id)
    
    def add_event_callback(self, callback: Callable[[ThoughtStreamEvent], None]) -> None:
        """Add a callback for thought events."""
        self._event_callbacks.append(callback)
    
    def _emit_event(self, event: ThoughtStreamEvent) -> None:
        """Emit an event to all callbacks."""
        for callback in self._event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    async def create_thought(
        self,
        tree: ThoughtTree,
        title: str,
        thought_type: ThoughtType,
        parent_id: Optional[str] = None,
        initial_content: str = "",
    ) -> ThoughtNode:
        """
        Create a new thought node.
        
        Args:
            tree: The thought tree
            title: Thought title
            thought_type: Type of thought
            parent_id: Optional parent thought ID
            initial_content: Initial content
            
        Returns:
            Created thought node
        """
        node = tree.create_node(
            title=title,
            content=initial_content,
            thought_type=thought_type,
            parent_id=parent_id,
        )
        
        # Emit event
        self._emit_event(ThoughtStreamEvent(
            event_type="thought_start",
            thought_id=node.id,
            data={
                "title": title,
                "thought_type": thought_type.value,
                "parent_id": parent_id,
            },
        ))
        
        return node
    
    async def stream_thought_content(
        self,
        tree: ThoughtTree,
        node: ThoughtNode,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream thought content generation.
        
        Args:
            tree: The thought tree
            node: The thought node to populate
            prompt: The generation prompt
            system_prompt: Optional system prompt
            context: Additional context
            
        Yields:
            Content chunks
        """
        from operation_room.services.llm import Message, GenerationConfig
        
        node.start()
        
        # Build messages
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        
        # Add context to prompt if provided
        if context:
            context_str = json.dumps(context, indent=2)
            prompt = f"Context:\n{context_str}\n\n{prompt}"
        
        messages.append(Message(role="user", content=prompt))
        
        # Stream generation
        full_content = ""
        try:
            async for chunk in self.llm_service.generate_stream(messages):
                if chunk.content:
                    full_content += chunk.content
                    node.content = full_content
                    
                    # Emit content event
                    self._emit_event(ThoughtStreamEvent(
                        event_type="thought_content",
                        thought_id=node.id,
                        content=chunk.content,
                    ))
                    
                    yield chunk.content
            
            # Complete the thought
            node.complete()
            self._emit_event(ThoughtStreamEvent(
                event_type="thought_complete",
                thought_id=node.id,
                data={"status": "completed"},
            ))
            
        except Exception as e:
            node.fail(str(e))
            self._emit_event(ThoughtStreamEvent(
                event_type="thought_complete",
                thought_id=node.id,
                data={"status": "failed", "error": str(e)},
            ))
            raise
    
    async def generate_thought(
        self,
        tree: ThoughtTree,
        node: ThoughtNode,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate thought content (non-streaming).
        
        Args:
            tree: The thought tree
            node: The thought node to populate
            prompt: The generation prompt
            system_prompt: Optional system prompt
            context: Additional context
            
        Returns:
            Generated content
        """
        content = ""
        async for chunk in self.stream_thought_content(
            tree, node, prompt, system_prompt, context
        ):
            content += chunk
        return content
    
    async def reason_about_evidence(
        self,
        tree: ThoughtTree,
        evidence: List[Dict[str, Any]],
        question: str,
        parent_id: Optional[str] = None,
    ) -> ThoughtNode:
        """
        Create a thought that reasons about evidence.
        
        Args:
            tree: The thought tree
            evidence: List of evidence items
            question: Question to answer
            parent_id: Optional parent thought
            
        Returns:
            Completed thought node
        """
        # Create thought node
        node = await self.create_thought(
            tree=tree,
            title=f"Analyzing: {question[:50]}...",
            thought_type=ThoughtType.ANALYSIS,
            parent_id=parent_id,
        )
        
        # Add evidence references
        for ev in evidence:
            if "id" in ev:
                node.add_evidence(ev["id"])
        
        # Build prompt
        system_prompt = """You are a forensic investigator analyzing digital evidence.
        
IMPORTANT RULES:
1. ONLY use facts from the provided evidence
2. Do NOT make up any IP addresses, timestamps, or user IDs
3. Cite evidence by reference when making claims
4. State your confidence level (low/medium/high/very high)
5. Identify gaps in evidence"""
        
        prompt = f"""Analyze the following evidence to answer: {question}

Evidence:
{json.dumps(evidence, indent=2)}

Provide your analysis with:
1. Key observations from the evidence
2. What this evidence proves or suggests
3. Any gaps or missing information
4. Confidence level in your conclusions"""
        
        # Generate analysis
        await self.generate_thought(tree, node, prompt, system_prompt)
        
        return node
    
    async def synthesize_findings(
        self,
        tree: ThoughtTree,
        findings: List[ThoughtNode],
        question: str,
        parent_id: Optional[str] = None,
    ) -> ThoughtNode:
        """
        Create a synthesis thought from multiple findings.
        
        Args:
            tree: The thought tree
            findings: List of finding nodes
            question: Overall question
            parent_id: Optional parent
            
        Returns:
            Synthesis thought node
        """
        # Create synthesis node
        node = await self.create_thought(
            tree=tree,
            title="Synthesizing findings",
            thought_type=ThoughtType.SYNTHESIS,
            parent_id=parent_id,
        )
        
        # Build findings summary
        findings_text = []
        for i, f in enumerate(findings, 1):
            findings_text.append(f"{i}. {f.title}\n   {f.content[:500]}...")
            for ref in f.evidence_refs:
                node.add_evidence(ref)
        
        system_prompt = """You are synthesizing multiple forensic findings into a coherent conclusion.

IMPORTANT RULES:
1. Only conclude based on the provided findings
2. Identify points of agreement and conflict
3. Note the strength of evidence for each conclusion
4. Be explicit about uncertainty"""
        
        prompt = f"""Synthesize these findings to answer: {question}

Findings:
{chr(10).join(findings_text)}

Provide:
1. Main conclusions supported by multiple findings
2. Points of conflict or uncertainty
3. Overall confidence assessment
4. Recommendations for further investigation"""
        
        await self.generate_thought(tree, node, prompt, system_prompt)
        
        return node
    
    async def evaluate_hypothesis(
        self,
        tree: ThoughtTree,
        hypothesis: str,
        evidence_for: List[Dict[str, Any]],
        evidence_against: List[Dict[str, Any]],
        parent_id: Optional[str] = None,
    ) -> ThoughtNode:
        """
        Evaluate a hypothesis against evidence.
        
        Args:
            tree: The thought tree
            hypothesis: The hypothesis statement
            evidence_for: Supporting evidence
            evidence_against: Contradicting evidence
            parent_id: Optional parent
            
        Returns:
            Evaluation thought node
        """
        node = await self.create_thought(
            tree=tree,
            title=f"Evaluating: {hypothesis[:40]}...",
            thought_type=ThoughtType.HYPOTHESIS,
            parent_id=parent_id,
        )
        
        # Add evidence refs
        for ev in evidence_for + evidence_against:
            if "id" in ev:
                node.add_evidence(ev["id"])
        
        system_prompt = """You are evaluating a forensic hypothesis using Analysis of Competing Hypotheses (ACH) methodology.

EVALUATION CRITERIA:
- SUPPORTED: Strong evidence confirms hypothesis
- LIKELY: Preponderance of evidence supports hypothesis
- INCONCLUSIVE: Insufficient evidence to decide
- UNLIKELY: Preponderance of evidence contradicts hypothesis
- REJECTED: Strong evidence refutes hypothesis

Use ODNI ICD 203 confidence levels:
- Very High (>90%): Multiple independent corroborating sources
- High (75-90%): Strong evidence with few gaps
- Moderate (50-75%): Mixed evidence
- Low (25-50%): Limited evidence
- Very Low (<25%): Speculative"""
        
        prompt = f"""Evaluate this hypothesis: {hypothesis}

Evidence SUPPORTING the hypothesis:
{json.dumps(evidence_for, indent=2)}

Evidence AGAINST the hypothesis:
{json.dumps(evidence_against, indent=2)}

Provide:
1. Verdict (Supported/Likely/Inconclusive/Unlikely/Rejected)
2. Confidence level and percentage
3. Key supporting points
4. Key contradicting points
5. Gaps in evidence
6. What additional evidence would change the verdict"""
        
        await self.generate_thought(tree, node, prompt, system_prompt)
        
        # Parse confidence from response
        content = node.content.lower()
        if "very high" in content or ">90%" in content:
            node.confidence = 0.95
        elif "high" in content or "75" in content:
            node.confidence = 0.82
        elif "moderate" in content or "50" in content:
            node.confidence = 0.62
        elif "low" in content or "25" in content:
            node.confidence = 0.37
        else:
            node.confidence = 0.15
        
        return node
    
    async def ask_clarification(
        self,
        tree: ThoughtTree,
        question: str,
        options: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
    ) -> ThoughtNode:
        """
        Create a clarification question thought.
        
        Args:
            tree: The thought tree
            question: The question to ask
            options: Optional answer options
            parent_id: Optional parent
            
        Returns:
            Question thought node
        """
        node = await self.create_thought(
            tree=tree,
            title="Clarification needed",
            thought_type=ThoughtType.QUESTION,
            parent_id=parent_id,
            initial_content=question,
        )
        
        node.data["question"] = question
        if options:
            node.data["options"] = options
        
        node.block("Waiting for user response")
        
        self._emit_event(ThoughtStreamEvent(
            event_type="thought_complete",
            thought_id=node.id,
            data={
                "status": "blocked",
                "question": question,
                "options": options,
            },
        ))
        
        return node
    
    def answer_question(
        self,
        tree: ThoughtTree,
        node_id: str,
        answer: str,
    ) -> None:
        """
        Provide answer to a clarification question.
        
        Args:
            tree: The thought tree
            node_id: The question node ID
            answer: The answer
        """
        node = tree.get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        
        node.data["answer"] = answer
        node.complete(result=answer)
        
        self._emit_event(ThoughtStreamEvent(
            event_type="thought_complete",
            thought_id=node.id,
            data={"status": "completed", "answer": answer},
        ))
    
    async def stream_tree_events(
        self,
        tree: ThoughtTree,
    ) -> AsyncIterator[ThoughtStreamEvent]:
        """
        Stream all tree events (for SSE endpoint).
        
        Args:
            tree: The thought tree
            
        Yields:
            ThoughtStreamEvents
        """
        queue: asyncio.Queue[Optional[ThoughtStreamEvent]] = asyncio.Queue()
        
        def callback(event: ThoughtStreamEvent):
            queue.put_nowait(event)
        
        self.add_event_callback(callback)
        
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self._event_callbacks.remove(callback)
    
    def get_tree_summary(self, tree: ThoughtTree) -> Dict[str, Any]:
        """Get summary of thought tree state."""
        return {
            "tree_id": tree.id,
            "investigation_id": tree.investigation_id,
            "summary": tree.get_summary(),
            "stream_format": tree.to_stream_format(),
        }
