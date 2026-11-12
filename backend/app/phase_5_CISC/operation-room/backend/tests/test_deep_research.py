"""
Test Deep Research Orchestrator Integration.

Tests the complete investigation workflow including:
- Investigation initialization
- Phase execution
- Plan management
- Report generation
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# Test imports
def test_orchestrator_import():
    """Test that orchestrator imports correctly."""
    from operation_room.services.deep_research import (
        DeepResearchOrchestrator,
        InvestigationContext,
        OrchestrationPhase,
        get_orchestrator,
    )
    assert DeepResearchOrchestrator is not None
    assert InvestigationContext is not None
    assert OrchestrationPhase is not None
    assert get_orchestrator is not None


def test_llm_service_import():
    """Test that LLM service imports correctly."""
    from operation_room.services.llm import (
        LLMService,
        get_llm_service,
        Message,
        ProviderType,
    )
    assert LLMService is not None
    assert Message is not None
    assert ProviderType is not None


def test_report_builder_import():
    """Test that report builder imports correctly."""
    from operation_room.services.deep_research import (
        ReportBuilder,
        ReportSection,
        ReportStructure,
        SectionType,
        get_report_builder,
    )
    assert ReportBuilder is not None
    assert ReportSection is not None
    assert ReportStructure is not None
    assert SectionType is not None


def test_api_routes_import():
    """Test that API routes import correctly."""
    from operation_room.routes.deep_research import router
    assert router is not None
    
    # Check route count
    routes = [r for r in router.routes]
    assert len(routes) > 10, "Should have multiple routes"


class TestOrchestrator:
    """Test orchestrator functionality."""
    
    def test_create_orchestrator(self):
        """Test orchestrator creation."""
        from operation_room.services.deep_research import DeepResearchOrchestrator
        
        orchestrator = DeepResearchOrchestrator()
        assert orchestrator is not None
    
    @pytest.mark.asyncio
    async def test_start_investigation(self):
        """Test starting an investigation."""
        from operation_room.services.deep_research import DeepResearchOrchestrator, OrchestrationPhase
        
        # Create orchestrator with mock LLM
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(content="{}"))
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm)
        
        # Start investigation
        context = await orchestrator.start_investigation(
            case_id="test-case-001",
            scenario="Test scenario for investigation",
            objectives=["Find evidence", "Generate report"],
            mode="focused",
        )
        
        assert context.investigation_id is not None
        assert context.case_id == "test-case-001"
        assert context.scenario == "Test scenario for investigation"
        assert context.phase == OrchestrationPhase.INTAKE
    
    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting investigation status."""
        from operation_room.services.deep_research import DeepResearchOrchestrator
        
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(content="{}"))
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm)
        
        context = await orchestrator.start_investigation(
            case_id="test-case-002",
            scenario="Another test scenario",
        )
        
        status = orchestrator.get_status(context.investigation_id)
        
        assert status["investigation_id"] == context.investigation_id
        assert status["phase"] == "intake"


class TestReportBuilder:
    """Test report builder functionality."""
    
    def test_create_structure(self):
        """Test creating report structure."""
        from operation_room.services.deep_research import ReportBuilder, SectionType
        
        builder = ReportBuilder()
        
        structure = builder.create_structure(
            investigation_id="test-inv-001",
            title="Test Report",
            template="detailed",
        )
        
        assert structure.id is not None
        assert structure.investigation_id == "test-inv-001"
        assert structure.title == "Test Report"
        assert len(structure.sections) > 10  # Detailed template has many sections
    
    def test_fill_section(self):
        """Test filling a report section."""
        from operation_room.services.deep_research import ReportBuilder
        
        builder = ReportBuilder()
        
        structure = builder.create_structure(
            investigation_id="test-inv-002",
            title="Test Report",
            template="standard",
        )
        
        # Get first section
        first_section_id = structure.section_order[0]
        
        # Fill it
        section = builder.fill_section(
            structure_id=structure.id,
            section_id=first_section_id,
            content="Test content for section",
            evidence_refs=["ev-001", "ev-002"],
        )
        
        assert section is not None
        assert section.content.text == "Test content for section"
        assert len(section.content.evidence_refs) == 2
    
    def test_generate_toc(self):
        """Test TOC generation."""
        from operation_room.services.deep_research import ReportBuilder
        
        builder = ReportBuilder()
        
        structure = builder.create_structure(
            investigation_id="test-inv-003",
            title="Test Report",
            template="standard",
        )
        
        toc = builder.generate_toc(structure.id)
        
        assert toc is not None
        assert len(toc) > 0
        assert "Title Page" in toc


