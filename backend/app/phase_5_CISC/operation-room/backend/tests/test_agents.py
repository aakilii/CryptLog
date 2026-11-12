"""
Test Suite for Multi-Agent System.

Run with: pytest tests/test_agents.py -v

Author: NFLIP Development Team
Version: 1.0.0
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

# Import agent components
from operation_room.agents.base import (
    BaseAgent, AgentRegistry, AgentMessage, MessageType, AgentStatus
)
from operation_room.agents.research.knowledge_base import (
    knowledge_base, ResearchCategory, ResearchMethodology
)
from operation_room.agents.integration_layer import (
    PipelineExecutor, PipelineContext, PipelineStage, ResultAggregator, RetryHandler
)
from operation_room.agents.evaluators.module_evaluators import (
    EvaluatorFactory, TimelineEvaluator, AnomalyEvaluator
)
from operation_room.services.llm_service import (
    EnhancedLLMService, LLMResponse, Conversation
)
from operation_room.services.agent_runner import (
    AgentRunnerService, AgentRun, RunStatus, RunProgress
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_scenario():
    """Sample investigation scenario."""
    return """
    On 2024-03-15, network monitoring detected unusual outbound traffic from 
    workstation WS-142 (192.168.1.142) to IP 203.0.113.50. The traffic occurred 
    between 02:00-04:00 AM, outside normal business hours. Analysis shows 
    approximately 2.3GB of data transferred using encrypted channels (port 443).
    
    The workstation belongs to user jsmith (John Smith, Finance Department).
    Prior to the incident, user received email with attachment invoice_march.pdf
    from unknown sender (billing@acme-invoice.net).
    
    Memory analysis shows PowerShell processes running encoded commands.
    Registry modifications detected in Run keys for persistence.
    """


@pytest.fixture
def sample_evidence():
    """Sample evidence list."""
    return [
        {
            "evidence_id": "E001",
            "type": "network_connection",
            "source_ip": "192.168.1.142",
            "dest_ip": "203.0.113.50",
            "bytes": 2300000000,
            "timestamp": "2024-03-15T02:15:00Z"
        },
        {
            "evidence_id": "E002",
            "type": "email",
            "sender": "billing@acme-invoice.net",
            "recipient": "jsmith@company.com",
            "attachment": "invoice_march.pdf",
            "timestamp": "2024-03-14T14:30:00Z"
        },
        {
            "evidence_id": "E003",
            "type": "process",
            "name": "powershell.exe",
            "command_line": "powershell -enc SQBFAFgA...",
            "timestamp": "2024-03-15T02:00:00Z"
        }
    ]


@pytest.fixture
def sample_hypotheses():
    """Sample hypotheses."""
    return [
        {
            "id": "H1",
            "statement": "Data exfiltration via malware delivered through spearphishing",
            "probability": 0.75,
            "attack_vectors": ["T1566.001", "T1041"],
            "evidence_required": ["email", "network", "malware"]
        },
        {
            "id": "H2",
            "statement": "Insider threat - intentional data theft",
            "probability": 0.15,
            "attack_vectors": ["T1567"],
            "evidence_required": ["user_behavior", "access_logs"]
        }
    ]


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return LLMResponse(
        content=json.dumps({
            "hypotheses": [
                {
                    "id": "H1",
                    "statement": "Malware infection via phishing",
                    "probability": 0.8
                }
            ]
        }),
        tokens_used=100,
        latency_ms=500,
        model="test/model",
        success=True,
        parsed_json={
            "hypotheses": [
                {
                    "id": "H1",
                    "statement": "Malware infection via phishing",
                    "probability": 0.8
                }
            ]
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH KNOWLEDGE BASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchKnowledgeBase:
    """Tests for the research knowledge base."""
    
    def test_knowledge_base_has_methodologies(self):
        """Test that knowledge base contains methodologies."""
        stats = knowledge_base.get_statistics()
        assert stats['total_methodologies'] >= 100, "Should have 100+ methodologies"
        
    def test_list_categories(self):
        """Test listing categories."""
        stats = knowledge_base.get_statistics()
        categories = stats['categories']
        
        assert 'digital_forensics' in categories
        assert 'network_forensics' in categories
        assert 'malware_analysis' in categories
        assert 'memory_forensics' in categories
        
    def test_search_by_keyword(self):
        """Test searching by keyword."""
        results = knowledge_base.search("volatility")
        assert len(results) > 0, "Should find results for 'volatility'"
        
    def test_search_by_category(self):
        """Test searching by category."""
        results = knowledge_base.get_by_category(ResearchCategory.MEMORY_FORENSICS)
        assert len(results) > 0, "Should find memory forensics methodologies"
        
    def test_search_by_module(self):
        """Test searching by module."""
        results = knowledge_base.get_by_module("timeline")
        assert len(results) > 0, "Should find timeline-related methodologies"
        
    def test_get_recommendations(self):
        """Test getting recommendations."""
        results = knowledge_base.get_recommendations(
            hypothesis_types=["malware"],
            modules=["anomaly"],
            limit=5
        )
        assert len(results) <= 5


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE EVALUATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestModuleEvaluators:
    """Tests for module evaluators."""
    
    def test_evaluator_factory(self):
        """Test evaluator factory creates all evaluators."""
        evaluators = EvaluatorFactory.create_all()
        
        assert "timeline" in evaluators
        assert "anomaly" in evaluators
        assert "correlation" in evaluators
        assert "network" in evaluators
        assert "depth" in evaluators
        assert "crud" in evaluators
        
    def test_available_modules(self):
        """Test listing available modules."""
        modules = EvaluatorFactory.available_modules()
        assert len(modules) == 6
        
    @pytest.mark.asyncio
    async def test_timeline_evaluator(self):
        """Test timeline evaluator."""
        evaluator = TimelineEvaluator()
        
        module_output = {
            "events": [
                {
                    "timestamp": "2024-03-15T02:00:00Z",
                    "event_type": "process_start",
                    "source": "sysmon",
                    "description": "PowerShell process started"
                },
                {
                    "timestamp": "2024-03-15T02:05:00Z",
                    "event_type": "network",
                    "source": "netmon",
                    "description": "Outbound connection to 203.0.113.50"
                }
            ]
        }
        
        evaluation = await evaluator.evaluate(module_output)
        
        assert evaluation.module_name == "timeline"
        assert 0 <= evaluation.overall_confidence <= 1
        assert evaluation.data_quality > 0
        
    @pytest.mark.asyncio
    async def test_anomaly_evaluator(self):
        """Test anomaly evaluator."""
        evaluator = AnomalyEvaluator()
        
        module_output = {
            "anomalies": [
                {
                    "anomaly_score": 0.95,
                    "feature": "network_bytes",
                    "timestamp": "2024-03-15T02:15:00Z",
                    "cluster_id": 1
                }
            ]
        }
        
        evaluation = await evaluator.evaluate(module_output)
        
        assert evaluation.module_name == "anomaly"
        assert len(evaluation.anomalies) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION LAYER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationLayer:
    """Tests for integration layer components."""
    
    def test_result_aggregator_merge_evidence(self):
        """Test merging evidence from multiple sources."""
        evidence_lists = [
            [{"evidence_id": "E1", "type": "A"}],
            [{"evidence_id": "E2", "type": "B"}],
            [{"evidence_id": "E1", "type": "A"}],  # Duplicate
        ]
        
        merged = ResultAggregator.merge_evidence(evidence_lists)
        
        assert len(merged) == 2  # Duplicates removed
        
    def test_result_aggregator_combine_confidence(self):
        """Test combining confidence scores."""
        scores = [
            {"evidence": 0.8, "consistency": 0.7},
            {"evidence": 0.6, "consistency": 0.9}
        ]
        
        combined = ResultAggregator.combine_confidence_scores(scores)
        
        assert "evidence" in combined
        assert "consistency" in combined
        assert 0.6 <= combined["evidence"] <= 0.8
        
    @pytest.mark.asyncio
    async def test_retry_handler(self):
        """Test retry handler."""
        handler = RetryHandler(max_retries=3, base_delay=0.1)
        
        call_count = 0
        
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
            
        result = await handler.execute_with_retry(failing_then_success)
        
        assert result == "success"
        assert call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# LLM SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMService:
    """Tests for LLM service."""
    
    def test_conversation_management(self):
        """Test conversation management."""
        conv = Conversation(conversation_id="test-conv")
        
        conv.add_message("user", "Hello")
        conv.add_message("assistant", "Hi there")
        
        assert len(conv.messages) == 2
        
        context = conv.get_context()
        assert "User: Hello" in context
        assert "Assistant: Hi there" in context
        
    def test_conversation_pruning(self):
        """Test conversation message pruning."""
        conv = Conversation(conversation_id="test", max_messages=3)
        
        conv.add_message("system", "You are a helper")
        conv.add_message("user", "Q1")
        conv.add_message("assistant", "A1")
        conv.add_message("user", "Q2")
        conv.add_message("assistant", "A2")
        
        # Should keep system + last 2 messages
        assert len(conv.messages) <= 3
        
    def test_llm_response_dataclass(self):
        """Test LLMResponse dataclass."""
        response = LLMResponse(
            content="Test response",
            tokens_used=50,
            latency_ms=200,
            model="test/model",
            success=True
        )
        
        data = response.to_dict()
        assert data["content"] == "Test response"
        assert data["success"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT RUNNER TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentRunner:
    """Tests for agent runner service."""
    
    def test_create_run(self):
        """Test creating a run."""
        runner = AgentRunnerService()
        
        run = runner.create_run(
            case_id="CASE-001",
            scenario="Test scenario",
            report_type="technical"
        )
        
        assert run.run_id is not None
        assert run.case_id == "CASE-001"
        assert run.status == RunStatus.PENDING
        
    def test_list_runs(self):
        """Test listing runs."""
        runner = AgentRunnerService()
        
        runner.create_run("CASE-001", "Scenario 1")
        runner.create_run("CASE-002", "Scenario 2")
        
        runs = runner.list_runs()
        assert len(runs) >= 2
        
    def test_get_health(self):
        """Test health check."""
        runner = AgentRunnerService()
        
        health = runner.get_health()
        
        assert "status" in health
        assert "active_runs" in health
        assert "llm_provider" in health
        
    def test_run_progress(self):
        """Test run progress tracking."""
        progress = RunProgress(
            current_stage="hypothesis_analysis",
            total_stages=7,
            completed_stages=2,
            percentage=28.5,
            message="Analyzing hypotheses..."
        )
        
        data = progress.to_dict()
        assert data["current_stage"] == "hypothesis_analysis"
        assert data["percentage"] == 28.5


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT BASE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentBase:
    """Tests for agent base classes."""
    
    def test_agent_registry(self):
        """Test agent registry."""
        registry = AgentRegistry()
        
        # Create mock agent
        mock_agent = Mock()
        mock_agent.agent_id = "test-agent"
        mock_agent.agent_name = "Test Agent"
        mock_agent.get_info.return_value = {"agent_id": "test-agent"}
        
        registry.register(mock_agent)
        
        assert registry.get("test-agent") == mock_agent
        assert "test-agent" in [a["agent_id"] for a in registry.list_agents()]
        
    def test_agent_message(self):
        """Test agent message creation."""
        msg = AgentMessage(
            message_type=MessageType.REQUEST,
            sender_id="agent-1",
            recipient_id="agent-2",
            payload={"action": "analyze"}
        )
        
        data = msg.to_dict()
        assert data["sender_id"] == "agent-1"
        assert data["message_type"] == "request"


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipeline:
    """Tests for pipeline execution."""
    
    def test_pipeline_context(self):
        """Test pipeline context."""
        context = PipelineContext(
            pipeline_id="test-pipeline",
            case_id="CASE-001",
            scenario="Test scenario",
            report_type="technical",
            llm_provider="ollama",
            started_at=datetime.now(timezone.utc)
        )
        
        data = context.to_dict()
        assert data["case_id"] == "CASE-001"
        assert data["pipeline_id"] == "test-pipeline"
        
    def test_pipeline_stages(self):
        """Test pipeline stage enum."""
        stages = list(PipelineStage)
        
        assert PipelineStage.INITIALIZATION in stages
        assert PipelineStage.HYPOTHESIS_ANALYSIS in stages
        assert PipelineStage.EVIDENCE_COLLECTION in stages
        assert PipelineStage.CONFIDENCE_SCORING in stages
        assert PipelineStage.SUMMARY_SYNTHESIS in stages


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """Integration tests (require LLM connection)."""
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="Requires LLM connection")
    async def test_full_pipeline(self, sample_scenario):
        """Test full pipeline execution."""
        executor = PipelineExecutor(llm_provider="ollama")
        
        context = await executor.execute(
            case_id="TEST-001",
            scenario=sample_scenario,
            report_type="technical"
        )
        
        assert context.pipeline_id is not None
        assert len(context.hypotheses) > 0
        assert context.confidence_scores.get("overall_confidence", 0) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
