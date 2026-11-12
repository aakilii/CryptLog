"""
End-to-End Workflow Test for Deep Research.

Tests the complete investigation workflow from scenario to report:
1. Start investigation with demo scenario
2. Run through all phases
3. Generate report
4. Verify all components work together
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service."""
    mock = MagicMock()
    mock.generate = AsyncMock(return_value=MagicMock(
        content='{"entities": {"devices": ["DESKTOP-JXK92M", "Samsung Galaxy S23"], "users": ["John Smith"]}, "actions": ["file_copy", "bluetooth_transfer", "email"], "channels": ["USB", "Bluetooth", "Email"], "missing_information": []}'
    ))
    mock.generate_stream = AsyncMock()
    return mock


@pytest.fixture
def demo_scenario():
    """Get demo scenario data."""
    from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
    return generate_demo_scenario()


# ============================================================================
# Demo Scenario Tests
# ============================================================================

class TestDemoScenario:
    """Test demo scenario generation."""
    
    def test_generate_demo_scenario(self):
        """Test that demo scenario generates valid data."""
        from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
        
        scenario = generate_demo_scenario()
        
        assert "scenario" in scenario
        assert "suspect" in scenario
        assert "victim_system" in scenario
        assert "events" in scenario
        assert "evidence" in scenario
        
        # Check event count
        assert len(scenario["events"]) > 20
        
        # Check evidence items
        assert len(scenario["evidence"]) >= 3
        
        # Check timeline summary
        assert "total_events" in scenario["timeline_summary"]
        assert scenario["timeline_summary"]["severity_breakdown"]["critical"] > 0
    
    def test_scenario_contains_exfiltration_events(self):
        """Test that scenario contains expected exfiltration events."""
        from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
        
        scenario = generate_demo_scenario()
        
        # Check for USB events
        usb_events = [e for e in scenario["events"] if e["type"] == "usb_device"]
        assert len(usb_events) >= 2  # Connect and disconnect
        
        # Check for file copy events
        copy_events = [e for e in scenario["events"] if e["type"] == "file_copy"]
        assert len(copy_events) >= 3
        
        # Check for Bluetooth events
        bt_events = [e for e in scenario["events"] if "bluetooth" in e["type"]]
        assert len(bt_events) >= 4
        
        # Check for email events
        email_events = [e for e in scenario["events"] if e["type"] == "email_sent"]
        assert len(email_events) >= 2
    
    def test_scenario_has_hashes(self):
        """Test that all events have SHA-256 hashes."""
        from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
        
        scenario = generate_demo_scenario()
        
        for event in scenario["events"]:
            assert "hash" in event
            assert len(event["hash"]) == 64  # SHA-256 hex length


# ============================================================================
# Analysis Integration Tests
# ============================================================================

class TestAnalysisIntegration:
    """Test analysis module integration."""
    
    def test_create_integration(self):
        """Test creating analysis integration."""
        from operation_room.services.deep_research.analysis_integration import AnalysisIntegration
        
        integration = AnalysisIntegration("test-case-001")
        
        assert integration.case_id == "test-case-001"
        assert integration.get_results() == []
    
    def test_store_result(self):
        """Test storing analysis results."""
        from operation_room.services.deep_research.analysis_integration import (
            AnalysisIntegration,
            AnalysisResult,
        )
        
        integration = AnalysisIntegration("test-case-002")
        
        result = AnalysisResult(
            module_name="timeline",
            success=True,
            data={"event_count": 100},
            confidence=0.9,
        )
        
        integration._store_result("timeline", result)
        
        results = integration.get_results("timeline")
        assert len(results) == 1
        assert results[0].module_name == "timeline"
        assert results[0].confidence == 0.9
    
    def test_compute_overall_confidence(self):
        """Test overall confidence computation."""
        from operation_room.services.deep_research.analysis_integration import (
            AnalysisIntegration,
            AnalysisResult,
        )
        
        integration = AnalysisIntegration("test-case-003")
        
        # Add multiple results
        integration._store_result("timeline", AnalysisResult(
            module_name="timeline", success=True, confidence=0.9
        ))
        integration._store_result("anomaly", AnalysisResult(
            module_name="anomaly", success=True, confidence=0.8
        ))
        integration._store_result("correlation", AnalysisResult(
            module_name="correlation", success=True, confidence=0.7
        ))
        
        confidence = integration.compute_overall_confidence()
        
        assert 0.7 < confidence < 0.9
        assert abs(confidence - 0.8) < 0.01  # Should be ~0.8


# ============================================================================
# Progress Tracker Tests
# ============================================================================

