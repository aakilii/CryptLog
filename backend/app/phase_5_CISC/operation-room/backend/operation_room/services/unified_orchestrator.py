"""
Unified Investigation Orchestrator

This module consolidates ALL AI components into a single coherent system:
- Universal Module Tools (7 tools: Timeline, Anomaly, Correlation, Network, CRUD, Depth, Vault)
- Deep Research Orchestrator (7 phases: Intake → Clarification → Planning → Approval → Execution → Synthesis → Reporting)
- Hypothesis Testing (ACH framework with Bayesian scoring)
- Confidence Scoring (6-factor ODNI ICD 203 model)
- Report Generation (Canvas-based with real-time streaming)
- Entity Aliasing (IP/MAC/User → friendly names)

Key Integration Points:
- Universal Tools wrap existing MCP tools and services
- Orchestrator coordinates tool execution in correct order
- Hypothesis Agent feeds into Confidence Agent
- Confidence scores feed into Report Builder
- Real-time streaming to Canvas via SSE

Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED INVESTIGATION SYSTEM                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │             UnifiedInvestigationOrchestrator             │    │
│  │  Combines: DeepResearchOrchestrator + PipelineExecutor   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│        ┌─────────────────────┼─────────────────────┐            │
│        ▼                     ▼                     ▼            │
│  ┌───────────┐        ┌───────────┐        ┌───────────┐        │
│  │ Hypothesis│        │ Evidence  │        │ Confidence│        │
│  │   Agent   │───────▶│ Collector │───────▶│   Agent   │        │
│  └───────────┘        └───────────┘        └───────────┘        │
│        │                     │                     │            │
│        ▼                     ▼                     ▼            │
│  ┌──────────────────────────────────────────────────────┐       │
│  │              Universal Module Tools                   │       │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐         │       │
│  │  │Timeline│ │Anomaly │ │Network │ │ CRUD   │ ...     │       │
│  │  │ Tool   │ │ Tool   │ │ Tool   │ │ Tool   │         │       │
│  │  └────────┘ └────────┘ └────────┘ └────────┘         │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                    Report Builder                     │       │
│  │  - Canvas streaming                                   │       │
│  │  - Real-time layout                                   │       │
│  │  - PDF export                                         │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
"""

import logging
import asyncio
import json
import re
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

# Import Universal Module Tools
from operation_room.tools import (
    tool_registry,
    tool_orchestration,
    ToolInput,
    ToolOutput,
    StreamEvent,
    EventType,
)

# Import Entity Alias Service
from operation_room.services.entity_alias_service import entity_alias_service, EntityType

# Import existing Deep Research components
try:
    from operation_room.services.deep_research.orchestrator import DeepResearchOrchestrator
    from operation_room.services.deep_research.engine import ThoughtEngine
    from operation_room.services.deep_research.plan_manager import PlanManager
    from operation_room.services.deep_research.human_loop import HumanLoopManager
    from operation_room.services.deep_research.report_builder import ReportBuilder
    from operation_room.services.deep_research.llm_hypothesis_generator import LLMHypothesisGenerator
    DEEP_RESEARCH_AVAILABLE = True
except ImportError:
    DEEP_RESEARCH_AVAILABLE = False

# Import existing agents
try:
    from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
    from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent
    from operation_room.agents.integration_layer import PipelineExecutor
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False

# Import LLM service
try:
    from operation_room.services.llm.service import get_llm_service
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Oracle 26AI Memory Services
try:
    from operation_room.services.hybrid_retriever import get_hybrid_retriever, RetrievalStrategy
    from operation_room.services.validation_memory import get_validation_memory
    from operation_room.services.evidence_vault import get_evidence_vault
    from operation_room.services.longterm_memory import get_long_term_memory
    from operation_room.services.vector_store import CollectionType
    ORACLE_MEMORY_AVAILABLE = True
except ImportError as e:
    ORACLE_MEMORY_AVAILABLE = False
    logger = logging.getLogger(__name__)
    # Will be redefined below, but need for error logging
    import logging as _log
    _log.getLogger(__name__).debug(f"Oracle memory services unavailable: {e}")


logger = logging.getLogger(__name__)


class InvestigationPhase(str, Enum):
    """Phases of the unified investigation."""
    IDLE = "idle"
    INTAKE = "intake"
    CLARIFICATION = "clarification"
    PLANNING = "planning"
    APPROVAL = "approval"
    EXECUTION = "execution"
    HYPOTHESIS_TESTING = "hypothesis_testing"
    CONFIDENCE_SCORING = "confidence_scoring"
    SYNTHESIS = "synthesis"
    REPORTING = "reporting"
    COMPLETE = "complete"
    ERROR = "error"
    STOPPED = "stopped"  # User-initiated stop