class TestPlanManager:
    """Test plan manager functionality."""
    
    def test_create_plan(self):
        """Test creating a plan."""
        from operation_room.services.deep_research import PlanManager
        
        manager = PlanManager()
        
        plan = manager.create_plan(
            investigation_id="test-inv-001",
            title="Test Investigation Plan",
            scenario_summary="Test scenario",
            objectives=["Objective 1", "Objective 2"],
        )
        
        assert plan.id is not None
        assert plan.investigation_id == "test-inv-001"
        assert plan.title == "Test Investigation Plan"
    
    def test_approve_plan(self):
        """Test approving a plan."""
        from operation_room.services.deep_research import PlanManager, PlanStatus
        
        manager = PlanManager()
        
        plan = manager.create_plan(
            investigation_id="test-inv-002",
            title="Test Plan",
        )
        
        manager.approve_plan(plan.id, "test-user")
        
        updated_plan = manager.get_plan(plan.id)
        assert updated_plan.status == PlanStatus.APPROVED


class TestHumanLoopManager:
    """Test human-in-loop manager functionality."""
    
    def test_create_question(self):
        """Test creating a question."""
        from operation_room.services.deep_research.human_loop import HumanLoopManager, QuestionPriority
        
        manager = HumanLoopManager()
        
        question = manager.create_question(
            question="What is the time range?",
            investigation_id="test-inv-001",
            priority=QuestionPriority.HIGH,
            options=["Last 24 hours", "Last 7 days", "Custom"],
        )
        
        assert question.id is not None
        assert question.question == "What is the time range?"
        assert question.priority == QuestionPriority.HIGH
        assert len(question.options) == 3
    
    def test_answer_question(self):
        """Test answering a question."""
        from operation_room.services.deep_research.human_loop import (
            HumanLoopManager,
            QuestionPriority,
            QuestionStatus,
        )
        
        manager = HumanLoopManager()
        
        question = manager.create_question(
            question="Test question?",
            investigation_id="test-inv-002",
            priority=QuestionPriority.MEDIUM,
        )
        
        result = manager.answer_question(question.id, "Test answer")
        
        assert result is not None  # Returns the question object
        assert question.answer == "Test answer"
        assert question.status == QuestionStatus.ANSWERED


class TestThoughtEngine:
    """Test thought engine functionality."""
    
    def test_create_tree(self):
        """Test creating a thought tree."""
        from operation_room.services.deep_research import ThoughtEngine
        
        engine = ThoughtEngine()
        tree = engine.create_tree("test-inv-001")
        
        assert tree.id is not None
        assert tree.investigation_id == "test-inv-001"
    
    @pytest.mark.asyncio
    async def test_create_thought(self):
        """Test creating a thought node."""
        from operation_room.services.deep_research import ThoughtEngine, ThoughtType
        
        engine = ThoughtEngine()
        tree = engine.create_tree("test-inv-002")
        
        thought = await engine.create_thought(
            tree=tree,
            title="Test thought",
            thought_type=ThoughtType.ANALYSIS,
            initial_content="Initial content",
        )
        
        assert thought.id is not None
        assert thought.title == "Test thought"
        assert thought.thought_type == ThoughtType.ANALYSIS


class TestIntegration:
    """Integration tests for the complete system."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_mock(self):
        """Test a complete workflow with mocked LLM."""
        from operation_room.services.deep_research import (
            DeepResearchOrchestrator,
            OrchestrationPhase,
        )
        
        # Create mock LLM
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(
            content='{"entities": {"devices": ["computer"], "users": ["suspect"]}, "missing_information": []}'
        ))
        
        orchestrator = DeepResearchOrchestrator(llm_service=mock_llm)
        
        # Start investigation
        context = await orchestrator.start_investigation(
            case_id="integration-test-001",
            scenario="A computer was seized containing evidence of data theft.",
            objectives=["Identify stolen data", "Build timeline"],
            mode="focused",
        )
        
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
        
        # Check status
        status = orchestrator.get_status(context.investigation_id)
        assert status["investigation_id"] == context.investigation_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
