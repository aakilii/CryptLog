"""
MCP Tool Registry — Tool registration, discovery, and invocation.

This module provides:
- Tool registration with metadata
- Tool discovery and introspection
- Parameter validation
- Execution tracking
- Chain of Custody logging

The registry is the central hub for all MCP tools. Tools register themselves
here and the MCP server uses this registry to discover and invoke tools.

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    Any, Awaitable, Callable, Dict, Generic, List, Optional, 
    Set, Tuple, Type, TypeVar, Union, get_args, get_origin, get_type_hints
)

from pydantic import BaseModel, Field, ValidationError, create_model

from .schemas import MCPToolResult, MCPBaseModel


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

T = TypeVar("T")
ToolFunc = Callable[..., Awaitable[Any]]


class ToolCategory(str, Enum):
    """Categories of MCP tools."""
    INVESTIGATION = "investigation"
    ANALYSIS = "analysis"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    REPORT = "report"
    UTILITY = "utility"


class ToolAccessLevel(str, Enum):
    """Access levels for tools."""
    PUBLIC = "public"        # Anyone can invoke
    AUTHENTICATED = "authenticated"  # Needs auth
    ADMIN = "admin"          # Admin only


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL METADATA
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolParameter:
    """Metadata for a tool parameter."""
    name: str
    type_annotation: Any
    description: str = ""
    required: bool = True
    default: Any = None
    validation_pattern: Optional[str] = None
    examples: List[Any] = field(default_factory=list)

    @staticmethod
    def _annotation_to_schema(annotation: Any) -> Dict[str, Any]:
        """Convert Python/typing annotation to a JSON Schema fragment."""
        if annotation in (inspect.Parameter.empty, Any, None):
            return {"type": "object"}

        origin = get_origin(annotation)
        args = get_args(annotation)

        if annotation == str:
            return {"type": "string"}
        if annotation == int:
            return {"type": "integer"}
        if annotation == float:
            return {"type": "number"}
        if annotation == bool:
            return {"type": "boolean"}

        if origin is Union:
            non_none_args = [a for a in args if a is not type(None)]
            if len(non_none_args) == 1:
                schema = ToolParameter._annotation_to_schema(non_none_args[0])
                schema["nullable"] = True
                return schema
            if non_none_args:
                return {
                    "oneOf": [ToolParameter._annotation_to_schema(a) for a in non_none_args],
                    "nullable": len(non_none_args) != len(args),
                }
            return {"type": "object", "nullable": True}

        if annotation == list or origin in (list, List, tuple, Tuple, set, Set):
            item_annotation = args[0] if args else Any
            return {
                "type": "array",
                "items": ToolParameter._annotation_to_schema(item_annotation),
            }

        if annotation == dict or origin in (dict, Dict):
            value_annotation = args[1] if len(args) > 1 else Any
            return {
                "type": "object",
                "additionalProperties": ToolParameter._annotation_to_schema(value_annotation),
            }

        return {"type": "object"}
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema for MCP protocol."""
        schema: Dict[str, Any] = self._annotation_to_schema(self.type_annotation)
        schema["description"] = self.description
        
        if not self.required:
            schema["default"] = self.default
            
        if self.validation_pattern:
            schema["pattern"] = self.validation_pattern
            
        if self.examples:
            schema["examples"] = self.examples
            
        return schema


