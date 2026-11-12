"""
MCP Infrastructure Tests — Comprehensive test suite for Phase 1.

This test suite validates:
- Schema creation and validation
- Tool registration and discovery
- Decorator functionality
- Server operation
- Evidence hashing integrity

Run with: pytest app/mcp/tests/test_mcp.py -v

Author: NFLIP Development Team
Version: 1.0.0
"""

import asyncio
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

# Import MCP modules
from operation_room.mcp import (
    # Schemas
    MCPBaseModel,
    HashedModel,
    EvidenceValue,
    EvidenceCard,
    SourceReference,
    EvidenceType,
    InvestigationContext,
    InvestigationStatus,
    Hypothesis,
    HypothesisVerdict,
    ConfidenceLevel,
    ConfidenceAssessment,
    TimeRange,
    PlanStep,
    PhaseStatus,
    MCPToolResult,
    
    # Registry
    ToolCategory,
    ToolRegistry,
    ToolExecutionContext,
    ToolParameter,
    ToolMetadata,
    get_registry,
    
    # Decorators
    mcp_tool,
    requires_case,
    with_coc_logging,
    with_evidence_hash,
    with_timeout,
    with_retry,
    audit_trail,
    verify_evidence_hash,
    get_audit_trail,
    CoCActionType,
    
    # Server
    MCPServer,
    MCPSession,
    SessionManager,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCErrorCode,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fresh_registry():
    """Create a fresh registry for testing."""
    reg = ToolRegistry.__new__(ToolRegistry)
    reg._initialized = False
    reg.__init__()
    return reg


@pytest.fixture
def sample_source():
    """Create a sample source reference."""
    return SourceReference(
        source_type="windows_event",
        source_file="C:\\logs\\Security.evtx",
        source_table="unified_timeline",
        row_id="row-12345"
    )


@pytest.fixture
def sample_evidence(sample_source):
    """Create a sample evidence value."""
    return EvidenceValue(
        evidence_type=EvidenceType.LOG_EVENT,
        field_name="src_ip",
        value="192.168.1.100",
        value_type="str",
        source=sample_source,
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_context():
    """Create a sample execution context."""
    return ToolExecutionContext(
        case_id="case-test-123",
        investigation_id="inv-test-456",
        user_id="user-test"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemas:
    """Test Pydantic schema functionality."""
    
    def test_source_reference_creation(self, sample_source):
        """Test creating a source reference."""
        assert sample_source.source_type == "windows_event"
        assert sample_source.source_table == "unified_timeline"
        assert sample_source.row_id == "row-12345"
    
    def test_source_reference_validation(self):
        """Test source reference validation."""
        # Must have row_id or row_ids
        with pytest.raises(ValueError):
            SourceReference(
                source_type="test",
                source_table="test"
            )
        
        # With row_ids should work
        source = SourceReference(
            source_type="test",
            source_table="test",
            row_ids=["row-1", "row-2"]
        )
        assert source.row_ids == ["row-1", "row-2"]
    
    def test_evidence_value_creation(self, sample_evidence):
        """Test creating an evidence value."""
        assert sample_evidence.field_name == "src_ip"
        assert sample_evidence.value == "192.168.1.100"
        assert sample_evidence.value_type == "str"
    
    def test_evidence_value_validation(self, sample_source):
        """Test evidence value validation."""
        # Cannot be None
        with pytest.raises(ValueError):
            EvidenceValue(
                evidence_type=EvidenceType.LOG_EVENT,
                field_name="test",
                value=None,
                value_type="str",
                source=sample_source
            )
        
        # Cannot be empty string
        with pytest.raises(ValueError):
            EvidenceValue(
                evidence_type=EvidenceType.LOG_EVENT,
                field_name="test",
                value="  ",
                value_type="str",
                source=sample_source
            )
    
    def test_hashed_model_hash_computation(self, sample_evidence):
        """Test automatic hash computation."""
        hash1 = sample_evidence.content_hash
        assert hash1.startswith("sha256:")
        assert len(hash1) == 71  # "sha256:" + 64 hex chars
        
        # Same data should produce same hash
        hash2 = sample_evidence.content_hash
        assert hash1 == hash2
    
    def test_evidence_card_creation(self, sample_evidence):
        """Test creating an evidence card."""
        card = EvidenceCard(
            title="Test Evidence Card",
            case_id="case-123",
            evidence_values=[sample_evidence],
            tags=["test", "network"]
        )
        
        assert card.title == "Test Evidence Card"
        assert card.evidence_count == 1
        assert card.content_hash.startswith("sha256:")
    
    def test_time_range_validation(self):
        """Test time range validation."""
        now = datetime.now(timezone.utc)
        
        # Valid range
        valid = TimeRange(
            start=now - timedelta(hours=1),
            end=now
        )
        assert valid.start < valid.end
        
        # Invalid: start >= end
        with pytest.raises(ValueError):
            TimeRange(start=now, end=now - timedelta(hours=1))
    
    def test_confidence_level_from_score(self):
        """Test confidence level conversion."""
        assert ConfidenceLevel.from_score(0.95) == ConfidenceLevel.VERY_HIGH
        assert ConfidenceLevel.from_score(0.80) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(0.60) == ConfidenceLevel.MODERATE
        assert ConfidenceLevel.from_score(0.30) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.10) == ConfidenceLevel.VERY_LOW
    
    def test_hypothesis_creation(self):
        """Test creating a hypothesis."""
        hyp = Hypothesis(
            investigation_id="inv-123",
            code="H1",
            statement="Data was exfiltrated via USB",
            baseline_assumption="false"
        )
        
        assert hyp.code == "H1"
        assert hyp.verdict == HypothesisVerdict.UNTESTED
        assert hyp.baseline_assumption == "false"
        assert hyp.content_hash.startswith("sha256:")
    
    def test_investigation_context(self):
        """Test investigation context creation."""
        ctx = InvestigationContext(
            case_id="case-123",
            scenario="Test scenario for investigation"
        )
        
        assert ctx.status == InvestigationStatus.INITIALIZING
        assert ctx.investigation_id.startswith("inv-")
        assert ctx.case_id == "case-123"
    
    def test_plan_step(self):
        """Test plan step creation."""
        step = PlanStep(
            phase="Phase 1: Timeline",
            step_number="1.1",
            title="Build Timeline",
            description="Build unified timeline from all sources",
            tool_name="analysis.timeline.build",
            tool_params={"sources": ["all"]},
            success_criteria="Timeline covers >80% of time range"
        )
        
        assert step.status == PhaseStatus.PENDING
        assert step.step_number == "1.1"
    
    def test_mcp_tool_result(self):
        """Test MCP tool result."""
        result = MCPToolResult(
            success=True,
            tool_name="test.tool",
            data={"key": "value"},
            evidence_hash="sha256:abc123"
        )
        
        assert result.success is True
        assert result.data == {"key": "value"}


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistry:
    """Test tool registry functionality."""
    
    def test_registry_singleton(self):
        """Test registry is a singleton."""
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2
    
    def test_tool_registration(self, fresh_registry):
        """Test registering a tool."""
        async def test_handler(case_id: str, _context=None) -> dict:
            return {"result": "success"}
        
        tool = fresh_registry.register(
            name="test.tool",
            handler=test_handler,
            category=ToolCategory.UTILITY,
            description="A test tool"
        )
        
        assert fresh_registry.exists("test.tool")
        assert tool.name == "test.tool"
        assert tool.category == ToolCategory.UTILITY
    
    def test_tool_unregistration(self, fresh_registry):
        """Test unregistering a tool."""
        async def test_handler(_context=None) -> dict:
            return {}
        
        fresh_registry.register("test.remove", test_handler)
        assert fresh_registry.exists("test.remove")
        
        result = fresh_registry.unregister("test.remove")
        assert result is True
        assert not fresh_registry.exists("test.remove")
    
    def test_list_tools_by_category(self, fresh_registry):
        """Test listing tools by category."""
        async def analysis_handler(_context=None) -> dict:
            return {}
        
        async def evidence_handler(_context=None) -> dict:
            return {}
        
        fresh_registry.register("analysis.test1", analysis_handler, category=ToolCategory.ANALYSIS)
        fresh_registry.register("analysis.test2", analysis_handler, category=ToolCategory.ANALYSIS)
        fresh_registry.register("evidence.test1", evidence_handler, category=ToolCategory.EVIDENCE)
        
        analysis_tools = fresh_registry.list_tools(category=ToolCategory.ANALYSIS)
        assert len(analysis_tools) == 2
        
        evidence_tools = fresh_registry.list_tools(category=ToolCategory.EVIDENCE)
        assert len(evidence_tools) == 1
    
    def test_tool_schema_generation(self, fresh_registry):
        """Test MCP schema generation."""
        async def test_handler(
            case_id: str,
            filters: Optional[Dict] = None,
            _context=None
        ) -> dict:
            return {}
        
        fresh_registry.register(
            name="test.schema",
            handler=test_handler,
            description="Test tool"
        )
        
        schema = fresh_registry.get_schema("test.schema")
        assert schema is not None
        assert schema["name"] == "test.schema"
        assert "inputSchema" in schema
        assert "case_id" in schema["inputSchema"]["properties"]
    
    @pytest.mark.asyncio
    async def test_tool_invocation(self, fresh_registry):
        """Test invoking a tool."""
        async def echo_handler(message: str, _context=None) -> dict:
            return {"echo": message}
        
        fresh_registry.register("test.echo", echo_handler)
        
        result = await fresh_registry.invoke(
            "test.echo",
            {"message": "hello"},
            ToolExecutionContext()
        )
        
        assert result.success is True
        assert result.result == {"echo": "hello"}
    
    @pytest.mark.asyncio
    async def test_tool_not_found(self, fresh_registry):
        """Test invoking non-existent tool."""
        result = await fresh_registry.invoke(
            "nonexistent.tool",
            {},
            ToolExecutionContext()
        )
        
        assert result.success is False
        assert result.error_code == "TOOL_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_tool_execution_error(self, fresh_registry):
        """Test tool execution error handling."""
        async def failing_handler(_context=None) -> dict:
            raise ValueError("Test error")
        
        fresh_registry.register("test.fail", failing_handler)
        
        result = await fresh_registry.invoke("test.fail", {})
        
        assert result.success is False
        assert result.error_code == "EXECUTION_ERROR"
        assert "Test error" in result.error
    
    def test_registry_stats(self, fresh_registry):
        """Test registry statistics."""
        async def handler(_context=None) -> dict:
            return {}
        
        fresh_registry.register("test.stats1", handler, category=ToolCategory.ANALYSIS)
        fresh_registry.register("test.stats2", handler, category=ToolCategory.EVIDENCE)
        
        stats = fresh_registry.get_stats()
        assert stats["total_tools"] == 2
        assert stats["by_category"]["analysis"] == 1
        assert stats["by_category"]["evidence"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecorators:
    """Test decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_requires_case_decorator(self):
        """Test requires_case decorator."""
        @requires_case()
        async def test_func(case_id: str, _context=None):
            return {"case_id": case_id}
        
        # With case_id
        result = await test_func(case_id="case-123")
        assert result["case_id"] == "case-123"
        
        # Without case_id (should fail)
        with pytest.raises(ValueError, match="case_id is required"):
            await test_func()
    
    @pytest.mark.asyncio
    async def test_with_timeout_decorator(self):
        """Test timeout decorator."""
        @with_timeout(seconds=0.1)
        async def slow_func():
            await asyncio.sleep(1)
            return "done"
        
        with pytest.raises(TimeoutError):
            await slow_func()
    
    @pytest.mark.asyncio
    async def test_with_retry_decorator(self):
        """Test retry decorator."""
        call_count = 0
        
        @with_retry(max_attempts=3, delay_seconds=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IOError("Temporary failure")
            return "success"
        
        result = await flaky_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_with_evidence_hash_decorator(self):
        """Test evidence hash decorator."""
        @with_evidence_hash(result_field="data")
        async def get_data():
            return {"data": {"ip": "192.168.1.1", "user": "admin"}}
        
        result = await get_data()
        assert "evidence_hash" in result
        assert result["evidence_hash"].startswith("sha256:")
    
    def test_verify_evidence_hash(self):
        """Test evidence hash verification."""
        data = {"ip": "192.168.1.1", "user": "admin"}
        
        # Compute hash
        canonical = json.dumps(data, sort_keys=True, default=str)
        expected = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        
        # Verify
        match, computed = verify_evidence_hash(data, expected)
        assert match is True
        assert computed == expected
        
        # Wrong hash
        match, _ = verify_evidence_hash(data, "sha256:wronghash")
        assert match is False
    
    @pytest.mark.asyncio
    async def test_with_coc_logging_decorator(self):
        """Test CoC logging decorator."""
        @with_coc_logging(action_type=CoCActionType.TOOL_EXECUTION)
        async def logged_func(case_id: str, _context=None):
            return {"result": "logged"}
        
        result = await logged_func(case_id="case-123")
        assert result == {"result": "logged"}
    
    @pytest.mark.asyncio
    async def test_audit_trail_decorator(self):
        """Test audit trail decorator."""
        @audit_trail(operation="TEST_OP")
        async def audited_func(case_id: str, _context=None):
            return {"audited": True}
        
        result = await audited_func(case_id="case-123")
        assert result == {"audited": True}
        
        # Check audit trail
        entries = get_audit_trail(limit=1)
        assert len(entries) >= 1
        assert entries[-1].operation == "TEST_OP"


# ═══════════════════════════════════════════════════════════════════════════════
# SERVER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestServer:
    """Test MCP server functionality."""
    
    @pytest.fixture
    def server(self):
        """Create a fresh server for testing."""
        return MCPServer()
    
    @pytest.mark.asyncio
    async def test_server_start_stop(self, server):
        """Test server lifecycle."""
        await server.start()
        assert server._started is True
        
        await server.stop()
        assert server._started is False
    
    @pytest.mark.asyncio
    async def test_server_lifespan(self, server):
        """Test server lifespan context manager."""
        async with server.lifespan():
            assert server._started is True
        assert server._started is False
    
    @pytest.mark.asyncio
    async def test_handle_initialize(self, server):
        """Test initialize request."""
        request = JSONRPCRequest(
            id=1,
            method="initialize",
            params={
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        )
        
        response = await server.handle_rpc(request)
        assert response.error is None
        assert response.result is not None
        assert "protocolVersion" in response.result
    
    @pytest.mark.asyncio
    async def test_handle_ping(self, server):
        """Test ping request."""
        request = JSONRPCRequest(id=1, method="ping")
        response = await server.handle_rpc(request)
        
        assert response.error is None
        assert response.result["pong"] is True
    
    @pytest.mark.asyncio
    async def test_handle_tools_list(self, server):
        """Test tools/list request."""
        # Register a test tool first
        async def test_handler(_context=None) -> dict:
            return {}
        
        server._registry.register(
            "test.list.tool",
            test_handler,
            description="Test tool"
        )
        
        request = JSONRPCRequest(id=1, method="tools/list")
        response = await server.handle_rpc(request)
        
        assert response.error is None
        assert "tools" in response.result
        tool_names = [t["name"] for t in response.result["tools"]]
        assert "test.list.tool" in tool_names
    
    @pytest.mark.asyncio
    async def test_handle_tools_call(self, server):
        """Test tools/call request."""
        async def echo_handler(msg: str, _context=None) -> dict:
            return {"echo": msg}
        
        server._registry.register("test.echo", echo_handler)
        
        request = JSONRPCRequest(
            id=1,
            method="tools/call",
            params={
                "name": "test.echo",
                "arguments": {"msg": "hello"}
            }
        )
        
        response = await server.handle_rpc(request)
        assert response.error is None
        assert response.result["isError"] is False
    
    @pytest.mark.asyncio
    async def test_handle_stats(self, server):
        """Test stats request."""
        request = JSONRPCRequest(id=1, method="stats")
        response = await server.handle_rpc(request)
        
        assert response.error is None
        assert "server" in response.result
        assert "registry" in response.result
    
    @pytest.mark.asyncio
    async def test_session_create_and_close(self, server):
        """Test session management."""
        # Create session
        create_request = JSONRPCRequest(
            id=1,
            method="session/create",
            params={"case_id": "case-test"}
        )
        create_response = await server.handle_rpc(create_request)
        
        assert create_response.error is None
        session_id = create_response.result["session_id"]
        
        # Get session info
        info_request = JSONRPCRequest(
            id=2,
            method="session/info",
            params={"session_id": session_id}
        )
        info_response = await server.handle_rpc(info_request, session_id)
        
        assert info_response.error is None
        assert info_response.result["case_id"] == "case-test"
        
        # Close session
        close_request = JSONRPCRequest(
            id=3,
            method="session/close",
            params={"session_id": session_id}
        )
        close_response = await server.handle_rpc(close_request)
        
        assert close_response.error is None
        assert close_response.result["closed"] is True
    
    @pytest.mark.asyncio
    async def test_raw_request_handling(self, server):
        """Test raw JSON request handling."""
        request_json = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "ping"
        })
        
        response_json = await server.handle_request(request_json)
        response = json.loads(response_json)
        
        assert response["result"]["pong"] is True
    
    @pytest.mark.asyncio
    async def test_invalid_json_request(self, server):
        """Test handling invalid JSON."""
        response_json = await server.handle_request("not valid json")
        response = json.loads(response_json)
        
        assert response["error"] is not None
        assert response["error"]["code"] == JSONRPCErrorCode.PARSE_ERROR.value
    
    @pytest.mark.asyncio
    async def test_method_not_found(self, server):
        """Test method not found error."""
        request = JSONRPCRequest(id=1, method="tools/nonexistent")
        response = await server.handle_rpc(request)
        
        assert response.error is not None
        assert response.error.code == JSONRPCErrorCode.METHOD_NOT_FOUND.value


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionManager:
    """Test session manager functionality."""
    
    @pytest.fixture
    def manager(self):
        return SessionManager(max_sessions=5, session_timeout=60)
    
    @pytest.mark.asyncio
    async def test_create_session(self, manager):
        """Test session creation."""
        session = await manager.create_session(
            client_name="test",
            case_id="case-123"
        )
        
        assert session.session_id.startswith("sess-")
        assert session.case_id == "case-123"
        assert session.active is True
    
    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        """Test getting a session."""
        session = await manager.create_session()
        retrieved = await manager.get_session(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    @pytest.mark.asyncio
    async def test_close_session(self, manager):
        """Test closing a session."""
        session = await manager.create_session()
        closed = await manager.close_session(session.session_id)
        
        assert closed is True
        
        # Should not be retrievable
        retrieved = await manager.get_session(session.session_id)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_max_sessions(self, manager):
        """Test max session limit."""
        # Create max sessions
        for i in range(5):
            await manager.create_session()
        
        assert manager.get_active_count() == 5
        
        # Creating one more should remove oldest
        await manager.create_session()
        assert manager.get_active_count() == 5
    
    def test_session_stats(self, manager):
        """Test session statistics."""
        stats = manager.get_stats()
        
        assert "active_sessions" in stats
        assert "max_sessions" in stats
        assert stats["max_sessions"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests for the complete MCP system."""
    
    @pytest.mark.asyncio
    async def test_full_tool_workflow(self):
        """Test complete tool registration and invocation."""
        server = MCPServer()
        await server.start()
        
        try:
            # Create session
            session_result = await server.handle_rpc(
                JSONRPCRequest(
                    id=1,
                    method="session/create",
                    params={"case_id": "case-workflow-test"}
                )
            )
            session_id = session_result.result["session_id"]
            
            # Register a tool
            async def workflow_tool(case_id: str, data: str, _context=None) -> dict:
                return {
                    "processed": True,
                    "case_id": case_id,
                    "data_length": len(data)
                }
            
            server._registry.register(
                "test.workflow",
                workflow_tool,
                category=ToolCategory.ANALYSIS,
                description="Workflow test tool"
            )
            
            # List tools
            list_result = await server.handle_rpc(
                JSONRPCRequest(id=2, method="tools/list"),
                session_id
            )
            tool_names = [t["name"] for t in list_result.result["tools"]]
            assert "test.workflow" in tool_names
            
            # Call tool
            call_result = await server.handle_rpc(
                JSONRPCRequest(
                    id=3,
                    method="tools/call",
                    params={
                        "name": "test.workflow",
                        "arguments": {
                            "case_id": "case-workflow-test",
                            "data": "test data"
                        }
                    }
                ),
                session_id
            )
            
            assert call_result.error is None
            assert call_result.result["isError"] is False
            
            # Check stats
            stats_result = await server.handle_rpc(
                JSONRPCRequest(id=4, method="stats"),
                session_id
            )
            
            assert stats_result.result["registry"]["total_executions"] >= 1
            
        finally:
            await server.stop()
    
    @pytest.mark.asyncio
    async def test_investigation_workflow(self):
        """Test investigation lifecycle."""
        server = MCPServer()
        await server.start()
        
        try:
            # Create session
            session_result = await server.handle_rpc(
                JSONRPCRequest(
                    id=1,
                    method="session/create",
                    params={"case_id": "case-inv-test"}
                )
            )
            session_id = session_result.result["session_id"]
            
            # Start investigation
            start_result = await server.handle_rpc(
                JSONRPCRequest(
                    id=2,
                    method="investigation/start",
                    params={
                        "case_id": "case-inv-test",
                        "scenario": "Test investigation scenario"
                    }
                ),
                session_id
            )
            
            assert start_result.error is None
            investigation_id = start_result.result["investigation_id"]
            assert investigation_id.startswith("inv-")
            
            # Get investigation status
            status_result = await server.handle_rpc(
                JSONRPCRequest(id=3, method="investigation/status"),
                session_id
            )
            
            assert status_result.error is None
            assert status_result.result["investigation_id"] == investigation_id
            assert status_result.result["status"] == "initializing"
            
        finally:
            await server.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
