"""
Findings Vault Service

Central repository for all investigation findings stored as key-value pairs.
Provides:
- Finding storage with unique keys
- Confidence score tracking
- Source module attribution
- Verification status
- Data provenance
- Key-based referencing for reports

Architecture:
- Each finding has a unique key (e.g., "ACTOR_TOP_SUSPICIOUS")
- Values stored as JSON for flexibility
- Metadata tracks source, confidence, verification
- Findings linked to investigation sessions

Database Schema:
    investigation_findings:
        - finding_id (VARCHAR PRIMARY KEY)
        - case_id (VARCHAR)
        - investigation_id (VARCHAR)
        - finding_key (VARCHAR UNIQUE per investigation)
        - finding_value (JSON) - actual data
        - finding_type (VARCHAR) - hypothesis, evidence, metric, entity
        - confidence_score (FLOAT 0.0-1.0)
        - verified (BOOLEAN)
        - source_module (VARCHAR) - anomaly, crud, network, etc.
        - source_data_path (VARCHAR) - data provenance
        - created_at (TIMESTAMP)
        - updated_at (TIMESTAMP)
        - metadata (JSON)
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from operation_room.database import open_vault
from operation_room.config import settings

logger = logging.getLogger(__name__)


# Key prefixes for different finding types
KEY_PREFIXES = {
    "hypothesis": "HYP",
    "evidence": "EVD",
    "metric": "MET",
    "entity": "ENT",
    "artifact": "ART",
    "timeline": "TML",
    "correlation": "COR",
    "conclusion": "CON",
    "anomaly": "ANOM",
    "network": "NET",
    "crud": "CRUD",
    "depth": "DEP",
    "actor": "ACT",
    "system": "SYS",
    "file": "FILE",
    "exfil": "EXFIL"
}


class FindingType:
    """Types of findings that can be stored."""
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    METRIC = "metric"
    ENTITY = "entity"
    ARTIFACT = "artifact"
    TIMELINE = "timeline"
    CORRELATION = "correlation"
    CONCLUSION = "conclusion"


class KeyGenerator:
    """
    Generates unique, descriptive keys for findings.
    
    Key format: PREFIX_DESCRIPTOR_YYYYMMDD_SEQ
    Example: ANOM_JDOE_20260406_001
    
    Keys are designed to be:
    - Unique within an investigation
    - Descriptive enough to understand context
    - Safe to use in prompts (no sensitive data)
    - Traceable back to the finding
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self._sequence_cache = {}
    
    def generate_key(
        self,
        prefix: str,
        descriptor: str,
        investigation_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a unique finding key.
        
        Args:
            prefix: Key prefix (use KEY_PREFIXES values)
            descriptor: Short descriptor (will be sanitized)
            investigation_id: Optional investigation ID for sequence tracking
            timestamp: Optional timestamp (defaults to now)
        
        Returns:
            Unique key like "ANOM_JDOE_20260406_001"
        """
        # Sanitize descriptor
        descriptor = self._sanitize_descriptor(descriptor)
        
        # Get date string
        ts = timestamp or datetime.utcnow()
        date_str = ts.strftime("%Y%m%d")
        
        # Get sequence number
        base_key = f"{prefix}_{descriptor}_{date_str}"
        seq = self._get_next_sequence(base_key, investigation_id)
        
        return f"{base_key}_{seq:03d}"
    
    def _sanitize_descriptor(self, descriptor: str) -> str:
        """Sanitize descriptor for use in key."""
        # Remove special characters, convert to uppercase
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', descriptor)
        sanitized = re.sub(r'_+', '_', sanitized)  # Remove multiple underscores
        sanitized = sanitized.strip('_').upper()
        # Limit length
        return sanitized[:20] if len(sanitized) > 20 else sanitized
    
    def _get_next_sequence(self, base_key: str, investigation_id: Optional[str]) -> int:
        """Get next sequence number for a base key."""
        cache_key = f"{investigation_id or 'global'}:{base_key}"
        
        if cache_key not in self._sequence_cache:
            # Query existing keys to find highest sequence
            conn = open_vault(self.case_id)
            try:
                if investigation_id:
                    result = conn.execute("""
                        SELECT finding_key FROM investigation_findings
                        WHERE investigation_id = ? AND finding_key LIKE ?
                        ORDER BY finding_key DESC LIMIT 1
                    """, [investigation_id, f"{base_key}_%"]).fetchone()
                else:
                    result = conn.execute("""
                        SELECT finding_key FROM investigation_findings
                        WHERE finding_key LIKE ?
                        ORDER BY finding_key DESC LIMIT 1
                    """, [f"{base_key}_%"]).fetchone()
                
                if result:
                    # Extract sequence from existing key
                    try:
                        seq = int(result[0].split('_')[-1])
                        self._sequence_cache[cache_key] = seq
                    except (ValueError, IndexError):
                        self._sequence_cache[cache_key] = 0
                else:
                    self._sequence_cache[cache_key] = 0
            finally:
                conn.close()
        
        self._sequence_cache[cache_key] += 1
        return self._sequence_cache[cache_key]
    
    def generate_anomaly_key(self, actor: Optional[str] = None, event_type: Optional[str] = None) -> str:
        """Generate key for anomaly finding."""
        if actor:
            return self.generate_key("ANOM", actor)
        elif event_type:
            return self.generate_key("ANOM", event_type)
        else:
            return self.generate_key("ANOM", "EVENT")
    
    def generate_network_key(self, source_ip: Optional[str] = None, flow_type: str = "FLOW") -> str:
        """Generate key for network finding."""
        if source_ip:
            # Sanitize IP
            descriptor = source_ip.replace('.', '_').replace(':', '_')
            return self.generate_key("NET", descriptor)
        return self.generate_key("NET", flow_type)
    
    def generate_exfil_key(self, source_ip: str) -> str:
        """Generate key for exfiltration finding."""
        descriptor = source_ip.replace('.', '_').replace(':', '_')
        return self.generate_key("EXFIL", descriptor)
    
    def generate_actor_key(self, actor: str) -> str:
        """Generate key for actor-related finding."""
        return self.generate_key("ACT", actor)
    
    def generate_hypothesis_key(self, hypothesis_name: str) -> str:
        """Generate key for hypothesis."""
        return self.generate_key("HYP", hypothesis_name)
    
    def generate_metric_key(self, module: str, metric_name: str) -> str:
        """Generate key for metric finding."""
        prefix = KEY_PREFIXES.get(module.lower(), "MET")
        return self.generate_key(prefix, metric_name)


class FindingsVault:
    """Service for managing investigation findings as key-value pairs."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.key_generator = KeyGenerator(case_id)
        self._ensure_schema()
    
    def _ensure_schema(self):
        """Create findings table if it doesn't exist."""
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigation_findings (
                    finding_id VARCHAR PRIMARY KEY,
                    case_id VARCHAR NOT NULL,
                    investigation_id VARCHAR,
                    finding_key VARCHAR NOT NULL,
                    finding_value JSON NOT NULL,
                    finding_type VARCHAR NOT NULL,
                    confidence_score FLOAT DEFAULT 0.5,
                    verified BOOLEAN DEFAULT FALSE,
                    source_module VARCHAR,
                    source_data_path VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSON,
                    UNIQUE(investigation_id, finding_key)
                )
            """)
            
            # Index for fast lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_case_inv 
                ON investigation_findings(case_id, investigation_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_key 
                ON investigation_findings(finding_key)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_findings_type 
                ON investigation_findings(finding_type)
            """)
            
        finally:
            conn.close()
    
    def save_finding(
        self,
        finding_key: str,
        finding_value: Any,
        finding_type: str,
        investigation_id: Optional[str] = None,
        confidence_score: float = 0.5,
        source_module: Optional[str] = None,
        source_data_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
        verified: bool = False
    ) -> str:
        """
        Save a finding to the vault.
        
        Args:
            finding_key: Unique key for this finding (e.g., "ACTOR_TOP_SUSPICIOUS")
            finding_value: The actual value/data (will be JSON serialized)
            finding_type: Type of finding (use FindingType constants)
            investigation_id: Optional investigation session ID
            confidence_score: Confidence level 0.0-1.0
            source_module: Module that generated this (anomaly, crud, network, etc.)
            source_data_path: Data provenance (table.column or file path)
            metadata: Additional metadata
            verified: Whether this finding has been verified
        
        Returns:
            finding_id: UUID of the created finding
        """
        finding_id = str(uuid.uuid4())
        
        # Ensure value is JSON serializable
        if not isinstance(finding_value, (dict, list, str, int, float, bool, type(None))):
            finding_value = str(finding_value)
        
        conn = open_vault(self.case_id)
        try:
            # Check if key already exists for this investigation
            if investigation_id:
                existing = conn.execute("""
                    SELECT finding_id FROM investigation_findings
                    WHERE investigation_id = ? AND finding_key = ?
                """, [investigation_id, finding_key]).fetchone()
                
                if existing:
                    # Update existing finding
                    conn.execute("""
                        UPDATE investigation_findings
                        SET finding_value = ?,
                            confidence_score = ?,
                            verified = ?,
                            source_module = ?,
                            source_data_path = ?,
                            updated_at = ?,
                            metadata = ?
                        WHERE finding_id = ?
                    """, [
                        json.dumps(finding_value),
                        confidence_score,
                        verified,
                        source_module,
                        source_data_path,
                        datetime.now(timezone.utc).isoformat(),
                        json.dumps(metadata) if metadata else None,
                        existing[0]
                    ])
                    logger.info(f"Updated finding {finding_key} for investigation {investigation_id}")
                    return existing[0]
            
            # Insert new finding
            conn.execute("""
                INSERT INTO investigation_findings (
                    finding_id, case_id, investigation_id, finding_key,
                    finding_value, finding_type, confidence_score, verified,
                    source_module, source_data_path, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                finding_id,
                self.case_id,
                investigation_id,
                finding_key,
                json.dumps(finding_value),
                finding_type,
                confidence_score,
                verified,
                source_module,
                source_data_path,
                json.dumps(metadata) if metadata else None
            ])
            
            logger.info(f"Saved finding {finding_key} with ID {finding_id}")
            return finding_id
            
        finally:
            conn.close()
    
    def save_finding_auto_key(
        self,
        prefix: str,
        descriptor: str,
        finding_value: Any,
        finding_type: str,
        investigation_id: Optional[str] = None,
        confidence_score: float = 0.5,
        source_module: Optional[str] = None,
        source_data_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
        verified: bool = False
    ) -> tuple[str, str]:
        """
        Save a finding with auto-generated unique key.
        
        Args:
            prefix: Key prefix (e.g., "ANOM", "NET", "ACT")
            descriptor: Short descriptor for the key
            finding_value: The actual value/data
            finding_type: Type of finding
            ... other params same as save_finding
        
        Returns:
            Tuple of (finding_id, finding_key)
        """
        # Generate unique key
        finding_key = self.key_generator.generate_key(
            prefix=prefix,
            descriptor=descriptor,
            investigation_id=investigation_id
        )
        
        # Save with generated key
        finding_id = self.save_finding(
            finding_key=finding_key,
            finding_value=finding_value,
            finding_type=finding_type,
            investigation_id=investigation_id,
            confidence_score=confidence_score,
            source_module=source_module,
            source_data_path=source_data_path,
            metadata=metadata,
            verified=verified
        )
        
        return finding_id, finding_key
    
    def get_key_value_map(
        self,
        investigation_id: Optional[str] = None,
        finding_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a dictionary mapping finding keys to their values.
        Used for key replacement in prompts and reports.
        
        Args:
            investigation_id: Filter by investigation
            finding_type: Filter by finding type
        
        Returns:
            Dict mapping keys to their values
        """
        findings = self.get_all_findings(
            investigation_id=investigation_id,
            finding_type=finding_type
        )
        
        return {
            f["finding_key"]: f["finding_value"]
            for f in findings
        }
    
    def get_finding(self, finding_key: str, investigation_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a finding by its key."""
        conn = open_vault(self.case_id)
        try:
            if investigation_id:
                query = """
                    SELECT * FROM investigation_findings
                    WHERE finding_key = ? AND investigation_id = ?
                    ORDER BY updated_at DESC LIMIT 1
                """
                params = [finding_key, investigation_id]
            else:
                query = """
                    SELECT * FROM investigation_findings
                    WHERE finding_key = ?
                    ORDER BY updated_at DESC LIMIT 1
                """
                params = [finding_key]
            
            row = conn.execute(query, params).fetchone()
            
            if not row:
                return None
            
            return self._row_to_dict(row)
            
        finally:
            conn.close()
    
    def get_all_findings(
        self,
        investigation_id: Optional[str] = None,
        finding_type: Optional[str] = None,
        verified_only: bool = False,
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Get all findings matching criteria."""
        conn = open_vault(self.case_id)
        try:
            conditions = ["case_id = ?"]
            params = [self.case_id]
            
            if investigation_id:
                conditions.append("investigation_id = ?")
                params.append(investigation_id)
            
            if finding_type:
                conditions.append("finding_type = ?")
                params.append(finding_type)
            
            if verified_only:
                conditions.append("verified = TRUE")
            
            if min_confidence > 0.0:
                conditions.append("confidence_score >= ?")
                params.append(min_confidence)
            
            query = f"""
                SELECT * FROM investigation_findings
                WHERE {' AND '.join(conditions)}
                ORDER BY confidence_score DESC, created_at DESC
            """
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
            
        finally:
            conn.close()
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert database row to dictionary."""
        return {
            "finding_id": row[0],
            "case_id": row[1],
            "investigation_id": row[2],
            "finding_key": row[3],
            "finding_value": json.loads(row[4]) if row[4] else None,
            "finding_type": row[5],
            "confidence_score": row[6],
            "verified": row[7],
            "source_module": row[8],
            "source_data_path": row[9],
            "created_at": row[10],
            "updated_at": row[11],
            "metadata": json.loads(row[12]) if row[12] else None,
        }
    
    def verify_finding(self, finding_key: str, investigation_id: Optional[str] = None) -> bool:
        """Mark a finding as verified."""
        conn = open_vault(self.case_id)
        try:
            if investigation_id:
                conn.execute("""
                    UPDATE investigation_findings
                    SET verified = TRUE, updated_at = ?
                    WHERE finding_key = ? AND investigation_id = ?
                """, [datetime.now(timezone.utc).isoformat(), finding_key, investigation_id])
            else:
                conn.execute("""
                    UPDATE investigation_findings
                    SET verified = TRUE, updated_at = ?
                    WHERE finding_key = ?
                """, [datetime.now(timezone.utc).isoformat(), finding_key])
            
            return True
        finally:
            conn.close()
    
    def update_confidence(
        self,
        finding_key: str,
        confidence_score: float,
        investigation_id: Optional[str] = None
    ) -> bool:
        """Update the confidence score for a finding."""
        conn = open_vault(self.case_id)
        try:
            if investigation_id:
                conn.execute("""
                    UPDATE investigation_findings
                    SET confidence_score = ?, updated_at = ?
                    WHERE finding_key = ? AND investigation_id = ?
                """, [confidence_score, datetime.now(timezone.utc).isoformat(), finding_key, investigation_id])
            else:
                conn.execute("""
                    UPDATE investigation_findings
                    SET confidence_score = ?, updated_at = ?
                    WHERE finding_key = ?
                """, [confidence_score, datetime.now(timezone.utc).isoformat(), finding_key])
            
            return True
        finally:
            conn.close()
    
    def get_findings_by_module(
        self,
        source_module: str,
        investigation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all findings from a specific module."""
        conn = open_vault(self.case_id)
        try:
            if investigation_id:
                query = """
                    SELECT * FROM investigation_findings
                    WHERE source_module = ? AND investigation_id = ?
                    ORDER BY confidence_score DESC
                """
                params = [source_module, investigation_id]
            else:
                query = """
                    SELECT * FROM investigation_findings
                    WHERE source_module = ?
                    ORDER BY confidence_score DESC
                """
                params = [source_module]
            
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
            
        finally:
            conn.close()
    
    def delete_finding(self, finding_key: str, investigation_id: Optional[str] = None) -> bool:
        """Delete a finding."""
        conn = open_vault(self.case_id)
        try:
            if investigation_id:
                conn.execute("""
                    DELETE FROM investigation_findings
                    WHERE finding_key = ? AND investigation_id = ?
                """, [finding_key, investigation_id])
            else:
                conn.execute("""
                    DELETE FROM investigation_findings
                    WHERE finding_key = ?
                """, [finding_key])
            
            return True
        finally:
            conn.close()
    
    def get_findings_summary(self, investigation_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics about findings."""
        conn = open_vault(self.case_id)
        try:
            conditions = ["case_id = ?"]
            params = [self.case_id]
            
            if investigation_id:
                conditions.append("investigation_id = ?")
                params.append(investigation_id)
            
            where_clause = ' AND '.join(conditions)
            
            stats = conn.execute(f"""
                SELECT 
                    COUNT(*) as total_findings,
                    SUM(CASE WHEN verified THEN 1 ELSE 0 END) as verified_count,
                    AVG(confidence_score) as avg_confidence,
                    MAX(confidence_score) as max_confidence,
                    MIN(confidence_score) as min_confidence
                FROM investigation_findings
                WHERE {where_clause}
            """, params).fetchone()
            
            # Breakdown by type
            type_breakdown = conn.execute(f"""
                SELECT finding_type, COUNT(*) as count
                FROM investigation_findings
                WHERE {where_clause}
                GROUP BY finding_type
                ORDER BY count DESC
            """, params).fetchall()
            
            # Breakdown by module
            module_breakdown = conn.execute(f"""
                SELECT source_module, COUNT(*) as count
                FROM investigation_findings
                WHERE {where_clause} AND source_module IS NOT NULL
                GROUP BY source_module
                ORDER BY count DESC
            """, params).fetchall()
            
            return {
                "total_findings": stats[0] or 0,
                "verified_count": stats[1] or 0,
                "avg_confidence": round(stats[2], 3) if stats[2] else 0.0,
                "max_confidence": stats[3] or 0.0,
                "min_confidence": stats[4] or 0.0,
                "by_type": [{"type": r[0], "count": r[1]} for r in type_breakdown],
                "by_module": [{"module": r[0], "count": r[1]} for r in module_breakdown],
            }
            
        finally:
            conn.close()


# Global registry of vault instances
_vault_instances: Dict[str, FindingsVault] = {}


def get_findings_vault(case_id: str) -> FindingsVault:
    """Get or create a findings vault for a case."""
    if case_id not in _vault_instances:
        _vault_instances[case_id] = FindingsVault(case_id)
    return _vault_instances[case_id]