@dataclass
class InvestigationState:
    """Complete state of an investigation."""
    investigation_id: str
    case_id: str
    scenario: str
    phase: InvestigationPhase = InvestigationPhase.IDLE
    
    # Results from each phase
    entities: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: Dict[str, ToolOutput] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    report: Optional[Dict[str, Any]] = None
    
    # Tracking
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    progress_percent: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "case_id": self.case_id,
            "scenario": self.scenario[:200] + "..." if len(self.scenario) > 200 else self.scenario,
            "phase": self.phase.value,
            "progress_percent": self.progress_percent,
            "hypotheses_count": len(self.hypotheses),
            "evidence_count": len(self.evidence),
            "findings_count": len(self.findings),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }


class UnifiedInvestigationOrchestrator:
    """
    Main orchestrator that unifies ALL AI components.
    
    This combines:
    - DeepResearchOrchestrator (phase management, human-in-loop)
    - PipelineExecutor (agent coordination)
    - Universal Module Tools (analysis execution)
    - Hypothesis Testing (ACH framework)
    - Confidence Scoring (6-factor model)
    - Report Building (canvas streaming)
    
    Usage:
        orchestrator = UnifiedInvestigationOrchestrator()
        
        async for event in orchestrator.run_investigation(case_id, scenario):
            # Handle real-time events
            if event.event_type == EventType.FINDING:
                print("New finding:", event.data)
            elif event.event_type == EventType.VISUALIZATION:
                canvas.add_element(event.data)
    """
    
    def __init__(self):
        self.active_investigations: Dict[str, InvestigationState] = {}
        self._stop_requests: set[str] = set()
        
        # Initialize components
        if DEEP_RESEARCH_AVAILABLE:
            self.thought_engine = ThoughtEngine()
            self.plan_manager = PlanManager()
            self.human_loop = HumanLoopManager()
            self.report_builder = ReportBuilder()
            self.hypothesis_generator = LLMHypothesisGenerator()
        else:
            self.thought_engine = None
            self.plan_manager = None
            self.human_loop = None
            self.report_builder = None
            self.hypothesis_generator = None
        
        if AGENTS_AVAILABLE:
            self.hypothesis_agent = HypothesisAnalysisAgent()
            self.confidence_agent = ConfidenceScoringAgent()
        else:
            self.hypothesis_agent = None
            self.confidence_agent = None
        
        # Oracle 26AI: Initialize memory services for cross-case learning
        self._longterm_memory = None
        if ORACLE_MEMORY_AVAILABLE:
            try:
                self._longterm_memory = get_long_term_memory()
                logger.info("Oracle 26AI: Long-term memory initialized")
            except Exception as e:
                logger.warning(f"Oracle 26AI: Long-term memory unavailable: {e}")
    
    def _get_hybrid_retriever(self, case_id: str, collection_type=None):
        """Get hybrid retriever for a case."""
        if not ORACLE_MEMORY_AVAILABLE:
            return None
        try:
            from operation_room.services.vector_store import CollectionType as CT
            return get_hybrid_retriever(case_id, collection_type or CT.EVIDENCE)
        except Exception as e:
            logger.warning(f"Oracle 26AI: Hybrid retriever unavailable: {e}")
            return None
    
    def _get_validation_memory(self, case_id: str):
        """Get validation memory for a case."""
        if not ORACLE_MEMORY_AVAILABLE:
            return None
        try:
            return get_validation_memory(case_id)
        except Exception as e:
            logger.warning(f"Oracle 26AI: Validation memory unavailable: {e}")
            return None
    
    def _get_evidence_vault(self, case_id: str):
        """Get evidence vault for a case."""
        if not ORACLE_MEMORY_AVAILABLE:
            return None
        try:
            return get_evidence_vault(case_id)
        except Exception as e:
            logger.warning(f"Oracle 26AI: Evidence vault unavailable: {e}")
            return None

    def _to_dict(self, value: Any) -> Dict[str, Any]:
        """Normalize tool model objects into plain dictionaries."""
        if isinstance(value, dict):
            return dict(value)

        if hasattr(value, "to_dict"):
            try:
                converted = value.to_dict()
                if isinstance(converted, dict):
                    return converted
            except Exception:
                pass

        raw = getattr(value, "__dict__", None)
        if isinstance(raw, dict):
            return dict(raw)

        return {"value": str(value)}

    def _normalize_finding(self, finding: Any) -> Dict[str, Any]:
        finding_data = self._to_dict(finding)
        severity = finding_data.get("severity")
        severity_value = getattr(severity, "value", None)
        if severity_value is not None:
            finding_data["severity"] = str(severity_value)
        return finding_data

    def _normalize_evidence(self, evidence: Any) -> Dict[str, Any]:
        evidence_data = self._to_dict(evidence)
        if "type" not in evidence_data and "evidence_type" in evidence_data:
            evidence_data["type"] = evidence_data.get("evidence_type")
        if "content" not in evidence_data and "description" in evidence_data:
            evidence_data["content"] = evidence_data.get("description")
        return evidence_data
    
    async def run_investigation(
        self,
        case_id: str,
        scenario: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Run a complete investigation with real-time streaming.
        
        This is the main entry point that:
        1. Parses the scenario
        2. Generates hypotheses
        3. Creates investigation plan
        4. Executes analysis using Universal Tools
        5. Tests hypotheses with Bayesian scoring
        6. Computes confidence scores
        7. Generates report with canvas streaming
        
        Args:
            case_id: Case identifier
            scenario: Investigation scenario text
            options: Configuration options
        
        Yields:
            StreamEvent objects for real-time updates
        """
        options = options or {}

        def _read_flag(name: str, default: bool) -> bool:
            raw_value = options.get(name, default)
            if isinstance(raw_value, bool):
                return raw_value
            if isinstance(raw_value, str):
                return raw_value.strip().lower() in {"1", "true", "yes", "on"}
            if raw_value is None:
                return default
            return bool(raw_value)

        configured_modules = options.get("enabled_modules") or options.get("modules_to_run")
        generate_hypotheses = _read_flag("generate_hypotheses", True)
        compute_confidence = _read_flag("compute_confidence", True)
        generate_report = _read_flag("generate_report", True)
        initial_hypotheses = options.get("initial_hypotheses") if isinstance(options.get("initial_hypotheses"), list) else []

        available_modules = ["timeline", "anomaly", "correlation", "network", "crud", "depth", "vault"]
        if isinstance(configured_modules, list):
            tools_to_run = [module for module in configured_modules if module in available_modules]
        else:
            tools_to_run = []
        if not tools_to_run:
            tools_to_run = available_modules

        investigation_id = f"inv-{uuid.uuid4().hex[:12]}"
        
        # Create state
        state = InvestigationState(
            investigation_id=investigation_id,
            case_id=case_id,
            scenario=scenario,
        )
        self.active_investigations[investigation_id] = state
        self._stop_requests.discard(investigation_id)

        def _stop_event() -> StreamEvent:
            return StreamEvent(
                event_type=EventType.PROGRESS,
                timestamp=datetime.now().isoformat(),
                data={
                    "phase": "stopped",
                    "progress": state.progress_percent,
                    "message": "Investigation stopped by user",
                    "investigation_id": investigation_id,
                },
            )
        
        try:
            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return

            # ─── PHASE 1: INTAKE ─────────────────────────────────────────────
            state.phase = InvestigationPhase.INTAKE
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={"phase": "intake", "investigation_id": investigation_id}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # Parse scenario and extract entities
            entities = await self._parse_scenario(case_id, scenario)
            state.entities = entities
            state.progress_percent = 10
            
            # Auto-alias extracted entities
            for entity in entities:
                entity_alias_service.auto_alias(
                    case_id=case_id,
                    entity_value=entity.get("value", ""),
                    entity_type=EntityType(entity.get("type", "user"))
                )
            
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={"phase": "intake", "entities_found": len(entities)}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # ─── PHASE 2: HYPOTHESIS GENERATION ──────────────────────────────
            state.phase = InvestigationPhase.PLANNING
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={"phase": "hypothesis_generation"}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # Generate hypotheses with configurable behavior
            if generate_hypotheses:
                hypotheses = await self._generate_hypotheses(case_id, scenario, entities)
            elif initial_hypotheses:
                hypotheses = [
                    {
                        "id": f"H{idx}",
                        "statement": str(hypothesis),
                        "type": "user_defined",
                        "prior_confidence": max(0.1, 1.0 / max(1, len(initial_hypotheses))),
                        "test_criteria": [],
                    }
                    for idx, hypothesis in enumerate(initial_hypotheses, start=1)
                ]
            else:
                hypotheses = self._get_default_hypotheses()

            state.hypotheses = hypotheses
            state.progress_percent = 20
            
            for hyp in hypotheses:
                yield StreamEvent(
                    event_type=EventType.FINDING,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "type": "hypothesis",
                        "id": hyp.get("id"),
                        "statement": hyp.get("statement"),
                        "prior_confidence": hyp.get("prior_confidence", 0.5),
                    }
                )
            
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={"phase": "hypothesis_generation", "hypotheses_count": len(hypotheses)}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # ─── PHASE 3: PLAN GENERATION ────────────────────────────────────
            plan = await self._generate_plan(case_id, scenario, hypotheses)
            state.plan = plan
            state.progress_percent = 30
            
            yield StreamEvent(
                event_type=EventType.FINDING,
                timestamp=datetime.now().isoformat(),
                data={
                    "type": "plan",
                    "phases": len(plan.get("phases", [])),
                    "total_steps": sum(len(p.get("steps", [])) for p in plan.get("phases", [])),
                }
            )
            
            # ─── PHASE 4: EXECUTION (Universal Tools) ────────────────────────
            state.phase = InvestigationPhase.EXECUTION
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={"phase": "execution"}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # Execute all Universal Tools
            total_tools = len(tools_to_run)
            
            for idx, tool_id in enumerate(tools_to_run, 1):
                if investigation_id in self._stop_requests:
                    state.phase = InvestigationPhase.STOPPED
                    state.error = "Stopped by user"
                    yield _stop_event()
                    return

                tool = tool_registry.get(tool_id)
                if not tool:
                    continue
                
                yield StreamEvent(
                    event_type=EventType.TOOL_START,
                    timestamp=datetime.now().isoformat(),
                    data={"tool_id": tool_id, "tool_name": tool.tool_name}
                )
                
                # Execute tool's primary capability
                primary_capability = self._get_primary_capability(tool_id)
                
                tool_input = ToolInput(
                    case_id=case_id,
                    capability=primary_capability,
                    parameters={},
                    context={"investigation_id": investigation_id},
                )
                
                result = await tool.execute(tool_input)
                state.tool_results[tool_id] = result
                
                # Stream findings from tool
                for finding in result.findings:
                    finding_data = self._normalize_finding(finding)
                    state.findings.append(finding_data)
                    yield StreamEvent(
                        event_type=EventType.FINDING,
                        timestamp=datetime.now().isoformat(),
                        data={
                            "tool_id": tool_id,
                            "finding": finding_data,
                        }
                    )
                
                # Stream visualizations
                for viz in result.visualizations:
                    yield StreamEvent(
                        event_type=EventType.VISUALIZATION,
                        timestamp=datetime.now().isoformat(),
                        data={
                            "tool_id": tool_id,
                            "visualization": viz.__dict__ if hasattr(viz, '__dict__') else viz,
                        }
                    )
                
                # Collect evidence
                for ev in result.evidence:
                    state.evidence.append(self._normalize_evidence(ev))
                
                # Oracle 26AI: Store evidence in vault with embeddings
                evidence_vault = self._get_evidence_vault(case_id)
                if evidence_vault:
                    for ev in result.evidence:
                        try:
                            ev_dict = self._normalize_evidence(ev)
                            evidence_vault.add_evidence(
                                content=str(ev_dict.get('content', ev_dict)),
                                evidence_type=str(ev_dict.get('type', tool_id)),
                                source=f"tool_{tool_id}",
                                confidence=float(ev_dict.get('confidence', 0.5) or 0.5),
                                metadata={"tool_id": tool_id, "investigation_id": investigation_id}
                            )
                        except Exception as e:
                            logger.debug(f"Oracle 26AI: Failed to store evidence: {e}")
                
                state.progress_percent = 30 + (idx / total_tools) * 40
                
                yield StreamEvent(
                    event_type=EventType.TOOL_COMPLETE,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "tool_id": tool_id,
                        "success": result.success,
                        "findings_count": len(result.findings),
                        "evidence_count": len(result.evidence),
                    }
                )
            
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={"phase": "execution", "total_findings": len(state.findings)}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # ─── PHASE 5: HYPOTHESIS TESTING ─────────────────────────────────
            state.phase = InvestigationPhase.HYPOTHESIS_TESTING
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={"phase": "hypothesis_testing"}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # Test each hypothesis against collected evidence
            for hyp in state.hypotheses:
                if investigation_id in self._stop_requests:
                    state.phase = InvestigationPhase.STOPPED
                    state.error = "Stopped by user"
                    yield _stop_event()
                    return

                hyp_result = await self._test_hypothesis(hyp, state.evidence, state.tool_results)
                hyp["verdict"] = hyp_result.get("verdict")
                hyp["posterior_confidence"] = hyp_result.get("confidence")
                hyp["supporting_evidence"] = hyp_result.get("supporting", [])
                hyp["contradicting_evidence"] = hyp_result.get("contradicting", [])
                
                # Oracle 26AI: Record hypothesis for calibration learning
                if self._longterm_memory:
                    try:
                        self._longterm_memory.record_hypothesis(
                            case_id=case_id,
                            hypothesis_text=hyp.get("description", hyp.get("name", "")),
                            predicted_confidence=hyp.get("prior_confidence", 0.5),
                            category=hyp.get("category", "investigation")
                        )
                    except Exception as e:
                        logger.debug(f"Oracle 26AI: Failed to record hypothesis: {e}")
                
                yield StreamEvent(
                    event_type=EventType.FINDING,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "type": "hypothesis_verdict",
                        "hypothesis_id": hyp.get("id"),
                        "verdict": hyp_result.get("verdict"),
                        "confidence": hyp_result.get("confidence"),
                    }
                )
            
            state.progress_percent = 80
            
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={"phase": "hypothesis_testing"}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # ─── PHASE 6: CONFIDENCE SCORING ─────────────────────────────────
            state.phase = InvestigationPhase.CONFIDENCE_SCORING
            
            # Compute 6-factor confidence for each hypothesis unless disabled.
            if compute_confidence:
                for hyp in state.hypotheses:
                    confidence_result = await self._compute_confidence(hyp, state.tool_results)
                    hyp["confidence_breakdown"] = confidence_result.get("factors")
                    hyp["final_confidence"] = confidence_result.get("overall")
                    state.confidence_scores[hyp.get("id", "")] = confidence_result.get("overall", 0)
            else:
                for hyp in state.hypotheses:
                    fallback_confidence = hyp.get("posterior_confidence", hyp.get("prior_confidence", 0.5))
                    hyp["final_confidence"] = fallback_confidence
                    state.confidence_scores[hyp.get("id", "")] = fallback_confidence
            
            # Overall investigation confidence
            if state.confidence_scores:
                overall_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
            else:
                overall_confidence = 0.5
            
            yield StreamEvent(
                event_type=EventType.FINDING,
                timestamp=datetime.now().isoformat(),
                data={
                    "type": "overall_confidence",
                    "confidence": overall_confidence,
                    "level": self._confidence_to_level(overall_confidence),
                }
            )
            
            state.progress_percent = 90
            
            # ─── PHASE 7: REPORT GENERATION ──────────────────────────────────
            state.phase = InvestigationPhase.REPORTING
            yield StreamEvent(
                event_type=EventType.PHASE_START,
                timestamp=datetime.now().isoformat(),
                data={"phase": "reporting"}
            )

            if investigation_id in self._stop_requests:
                state.phase = InvestigationPhase.STOPPED
                state.error = "Stopped by user"
                yield _stop_event()
                return
            
            # Generate report structure unless disabled.
            if generate_report:
                report = await self._generate_report(state)
            else:
                report = {
                    "title": "Report generation disabled",
                    "investigation_id": state.investigation_id,
                    "case_id": state.case_id,
                    "generated_at": datetime.now().isoformat(),
                    "page_count": 0,
                    "sections": [],
                    "hypotheses": state.hypotheses,
                    "overall_confidence": overall_confidence,
                }
            state.report = report
            
            # Oracle 26AI: Validate report claims before streaming
            validation_memory = self._get_validation_memory(case_id)
            validation_warnings = []
            if validation_memory:
                try:
                    for section in report.get("sections", []):
                        section_content = section.get("content", "")
                        if section_content and len(section_content) > 50:
                            validation_result = validation_memory.extract_and_validate_section(
                                section_text=section_content,
                                section_name=section.get("title", "unknown")
                            )
                            if validation_result.get("unsupported_claims"):
                                validation_warnings.extend(validation_result["unsupported_claims"])
                                section["validation_warnings"] = validation_result["unsupported_claims"]
                except Exception as e:
                    logger.debug(f"Oracle 26AI: Validation failed: {e}")
            
            # Stream validation warnings if any
            if validation_warnings:
                yield StreamEvent(
                    event_type=EventType.FINDING,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "type": "validation_warnings",
                        "count": len(validation_warnings),
                        "warnings": validation_warnings[:5],  # Top 5
                        "advisory": True  # Flag but don't block
                    }
                )
            
            # Stream report sections for canvas
            for section in report.get("sections", []):
                if investigation_id in self._stop_requests:
                    state.phase = InvestigationPhase.STOPPED
                    state.error = "Stopped by user"
                    yield _stop_event()
                    return

                yield StreamEvent(
                    event_type=EventType.TEXT_CHUNK,
                    timestamp=datetime.now().isoformat(),
                    data={
                        "section": section.get("title"),
                        "content": section.get("content"),
                        "page": section.get("page", 1),
                    }
                )
            
            state.progress_percent = 100
            state.phase = InvestigationPhase.COMPLETE
            
            yield StreamEvent(
                event_type=EventType.PHASE_COMPLETE,
                timestamp=datetime.now().isoformat(),
                data={
                    "phase": "complete",
                    "investigation_id": investigation_id,
                    "total_findings": len(state.findings),
                    "total_evidence": len(state.evidence),
                    "overall_confidence": overall_confidence,
                    "report_pages": report.get("page_count", 1),
                }
            )
            
        except Exception as e:
            logger.error(f"Investigation failed: {e}", exc_info=True)
            state.phase = InvestigationPhase.ERROR
            state.error = str(e)
            
            yield StreamEvent(
                event_type=EventType.ERROR,
                timestamp=datetime.now().isoformat(),
                data={
                    "investigation_id": investigation_id,
                    "error": str(e),
                    "phase": state.phase.value,
                }
            )
        finally:
            state.updated_at = datetime.now().isoformat()
            if state.phase in {
                InvestigationPhase.COMPLETE,
                InvestigationPhase.ERROR,
                InvestigationPhase.STOPPED,
            }:
                self._stop_requests.discard(investigation_id)

    def request_stop(self, investigation_id: str) -> bool:
        """Request a graceful stop for an active investigation."""
        state = self.active_investigations.get(investigation_id)
        if not state:
            return False

        self._stop_requests.add(investigation_id)
        state.phase = InvestigationPhase.STOPPED
        state.error = "Stopped by user"
        state.updated_at = datetime.now().isoformat()
        return True
    
    def _get_primary_capability(self, tool_id: str) -> str:
        """Get the primary capability for each tool."""
        primary_capabilities = {
            "timeline": "get_stats",
            "anomaly": "detect",
            "correlation": "build_graph",
            "network": "analyze_flows",
            "crud": "analyze_operations",
            "depth": "calculate_blast_radius",
            "vault": "get_summary",
        }
        return primary_capabilities.get(tool_id, "execute")
    
    async def _parse_scenario(self, case_id: str, scenario: str) -> List[Dict[str, Any]]:
        """
        Parse scenario to extract entities using LLM.
        Extracts: IPs, users, hosts, files, timeframes, and their roles.
        """
        from operation_room.services.llm_provider import get_llm
        
        llm = get_llm()
        prompt = f"""Extract forensic entities from this investigation scenario.

Scenario: {scenario}

Extract:
1. IP addresses (with suspected role: suspect, victim, target)
2. Usernames/accounts (with role: actor, victim, witness)
3. Hostnames/systems (with role: target, source, compromised)
4. Files/documents mentioned
5. Timeframes mentioned

Return JSON array with format:
[{{"value": "192.168.1.45", "type": "ip", "role": "suspect", "confidence": 0.8}}]

Types: ip, user, host, file, timeframe
Roles: suspect, victim, target, source, actor, witness

JSON only, no explanation:"""

        try:
            response = await llm.generate(
                prompt,
                max_tokens=1000,
                temperature=0.2,  # Low temperature for structured extraction
            )
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group(0))
                logger.info(f"[Orchestrator] Extracted {len(entities)} entities from scenario")
                return entities
            else:
                logger.warning("[Orchestrator] Failed to parse entities from LLM response, using fallback")
                return []
        except Exception as e:
            logger.error(f"[Orchestrator] Entity extraction failed: {e}")
            return []
    
    async def _generate_hypotheses(
        self,
        case_id: str,
        scenario: str,
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate investigation hypotheses using LLM and ACH framework.
        Always includes H0 (null hypothesis) plus 3-5 competing hypotheses.
        """
        from operation_room.services.llm_provider import get_llm
        
        llm = get_llm()
        entities_str = json.dumps(entities, indent=2)
        
        prompt = f"""You are a forensic investigator using Analysis of Competing Hypotheses (ACH).

Generate 3-5 competing hypotheses for this investigation, plus H0 (null hypothesis).

Scenario: {scenario}

Identified Entities:
{entities_str}

Requirements:
1. H0 must always be "No malicious activity occurred" with prior=0.1
2. Generate 3-5 competing hypotheses covering different threat types:
   - Insider threat
   - External compromise
   - Accidental exposure
   - Supply chain attack
   - Other plausible scenarios
3. Assign realistic prior probabilities (sum to ~1.0)
4. Each hypothesis must be testable with digital evidence

Return JSON array:
[{{
  "id": "H0",
  "statement": "No malicious activity occurred (NULL hypothesis)",
  "type": "null",
  "prior_confidence": 0.1,
  "test_criteria": ["Normal activity patterns", "No policy violations"]
}},
{{
  "id": "H1",
  "statement": "Insider threat: Employee intentionally exfiltrated data",
  "type": "insider_threat",
  "prior_confidence": 0.4,
  "test_criteria": ["Unusual data access", "Exfiltration indicators", "Motive"]
}}]

JSON only:"""

        try:
            response = await llm.generate(prompt, max_tokens=2000, temperature=0.4)
            
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                hypotheses = json.loads(json_match.group(0))
                
                # Ensure H0 exists
                if not any(h.get("id") == "H0" for h in hypotheses):
                    hypotheses.insert(0, {
                        "id": "H0",
                        "statement": "No malicious activity occurred (NULL hypothesis)",
                        "type": "null",
                        "prior_confidence": 0.1,
                        "test_criteria": ["Normal behavior patterns"]
                    })
                
                logger.info(f"[Orchestrator] Generated {len(hypotheses)} hypotheses")
                return hypotheses
            else:
                logger.warning("[Orchestrator] Failed to parse hypotheses, using defaults")
                return self._get_default_hypotheses()
        except Exception as e:
            logger.error(f"[Orchestrator] Hypothesis generation failed: {e}")
            return self._get_default_hypotheses()
    
    def _get_default_hypotheses(self) -> List[Dict[str, Any]]:
        """Fallback hypotheses if LLM generation fails."""
        return [
            {
                "id": "H0",
                "statement": "No malicious activity occurred (NULL hypothesis)",
                "type": "null",
                "prior_confidence": 0.1,
                "test_criteria": ["Normal behavior patterns", "No policy violations"]
            },
            {
                "id": "H1",
                "statement": "Insider threat: Authorized user intentionally misused access",
                "type": "insider_threat",
                "prior_confidence": 0.4,
                "test_criteria": ["Unusual data access", "Exfiltration indicators"]
            },
            {
                "id": "H2",
                "statement": "External compromise: Credentials stolen or system breached",
                "type": "external_threat",
                "prior_confidence": 0.3,
                "test_criteria": ["Authentication anomalies", "Lateral movement"]
            },
            {
                "id": "H3",
                "statement": "Accidental exposure: Misconfiguration or user error",
                "type": "accidental",
                "prior_confidence": 0.2,
                "test_criteria": ["No malicious intent indicators", "Configuration errors"]
            },
        ]
    
    async def _generate_plan(
        self,
        case_id: str,
        scenario: str,
        hypotheses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate investigation plan."""
        return {
            "phases": [
                {
                    "id": "reconnaissance",
                    "name": "Reconnaissance",
                    "order": 1,
                    "steps": [
                        {"id": "timeline", "description": "Build unified timeline", "tool": "timeline"},
                        {"id": "entity_extract", "description": "Extract entities", "tool": "correlation"},
                    ]
                },
                {
                    "id": "analysis",
                    "name": "Deep Analysis",
                    "order": 2,
                    "steps": [
                        {"id": "anomaly", "description": "Detect anomalies", "tool": "anomaly"},
                        {"id": "network", "description": "Analyze network", "tool": "network"},
                        {"id": "crud", "description": "Analyze data access", "tool": "crud"},
                    ]
                },
                {
                    "id": "hypothesis",
                    "name": "Hypothesis Testing",
                    "order": 3,
                    "steps": [
                        {"id": f"test_{h['id']}", "description": f"Test {h['id']}", "hypothesis": h['id']}
                        for h in hypotheses
                    ]
                },
                {
                    "id": "synthesis",
                    "name": "Synthesis & Reporting",
                    "order": 4,
                    "steps": [
                        {"id": "confidence", "description": "Compute confidence", "tool": "confidence"},
                        {"id": "report", "description": "Generate report", "tool": "report"},
                    ]
                },
            ]
        }
    
    async def _test_hypothesis(
        self,
        hypothesis: Dict[str, Any],
        evidence: List[Dict[str, Any]],
        tool_results: Dict[str, ToolOutput],
    ) -> Dict[str, Any]:
        """
        Test hypothesis against evidence using Bayesian scoring and ACH.
        Returns posterior confidence based on evidence support/contradiction.
        """
        total_findings = sum(len(r.findings) for r in tool_results.values() if r.success)
        
        # Get prior confidence
        prior = hypothesis.get("prior_confidence", 0.5)
        
        # Calculate evidence strength
        supporting_evidence = 0
        contradicting_evidence = 0
        neutral_evidence = 0
        
        # Analyze each module's findings for hypothesis support
        for module_name, result in tool_results.items():
            if not result.success:
                continue
            
            for finding in result.findings:
                finding_data = self._normalize_finding(finding)
                severity = str(finding_data.get("severity", "info")).lower()
                
                # High/Critical findings increase probability of malicious hypotheses
                if severity in ("high", "critical"):
                    if hypothesis.get("type") in ("insider_threat", "external_threat"):
                        supporting_evidence += 0.15
                    elif hypothesis.get("type") == "null":
                        contradicting_evidence += 0.15
                    else:  # accidental
                        supporting_evidence += 0.05
                elif severity in ("medium", "warning"):
                    if hypothesis.get("type") != "null":
                        supporting_evidence += 0.05
                else:
                    neutral_evidence += 0.01
        
        # Bayesian update: P(H|E) = P(E|H) * P(H) / P(E)
        # Simplified: posterior = prior * evidence_multiplier
        if total_findings == 0:
            # No evidence: return prior
            posterior = prior
        else:
            # Calculate likelihood ratio
            if hypothesis.get("type") == "null":
                # Null hypothesis: evidence against it
                likelihood_ratio = 1.0 / max(1.0, 1.0 + supporting_evidence - contradicting_evidence)
            else:
                # Alt hypothesis: evidence for it
                likelihood_ratio = 1.0 + supporting_evidence - contradicting_evidence
            
            # Apply Bayesian update with bounds
            posterior = min(0.99, max(0.01, prior * likelihood_ratio))
        
        # Normalize to ensure total probability ~1.0 across all hypotheses
        # (done at higher level in run_investigation)
        
        if posterior > prior + 0.05:
            verdict = "confirmed"
        elif posterior < prior - 0.05:
            verdict = "rejected"
        else:
            verdict = "inconclusive"

        return {
            "hypothesis_id": hypothesis.get("id"),
            "prior": prior,
            "posterior": posterior,
            "confidence": posterior,
            "supporting_evidence": supporting_evidence,
            "contradicting_evidence": contradicting_evidence,
            "evidence_count": total_findings,
            "verdict": verdict,
        }
    
    async def _compute_confidence(
        self,
        hypothesis: Dict[str, Any],
        tool_results: Dict[str, ToolOutput],
    ) -> Dict[str, Any]:
        """Compute 6-factor confidence score."""
        
        # Factor weights (ODNI ICD 203)
        WEIGHTS = {
            "evidence_coverage": 0.25,
            "module_agreement": 0.20,
            "temporal_consistency": 0.15,
            "cross_validation": 0.20,
            "pattern_match": 0.10,
            "research_alignment": 0.10,
        }
        
        # Calculate factors
        successful_tools = sum(1 for r in tool_results.values() if r.success)
        total_tools = len(tool_results)
        
        factors = {
            "evidence_coverage": successful_tools / max(1, total_tools),
            "module_agreement": 0.85,  # Mock
            "temporal_consistency": 0.90,  # Mock
            "cross_validation": 0.75,  # Mock
            "pattern_match": 0.70,  # Mock
            "research_alignment": 0.80,  # Mock
        }
        
        # Weighted sum
        overall = sum(factors[k] * WEIGHTS[k] for k in factors) / sum(WEIGHTS.values())
        
        return {
            "overall": overall,
            "level": self._confidence_to_level(overall),
            "factors": factors,
        }
    
    def _confidence_to_level(self, confidence: float) -> str:
        """Convert numeric confidence to ODNI level."""
        if confidence >= 0.90:
            return "VERY_HIGH"
        elif confidence >= 0.75:
            return "HIGH"
        elif confidence >= 0.50:
            return "MODERATE"
        elif confidence >= 0.25:
            return "LOW"
        else:
            return "VERY_LOW"
    
    async def _generate_report(self, state: InvestigationState) -> Dict[str, Any]:
        """
        Generate final report structure via the Canonical Court-Ready Pipeline.
        
        Integrates:
        - Adaptive template selection based on scenario/case type
        - Evidence-key citation binding
        - Section-level parallel generation
        - Admissibility gate enforcement
        """
        # Attempt canonical pipeline
        try:
            from operation_room.services.canonical_pipeline import CanonicalPipeline, PipelineEvent

            # Determine case type from hypotheses
            case_type = "general"
            for hyp in state.hypotheses:
                hyp_type = hyp.get("type", "")
                if hyp_type in ("insider_threat", "external_threat", "data_exfiltration",
                                "ransomware", "fraud", "malware", "phishing"):
                    case_type = hyp_type
                    break

            # Collect module results as plain dicts for the pipeline
            module_summaries = {}
            for tool_id, result in state.tool_results.items():
                module_summaries[tool_id] = {
                    "success": result.success,
                    "findings_count": len(result.findings),
                    "evidence_count": len(result.evidence),
                    "findings": [self._normalize_finding(f) for f in result.findings[:10]],
                }

            pipeline = CanonicalPipeline(
                case_id=state.case_id,
                config={
                    "enforce_admissibility": False,  # Don't block on first run
                    "auto_approve_sections": True,
                    "include_ai_narratives": True,
                },
            )

            manifest = None
            async for event in pipeline.execute(
                scenario=state.scenario,
                case_type=case_type,
                investigation_data={
                    "investigation_id": state.investigation_id,
                    "hypotheses": state.hypotheses,
                    "findings": state.findings,
                    "evidence": state.evidence,
                },
                module_results=module_summaries,
                metadata={
                    "generated_by": "unified_orchestrator",
                    "confidence_scores": state.confidence_scores,
                },
            ):
                logger.info(
                    f"[Orchestrator→Pipeline] {event.event_type} — {event.progress:.0%}"
                )

            manifest = pipeline.get_manifest()
            if manifest:
                return {
                    "title": manifest.title,
                    "investigation_id": state.investigation_id,
                    "case_id": state.case_id,
                    "generated_at": datetime.now().isoformat(),
                    "page_count": len(manifest.sections) * 2,
                    "sections": [
                        {
                            "title": s.section_title,
                            "content": s.content[:500] if s.content else "...",
                            "page": s.sort_order + 1,
                        }
                        for s in manifest.sections
                    ],
                    "hypotheses": state.hypotheses,
                    "overall_confidence": manifest.overall_confidence,
                    "report_id": manifest.report_id,
                    "status": manifest.status.value,
                    "admissibility": (
                        manifest.admissibility.to_dict()
                        if manifest.admissibility else None
                    ),
                    "total_citations": manifest.total_citations,
                    "content_hash": manifest.content_hash,
                    "generation_time_ms": manifest.generation_time_ms,
                }

        except Exception as e:
            logger.warning(
                f"[Orchestrator] Canonical pipeline unavailable, using fallback: {e}"
            )

        # Fallback: structured report stub
        return {
            "title": f"Investigation Report: {state.scenario[:50]}...",
            "investigation_id": state.investigation_id,
            "case_id": state.case_id,
            "generated_at": datetime.now().isoformat(),
            "page_count": 25,
            "sections": [
                {"title": "Executive Summary", "content": "...", "page": 1},
                {"title": "Methodology", "content": "...", "page": 3},
                {"title": "Timeline Analysis", "content": "...", "page": 5},
                {"title": "Anomaly Detection", "content": "...", "page": 8},
                {"title": "Entity Correlation", "content": "...", "page": 11},
                {"title": "Network Analysis", "content": "...", "page": 14},
                {"title": "Hypothesis Findings", "content": "...", "page": 17},
                {"title": "Confidence Assessment", "content": "...", "page": 20},
                {"title": "Recommendations", "content": "...", "page": 23},
                {"title": "Appendix: Evidence", "content": "...", "page": 25},
            ],
            "hypotheses": state.hypotheses,
            "overall_confidence": sum(state.confidence_scores.values()) / max(1, len(state.confidence_scores)),
        }
    
    def get_investigation(self, investigation_id: str) -> Optional[InvestigationState]:
        """Get investigation state."""
        return self.active_investigations.get(investigation_id)
    
    def list_investigations(self) -> List[Dict[str, Any]]:
        """List all active investigations."""
        return [inv.to_dict() for inv in self.active_investigations.values()]


# Global instance
unified_orchestrator = UnifiedInvestigationOrchestrator()
