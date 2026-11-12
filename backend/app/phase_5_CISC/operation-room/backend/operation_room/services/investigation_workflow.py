"""
Investigation Workflow Orchestrator

Step-by-step investigation workflow that:
1. Collects scenario and scope from user
2. Checks existing data and identifies gaps
3. Generates hypotheses using LLM
4. Collects evidence using modules as tools
5. Saves all findings with keys to vault
6. Calculates confidence scores
7. Builds report in Report Studio
8. Exports as PDF with key-value replacement

This is the main orchestrator for the complete investigation workflow.
Supports 3 execution modes:
- autopilot: AI runs all relevant modules automatically
- smart_recommendation: AI recommends modules, user approves
- run_all: Run all modules regardless of hypothesis
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field

from operation_room.database import open_vault
from operation_room.config import settings
from operation_room.services.findings_vault import get_findings_vault, FindingType
from operation_room.services.confidence_scoring import get_confidence_engine
from operation_room.services.llm_provider import get_llm

# Module imports
from operation_room.services.anomaly_agent import run_anomaly_detection, get_anomaly_summary
from operation_room.services.crud_agent import run_crud_analysis, get_crud_summary
from operation_room.services.network_agent import get_network_flows_stats_search, get_exfil_candidates
from operation_room.services.depth_agent import run_depth_analysis, generate_impact_narrative
from operation_room.services.timeline_service import get_timeline_stats_search

# Oracle 26AI Open-Source Alternatives - Long-term Memory for Calibration
try:
    from operation_room.services.longterm_memory import get_long_term_memory, HypothesisOutcome
    from operation_room.services.procedural_memory import get_procedural_memory
    MEMORY_SERVICES_AVAILABLE = True
except ImportError:
    MEMORY_SERVICES_AVAILABLE = False

logger = logging.getLogger(__name__)


class InvestigationPhase(str, Enum):
    """Phases of the investigation workflow."""
    IDLE = "idle"
    SCENARIO_GATHERING = "scenario_gathering"
    DATA_VALIDATION = "data_validation"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EVIDENCE_COLLECTION = "evidence_collection"
    FINDING_ANALYSIS = "finding_analysis"
    CONFIDENCE_SCORING = "confidence_scoring"
    REPORT_BUILDING = "report_building"
    COMPLETE = "complete"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """Module execution modes."""
    AUTOPILOT = "autopilot"  # AI runs all relevant modules automatically
    SMART_RECOMMENDATION = "smart_recommendation"  # AI recommends, user approves
    RUN_ALL = "run_all"  # Run all modules regardless


@dataclass
class ModuleConfig:
    """Configuration for an analysis module."""
    name: str
    description: str
    run_func: Callable
    relevant_for: List[str]  # Hypothesis types/keywords this module is relevant for
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1  # Lower = higher priority
    estimated_duration: str = "30s"


@dataclass
class ModuleRecommendation:
    """A module recommendation for smart_recommendation mode."""
    module_name: str
    reason: str
    relevance_score: float  # 0.0-1.0
    recommended: bool
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class ModuleResult:
    """Result from running a module."""
    module_name: str
    status: str  # success, failed, skipped
    findings_count: int
    duration_ms: int
    error: Optional[str] = None
    findings_keys: List[str] = field(default_factory=list)


class ExecutionController:
    """
    Controls module execution based on selected mode.
    
    Modes:
    - autopilot: Automatically runs all relevant modules based on hypotheses
    - smart_recommendation: Generates recommendations for user approval
    - run_all: Runs all modules regardless of relevance
    """
    
    def __init__(self, case_id: str, investigation_id: str):
        self.case_id = case_id
        self.investigation_id = investigation_id
        self.mode = ExecutionMode.AUTOPILOT
        self.approved_modules: List[str] = []
        self.skipped_modules: List[str] = []
        self.module_results: List[ModuleResult] = []
        
        # Define available modules
        self.modules = self._define_modules()
        
        # Oracle 26AI: Initialize memory services for calibration
        self._longterm_memory = None
        self._procedural_memory = None
        if MEMORY_SERVICES_AVAILABLE:
            try:
                self._longterm_memory = get_long_term_memory()
                self._procedural_memory = get_procedural_memory()
                logger.info(f"[Workflow] Memory services initialized for {investigation_id}")
            except Exception as e:
                logger.debug(f"Memory services unavailable: {e}")
    
    def _define_modules(self) -> Dict[str, ModuleConfig]:
        """Define all available analysis modules."""
        return {
            "anomaly": ModuleConfig(
                name="anomaly",
                description="Statistical analysis of event patterns to detect anomalies",
                run_func=self._run_anomaly,
                relevant_for=["suspicious_activity", "insider_threat", "policy_violation", 
                             "unauthorized_access", "abnormal_behavior"],
                priority=1,
                estimated_duration="30s"
            ),
            "network": ModuleConfig(
                name="network",
                description="Network flow analysis for data exfiltration detection",
                run_func=self._run_network,
                relevant_for=["data_exfiltration", "lateral_movement", "external_attack",
                             "data_theft", "network_breach"],
                priority=1,
                estimated_duration="45s"
            ),
            "crud": ModuleConfig(
                name="crud",
                description="Create/Read/Update/Delete operation tracking and analysis",
                run_func=self._run_crud,
                relevant_for=["data_theft", "unauthorized_access", "data_modification",
                             "data_deletion", "insider_threat"],
                priority=2,
                estimated_duration="30s"
            ),
            "depth": ModuleConfig(
                name="depth",
                description="Access depth and permission escalation analysis",
                run_func=self._run_depth,
                relevant_for=["privilege_escalation", "deep_access", "permission_abuse",
                             "lateral_movement", "impact_assessment"],
                priority=2,
                estimated_duration="30s"
            ),
            "timeline": ModuleConfig(
                name="timeline",
                description="Temporal pattern and sequence analysis",
                run_func=self._run_timeline,
                relevant_for=["all"],  # Always relevant
                priority=0,  # Run first
                estimated_duration="20s"
            ),
            "correlation": ModuleConfig(
                name="correlation",
                description="Cross-module pattern correlation",
                run_func=self._run_correlation,
                relevant_for=["all"],  # Always relevant
                priority=3,  # Run after other modules
                estimated_duration="40s"
            )
        }
    
    def set_mode(self, mode: ExecutionMode):
        """Set the execution mode."""
        self.mode = mode
        logger.info(f"Execution mode set to: {mode.value}")
    
    def get_recommendations(
        self, 
        hypotheses: List[Dict[str, Any]]
    ) -> List[ModuleRecommendation]:
        """
        Generate module recommendations based on hypotheses.
        Used in smart_recommendation mode.
        """
        recommendations = []
        
        # Extract keywords from hypotheses (both raw and split by underscore)
        hypothesis_keywords = set()
        for hyp in hypotheses:
            # Extract from name, description, type
            hyp_text = f"{hyp.get('name', '')} {hyp.get('description', '')} {hyp.get('type', '')}".lower()
            for word in hyp_text.split():
                hypothesis_keywords.add(word)
                # Also add underscore-split parts
                if '_' in word:
                    hypothesis_keywords.update(word.split('_'))
        
        for module_name, config in self.modules.items():
            relevance_score = 0.0
            reasons = []
            
            # Check if module is always relevant
            if "all" in config.relevant_for:
                relevance_score = 1.0
                reasons.append("Essential for all investigations")
            else:
                # Calculate relevance based on keyword matches
                for keyword in config.relevant_for:
                    # Check exact match first
                    if keyword.lower() in hypothesis_keywords:
                        relevance_score += 0.4
                        reasons.append(f"Direct match: '{keyword}'")
                    else:
                        # Check partial matches
                        keyword_parts = keyword.lower().split("_")
                        matches = sum(1 for part in keyword_parts if part in hypothesis_keywords)
                        if matches > 0:
                            relevance_score += 0.2 * matches / len(keyword_parts)
                            reasons.append(f"Partial match: '{keyword}'")
            
            # Cap at 1.0
            relevance_score = min(relevance_score, 1.0)
            
            recommendations.append(ModuleRecommendation(
                module_name=module_name,
                reason="; ".join(reasons) if reasons else "No direct match but may provide supporting evidence",
                relevance_score=relevance_score,
                recommended=relevance_score >= 0.4 or "all" in config.relevant_for,
                parameters=config.parameters
            ))
        
        # Sort by relevance
        recommendations.sort(key=lambda r: (-r.relevance_score, self.modules[r.module_name].priority))
        
        return recommendations
    
    def approve_modules(self, module_names: List[str]):
        """Approve specific modules for execution in smart_recommendation mode."""
        self.approved_modules = module_names
        logger.info(f"Approved modules: {module_names}")
    
    def skip_modules(self, module_names: List[str]):
        """Skip specific modules."""
        self.skipped_modules = module_names
        logger.info(f"Skipped modules: {module_names}")
    
    async def execute(
        self, 
        hypotheses: List[Dict[str, Any]],
        vault,
        on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None
    ) -> List[ModuleResult]:
        """
        Execute modules based on the current mode.
        
        Args:
            hypotheses: List of approved hypotheses
            vault: FindingsVault instance
            on_progress: Optional callback for progress updates
        
        Returns:
            List of ModuleResult for each executed module
        """
        self.vault = vault
        results = []
        
        # Oracle 26AI: Record hypotheses for calibration
        if self._longterm_memory:
            for hyp in hypotheses:
                try:
                    self._longterm_memory.record_hypothesis(
                        case_id=self.case_id,
                        hypothesis_text=hyp.get("statement", hyp.get("description", "")),
                        predicted_confidence=hyp.get("prior_confidence", 0.5),
                        category=hyp.get("type", "investigation")
                    )
                except Exception as e:
                    logger.debug(f"Failed to record hypothesis: {e}")
        
        # Determine which modules to run
        if self.mode == ExecutionMode.RUN_ALL:
            modules_to_run = list(self.modules.keys())
        elif self.mode == ExecutionMode.SMART_RECOMMENDATION:
            modules_to_run = self.approved_modules
        else:  # AUTOPILOT
            recommendations = self.get_recommendations(hypotheses)
            modules_to_run = [r.module_name for r in recommendations if r.recommended]
        
        # Remove skipped modules
        modules_to_run = [m for m in modules_to_run if m not in self.skipped_modules]
        
        # Sort by priority
        modules_to_run.sort(key=lambda m: self.modules[m].priority)
        
        logger.info(f"Executing modules ({self.mode.value}): {modules_to_run}")
        
        for module_name in modules_to_run:
            if on_progress:
                await on_progress(module_name, "starting")
            
            config = self.modules[module_name]
            start_time = datetime.now()
            
            try:
                findings_keys = await config.run_func(hypotheses)
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                result = ModuleResult(
                    module_name=module_name,
                    status="success",
                    findings_count=len(findings_keys),
                    duration_ms=duration_ms,
                    findings_keys=findings_keys
                )
                
                # Oracle 26AI: Record successful module execution
                if self._longterm_memory:
                    try:
                        # This helps calibrate module effectiveness
                        logger.debug(f"Module {module_name}: {len(findings_keys)} findings in {duration_ms}ms")
                    except Exception:
                        pass
                
                if on_progress:
                    await on_progress(module_name, "complete")
                    
            except Exception as e:
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                logger.error(f"Module {module_name} failed: {e}")
                
                result = ModuleResult(
                    module_name=module_name,
                    status="failed",
                    findings_count=0,
                    duration_ms=duration_ms,
                    error=str(e)
                )
                
                if on_progress:
                    await on_progress(module_name, f"failed: {e}")
            
            results.append(result)
            self.module_results.append(result)
        
        return results
    
    async def calibrate_hypothesis(
        self, 
        hypothesis_id: str, 
        outcome: str,
        actual_confidence: Optional[float] = None
    ):
        """
        Oracle 26AI: Record hypothesis outcome for calibration learning.
        
        Args:
            hypothesis_id: ID of the hypothesis
            outcome: 'confirmed', 'rejected', 'partial', 'inconclusive'
            actual_confidence: Actual confidence level (optional)
        """
        if not self._longterm_memory or not MEMORY_SERVICES_AVAILABLE:
            return
        
        try:
            hyp_outcome = HypothesisOutcome(outcome)
            self._longterm_memory.resolve_hypothesis(
                hypothesis_id=hypothesis_id,
                outcome=hyp_outcome,
                actual_confidence=actual_confidence
            )
            logger.info(f"[Calibration] Recorded outcome for {hypothesis_id}: {outcome}")
        except Exception as e:
            logger.debug(f"Failed to calibrate hypothesis: {e}")
    
    async def run_targeted_module(
        self,
        module_name: str,
        parameters: Dict[str, Any],
        hypotheses: List[Dict[str, Any]]
    ) -> ModuleResult:
        """
        Run a specific module with targeted parameters.
        Used for hypothesis-specific re-runs.
        """
        if module_name not in self.modules:
            return ModuleResult(
                module_name=module_name,
                status="failed",
                findings_count=0,
                duration_ms=0,
                error=f"Unknown module: {module_name}"
            )
        
        config = self.modules[module_name]
        config.parameters = parameters
        
        start_time = datetime.now()
        try:
            findings_keys = await config.run_func(hypotheses)
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ModuleResult(
                module_name=module_name,
                status="success",
                findings_count=len(findings_keys),
                duration_ms=duration_ms,
                findings_keys=findings_keys
            )
        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            return ModuleResult(
                module_name=module_name,
                status="failed",
                findings_count=0,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    # ─── Module Runner Methods ───────────────────────────────────────────────────
    
    async def _run_anomaly(self, hypotheses: List[Dict]) -> List[str]:
        """Run anomaly detection and save findings."""
        findings_keys = []
        
        anomaly_summary = get_anomaly_summary(self.case_id)
        
        if anomaly_summary.get("anomalies_found", 0) > 0:
            # Generate unique key
            key = self.vault.key_generator.generate_anomaly_key("summary")
            
            self.vault.save_finding(
                finding_key=key,
                finding_value={
                    "total_anomalies": anomaly_summary["anomalies_found"],
                    "anomaly_rate": anomaly_summary.get("anomaly_rate", 0),
                    "max_score": anomaly_summary.get("max_score", 0),
                    "top_actors": anomaly_summary.get("top_anomalous_actors", [])[:5]
                },
                finding_type=FindingType.METRIC,
                investigation_id=self.investigation_id,
                source_module="anomaly",
                confidence_score=0.8
            )
            findings_keys.append(key)
            
            # Save individual top actors
            for i, actor in enumerate(anomaly_summary.get("top_anomalous_actors", [])[:3]):
                actor_key = self.vault.key_generator.generate_anomaly_key(actor.get("actor", f"actor_{i}"))
                self.vault.save_finding(
                    finding_key=actor_key,
                    finding_value=actor,
                    finding_type=FindingType.ENTITY,
                    investigation_id=self.investigation_id,
                    source_module="anomaly",
                    confidence_score=actor.get("anomaly_rate", 0.5)
                )
                findings_keys.append(actor_key)
        
        return findings_keys
    
    async def _run_network(self, hypotheses: List[Dict]) -> List[str]:
        """Run network analysis and save findings."""
        findings_keys = []
        
        network_stats = get_network_flows_stats_search(self.case_id, {})
        exfil_candidates = get_exfil_candidates(self.case_id)
        
        if network_stats.get("total_flows", 0) > 0:
            key = self.vault.key_generator.generate_network_key(flow_type="STATS")
            self.vault.save_finding(
                finding_key=key,
                finding_value=network_stats,
                finding_type=FindingType.METRIC,
                investigation_id=self.investigation_id,
                source_module="network",
                confidence_score=0.9
            )
            findings_keys.append(key)
        
        if len(exfil_candidates) > 0:
            # Save exfiltration summary
            exfil_key = self.vault.key_generator.generate_key("EXFIL", "DETECTED")
            self.vault.save_finding(
                finding_key=exfil_key,
                finding_value={
                    "candidate_count": len(exfil_candidates),
                    "top_candidates": exfil_candidates[:5]
                },
                finding_type=FindingType.EVIDENCE,
                investigation_id=self.investigation_id,
                source_module="network",
                confidence_score=0.85
            )
            findings_keys.append(exfil_key)
            
            # Save individual exfil candidates
            for candidate in exfil_candidates[:3]:
                src_ip = candidate.get("source_ip", "unknown")
                cand_key = self.vault.key_generator.generate_exfil_key(src_ip)
                self.vault.save_finding(
                    finding_key=cand_key,
                    finding_value=candidate,
                    finding_type=FindingType.EVIDENCE,
                    investigation_id=self.investigation_id,
                    source_module="network",
                    confidence_score=candidate.get("risk_score", 0.5)
                )
                findings_keys.append(cand_key)
        
        return findings_keys
    
    async def _run_crud(self, hypotheses: List[Dict]) -> List[str]:
        """Run CRUD analysis and save findings."""
        findings_keys = []
        
        crud_summary = get_crud_summary(self.case_id)
        
        if crud_summary.get("total_events", 0) > 0:
            key = self.vault.key_generator.generate_key("CRUD", "SUMMARY")
            self.vault.save_finding(
                finding_key=key,
                finding_value={
                    "total_events": crud_summary["total_events"],
                    "by_operation": crud_summary.get("by_operation", {}),
                    "by_sensitivity": crud_summary.get("by_sensitivity", {}),
                    "top_actors": crud_summary.get("top_actors", [])[:5]
                },
                finding_type=FindingType.METRIC,
                investigation_id=self.investigation_id,
                source_module="crud",
                confidence_score=0.9
            )
            findings_keys.append(key)
        
        return findings_keys
    
    async def _run_depth(self, hypotheses: List[Dict]) -> List[str]:
        """Run depth analysis and save findings."""
        findings_keys = []
        
        depth_result = run_depth_analysis(self.case_id)
        
        if depth_result.get("impact_score"):
            key = self.vault.key_generator.generate_key("DEP", "IMPACT")
            self.vault.save_finding(
                finding_key=key,
                finding_value={
                    "overall_score": depth_result["impact_score"].get("overall", 0),
                    "level": depth_result["impact_score"].get("level", "unknown"),
                    "dimensions": depth_result.get("dimensions", {})
                },
                finding_type=FindingType.METRIC,
                investigation_id=self.investigation_id,
                source_module="depth",
                confidence_score=0.85
            )
            findings_keys.append(key)
        
        return findings_keys
    
    async def _run_timeline(self, hypotheses: List[Dict]) -> List[str]:
        """Run timeline analysis and save findings."""
        findings_keys = []
        
        timeline_stats = get_timeline_stats_search(self.case_id, {})
        
        key = self.vault.key_generator.generate_key("TML", "SCOPE")
        self.vault.save_finding(
            finding_key=key,
            finding_value={
                "total_events": timeline_stats.get("total", 0),
                "time_range": timeline_stats.get("time_range", {}),
                "event_types": timeline_stats.get("by_event_type", [])[:10]
            },
            finding_type=FindingType.METRIC,
            investigation_id=self.investigation_id,
            source_module="timeline",
            confidence_score=1.0  # Timeline is factual
        )
        findings_keys.append(key)
        
        return findings_keys
    
    async def _run_correlation(self, hypotheses: List[Dict]) -> List[str]:
        """Run correlation analysis across modules."""
        findings_keys = []
        
        # Get existing findings for correlation
        all_findings = self.vault.get_all_findings(self.investigation_id)
        
        # Group findings by source module
        by_module = {}
        for f in all_findings:
            module = f.get("source_module", "unknown")
            if module not in by_module:
                by_module[module] = []
            by_module[module].append(f)
        
        # Generate correlation summary
        key = self.vault.key_generator.generate_key("COR", "SUMMARY")
        self.vault.save_finding(
            finding_key=key,
            finding_value={
                "modules_analyzed": list(by_module.keys()),
                "findings_by_module": {k: len(v) for k, v in by_module.items()},
                "total_findings": len(all_findings),
                "cross_module_patterns": []  # TODO: Implement actual correlation
            },
            finding_type=FindingType.CORRELATION,
            investigation_id=self.investigation_id,
            source_module="correlation",
            confidence_score=0.7
        )
        findings_keys.append(key)
        
        return findings_keys


class WorkflowOrchestrator:
    """Orchestrates the complete investigation workflow."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.investigation_id = str(uuid.uuid4())
        self.vault = get_findings_vault(case_id)
        self.confidence_engine = get_confidence_engine(case_id)
        self.execution_controller = ExecutionController(case_id, self.investigation_id)
        self.phase = InvestigationPhase.IDLE
        self.metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def set_execution_mode(self, mode: str):
        """Set the module execution mode."""
        try:
            exec_mode = ExecutionMode(mode)
            self.execution_controller.set_mode(exec_mode)
        except ValueError:
            logger.warning(f"Invalid execution mode: {mode}, using autopilot")
            self.execution_controller.set_mode(ExecutionMode.AUTOPILOT)
    
    def get_module_recommendations(self, hypotheses: List[Dict]) -> List[Dict]:
        """Get module recommendations for smart_recommendation mode."""
        recommendations = self.execution_controller.get_recommendations(hypotheses)
        return [
            {
                "module_name": r.module_name,
                "description": self.execution_controller.modules[r.module_name].description,
                "reason": r.reason,
                "relevance_score": r.relevance_score,
                "recommended": r.recommended,
                "estimated_duration": self.execution_controller.modules[r.module_name].estimated_duration
            }
            for r in recommendations
        ]
    
    def approve_modules(self, module_names: List[str]):
        """Approve specific modules for execution."""
        self.execution_controller.approve_modules(module_names)
    
    async def run_complete_workflow(
        self,
        scenario: str,
        timeline_range: Optional[Dict] = None,
        scope: Optional[Dict] = None,
        llm_provider: str = "gemini",
        execution_mode: str = "autopilot",
        approved_modules: Optional[List[str]] = None,
        on_progress: Optional[Callable[[str, str], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Run the complete investigation workflow.
        
        Args:
            scenario: Investigation scenario description
            timeline_range: Optional {"start": "2024-01-01", "end": "2024-01-31"}
            scope: Optional scope restrictions
            llm_provider: LLM provider to use
            execution_mode: autopilot, smart_recommendation, or run_all
            approved_modules: Modules to run (for smart_recommendation mode)
            on_progress: Optional callback for progress updates
        
        Returns:
            Complete investigation results with findings and report
        """
        # Set execution mode
        self.set_execution_mode(execution_mode)
        if approved_modules:
            self.approve_modules(approved_modules)
        
        results = {
            "investigation_id": self.investigation_id,
            "case_id": self.case_id,
            "scenario": scenario,
            "phases": {},
            "findings_count": 0,
            "confidence_summary": {},
            "report_doc_id": None,
            "status": "started"
        }
        
        try:
            # ═══ PHASE 1: Scenario Gathering ═══
            logger.info(f"[{self.investigation_id}] Phase 1: Scenario Gathering")
            self.phase = InvestigationPhase.SCENARIO_GATHERING
            
            scenario_data = await self._gather_scenario(scenario, timeline_range, scope)
            results["phases"]["scenario_gathering"] = scenario_data
            
            # Save scenario as finding
            self.vault.save_finding(
                finding_key="INVESTIGATION_SCENARIO",
                finding_value=scenario_data,
                finding_type=FindingType.HYPOTHESIS,
                investigation_id=self.investigation_id,
                source_module="orchestrator",
                metadata={"phase": "scenario_gathering"}
            )
            
            # ═══ PHASE 2: Data Validation ═══
            logger.info(f"[{self.investigation_id}] Phase 2: Data Validation")
            self.phase = InvestigationPhase.DATA_VALIDATION
            
            data_status = await self._validate_existing_data()
            results["phases"]["data_validation"] = data_status
            
            if data_status["missing_data"]:
                # Save data gaps
                self.vault.save_finding(
                    finding_key="DATA_GAPS",
                    finding_value=data_status["missing_data"],
                    finding_type=FindingType.METRIC,
                    investigation_id=self.investigation_id,
                    source_module="orchestrator",
                    confidence_score=1.0  # We know what's missing
                )
            
            # ═══ PHASE 3: Hypothesis Generation ═══
            logger.info(f"[{self.investigation_id}] Phase 3: Hypothesis Generation")
            self.phase = InvestigationPhase.HYPOTHESIS_GENERATION
            
            hypotheses = await self._generate_hypotheses(scenario, data_status, llm_provider)
            results["phases"]["hypothesis_generation"] = hypotheses
            
            for idx, hyp in enumerate(hypotheses):
                self.vault.save_finding(
                    finding_key=f"HYPOTHESIS_{idx+1}",
                    finding_value=hyp,
                    finding_type=FindingType.HYPOTHESIS,
                    investigation_id=self.investigation_id,
                    source_module="llm",
                    confidence_score=hyp.get("initial_confidence", 0.5)
                )
            
            # ═══ PHASE 4: Evidence Collection ═══
            logger.info(f"[{self.investigation_id}] Phase 4: Evidence Collection (mode: {self.execution_controller.mode.value})")
            self.phase = InvestigationPhase.EVIDENCE_COLLECTION
            
            # Use ExecutionController for module execution
            self.execution_controller.vault = self.vault
            module_results = await self.execution_controller.execute(
                hypotheses=hypotheses,
                vault=self.vault,
                on_progress=on_progress
            )
            
            # Convert to evidence dict
            evidence = {
                "execution_mode": self.execution_controller.mode.value,
                "modules_executed": [r.module_name for r in module_results],
                "results": [
                    {
                        "module": r.module_name,
                        "status": r.status,
                        "findings_count": r.findings_count,
                        "duration_ms": r.duration_ms,
                        "findings_keys": r.findings_keys,
                        "error": r.error
                    }
                    for r in module_results
                ],
                "total_findings": sum(r.findings_count for r in module_results)
            }
            results["phases"]["evidence_collection"] = evidence
            
            # ═══ PHASE 5: Finding Analysis ═══
            logger.info(f"[{self.investigation_id}] Phase 5: Finding Analysis")
            self.phase = InvestigationPhase.FINDING_ANALYSIS
            
            analysis = await self._analyze_findings(llm_provider)
            results["phases"]["finding_analysis"] = analysis
            
            # ═══ PHASE 6: Confidence Scoring ═══
            logger.info(f"[{self.investigation_id}] Phase 6: Confidence Scoring")
            self.phase = InvestigationPhase.CONFIDENCE_SCORING
            
            # Recalculate all confidence scores now that we have complete data
            self.confidence_engine.recalculate_all_confidences(self.investigation_id)
            
            confidence_summary = self.vault.get_findings_summary(self.investigation_id)
            results["confidence_summary"] = confidence_summary
            
            # ═══ PHASE 7: Report Building ═══
            logger.info(f"[{self.investigation_id}] Phase 7: Report Building")
            self.phase = InvestigationPhase.REPORT_BUILDING
            
            report_doc_id = await self._build_report(llm_provider)
            results["report_doc_id"] = report_doc_id
            
            # ═══ COMPLETE ═══
            self.phase = InvestigationPhase.COMPLETE
            results["status"] = "complete"
            results["findings_count"] = confidence_summary.get("total_findings", 0)
            
            logger.info(f"[{self.investigation_id}] Investigation Complete!")
            return results
            
        except Exception as e:
            logger.error(f"[{self.investigation_id}] Workflow error: {e}", exc_info=True)
            self.phase = InvestigationPhase.ERROR
            results["status"] = "error"
            results["error"] = str(e)
            return results
    
    async def _gather_scenario(
        self,
        scenario: str,
        timeline_range: Optional[Dict],
        scope: Optional[Dict]
    ) -> Dict[str, Any]:
        """Gather and validate scenario details."""
        return {
            "description": scenario,
            "timeline_range": timeline_range or "all_available",
            "scope": scope or "full_case",
            "gathered_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def _validate_existing_data(self) -> Dict[str, Any]:
        """Check what data exists and identify gaps."""
        conn = open_vault(self.case_id)
        
        available_tables = []
        missing_data = []
        
        try:
            # Check for key tables
            tables_result = conn.execute("SHOW TABLES").fetchall()
            available_tables = [row[0] for row in tables_result]
            
            # Check for essential data
            required_tables = {
                "unified_timeline": "Timeline events",
                "anomaly_scores": "Anomaly detection data",
                "crud_events": "Data access patterns",
                "network_flows": "Network traffic data"
            }
            
            for table, description in required_tables.items():
                if table not in available_tables:
                    missing_data.append({
                        "type": "table",
                        "name": table,
                        "description": description
                    })
                else:
                    # Check if table has data
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    if count == 0:
                        missing_data.append({
                            "type": "empty_table",
                            "name": table,
                            "description": f"{description} (table exists but empty)"
                        })
            
            return {
                "available_tables": available_tables,
                "table_count": len(available_tables),
                "missing_data": missing_data,
                "status": "sufficient" if len(missing_data) == 0 else "partial"
            }
            
        finally:
            conn.close()
    
    async def _generate_hypotheses(
        self,
        scenario: str,
        data_status: Dict,
        llm_provider: str
    ) -> List[Dict[str, Any]]:
        """Generate investigation hypotheses using LLM."""
        llm = get_llm(provider=llm_provider)
        
        prompt = f"""You are a forensic investigator generating hypotheses for an investigation.

Scenario:
{scenario}

Available Data:
- Tables: {', '.join(data_status.get('available_tables', []))}
- Status: {data_status.get('status', 'unknown')}

Generate 3-5 specific, testable hypotheses about what might have happened.
For each hypothesis, provide:
1. A clear statement
2. What evidence would support it
3. What evidence would refute it
4. Initial confidence level (0.0-1.0)

Format as JSON array:
[
  {{
    "hypothesis": "statement",
    "supporting_evidence_needed": ["item1", "item2"],
    "refuting_evidence": ["item1"],
    "initial_confidence": 0.5,
    "priority": "high|medium|low"
  }}
]

Return ONLY valid JSON, no markdown formatting."""
        
        try:
            response = await llm.generate(
                prompt,
                system="You are a forensic analyst generating testable hypotheses. Return only valid JSON."
            )
            
            # Parse JSON response
            hypotheses = json.loads(response)
            
            if not isinstance(hypotheses, list):
                hypotheses = [hypotheses]
            
            return hypotheses
            
        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            # Fallback to basic hypothesis
            return [{
                "hypothesis": f"Investigation of: {scenario[:100]}",
                "supporting_evidence_needed": ["timeline_events", "anomalies", "network_flows"],
                "refuting_evidence": ["no_suspicious_activity"],
                "initial_confidence": 0.5,
                "priority": "high"
            }]
    
    async def _collect_evidence(self, hypotheses: List[Dict]) -> Dict[str, Any]:
        """
        Collect evidence by running all analysis modules.
        
        Each module result is saved as findings with keys.
        """
        evidence = {
            "anomaly": None,
            "crud": None,
            "network": None,
            "depth": None,
            "timeline": None
        }
        
        # Run Anomaly Detection
        try:
            logger.info("Running anomaly detection...")
            anomaly_summary = get_anomaly_summary(self.case_id)
            evidence["anomaly"] = anomaly_summary
            
            # Save key findings
            if anomaly_summary.get("anomalies_found", 0) > 0:
                self.vault.save_finding(
                    finding_key="ANOMALY_COUNT",
                    finding_value={
                        "total_anomalies": anomaly_summary["anomalies_found"],
                        "anomaly_rate": anomaly_summary["anomaly_rate"],
                        "max_score": anomaly_summary["max_score"]
                    },
                    finding_type=FindingType.METRIC,
                    investigation_id=self.investigation_id,
                    source_module="anomaly",
                    source_data_path="anomaly_scores.aggregated"
                )
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
        
        # Run CRUD Analysis
        try:
            logger.info("Running CRUD analysis...")
            crud_summary = get_crud_summary(self.case_id)
            evidence["crud"] = crud_summary
            
            if crud_summary.get("total_events", 0) > 0:
                self.vault.save_finding(
                    finding_key="DATA_ACCESS_PATTERN",
                    finding_value={
                        "total_events": crud_summary["total_events"],
                        "by_operation": crud_summary.get("by_operation", {}),
                        "by_sensitivity": crud_summary.get("by_sensitivity", {})
                    },
                    finding_type=FindingType.METRIC,
                    investigation_id=self.investigation_id,
                    source_module="crud",
                    source_data_path="crud_events.aggregated"
                )
        except Exception as e:
            logger.error(f"CRUD analysis failed: {e}")
        
        # Run Network Analysis
        try:
            logger.info("Running network analysis...")
            network_stats = get_network_flows_stats_search(self.case_id, {})
            exfil_candidates = get_exfil_candidates(self.case_id)
            evidence["network"] = {
                "stats": network_stats,
                "exfiltration_candidates": exfil_candidates
            }
            
            if len(exfil_candidates) > 0:
                self.vault.save_finding(
                    finding_key="EXFILTRATION_DETECTED",
                    finding_value={
                        "candidate_count": len(exfil_candidates),
                        "top_candidates": exfil_candidates[:5]
                    },
                    finding_type=FindingType.EVIDENCE,
                    investigation_id=self.investigation_id,
                    source_module="network",
                    source_data_path="network_flows.exfil_candidates"
                )
        except Exception as e:
            logger.error(f"Network analysis failed: {e}")
        
        # Run Depth/Impact Analysis
        try:
            logger.info("Running depth analysis...")
            depth_result = run_depth_analysis(self.case_id)
            evidence["depth"] = depth_result
            
            if depth_result.get("impact_score"):
                self.vault.save_finding(
                    finding_key="IMPACT_ASSESSMENT",
                    finding_value={
                        "overall_score": depth_result["impact_score"]["overall"],
                        "level": depth_result["impact_score"]["level"],
                        "dimensions": depth_result.get("dimensions", {})
                    },
                    finding_type=FindingType.METRIC,
                    investigation_id=self.investigation_id,
                    source_module="depth",
                    source_data_path="depth_analysis.impact"
                )
        except Exception as e:
            logger.error(f"Depth analysis failed: {e}")
        
        # Get Timeline Stats
        try:
            logger.info("Getting timeline stats...")
            timeline_stats = get_timeline_stats_search(self.case_id, {})
            evidence["timeline"] = timeline_stats
            
            self.vault.save_finding(
                finding_key="TIMELINE_SCOPE",
                finding_value={
                    "total_events": timeline_stats.get("total", 0),
                    "time_range": timeline_stats.get("time_range", {}),
                    "event_types": timeline_stats.get("by_event_type", [])
                },
                finding_type=FindingType.METRIC,
                investigation_id=self.investigation_id,
                source_module="timeline",
                source_data_path="unified_timeline.stats"
            )
        except Exception as e:
            logger.error(f"Timeline stats failed: {e}")
        
        return evidence
    
    async def _analyze_findings(self, llm_provider: str) -> Dict[str, Any]:
        """Analyze collected findings to draw conclusions."""
        # Get all findings
        findings = self.vault.get_all_findings(self.investigation_id)
        
        # Group by type
        by_type = {}
        for finding in findings:
            ftype = finding["finding_type"]
            if ftype not in by_type:
                by_type[ftype] = []
            by_type[ftype].append(finding)
        
        # Generate AI analysis
        llm = get_llm(provider=llm_provider)
        
        summary = f"""Findings collected:
- Total: {len(findings)}
- Evidence: {len(by_type.get(FindingType.EVIDENCE, []))}
- Metrics: {len(by_type.get(FindingType.METRIC, []))}
- Hypotheses: {len(by_type.get(FindingType.HYPOTHESIS, []))}

Key findings:
{json.dumps([f["finding_key"] for f in findings[:10]], indent=2)}"""
        
        prompt = f"""Analyze these investigation findings and provide:
1. Key patterns discovered
2. Notable anomalies or suspicious activities
3. Confidence in conclusions
4. Recommended next steps

{summary}

Provide a brief 2-3 paragraph analysis."""
        
        try:
            analysis_text = await llm.generate(
                prompt,
                system="You are a forensic analyst providing findings analysis."
            )
            
            # Save analysis as finding
            self.vault.save_finding(
                finding_key="ANALYSIS_SUMMARY",
                finding_value={"analysis": analysis_text},
                finding_type=FindingType.CONCLUSION,
                investigation_id=self.investigation_id,
                source_module="llm",
                confidence_score=0.7
            )
            
            return {
                "analysis_text": analysis_text,
                "findings_analyzed": len(findings),
                "by_type": {k: len(v) for k, v in by_type.items()}
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {
                "analysis_text": "Analysis generation failed",
                "findings_analyzed": len(findings),
                "error": str(e)
            }
    
    async def _build_report(self, llm_provider: str) -> str:
        """Build report in Report Studio."""
        from operation_room.services.studio_v2_service import create_document
        
        # Create new document
        doc_id = str(uuid.uuid4())
        
        # Get all findings
        findings = self.vault.get_all_findings(self.investigation_id)
        
        # Build TipTap AST with findings
        content = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": "Investigation Report"}]
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"Investigation ID: {self.investigation_id}"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": f"Case ID: {self.case_id}"},
                        {"type": "hardBreak"},
                        {"type": "text", "text": f"Findings: {len(findings)}"}
                    ]
                }
            ]
        }
        
        # Add findings sections
        for finding in findings[:20]:  # Limit to top 20
            # Add finding as a block with key reference
            content["content"].append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": finding["finding_key"]}]
            })
            
            content["content"].append({
                "type": "paragraph",
                "attrs": {
                    "data-finding-key": finding["finding_key"],  # Key for hover
                    "data-confidence": finding["confidence_score"],
                    "data-source": finding.get("source_module", "unknown")
                },
                "content": [
                    {"type": "text", "text": json.dumps(finding["finding_value"], indent=2)}
                ]
            })
        
        # Create document
        result = create_document(
            case_id=self.case_id,
            title=f"Investigation Report - {self.investigation_id[:8]}",
            initial_ast=content
        )
        
        doc_id = result.get("doc_id", "unknown")
        logger.info(f"Report created: {doc_id}")
        return doc_id


def get_workflow_orchestrator(case_id: str) -> WorkflowOrchestrator:
    """Get workflow orchestrator for a case."""
    return WorkflowOrchestrator(case_id)
