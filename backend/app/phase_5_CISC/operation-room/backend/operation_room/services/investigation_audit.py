"""
Investigation Audit Service

Comprehensive audit logging for all AI decisions, module runs, user approvals,
and investigation events. Provides full chain of custody tracking.
"""

import logging
import uuid
import hashlib
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from operation_room.database import open_vault

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    
    # Investigation events
    INVESTIGATION_CREATED = "investigation_created"
    INVESTIGATION_UPDATED = "investigation_updated"
    INVESTIGATION_COMPLETED = "investigation_completed"
    
    # Chat events
    CHAT_MESSAGE_USER = "chat_message_user"
    CHAT_MESSAGE_AI = "chat_message_ai"
    CONTEXT_EXTRACTED = "context_extracted"
    
    # Hypothesis events
    HYPOTHESIS_GENERATED = "hypothesis_generated"
    HYPOTHESIS_APPROVED = "hypothesis_approved"
    HYPOTHESIS_MODIFIED = "hypothesis_modified"
    HYPOTHESIS_REJECTED = "hypothesis_rejected"
    HYPOTHESIS_ADDED = "hypothesis_added"
    
    # Module events
    MODULE_STARTED = "module_started"
    MODULE_COMPLETED = "module_completed"
    MODULE_FAILED = "module_failed"
    MODULE_SKIPPED = "module_skipped"
    
    # Finding events
    FINDING_CREATED = "finding_created"
    FINDING_UPDATED = "finding_updated"
    FINDING_VERIFIED = "finding_verified"
    FINDING_DELETED = "finding_deleted"
    
    # Confidence events
    CONFIDENCE_CALCULATED = "confidence_calculated"
    CONFIDENCE_RECALCULATED = "confidence_recalculated"
    
    # Report events
    REPORT_CREATED = "report_created"
    SECTION_GENERATED = "section_generated"
    SECTION_APPROVED = "section_approved"
    SECTION_ENHANCED = "section_enhanced"
    SECTION_REGENERATED = "section_regenerated"
    REPORT_FINALIZED = "report_finalized"
    
    # Export events
    EXPORT_STARTED = "export_started"
    EXPORT_COMPLETED = "export_completed"
    EXPORT_FAILED = "export_failed"
    
    # AI Decision events
    AI_DECISION = "ai_decision"
    AI_RECOMMENDATION = "ai_recommendation"
    AI_ERROR = "ai_error"
    
    # User action events
    USER_APPROVAL = "user_approval"
    USER_MODIFICATION = "user_modification"
    USER_OVERRIDE = "user_override"
    
    # System events
    SYSTEM_ERROR = "system_error"
    VALIDATION_FAILED = "validation_failed"
    DATA_INTEGRITY_CHECK = "data_integrity_check"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """A single audit log entry."""
    event_id: str
    case_id: str
    investigation_id: Optional[str]
    session_id: Optional[str]
    event_type: AuditEventType
    severity: AuditSeverity
    actor: str  # user, system, or AI agent name
    action: str
    target: Optional[str]  # What was acted upon
    details: Dict[str, Any]
    timestamp: datetime
    parent_event_id: Optional[str] = None
    content_hash: Optional[str] = None  # SHA-256 of details for integrity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            "session_id": self.session_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "parent_event_id": self.parent_event_id,
            "content_hash": self.content_hash
        }


