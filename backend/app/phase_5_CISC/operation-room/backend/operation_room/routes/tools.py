"""
Universal Tool API Routes

Provides REST and SSE endpoints for:
- Tool discovery and capabilities
- Tool execution with real-time streaming
- Integration with Deep Research investigation flow
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import asyncio
import json
import logging
import os

from operation_room.tools import (
    tool_registry,
    tool_orchestration,
    ToolInput,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ToolExecuteRequest(BaseModel):
    """Request to execute a tool capability."""
    case_id: str
    tool_id: str
    capability: str
    parameters: Dict[str, Any] = {}
    context: Optional[Dict[str, Any]] = None


class InvestigationExecuteRequest(BaseModel):
    """Request to execute full investigation plan."""
    case_id: str
    investigation_id: str
    plan_phases: List[Dict[str, Any]]


class ToolInfo(BaseModel):
    """Information about a registered tool."""
    tool_id: str
    tool_name: str
    tool_version: str
    category: str
    description: str
    capabilities_count: int


class CapabilityInfo(BaseModel):
    """Information about a tool capability."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class AddApiKeyRequest(BaseModel):
    """Request payload to add a provider API key."""
    provider: str
    key: str
    supports_streaming: bool
    visualization_types: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[ToolInfo])
async def list_tools():
    """
    Get list of all registered Universal Tools.
    
    Returns basic information about each tool including:
    - Tool ID and name
    - Version and category
    - Number of capabilities
    """
    tools = tool_registry.get_all()
    
    return [
        ToolInfo(
            tool_id=tool.tool_id,
            tool_name=tool.tool_name,
            tool_version=tool.tool_version,
            category=tool.tool_category.value,
            description=tool.description,
            capabilities_count=len(tool.get_capabilities()),
        )
        for tool in tools
    ]


@router.get("/{tool_id}/capabilities", response_model=List[CapabilityInfo])
async def get_tool_capabilities(tool_id: str):
    """
    Get detailed capability information for a specific tool.
    
    Args:
        tool_id: Tool identifier (e.g., "timeline", "anomaly")
    
    Returns:
        List of capabilities with schemas and metadata
    """
    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    
    capabilities = tool.get_capabilities()
    
    return [
        CapabilityInfo(
            name=cap.name,
            description=cap.description,
            input_schema=cap.input_schema,
            output_schema=cap.output_schema,
            supports_streaming=cap.supports_streaming,
            visualization_types=[vt.value for vt in cap.visualization_types],
        )
        for cap in capabilities
    ]


@router.post("/{tool_id}/execute")
async def execute_tool(tool_id: str, request: ToolExecuteRequest):
    """
    Execute a tool capability (non-streaming).
    
    For one-shot execution where full result is returned at once.
    Use /stream endpoint for real-time streaming.
    
    Args:
        tool_id: Tool identifier
        request: Execution request with case_id, capability, parameters
    
    Returns:
        ToolOutput with narrative, findings, visualizations, etc.
    """
    tool = tool_registry.get(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    
    # Create tool input
    tool_input = ToolInput(
        case_id=request.case_id,
        capability=request.capability,
        parameters=request.parameters,
        context=request.context or {},
        request_id=f"{tool_id}-{request.capability}",
    )
    
    # Execute
    try:
        result = await tool.execute(tool_input)
        return result.to_dict()
    except Exception as e:
        logger.error(f"Tool execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution error: {str(e)}"
        )


@router.post("/{tool_id}/stream")
async def stream_tool_execution(tool_id: str, request: ToolExecuteRequest):
    """
    Execute a tool capability with real-time streaming.
    
    Returns Server-Sent Events (SSE) stream with progressive results:
    - TEXT_CHUNK events for narrative text
    - FINDING events for individual findings
    - VISUALIZATION events for charts/tables
    - TOOL_COMPLETE event when done
    
    Args:
        tool_id: Tool identifier
        request: Execution request
    
    Returns:
        SSE stream
    """
    async def event_generator():
        try:
            # Stream events from orchestration service
            async for event in tool_orchestration.execute_tool(
                case_id=request.case_id,
                tool_id=tool_id,
                capability=request.capability,
                parameters=request.parameters,
                context=request.context,
            ):
                # Format as SSE
                event_data = {
                    "type": event.event_type.value,
                    "timestamp": event.timestamp,
                    "data": event.data,
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "data": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/investigation/execute")
async def execute_investigation_plan(request: InvestigationExecuteRequest):
    """
    Execute full investigation plan with real-time streaming.
    
    Takes a Deep Research investigation plan and executes each phase/step
    using Universal Tools, streaming results as they're generated.
    
    This is the main integration point between:
    - Deep Research Orchestrator (plan generation)
    - Universal Module Tools (analysis execution)
    - Report Canvas (real-time updates)
    
    Args:
        request: Investigation execution request with plan phases
    
    Returns:
        SSE stream with phase/step/tool events
    """
    async def event_generator():
        try:
            async for event in tool_orchestration.execute_investigation_plan(
                case_id=request.case_id,
                investigation_id=request.investigation_id,
                plan_phases=request.plan_phases,
            ):
                # Format as SSE
                event_data = {
                    "type": event.event_type.value,
                    "timestamp": event.timestamp,
                    "data": event.data,
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
                
                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)
            
            # Send completion event
            completion_event = {
                "type": "investigation_complete",
                "data": {
                    "investigation_id": request.investigation_id,
                }
            }
            yield f"data: {json.dumps(completion_event)}\n\n"
            
        except Exception as e:
            logger.error(f"Investigation execution error: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "data": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/health")
async def tools_health():
    """
    Health check for Universal Tools system.
    
    Returns:
        Status and tool count
    """
    tools = tool_registry.get_all()  # Use get_all() for ModuleTool objects
    
    return {
        "status": "healthy",
        "tools_registered": len(tools),
        "tools": [
            {
                "id": tool.tool_id,
                "name": tool.tool_name,
                "version": tool.tool_version,
            }
            for tool in tools
        ]
    }


@router.get("/llm/status")
async def llm_status():
    """
    Get LLM provider status including multi-key information.
    
    Returns:
        Provider status and API key statistics
    """
    from operation_room.services.llm.multi_key import get_multi_key_provider
    from operation_room.services.llm.service import get_llm_service
    
    try:
        mkp = get_multi_key_provider()
        llm_service = get_llm_service()
        
        return {
            "status": "healthy",
            "current_provider": llm_service.current_provider.value,
            "providers": llm_service.list_providers(),
            "multi_key_stats": mkp.get_stats(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@router.post("/llm/add-key")
async def add_api_key(
    request: AddApiKeyRequest,
    x_admin_token: Optional[str] = Header(default=None),
):
    """
    Add a new API key for rotation.
    
    Requires:
        Optional `x-admin-token` header if OPROOM_ADMIN_TOKEN is configured.
    """
    from operation_room.services.llm.multi_key import get_multi_key_provider

    required_token = os.environ.get("OPROOM_ADMIN_TOKEN", "").strip()
    if required_token and x_admin_token != required_token:
        raise HTTPException(status_code=403, detail="Forbidden")

    provider = request.provider
    key = request.key
    
    if provider not in ["gemini", "openai"]:
        raise HTTPException(400, "Provider must be 'gemini' or 'openai'")
    
    if not key or len(key) < 10:
        raise HTTPException(400, "Invalid API key")
    
    mkp = get_multi_key_provider()
    mkp.add_key(key, provider)
    
    return {
        "status": "ok",
        "message": f"Added {provider} API key ending in ...{key[-4:]}",
        "stats": mkp.get_stats(),
    }