class TestProgressTracker:
    """Test progress tracking."""
    
    def test_create_tracker(self):
        """Test creating progress tracker."""
        from operation_room.services.deep_research.progress_tracker import ProgressTracker
        
        tracker = ProgressTracker("test-inv-001")
        
        assert tracker.investigation_id == "test-inv-001"
        assert len(tracker.phases) == 7  # Default phases
    
    def test_start_and_complete_phase(self):
        """Test phase lifecycle."""
        from operation_room.services.deep_research.progress_tracker import (
            ProgressTracker,
            ProgressStatus,
        )
        
        tracker = ProgressTracker("test-inv-002")
        tracker.start()
        
        # Start intake phase
        tracker.start_phase("intake")
        
        assert tracker.phases["intake"].status == ProgressStatus.RUNNING
        assert tracker.current_phase == "intake"
        
        # Complete phase
        tracker.complete_phase("intake")
        
        assert tracker.phases["intake"].status == ProgressStatus.COMPLETED
    
    def test_step_tracking(self):
        """Test step-level tracking."""
        from operation_room.services.deep_research.progress_tracker import (
            ProgressTracker,
            ProgressStatus,
        )
        
        tracker = ProgressTracker("test-inv-003")
        tracker.start()
        tracker.start_phase("intake")
        
        # Start step
        tracker.start_step("intake_parse_scenario")
        
        phase = tracker.phases["intake"]
        step = next(s for s in phase.steps if s.id == "intake_parse_scenario")
        
        assert step.status == ProgressStatus.RUNNING
        
        # Complete step
        tracker.complete_step("intake_parse_scenario", output={"parsed": True})
        
        assert step.status == ProgressStatus.COMPLETED
    
    def test_progress_calculation(self):
        """Test progress percentage calculation."""
        from operation_room.services.deep_research.progress_tracker import ProgressTracker
        
        tracker = ProgressTracker("test-inv-004")
        tracker.start()
        
        # Complete some steps
        tracker.start_phase("intake")
        for step in tracker.phases["intake"].steps:
            tracker.start_step(step.id)
            tracker.complete_step(step.id)
        tracker.complete_phase("intake")
        
        # Check progress
        assert tracker.phases["intake"].progress == 1.0
        assert tracker.overall_progress > 0


# ============================================================================
# WebSocket Manager Tests
# ============================================================================

class TestWebSocketManager:
    """Test WebSocket manager."""
    
    def test_create_manager(self):
        """Test creating WebSocket manager."""
        from operation_room.services.deep_research.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        
        assert manager.get_client_count() == 0
    
    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting to investigation."""
        from operation_room.services.deep_research.websocket_manager import WebSocketManager
        
        manager = WebSocketManager()
        
        # No clients - should return 0
        sent = await manager.broadcast_to_investigation("test-inv", {"test": "data"})
        assert sent == 0


# ============================================================================
# Full Orchestration Tests
# ============================================================================

class TestFullOrchestration:
    """Test complete orchestration workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, mock_llm_service):
        """Test complete investigation workflow."""
        from operation_room.services.deep_research import (
            DeepResearchOrchestrator,
            OrchestrationPhase,
        )
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm_service)
        
        # Start investigation
        context = await orchestrator.start_investigation(
            case_id="E2E-TEST-001",
            scenario="Test scenario for end-to-end testing",
            objectives=["Test objective 1", "Test objective 2"],
            mode="focused",
        )
        
        assert context.investigation_id
        assert context.phase == OrchestrationPhase.INTAKE
        
        # Run intake
        intake_result = await orchestrator.run_phase_intake(context.investigation_id)
        assert intake_result["phase"] == "intake"
        
        # Run clarification
        clarify_result = await orchestrator.run_phase_clarification(context.investigation_id)
        assert "questions" in clarify_result
        
        # Run planning
        plan_result = await orchestrator.run_phase_planning(context.investigation_id)
        assert "plan" in plan_result
        
        # Get status
        status = orchestrator.get_status(context.investigation_id)
        assert status["investigation_id"] == context.investigation_id
        assert status["plan_progress"] is not None
    
    @pytest.mark.asyncio
    async def test_workflow_with_demo_scenario(self, mock_llm_service, demo_scenario):
        """Test workflow with demo scenario data."""
        from operation_room.services.deep_research import DeepResearchOrchestrator
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm_service)
        
        # Start with demo scenario
        context = await orchestrator.start_investigation(
            case_id="DEMO-E2E-001",
            scenario=demo_scenario["scenario"],
            objectives=[
                "Establish timeline of file transfers",
                "Identify all IP addresses",
            ],
            mode="focused",
        )
        
        assert context.case_id == "DEMO-E2E-001"
        
        # Run intake with actual scenario
        intake_result = await orchestrator.run_phase_intake(context.investigation_id)
        
        # Should have parsed scenario
        assert intake_result["phase"] == "intake"


