"""
MCP Tool Decorators — Declarative tool registration and enhancement.

This module provides decorators for:
- @mcp_tool: Register functions as MCP tools with full metadata
- @requires_case: Ensure case_id is valid before execution
- @requires_investigation: Ensure investigation context exists
- @with_coc_logging: Add Chain of Custody logging
- @with_evidence_hash: Compute and verify evidence hashes
- @with_timeout: Add timeout handling
- @with_retry: Add retry logic for transient failures
- @validate_params: Add parameter validation
- @audit_trail: Create detailed audit logs

Design Principles:
- Decorators are composable (can stack multiple)
- Minimal boilerplate for tool authors
- Automatic CoC integration
- Evidence integrity guaranteed

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import json
import logging
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any, Awaitable, Callable, Dict, Generic, List, Optional, 
    ParamSpec, Set, Tuple, Type, TypeVar, Union, get_type_hints
)

from pydantic import BaseModel, ValidationError

from .registry import (
    ToolCategory, ToolAccessLevel, ToolExecutionContext,
    ToolRegistry, registry, RegisteredTool
)
from .schemas import (
    MCPToolResult, EvidenceValue, SourceReference, EvidenceType
)


logger = logging.getLogger(__name__)


# Type variables for generic decorators
T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


# ═══════════════════════════════════════════════════════════════════════════════
# CORE DECORATOR: @mcp_tool
# ═══════════════════════════════════════════════════════════════════════════════

def mcp_tool(
    name: str,
    *,
    category: ToolCategory = ToolCategory.UTILITY,
    description: str = "",
    version: str = "1.0.0",
    access_level: ToolAccessLevel = ToolAccessLevel.AUTHENTICATED,
    requires_case_id: bool = True,
    requires_investigation_id: bool = False,
    logs_to_coc: bool = True,
    timeout_seconds: float = 300.0,
    tags: Optional[Set[str]] = None,
    input_schema: Optional[Type[BaseModel]] = None,
    output_schema: Optional[Type[BaseModel]] = None,
    examples: Optional[List[Dict[str, Any]]] = None,
    related_tools: Optional[List[str]] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Main decorator for registering MCP tools.
    
    This decorator:
    - Registers the function with the tool registry
    - Adds parameter validation
    - Handles execution context injection
    - Manages Chain of Custody logging
    - Computes evidence hashes
    
    Args:
        name: Unique tool name (e.g., "analysis.timeline.build")
        category: Tool category for organization
        description: Human-readable description
        version: Tool version
        access_level: Access control level
        requires_case_id: Require case_id parameter
        requires_investigation_id: Require investigation_id parameter
        logs_to_coc: Log executions to Chain of Custody
        timeout_seconds: Execution timeout
        tags: Tags for discovery
        input_schema: Pydantic model for input validation
        output_schema: Pydantic model for output validation
        examples: Usage examples
        related_tools: Names of related tools
    
    Usage:
        @mcp_tool(
            name="analysis.timeline.build",
            category=ToolCategory.ANALYSIS,
            description="Build unified timeline from evidence"
        )
        async def build_timeline(
            case_id: str,
            sources: Optional[List[str]] = None,
            _context: ToolExecutionContext = None
        ) -> TimelineResult:
            # Implementation
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract or create context
            context = kwargs.pop("_context", None)
            if context is None:
                context = ToolExecutionContext(
                    case_id=kwargs.get("case_id"),
                    investigation_id=kwargs.get("investigation_id"),
                    timeout_seconds=timeout_seconds
                )
            
            # Validate required parameters
            if requires_case_id and not kwargs.get("case_id") and not context.case_id:
                raise ValueError(f"Tool {name} requires case_id parameter")
            
            if requires_investigation_id:
                inv_id = kwargs.get("investigation_id") or context.investigation_id
                if not inv_id:
                    raise ValueError(f"Tool {name} requires investigation_id parameter")
            
            # Input validation
            if input_schema:
                try:
                    validated = input_schema(**kwargs)
                    kwargs = validated.model_dump()
                except ValidationError as e:
                    raise ValueError(f"Input validation failed: {e}")
            
            # Re-inject context
            kwargs["_context"] = context
            
            # Execute
            result = await func(*args, **kwargs)
            
            # Output validation
            if output_schema and result is not None:
                if isinstance(result, dict):
                    try:
                        output_schema(**result)
                    except ValidationError as e:
                        logger.warning(f"Output validation warning: {e}")
            
            return result
        
        # Register with registry
        registry.register(
            name=name,
            handler=wrapper,
            category=category,
            description=description,
            version=version,
            access_level=access_level,
            requires_case_id=requires_case_id,
            logs_to_coc=logs_to_coc,
            timeout_seconds=timeout_seconds,
            tags=tags or set(),
            input_schema=input_schema,
            output_schema=output_schema,
            examples=examples or [],
            related_tools=related_tools or []
        )
        
        # Store metadata on function for introspection
        wrapper._mcp_tool_name = name
        wrapper._mcp_category = category
        wrapper._mcp_registered = True
        
        return wrapper
    
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

def requires_case(
    validate_exists: bool = False,
    db_func: Optional[Callable] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to ensure case_id is valid.
    
    Args:
        validate_exists: Whether to check if case exists in database
        db_func: Optional async function to check case existence
    
    Usage:
        @requires_case(validate_exists=True)
        async def my_tool(case_id: str, ...) -> Result:
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            case_id = kwargs.get("case_id")
            context = kwargs.get("_context")
            
            if not case_id:
                if context and context.case_id:
                    case_id = context.case_id
                    kwargs["case_id"] = case_id
                else:
                    raise ValueError("case_id is required")
            
            if validate_exists and db_func:
                exists = await db_func(case_id)
                if not exists:
                    raise ValueError(f"Case not found: {case_id}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def requires_investigation() -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to ensure investigation context exists.
    
    Usage:
        @requires_investigation()
        async def my_tool(investigation_id: str, ...) -> Result:
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            investigation_id = kwargs.get("investigation_id")
            context = kwargs.get("_context")
            
            if not investigation_id:
                if context and context.investigation_id:
                    investigation_id = context.investigation_id
                    kwargs["investigation_id"] = investigation_id
                else:
                    raise ValueError("investigation_id is required")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def validate_params(
    schema: Type[BaseModel]
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to validate parameters against a Pydantic schema.
    
    Args:
        schema: Pydantic model class for validation
    
    Usage:
        class MyToolParams(BaseModel):
            case_id: str
            filters: Dict[str, Any]
        
        @validate_params(MyToolParams)
        async def my_tool(**kwargs) -> Result:
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Extract context before validation
            context = kwargs.pop("_context", None)
            
            try:
                validated = schema(**kwargs)
                kwargs = validated.model_dump()
            except ValidationError as e:
                raise ValueError(f"Parameter validation failed: {e}")
            
            # Re-inject context
            if context:
                kwargs["_context"] = context
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# CHAIN OF CUSTODY DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

class CoCActionType(str, Enum):
    """Chain of Custody action types."""
    TOOL_EXECUTION = "TOOL_EXECUTION"
    EVIDENCE_QUERY = "EVIDENCE_QUERY"
    EVIDENCE_CREATE = "EVIDENCE_CREATE"
    EVIDENCE_MODIFY = "EVIDENCE_MODIFY"
    REPORT_UPDATE = "REPORT_UPDATE"
    HYPOTHESIS_TEST = "HYPOTHESIS_TEST"
    INVESTIGATION_EVENT = "INVESTIGATION_EVENT"


@dataclass
class CoCEntry:
    """A Chain of Custody entry."""
    event_id: str
    timestamp: datetime
    action: CoCActionType
    case_id: Optional[str]
    investigation_id: Optional[str]
    tool_name: Optional[str]
    user_id: Optional[str]
    params_hash: str
    result_hash: Optional[str]
    success: bool
    duration_ms: float
    details: Dict[str, Any]


def with_coc_logging(
    action_type: CoCActionType = CoCActionType.TOOL_EXECUTION,
    include_params: bool = True,
    include_result: bool = True,
    sensitive_params: Optional[Set[str]] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to add Chain of Custody logging.
    
    This creates an audit trail of all tool executions with:
    - Timestamp
    - Action type
    - Parameters (hashed)
    - Result (hashed)
    - Duration
    - Success/failure
    
    Args:
        action_type: Type of CoC action
        include_params: Include parameter hash in log
        include_result: Include result hash in log
        sensitive_params: Parameters to exclude from logging
    
    Usage:
        @with_coc_logging(action_type=CoCActionType.EVIDENCE_QUERY)
        async def query_evidence(case_id: str, ...) -> Evidence:
            ...
    """
    sensitive = sensitive_params or set()
    
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            context = kwargs.get("_context")
            start_time = time.time()
            event_id = f"coc-{uuid.uuid4().hex[:12]}"
            
            # Hash parameters (excluding sensitive ones)
            params_to_hash = {
                k: v for k, v in kwargs.items() 
                if k not in sensitive and k != "_context"
            }
            params_hash = hashlib.sha256(
                json.dumps(params_to_hash, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            
            # Create CoC entry
            entry = CoCEntry(
                event_id=event_id,
                timestamp=datetime.now(timezone.utc),
                action=action_type,
                case_id=kwargs.get("case_id") or (context.case_id if context else None),
                investigation_id=kwargs.get("investigation_id") or (context.investigation_id if context else None),
                tool_name=getattr(func, "_mcp_tool_name", func.__name__),
                user_id=context.user_id if context else None,
                params_hash=params_hash,
                result_hash=None,
                success=False,
                duration_ms=0,
                details={}
            )
            
            try:
                result = await func(*args, **kwargs)
                
                # Compute result hash
                if include_result and result is not None:
                    if hasattr(result, "model_dump"):
                        result_data = result.model_dump()
                    elif isinstance(result, dict):
                        result_data = result
                    else:
                        result_data = {"result": str(result)}
                    
                    entry.result_hash = hashlib.sha256(
                        json.dumps(result_data, sort_keys=True, default=str).encode()
                    ).hexdigest()[:16]
                
                entry.success = True
                return result
                
            except Exception as e:
                entry.details["error"] = str(e)
                entry.details["traceback"] = traceback.format_exc()
                raise
                
            finally:
                entry.duration_ms = (time.time() - start_time) * 1000
                
                # Log to CoC service (if available)
                if context and hasattr(context, "coc_event_id"):
                    context.coc_event_id = entry.event_id
                
                # Get action string (handle both enum and string)
                action_str = entry.action.value if hasattr(entry.action, 'value') else str(entry.action)
                
                # Also log locally
                logger.info(
                    f"CoC: {action_str} | "
                    f"tool={entry.tool_name} | "
                    f"case={entry.case_id} | "
                    f"success={entry.success} | "
                    f"duration={entry.duration_ms:.1f}ms"
                )
        
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE INTEGRITY DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

def with_evidence_hash(
    result_field: str = "evidence",
    hash_field: str = "evidence_hash",
    algorithm: str = "sha256"
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to compute evidence hash on result.
    
    This ensures evidence integrity by computing a cryptographic
    hash of the evidence data that can be verified later.
    
    Args:
        result_field: Field in result containing evidence
        hash_field: Field name for computed hash
        algorithm: Hash algorithm (sha256, sha512)
    
    Usage:
        @with_evidence_hash(result_field="data")
        async def get_evidence(case_id: str, ...) -> Dict:
            return {"data": [...]}
        # Result will have "evidence_hash" field added
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = await func(*args, **kwargs)
            
            if result is not None:
                # Get evidence data
                if hasattr(result, result_field):
                    evidence = getattr(result, result_field)
                elif isinstance(result, dict) and result_field in result:
                    evidence = result[result_field]
                else:
                    evidence = result
                
                # Compute hash (RFC 8785 canonical JSON)
                if evidence is not None:
                    if hasattr(evidence, "model_dump"):
                        evidence_data = evidence.model_dump()
                    elif isinstance(evidence, (list, dict)):
                        evidence_data = evidence
                    else:
                        evidence_data = {"value": evidence}
                    
                    canonical = json.dumps(evidence_data, sort_keys=True, default=str)
                    
                    if algorithm == "sha256":
                        hash_value = hashlib.sha256(canonical.encode()).hexdigest()
                    elif algorithm == "sha512":
                        hash_value = hashlib.sha512(canonical.encode()).hexdigest()
                    else:
                        hash_value = hashlib.sha256(canonical.encode()).hexdigest()
                    
                    hash_str = f"{algorithm}:{hash_value}"
                    
                    # Add hash to result
                    if isinstance(result, dict):
                        result[hash_field] = hash_str
                    elif hasattr(result, "__dict__"):
                        setattr(result, hash_field, hash_str)
            
            return result
        return wrapper
    return decorator


def verify_evidence_hash(
    data: Any,
    expected_hash: str
) -> Tuple[bool, Optional[str]]:
    """
    Verify evidence hash matches expected value.
    
    Args:
        data: Evidence data to verify
        expected_hash: Expected hash string (e.g., "sha256:abc123...")
    
    Returns:
        Tuple of (match: bool, computed_hash: str)
    """
    # Parse expected hash
    parts = expected_hash.split(":", 1)
    if len(parts) == 2:
        algorithm, expected = parts
    else:
        algorithm, expected = "sha256", expected_hash
    
    # Compute hash
    if hasattr(data, "model_dump"):
        data_dict = data.model_dump()
    elif isinstance(data, (list, dict)):
        data_dict = data
    else:
        data_dict = {"value": data}
    
    canonical = json.dumps(data_dict, sort_keys=True, default=str)
    
    if algorithm == "sha256":
        computed = hashlib.sha256(canonical.encode()).hexdigest()
    elif algorithm == "sha512":
        computed = hashlib.sha512(canonical.encode()).hexdigest()
    else:
        computed = hashlib.sha256(canonical.encode()).hexdigest()
    
    return computed == expected, f"{algorithm}:{computed}"


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION CONTROL DECORATORS
# ═══════════════════════════════════════════════════════════════════════════════

def with_timeout(
    seconds: float = 300.0,
    error_message: Optional[str] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to add timeout handling.
    
    Args:
        seconds: Timeout in seconds
        error_message: Custom error message
    
    Usage:
        @with_timeout(seconds=60)
        async def slow_operation(...) -> Result:
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                msg = error_message or f"Operation timed out after {seconds}s"
                raise TimeoutError(msg)
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to add retry logic for transient failures.
    
    Args:
        max_attempts: Maximum retry attempts
        delay_seconds: Initial delay between retries
        backoff_factor: Multiply delay by this factor each retry
        exceptions: Exception types to catch and retry
        on_retry: Callback when retrying (attempt, exception)
    
    Usage:
        @with_retry(max_attempts=3, exceptions=(IOError, TimeoutError))
        async def unreliable_operation(...) -> Result:
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        if on_retry:
                            on_retry(attempt, e)
                        
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed. "
                            f"Last error: {e}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT TRAIL DECORATOR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AuditEntry:
    """An audit trail entry."""
    audit_id: str
    timestamp: datetime
    tool_name: str
    operation: str
    user_id: Optional[str]
    case_id: Optional[str]
    investigation_id: Optional[str]
    params: Dict[str, Any]
    result_summary: Optional[str]
    success: bool
    duration_ms: float
    metadata: Dict[str, Any]


# In-memory audit trail (should be persisted in production)
_audit_trail: List[AuditEntry] = []


def audit_trail(
    operation: Optional[str] = None,
    include_params: bool = True,
    sensitive_params: Optional[Set[str]] = None,
    summarize_result: Optional[Callable[[Any], str]] = None
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Decorator to create detailed audit logs.
    
    This creates a comprehensive audit trail for compliance
    and debugging purposes.
    
    Args:
        operation: Operation name (defaults to function name)
        include_params: Include parameters in audit log
        sensitive_params: Parameters to redact
        summarize_result: Function to summarize result
    
    Usage:
        @audit_trail(operation="BUILD_TIMELINE")
        async def build_timeline(...) -> Result:
            ...
    """
    sensitive = sensitive_params or {"password", "token", "secret", "key"}
    
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        op_name = operation or func.__name__.upper()
        
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            context = kwargs.get("_context")
            start_time = time.time()
            audit_id = f"audit-{uuid.uuid4().hex[:12]}"
            
            # Prepare params (redacting sensitive)
            params = {}
            if include_params:
                for k, v in kwargs.items():
                    if k == "_context":
                        continue
                    if k in sensitive:
                        params[k] = "[REDACTED]"
                    else:
                        params[k] = v
            
            entry = AuditEntry(
                audit_id=audit_id,
                timestamp=datetime.now(timezone.utc),
                tool_name=getattr(func, "_mcp_tool_name", func.__name__),
                operation=op_name,
                user_id=context.user_id if context else None,
                case_id=kwargs.get("case_id") or (context.case_id if context else None),
                investigation_id=kwargs.get("investigation_id") or (context.investigation_id if context else None),
                params=params,
                result_summary=None,
                success=False,
                duration_ms=0,
                metadata={}
            )
            
            try:
                result = await func(*args, **kwargs)
                entry.success = True
                
                if summarize_result:
                    entry.result_summary = summarize_result(result)
                elif isinstance(result, dict):
                    entry.result_summary = f"Dict with {len(result)} keys"
                elif hasattr(result, "__len__"):
                    entry.result_summary = f"Collection with {len(result)} items"
                else:
                    entry.result_summary = "Completed"
                
                return result
                
            except Exception as e:
                entry.metadata["error"] = str(e)
                entry.metadata["error_type"] = type(e).__name__
                raise
                
            finally:
                entry.duration_ms = (time.time() - start_time) * 1000
                _audit_trail.append(entry)
                
                # Keep audit trail bounded
                if len(_audit_trail) > 10000:
                    _audit_trail.pop(0)
        
        return wrapper
    return decorator


def get_audit_trail(
    limit: int = 100,
    case_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    since: Optional[datetime] = None
) -> List[AuditEntry]:
    """
    Get audit trail entries.
    
    Args:
        limit: Maximum entries to return
        case_id: Filter by case ID
        tool_name: Filter by tool name
        since: Filter by timestamp
    
    Returns:
        List of audit entries
    """
    entries = _audit_trail
    
    if case_id:
        entries = [e for e in entries if e.case_id == case_id]
    
    if tool_name:
        entries = [e for e in entries if e.tool_name == tool_name]
    
    if since:
        entries = [e for e in entries if e.timestamp >= since]
    
    return entries[-limit:]


# ═══════════════════════════════════════════════════════════════════════════════
# COMPOSITION HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def compose_decorators(
    *decorators: Callable
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Compose multiple decorators into one.
    
    Usage:
        standard_tool = compose_decorators(
            with_timeout(60),
            with_coc_logging(),
            with_evidence_hash(),
            audit_trail()
        )
        
        @standard_tool
        @mcp_tool(name="my.tool", ...)
        async def my_tool(...):
            ...
    """
    def composed(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        result = func
        for decorator in reversed(decorators):
            result = decorator(result)
        return result
    return composed


# ═══════════════════════════════════════════════════════════════════════════════
# PRESET DECORATOR COMBINATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def analysis_tool(
    name: str,
    description: str,
    **kwargs
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Preset decorator for analysis tools.
    
    Combines:
    - mcp_tool registration
    - CoC logging
    - Evidence hashing
    - Audit trail
    
    Usage:
        @analysis_tool(
            name="analysis.timeline.build",
            description="Build unified timeline"
        )
        async def build_timeline(...):
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        # Apply decorators from innermost to outermost
        wrapped = func
        wrapped = audit_trail(operation=name.upper().replace(".", "_"))(wrapped)
        wrapped = with_evidence_hash()(wrapped)
        wrapped = with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)(wrapped)
        wrapped = mcp_tool(
            name=name,
            category=ToolCategory.ANALYSIS,
            description=description,
            **kwargs
        )(wrapped)
        return wrapped
    return decorator


def evidence_tool(
    name: str,
    description: str,
    **kwargs
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Preset decorator for evidence tools.
    
    Usage:
        @evidence_tool(
            name="evidence.query",
            description="Query evidence vault"
        )
        async def query_evidence(...):
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        wrapped = func
        wrapped = audit_trail(operation=name.upper().replace(".", "_"))(wrapped)
        wrapped = with_evidence_hash()(wrapped)
        wrapped = with_coc_logging(action_type=CoCActionType.EVIDENCE_QUERY)(wrapped)
        wrapped = mcp_tool(
            name=name,
            category=ToolCategory.EVIDENCE,
            description=description,
            **kwargs
        )(wrapped)
        return wrapped
    return decorator


def hypothesis_tool(
    name: str,
    description: str,
    **kwargs
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Preset decorator for hypothesis tools.
    
    Usage:
        @hypothesis_tool(
            name="hypothesis.create",
            description="Create hypothesis"
        )
        async def create_hypothesis(...):
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        wrapped = func
        wrapped = audit_trail(operation=name.upper().replace(".", "_"))(wrapped)
        wrapped = with_coc_logging(action_type=CoCActionType.HYPOTHESIS_TEST)(wrapped)
        wrapped = mcp_tool(
            name=name,
            category=ToolCategory.HYPOTHESIS,
            description=description,
            **kwargs
        )(wrapped)
        return wrapped
    return decorator


def report_tool(
    name: str,
    description: str,
    **kwargs
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    Preset decorator for report tools.
    
    Usage:
        @report_tool(
            name="report.canvas.add",
            description="Add element to canvas"
        )
        async def add_canvas_element(...):
            ...
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        wrapped = func
        wrapped = audit_trail(operation=name.upper().replace(".", "_"))(wrapped)
        wrapped = with_coc_logging(action_type=CoCActionType.REPORT_UPDATE)(wrapped)
        wrapped = mcp_tool(
            name=name,
            category=ToolCategory.REPORT,
            description=description,
            **kwargs
        )(wrapped)
        return wrapped
    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core decorator
    "mcp_tool",
    
    # Validation
    "requires_case",
    "requires_investigation",
    "validate_params",
    
    # Chain of Custody
    "CoCActionType",
    "CoCEntry",
    "with_coc_logging",
    
    # Evidence
    "with_evidence_hash",
    "verify_evidence_hash",
    
    # Execution control
    "with_timeout",
    "with_retry",
    
    # Audit
    "AuditEntry",
    "audit_trail",
    "get_audit_trail",
    
    # Composition
    "compose_decorators",
    
    # Presets
    "analysis_tool",
    "evidence_tool",
    "hypothesis_tool",
    "report_tool",
]
