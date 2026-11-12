"""
MCP Server — Model Context Protocol server implementation.

This module provides a complete MCP server that:
- Exposes all registered tools via JSON-RPC 2.0
- Handles tool discovery and introspection
- Manages execution contexts and sessions
- Integrates with Chain of Custody logging
- Supports both HTTP and WebSocket transports

The server acts as the bridge between AI agents and the tool registry,
enabling intelligent investigation through structured tool calls.

Protocol Reference: https://modelcontextprotocol.io/

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any, AsyncGenerator, Callable, Dict, List, 
    Optional, Set, Tuple, Union
)

from pydantic import BaseModel, Field, ValidationError
from starlette.requests import Request

from .registry import (
    ToolRegistry, ToolCategory, ToolExecutionContext,
    ToolExecutionResult, registry, get_registry
)
from .schemas import (
    MCPToolResult, InvestigationContext, InvestigationStatus
)


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PROTOCOL CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_IMPLEMENTATION_NAME = "nflip-mcp-server"
MCP_IMPLEMENTATION_VERSION = "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# JSON-RPC TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class JSONRPCErrorCode(int, Enum):
    """Standard JSON-RPC 2.0 error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # MCP-specific error codes
    TOOL_NOT_FOUND = -32001
    TOOL_EXECUTION_ERROR = -32002
    VALIDATION_ERROR = -32003
    TIMEOUT_ERROR = -32004
    PERMISSION_DENIED = -32005
    SESSION_NOT_FOUND = -32006
    INVESTIGATION_ERROR = -32007


class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 request."""
    jsonrpc: str = Field(default="2.0", description="Protocol version")
    id: Optional[Union[str, int]] = Field(default=None, description="Request ID")
    method: str = Field(..., description="Method name")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Parameters")


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""
    code: int = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    data: Optional[Any] = Field(default=None, description="Additional data")


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 response."""
    jsonrpc: str = Field(default="2.0")
    id: Optional[Union[str, int]] = Field(default=None)
    result: Optional[Any] = Field(default=None)
    error: Optional[JSONRPCError] = Field(default=None)
    
    @classmethod
    def success(cls, id: Union[str, int], result: Any) -> "JSONRPCResponse":
        """Create a success response."""
        return cls(id=id, result=result)
    
    @classmethod
    def error_response(
        cls, 
        id: Optional[Union[str, int]], 
        code: JSONRPCErrorCode,
        message: str,
        data: Optional[Any] = None
    ) -> "JSONRPCResponse":
        """Create an error response."""
        return cls(
            id=id,
            error=JSONRPCError(code=code.value, message=message, data=data)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MCP MESSAGE TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class MCPCapabilities(BaseModel):
    """Server capabilities."""
    tools: Dict[str, Any] = Field(default_factory=lambda: {"listChanged": True})
    prompts: Dict[str, Any] = Field(default_factory=dict)
    resources: Dict[str, Any] = Field(default_factory=dict)
    logging: Dict[str, Any] = Field(default_factory=dict)


class MCPServerInfo(BaseModel):
    """Server information."""
    name: str = Field(default=MCP_IMPLEMENTATION_NAME)
    version: str = Field(default=MCP_IMPLEMENTATION_VERSION)


class MCPInitializeResult(BaseModel):
    """Result of initialize request."""
    protocolVersion: str = Field(default=MCP_PROTOCOL_VERSION)
    capabilities: MCPCapabilities = Field(default_factory=MCPCapabilities)
    serverInfo: MCPServerInfo = Field(default_factory=MCPServerInfo)


class MCPTool(BaseModel):
    """MCP tool definition."""
    name: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any] = Field(default_factory=dict)


class MCPToolsListResult(BaseModel):
    """Result of tools/list request."""
    tools: List[MCPTool]