# ============================================================================
# Report Generation Tests
# ============================================================================

class TestReportGeneration:
    """Test report generation in workflow."""
    
    @pytest.mark.asyncio
    async def test_report_generation(self, mock_llm_service):
        """Test report generation after investigation."""
        from operation_room.services.deep_research import (
            DeepResearchOrchestrator,
            get_report_builder,
        )
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm_service)
        
        # Start investigation
        context = await orchestrator.start_investigation(
            case_id="REPORT-TEST-001",
            scenario="Test scenario for report generation",
        )
        
        # Run through to reporting
        await orchestrator.run_phase_intake(context.investigation_id)
        await orchestrator.run_phase_clarification(context.investigation_id)
        plan_result = await orchestrator.run_phase_planning(context.investigation_id)
        
        # Approve plan
        from operation_room.services.deep_research import get_plan_manager
        plan_manager = get_plan_manager()
        if context.plan_id:
            plan_manager.approve_plan(context.plan_id, "test")
        
        # Generate report
        report_result = await orchestrator.run_phase_reporting(context.investigation_id)
        
        assert "report_structure" in report_result
        assert report_result["report_structure"]["sections"]
    
    def test_report_toc_generation(self):
        """Test Table of Contents generation."""
        from operation_room.services.deep_research import get_report_builder
        
        builder = get_report_builder()
        
        structure = builder.create_structure(
            investigation_id="TOC-TEST-001",
            title="Test Report",
            template="detailed",
        )
        
        toc = builder.generate_toc(structure.id)
        
        assert toc
        assert "Title Page" in toc
        assert "Table of Contents" in toc
        assert "Executive Summary" in toc


# ============================================================================
# Integration with Existing Modules
# ============================================================================

class TestModuleIntegration:
    """Test integration with existing analysis modules."""
    
    def test_analysis_result_serialization(self):
        """Test AnalysisResult can be serialized."""
        from operation_room.services.deep_research.analysis_integration import AnalysisResult
        
        result = AnalysisResult(
            module_name="timeline",
            success=True,
            data={"events": [{"id": 1}, {"id": 2}]},
            evidence_refs=["ev-001", "ev-002"],
            confidence=0.95,
            duration_ms=1234,
        )
        
        as_dict = result.to_dict()
        
        assert as_dict["module_name"] == "timeline"
        assert as_dict["success"] is True
        assert len(as_dict["evidence_refs"]) == 2
        assert as_dict["confidence"] == 0.95
    
    def test_evidence_ref_collection(self):
        """Test collecting all evidence references."""
        from operation_room.services.deep_research.analysis_integration import (
            AnalysisIntegration,
            AnalysisResult,
        )
        
        integration = AnalysisIntegration("test-case-005")
        
        # Add results with evidence
        integration._store_result("timeline", AnalysisResult(
            module_name="timeline",
            success=True,
            evidence_refs=["ev-001", "ev-002"],
        ))
        integration._store_result("anomaly", AnalysisResult(
            module_name="anomaly",
            success=True,
            evidence_refs=["ev-002", "ev-003"],  # ev-002 duplicate
        ))
        
        all_refs = integration.get_all_evidence_refs()
        
        # Should dedupe
        assert len(all_refs) == 3
        assert "ev-001" in all_refs
        assert "ev-002" in all_refs
        assert "ev-003" in all_refs


# ============================================================================
# API Route Tests
# ============================================================================

class TestAPIRoutes:
    """Test API routes work correctly."""
    
    def test_routes_registered(self):
        """Test all expected routes are registered."""
        from operation_room.routes.deep_research import router
        
        routes = [r.path for r in router.routes]
        
        # Check key routes (with prefix)
        assert "/deep-research/orchestrator/start" in routes
        assert "/deep-research/demo/scenario" in routes
        assert "/deep-research/demo/run" in routes
        assert "/deep-research/ws/status" in routes
    
    def test_demo_scenario_endpoint(self):
        """Test demo scenario endpoint returns valid data."""
        from operation_room.services.deep_research.demo_scenario import generate_demo_scenario
        
        scenario = generate_demo_scenario()
        
        # Verify structure matches what API would return
        assert isinstance(scenario["events"], list)
        assert isinstance(scenario["evidence"], list)
        assert "scenario" in scenario


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
