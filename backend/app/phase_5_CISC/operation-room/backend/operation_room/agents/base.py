"""
Base Agent Framework — Abstract classes and common utilities for all agents.

This module provides:
- BaseAgent: Abstract class with standard lifecycle methods
- AgentState: TypedDict for standardized state management
- AgentRegistry: Central registry for agent discovery
- AgentMessage: Inter-agent communication protocol
- AgentMetrics: Performance tracking and observability

Design Principles:
1. Non-destructive: Agents read from shared evidence, write to their own namespaces
2. Audit-first: Every action logged via Chain of Custody
3. Re-entrant: Agents can be run multiple times safely
4. Explainable: All decisions include reasoning traces
"""

import json
import uuid
import logging
import hashlib
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TypedDict, Optional, Any, Dict, List, Literal, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentStatus(str, Enum):
    """Agent execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    WAITING = "waiting"


class AgentPriority(int, Enum):
    """Agent execution priority (lower = higher priority)."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class MessageType(str, Enum):
    """Inter-agent message types."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


# ═══════════════════════════════════════════════════════════════════════════════
# STATE SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseAgentState(TypedDict, total=False):
    """Base state schema shared by all agents."""
    # Identifiers
    agent_id: str
    run_id: str
    case_id: str
    parent_run_id: Optional[str]
    
    # Execution metadata
    status: str
    started_at: str
    completed_at: Optional[str]
    duration_ms: Optional[int]
    
    # Input/Output
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    
    # Audit trail
    hash_value: str
    coc_event_id: str
    
    # Error handling
    error: Optional[str]
    error_trace: Optional[str]
    retry_count: int
    
    # Reasoning trace (for explainability)
    reasoning_steps: List[Dict[str, Any]]


@dataclass
class AgentMessage:
    """
    Inter-agent communication message.
    
    Attributes:
        message_id: Unique identifier for this message
        message_type: Type of message (request, response, event, error)
        sender_id: Agent ID of the sender
        recipient_id: Agent ID of the recipient (or "broadcast")
        payload: Message content
        correlation_id: Links related messages together
        timestamp: When the message was created
        ttl: Time-to-live in seconds (0 = no expiry)
    """
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.REQUEST
    sender_id: str = ""
    recipient_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            message_type=MessageType(data.get("message_type", "request")),
            sender_id=data.get("sender_id", ""),
            recipient_id=data.get("recipient_id", ""),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id"),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            ttl=data.get("ttl", 0),
        )


@dataclass
class AgentMetrics:
    """Performance metrics for agent execution."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_duration_ms: int = 0
    avg_duration_ms: float = 0.0
    last_run_at: Optional[str] = None
    error_rate: float = 0.0
    
    def record_run(self, duration_ms: int, success: bool):
        """Record a single run's metrics."""
        self.total_runs += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_runs
        self.last_run_at = datetime.now(timezone.utc).isoformat()
        
        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1
        
        self.error_rate = self.failed_runs / self.total_runs if self.total_runs > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# BASE AGENT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the multi-agent system.
    
    Lifecycle:
        1. validate_inputs() - Check prerequisites are met
        2. prepare() - Initialize state, load dependencies
        3. execute() - Main processing logic
        4. finalize() - Store results, update CoC
        5. cleanup() - Release resources
    
    Subclasses must implement:
        - agent_id: Unique identifier
        - agent_name: Human-readable name
        - execute(): Core processing logic
    """
    
    def __init__(self, llm_provider: str = "ollama"):
        self.llm_provider = llm_provider
        self._metrics = AgentMetrics()
        self._message_handlers: Dict[str, Callable] = {}
        self._logger = logging.getLogger(f"agent.{self.agent_id}")
    
    # ─── Abstract Properties ─────────────────────────────────────────────────
    
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier for this agent type."""
        ...
    
    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name for this agent."""
        ...
    
    @property
    def agent_version(self) -> str:
        """Semantic version of this agent."""
        return "1.0.0"
    
    @property
    def agent_description(self) -> str:
        """Brief description of agent capabilities."""
        return "Base agent - no specific capabilities"
    
    @property
    def dependencies(self) -> List[str]:
        """List of agent IDs this agent depends on."""
        return []
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema for expected input data."""
        return {"type": "object"}
    
    @property
    def output_schema(self) -> Dict[str, Any]:
        """JSON Schema for output data."""
        return {"type": "object"}
    
    # ─── Lifecycle Methods ───────────────────────────────────────────────────
    
    async def run(self, state: BaseAgentState) -> BaseAgentState:
        """
        Execute the full agent lifecycle.
        
        Args:
            state: Initial state with input data
            
        Returns:
            Updated state with output data and status
        """
        run_id = state.get("run_id", str(uuid.uuid4()))
        start_time = datetime.now(timezone.utc)
        
        state["agent_id"] = self.agent_id
        state["run_id"] = run_id
        state["status"] = AgentStatus.RUNNING.value
        state["started_at"] = start_time.isoformat()
        state["reasoning_steps"] = []
        
        self._logger.info(f"[{run_id}] Starting {self.agent_name}")
        
        try:
            # Phase 1: Validate
            validation = await self.validate_inputs(state)
            if not validation["valid"]:
                state["status"] = AgentStatus.BLOCKED.value
                state["error"] = f"Validation failed: {validation.get('missing', [])}"
                return state
            
            self._add_reasoning_step(state, "validation", "Input validation passed", validation)
            
            # Phase 2: Prepare
            state = await self.prepare(state)
            self._add_reasoning_step(state, "preparation", "Agent preparation completed")
            
            # Phase 3: Execute
            state = await self.execute(state)
            
            # Phase 4: Finalize
            state = await self.finalize(state)
            
            # Success
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            state["status"] = AgentStatus.COMPLETED.value
            state["completed_at"] = end_time.isoformat()
            state["duration_ms"] = duration_ms
            
            # Compute integrity hash
            state["hash_value"] = self._compute_hash(state)
            
            self._metrics.record_run(duration_ms, success=True)
            self._logger.info(f"[{run_id}] Completed in {duration_ms}ms")
            
        except Exception as e:
            import traceback
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            state["status"] = AgentStatus.FAILED.value
            state["completed_at"] = end_time.isoformat()
            state["duration_ms"] = duration_ms
            state["error"] = str(e)
            state["error_trace"] = traceback.format_exc()
            
            self._metrics.record_run(duration_ms, success=False)
            self._logger.error(f"[{run_id}] Failed: {e}")
            
        finally:
            await self.cleanup(state)
        
        return state
    
    async def validate_inputs(self, state: BaseAgentState) -> Dict[str, Any]:
        """
        Validate that all required inputs are present.
        
        Override in subclasses for custom validation.
        
        Returns:
            {"valid": bool, "missing": list[str], "warnings": list[str]}
        """
        return {"valid": True, "missing": [], "warnings": []}
    
    async def prepare(self, state: BaseAgentState) -> BaseAgentState:
        """
        Prepare the agent for execution.
        
        Override in subclasses for initialization logic.
        """
        return state
    
    @abstractmethod
    async def execute(self, state: BaseAgentState) -> BaseAgentState:
        """
        Main execution logic.
        
        Must be implemented by all subclasses.
        """
        ...
    
    async def finalize(self, state: BaseAgentState) -> BaseAgentState:
        """
        Finalize execution, store results.
        
        Override in subclasses for cleanup logic.
        """
        return state
    
    async def cleanup(self, state: BaseAgentState) -> None:
        """
        Release any resources held by the agent.
        
        Always called, even on failure.
        """
        pass
    
    # ─── Messaging ───────────────────────────────────────────────────────────
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a handler for a specific message type."""
        self._message_handlers[message_type] = handler
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Process an incoming message.
        
        Returns a response message or None.
        """
        handler = self._message_handlers.get(message.message_type.value)
        if handler:
            return await handler(message)
        return None
    
    def send_message(
        self,
        recipient_id: str,
        payload: Dict[str, Any],
        message_type: MessageType = MessageType.REQUEST,
        correlation_id: Optional[str] = None,
    ) -> AgentMessage:
        """Create an outgoing message."""
        return AgentMessage(
            message_type=message_type,
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            payload=payload,
            correlation_id=correlation_id,
        )
    
    # ─── Utilities ───────────────────────────────────────────────────────────
    
    def _add_reasoning_step(
        self,
        state: BaseAgentState,
        step_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Add a reasoning step to the trace."""
        step = {
            "step_type": step_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        if "reasoning_steps" not in state:
            state["reasoning_steps"] = []
        state["reasoning_steps"].append(step)
    
    def _compute_hash(self, state: BaseAgentState) -> str:
        """Compute SHA-256 hash of output data for integrity verification."""
        output_str = json.dumps(state.get("output_data", {}), sort_keys=True)
        return f"sha256:{hashlib.sha256(output_str.encode()).hexdigest()}"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics."""
        return {
            "agent_id": self.agent_id,
            "total_runs": self._metrics.total_runs,
            "successful_runs": self._metrics.successful_runs,
            "failed_runs": self._metrics.failed_runs,
            "avg_duration_ms": self._metrics.avg_duration_ms,
            "error_rate": self._metrics.error_rate,
            "last_run_at": self._metrics.last_run_at,
        }
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent metadata."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_version": self.agent_version,
            "description": self.agent_description,
            "dependencies": self.dependencies,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class AgentRegistry:
    """
    Central registry for agent discovery and management.
    
    Provides:
    - Agent registration and lookup
    - Dependency graph resolution
    - Health monitoring
    """
    
    _instance = None
    _agents: Dict[str, BaseAgent] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
        return cls._instance
    
    def register(self, agent: BaseAgent) -> None:
        """Register an agent instance."""
        self._agents[agent.agent_id] = agent
        logger.info(f"Registered agent: {agent.agent_id} ({agent.agent_name})")
    
    def unregister(self, agent_id: str) -> None:
        """Unregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")
    
    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        return [agent.get_info() for agent in self._agents.values()]
    
    def resolve_dependencies(self, agent_id: str) -> List[str]:
        """
        Resolve the execution order for an agent and its dependencies.
        
        Returns a topologically sorted list of agent IDs.
        """
        visited = set()
        order = []
        
        def visit(aid: str):
            if aid in visited:
                return
            visited.add(aid)
            
            agent = self._agents.get(aid)
            if agent:
                for dep in agent.dependencies:
                    visit(dep)
                order.append(aid)
        
        visit(agent_id)
        return order
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all agents."""
        return {
            agent_id: agent.get_metrics()
            for agent_id, agent in self._agents.items()
        }


# Singleton instance
registry = AgentRegistry()
