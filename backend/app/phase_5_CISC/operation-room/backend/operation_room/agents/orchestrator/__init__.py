"""
Orchestrator Module Init

Note: MasterOrchestrator has been consolidated into PipelineExecutor.
Import from operation_room.agents.integration_layer instead.
"""

# Re-export from integration_layer for backwards compatibility
from operation_room.agents.integration_layer import (
    PipelineExecutor,
    PipelineContext,
    PipelineStage,
    StageResult,
)

__all__ = [
    "PipelineExecutor",
    "PipelineContext",
    "PipelineStage",
    "StageResult",
]