class InvestigationAuditService:
    """Service for comprehensive investigation audit logging."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure audit tables exist in the case vault."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigation_audit_log (
                    event_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    investigation_id VARCHAR,
                    session_id VARCHAR,
                    event_type VARCHAR NOT NULL,
                    severity VARCHAR NOT NULL,
                    actor VARCHAR NOT NULL,
                    action TEXT NOT NULL,
                    target VARCHAR,
                    details_json JSON,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    parent_event_id VARCHAR,
                    content_hash VARCHAR,
                    FOREIGN KEY (parent_event_id) REFERENCES investigation_audit_log(event_id)
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_investigation 
                ON investigation_audit_log(investigation_id, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_session 
                ON investigation_audit_log(session_id, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_type 
                ON investigation_audit_log(event_type, timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_actor 
                ON investigation_audit_log(actor, timestamp)
            """)
        finally:
            conn.close()
    
    def _compute_hash(self, details: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of event details for integrity."""
        content = json.dumps(details, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def log_event(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        details: Dict[str, Any],
        investigation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        target: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        parent_event_id: Optional[str] = None
    ) -> str:
        """
        Log an audit event.
        
        Returns the event_id for the logged event.
        """
        event_id = f"audit-{uuid.uuid4().hex[:12]}"
        content_hash = self._compute_hash(details)
        
        event = AuditEvent(
            event_id=event_id,
            case_id=self.case_id,
            investigation_id=investigation_id,
            session_id=session_id,
            event_type=event_type,
            severity=severity,
            actor=actor,
            action=action,
            target=target,
            details=details,
            timestamp=datetime.utcnow(),
            parent_event_id=parent_event_id,
            content_hash=content_hash
        )
        
        # Save to database
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO investigation_audit_log
                (event_id, case_id, investigation_id, session_id, event_type,
                 severity, actor, action, target, details_json, timestamp,
                 parent_event_id, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                event.event_id,
                event.case_id,
                event.investigation_id,
                event.session_id,
                event.event_type.value,
                event.severity.value,
                event.actor,
                event.action,
                event.target,
                json.dumps(event.details),
                event.timestamp.isoformat(),
                event.parent_event_id,
                event.content_hash
            ])
        finally:
            conn.close()
        
        logger.debug(f"Audit event logged: {event_type.value} by {actor}")
        return event_id
    
    # ─── Convenience Methods ─────────────────────────────────────────────────────
    
    def log_session_start(
        self,
        investigation_id: Optional[str],
        details: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> str:
        """Log session start event."""
        return self.log_event(
            event_type=AuditEventType.SESSION_START,
            actor="system",
            action="Chat session started",
            details=details,
            investigation_id=investigation_id,
            session_id=session_id or details.get("session_id")
        )
    
    def log_chat_message(
        self, 
        role: str, 
        content: str, 
        session_id: str,
        investigation_id: Optional[str] = None
    ) -> str:
        """Log a chat message event."""
        event_type = AuditEventType.CHAT_MESSAGE_USER if role == "user" else AuditEventType.CHAT_MESSAGE_AI
        return self.log_event(
            event_type=event_type,
            actor=role,
            action=f"Sent message",
            details={"content": content[:500], "full_length": len(content)},
            investigation_id=investigation_id,
            session_id=session_id
        )
    
    def log_hypothesis_generated(
        self,
        hypotheses: List[Dict[str, Any]],
        investigation_id: str,
        session_id: Optional[str] = None,
        generation_method: str = "llm"
    ) -> str:
        """Log hypothesis generation event."""
        return self.log_event(
            event_type=AuditEventType.HYPOTHESIS_GENERATED,
            actor="ai_hypothesis_agent",
            action=f"Generated {len(hypotheses)} hypotheses using {generation_method}",
            details={
                "hypothesis_count": len(hypotheses),
                "hypotheses": [{"id": h.get("id"), "name": h.get("name")} for h in hypotheses],
                "generation_method": generation_method
            },
            investigation_id=investigation_id,
            session_id=session_id,
            target="hypotheses"
        )
    
    def log_hypothesis_approved(
        self,
        hypotheses: List[Dict[str, Any]],
        investigation_id: str,
        approved_by: str = "user",
        modifications: Optional[List[str]] = None
    ) -> str:
        """Log hypothesis approval event."""
        return self.log_event(
            event_type=AuditEventType.HYPOTHESIS_APPROVED,
            actor=approved_by,
            action=f"Approved {len(hypotheses)} hypotheses",
            details={
                "hypotheses": [h.get("id") for h in hypotheses],
                "modifications": modifications or []
            },
            investigation_id=investigation_id,
            target="hypotheses",
            severity=AuditSeverity.INFO
        )
    
    def log_module_execution(
        self,
        module_name: str,
        status: str,  # started, completed, failed
        investigation_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        results_summary: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> str:
        """Log module execution event."""
        event_type = {
            "started": AuditEventType.MODULE_STARTED,
            "completed": AuditEventType.MODULE_COMPLETED,
            "failed": AuditEventType.MODULE_FAILED,
            "skipped": AuditEventType.MODULE_SKIPPED
        }.get(status, AuditEventType.MODULE_STARTED)
        
        severity = AuditSeverity.ERROR if status == "failed" else AuditSeverity.INFO
        
        return self.log_event(
            event_type=event_type,
            actor=f"module_{module_name}",
            action=f"Module {module_name} {status}",
            details={
                "module": module_name,
                "status": status,
                "parameters": parameters or {},
                "results_summary": results_summary or {},
                "error": error,
                "duration_seconds": duration_seconds
            },
            investigation_id=investigation_id,
            target=module_name,
            severity=severity
        )
    
    def log_finding_created(
        self,
        finding_key: str,
        finding_type: str,
        source_module: str,
        investigation_id: str,
        confidence_score: Optional[float] = None
    ) -> str:
        """Log finding creation event."""
        return self.log_event(
            event_type=AuditEventType.FINDING_CREATED,
            actor=source_module,
            action=f"Created finding {finding_key}",
            details={
                "finding_key": finding_key,
                "finding_type": finding_type,
                "source_module": source_module,
                "confidence_score": confidence_score
            },
            investigation_id=investigation_id,
            target=finding_key
        )
    
    def log_ai_decision(
        self,
        decision: str,
        reasoning: str,
        alternatives: Optional[List[str]] = None,
        investigation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_name: str = "ai_orchestrator"
    ) -> str:
        """Log an AI decision with reasoning."""
        return self.log_event(
            event_type=AuditEventType.AI_DECISION,
            actor=agent_name,
            action=decision,
            details={
                "decision": decision,
                "reasoning": reasoning,
                "alternatives_considered": alternatives or []
            },
            investigation_id=investigation_id,
            session_id=session_id
        )
    
    def log_user_approval(
        self,
        item_type: str,  # hypothesis, section, report, etc.
        item_id: str,
        approved: bool,
        feedback: Optional[str] = None,
        investigation_id: Optional[str] = None,
        user: str = "user"
    ) -> str:
        """Log user approval/rejection event."""
        return self.log_event(
            event_type=AuditEventType.USER_APPROVAL,
            actor=user,
            action=f"{'Approved' if approved else 'Rejected'} {item_type}",
            details={
                "item_type": item_type,
                "item_id": item_id,
                "approved": approved,
                "feedback": feedback
            },
            investigation_id=investigation_id,
            target=item_id
        )
    
    def log_section_event(
        self,
        event_type: str,  # generated, approved, enhanced, regenerated
        section_id: str,
        section_name: str,
        investigation_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Log report section event."""
        type_map = {
            "generated": AuditEventType.SECTION_GENERATED,
            "approved": AuditEventType.SECTION_APPROVED,
            "enhanced": AuditEventType.SECTION_ENHANCED,
            "regenerated": AuditEventType.SECTION_REGENERATED
        }
        return self.log_event(
            event_type=type_map.get(event_type, AuditEventType.SECTION_GENERATED),
            actor="report_generator" if event_type == "generated" else "user",
            action=f"Section {section_name} {event_type}",
            details={
                "section_id": section_id,
                "section_name": section_name,
                **(details or {})
            },
            investigation_id=investigation_id,
            target=section_id
        )
    
    def log_export(
        self,
        export_format: str,
        status: str,
        investigation_id: str,
        doc_id: Optional[str] = None,
        file_path: Optional[str] = None,
        file_hash: Optional[str] = None,
        error: Optional[str] = None
    ) -> str:
        """Log export event."""
        event_type = {
            "started": AuditEventType.EXPORT_STARTED,
            "completed": AuditEventType.EXPORT_COMPLETED,
            "failed": AuditEventType.EXPORT_FAILED
        }.get(status, AuditEventType.EXPORT_STARTED)
        
        return self.log_event(
            event_type=event_type,
            actor="export_service",
            action=f"Export to {export_format} {status}",
            details={
                "format": export_format,
                "status": status,
                "doc_id": doc_id,
                "file_path": file_path,
                "file_hash": file_hash,
                "error": error
            },
            investigation_id=investigation_id,
            target=doc_id,
            severity=AuditSeverity.ERROR if status == "failed" else AuditSeverity.INFO
        )
    
    def log_confidence_calculation(
        self,
        finding_key: str,
        old_score: Optional[float],
        new_score: float,
        factors: Dict[str, float],
        investigation_id: str
    ) -> str:
        """Log confidence score calculation."""
        return self.log_event(
            event_type=AuditEventType.CONFIDENCE_CALCULATED,
            actor="confidence_engine",
            action=f"Calculated confidence for {finding_key}",
            details={
                "finding_key": finding_key,
                "old_score": old_score,
                "new_score": new_score,
                "factors": factors
            },
            investigation_id=investigation_id,
            target=finding_key
        )
    
    # ─── Query Methods ───────────────────────────────────────────────────────────
    
    def get_audit_log(
        self,
        investigation_id: Optional[str] = None,
        session_id: Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        actor: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Query audit log with filters."""
        conn = open_vault(self.case_id)
        try:
            where_clauses = ["1=1"]
            params = []
            
            if investigation_id:
                where_clauses.append("investigation_id = ?")
                params.append(investigation_id)
            if session_id:
                where_clauses.append("session_id = ?")
                params.append(session_id)
            if event_types:
                placeholders = ",".join(["?"] * len(event_types))
                where_clauses.append(f"event_type IN ({placeholders})")
                params.extend([et.value for et in event_types])
            if actor:
                where_clauses.append("actor = ?")
                params.append(actor)
            if start_time:
                where_clauses.append("timestamp >= ?")
                params.append(start_time.isoformat())
            if end_time:
                where_clauses.append("timestamp <= ?")
                params.append(end_time.isoformat())
            
            query = f"""
                SELECT event_id, case_id, investigation_id, session_id, event_type,
                       severity, actor, action, target, details_json, timestamp,
                       parent_event_id, content_hash
                FROM investigation_audit_log
                WHERE {" AND ".join(where_clauses)}
                ORDER BY timestamp DESC
                LIMIT {limit}
            """
            
            rows = conn.execute(query, params).fetchall()
            
            events = []
            for row in rows:
                events.append(AuditEvent(
                    event_id=row[0],
                    case_id=row[1],
                    investigation_id=row[2],
                    session_id=row[3],
                    event_type=AuditEventType(row[4]),
                    severity=AuditSeverity(row[5]),
                    actor=row[6],
                    action=row[7],
                    target=row[8],
                    details=json.loads(row[9]) if row[9] else {},
                    timestamp=datetime.fromisoformat(row[10]) if isinstance(row[10], str) else row[10],
                    parent_event_id=row[11],
                    content_hash=row[12]
                ))
            
            return events
        finally:
            conn.close()
    
    def get_investigation_timeline(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Get a timeline of all events for an investigation."""
        events = self.get_audit_log(investigation_id=investigation_id, limit=1000)
        return [e.to_dict() for e in sorted(events, key=lambda e: e.timestamp)]
    
    def get_decision_chain(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Get all AI decisions made during an investigation."""
        events = self.get_audit_log(
            investigation_id=investigation_id,
            event_types=[AuditEventType.AI_DECISION, AuditEventType.AI_RECOMMENDATION],
            limit=500
        )
        return [e.to_dict() for e in events]
    
    def get_user_actions(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Get all user actions during an investigation."""
        events = self.get_audit_log(
            investigation_id=investigation_id,
            event_types=[
                AuditEventType.USER_APPROVAL,
                AuditEventType.USER_MODIFICATION,
                AuditEventType.USER_OVERRIDE,
                AuditEventType.HYPOTHESIS_APPROVED,
                AuditEventType.SECTION_APPROVED
            ],
            limit=500
        )
        return [e.to_dict() for e in events]
    
    def get_module_runs(self, investigation_id: str) -> List[Dict[str, Any]]:
        """Get all module execution events."""
        events = self.get_audit_log(
            investigation_id=investigation_id,
            event_types=[
                AuditEventType.MODULE_STARTED,
                AuditEventType.MODULE_COMPLETED,
                AuditEventType.MODULE_FAILED
            ],
            limit=500
        )
        return [e.to_dict() for e in events]
    
    def generate_audit_report(self, investigation_id: str) -> Dict[str, Any]:
        """Generate a summary audit report for an investigation."""
        conn = open_vault(self.case_id)
        try:
            # Count events by type
            type_counts = conn.execute("""
                SELECT event_type, COUNT(*) as count
                FROM investigation_audit_log
                WHERE investigation_id = ?
                GROUP BY event_type
                ORDER BY count DESC
            """, [investigation_id]).fetchall()
            
            # Count events by actor
            actor_counts = conn.execute("""
                SELECT actor, COUNT(*) as count
                FROM investigation_audit_log
                WHERE investigation_id = ?
                GROUP BY actor
                ORDER BY count DESC
            """, [investigation_id]).fetchall()
            
            # Get time range
            time_range = conn.execute("""
                SELECT MIN(timestamp), MAX(timestamp)
                FROM investigation_audit_log
                WHERE investigation_id = ?
            """, [investigation_id]).fetchone()
            
            # Count errors
            error_count = conn.execute("""
                SELECT COUNT(*) FROM investigation_audit_log
                WHERE investigation_id = ? AND severity = 'error'
            """, [investigation_id]).fetchone()[0]
            
            # Get key decisions
            decisions = self.get_decision_chain(investigation_id)
            
            return {
                "investigation_id": investigation_id,
                "case_id": self.case_id,
                "generated_at": datetime.utcnow().isoformat(),
                "summary": {
                    "total_events": sum(c[1] for c in type_counts),
                    "event_types": {c[0]: c[1] for c in type_counts},
                    "actors": {c[0]: c[1] for c in actor_counts},
                    "time_range": {
                        "start": time_range[0],
                        "end": time_range[1]
                    } if time_range[0] else None,
                    "error_count": error_count
                },
                "key_decisions": decisions[:10],
                "user_actions": self.get_user_actions(investigation_id)[:20]
            }
        finally:
            conn.close()
    
    def verify_integrity(self, investigation_id: str) -> Dict[str, Any]:
        """Verify integrity of audit log entries by checking hashes."""
        events = self.get_audit_log(investigation_id=investigation_id, limit=10000)
        
        verified = 0
        failed = 0
        failures = []
        
        for event in events:
            expected_hash = self._compute_hash(event.details)
            if event.content_hash == expected_hash:
                verified += 1
            else:
                failed += 1
                failures.append({
                    "event_id": event.event_id,
                    "expected_hash": expected_hash,
                    "stored_hash": event.content_hash
                })
        
        return {
            "investigation_id": investigation_id,
            "total_events": len(events),
            "verified": verified,
            "failed": failed,
            "integrity_percentage": (verified / len(events) * 100) if events else 100,
            "failures": failures[:10] if failures else []
        }


def get_audit_service(case_id: str) -> InvestigationAuditService:
    """Factory function to get an audit service instance."""
    return InvestigationAuditService(case_id)
