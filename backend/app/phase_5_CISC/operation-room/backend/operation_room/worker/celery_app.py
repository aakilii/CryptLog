"""
Celery Application Factory.

Configures the Celery worker with Redis as the broker and result backend.
This enables true async execution for long-running report generation tasks
that would otherwise timeout on HTTP connections.

Usage:
    # Start worker:
    celery -A app.worker.celery_app worker --loglevel=info --pool=solo

    # Dispatch task:
    from operation_room.worker.tasks import generate_report_task
    result = generate_report_task.delay(case_id, investigation_id, context)
"""

import os
import logging
from celery import Celery

logger = logging.getLogger(__name__)

# Redis URL from environment or docker-compose default
REDIS_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

celery_app = Celery(
    "nflip_worker",
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "operation_room.worker.tasks.generate_report_task": {"queue": "reports"},
        "operation_room.worker.tasks.generate_section_task": {"queue": "sections"},
    },

    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Result expiration (24 hours)
    result_expires=86400,

    # Dead Letter Queue — tasks that fail max_retries go here
    task_default_queue="default",

    # Timeouts
    task_soft_time_limit=300,   # 5 minutes soft limit
    task_time_limit=600,        # 10 minutes hard kill

    # Concurrency — solo pool for Windows compatibility
    worker_pool="solo",
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["operation_room.worker"])
