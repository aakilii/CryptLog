"""
MCP Tools Package — Individual tool implementations.

This package contains all MCP tool implementations organized by category:

    investigation.py    - Investigation lifecycle tools
    clarification.py    - User clarification workflow
    planning.py         - Investigation planning
    hypothesis.py       - Hypothesis management & confidence scoring
    evidence.py         - Evidence Vault with hash verification
    timeline.py         - Timeline analysis with anchor marking
    analysis.py         - All analysis module wrappers (anomaly, correlation, CRUD, network, depth)
    
    (Future phases)
    canvas.py           - Report canvas tools
    narrative.py        - AI narrative generation
    citation.py         - Citation management
    export.py           - Report export

Each tool follows the MCP protocol and uses the @mcp_tool decorator
for registration.

Usage:
    # Tools are auto-registered when imported
    from operation_room.mcp.tools import investigation, clarification, planning
    
    # Or import specific tools
    from operation_room.mcp.tools.investigation import start_investigation

Author: NFLIP Development Team
Version: 1.0.0
"""

# Investigation lifecycle tools
from .investigation import (
    ScenarioParser,
    DataSourceDiscovery,
    InvestigationStore,
    start_investigation,
    get_investigation_context,
    manage_investigation_sources,
    list_investigations,
    enum_value,
)

# Clarification workflow tools
from .clarification import (
    AnswerValidator,
    ClarificationProcessor,
    answer_clarification,
    add_clarification_question,
    validate_investigation,
    list_clarification_questions,
)

# Planning tools
from .planning import (
    PlanStore,
    PlanGenerator,
    PlanExecutor,
    generate_investigation_plan,
    get_investigation_plan,
    approve_plan_steps,
    execute_plan_step,
)

# Hypothesis and confidence tools
from .hypothesis import (
    HypothesisStore,
    ConfidenceStore,
    HypothesisGenerator,
    HypothesisTester,
    ConfidenceCalculator,
    generate_hypotheses,
    create_hypothesis,
    test_hypotheses,
    get_hypothesis_tree,
    compute_confidence,
)

# Evidence Vault tools
from .evidence import (
    EvidenceVault,
    EvidenceFactory,
    EvidenceCategory,
    AnchorType,
    EvidenceItem,
    EvidenceSnapshot,
    EvidenceCitation,
    anchor_evidence,
    query_evidence,
    create_evidence_snapshot,
    verify_evidence,
    cite_evidence,
    link_evidence,
    get_evidence_stats,
    get_evidence,
)

# Timeline tools
from .timeline import (
    TimelineAnchorManager,
    build_timeline,
    query_timeline,
    anchor_timeline_event,
    list_timeline_anchors,
    get_timeline_stats,
    visualize_timeline,
)

# Analysis module wrappers
from .analysis import (
    detect_anomalies,
    vault_anomaly,
    build_correlation,
    vault_correlation,
    analyze_crud,
    analyze_network,
    vault_network,
    analyze_depth,
    run_full_analysis,
)

# Report generation tools
from .report import (
    DocumentStatus,
    SectionType,
    ElementType,
    NarrativeStyle,
    ExportFormat,
    CanvasPosition,
    CanvasElement,
    CanvasPage,
    ReportDocument,
    ReportStore,
    create_report_document,
    get_report_document,
    list_report_documents,
    update_document_status,
    add_canvas_page,
    add_canvas_element,
    add_evidence_block,
    get_canvas_page,
    reorder_canvas_pages,
    generate_narrative,
    insert_narrative_to_canvas,
    validate_report,
    export_report,
    list_exports,
    build_report_from_investigation,
    get_report_summary,
)

# LLM integration tools
from .llm import (
    LLMConfig,
    GeminiClient,
    GenerationRequest,
    GenerationResponse,
    generate_text,
    generate_report_section,
    fact_check_content,
    analyze_content,
    summarize_content,
    configure_llm,
    get_llm_status,
)


__all__ = [
    # Investigation
    "ScenarioParser",
    "DataSourceDiscovery",
    "InvestigationStore",
    "start_investigation",
    "get_investigation_context",
    "manage_investigation_sources",
    "list_investigations",
    "enum_value",
    
    # Clarification
    "AnswerValidator",
    "ClarificationProcessor",
    "answer_clarification",
    "add_clarification_question",
    "validate_investigation",
    "list_clarification_questions",
    
    # Planning
    "PlanStore",
    "PlanGenerator",
    "PlanExecutor",
    "generate_investigation_plan",
    "get_investigation_plan",
    "approve_plan_steps",
    "execute_plan_step",
    
    # Hypothesis
    "HypothesisStore",
    "ConfidenceStore",
    "HypothesisGenerator",
    "HypothesisTester",
    "ConfidenceCalculator",
    "generate_hypotheses",
    "create_hypothesis",
    "test_hypotheses",
    "get_hypothesis_tree",
    "compute_confidence",
    
    # Evidence Vault
    "EvidenceVault",
    "EvidenceFactory",
    "EvidenceCategory",
    "AnchorType",
    "EvidenceItem",
    "EvidenceSnapshot",
    "EvidenceCitation",
    "anchor_evidence",
    "query_evidence",
    "create_evidence_snapshot",
    "verify_evidence",
    "cite_evidence",
    "link_evidence",
    "get_evidence_stats",
    "get_evidence",
    
    # Timeline
    "TimelineAnchorManager",
    "build_timeline",
    "query_timeline",
    "anchor_timeline_event",
    "list_timeline_anchors",
    "get_timeline_stats",
    "visualize_timeline",
    
    # Analysis
    "detect_anomalies",
    "vault_anomaly",
    "build_correlation",
    "vault_correlation",
    "analyze_crud",
    "analyze_network",
    "vault_network",
    "analyze_depth",
    "run_full_analysis",
    
    # Report
    "DocumentStatus",
    "SectionType",
    "ElementType",
    "NarrativeStyle",
    "ExportFormat",
    "CanvasPosition",
    "CanvasElement",
    "CanvasPage",
    "ReportDocument",
    "ReportStore",
    "create_report_document",
    "get_report_document",
    "list_report_documents",
    "update_document_status",
    "add_canvas_page",
    "add_canvas_element",
    "add_evidence_block",
    "get_canvas_page",
    "reorder_canvas_pages",
    "generate_narrative",
    "insert_narrative_to_canvas",
    "validate_report",
    "export_report",
    "list_exports",
    "build_report_from_investigation",
    "get_report_summary",
    
    # LLM
    "LLMConfig",
    "GeminiClient",
    "GenerationRequest",
    "GenerationResponse",
    "generate_text",
    "generate_report_section",
    "fact_check_content",
    "analyze_content",
    "summarize_content",
    "configure_llm",
    "get_llm_status",
]