@dataclass
class ToolMetadata:
    """Complete metadata for a registered tool."""
    name: str
    description: str
    category: ToolCategory
    access_level: ToolAccessLevel = ToolAccessLevel.AUTHENTICATED
    version: str = "1.0.0"
    
    # Parameters
    parameters: List[ToolParameter] = field(default_factory=list)
    input_schema: Optional[Type[BaseModel]] = None
    output_schema: Optional[Type[BaseModel]] = None
    
    # Execution info
    is_async: bool = True
    timeout_seconds: float = 300.0
    requires_case_id: bool = True
    
    # Chain of custody
    logs_to_coc: bool = True
    coc_action_type: str = "TOOL_EXECUTION"
    
    # Documentation
    long_description: Optional[str] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    related_tools: List[str] = field(default_factory=list)
    
    # Tags for discovery
    tags: Set[str] = field(default_factory=set)
    
    def to_mcp_schema(self) -> Dict[str, Any]:
        """Convert to MCP-compatible tool schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolExecutionContext:
    """Context passed to every tool execution."""
    execution_id: str = field(default_factory=lambda: f"texec-{uuid.uuid4().hex[:12]}")
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    user_id: Optional[str] = None
    
    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: float = 300.0
    
    # Chain of custody
    log_to_coc: bool = True
    coc_event_id: Optional[str] = None
    
    # State
    parent_execution: Optional[str] = None
    depth: int = 0
    
    # Cancellation
    cancelled: bool = False
    cancel_reason: Optional[str] = None
    
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000


@dataclass
class ToolExecutionResult:
    """Result of a tool execution."""
    execution_id: str
    tool_name: str
    success: bool
    
    # Timing
    started_at: datetime
    completed_at: datetime
    duration_ms: float
    
    # Results
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    
    # Evidence
    evidence_hash: Optional[str] = None
    evidence_cards_created: List[str] = field(default_factory=list)
    
    # Chain of custody
    coc_event_id: Optional[str] = None
    
    def to_mcp_result(self) -> MCPToolResult:
        """Convert to MCP tool result."""
        return MCPToolResult(
            success=self.success,
            tool_name=self.tool_name,
            execution_id=self.execution_id,
            timestamp=self.completed_at,
            data=self.result if isinstance(self.result, dict) else None,
            evidence_hash=self.evidence_hash,
            evidence_cards_created=self.evidence_cards_created,
            coc_event_id=self.coc_event_id,
            error=self.error,
            error_code=self.error_code
        )


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTERED TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class RegisteredTool:
    """A registered MCP tool with its handler function."""
    
    def __init__(
        self,
        metadata: ToolMetadata,
        handler: ToolFunc,
        input_validator: Optional[Type[BaseModel]] = None,
        output_validator: Optional[Type[BaseModel]] = None
    ):
        self.metadata = metadata
        self.handler = handler
        self.input_validator = input_validator
        self.output_validator = output_validator
        self._execution_count = 0
        self._error_count = 0
        self._total_duration_ms = 0.0
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def category(self) -> ToolCategory:
        return self.metadata.category
    
    def validate_input(self, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate input parameters."""
        if self.input_validator:
            try:
                self.input_validator(**params)
                return True, None
            except ValidationError as e:
                return False, str(e)
        
        # Basic validation based on parameter metadata
        for param in self.metadata.parameters:
            if param.required and param.name not in params:
                return False, f"Missing required parameter: {param.name}"
        
        return True, None
    
    def validate_output(self, result: Any) -> Tuple[bool, Optional[str]]:
        """Validate output result."""
        if self.output_validator and result is not None:
            try:
                if isinstance(result, dict):
                    self.output_validator(**result)
                return True, None
            except ValidationError as e:
                return False, str(e)
        return True, None
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: ToolExecutionContext
    ) -> ToolExecutionResult:
        """Execute the tool with given parameters."""
        started_at = datetime.now(timezone.utc)
        
        # Validate input
        valid, error_msg = self.validate_input(params)
        if not valid:
            return ToolExecutionResult(
                execution_id=context.execution_id,
                tool_name=self.name,
                success=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=0,
                error=f"Input validation failed: {error_msg}",
                error_code="VALIDATION_ERROR"
            )
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                self.handler(**params, _context=context),
                timeout=context.timeout_seconds
            )
            
            completed_at = datetime.now(timezone.utc)
            duration_ms = (completed_at - started_at).total_seconds() * 1000
            
            # Update stats
            self._execution_count += 1
            self._total_duration_ms += duration_ms
            
            # Extract evidence info if present
            evidence_hash = None
            evidence_cards = []
            
            if isinstance(result, dict):
                evidence_hash = result.get("evidence_hash")
                evidence_cards = result.get("evidence_cards_created", [])
            elif isinstance(result, MCPToolResult):
                evidence_hash = result.evidence_hash
                evidence_cards = result.evidence_cards_created
            
            return ToolExecutionResult(
                execution_id=context.execution_id,
                tool_name=self.name,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                result=result,
                evidence_hash=evidence_hash,
                evidence_cards_created=evidence_cards,
                coc_event_id=context.coc_event_id
            )
            
        except asyncio.TimeoutError:
            self._error_count += 1
            return ToolExecutionResult(
                execution_id=context.execution_id,
                tool_name=self.name,
                success=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=context.timeout_seconds * 1000,
                error=f"Tool execution timed out after {context.timeout_seconds}s",
                error_code="TIMEOUT"
            )
            
        except Exception as e:
            self._error_count += 1
            logger.exception(f"Tool {self.name} failed: {e}")
            return ToolExecutionResult(
                execution_id=context.execution_id,
                tool_name=self.name,
                success=False,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                duration_ms=(datetime.now(timezone.utc) - started_at).total_seconds() * 1000,
                error=str(e),
                error_code="EXECUTION_ERROR"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            "name": self.name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(1, self._execution_count),
            "total_duration_ms": self._total_duration_ms,
            "avg_duration_ms": self._total_duration_ms / max(1, self._execution_count)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

class ToolRegistry:
    """
    Central registry for all MCP tools.
    
    The registry manages tool lifecycle:
    - Registration with metadata
    - Discovery by category, tag, or name
    - Validation of inputs/outputs
    - Execution tracking and statistics
    - Chain of Custody integration
    
    Usage:
        registry = ToolRegistry()
        
        @registry.tool(
            name="analysis.timeline.build",
            category=ToolCategory.ANALYSIS,
            description="Build unified timeline from evidence"
        )
        async def build_timeline(case_id: str, ...) -> TimelineResult:
            ...
        
        # List tools
        tools = registry.list_tools(category=ToolCategory.ANALYSIS)
        
        # Invoke tool
        result = await registry.invoke("analysis.timeline.build", params, context)
    """
    
    _instance: Optional["ToolRegistry"] = None
    
    def __new__(cls) -> "ToolRegistry":
        """Singleton pattern for global registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._tools: Dict[str, RegisteredTool] = {}
        self._by_category: Dict[ToolCategory, Set[str]] = {cat: set() for cat in ToolCategory}
        self._by_tag: Dict[str, Set[str]] = {}
        self._execution_history: List[ToolExecutionResult] = []
        self._max_history = 1000
        self._coc_service = None  # Will be set during app startup
        self._initialized = True
        
        logger.info("ToolRegistry initialized")
    
    def set_coc_service(self, coc_service: Any) -> None:
        """Set the Chain of Custody service for logging."""
        self._coc_service = coc_service
    
    def register(
        self,
        name: str,
        handler: ToolFunc,
        category: ToolCategory = ToolCategory.UTILITY,
        description: str = "",
        **kwargs
    ) -> RegisteredTool:
        """
        Register a tool with the registry.
        
        Args:
            name: Unique tool name (e.g., "analysis.timeline.build")
            handler: Async function that implements the tool
            category: Tool category
            description: Human-readable description
            **kwargs: Additional ToolMetadata fields
        
        Returns:
            RegisteredTool instance
        """
        if name in self._tools:
            logger.warning(f"Tool {name} already registered, overwriting")
        
        # Extract parameters from function signature
        sig = inspect.signature(handler)
        params = []
        
        for param_name, param in sig.parameters.items():
            if param_name == "_context":
                continue  # Skip context parameter
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue  # Skip *args/**kwargs from tool schemas
            
            params.append(ToolParameter(
                name=param_name,
                type_annotation=param.annotation if param.annotation != inspect.Parameter.empty else Any,
                required=param.default == inspect.Parameter.empty,
                default=param.default if param.default != inspect.Parameter.empty else None
            ))
        
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            parameters=params,
            **kwargs
        )
        
        # Get input/output validators from type hints if present
        hints = get_type_hints(handler) if hasattr(handler, "__annotations__") else {}
        input_validator = kwargs.get("input_schema")
        output_validator = hints.get("return")
        
        tool = RegisteredTool(
            metadata=metadata,
            handler=handler,
            input_validator=input_validator,
            output_validator=output_validator if isinstance(output_validator, type) and issubclass(output_validator, BaseModel) else None
        )
        
        self._tools[name] = tool
        self._by_category[category].add(name)
        
        for tag in metadata.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(name)
        
        logger.info(f"Registered tool: {name} (category: {category.value})")
        return tool
    
    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry."""
        if name not in self._tools:
            return False
        
        tool = self._tools[name]
        del self._tools[name]
        self._by_category[tool.category].discard(name)
        
        for tag in tool.metadata.tags:
            if tag in self._by_tag:
                self._by_tag[tag].discard(name)
        
        logger.info(f"Unregistered tool: {name}")
        return True
    
    def get(self, name: str) -> Optional[RegisteredTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def exists(self, name: str) -> bool:
        """Check if a tool exists."""
        return name in self._tools
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tag: Optional[str] = None,
        access_level: Optional[ToolAccessLevel] = None
    ) -> List[RegisteredTool]:
        """
        List tools with optional filtering.
        
        Args:
            category: Filter by category
            tag: Filter by tag
            access_level: Filter by access level
        
        Returns:
            List of matching tools
        """
        if category:
            names = self._by_category.get(category, set())
        elif tag:
            names = self._by_tag.get(tag, set())
        else:
            names = set(self._tools.keys())
        
        tools = [self._tools[n] for n in names if n in self._tools]
        
        if access_level:
            tools = [t for t in tools if t.metadata.access_level == access_level]
        
        return sorted(tools, key=lambda t: t.name)
    
    def list_categories(self) -> Dict[ToolCategory, int]:
        """Get all categories with tool counts."""
        return {cat: len(names) for cat, names in self._by_category.items() if names}
    
    def list_tags(self) -> Dict[str, int]:
        """Get all tags with tool counts."""
        return {tag: len(names) for tag, names in self._by_tag.items()}
    
    def get_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get MCP schema for a tool."""
        tool = self.get(name)
        return tool.metadata.to_mcp_schema() if tool else None
    
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get MCP schemas for all tools."""
        return [tool.metadata.to_mcp_schema() for tool in self._tools.values()]
    
    async def invoke(
        self,
        name: str,
        params: Dict[str, Any],
        context: Optional[ToolExecutionContext] = None
    ) -> ToolExecutionResult:
        """
        Invoke a tool by name.
        
        Args:
            name: Tool name
            params: Parameters to pass to the tool
            context: Execution context (created if not provided)
        
        Returns:
            ToolExecutionResult with success/failure and result data
        """
        tool = self.get(name)
        if not tool:
            return ToolExecutionResult(
                execution_id=context.execution_id if context else str(uuid.uuid4()),
                tool_name=name,
                success=False,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=0,
                error=f"Tool not found: {name}",
                error_code="TOOL_NOT_FOUND"
            )
        
        # Create context if not provided
        if context is None:
            context = ToolExecutionContext(
                timeout_seconds=tool.metadata.timeout_seconds
            )
        
        # Log to Chain of Custody before execution
        if tool.metadata.logs_to_coc and self._coc_service:
            try:
                context.coc_event_id = await self._coc_service.log_event(
                    case_id=context.case_id,
                    action=tool.metadata.coc_action_type,
                    details={
                        "tool": name,
                        "execution_id": context.execution_id,
                        "params_hash": hashlib.sha256(
                            json.dumps(params, sort_keys=True, default=str).encode()
                        ).hexdigest()[:16]
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log to CoC: {e}")
        
        # Execute
        result = await tool.execute(params, context)
        
        # Update CoC with result
        if result.coc_event_id and self._coc_service:
            try:
                await self._coc_service.update_event(
                    event_id=result.coc_event_id,
                    success=result.success,
                    evidence_hash=result.evidence_hash,
                    duration_ms=result.duration_ms
                )
            except Exception as e:
                logger.warning(f"Failed to update CoC: {e}")
        
        # Store in history
        self._execution_history.append(result)
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        total_executions = sum(t._execution_count for t in self._tools.values())
        total_errors = sum(t._error_count for t in self._tools.values())
        
        return {
            "total_tools": len(self._tools),
            "by_category": {cat.value: len(names) for cat, names in self._by_category.items()},
            "total_tags": len(self._by_tag),
            "total_executions": total_executions,
            "total_errors": total_errors,
            "error_rate": total_errors / max(1, total_executions),
            "tools": {name: tool.get_stats() for name, tool in self._tools.items()}
        }
    
    def get_recent_executions(self, limit: int = 100) -> List[ToolExecutionResult]:
        """Get recent execution history."""
        return self._execution_history[-limit:]
    
    def tool(
        self,
        name: str,
        category: ToolCategory = ToolCategory.UTILITY,
        description: str = "",
        **kwargs
    ) -> Callable[[ToolFunc], ToolFunc]:
        """
        Decorator for registering tools.
        
        Usage:
            @registry.tool(
                name="analysis.timeline.build",
                category=ToolCategory.ANALYSIS,
                description="Build unified timeline"
            )
            async def build_timeline(case_id: str, ...) -> TimelineResult:
                ...
        """
        def decorator(func: ToolFunc) -> ToolFunc:
            self.register(
                name=name,
                handler=func,
                category=category,
                description=description,
                **kwargs
            )
            return func
        return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL REGISTRY INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton instance
registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ToolCategory",
    "ToolAccessLevel",
    "ToolParameter",
    "ToolMetadata",
    "ToolExecutionContext",
    "ToolExecutionResult",
    "RegisteredTool",
    "ToolRegistry",
    "registry",
    "get_registry",
]
