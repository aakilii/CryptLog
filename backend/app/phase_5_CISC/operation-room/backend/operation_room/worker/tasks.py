"""
Celery Tasks for Report Generation.

These tasks run in the Celery worker process, decoupled from the
FastAPI HTTP layer. This prevents HTTP timeouts when generating
150+ page reports.

Key tasks:
- generate_report_task: Full pipeline via CanonicalPipeline
- generate_section_task: Single section generation (for retry)

Status updates are published to Redis Pub/Sub so the FastAPI
WebSocket gateway can stream them to the browser.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from operation_room.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _publish_status(
    investigation_id: str,
    event_type: str,
    data: Dict[str, Any],
    progress: float = 0.0,
) -> None:
    """Publish status update to Redis Pub/Sub for WebSocket relay."""
    try:
        import redis
        redis_url = celery_app.conf.broker_url
        r = redis.from_url(redis_url)
        r.publish(
            f"nflip:report:{investigation_id}",
            json.dumps({
                "event_type": event_type,
                "data": data,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }),
        )
    except Exception as e:
        logger.warning(f"Failed to publish status to Redis: {e}")


@celery_app.task(
    name="operation_room.worker.tasks.generate_report_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    queue="reports",
)
def generate_report_task(
    self,
    case_id: str,
    investigation_id: str,
    scenario: str = "",
    case_type: str = "general",
    investigation_data: Optional[Dict[str, Any]] = None,
    module_results: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a complete forensic report via the Canonical Pipeline.
    
    This runs in the Celery worker, fully decoupled from HTTP.
    Status updates go to Redis Pub/Sub → WebSocket gateway → browser.
    
    Returns:
        Report manifest dict on success
    """
    import asyncio
    
    start_time = time.monotonic()
    job_id = self.request.id or "unknown"
    
    logger.info(
        f"[CeleryWorker] Starting report generation job={job_id} "
        f"case={case_id} investigation={investigation_id}"
    )
    
    _publish_status(investigation_id, "job_started", {
        "job_id": job_id,
        "case_id": case_id,
        "stage": "initializing",
    }, 0.05)
    
    try:
        from operation_room.services.canonical_pipeline import CanonicalPipeline
        
        pipeline = CanonicalPipeline(
            case_id=case_id,
            config={
                "enforce_admissibility": True,
                "auto_approve_sections": True,
                "include_ai_narratives": True,
                "export_format": "pdf",
            },
        )
        
        # Run async pipeline in sync Celery context
        async def _run() -> Dict[str, Any]:
            last_event = None
            async for event in pipeline.execute(
                scenario=scenario,
                case_type=case_type,
                investigation_data=investigation_data or {},
                module_results=module_results or {},
                metadata=metadata or {},
            ):
                last_event = event
                _publish_status(
                    investigation_id,
                    event.event_type,
                    event.data,
                    event.progress,
                )
            
            manifest = pipeline.get_manifest()
            if manifest:
                return manifest.to_dict()
            return {"error": "No manifest generated"}
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(_run())
        
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        _publish_status(investigation_id, "job_completed", {
            "job_id": job_id,
            "elapsed_ms": elapsed_ms,
            "status": result.get("status", "unknown"),
        }, 1.0)
        
        logger.info(
            f"[CeleryWorker] Report generation complete job={job_id} "
            f"elapsed={elapsed_ms}ms"
        )
        
        return result
        
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        _publish_status(investigation_id, "job_failed", {
            "job_id": job_id,
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
            "retry_count": self.request.retries,
        }, 0.0)
        
        logger.error(
            f"[CeleryWorker] Report generation failed job={job_id}: {exc}",
            exc_info=True,
        )
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(
                exc=exc,
                countdown=30 * (2 ** self.request.retries),
            )
        
        return {
            "error": str(exc),
            "job_id": job_id,
            "status": "FAILED",
            "retry_count": self.request.retries,
        }


@celery_app.task(
    name="operation_room.worker.tasks.generate_section_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    queue="sections",
)
def generate_section_task(
    self,
    case_id: str,
    section_key: str,
    section_title: str,
    evidence_keys: list,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a single report section.
    
    Used for retry of individual failed sections from the
    SectionStateMachine checkpoint/restore flow.
    """
    import asyncio
    
    job_id = self.request.id or "unknown"
    
    try:
        from operation_room.services.evidence_binder import get_evidence_binder
        from operation_room.services.canonical_contracts import SectionContract, SectionStatus
        
        binder = get_evidence_binder(case_id)
        
        # Build section contract
        section = SectionContract(
            section_key=section_key,
            section_title=section_title,
            status=SectionStatus.PENDING,
        )
        
        # Build prompt
        prompt = binder.build_evidence_prompt(
            section_key=section_key,
            section_title=section_title,
            evidence_keys=evidence_keys,
            case_context=context.get("case_context"),
        )
        
        # Call LLM
        async def _generate():
            from operation_room.services.llm_provider import get_llm
            llm = get_llm()
            
            # Phase 4: Primary Draft Pass
            response = await llm.ainvoke(prompt)
            draft_content = response.content if hasattr(response, "content") else str(response)
            
            # Phase 4: Red Team Critique Pass (temperature=0.0)
            critique_prompt = f"""
            Act as an adversarial forensic peer-reviewer. Critique the following text for hallucinated facts, illogical statements, or missing required evidence citations.
            Fix any errors, enhance clarity, ensure zero hallucinations, and return ONLY the corrected, polished pure text.
            Do not acknowledge this prompt.
            DRAFT:
            {draft_content}
            """
            logger.info(f"[Celery] Running Phase 4 Red Team Critique on {section_key}")
            # Ensure we fallback gracefully depending on the llm provider method signatures
            if hasattr(llm, "generate"):
                 critique_response = await llm.generate(critique_prompt, max_tokens=1000, temperature=0.0)
                 return critique_response.strip()
            else:
                 # Default Langchain invoke
                 critique_response = await llm.ainvoke(critique_prompt, temperature=0.0)
                 return critique_response.content if hasattr(critique_response, "content") else str(critique_response)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        content = loop.run_until_complete(_generate())
        
        # Bind citations
        section = binder.bind_citations(section, content)
        
        return {
            "section_key": section_key,
            "status": section.status.value,
            "content": section.content,
            "citations": len(section.citations),
            "orphans": len(section.orphan_citations),
            "word_count": section.word_count,
        }
        
    except Exception as exc:
        logger.error(f"[CeleryWorker] Section '{section_key}' failed: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
        return {"section_key": section_key, "status": "FAILED", "error": str(exc)}
