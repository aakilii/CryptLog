"""
Deep Research Module for NFLIP Investigation Assistant.

Implements:
- ThoughtNode: Individual reasoning step
- ThoughtTree: Hierarchical thought structure
- ThoughtEngine: Streaming thought generation
- PlanModels: Investigation plan data structures
- PlanManager: Plan CRUD and approval workflow
- HumanLoopManager: Human-in-loop question management
- ReportBuilder: Hybrid report generation
- DeepResearchOrchestrator: Main orchestrator
- AnalysisIntegration: Module integration
- ProgressTracker: Real-time progress tracking
- WebSocketManager: Real-time communication
- DemoScenarioGenerator: Demo data generation
- HypothesisReportBinder: Auto-generate report from findings
- StudioV4Integration: Connect to Report Canvas
"""

from .models import ThoughtNode, ThoughtTree, ThoughtType, ThoughtStatus
from .engine import ThoughtEngine
from .plan_models import (
    InvestigationPlan,
    PlanPhase,
    PlanStep,
    PlanStatus,
    StepType,
)
from .plan_manager import PlanManager, PlanCommand, get_plan_manager
from .human_loop import (
    HumanQuestion,
    HumanLoopManager,
    QuestionPriority,
    get_hil_manager,
)
from .report_builder import (
    ReportSection,
    ReportStructure,
    ReportBuilder,
    SectionType,
    SectionStatus,
    get_report_builder,
)
from .orchestrator import (
    DeepResearchOrchestrator,
    InvestigationContext,
    OrchestrationPhase,
    get_orchestrator,
)
from .analysis_integration import (
    AnalysisIntegration,
    AnalysisResult,
)
from .progress_tracker import (
    ProgressTracker,
    ProgressStatus,
    get_tracker,
)
from .websocket_manager import (
    WebSocketManager,
    get_ws_manager,
)
from .demo_scenario import (
    DemoScenarioGenerator,
    generate_demo_scenario,
)
from .hypothesis_report_binder import (
    HypothesisReportBinder,
    HypothesisFinding,
    EvidenceReference,
    ReportSectionType,
    bind_hypothesis_to_report,
)
from .studio_v4_integration import (
    StudioV4Integration,
    CanvasElement,
    CanvasPage,
    create_report_from_findings,
)
from .llm_hypothesis_generator import (
    LLMHypothesisGenerator,
    GeneratedHypothesis,
    get_hypothesis_generator,
)
from .report_version_control import (
    ReportVersionControl,
    ReportVersion,
    ReportChange,
    ChangeType,
    get_version_control,
)

__all__ = [
    # Thought models
    "ThoughtNode",
    "ThoughtTree",
    "ThoughtType",
    "ThoughtStatus",
    "ThoughtEngine",
    # Plan models
    "InvestigationPlan",
    "PlanPhase",
    "PlanStep",
    "PlanStatus",
    "StepType",
    # Plan management
    "PlanManager",
    "PlanCommand",
    "get_plan_manager",
    # Human-in-loop
    "HumanQuestion",
    "HumanLoopManager",
    "QuestionPriority",
    "get_hil_manager",
    # Report builder
    "ReportSection",
    "ReportStructure",
    "ReportBuilder",
    "SectionType",
    "SectionStatus",
    "get_report_builder",
    # Orchestrator
    "DeepResearchOrchestrator",
    "InvestigationContext",
    "OrchestrationPhase",
    "get_orchestrator",
    # Analysis integration
    "AnalysisIntegration",
    "AnalysisResult",
    # Progress tracking
    "ProgressTracker",
    "ProgressStatus",
    "get_tracker",
    # WebSocket
    "WebSocketManager",
    "get_ws_manager",
    # Demo
    "DemoScenarioGenerator",
    "generate_demo_scenario",
    # Hypothesis to Report binding
    "HypothesisReportBinder",
    "HypothesisFinding",
    "EvidenceReference",
    "ReportSectionType",
    "bind_hypothesis_to_report",
    # Studio V4 Integration
    "StudioV4Integration",
    "CanvasElement",
    "CanvasPage",
    "create_report_from_findings",
    # LLM Hypothesis Generator
    "LLMHypothesisGenerator",
    "GeneratedHypothesis",
    "get_hypothesis_generator",
    # Report Version Control
    "ReportVersionControl",
    "ReportVersion",
    "ReportChange",
    "ChangeType",
    "get_version_control",
]
