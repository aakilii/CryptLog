"""
Agent Runner Service — Executes agents with proper lifecycle management.

Provides:
- Agent execution with timeouts
- Progress tracking and callbacks
- Logging and metrics collection
- Background task management
- Health monitoring

Author: NFLIP Development Team
Version: 1.0.0
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, TypeVar

from operation_room.config import settings
from operation_room.services.llm_service import get_llm_service, EnhancedLLMService
from operation_room.agents.base import registry, AgentStatus
from operation_room.agents.integration_layer import PipelineExecutor, PipelineContext, PipelineStage

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class RunStatus(str, Enum):
    """Status of an agent run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class RunProgress:
    """Progress information for a run."""
    current_stage: str = ""
    total_stages: int = 0
    completed_stages: int = 0
    percentage: float = 0.0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_stage": self.current_stage,
            "total_stages": self.total_stages,
            "completed_stages": self.completed_stages,
            "percentage": self.percentage,
            "message": self.message,
        }


@dataclass
class AgentRun:
    """Tracks a single agent execution."""
    run_id: str
    case_id: str
    scenario: str
    report_type: str
    llm_provider: str
    status: RunStatus = RunStatus.PENDING
    progress: RunProgress = field(default_factory=RunProgress)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "scenario": self.scenario[:100] + "..." if len(self.scenario) > 100 else self.scenario,
            "report_type": self.report_type,
            "llm_provider": self.llm_provider,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            ),
            "error": self.error,
            "logs_count": len(self.logs),
        }
        
    def add_log(self, message: str):
        """Add a log entry."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.logs.append(f"[{timestamp}] {message}")
        logger.info(f"[{self.run_id}] {message}")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT RUNNER SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class AgentRunnerService:
    """
    Service for executing multi-agent pipelines.
    
    Features:
    - Async execution with progress tracking
    - Run history management
    - Callbacks for progress updates
    - Configurable timeouts
    """
    
    def __init__(
        self,
        default_timeout: float = 300.0,  # 5 minutes
        max_concurrent_runs: int = 5
    ):
        self.default_timeout = default_timeout
        self.max_concurrent_runs = max_concurrent_runs
        self._runs: Dict[str, AgentRun] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._llm_service: Optional[EnhancedLLMService] = None
        
    @property
    def llm_service(self) -> EnhancedLLMService:
        """Get LLM service instance."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service
        
    # ───────────────────────────────────────────────────────────────────────────
    # RUN MANAGEMENT
    # ───────────────────────────────────────────────────────────────────────────
    
    def create_run(
        self,
        case_id: str,
        scenario: str,
        report_type: str = "technical",
        llm_provider: str = None
    ) -> AgentRun:
        """Create a new run."""
        run = AgentRun(
            run_id=str(uuid.uuid4()),
            case_id=case_id,
            scenario=scenario,
            report_type=report_type,
            llm_provider=llm_provider or settings.LLM_PROVIDER
        )
        self._runs[run.run_id] = run
        run.add_log(f"Run created for case {case_id}")
        return run
        
    def get_run(self, run_id: str) -> Optional[AgentRun]:
        """Get a run by ID."""
        return self._runs.get(run_id)
        
    def list_runs(
        self,
        status: Optional[RunStatus] = None,
        case_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AgentRun]:
        """List runs with optional filtering."""
        runs = list(self._runs.values())
        
        if status:
            runs = [r for r in runs if r.status == status]
        if case_id:
            runs = [r for r in runs if r.case_id == case_id]
            
        # Sort by start time, most recent first
        runs.sort(key=lambda r: r.started_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        return runs[:limit]
        
    def get_active_runs(self) -> List[AgentRun]:
        """Get currently running executions."""
        return [r for r in self._runs.values() if r.status == RunStatus.RUNNING]
        
    # ───────────────────────────────────────────────────────────────────────────
    # EXECUTION
    # ───────────────────────────────────────────────────────────────────────────
    
    async def execute_run(
        self,
        run: AgentRun,
        timeout: Optional[float] = None,
        on_progress: Optional[Callable[[RunProgress], None]] = None
    ) -> AgentRun:
        """
        Execute a run synchronously (awaits completion).
        
        Args:
            run: The run to execute
            timeout: Optional timeout in seconds
            on_progress: Optional progress callback
            
        Returns:
            Updated AgentRun with results
        """
        timeout = timeout or self.default_timeout
        
        # Check concurrent limit
        active = len(self.get_active_runs())
        if active >= self.max_concurrent_runs:
            run.status = RunStatus.FAILED
            run.error = f"Too many concurrent runs ({active}/{self.max_concurrent_runs})"
            run.add_log(f"Rejected: {run.error}")
            return run
            
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.add_log("Execution started")
        
        try:
            # Create pipeline executor
            executor = PipelineExecutor(llm_provider=run.llm_provider)
            
            # Build callbacks
            callbacks = {}
            if on_progress:
                callbacks["on_stage_start"] = lambda stage, ctx: self._handle_stage_start(
                    run, stage, on_progress
                )
                callbacks["on_stage_complete"] = lambda stage, ctx, result: self._handle_stage_complete(
                    run, stage, result, on_progress
                )
                callbacks["on_stage_error"] = lambda stage, ctx, error: self._handle_stage_error(
                    run, stage, error
                )
                
            # Execute with timeout
            context = await asyncio.wait_for(
                executor.execute(
                    case_id=run.case_id,
                    scenario=run.scenario,
                    report_type=run.report_type,
                    callbacks=callbacks
                ),
                timeout=timeout
            )
            
            # Store result
            run.result = {
                "pipeline_id": context.pipeline_id,
                "hypotheses": context.hypotheses,
                "entities": context.entities,
                "evidence_count": len(context.evidence_inventory.get("evidence", [])),
                "confidence": context.confidence_scores,
                "report": context.final_report,
                "stage_results": {
                    k.value: v.to_dict() if hasattr(v, 'to_dict') else {
                        "success": v.success,
                        "duration_ms": v.duration_ms
                    }
                    for k, v in context.stage_results.items()
                }
            }
            
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.add_log("Execution completed successfully")
            
        except asyncio.TimeoutError:
            run.status = RunStatus.TIMEOUT
            run.error = f"Execution timed out after {timeout}s"
            run.completed_at = datetime.now(timezone.utc)
            run.add_log(f"Timeout: {run.error}")
            
        except Exception as e:
            run.status = RunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            run.add_log(f"Error: {run.error}")
            logger.exception(f"[{run.run_id}] Execution failed")
            
        return run
        
    def start_run_async(
        self,
        run: AgentRun,
        timeout: Optional[float] = None
    ) -> str:
        """
        Start a run in the background.
        
        Args:
            run: The run to execute
            timeout: Optional timeout in seconds
            
        Returns:
            run_id
        """
        task = asyncio.create_task(self.execute_run(run, timeout))
        self._active_tasks[run.run_id] = task
        
        # Clean up task reference when done
        task.add_done_callback(lambda t: self._active_tasks.pop(run.run_id, None))
        
        return run.run_id
        
    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running execution."""
        run = self.get_run(run_id)
        if not run:
            return False
            
        task = self._active_tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            run.status = RunStatus.CANCELLED
            run.completed_at = datetime.now(timezone.utc)
            run.add_log("Cancelled by user")
            return True
            
        return False
        
    # ───────────────────────────────────────────────────────────────────────────
    # PROGRESS HANDLING
    # ───────────────────────────────────────────────────────────────────────────
    
    def _handle_stage_start(
        self,
        run: AgentRun,
        stage: PipelineStage,
        callback: Callable
    ):
        """Handle stage start event."""
        total_stages = 7  # Number of pipeline stages
        completed = len([
            s for s in PipelineStage
            if s.value < stage.value and run.result  # Approximate ordering
        ])
        
        run.progress = RunProgress(
            current_stage=stage.value,
            total_stages=total_stages,
            completed_stages=completed,
            percentage=(completed / total_stages) * 100,
            message=f"Running {stage.value}..."
        )
        run.add_log(f"Stage started: {stage.value}")
        
        try:
            callback(run.progress)
        except Exception as e:
            logger.warning(f"Progress callback error: {e}")
            
    def _handle_stage_complete(
        self,
        run: AgentRun,
        stage: PipelineStage,
        result: Dict[str, Any],
        callback: Callable
    ):
        """Handle stage completion event."""
        run.progress.completed_stages += 1
        run.progress.percentage = (run.progress.completed_stages / run.progress.total_stages) * 100
        run.progress.message = f"Completed {stage.value}"
        run.add_log(f"Stage completed: {stage.value}")
        
        try:
            callback(run.progress)
        except Exception as e:
            logger.warning(f"Progress callback error: {e}")
            
    def _handle_stage_error(
        self,
        run: AgentRun,
        stage: PipelineStage,
        error: Exception
    ):
        """Handle stage error event."""
        run.add_log(f"Stage error in {stage.value}: {error}")
        
    # ───────────────────────────────────────────────────────────────────────────
    # HEALTH & METRICS
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health status."""
        runs = list(self._runs.values())
        
        return {
            "status": "healthy",
            "active_runs": len(self.get_active_runs()),
            "max_concurrent_runs": self.max_concurrent_runs,
            "total_runs": len(runs),
            "completed_runs": sum(1 for r in runs if r.status == RunStatus.COMPLETED),
            "failed_runs": sum(1 for r in runs if r.status == RunStatus.FAILED),
            "llm_provider": self.llm_service.provider_name,
            "llm_metrics": self.llm_service.get_metrics(),
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        runs = list(self._runs.values())
        completed = [r for r in runs if r.status == RunStatus.COMPLETED and r.started_at and r.completed_at]
        
        avg_duration = 0
        if completed:
            durations = [(r.completed_at - r.started_at).total_seconds() for r in completed]
            avg_duration = sum(durations) / len(durations)
            
        by_status = {}
        for status in RunStatus:
            by_status[status.value] = sum(1 for r in runs if r.status == status)
            
        by_case = {}
        for run in runs:
            by_case[run.case_id] = by_case.get(run.case_id, 0) + 1
            
        return {
            "total_runs": len(runs),
            "by_status": by_status,
            "by_case": by_case,
            "avg_duration_seconds": avg_duration,
            "success_rate": (
                by_status.get("completed", 0) / len(runs) * 100
                if runs else 0
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_runner_service: Optional[AgentRunnerService] = None


def get_runner_service() -> AgentRunnerService:
    """Get or create the global runner service instance."""
    global _runner_service
    
    if _runner_service is None:
        _runner_service = AgentRunnerService()
        
    return _runner_service


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "RunStatus",
    "RunProgress",
    "AgentRun",
    "AgentRunnerService",
    "get_runner_service",
]
