"""
Report Evidence Service - Intelligent Report Generation Phase 4.

Specialized KEY-VALUE evidence storage for report generation with:
- Key-only AI access (redacted mode)
- Full value storage for actual report
- Audit trail for all evidence access
- Evidence chain linking for narrative building
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from operation_room.database import open_vault, get_vault_path
from operation_room.services.evidence_vault import EvidenceVault

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class RedactionMode(str, Enum):
    """Modes for accessing evidence values."""
    FULL = "full"              # Complete value (for final report)
    KEY_ONLY = "key_only"      # Only key, no value (for AI processing)
    REDACTED = "redacted"      # Value replaced with placeholder
    SUMMARY = "summary"        # Summarized/sanitized value


class AccessPurpose(str, Enum):
    """Purpose for evidence access - for audit trail."""
    AI_ANALYSIS = "ai_analysis"        # AI model analyzing evidence
    REPORT_GENERATION = "report_gen"   # Generating final report
    REVIEW = "review"                   # Human review
    AUDIT = "audit"                     # Audit/compliance check
    EXPORT = "export"                   # Exporting data
    STORY_MODE = "story_mode"          # Narrative/story presentation


@dataclass
class EvidenceKey:
    """A key referencing evidence in the vault."""
    key_id: str
    key_name: str                      # Human-readable identifier
    category: str                      # Category (suspect, device, ip, file, etc.)
    summary: str                       # Brief summary for AI
    evidence_type: str                 # Type of underlying evidence
    section_id: Optional[str] = None   # Which report section this belongs to
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_name": self.key_name,
            "category": self.category,
            "summary": self.summary,
            "evidence_type": self.evidence_type,
            "section_id": self.section_id,
            "created_at": self.created_at.isoformat()
        }
    
    def to_ai_reference(self) -> str:
        """Generate AI-safe reference string."""
        return f"[EVIDENCE:{self.key_id}:{self.category}:{self.key_name}]"


@dataclass 
class EvidenceValue:
    """The actual evidence value (may be redacted)."""
    key_id: str
    raw_value: str                     # Actual evidence content
    value_hash: str                    # Hash for integrity
    source_module: str                 # Which module produced this
    source_finding_id: Optional[str]   # Link to finding
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceAccessLog:
    """Audit log for evidence access."""
    log_id: str
    key_id: str
    accessed_by: str                   # User or system component
    access_purpose: AccessPurpose
    redaction_mode: RedactionMode
    timestamp: datetime
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceChain:
    """Chain of evidence keys for building narrative."""
    chain_id: str
    section_id: str
    keys: List[str]                    # Ordered list of key_ids
    narrative_hint: str                # How these connect
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT EVIDENCE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class ReportEvidenceService:
    """
    KEY-VALUE evidence storage for intelligent report generation.
    
    Supports:
    - Storing evidence with keys for AI reference
    - Redacted access modes for different use cases
    - Full audit trail of all access
    - Evidence chains for narrative building
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._evidence_vault = EvidenceVault(case_id)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create report evidence tables."""
        vault_path = get_vault_path(self.case_id)
        if not vault_path.exists():
            return
            
        conn = open_vault(self.case_id)
        try:
            # KEY table - references to evidence
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_evidence_keys (
                    key_id VARCHAR PRIMARY KEY,
                    key_name VARCHAR NOT NULL,
                    category VARCHAR NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_type VARCHAR NOT NULL,
                    section_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # VALUE table - actual evidence content
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_evidence_values (
                    key_id VARCHAR PRIMARY KEY,
                    raw_value TEXT NOT NULL,
                    value_hash VARCHAR NOT NULL,
                    source_module VARCHAR,
                    source_finding_id VARCHAR,
                    confidence FLOAT DEFAULT 0.5,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (key_id) REFERENCES report_evidence_keys(key_id)
                )
            """)
            
            # ACCESS LOG table - audit trail
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_evidence_access_log (
                    log_id VARCHAR PRIMARY KEY,
                    key_id VARCHAR NOT NULL,
                    accessed_by VARCHAR NOT NULL,
                    access_purpose VARCHAR NOT NULL,
                    redaction_mode VARCHAR NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR,
                    session_id VARCHAR,
                    details JSON
                )
            """)
            
            # CHAINS table - evidence chains for narrative
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_evidence_chains (
                    chain_id VARCHAR PRIMARY KEY,
                    section_id VARCHAR NOT NULL,
                    key_ids JSON NOT NULL,
                    narrative_hint TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_keys_category 
                ON report_evidence_keys(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_keys_section 
                ON report_evidence_keys(section_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_access_key 
                ON report_evidence_access_log(key_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_access_time 
                ON report_evidence_access_log(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_evidence_chains_section 
                ON report_evidence_chains(section_id)
            """)
            
        finally:
            conn.close()
    
    # ───────────────────────────────────────────────────────────────────────────
    # STORE OPERATIONS
    # ───────────────────────────────────────────────────────────────────────────
    
    def store_evidence(
        self,
        key_name: str,
        category: str,
        raw_value: str,
        summary: str,
        evidence_type: str,
        source_module: str,
        source_finding_id: Optional[str] = None,
        confidence: float = 0.5,
        section_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store evidence with a KEY-VALUE pair.
        
        Args:
            key_name: Human-readable key name
            category: Evidence category (suspect, device, ip, etc.)
            raw_value: Actual evidence content
            summary: Brief AI-safe summary
            evidence_type: Type of evidence
            source_module: Which module produced this
            source_finding_id: Optional link to source finding
            confidence: Confidence score 0-1
            section_id: Which report section this belongs to
            metadata: Additional metadata
            
        Returns:
            Generated key_id
        """
        key_id = f"EVD-{uuid.uuid4().hex[:8].upper()}"
        value_hash = hashlib.sha256(raw_value.encode()).hexdigest()
        
        conn = open_vault(self.case_id)
        try:
            # Store KEY
            conn.execute("""
                INSERT INTO report_evidence_keys 
                (key_id, key_name, category, summary, evidence_type, section_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [key_id, key_name, category, summary, evidence_type, section_id])
            
            # Store VALUE
            conn.execute("""
                INSERT INTO report_evidence_values
                (key_id, raw_value, value_hash, source_module, source_finding_id, 
                 confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                key_id, raw_value, value_hash, source_module, source_finding_id,
                confidence, json.dumps(metadata or {})
            ])
            
            logger.info(f"Stored evidence key: {key_id} ({category}/{key_name})")
            
        finally:
            conn.close()
        
        return key_id
    
    def store_from_finding(
        self,
        finding_id: str,
        finding_content: str,
        module_name: str,
        category: str,
        key_name: Optional[str] = None,
        section_id: Optional[str] = None
    ) -> str:
        """
        Create evidence key from a module finding.
        
        Args:
            finding_id: ID of the source finding
            finding_content: Content of the finding
            module_name: Name of the module that produced it
            category: Evidence category
            key_name: Optional key name (auto-generated if not provided)
            section_id: Which report section this belongs to
            
        Returns:
            Generated key_id
        """
        # Generate key name if not provided
        if not key_name:
            key_name = f"{module_name}_{finding_id[:8]}"
        
        # Generate summary (first 200 chars, sanitized)
        summary = finding_content[:200].replace('\n', ' ').strip()
        if len(finding_content) > 200:
            summary += "..."
        
        return self.store_evidence(
            key_name=key_name,
            category=category,
            raw_value=finding_content,
            summary=summary,
            evidence_type="finding",
            source_module=module_name,
            source_finding_id=finding_id,
            section_id=section_id
        )
    
    # ───────────────────────────────────────────────────────────────────────────
    # RETRIEVE OPERATIONS (with redaction)
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_key(self, key_id: str) -> Optional[EvidenceKey]:
        """Get evidence key metadata (no value)."""
        conn = open_vault(self.case_id)
        try:
            result = conn.execute("""
                SELECT key_id, key_name, category, summary, evidence_type, 
                       section_id, created_at
                FROM report_evidence_keys
                WHERE key_id = ?
            """, [key_id]).fetchone()
            
            if not result:
                return None
            
            return EvidenceKey(
                key_id=result[0],
                key_name=result[1],
                category=result[2],
                summary=result[3],
                evidence_type=result[4],
                section_id=result[5],
                created_at=datetime.fromisoformat(result[6]) if result[6] else datetime.now(timezone.utc)
            )
        finally:
            conn.close()
    
    def get_value(
        self,
        key_id: str,
        mode: RedactionMode,
        accessed_by: str,
        purpose: AccessPurpose,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get evidence value with specified redaction mode.
        
        ALWAYS logs access for audit trail.
        
        Args:
            key_id: Evidence key ID
            mode: Redaction mode
            accessed_by: Who is accessing
            purpose: Why accessing
            session_id: Optional session ID
            
        Returns:
            Value (potentially redacted based on mode)
        """
        conn = open_vault(self.case_id)
        try:
            # Get key and value
            result = conn.execute("""
                SELECT k.key_id, k.key_name, k.summary, v.raw_value
                FROM report_evidence_keys k
                JOIN report_evidence_values v ON k.key_id = v.key_id
                WHERE k.key_id = ?
            """, [key_id]).fetchone()
            
            if not result:
                return None
            
            key_name = result[1]
            summary = result[2]
            raw_value = result[3]
            
            # Log the access
            self._log_access(
                key_id=key_id,
                accessed_by=accessed_by,
                purpose=purpose,
                mode=mode,
                session_id=session_id
            )
            
            # Return based on mode
            if mode == RedactionMode.FULL:
                return raw_value
            elif mode == RedactionMode.KEY_ONLY:
                return f"[Reference: {key_name}]"
            elif mode == RedactionMode.REDACTED:
                return f"[REDACTED - Evidence Key: {key_id}]"
            elif mode == RedactionMode.SUMMARY:
                return summary
            else:
                return f"[REDACTED]"
                
        finally:
            conn.close()
    
    def get_for_ai(
        self,
        key_id: str,
        system_component: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get evidence reference for AI processing.
        
        Returns only summary/key, never raw value.
        """
        key = self.get_key(key_id)
        if not key:
            return f"[Unknown Evidence: {key_id}]"
        
        # Log the access
        self._log_access(
            key_id=key_id,
            accessed_by=f"AI:{system_component}",
            purpose=AccessPurpose.AI_ANALYSIS,
            mode=RedactionMode.KEY_ONLY,
            session_id=session_id
        )
        
        return key.to_ai_reference()
    
    def get_for_report(
        self,
        key_id: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get full evidence value for final report generation.
        """
        return self.get_value(
            key_id=key_id,
            mode=RedactionMode.FULL,
            accessed_by=user_id,
            purpose=AccessPurpose.REPORT_GENERATION,
            session_id=session_id
        )
    
    def get_for_review(
        self,
        key_id: str,
        reviewer: str,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get evidence for human review (full access).
        """
        return self.get_value(
            key_id=key_id,
            mode=RedactionMode.FULL,
            accessed_by=reviewer,
            purpose=AccessPurpose.REVIEW,
            session_id=session_id
        )
    
    def get_for_story_mode(
        self,
        key_id: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Get summarized evidence for narrative/story presentation.
        """
        return self.get_value(
            key_id=key_id,
            mode=RedactionMode.SUMMARY,
            accessed_by=user_id,
            purpose=AccessPurpose.STORY_MODE,
            session_id=session_id
        )
    
    # ───────────────────────────────────────────────────────────────────────────
    # BATCH OPERATIONS
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_keys_by_section(self, section_id: str) -> List[EvidenceKey]:
        """Get all evidence keys for a report section."""
        conn = open_vault(self.case_id)
        try:
            results = conn.execute("""
                SELECT key_id, key_name, category, summary, evidence_type, 
                       section_id, created_at
                FROM report_evidence_keys
                WHERE section_id = ?
                ORDER BY created_at
            """, [section_id]).fetchall()
            
            return [
                EvidenceKey(
                    key_id=r[0],
                    key_name=r[1],
                    category=r[2],
                    summary=r[3],
                    evidence_type=r[4],
                    section_id=r[5],
                    created_at=datetime.fromisoformat(r[6]) if r[6] else datetime.now(timezone.utc)
                )
                for r in results
            ]
        finally:
            conn.close()
    
    def get_keys_by_category(self, category: str) -> List[EvidenceKey]:
        """Get all evidence keys in a category."""
        conn = open_vault(self.case_id)
        try:
            results = conn.execute("""
                SELECT key_id, key_name, category, summary, evidence_type, 
                       section_id, created_at
                FROM report_evidence_keys
                WHERE category = ?
                ORDER BY created_at
            """, [category]).fetchall()
            
            return [
                EvidenceKey(
                    key_id=r[0],
                    key_name=r[1],
                    category=r[2],
                    summary=r[3],
                    evidence_type=r[4],
                    section_id=r[5],
                    created_at=datetime.fromisoformat(r[6]) if r[6] else datetime.now(timezone.utc)
                )
                for r in results
            ]
        finally:
            conn.close()
    
    def get_all_keys(self) -> List[EvidenceKey]:
        """Get all evidence keys for the case."""
        conn = open_vault(self.case_id)
        try:
            results = conn.execute("""
                SELECT key_id, key_name, category, summary, evidence_type, 
                       section_id, created_at
                FROM report_evidence_keys
                ORDER BY category, created_at
            """).fetchall()
            
            return [
                EvidenceKey(
                    key_id=r[0],
                    key_name=r[1],
                    category=r[2],
                    summary=r[3],
                    evidence_type=r[4],
                    section_id=r[5],
                    created_at=datetime.fromisoformat(r[6]) if r[6] else datetime.now(timezone.utc)
                )
                for r in results
            ]
        finally:
            conn.close()
    
    # ───────────────────────────────────────────────────────────────────────────
    # EVIDENCE CHAINS
    # ───────────────────────────────────────────────────────────────────────────
    
    def create_chain(
        self,
        section_id: str,
        key_ids: List[str],
        narrative_hint: str
    ) -> str:
        """
        Create an evidence chain for narrative building.
        
        Args:
            section_id: Report section ID
            key_ids: Ordered list of evidence key IDs
            narrative_hint: How these pieces connect
            
        Returns:
            Chain ID
        """
        chain_id = f"CHN-{uuid.uuid4().hex[:8].upper()}"
        
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO report_evidence_chains
                (chain_id, section_id, key_ids, narrative_hint)
                VALUES (?, ?, ?, ?)
            """, [chain_id, section_id, json.dumps(key_ids), narrative_hint])
            
            logger.info(f"Created evidence chain: {chain_id} with {len(key_ids)} keys")
            
        finally:
            conn.close()
        
        return chain_id
    
    def get_chains_for_section(self, section_id: str) -> List[EvidenceChain]:
        """Get all evidence chains for a section."""
        conn = open_vault(self.case_id)
        try:
            results = conn.execute("""
                SELECT chain_id, section_id, key_ids, narrative_hint, created_at
                FROM report_evidence_chains
                WHERE section_id = ?
            """, [section_id]).fetchall()
            
            return [
                EvidenceChain(
                    chain_id=r[0],
                    section_id=r[1],
                    keys=json.loads(r[2]),
                    narrative_hint=r[3],
                    created_at=datetime.fromisoformat(r[4]) if r[4] else datetime.now(timezone.utc)
                )
                for r in results
            ]
        finally:
            conn.close()
    
    # ───────────────────────────────────────────────────────────────────────────
    # AUDIT & LOGGING
    # ───────────────────────────────────────────────────────────────────────────
    
    def _log_access(
        self,
        key_id: str,
        accessed_by: str,
        purpose: AccessPurpose,
        mode: RedactionMode,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log evidence access for audit trail."""
        log_id = f"LOG-{uuid.uuid4().hex[:8].upper()}"
        
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO report_evidence_access_log
                (log_id, key_id, accessed_by, access_purpose, redaction_mode,
                 session_id, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                log_id, key_id, accessed_by, purpose.value, mode.value,
                session_id, json.dumps(details or {})
            ])
        finally:
            conn.close()
    
    def get_access_log(
        self,
        key_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get access audit log.
        
        Args:
            key_id: Filter by evidence key
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Max results
            
        Returns:
            List of access log entries
        """
        conn = open_vault(self.case_id)
        try:
            query = "SELECT * FROM report_evidence_access_log WHERE 1=1"
            params = []
            
            if key_id:
                query += " AND key_id = ?"
                params.append(key_id)
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            results = conn.execute(query, params).fetchall()
            
            columns = [
                "log_id", "key_id", "accessed_by", "access_purpose",
                "redaction_mode", "timestamp", "ip_address", "session_id", "details"
            ]
            
            return [dict(zip(columns, r)) for r in results]
            
        finally:
            conn.close()
    
    def get_audit_summary(self) -> Dict[str, Any]:
        """Get summary of evidence access for audit."""
        conn = open_vault(self.case_id)
        try:
            # Count by purpose
            purpose_counts = conn.execute("""
                SELECT access_purpose, COUNT(*) as cnt
                FROM report_evidence_access_log
                GROUP BY access_purpose
            """).fetchall()
            
            # Count by mode
            mode_counts = conn.execute("""
                SELECT redaction_mode, COUNT(*) as cnt
                FROM report_evidence_access_log
                GROUP BY redaction_mode
            """).fetchall()
            
            # Total evidence keys
            key_count = conn.execute("""
                SELECT COUNT(*) FROM report_evidence_keys
            """).fetchone()[0]
            
            # Total access logs
            log_count = conn.execute("""
                SELECT COUNT(*) FROM report_evidence_access_log
            """).fetchone()[0]
            
            return {
                "total_evidence_keys": key_count,
                "total_access_logs": log_count,
                "access_by_purpose": dict(purpose_counts),
                "access_by_mode": dict(mode_counts)
            }
            
        finally:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_report_evidence_services: Dict[str, ReportEvidenceService] = {}


def get_report_evidence_service(case_id: str) -> ReportEvidenceService:
    """Get or create ReportEvidenceService for a case."""
    global _report_evidence_services
    if case_id not in _report_evidence_services:
        _report_evidence_services[case_id] = ReportEvidenceService(case_id)
    return _report_evidence_services[case_id]
