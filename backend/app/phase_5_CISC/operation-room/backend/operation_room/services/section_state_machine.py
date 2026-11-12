"""
Section State Machine — Phase 4.

Deterministic, event-driven state machine for parallel section generation.

Features:
- Dependency graph resolution for parallel execution
- Section-level status tracking
- Checkpoint/restore for resumability
- Timeout and retry handling
- Integration with report_agent.py pipeline
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from operation_room.services.canonical_contracts import (
    PipelineCheckpoint,
    ReportManifest,
    ReportStatus,
    SectionContract,
    SectionStatus,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# STATE MACHINE EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

class SectionEvent(str, Enum):
    """Events that trigger state transitions in a section."""
    START = "START"
    GENERATE_COMPLETE = "GENERATE_COMPLETE"
    GENERATE_FAILED = "GENERATE_FAILED"
    BIND_COMPLETE = "BIND_COMPLETE"
    BIND_FAILED = "BIND_FAILED"
    REVIEW_APPROVED = "REVIEW_APPROVED"
    REVIEW_REJECTED = "REVIEW_REJECTED"
    SKIP = "SKIP"
    RETRY = "RETRY"
    TIMEOUT = "TIMEOUT"


# Section status transition table
SECTION_TRANSITIONS = {
    SectionStatus.PENDING: {
        SectionEvent.START: SectionStatus.GENERATING,
        SectionEvent.SKIP: SectionStatus.SKIPPED,
    },
    SectionStatus.GENERATING: {
        SectionEvent.GENERATE_COMPLETE: SectionStatus.GENERATED,
        SectionEvent.GENERATE_FAILED: SectionStatus.FAILED,
        SectionEvent.TIMEOUT: SectionStatus.FAILED,
    },
    SectionStatus.GENERATED: {
        SectionEvent.START: SectionStatus.BINDING_EVIDENCE,
        SectionEvent.SKIP: SectionStatus.APPROVED,  # Skip binding
    },
    SectionStatus.BINDING_EVIDENCE: {
        SectionEvent.BIND_COMPLETE: SectionStatus.BOUND,
        SectionEvent.BIND_FAILED: SectionStatus.FAILED,
    },
    SectionStatus.BOUND: {
        SectionEvent.REVIEW_APPROVED: SectionStatus.APPROVED,
        SectionEvent.REVIEW_REJECTED: SectionStatus.GENERATING,  # Re-generate
        SectionEvent.SKIP: SectionStatus.APPROVED,  # Auto-approve
    },
    SectionStatus.REVIEW: {
        SectionEvent.REVIEW_APPROVED: SectionStatus.APPROVED,
        SectionEvent.REVIEW_REJECTED: SectionStatus.GENERATING,
    },
    SectionStatus.FAILED: {
        SectionEvent.RETRY: SectionStatus.PENDING,
    },
}


@dataclass
class SectionTask:
    """A section generation task with tracking metadata."""
    section: SectionContract
    retries: int = 0
    max_retries: int = 2
    timeout_seconds: float = 120.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None

    @property
    def elapsed_ms(self) -> int:
        if self.started_at is None:
            return 0
        end = self.completed_at or time.monotonic()
        return int((end - self.started_at) * 1000)

    @property
    def can_retry(self) -> bool:
        return self.retries < self.max_retries


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

# Type for section generator functions
SectionGenerator = Callable[
    [SectionContract, Dict[str, Any]],
    Coroutine[Any, Any, SectionContract]
]


class SectionStateMachine:
    """
    Deterministic state machine for parallel section generation.
    
    The state machine:
    1. Resolves dependency DAG from section contracts
    2. Executes independent sections in parallel
    3. Tracks section-level state transitions
    4. Creates checkpoints for resumability
    5. Handles timeouts and retries
    
    Usage:
        machine = SectionStateMachine(manifest)
        machine.set_generator(my_section_generator)
        
        await machine.execute_all(context)
        
        checkpoint = machine.create_checkpoint()
    """

    def __init__(
        self,
        manifest: ReportManifest,
        max_concurrency: int = 4,
    ):
        self.manifest = manifest
        self.max_concurrency = max_concurrency
        self._tasks: Dict[str, SectionTask] = {}
        self._generator: Optional[SectionGenerator] = None
        self._event_log: List[Dict[str, Any]] = []
        self._semaphore = asyncio.Semaphore(max_concurrency)

        # Build task registry
        for section in manifest.sections:
            self._tasks[section.section_key] = SectionTask(section=section)

    def set_generator(self, generator: SectionGenerator) -> None:
        """Set the section generator function."""
        self._generator = generator

    def transition(self, section_key: str, event: SectionEvent) -> SectionStatus:
        """
        Apply a state transition to a section.
        
        Raises ValueError for illegal transitions.
        """
        task = self._tasks.get(section_key)
        if not task:
            raise ValueError(f"Unknown section: {section_key}")

        current = task.section.status
        transitions = SECTION_TRANSITIONS.get(current, {})
        new_status = transitions.get(event)

        if new_status is None:
            raise ValueError(
                f"Illegal transition: {section_key} [{current.value}] + {event.value}. "
                f"Allowed events: {list(transitions.keys())}"
            )

        task.section.status = new_status
        self._log_event(section_key, event, current, new_status)

        return new_status

    async def execute_all(
        self,
        context: Dict[str, Any],
        auto_approve: bool = True,
    ) -> ReportManifest:
        """
        Execute all sections respecting dependencies.
        
        Args:
            context: Shared context (case_meta, module_summaries, etc.)
            auto_approve: If True, auto-approve bound sections
            
        Returns:
            Updated ReportManifest
        """
        if self._generator is None:
            raise ValueError("No section generator set. Call set_generator() first.")

        self.manifest.transition_to(ReportStatus.SECTION_GENERATION)

        # Build dependency sets
        dep_graph = self._build_dependency_graph()

        # Track completed sections
        completed: Set[str] = set()
        failed: Set[str] = set()

        while True:
            # Find ready sections (all deps satisfied, status PENDING)
            ready = []
            for key, task in self._tasks.items():
                if key in completed or key in failed:
                    continue
                if task.section.status not in (SectionStatus.PENDING, SectionStatus.FAILED):
                    continue
                deps = dep_graph.get(key, set())
                if deps.issubset(completed):
                    ready.append(key)

            if not ready:
                # Check if all done or stuck
                pending = [
                    k for k, t in self._tasks.items()
                    if k not in completed and k not in failed
                ]
                if not pending:
                    break
                # Check for deadlock
                if all(self._tasks[k].section.status == SectionStatus.FAILED for k in pending):
                    break
                # Some sections are still in progress (shouldn't happen in this flow)
                break

            # Execute ready sections in parallel (with concurrency limit)
            tasks = [
                self._execute_section(key, context, auto_approve)
                for key in ready
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for key, result in zip(ready, results):
                task = self._tasks[key]
                if isinstance(result, Exception):
                    logger.error(f"Section '{key}' failed: {result}")
                    task.error = str(result)
                    task.section.status = SectionStatus.FAILED
                    if task.can_retry:
                        task.retries += 1
                        task.section.status = SectionStatus.PENDING
                    else:
                        failed.add(key)
                elif task.section.status == SectionStatus.APPROVED:
                    completed.add(key)
                elif task.section.status == SectionStatus.FAILED:
                    if task.can_retry:
                        task.retries += 1
                        task.section.status = SectionStatus.PENDING
                    else:
                        failed.add(key)
                else:
                    completed.add(key)

        # Update manifest metrics
        self.manifest.update_rollup_metrics()
        self.manifest.compute_content_hash()

        return self.manifest

    async def _execute_section(
        self,
        section_key: str,
        context: Dict[str, Any],
        auto_approve: bool,
    ) -> None:
        """Execute a single section through the state machine."""
        task = self._tasks[section_key]

        async with self._semaphore:
            try:
                # START → GENERATING
                self.transition(section_key, SectionEvent.START)
                task.started_at = time.monotonic()

                # Generate content
                try:
                    updated_section = await asyncio.wait_for(
                        self._generator(task.section, context),
                        timeout=task.timeout_seconds,
                    )
                    task.section = updated_section
                    # GENERATING → GENERATED
                    self.transition(section_key, SectionEvent.GENERATE_COMPLETE)
                except asyncio.TimeoutError:
                    self.transition(section_key, SectionEvent.TIMEOUT)
                    task.error = f"Timeout after {task.timeout_seconds}s"
                    return
                except Exception as e:
                    self.transition(section_key, SectionEvent.GENERATE_FAILED)
                    task.error = str(e)
                    return

                # GENERATED → BINDING_EVIDENCE
                self.transition(section_key, SectionEvent.START)

                # Evidence binding is done by the generator
                if task.section.citations:
                    self.transition(section_key, SectionEvent.BIND_COMPLETE)
                else:
                    # Skip binding if no citations
                    self.transition(section_key, SectionEvent.BIND_FAILED)
                    # Even without citations, proceed if auto_approve
                    if auto_approve and task.can_retry:
                        task.section.status = SectionStatus.APPROVED
                    return

                # BOUND → APPROVED (auto-approve)
                if auto_approve:
                    self.transition(section_key, SectionEvent.SKIP)

                task.completed_at = time.monotonic()

            except Exception as e:
                logger.error(f"State machine error for '{section_key}': {e}")
                task.error = str(e)
                task.section.status = SectionStatus.FAILED

    def _build_dependency_graph(self) -> Dict[str, Set[str]]:
        """Build dependency graph from section contracts."""
        graph: Dict[str, Set[str]] = {}
        all_keys = {t.section.section_key for t in self._tasks.values()}

        for key, task in self._tasks.items():
            deps = set(task.section.dependencies) & all_keys
            graph[key] = deps

        return graph

    def create_checkpoint(self) -> PipelineCheckpoint:
        """Create a checkpoint for pipeline resumability."""
        completed = [
            k for k, t in self._tasks.items()
            if t.section.status == SectionStatus.APPROVED
        ]
        pending = [
            k for k, t in self._tasks.items()
            if t.section.status in (SectionStatus.PENDING, SectionStatus.GENERATING)
        ]
        failed = [
            k for k, t in self._tasks.items()
            if t.section.status == SectionStatus.FAILED
        ]

        return PipelineCheckpoint(
            report_id=self.manifest.report_id,
            case_id=self.manifest.case_id,
            current_status=self.manifest.status,
            completed_sections=completed,
            pending_sections=pending,
            failed_sections=failed,
            evidence_keys_bound=[
                c.evidence_key_id
                for task in self._tasks.values()
                for c in task.section.citations
            ],
            manifest_snapshot=self.manifest.to_json(),
        )

    def restore_from_checkpoint(self, checkpoint: PipelineCheckpoint) -> None:
        """Restore state from a checkpoint."""
        for key in checkpoint.completed_sections:
            if key in self._tasks:
                self._tasks[key].section.status = SectionStatus.APPROVED

        for key in checkpoint.failed_sections:
            if key in self._tasks:
                self._tasks[key].section.status = SectionStatus.FAILED

        logger.info(
            f"Restored checkpoint: {len(checkpoint.completed_sections)} completed, "
            f"{len(checkpoint.pending_sections)} pending, "
            f"{len(checkpoint.failed_sections)} failed"
        )

    def get_progress(self) -> Dict[str, Any]:
        """Get current execution progress."""
        total = len(self._tasks)
        completed = sum(
            1 for t in self._tasks.values()
            if t.section.status == SectionStatus.APPROVED
        )
        failed = sum(
            1 for t in self._tasks.values()
            if t.section.status == SectionStatus.FAILED
        )
        in_progress = sum(
            1 for t in self._tasks.values()
            if t.section.status in (SectionStatus.GENERATING, SectionStatus.BINDING_EVIDENCE)
        )

        return {
            "total_sections": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": total - completed - failed - in_progress,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
            "sections": {
                k: {
                    "status": t.section.status.value,
                    "retries": t.retries,
                    "elapsed_ms": t.elapsed_ms,
                    "error": t.error,
                }
                for k, t in self._tasks.items()
            },
        }

    def _log_event(
        self,
        section_key: str,
        event: SectionEvent,
        from_status: SectionStatus,
        to_status: SectionStatus,
    ) -> None:
        """Log a state transition event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "section_key": section_key,
            "event": event.value,
            "from": from_status.value,
            "to": to_status.value,
        }
        self._event_log.append(entry)
        logger.debug(
            f"[StateMachine] {section_key}: {from_status.value} → {to_status.value} ({event.value})"
        )

    def get_event_log(self) -> List[Dict[str, Any]]:
        """Get the full state transition event log."""
        return list(self._event_log)
