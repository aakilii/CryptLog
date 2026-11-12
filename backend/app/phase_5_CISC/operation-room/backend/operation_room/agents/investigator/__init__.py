"""
NFLIP Investigation Agent
==========================

Core investigation agent that orchestrates forensic analysis using MCP tools.

This agent follows the principle: "AI reasons about evidence, never generates it."

Components:
- InvestigationAgent: Main agent orchestrating investigation workflow
- PlanningEngine: State machine for investigation phases  
- HypothesisTree: BFS/DFS hypothesis exploration
- SummaryGenerator: Evidence-backed summary cards

Author: NFLIP Development Team
Version: 1.0.0
"""

from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
from typing import Any, Dict, List, Optional

from .agent import InvestigationAgent, AgentState, AgentConfig, AgentPhase, AgentMode


try:
    _planner_module = import_module(f"{__name__}.planner")
    PlanningEngine = _planner_module.PlanningEngine
    InvestigationPhase = _planner_module.InvestigationPhase
    PhaseTransition = _planner_module.PhaseTransition
    PhaseConfig = _planner_module.PhaseConfig
    PhaseStatus = _planner_module.PhaseStatus
except ModuleNotFoundError:
    class PhaseStatus(str, Enum):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETE = "complete"


    class InvestigationPhase(str, Enum):
        CLARIFICATION = "clarification"
        PLANNING = "planning"
        ANALYSIS = "analysis"
        REPORTING = "reporting"


    @dataclass
    class PhaseConfig:
        phase_id: str
        phase: InvestigationPhase
        status: PhaseStatus = PhaseStatus.PENDING


    @dataclass
    class PhaseTransition:
        from_phase: InvestigationPhase
        to_phase: InvestigationPhase
        condition: str = ""


    class PlanningEngine:
        """Lightweight compatibility fallback when planner module is unavailable."""

        def __init__(self, investigation_id: str):
            self.investigation_id = investigation_id
            self.phases: List[PhaseConfig] = []

        def create_plan_from_scenario(self, scenario: str, case_type: str = "general") -> List[PhaseConfig]:
            self.phases = [
                PhaseConfig("phase-clarification", InvestigationPhase.CLARIFICATION),
                PhaseConfig("phase-planning", InvestigationPhase.PLANNING),
                PhaseConfig("phase-analysis", InvestigationPhase.ANALYSIS),
                PhaseConfig("phase-reporting", InvestigationPhase.REPORTING),
            ]
            return self.phases

        def get_next_executable_phase(self) -> Optional[PhaseConfig]:
            for phase in self.phases:
                if phase.status != PhaseStatus.COMPLETE:
                    return phase
            return None

        def is_complete(self) -> bool:
            return bool(self.phases) and all(p.status == PhaseStatus.COMPLETE for p in self.phases)


try:
    _hypothesis_module = import_module(f"{__name__}.hypothesis_tree")
    HypothesisTree = _hypothesis_module.HypothesisTree
    HypothesisNode = _hypothesis_module.HypothesisNode
    TraversalStrategy = _hypothesis_module.TraversalStrategy
    HypothesisStatus = _hypothesis_module.HypothesisStatus
    HypothesisType = _hypothesis_module.HypothesisType
except ModuleNotFoundError:
    class TraversalStrategy(str, Enum):
        BFS = "bfs"
        DFS = "dfs"


    class HypothesisStatus(str, Enum):
        PROPOSED = "proposed"
        TESTED = "tested"


    class HypothesisType(str, Enum):
        ROOT = "root"
        CHILD = "child"


    @dataclass
    class HypothesisNode:
        node_id: str
        statement: str
        node_type: HypothesisType = HypothesisType.ROOT
        status: HypothesisStatus = HypothesisStatus.PROPOSED
        children: List[str] = field(default_factory=list)


    class HypothesisTree:
        """Lightweight compatibility fallback when hypothesis_tree module is unavailable."""

        def __init__(self, investigation_id: str):
            self.investigation_id = investigation_id
            self._nodes: Dict[str, HypothesisNode] = {}

        def add_root_hypothesis(self, node_id: str, statement: str) -> HypothesisNode:
            node = HypothesisNode(node_id=node_id, statement=statement, node_type=HypothesisType.ROOT)
            self._nodes[node_id] = node
            return node

        def get_node(self, node_id: str) -> Optional[HypothesisNode]:
            return self._nodes.get(node_id)


try:
    _summary_module = import_module(f"{__name__}.summary")
    SummaryGenerator = _summary_module.SummaryGenerator
    SummaryCard = _summary_module.SummaryCard
    SummaryType = _summary_module.SummaryType
    CitedFact = _summary_module.CitedFact
    Severity = _summary_module.Severity
    ConfidenceLevel = _summary_module.ConfidenceLevel
except ModuleNotFoundError:
    class SummaryType(str, Enum):
        FINDING = "finding"
        TIMELINE = "timeline"


    class Severity(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"


    class ConfidenceLevel(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"


    @dataclass
    class CitedFact:
        text: str
        evidence_id: str


    @dataclass
    class SummaryCard:
        summary_type: SummaryType
        title: str
        facts: List[CitedFact] = field(default_factory=list)
        severity: Severity = Severity.LOW
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


    class SummaryGenerator:
        """Lightweight compatibility fallback when summary module is unavailable."""

        def __init__(self, investigation_id: str):
            self.investigation_id = investigation_id

        def generate_finding_card(self, title: str, facts: Optional[List[Dict[str, Any]]] = None) -> SummaryCard:
            cited = [
                CitedFact(text=str(f.get("text", "")), evidence_id=str(f.get("evidence_id", "")))
                for f in (facts or [])
            ]
            return SummaryCard(summary_type=SummaryType.FINDING, title=title, facts=cited)

        def generate_timeline_card(self, title: str, facts: Optional[List[Dict[str, Any]]] = None) -> SummaryCard:
            cited = [
                CitedFact(text=str(f.get("text", "")), evidence_id=str(f.get("evidence_id", "")))
                for f in (facts or [])
            ]
            return SummaryCard(summary_type=SummaryType.TIMELINE, title=title, facts=cited)

__all__ = [
    # Core Agent
    "InvestigationAgent",
    "AgentState",
    "AgentConfig",
    "AgentPhase",
    "AgentMode",
    
    # Planning Engine
    "PlanningEngine",
    "InvestigationPhase",
    "PhaseTransition",
    "PhaseConfig",
    "PhaseStatus",
    
    # Hypothesis Tree
    "HypothesisTree",
    "HypothesisNode",
    "TraversalStrategy",
    "HypothesisStatus",
    "HypothesisType",
    
    # Summary Generator
    "SummaryGenerator",
    "SummaryCard",
    "SummaryType",
    "CitedFact",
    "Severity",
    "ConfidenceLevel",
]
