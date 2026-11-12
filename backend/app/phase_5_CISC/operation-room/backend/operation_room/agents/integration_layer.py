"""
Integration Layer — Agent-to-Agent Communication and Pipeline Coordination.

This module provides:
- Inter-agent communication protocols
- Pipeline execution coordination
- Result aggregation and transformation
- Error handling and retry logic

Author: NFLIP Development Team
Version: 2.0.0  # Updated: Consolidated orchestration
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, TypeVar, Generic

from operation_room.agents.base import registry, AgentMessage, MessageType, AgentStatus, BaseAgentState
# Note: MasterOrchestrator removed - functionality consolidated here
from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
from operation_room.agents.evidence.evidence_collector import EvidenceCollectionAgent
from operation_room.agents.confidence.confidence_agent import ConfidenceScoringAgent
from operation_room.agents.synthesis.synthesis_agent import SummarySynthesisAgent
from operation_room.agents.research.knowledge_base import knowledge_base

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineStage(Enum):
    """Stages in the report generation pipeline."""
    INITIALIZATION = "initialization"
    HYPOTHESIS_ANALYSIS = "hypothesis_analysis"
    EVIDENCE_COLLECTION = "evidence_collection"
    MODULE_EVALUATION = "module_evaluation"
    CONFIDENCE_SCORING = "confidence_scoring"
    SUMMARY_SYNTHESIS = "summary_synthesis"
    FINALIZATION = "finalization"


@dataclass
class StageResult:
    """Result from a pipeline stage."""
    stage: PipelineStage
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """Context passed through the pipeline."""
    pipeline_id: str
    case_id: str
    scenario: str
    report_type: str
    llm_provider: str
    started_at: datetime
    stage_results: Dict[PipelineStage, StageResult] = field(default_factory=dict)
    
    # Accumulated data
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[Dict[str, Any]] = field(default_factory=list)
    attack_vectors: List[Dict[str, Any]] = field(default_factory=list)
    evidence_inventory: Dict[str, Any] = field(default_factory=dict)
    module_results: Dict[str, Any] = field(default_factory=dict)
    confidence_scores: Dict[str, Any] = field(default_factory=dict)
    final_report: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "case_id": self.case_id,
            "scenario": self.scenario,
            "report_type": self.report_type,
            "started_at": self.started_at.isoformat(),
            "stages": {
                k.value: {
                    "success": v.success,
                    "duration_ms": v.duration_ms,
                    "error": v.error
                }
                for k, v in self.stage_results.items()
            },
            "hypothesis_count": len(self.hypotheses),
            "entity_count": len(self.entities),
            "evidence_count": len(self.evidence_inventory.get("evidence", [])),
            "confidence": self.confidence_scores.get("overall_confidence", 0)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineExecutor:
    """
    Executes the multi-agent report generation pipeline.
    
    Coordinates the flow of data between agents:
    1. HypothesisAnalysisAgent → generates hypotheses from scenario
    2. EvidenceCollectionAgent → collects evidence from modules
    3. ConfidenceScoringAgent → scores hypothesis confidence
    4. SummarySynthesisAgent → generates final report
    """
    
    def __init__(self, llm_provider: str = "ollama"):
        self.llm_provider = llm_provider
        self.hypothesis_agent = None
        self.evidence_agent = None
        self.confidence_agent = None
        self.synthesis_agent = None
        
    def _init_agents(self):
        """Initialize all agents."""
        self.hypothesis_agent = HypothesisAnalysisAgent(
            llm_provider=self.llm_provider
        )
        self.evidence_agent = EvidenceCollectionAgent()
        self.confidence_agent = ConfidenceScoringAgent()
        self.synthesis_agent = SummarySynthesisAgent(
            llm_provider=self.llm_provider
        )
        
    async def execute(
        self,
        case_id: str,
        scenario: str,
        report_type: str = "technical",
        callbacks: Optional[Dict[str, Callable]] = None
    ) -> PipelineContext:
        """
        Execute the full pipeline.
        
        Args:
            case_id: Target case identifier
            scenario: Investigation scenario text
            report_type: Type of report (technical, executive, regulatory)
            callbacks: Optional callbacks for stage events
            
        Returns:
            PipelineContext with all results
        """
        callbacks = callbacks or {}
        
        # Create context
        context = PipelineContext(
            pipeline_id=str(uuid.uuid4()),
            case_id=case_id,
            scenario=scenario,
            report_type=report_type,
            llm_provider=self.llm_provider,
            started_at=datetime.now(timezone.utc)
        )
        
        logger.info(f"[{context.pipeline_id}] Starting pipeline for case {case_id}")
        
        # Initialize agents
        self._init_agents()
        
        try:
            # Stage 1: Initialization
            await self._run_stage(
                context,
                PipelineStage.INITIALIZATION,
                self._stage_initialization,
                callbacks
            )
            
            # Stage 2: Hypothesis Analysis
            await self._run_stage(
                context,
                PipelineStage.HYPOTHESIS_ANALYSIS,
                self._stage_hypothesis_analysis,
                callbacks
            )
            
            # Stage 3: Evidence Collection
            await self._run_stage(
                context,
                PipelineStage.EVIDENCE_COLLECTION,
                self._stage_evidence_collection,
                callbacks
            )
            
            # Stage 4: Module Evaluation
            await self._run_stage(
                context,
                PipelineStage.MODULE_EVALUATION,
                self._stage_module_evaluation,
                callbacks
            )
            
            # Stage 5: Confidence Scoring
            await self._run_stage(
                context,
                PipelineStage.CONFIDENCE_SCORING,
                self._stage_confidence_scoring,
                callbacks
            )
            
            # Stage 6: Summary Synthesis
            await self._run_stage(
                context,
                PipelineStage.SUMMARY_SYNTHESIS,
                self._stage_summary_synthesis,
                callbacks
            )
            
            # Stage 7: Finalization
            await self._run_stage(
                context,
                PipelineStage.FINALIZATION,
                self._stage_finalization,
                callbacks
            )
            
        except Exception as e:
            logger.error(f"[{context.pipeline_id}] Pipeline failed: {e}")
            raise
            
        logger.info(f"[{context.pipeline_id}] Pipeline completed")
        return context
        
    async def _run_stage(
        self,
        context: PipelineContext,
        stage: PipelineStage,
        handler: Callable,
        callbacks: Dict[str, Callable]
    ):
        """Run a single pipeline stage."""
        start_time = datetime.now(timezone.utc)
        
        # Notify start
        if "on_stage_start" in callbacks:
            await self._call_callback(callbacks["on_stage_start"], stage, context)
            
        try:
            result = await handler(context)
            
            # Record result
            context.stage_results[stage] = StageResult(
                stage=stage,
                success=True,
                data=result,
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            
            # Notify completion
            if "on_stage_complete" in callbacks:
                await self._call_callback(
                    callbacks["on_stage_complete"],
                    stage,
                    context,
                    result
                )
                
        except Exception as e:
            # Record failure
            context.stage_results[stage] = StageResult(
                stage=stage,
                success=False,
                error=str(e),
                duration_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            
            # Notify error
            if "on_stage_error" in callbacks:
                await self._call_callback(
                    callbacks["on_stage_error"],
                    stage,
                    context,
                    e
                )
            raise
            
    async def _call_callback(self, callback: Callable, *args):
        """Call a callback, handling both sync and async."""
        if asyncio.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)
            
    # ───────────────────────────────────────────────────────────────────────────
    # STAGE HANDLERS
    # ───────────────────────────────────────────────────────────────────────────
    
    async def _stage_initialization(self, context: PipelineContext) -> Dict[str, Any]:
        """Initialize the pipeline."""
        logger.info(f"[{context.pipeline_id}] Stage: Initialization")
        
        # Fetch relevant research methodologies
        recommendations = knowledge_base.get_recommendations(
            hypothesis_types=["malware", "intrusion", "data_breach"],
            modules=["timeline", "anomaly", "network"],
            limit=20
        )
        
        return {
            "case_id": context.case_id,
            "scenario_length": len(context.scenario),
            "recommended_methodologies": len(recommendations)
        }
        
    async def _stage_hypothesis_analysis(self, context: PipelineContext) -> Dict[str, Any]:
        """Run hypothesis analysis."""
        logger.info(f"[{context.pipeline_id}] Stage: Hypothesis Analysis")
        
        result = await self.hypothesis_agent.analyze(
            scenario=context.scenario,
            case_id=context.case_id,
            llm_provider=self.llm_provider
        )
        
        # Store results in context
        context.hypotheses = result.get("hypotheses", [])
        context.entities = result.get("entities", [])
        context.attack_vectors = result.get("attack_vectors", [])
        
        return {
            "hypothesis_count": len(context.hypotheses),
            "entity_count": len(context.entities),
            "attack_vector_count": len(context.attack_vectors)
        }
        
    async def _stage_evidence_collection(self, context: PipelineContext) -> Dict[str, Any]:
        """Collect evidence from modules."""
        logger.info(f"[{context.pipeline_id}] Stage: Evidence Collection")
        
        # Build evidence requirements from hypotheses
        evidence_requirements = []
        for h in context.hypotheses:
            evidence_requirements.extend(h.get("evidence_requirements", []))
            
        result = await self.evidence_agent.collect(
            case_id=context.case_id,
            evidence_requirements=evidence_requirements
        )
        
        # Store results in context
        context.evidence_inventory = result.get("evidence_inventory", {})
        
        return {
            "evidence_count": len(context.evidence_inventory.get("evidence", [])),
            "modules_queried": result.get("modules_queried", [])
        }
        
    async def _stage_module_evaluation(self, context: PipelineContext) -> Dict[str, Any]:
        """Evaluate results from each module."""
        logger.info(f"[{context.pipeline_id}] Stage: Module Evaluation")
        
        # Evidence collector already stores per-module results
        context.module_results = context.evidence_inventory.get("by_module", {})
        
        module_stats = {}
        for module, evidence_list in context.module_results.items():
            module_stats[module] = {
                "evidence_count": len(evidence_list),
                "high_confidence": sum(1 for e in evidence_list if e.get("confidence", 0) > 0.8)
            }
            
        return {
            "modules_evaluated": list(context.module_results.keys()),
            "module_stats": module_stats
        }
        
    async def _stage_confidence_scoring(self, context: PipelineContext) -> Dict[str, Any]:
        """Score confidence for hypotheses."""
        logger.info(f"[{context.pipeline_id}] Stage: Confidence Scoring")
        
        result = await self.confidence_agent.score(
            case_id=context.case_id,
            hypotheses=context.hypotheses,
            evidence_inventory=context.evidence_inventory,
            module_results=context.module_results
        )
        
        # Store results in context
        context.confidence_scores = result
        
        return {
            "overall_confidence": result.get("overall_case_confidence", 0),
            "confidence_level": result.get("overall_confidence_level", "moderate"),
            "hypothesis_scores": len(result.get("hypothesis_confidences", []))
        }
        
    async def _stage_summary_synthesis(self, context: PipelineContext) -> Dict[str, Any]:
        """Generate the final report."""
        logger.info(f"[{context.pipeline_id}] Stage: Summary Synthesis")
        
        result = await self.synthesis_agent.synthesize(
            case_id=context.case_id,
            report_type=context.report_type,
            hypotheses=context.hypotheses,
            evidence_inventory=context.evidence_inventory,
            confidence_scores=context.confidence_scores,
            llm_provider=self.llm_provider
        )
        
        # Store results in context
        context.final_report = result.get("report", {})
        
        return {
            "report_generated": True,
            "sections": list(context.final_report.keys()),
            "word_count": len(str(context.final_report).split())
        }
        
    async def _stage_finalization(self, context: PipelineContext) -> Dict[str, Any]:
        """Finalize the pipeline."""
        logger.info(f"[{context.pipeline_id}] Stage: Finalization")
        
        # Calculate total duration
        total_duration = (datetime.now(timezone.utc) - context.started_at).total_seconds() * 1000
        
        # Count successes
        successful_stages = sum(
            1 for r in context.stage_results.values() if r.success
        )
        
        return {
            "total_duration_ms": total_duration,
            "successful_stages": successful_stages,
            "total_stages": len(context.stage_results),
            "pipeline_id": context.pipeline_id
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE BROKER
# ═══════════════════════════════════════════════════════════════════════════════

class MessageBroker:
    """
    Handles inter-agent communication via messages.
    
    Provides pub/sub pattern for agents to communicate:
    - Agents publish messages to topics
    - Agents subscribe to topics they're interested in
    - Broker routes messages to subscribers
    """
    
    def __init__(self):
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        
    def subscribe(self, topic: str, handler: Callable):
        """Subscribe to a topic."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(handler)
        
    def unsubscribe(self, topic: str, handler: Callable):
        """Unsubscribe from a topic."""
        if topic in self._subscriptions:
            self._subscriptions[topic] = [
                h for h in self._subscriptions[topic] if h != handler
            ]
            
    async def publish(self, topic: str, message: AgentMessage):
        """Publish a message to a topic."""
        await self._message_queue.put((topic, message))
        
    async def start(self):
        """Start the message broker."""
        self._running = True
        asyncio.create_task(self._process_messages())
        
    async def stop(self):
        """Stop the message broker."""
        self._running = False
        
    async def _process_messages(self):
        """Process messages from the queue."""
        while self._running:
            try:
                topic, message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                
                handlers = self._subscriptions.get(topic, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Handler error for topic {topic}: {e}")
                        
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message broker error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT AGGREGATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ResultAggregator:
    """
    Aggregates results from multiple agents into a unified structure.
    
    Handles:
    - Merging evidence from different modules
    - Combining confidence scores
    - Resolving conflicts between agent outputs
    """
    
    @staticmethod
    def merge_evidence(
        evidence_lists: List[List[Dict[str, Any]]],
        dedup_key: str = "evidence_id"
    ) -> List[Dict[str, Any]]:
        """
        Merge evidence from multiple sources, removing duplicates.
        
        Args:
            evidence_lists: Lists of evidence dictionaries
            dedup_key: Key to use for deduplication
            
        Returns:
            Merged and deduplicated evidence list
        """
        seen = set()
        merged = []
        
        for evidence_list in evidence_lists:
            for evidence in evidence_list:
                key = evidence.get(dedup_key, str(evidence))
                if key not in seen:
                    seen.add(key)
                    merged.append(evidence)
                    
        return merged
        
    @staticmethod
    def combine_confidence_scores(
        scores: List[Dict[str, float]],
        weights: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """
        Combine confidence scores from multiple sources.
        
        Args:
            scores: List of score dictionaries
            weights: Optional weights for each source
            
        Returns:
            Combined confidence scores
        """
        if not scores:
            return {}
            
        if weights is None:
            weights = [1.0 / len(scores)] * len(scores)
            
        # Get all keys
        all_keys = set()
        for s in scores:
            all_keys.update(s.keys())
            
        # Weighted average for each key
        combined = {}
        for key in all_keys:
            values = []
            weight_sum = 0
            for score, weight in zip(scores, weights):
                if key in score:
                    values.append(score[key] * weight)
                    weight_sum += weight
                    
            if values and weight_sum > 0:
                combined[key] = sum(values) / weight_sum
                
        return combined
        
    @staticmethod
    def resolve_conflicts(
        results: List[Dict[str, Any]],
        priority_order: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Resolve conflicts between agent outputs.
        
        Args:
            results: List of result dictionaries from different agents
            priority_order: Optional agent priority for conflict resolution
            
        Returns:
            Resolved result dictionary
        """
        if not results:
            return {}
            
        # Simple priority-based resolution
        resolved = {}
        
        for result in results:
            for key, value in result.items():
                if key not in resolved:
                    resolved[key] = value
                elif isinstance(resolved[key], list) and isinstance(value, list):
                    # Merge lists
                    resolved[key].extend(value)
                elif isinstance(resolved[key], dict) and isinstance(value, dict):
                    # Merge dicts
                    resolved[key].update(value)
                    
        return resolved


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

class RetryHandler:
    """
    Handles retry logic for agent operations.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Async callable to execute
            *args: Arguments for the operation
            **kwargs: Keyword arguments for the operation
            
        Returns:
            Operation result
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.base_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    logger.warning(
                        f"Retry {attempt + 1}/{self.max_retries} after {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                    
        raise last_exception


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════

# Global message broker
broker = MessageBroker()

# Global result aggregator
aggregator = ResultAggregator()

# Global retry handler
retry_handler = RetryHandler()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "PipelineStage",
    "StageResult",
    "PipelineContext",
    "PipelineExecutor",
    "MessageBroker",
    "ResultAggregator",
    "RetryHandler",
    "broker",
    "aggregator",
    "retry_handler",
]
