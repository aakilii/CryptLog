"""
Node 5: Chronograph (Timeline Sync)
Timestamp normalization to ISO-8601 UTC
"""

from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.phase2.utils.timestamp_parser import (
    normalize_timestamp,
    extract_timestamp_from_line
)
from app.db.models import AuditLog


def get_previous_logs(
    db: Session,
    source_ip: Optional[str],
    limit: int = 50
) -> List[Dict]:
    """
    Get previous logs from same IP for format inference.
    
    Args:
        db: Database session
        source_ip: Source IP address
        limit: Maximum number of logs to retrieve
    
    Returns:
        List of previous log entries
    """
    if not source_ip:
        return []
    
    try:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.source_ip == source_ip)
            .order_by(AuditLog.upload_time.desc())
            .limit(limit)
            .all()
        )
        
        return [
            {
                "timestamp": str(log.upload_time) if log.upload_time else "",
                "source_ip": log.source_ip
            }
            for log in logs
        ]
    except Exception as e:
        logger.warning(f"[Node5] Failed to fetch previous logs: {e}")
        return []


def extract_timestamp(
    log_line: str,
    extracted_variables: Optional[Dict] = None
) -> Optional[str]:
    """
    Extract timestamp from log line or variables.
    
    Priority:
    1. extracted_variables.get("timestamp")
    2. Pattern matching from log line
    3. First token of log line (fallback)
    
    Args:
        log_line: Full log line text
        extracted_variables: Variables extracted from Node 3 (DRAIN3)
    
    Returns:
        Extracted timestamp string, or None
    """
    # Priority 1: Check extracted variables from Node 3
    if extracted_variables and extracted_variables.get("timestamp"):
        return extracted_variables.get("timestamp")
    
    # Priority 2: Pattern matching
    extracted = extract_timestamp_from_line(log_line)
    if extracted:
        return extracted
    
    # Priority 3: Fallback to first token ONLY if it actually looks like a timestamp.
    # This prevents false positives on binary-ish logs (e.g., PDF tokens like "endobj").
    parts = log_line.strip().split()
    if parts:
        candidate = parts[0]
        if extract_timestamp_from_line(candidate):
            return candidate
    
    return None


def process_timestamp_sync(
    db: Session,
    timestamp_str: str,
    source_ip: Optional[str] = None,
    time_delta: Optional[int] = None,
    log_line: Optional[str] = None
) -> Dict:
    """
    Process timestamp through chronograph pipeline.
    
    Args:
        db: Database session
        timestamp_str: Input timestamp string (can be None, will extract from log_line)
        source_ip: Source IP for context
        time_delta: Timezone offset in seconds
        log_line: Optional full log line for better extraction
    
    Returns:
        Normalized timestamp result with metadata
    """
    from datetime import timedelta
    
    # If timestamp_str is None, try to extract from log_line
    if not timestamp_str and log_line:
        timestamp_str = extract_timestamp_from_line(log_line)
    
    if not timestamp_str:
        logger.debug("[Node5] No timestamp found in log line")
        return {
            "normalized": None,
            "normalized_iso": None,
            "original": None,
            "format_detected": "none",
            "ambiguous": False,
            "ambiguous_flag": False,
            "timezone_detected": None
        }
    
    previous_logs = get_previous_logs(db, source_ip, limit=50)
    delta = timedelta(seconds=time_delta) if time_delta else None
    
    result = normalize_timestamp(
        timestamp_str=timestamp_str,
        source_ip=source_ip,
        previous_logs=previous_logs,
        time_delta=delta
    )
    
    if result["normalized"]:
        logger.debug(
            f"[Node5] Timestamp normalized: {timestamp_str} -> {result['normalized_iso']} "
            f"(format: {result.get('format_detected', 'unknown')})"
        )
    else:
        logger.warning(
            f"[Node5] Failed to normalize timestamp: {timestamp_str} "
            f"(format: {result.get('format_detected', 'unknown')})"
        )
    
    if result["ambiguous_flag"]:
        logger.warning(
            f"[Node5] Ambiguous timestamp format detected: {timestamp_str} "
            f"(no context for inference)"
        )
    
    return result