class MCPToolCallResult(BaseModel):
    """Result of tools/call request."""
    content: List[Dict[str, Any]]
    isError: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MCPSession:
    """An MCP session with a client."""
    session_id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Client info
    client_name: Optional[str] = None
    client_version: Optional[str] = None
    
    # State
    initialized: bool = False
    active: bool = True
    
    # Context
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    investigation_context: Optional[InvestigationContext] = None
    user_id: Optional[str] = None
    
    # Statistics
    request_count: int = 0
    tool_call_count: int = 0
    error_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def is_expired(self, timeout_seconds: float = 3600) -> bool:
        """Check if session has expired."""
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > timeout_seconds


class SessionManager:
    """Manages MCP sessions."""
    
    def __init__(
        self,
        max_sessions: int = 100,
        session_timeout: float = 3600
    ):
        self._sessions: Dict[str, MCPSession] = {}
        self._max_sessions = max_sessions
        self._session_timeout = session_timeout
        self._lock = asyncio.Lock()
    
    async def create_session(
        self,
        client_name: Optional[str] = None,
        client_version: Optional[str] = None,
        case_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> MCPSession:
        """Create a new session."""
        async with self._lock:
            # Clean up expired sessions
            await self._cleanup_expired()
            
            # Check capacity
            if len(self._sessions) >= self._max_sessions:
                # Remove oldest session
                oldest = min(self._sessions.values(), key=lambda s: s.last_activity)
                del self._sessions[oldest.session_id]
            
            session = MCPSession(
                client_name=client_name,
                client_version=client_version,
                case_id=case_id,
                user_id=user_id
            )
            self._sessions[session.session_id] = session
            
            logger.info(f"Created session: {session.session_id}")
            return session
    
    async def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)
        if session and not session.is_expired(self._session_timeout):
            session.touch()
            return session
        return None
    
    async def close_session(self, session_id: str) -> bool:
        """Close a session."""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].active = False
                del self._sessions[session_id]
                logger.info(f"Closed session: {session_id}")
                return True
            return False
    
    async def _cleanup_expired(self) -> int:
        """Remove expired sessions."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired(self._session_timeout)
        ]
        for sid in expired:
            del self._sessions[sid]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)
    
    def get_active_count(self) -> int:
        """Get count of active sessions."""
        return len(self._sessions)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics."""
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
            "session_timeout": self._session_timeout,
            "sessions": {
                sid: {
                    "created_at": s.created_at.isoformat(),
                    "last_activity": s.last_activity.isoformat(),
                    "request_count": s.request_count,
                    "tool_call_count": s.tool_call_count,
                    "error_count": s.error_count,
                    "case_id": s.case_id
                }
                for sid, s in self._sessions.items()
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class MCPServer:
    """
    Model Context Protocol server.
    
    This server implements the MCP protocol for exposing tools to AI agents.
    It handles:
    - Tool discovery and listing
    - Tool invocation with parameter validation
    - Session management
    - Chain of Custody integration
    
    Usage:
        server = MCPServer()
        
        # Handle a JSON-RPC request
        response = await server.handle_request(request_json)
        
        # Or use with FastAPI
        @app.post("/mcp")
        async def mcp_endpoint(request: JSONRPCRequest):
            return await server.handle_rpc(request)
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_sessions: int = 100,
        session_timeout: float = 3600
    ):
        self._registry = registry or get_registry()
        self._sessions = SessionManager(max_sessions, session_timeout)
        self._started = False
        self._coc_service = None
        
        # Method handlers
        self._handlers: Dict[str, Callable] = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "session/create": self._handle_session_create,
            "session/close": self._handle_session_close,
            "session/info": self._handle_session_info,
            "investigation/start": self._handle_investigation_start,
            "investigation/status": self._handle_investigation_status,
            "stats": self._handle_stats,
        }
        
        logger.info("MCPServer initialized")
    
    def set_coc_service(self, coc_service: Any) -> None:
        """Set Chain of Custody service."""
        self._coc_service = coc_service
        self._registry.set_coc_service(coc_service)
    
    async def start(self) -> None:
        """Start the server."""
        self._started = True
        logger.info("MCPServer started")
    
    async def stop(self) -> None:
        """Stop the server."""
        self._started = False
        logger.info("MCPServer stopped")
    
    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        """Context manager for server lifespan."""
        await self.start()
        try:
            yield
        finally:
            await self.stop()
    
    async def handle_request(
        self,
        request_data: Union[str, bytes, Dict[str, Any]],
        session_id: Optional[str] = None
    ) -> str:
        """
        Handle a raw JSON-RPC request.
        
        Args:
            request_data: JSON string, bytes, or dict
            session_id: Optional session ID for context
        
        Returns:
            JSON-RPC response as string
        """
        # Parse request
        try:
            if isinstance(request_data, bytes):
                request_data = request_data.decode("utf-8")
            if isinstance(request_data, str):
                data = json.loads(request_data)
            else:
                data = request_data
            
            request = JSONRPCRequest(**data)
        except json.JSONDecodeError as e:
            response = JSONRPCResponse.error_response(
                None,
                JSONRPCErrorCode.PARSE_ERROR,
                f"Invalid JSON: {e}"
            )
            return response.model_dump_json()
        except ValidationError as e:
            response = JSONRPCResponse.error_response(
                None,
                JSONRPCErrorCode.INVALID_REQUEST,
                f"Invalid request: {e}"
            )
            return response.model_dump_json()
        
        # Handle request
        response = await self.handle_rpc(request, session_id)
        return response.model_dump_json()
    
    async def handle_rpc(
        self,
        request: JSONRPCRequest,
        session_id: Optional[str] = None
    ) -> JSONRPCResponse:
        """
        Handle a parsed JSON-RPC request.
        
        Args:
            request: Parsed JSON-RPC request
            session_id: Optional session ID
        
        Returns:
            JSON-RPC response
        """
        logger.debug(f"Handling request: {request.method}")
        
        # Get session if provided
        session = None
        if session_id:
            session = await self._sessions.get_session(session_id)
            if session:
                session.request_count += 1
        
        # Find handler
        handler = self._handlers.get(request.method)
        
        if handler:
            try:
                result = await handler(request.params or {}, session)
                return JSONRPCResponse.success(request.id, result)
            except Exception as e:
                logger.exception(f"Handler error for {request.method}: {e}")
                if session:
                    session.error_count += 1
                return JSONRPCResponse.error_response(
                    request.id,
                    JSONRPCErrorCode.INTERNAL_ERROR,
                    str(e)
                )
        
        # Check if it's a tool call with tools/ prefix
        if request.method.startswith("tools/"):
            return JSONRPCResponse.error_response(
                request.id,
                JSONRPCErrorCode.METHOD_NOT_FOUND,
                f"Unknown method: {request.method}"
            )
        
        # Treat as tool name directly
        return await self._invoke_tool(request.method, request.params or {}, session, request.id)
    
    async def _invoke_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        session: Optional[MCPSession],
        request_id: Optional[Union[str, int]]
    ) -> JSONRPCResponse:
        """Invoke a tool by name."""
        if not self._registry.exists(tool_name):
            return JSONRPCResponse.error_response(
                request_id,
                JSONRPCErrorCode.TOOL_NOT_FOUND,
                f"Tool not found: {tool_name}"
            )
        
        # Build execution context
        context = ToolExecutionContext(
            case_id=params.get("case_id") or (session.case_id if session else None),
            investigation_id=params.get("investigation_id") or (session.investigation_id if session else None),
            user_id=session.user_id if session else None
        )
        
        # Invoke tool
        result = await self._registry.invoke(tool_name, params, context)
        
        if session:
            session.tool_call_count += 1
            if not result.success:
                session.error_count += 1
        
        if result.success:
            # Convert to MCP tool call result format
            content = []
            
            if result.result is not None:
                if hasattr(result.result, "model_dump"):
                    content.append({
                        "type": "text",
                        "text": json.dumps(result.result.model_dump(), default=str)
                    })
                elif isinstance(result.result, dict):
                    content.append({
                        "type": "text",
                        "text": json.dumps(result.result, default=str)
                    })
                else:
                    content.append({
                        "type": "text",
                        "text": str(result.result)
                    })
            
            # Add evidence hash if present
            if result.evidence_hash:
                content.append({
                    "type": "evidence",
                    "hash": result.evidence_hash,
                    "cards": result.evidence_cards_created
                })
            
            return JSONRPCResponse.success(
                request_id,
                MCPToolCallResult(content=content, isError=False).model_dump()
            )
        else:
            return JSONRPCResponse.error_response(
                request_id,
                JSONRPCErrorCode.TOOL_EXECUTION_ERROR,
                result.error or "Tool execution failed",
                data={"error_code": result.error_code}
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Protocol Handlers
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _handle_initialize(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle initialize request."""
        if session:
            session.initialized = True
            session.client_name = params.get("clientInfo", {}).get("name")
            session.client_version = params.get("clientInfo", {}).get("version")
        
        return MCPInitializeResult().model_dump()
    
    async def _handle_ping(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True, "timestamp": datetime.now(timezone.utc).isoformat()}
    
    async def _handle_tools_list(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle tools/list request."""
        # Get optional filters
        category = params.get("category")
        tag = params.get("tag")
        
        # Convert category string to enum if provided
        category_enum = None
        if category:
            try:
                category_enum = ToolCategory(category)
            except ValueError:
                pass
        
        # Get tools
        tools = self._registry.list_tools(category=category_enum, tag=tag)
        
        # Convert to MCP format
        mcp_tools = []
        for tool in tools:
            schema = tool.metadata.to_mcp_schema()
            mcp_tools.append(MCPTool(
                name=schema["name"],
                description=schema["description"],
                inputSchema=schema["inputSchema"]
            ))
        
        return MCPToolsListResult(tools=mcp_tools).model_dump()
    
    async def _handle_tools_call(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        tool_params = params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("Missing tool name")
        
        # Invoke the tool
        response = await self._invoke_tool(tool_name, tool_params, session, None)
        
        if response.error:
            return MCPToolCallResult(
                content=[{
                    "type": "text",
                    "text": response.error.message
                }],
                isError=True
            ).model_dump()
        
        return response.result
    
    async def _handle_session_create(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle session/create request."""
        new_session = await self._sessions.create_session(
            client_name=params.get("client_name"),
            client_version=params.get("client_version"),
            case_id=params.get("case_id"),
            user_id=params.get("user_id")
        )
        
        return {
            "session_id": new_session.session_id,
            "created_at": new_session.created_at.isoformat()
        }
    
    async def _handle_session_close(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle session/close request."""
        session_id = params.get("session_id") or (session.session_id if session else None)
        
        if not session_id:
            raise ValueError("Missing session_id")
        
        closed = await self._sessions.close_session(session_id)
        return {"closed": closed}
    
    async def _handle_session_info(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle session/info request."""
        target_id = params.get("session_id") or (session.session_id if session else None)
        
        if not target_id:
            raise ValueError("Missing session_id")
        
        target = await self._sessions.get_session(target_id)
        if not target:
            raise ValueError(f"Session not found: {target_id}")
        
        return {
            "session_id": target.session_id,
            "created_at": target.created_at.isoformat(),
            "last_activity": target.last_activity.isoformat(),
            "initialized": target.initialized,
            "active": target.active,
            "case_id": target.case_id,
            "investigation_id": target.investigation_id,
            "request_count": target.request_count,
            "tool_call_count": target.tool_call_count,
            "error_count": target.error_count
        }
    
    async def _handle_investigation_start(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle investigation/start request."""
        if not session:
            raise ValueError("Session required to start investigation")
        
        # Create investigation context
        context = InvestigationContext(
            case_id=params.get("case_id") or session.case_id,
            scenario=params.get("scenario", ""),
            llm_provider=params.get("llm_provider", "gemini")
        )
        
        if not context.case_id:
            raise ValueError("case_id is required")
        
        session.case_id = context.case_id
        session.investigation_id = context.investigation_id
        session.investigation_context = context
        
        return {
            "investigation_id": context.investigation_id,
            "status": context.status.value,
            "case_id": context.case_id
        }
    
    async def _handle_investigation_status(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle investigation/status request."""
        if not session or not session.investigation_context:
            raise ValueError("No active investigation in session")
        
        ctx = session.investigation_context
        return {
            "investigation_id": ctx.investigation_id,
            "status": ctx.status.value,
            "case_id": ctx.case_id,
            "scenario": ctx.scenario,
            "objectives": [o.model_dump() for o in ctx.objectives],
            "clarification_questions": [q.model_dump() for q in ctx.clarification_questions]
        }
    
    async def _handle_stats(
        self,
        params: Dict[str, Any],
        session: Optional[MCPSession]
    ) -> Dict[str, Any]:
        """Handle stats request."""
        return {
            "server": {
                "name": MCP_IMPLEMENTATION_NAME,
                "version": MCP_IMPLEMENTATION_VERSION,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "started": self._started
            },
            "registry": self._registry.get_stats(),
            "sessions": self._sessions.get_stats()
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    def list_tools(
        self,
        category: Optional[ToolCategory] = None
    ) -> List[Dict[str, Any]]:
        """List available tools synchronously."""
        tools = self._registry.list_tools(category=category)
        return [t.metadata.to_mcp_schema() for t in tools]
    
    async def call_tool(
        self,
        name: str,
        params: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> MCPToolResult:
        """Call a tool directly."""
        session = None
        if session_id:
            session = await self._sessions.get_session(session_id)
        
        context = ToolExecutionContext(
            case_id=params.get("case_id") or (session.case_id if session else None),
            investigation_id=params.get("investigation_id") or (session.investigation_id if session else None),
            user_id=session.user_id if session else None
        )
        
        result = await self._registry.invoke(name, params, context)
        return result.to_mcp_result()


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_mcp_router(server: Optional[MCPServer] = None):
    """
    Create a FastAPI router for MCP endpoints.
    
    Usage:
        from fastapi import FastAPI
        from operation_room.mcp.server import create_mcp_router
        
        app = FastAPI()
        mcp_server = MCPServer()
        app.include_router(create_mcp_router(mcp_server), prefix="/mcp")
    """
    try:
        from fastapi import APIRouter, Header, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError("FastAPI is required for create_mcp_router")
    
    router = APIRouter(tags=["MCP"])
    _server = server or MCPServer()
    
    @router.post("/")
    async def mcp_endpoint(
        request: Request,
        x_session_id: Optional[str] = Header(None)
    ):
        """Main MCP JSON-RPC endpoint."""
        body = await request.body()
        response_json = await _server.handle_request(body, x_session_id)
        return JSONResponse(
            content=json.loads(response_json),
            media_type="application/json"
        )
    
    @router.get("/tools")
    async def list_tools(category: Optional[str] = None):
        """List available tools."""
        cat_enum = None
        if category:
            try:
                cat_enum = ToolCategory(category)
            except ValueError:
                raise HTTPException(400, f"Invalid category: {category}")
        
        return {"tools": _server.list_tools(cat_enum)}
    
    @router.get("/health")
    async def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "server": MCP_IMPLEMENTATION_NAME,
            "version": MCP_IMPLEMENTATION_VERSION
        }
    
    return router


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL SERVER INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton instance
_server: Optional[MCPServer] = None


def get_server() -> MCPServer:
    """Get the global MCP server instance."""
    global _server
    if _server is None:
        _server = MCPServer()
    return _server


def set_server(server: MCPServer) -> None:
    """Set the global MCP server instance."""
    global _server
    _server = server


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Constants
    "MCP_PROTOCOL_VERSION",
    "MCP_IMPLEMENTATION_NAME",
    "MCP_IMPLEMENTATION_VERSION",
    
    # JSON-RPC
    "JSONRPCErrorCode",
    "JSONRPCRequest",
    "JSONRPCError",
    "JSONRPCResponse",
    
    # MCP Types
    "MCPCapabilities",
    "MCPServerInfo",
    "MCPInitializeResult",
    "MCPTool",
    "MCPToolsListResult",
    "MCPToolCallResult",
    
    # Session
    "MCPSession",
    "SessionManager",
    
    # Server
    "MCPServer",
    "create_mcp_router",
    "get_server",
    "set_server",
]
