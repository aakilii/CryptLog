"""
NFLIP Multi-Agent Report Automation System

A hierarchical multi-agent architecture for automated forensic report generation.
This system transforms the manual Report Studio workflow into an intelligent,
automated pipeline that:

1. Analyzes hypothesis scenarios
2. Collects and evaluates evidence across modules
3. Computes confidence scores using multi-factor analysis
4. Synthesizes comprehensive forensic reports

Architecture Overview:
─────────────────────────────────────────────────────────────────────────────────
                         ┌─────────────────────────────┐
                         │   PIPELINE EXECUTOR         │
                         │   (Orchestration &          │
                         │    Agent Coordination)      │
                         └─────────────┬───────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         │                             │                             │
         ▼                             ▼                             ▼
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   HYPOTHESIS    │         │    EVIDENCE     │         │     MODULE      │
│    ANALYSIS     │         │   COLLECTION    │         │   EVALUATORS    │
│     AGENT       │         │     AGENT       │         │    (6 Agents)   │
└────────┬────────┘         └────────┬────────┘         └────────┬────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────────┐
                         │   CONFIDENCE SCORING        │
                         │        AGENT                │
                         │  (Multi-Factor Analysis)    │
                         └─────────────┬───────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │   SUMMARY SYNTHESIS         │
                         │        AGENT                │
                         │ (Report Generation + NLG)   │
                         └─────────────────────────────┘
─────────────────────────────────────────────────────────────────────────────────

Research Integration:
- 120+ research methodologies integrated across forensic domains
- Evidence-backed confidence scoring (ODNI ICD 203)
- MITRE ATT&CK framework alignment
- SHAP explainability for ML decisions

Author: NFLIP Development Team
Version: 2.0.0  # Updated: Consolidated architecture
"""

# Core base classes
from operation_room.agents.base import (
    BaseAgent,
    AgentRegistry,
    AgentMessage,
    AgentMetrics,
    AgentStatus,
    MessageType,
    registry,
)

# Specialized agents (no more MasterOrchestrator - consolidated into PipelineExecutor)
from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
from operation_room.agents.evidence.evidence_collector import EvidenceCollectionAgent
from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent
from operation_room.agents.synthesis.synthesis_agent import SummarySynthesisAgent

# Research knowledge base
from operation_room.agents.research.knowledge_base import (
    ResearchKnowledgeBase,
    ResearchMethodology,
    ResearchCategory,
    knowledge_base,
)

# Integration layer (primary orchestration)
from operation_room.agents.integration_layer import (
    PipelineExecutor,
    PipelineContext,
    PipelineStage,
    StageResult,
    MessageBroker,
    ResultAggregator,
    RetryHandler,
    broker,
    aggregator,
    retry_handler,
)

__all__ = [
    # Base classes
    "BaseAgent",
    "AgentRegistry",
    "AgentMessage",
    "AgentMetrics",
    "AgentStatus",
    "MessageType",
    "registry",
    
    # Specialized agents
    "HypothesisAnalysisAgent",
    "EvidenceCollectionAgent",
    "ConfidenceScoringAgent",
    "SummarySynthesisAgent",
    
    # Research knowledge
    "ResearchKnowledgeBase",
    "ResearchMethodology",
    "ResearchCategory",
    "knowledge_base",
    
    # Integration layer
    "PipelineExecutor",
    "PipelineContext",
    "PipelineStage",
    "StageResult",
    "MessageBroker",
    "ResultAggregator",
    "RetryHandler",
    "broker",
    "aggregator",
    "retry_handler",
]
