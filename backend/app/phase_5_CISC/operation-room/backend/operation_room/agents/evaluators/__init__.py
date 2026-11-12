"""
Module Evaluators Package — Specialized evaluation agents for each forensic module.

This package contains dedicated evaluator agents for:
- Timeline Analysis
- Anomaly Detection
- Correlation Analysis
- Network Forensics
- Depth Analysis
- CRUD Operations

Each evaluator wraps the corresponding module's results with:
- Quality assessment
- Confidence scoring
- Finding extraction
- Cross-validation support

Author: NFLIP Development Team
Version: 1.0.0
"""

from operation_room.agents.evaluators.module_evaluators import (
    BaseModuleEvaluator,
    TimelineEvaluator,
    AnomalyEvaluator,
    CorrelationEvaluator,
    NetworkEvaluator,
    DepthEvaluator,
    CRUDEvaluator,
    EvaluatorFactory,
    MODULE_EVALUATORS,
)

__all__ = [
    "BaseModuleEvaluator",
    "TimelineEvaluator",
    "AnomalyEvaluator",
    "CorrelationEvaluator",
    "NetworkEvaluator",
    "DepthEvaluator",
    "CRUDEvaluator",
    "EvaluatorFactory",
    "MODULE_EVALUATORS",
]
