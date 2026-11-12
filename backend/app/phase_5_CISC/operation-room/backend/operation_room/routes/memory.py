"""
Oracle 26AI Memory Systems API Routes.

Phase 8: API endpoints for memory systems:
- Evidence vault
- Session memory
- Long-term memory / Calibration
- Procedural memory
- Validation memory
- Hybrid retrieval
- Learning loop / Feedback
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["Memory Systems"])


# ═══════════════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════════════

class AddEvidenceRequest(BaseModel):
    content: str = Field(..., description="Evidence content")
    evidence_type: str = Field(..., description="Type of evidence")
    source: str = Field(..., description="Source of evidence")
    confidence: float = Field(0.5, ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = None


class LinkEvidenceRequest(BaseModel):
    claim_id: str = Field(..., description="Claim/finding ID")
    evidence_id: str = Field(..., description="Evidence ID")
    link_type: str = Field("supports", description="supports, contradicts, related")
    confidence: float = Field(0.5, ge=0, le=1)


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    n_results: int = Field(10, ge=1, le=100)
    strategy: str = Field("hybrid_rrf", description="semantic, keyword, hybrid_linear, hybrid_rrf")
    semantic_weight: float = Field(0.7, ge=0, le=1)
    rerank: bool = Field(True)


class RecordHypothesisRequest(BaseModel):
    hypothesis_text: str = Field(..., description="Hypothesis statement")
    predicted_confidence: float = Field(0.5, ge=0, le=1)
    category: str = Field("general")


class ResolveHypothesisRequest(BaseModel):
    hypothesis_id: str
    outcome: str = Field(..., description="confirmed, rejected, partial, inconclusive")
    actual_confidence: Optional[float] = None
    supporting_evidence: Optional[List[str]] = None


class ValidationRequest(BaseModel):
    section_text: str = Field(..., description="Text to validate")
    section_name: str = Field("unknown")


class FeedbackRequest(BaseModel):
    feedback_type: str = Field(..., description="retrieval, hypothesis, report, general")
    sentiment: str = Field(..., description="positive, negative, neutral")
    target_id: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: str = ""
    context: Optional[Dict[str, Any]] = None


class RetrievalFeedbackRequest(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    relevant_ids: List[str]
    irrelevant_ids: List[str]


# ═══════════════════════════════════════════════════════════════
# Evidence Vault Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/evidence")
async def add_evidence(case_id: str, body: AddEvidenceRequest):
    """Add evidence to the vault with vector embedding."""
    from operation_room.services.evidence_vault import get_evidence_vault
    
    try:
        vault = get_evidence_vault(case_id)
        evidence_id = vault.add_evidence(
            content=body.content,
            evidence_type=body.evidence_type,
            source=body.source,
            confidence=body.confidence,
            metadata=body.metadata
        )
        
        return {
            "evidence_id": evidence_id,
            "case_id": case_id,
            "status": "created"
        }
        
    except Exception as e:
        logger.error(f"Failed to add evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/{case_id}/evidence/link")
async def link_evidence(case_id: str, body: LinkEvidenceRequest):
    """Link evidence to a claim/finding."""
    from operation_room.services.evidence_vault import get_evidence_vault
    
    try:
        vault = get_evidence_vault(case_id)
        link_id = vault.link_evidence(
            claim_id=body.claim_id,
            evidence_id=body.evidence_id,
            link_type=body.link_type,
            confidence=body.confidence
        )
        
        return {"link_id": link_id, "status": "linked"}
        
    except Exception as e:
        logger.error(f"Failed to link evidence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/evidence/search")
async def search_evidence(
    case_id: str,
    query: str = Query(...),
    n_results: int = Query(10, ge=1, le=100),
    semantic_weight: float = Query(0.7, ge=0, le=1)
):
    """Search evidence using hybrid search."""
    from operation_room.services.evidence_vault import get_evidence_vault
    
    try:
        vault = get_evidence_vault(case_id)
        results = vault.search_hybrid(
            query=query,
            n_results=n_results,
            semantic_weight=semantic_weight
        )
        
        return {
            "query": query,
            "results": [
                {
                    "evidence_id": r.evidence_id,
                    "content": r.content[:500],
                    "combined_score": r.combined_score,
                    "semantic_score": r.semantic_score,
                    "keyword_score": r.keyword_score,
                    "metadata": r.metadata
                }
                for r in results
            ],
            "total": len(results)
        }
        
    except Exception as e:
        logger.error(f"Evidence search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/evidence/{evidence_id}")
async def get_evidence(case_id: str, evidence_id: str):
    """Get evidence by ID."""
    from operation_room.services.evidence_vault import get_evidence_vault
    
    vault = get_evidence_vault(case_id)
    evidence = vault.get_evidence(evidence_id)
    
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    return {
        "evidence_id": evidence.evidence_id,
        "content": evidence.content,
        "evidence_type": evidence.evidence_type,
        "source": evidence.source,
        "confidence": evidence.confidence,
        "hash": evidence.hash,
        "created_at": evidence.created_at.isoformat()
    }


@router.get("/cases/{case_id}/evidence/stats")
async def get_evidence_stats(case_id: str):
    """Get evidence vault statistics."""
    from operation_room.services.evidence_vault import get_evidence_vault
    
    vault = get_evidence_vault(case_id)
    return vault.get_stats()


# ═══════════════════════════════════════════════════════════════
# Session Memory Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/sessions/{session_id}/turns")
async def add_turn(case_id: str, session_id: str, role: str, content: str, phase: str = "discovery"):
    """Add a conversation turn to session memory."""
    from operation_room.services.session_memory import get_session_memory, InvestigationPhase
    
    try:
        memory = get_session_memory(case_id, session_id)
        
        # Parse phase
        try:
            phase_enum = InvestigationPhase(phase)
        except:
            phase_enum = InvestigationPhase.DISCOVERY
        
        turn_id = memory.add_turn(
            role=role,
            content=content,
            phase=phase_enum
        )
        
        return {"turn_id": turn_id, "session_id": session_id}
        
    except Exception as e:
        logger.error(f"Failed to add turn: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/sessions/{session_id}/context")
async def get_session_context(
    case_id: str,
    session_id: str,
    query: str = Query(""),
    max_tokens: int = Query(4000)
):
    """Get relevant context for a query from session memory."""
    from operation_room.services.session_memory import get_session_memory
    
    memory = get_session_memory(case_id, session_id)
    
    if query:
        turns = memory.get_context_for_query(query, max_tokens=max_tokens)
    else:
        turns = memory.get_recent_turns(n_turns=10)
    
    return {
        "session_id": session_id,
        "turns": [
            {
                "turn_id": t.turn_id,
                "role": t.role,
                "content": t.content[:500],
                "phase": t.phase.value,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None
            }
            for t in turns
        ],
        "total": len(turns)
    }


@router.get("/cases/{case_id}/sessions/{session_id}/stats")
async def get_session_stats(case_id: str, session_id: str):
    """Get session memory statistics."""
    from operation_room.services.session_memory import get_session_memory
    
    memory = get_session_memory(case_id, session_id)
    return memory.get_stats()


# ═══════════════════════════════════════════════════════════════
# Long-term Memory / Calibration Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/hypotheses")
async def record_hypothesis(case_id: str, body: RecordHypothesisRequest):
    """Record a new hypothesis for calibration tracking."""
    from operation_room.services.longterm_memory import get_long_term_memory
    
    try:
        memory = get_long_term_memory()
        hypothesis_id = memory.record_hypothesis(
            case_id=case_id,
            hypothesis_text=body.hypothesis_text,
            predicted_confidence=body.predicted_confidence,
            category=body.category
        )
        
        return {"hypothesis_id": hypothesis_id, "status": "recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record hypothesis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hypotheses/{hypothesis_id}/resolve")
async def resolve_hypothesis(hypothesis_id: str, body: ResolveHypothesisRequest):
    """Resolve a hypothesis with its outcome."""
    from operation_room.services.longterm_memory import get_long_term_memory, HypothesisOutcome
    
    try:
        memory = get_long_term_memory()
        
        outcome = HypothesisOutcome(body.outcome)
        
        success = memory.resolve_hypothesis(
            hypothesis_id=hypothesis_id,
            outcome=outcome,
            actual_confidence=body.actual_confidence,
            supporting_evidence=body.supporting_evidence
        )
        
        return {"hypothesis_id": hypothesis_id, "outcome": body.outcome, "resolved": success}
        
    except Exception as e:
        logger.error(f"Failed to resolve hypothesis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration")
async def get_calibration_metrics(
    case_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """Get hypothesis calibration metrics."""
    from operation_room.services.longterm_memory import get_long_term_memory
    
    memory = get_long_term_memory()
    metrics = memory.get_calibration_metrics(case_id=case_id, category=category)
    
    return {
        "total_hypotheses": metrics.total_hypotheses,
        "confirmed": metrics.confirmed,
        "rejected": metrics.rejected,
        "partial": metrics.partial,
        "inconclusive": metrics.inconclusive,
        "mean_predicted_confidence": round(metrics.mean_predicted_confidence, 3),
        "mean_actual_confidence": round(metrics.mean_actual_confidence, 3),
        "calibration_error": round(metrics.calibration_error, 3),
        "brier_score": round(metrics.brier_score, 4),
        "by_category": metrics.by_category
    }


@router.post("/hypotheses/suggest-confidence")
async def suggest_confidence(
    hypothesis_text: str,
    initial_confidence: float,
    category: str = "general"
):
    """Get calibration-adjusted confidence suggestion."""
    from operation_room.services.longterm_memory import get_long_term_memory
    
    memory = get_long_term_memory()
    suggested, explanation = memory.suggest_confidence_adjustment(
        hypothesis_text=hypothesis_text,
        initial_confidence=initial_confidence,
        category=category
    )
    
    return {
        "initial_confidence": initial_confidence,
        "suggested_confidence": round(suggested, 3),
        "adjustment": round(suggested - initial_confidence, 3),
        "explanation": explanation
    }


# ═══════════════════════════════════════════════════════════════
# Procedural Memory Routes
# ═══════════════════════════════════════════════════════════════

@router.get("/templates")
async def list_templates(
    template_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """List available procedural templates."""
    from operation_room.services.procedural_memory import get_procedural_memory, TemplateType
    
    memory = get_procedural_memory()
    
    ttype = TemplateType(template_type) if template_type else None
    templates = memory.list_templates(template_type=ttype, category=category)
    
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "type": t.template_type.value,
                "category": t.category,
                "description": t.description,
                "steps_count": len(t.steps),
                "success_rate": round(t.success_rate, 3),
                "usage_count": t.usage_count
            }
            for t in templates
        ],
        "total": len(templates)
    }


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific template."""
    from operation_room.services.procedural_memory import get_procedural_memory
    
    memory = get_procedural_memory()
    template = memory.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "template_id": template.template_id,
        "name": template.name,
        "type": template.template_type.value,
        "scope": template.scope.value,
        "category": template.category,
        "description": template.description,
        "steps": [
            {
                "step_number": s.step_number,
                "action": s.action,
                "description": s.description,
                "expected_output": s.expected_output
            }
            for s in template.steps
        ],
        "expected_duration_minutes": template.expected_duration_minutes,
        "confidence_boost": template.confidence_boost,
        "success_rate": template.success_rate,
        "usage_count": template.usage_count
    }


