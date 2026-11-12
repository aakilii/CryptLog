"""
Clarification Tools — Interactive clarification workflow.

This module provides tools for the clarification workflow:
- investigation.clarify: Answer clarification questions
- investigation.ask: Generate new clarification questions
- investigation.validate: Validate investigation readiness

The clarification workflow ensures the investigation has sufficient
context before proceeding with analysis.

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..schemas import (
    InvestigationContext,
    InvestigationStatus,
    ClarificationQuestion,
    ClarificationPriority,
    TimeRange,
    EntityReference,
)
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ANSWER VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════════

class AnswerValidator:
    """Validates answers to clarification questions."""
    
    @staticmethod
    def validate_time_range(answer: str) -> Optional[TimeRange]:
        """Parse and validate time range answer."""
        now = datetime.now(timezone.utc)
        
        # Predefined ranges
        if "24 hour" in answer.lower() or "last day" in answer.lower():
            return TimeRange(
                start=now - timedelta(hours=24),
                end=now
            )
        elif "7 day" in answer.lower() or "week" in answer.lower():
            return TimeRange(
                start=now - timedelta(days=7),
                end=now
            )
        elif "30 day" in answer.lower() or "month" in answer.lower():
            return TimeRange(
                start=now - timedelta(days=30),
                end=now
            )
        elif "90 day" in answer.lower() or "quarter" in answer.lower():
            return TimeRange(
                start=now - timedelta(days=90),
                end=now
            )
        
        # Try to parse custom date range
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        dates = re.findall(date_pattern, answer)
        if len(dates) >= 2:
            try:
                start = datetime.fromisoformat(dates[0] + "T00:00:00+00:00")
                end = datetime.fromisoformat(dates[1] + "T23:59:59+00:00")
                return TimeRange(start=start, end=end)
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def validate_ownership(answer: str) -> Optional[str]:
        """Parse ownership answer."""
        answer_lower = answer.lower()
        if "suspect" in answer_lower:
            return "suspect"
        elif "organization" in answer_lower or "company" in answer_lower or "corp" in answer_lower:
            return "organization"
        elif "victim" in answer_lower:
            return "victim"
        elif "unknown" in answer_lower:
            return "unknown"
        return answer
    
    @staticmethod
    def validate_channels(answer: str) -> List[str]:
        """Parse channel selection answer."""
        channels = []
        answer_lower = answer.lower()
        
        if "usb" in answer_lower or "removable" in answer_lower:
            channels.append("USB")
        if "network" in answer_lower or "email" in answer_lower:
            channels.append("Network")
            channels.append("Email")
        if "bluetooth" in answer_lower or "bt" in answer_lower:
            channels.append("Bluetooth")
        if "all" in answer_lower:
            channels = ["USB", "Network", "Email", "Bluetooth", "Cloud"]
        
        return channels if channels else [answer]
    
    @staticmethod
    def validate_depth(answer: str) -> str:
        """Parse investigation depth answer."""
        answer_lower = answer.lower()
        if "quick" in answer_lower or "triage" in answer_lower:
            return "quick"
        elif "deep" in answer_lower or "thorough" in answer_lower or "forensic" in answer_lower:
            return "deep"
        else:
            return "standard"
    
    @staticmethod
    def validate_suspect(answer: str) -> Optional[EntityReference]:
        """Parse suspect identification answer."""
        answer_lower = answer.lower()
        
        if "no" in answer_lower or "not yet" in answer_lower or "unknown" in answer_lower:
            return None
        
        # Try to extract username/ID
        # Remove common prefixes
        cleaned = answer.replace("Yes", "").replace("yes", "").strip()
        cleaned = cleaned.strip("()[]{}:,")
        
        if cleaned:
            return EntityReference(
                entity_type="user",
                entity_value=cleaned,
                role="suspect"
            )
        
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLARIFICATION PROCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

class ClarificationProcessor:
    """
    Processes clarification answers and updates investigation context.
    """
    
    def __init__(self, investigation: InvestigationContext):
        self.investigation = investigation
    
    def process_answer(
        self,
        question_id: str,
        answer: str
    ) -> Dict[str, Any]:
        """
        Process an answer to a clarification question.
        
        Returns dict with processing result and any context updates.
        """
        # Find the question
        question = None
        for q in self.investigation.clarification_questions:
            if q.question_id == question_id:
                question = q
                break
        
        if not question:
            return {"success": False, "error": f"Question not found: {question_id}"}
        
        # Mark as answered
        question.answered = True
        question.answer = answer
        
        # Process based on question context
        context_updates = {}
        processed_value = None
        
        question_lower = question.question.lower()
        
        if "time range" in question_lower or "time period" in question_lower:
            time_range = AnswerValidator.validate_time_range(answer)
            if time_range:
                context_updates["time_range"] = time_range
                processed_value = {
                    "start": time_range.start.isoformat(),
                    "end": time_range.end.isoformat()
                }
        
        elif "own" in question_lower or "control" in question_lower:
            ownership = AnswerValidator.validate_ownership(answer)
            # Update entity roles based on ownership
            for entity in self.investigation.entities:
                if entity.entity_type == "system":
                    if ownership == "suspect":
                        entity.role = "suspect"
                    elif ownership == "organization":
                        entity.role = "witness"
            processed_value = ownership
        
        elif "channel" in question_lower or "transfer" in question_lower:
            channels = AnswerValidator.validate_channels(answer)
            # This might affect source selection
            processed_value = channels
        
        elif "suspect" in question_lower or "user of interest" in question_lower:
            suspect = AnswerValidator.validate_suspect(answer)
            if suspect:
                self.investigation.entities.append(suspect)
                processed_value = suspect.model_dump()
        
        elif "depth" in question_lower or "level" in question_lower:
            depth = AnswerValidator.validate_depth(answer)
            # Map depth to mode
            if depth == "quick":
                context_updates["mode"] = "focused"
            elif depth == "deep":
                context_updates["mode"] = "brute_force"
            processed_value = depth
        
        # Apply context updates
        for key, value in context_updates.items():
            setattr(self.investigation, key, value)
        
        return {
            "success": True,
            "question_id": question_id,
            "answer": answer,
            "processed_value": processed_value,
            "context_updates": {k: str(v) for k, v in context_updates.items()},
            "remaining_questions": len([
                q for q in self.investigation.clarification_questions 
                if not q.answered
            ])
        }
    
    def check_readiness(self) -> Dict[str, Any]:
        """
        Check if investigation is ready to proceed.
        
        Returns readiness status and any blocking issues.
        """
        blocking_unanswered = [
            q for q in self.investigation.clarification_questions
            if not q.answered and q.priority == ClarificationPriority.BLOCKING
        ]
        
        high_unanswered = [
            q for q in self.investigation.clarification_questions
            if not q.answered and q.priority == ClarificationPriority.HIGH
        ]
        
        issues = []
        
        if blocking_unanswered:
            issues.append({
                "level": "blocking",
                "message": f"{len(blocking_unanswered)} blocking question(s) unanswered",
                "questions": [q.question_id for q in blocking_unanswered]
            })
        
        if not self.investigation.time_range:
            issues.append({
                "level": "warning",
                "message": "No time range specified (will use default)"
            })
        
        if not self.investigation.selected_sources:
            issues.append({
                "level": "warning",
                "message": "No data sources selected (will use all available)"
            })
        
        if not self.investigation.objectives:
            issues.append({
                "level": "warning",
                "message": "No objectives defined"
            })
        
        is_ready = len(blocking_unanswered) == 0
        
        return {
            "ready": is_ready,
            "blocking_questions": len(blocking_unanswered),
            "high_priority_unanswered": len(high_unanswered),
            "total_unanswered": len([
                q for q in self.investigation.clarification_questions
                if not q.answered
            ]),
            "issues": issues,
            "can_proceed_with_defaults": is_ready
        }
    
    def generate_followup_questions(self) -> List[ClarificationQuestion]:
        """
        Generate follow-up questions based on current context.
        """
        followups = []
        
        # Check for vague time range
        if self.investigation.time_range:
            days = (self.investigation.time_range.end - self.investigation.time_range.start).days
            if days > 30:
                followups.append(ClarificationQuestion(
                    question=f"The time range covers {days} days. Can you narrow it down to specific dates of interest?",
                    context="Narrower time ranges improve analysis speed and accuracy.",
                    priority=ClarificationPriority.MEDIUM,
                    options=[
                        "Keep current range",
                        "Focus on last 7 days",
                        "Specify custom dates"
                    ]
                ))
        
        # Check for multiple suspects
        suspects = [e for e in self.investigation.entities if e.role == "suspect"]
        if len(suspects) > 1:
            followups.append(ClarificationQuestion(
                question=f"Multiple suspects identified ({len(suspects)}). Should the investigation focus on a primary suspect?",
                context="Focusing on a primary suspect can make the investigation more efficient.",
                priority=ClarificationPriority.MEDIUM,
                options=[
                    "Investigate all equally",
                    "Focus on primary suspect",
                    "Investigate sequentially"
                ]
            ))
        
        return followups


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="investigation.clarify",
    category=ToolCategory.INVESTIGATION,
    description="Answer clarification questions for an investigation. Processes answers and updates investigation context.",
    requires_case_id=False,
    tags={"investigation", "clarify", "question"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="INVESTIGATION_CLARIFY")
async def answer_clarification(
    investigation_id: str,
    answers: Dict[str, str],
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Answer one or more clarification questions.
    
    Args:
        investigation_id: Investigation to update
        answers: Dict of question_id -> answer
    
    Returns:
        Processing results and updated readiness status
    """
    # Get investigation
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    processor = ClarificationProcessor(inv)
    results = []
    
    # Process each answer
    for question_id, answer in answers.items():
        result = processor.process_answer(question_id, answer)
        results.append(result)
    
    # Save updated investigation
    InvestigationStore.save(inv)
    
    # Check readiness
    readiness = processor.check_readiness()
    
    # Generate follow-up questions if needed
    followups = processor.generate_followup_questions()
    if followups:
        inv.clarification_questions.extend(followups)
        InvestigationStore.save(inv)
    
    # Update status if ready
    if readiness["ready"] and inv.status == InvestigationStatus.AWAITING_CLARIFICATION:
        inv.status = InvestigationStatus.PLANNING
        InvestigationStore.save(inv)
    
    return {
        "success": True,
        "investigation_id": investigation_id,
        "answers_processed": len(results),
        "results": results,
        "readiness": readiness,
        "followup_questions": [q.model_dump() for q in followups] if followups else [],
        "status": enum_value(inv.status),
        "next_action": (
            "Use investigation.plan to create investigation plan"
            if readiness["ready"]
            else "Answer remaining blocking questions"
        )
    }


@mcp_tool(
    name="investigation.ask",
    category=ToolCategory.INVESTIGATION,
    description="Add new clarification questions to an investigation.",
    requires_case_id=False,
    tags={"investigation", "clarify", "question"}
)
@audit_trail(operation="INVESTIGATION_ASK")
async def add_clarification_question(
    investigation_id: str,
    question: str,
    context: Optional[str] = None,
    priority: str = "high",
    options: Optional[List[str]] = None,
    default_value: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Add a new clarification question to an investigation.
    
    Args:
        investigation_id: Investigation to update
        question: The question text
        context: Why this question is being asked
        priority: Question priority (blocking, high, medium, low)
        options: Multiple choice options
        default_value: Default answer if not provided
    
    Returns:
        Created question and updated question list
    """
    # Get investigation
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    # Map priority string to enum
    priority_map = {
        "blocking": ClarificationPriority.BLOCKING,
        "high": ClarificationPriority.HIGH,
        "medium": ClarificationPriority.MEDIUM,
        "low": ClarificationPriority.LOW
    }
    priority_enum = priority_map.get(priority.lower(), ClarificationPriority.HIGH)
    
    # Create question
    new_question = ClarificationQuestion(
        question=question,
        context=context,
        priority=priority_enum,
        options=options,
        default_value=default_value
    )
    
    # Add to investigation
    inv.clarification_questions.append(new_question)
    
    # Update status if was planning/executing
    if inv.status in [InvestigationStatus.PLANNING, InvestigationStatus.EXECUTING]:
        if priority_enum == ClarificationPriority.BLOCKING:
            inv.status = InvestigationStatus.AWAITING_CLARIFICATION
    
    InvestigationStore.save(inv)
    
    return {
        "success": True,
        "question_id": new_question.question_id,
        "question": new_question.model_dump(),
        "total_questions": len(inv.clarification_questions),
        "unanswered_count": len([q for q in inv.clarification_questions if not q.answered]),
        "status": enum_value(inv.status)
    }


@mcp_tool(
    name="investigation.validate",
    category=ToolCategory.INVESTIGATION,
    description="Validate that an investigation has sufficient context to proceed.",
    requires_case_id=False,
    tags={"investigation", "validate", "readiness"}
)
@audit_trail(operation="INVESTIGATION_VALIDATE")
async def validate_investigation(
    investigation_id: str,
    apply_defaults: bool = False,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Validate investigation readiness.
    
    Args:
        investigation_id: Investigation to validate
        apply_defaults: Whether to apply default values for unanswered questions
    
    Returns:
        Validation results and readiness status
    """
    # Get investigation
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    processor = ClarificationProcessor(inv)
    
    # Apply defaults if requested
    if apply_defaults:
        for q in inv.clarification_questions:
            if not q.answered and q.default_value:
                result = processor.process_answer(q.question_id, q.default_value)
                logger.info(f"Applied default for {q.question_id}: {q.default_value}")
        InvestigationStore.save(inv)
    
    # Check readiness
    readiness = processor.check_readiness()
    
    # Build validation report
    validation = {
        "has_scenario": bool(inv.scenario),
        "has_objectives": len(inv.objectives) > 0,
        "has_entities": len(inv.entities) > 0,
        "has_time_range": inv.time_range is not None,
        "has_sources": len(inv.selected_sources) > 0,
        "blocking_questions_answered": readiness["blocking_questions"] == 0,
        "mode_selected": inv.mode in ["brute_force", "focused", "hybrid"]
    }
    
    all_valid = all(validation.values())
    
    # Update status if ready
    if all_valid and inv.status == InvestigationStatus.AWAITING_CLARIFICATION:
        inv.status = InvestigationStatus.PLANNING
        InvestigationStore.save(inv)
    
    return {
        "success": True,
        "investigation_id": investigation_id,
        "valid": all_valid,
        "validation": validation,
        "readiness": readiness,
        "status": enum_value(inv.status),
        "summary": {
            "scenario_length": len(inv.scenario),
            "objective_count": len(inv.objectives),
            "entity_count": len(inv.entities),
            "source_count": len(inv.selected_sources),
            "time_range": (
                f"{inv.time_range.start.date()} to {inv.time_range.end.date()}"
                if inv.time_range else "Not set"
            ),
            "mode": inv.mode
        },
        "next_action": (
            "Use investigation.plan to create investigation plan"
            if all_valid
            else "Address validation issues before proceeding"
        )
    }


@mcp_tool(
    name="investigation.questions",
    category=ToolCategory.INVESTIGATION,
    description="Get pending clarification questions for an investigation.",
    requires_case_id=False,
    tags={"investigation", "clarify", "question", "list"}
)
async def list_clarification_questions(
    investigation_id: str,
    only_unanswered: bool = True,
    priority_filter: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    List clarification questions for an investigation.
    
    Args:
        investigation_id: Investigation ID
        only_unanswered: Only return unanswered questions
        priority_filter: Filter by priority (blocking, high, medium, low)
    
    Returns:
        List of questions
    """
    # Get investigation
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    questions = inv.clarification_questions
    
    # Filter by answered status
    if only_unanswered:
        questions = [q for q in questions if not q.answered]
    
    # Filter by priority
    if priority_filter:
        priority_map = {
            "blocking": ClarificationPriority.BLOCKING,
            "high": ClarificationPriority.HIGH,
            "medium": ClarificationPriority.MEDIUM,
            "low": ClarificationPriority.LOW
        }
        if priority_filter.lower() in priority_map:
            target_priority = priority_map[priority_filter.lower()]
            questions = [q for q in questions if q.priority == target_priority]
    
    # Group by priority
    by_priority = {
        "blocking": [],
        "high": [],
        "medium": [],
        "low": []
    }
    
    for q in questions:
        priority_name = q.priority.value if hasattr(q.priority, 'value') else str(q.priority)
        if priority_name in by_priority:
            by_priority[priority_name].append(q.model_dump())
    
    return {
        "success": True,
        "investigation_id": investigation_id,
        "total_questions": len(inv.clarification_questions),
        "filtered_count": len(questions),
        "by_priority": by_priority,
        "questions": [q.model_dump() for q in questions]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "AnswerValidator",
    "ClarificationProcessor",
    "answer_clarification",
    "add_clarification_question",
    "validate_investigation",
    "list_clarification_questions",
]