@router.post("/templates/recommend")
async def recommend_templates(
    context: str,
    current_phase: str = "discovery",
    case_category: Optional[str] = None
):
    """Get template recommendations for current context."""
    from operation_room.services.procedural_memory import get_procedural_memory
    
    memory = get_procedural_memory()
    recommendations = memory.recommend_templates(
        context=context,
        current_phase=current_phase,
        case_category=case_category
    )
    
    return {
        "recommendations": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "type": t.template_type.value,
                "description": t.description,
                "relevance_score": round(score, 3),
                "steps_count": len(t.steps)
            }
            for t, score in recommendations
        ]
    }


# ═══════════════════════════════════════════════════════════════
# Validation Memory Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/validate")
async def validate_section(case_id: str, body: ValidationRequest):
    """Extract and validate claims from a section."""
    from operation_room.services.validation_memory import get_validation_memory
    
    try:
        memory = get_validation_memory(case_id)
        result = memory.extract_and_validate_section(
            section_text=body.section_text,
            section_name=body.section_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/validation/summary")
async def get_validation_summary(case_id: str):
    """Get validation summary for a case."""
    from operation_room.services.validation_memory import get_validation_memory
    
    memory = get_validation_memory(case_id)
    return memory.get_validation_summary()


@router.get("/cases/{case_id}/validation/unsupported")
async def get_unsupported_claims(case_id: str):
    """Get unsupported claims (advisory warnings)."""
    from operation_room.services.validation_memory import get_validation_memory
    
    memory = get_validation_memory(case_id)
    return {"unsupported_claims": memory.get_unsupported_claims()}


@router.get("/cases/{case_id}/validation/contradictions")
async def get_contradictions(case_id: str):
    """Get unresolved contradictions."""
    from operation_room.services.validation_memory import get_validation_memory
    
    memory = get_validation_memory(case_id)
    return {"contradictions": memory.get_unresolved_contradictions()}


# ═══════════════════════════════════════════════════════════════
# Hybrid Retrieval Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/retrieve")
async def hybrid_retrieve(case_id: str, body: SearchRequest):
    """Perform hybrid retrieval with optional reranking."""
    from operation_room.services.hybrid_retriever import get_hybrid_retriever, RetrievalStrategy, CollectionType
    
    try:
        retriever = get_hybrid_retriever(
            case_id=case_id,
            collection_type=CollectionType.EVIDENCE,
            enable_reranking=body.rerank
        )
        
        strategy = RetrievalStrategy(body.strategy)
        
        results, metrics = retriever.retrieve(
            query=body.query,
            n_results=body.n_results,
            strategy=strategy,
            semantic_weight=body.semantic_weight,
            rerank=body.rerank
        )
        
        return {
            "query": body.query,
            "results": [
                {
                    "doc_id": r.doc_id,
                    "content": r.content[:500],
                    "score": round(r.score, 4),
                    "semantic_score": round(r.semantic_score, 4),
                    "keyword_score": round(r.keyword_score, 4),
                    "rerank_score": round(r.rerank_score, 4) if r.rerank_score else None,
                    "method": r.retrieval_method
                }
                for r in results
            ],
            "metrics": {
                "total_retrieved": metrics.total_retrieved,
                "semantic_candidates": metrics.semantic_candidates,
                "keyword_candidates": metrics.keyword_candidates,
                "reranked": metrics.reranked,
                "avg_score": round(metrics.avg_score, 4),
                "retrieval_time_ms": round(metrics.retrieval_time_ms, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Learning Loop / Feedback Routes
# ═══════════════════════════════════════════════════════════════

@router.post("/feedback")
async def record_feedback(case_id: Optional[str], body: FeedbackRequest):
    """Record user feedback."""
    from operation_room.services.learning_loop import (
        get_learning_loop, FeedbackType, FeedbackSentiment
    )
    
    try:
        loop = get_learning_loop()
        
        feedback_id = loop.record_feedback(
            feedback_type=FeedbackType(body.feedback_type),
            sentiment=FeedbackSentiment(body.sentiment),
            case_id=case_id,
            target_id=body.target_id,
            rating=body.rating,
            comment=body.comment,
            context=body.context
        )
        
        return {"feedback_id": feedback_id, "status": "recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/{case_id}/feedback/retrieval")
async def record_retrieval_feedback(case_id: str, body: RetrievalFeedbackRequest):
    """Record feedback on retrieval results."""
    from operation_room.services.learning_loop import get_learning_loop
    
    try:
        loop = get_learning_loop()
        
        feedback_id = loop.record_retrieval_feedback(
            case_id=case_id,
            query=body.query,
            results=body.results,
            relevant_ids=body.relevant_ids,
            irrelevant_ids=body.irrelevant_ids
        )
        
        return {"feedback_id": feedback_id, "status": "recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record retrieval feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learning/metrics")
async def get_learning_metrics(days: int = Query(30, ge=1, le=365)):
    """Get learning loop metrics."""
    from operation_room.services.learning_loop import get_learning_loop
    
    loop = get_learning_loop()
    return loop.get_stats()


@router.get("/learning/recommendations")
async def get_improvement_recommendations():
    """Get system improvement recommendations."""
    from operation_room.services.learning_loop import get_learning_loop
    
    loop = get_learning_loop()
    return {"recommendations": loop.get_improvement_recommendations()}


@router.post("/learning/snapshot")
async def save_metrics_snapshot():
    """Save current learning metrics as a snapshot."""
    from operation_room.services.learning_loop import get_learning_loop
    
    loop = get_learning_loop()
    snapshot_id = loop.save_metrics_snapshot()
    
    return {"snapshot_id": snapshot_id, "status": "saved"}


# ═══════════════════════════════════════════════════════════════
# System Stats Route
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_memory_system_stats():
    """Get overall memory system statistics."""
    from operation_room.services.longterm_memory import get_long_term_memory
    from operation_room.services.procedural_memory import get_procedural_memory
    from operation_room.services.learning_loop import get_learning_loop
    
    try:
        ltm = get_long_term_memory()
        pm = get_procedural_memory()
        ll = get_learning_loop()
        
        return {
            "longterm_memory": ltm.get_stats(),
            "procedural_memory": pm.get_stats(),
            "learning_loop": ll.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
