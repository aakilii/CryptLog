"""
Timestamp Parsing and Normalization
Chronograph: Timeline Sync
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List

# Optional dependency: python-dateutil provides robust fuzzy parsing.
# We keep a graceful stdlib fallback so Phase 2 does not hard-fail if the
# dependency is missing in a given deployment environment.
try:
    from dateutil import parser as date_parser  # type: ignore
except Exception:  # pragma: no cover
    date_parser = None


ISO_8601_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
)

AMBIGUOUS_DATE_PATTERN = re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')

# Common timestamp patterns in log files
TIMESTAMP_PATTERNS = [
    # ISO 8601 variants
    re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?'),
    # RFC 2822 / RFC 822
    re.compile(r'[A-Za-z]{3}, \d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2} [A-Z]{3,5}'),
    # Apache / Common Log Format
    re.compile(r'\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}'),
    # Syslog (RFC 3164)
    re.compile(r'[A-Za-z]{3} \d{1,2} \d{2}:\d{2}:\d{2}'),
    # Windows Event Log
    re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'),
    # Unix timestamp (10 digits)
    re.compile(r'\b\d{10}\b'),
    # Unix timestamp with milliseconds (13 digits)
    re.compile(r'\b\d{13}\b'),
    # Date formats
    re.compile(r'\d{4}[/-]\d{2}[/-]\d{2}'),
    re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),
    # Time formats
    re.compile(r'\d{2}:\d{2}:\d{2}(\.\d+)?'),
]


def extract_timestamp_from_line(log_line: str) -> Optional[str]:
    """
    Extract timestamp string from a log line using pattern matching.
    
    Args:
        log_line: Full log line text
    
    Returns:
        Extracted timestamp string, or None if not found
    """
    if not log_line:
        return None
    
    # Try each pattern in order of specificity.
    # Use match.group(0) rather than findall(), because several patterns include
    # capturing groups which makes findall() return tuples instead of the full match.
    for pattern in TIMESTAMP_PATTERNS:
        m = pattern.search(log_line)
        if m:
            return m.group(0)
    
    # Fallback: try to find date-like patterns at the start of the line
    # Common format: timestamp at the beginning
    parts = log_line.strip().split()
    if parts:
        # Check first few tokens for timestamp-like patterns
        for i in range(min(3, len(parts))):
            candidate = ' '.join(parts[:i+1])
            if any(pattern.search(candidate) for pattern in TIMESTAMP_PATTERNS[:5]):
                return candidate
    
    return None


def parse_timestamp(timestamp_str: str, source_ip: Optional[str] = None) -> Optional[datetime]:
    """
    Parse timestamp from various formats.
    
    Supports:
    - ISO 8601 (2024-01-15T10:30:00Z, 2024-01-15 10:30:00+05:30)
    - RFC 2822 (Mon, 15 Jan 2024 10:30:00 GMT)
    - Apache/Common Log (15/Jan/2024:10:30:00 +0530)
    - Syslog (Jan 15 10:30:00)
    - Windows Event Log (2024-01-15 10:30:00)
    - Unix timestamps (1705312200, 1705312200000)
    - Various date formats (2024-01-15, 01/15/2024)
    
    Args:
        timestamp_str: Timestamp string in various formats
        source_ip: Source IP for context (used in heuristic inference)
    
    Returns:
        datetime object in UTC, or None if parsing fails
    """
    if not timestamp_str:
        return None
    
    timestamp_str = timestamp_str.strip()
    
    # Try python-dateutil if available (handles most formats, supports fuzzy parsing)
    if date_parser is not None:
        try:
            dt = date_parser.parse(timestamp_str, fuzzy=True)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass

    # Stdlib fallbacks (no fuzzy parsing)
    # 1) ISO-8601
    try:
        iso = timestamp_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso.replace("T", " "))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # 2) Common explicit formats
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%b/%Y:%H:%M:%S %z",  # Apache common log
        "%b %d %H:%M:%S",  # Syslog (no year)
    ):
        try:
            dt = datetime.strptime(timestamp_str, fmt)
            if fmt == "%b %d %H:%M:%S":
                dt = dt.replace(year=datetime.now(timezone.utc).year)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    
    # Try Unix timestamp (seconds since epoch)
    try:
        unix_ts = float(timestamp_str)
        # Valid range: 1970-01-01 to 2038-01-19 (32-bit signed int max)
        if 0 < unix_ts < 2147483647:
            return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    except Exception:
        pass
    
    # Try Unix timestamp in milliseconds
    try:
        unix_ts_ms = float(timestamp_str)
        if 1000000000000 < unix_ts_ms < 9999999999999:  # 13 digits
            return datetime.fromtimestamp(unix_ts_ms / 1000, tz=timezone.utc)
    except Exception:
        pass
    
    # Try ISO 8601 pattern match
    if ISO_8601_PATTERN.match(timestamp_str):
        try:
            # Remove 'T' or space, normalize
            normalized = timestamp_str.replace('T', ' ').replace('Z', '+00:00')
            dt = date_parser.parse(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    
    return None


def is_ambiguous_date(date_str: str) -> bool:
    """
    Check if date format is ambiguous (e.g., 05/04 could be May 4 or April 5).
    
    Args:
        date_str: Date string to check
    
    Returns:
        True if date format is ambiguous
    """
    return bool(AMBIGUOUS_DATE_PATTERN.match(date_str))


def infer_date_format(
    ambiguous_date: str,
    previous_logs: list[dict],
    source_ip: Optional[str] = None
) -> Tuple[Optional[str], bool]:
    """
    Infer date format from previous logs.
    
    Args:
        ambiguous_date: Ambiguous date string (e.g., "05/04/2024")
        previous_logs: List of previous log entries with timestamps
        source_ip: Source IP for filtering context
    
    Returns:
        (deduced_format: "DD/MM" or "MM/DD", has_context: bool)
    """
    if not previous_logs:
        return None, False
    
    dd_mm_count = 0
    mm_dd_count = 0
    
    for log in previous_logs[:50]:
        if source_ip and log.get("source_ip") != source_ip:
            continue
        
        ts_str = str(log.get("timestamp", ""))
        if not ts_str:
            continue
        
        try:
            if date_parser is None:
                continue
            parsed = date_parser.parse(ts_str, fuzzy=True)
            day = parsed.day
            month = parsed.month
            
            parts = ambiguous_date.replace('-', '/').split('/')
            if len(parts) >= 2:
                first = int(parts[0])
                second = int(parts[1])
                
                if first == day and second == month:
                    dd_mm_count += 1
                elif first == month and second == day:
                    mm_dd_count += 1
        except Exception:
            continue
    
    if dd_mm_count > mm_dd_count:
        return "DD/MM", True
    elif mm_dd_count > dd_mm_count:
        return "MM/DD", True
    
    return None, False


def detect_timezone_offset(timestamp_str: str) -> Optional[timedelta]:
    """
    Detect timezone offset from timestamp string.
    
    Args:
        timestamp_str: Timestamp string that may contain timezone info
    
    Returns:
        timedelta representing timezone offset, or None
    """
    # Look for timezone patterns: +05:30, -08:00, +0530, GMT, UTC, etc.
    tz_patterns = [
        (re.compile(r'([+-])(\d{2}):?(\d{2})\b'), lambda m: timedelta(
            hours=int(m.group(2)), minutes=int(m.group(3)) if m.group(3) else 0
        ) if m.group(1) == '+' else timedelta(
            hours=-int(m.group(2)), minutes=-int(m.group(3)) if m.group(3) else 0
        )),
        (re.compile(r'\bUTC\b', re.IGNORECASE), lambda m: timedelta(0)),
        (re.compile(r'\bGMT\b', re.IGNORECASE), lambda m: timedelta(0)),
        (re.compile(r'\bZ\b'), lambda m: timedelta(0)),
    ]
    
    for pattern, converter in tz_patterns:
        match = pattern.search(timestamp_str)
        if match:
            try:
                return converter(match)
            except Exception:
                continue
    
    return None


def normalize_timestamp(
    timestamp_str: str,
    source_ip: Optional[str] = None,
    previous_logs: Optional[list] = None,
    time_delta: Optional[timedelta] = None
) -> dict:
    """
    Normalize timestamp to ISO-8601 UTC.
    
    Args:
        timestamp_str: Input timestamp string
        source_ip: Source IP for context
        previous_logs: Previous logs for format inference
        time_delta: Timezone offset to apply (overrides auto-detection)
    
    Returns:
        {
            "normalized": datetime | None,
            "normalized_iso": str | None,
            "original": str,
            "format_detected": str,
            "ambiguous": bool,
            "ambiguous_flag": bool,
            "timezone_detected": str | None
        }
    """
    original = timestamp_str
    ambiguous_flag = False
    format_detected = "unknown"
    timezone_detected = None
    
    # Detect timezone from timestamp string if not provided
    if time_delta is None:
        detected_tz = detect_timezone_offset(timestamp_str)
        if detected_tz:
            time_delta = detected_tz
            timezone_detected = str(detected_tz)
    
    # Handle ambiguous dates (DD/MM vs MM/DD)
    if is_ambiguous_date(timestamp_str):
        if previous_logs:
            format_deduced, has_context = infer_date_format(
                timestamp_str,
                previous_logs,
                source_ip
            )
            
            if not has_context:
                ambiguous_flag = True
            
            if format_deduced == "DD/MM":
                parts = timestamp_str.replace('-', '/').split('/')
                if len(parts) >= 3:
                    timestamp_str = f"{parts[1]}/{parts[0]}/{parts[2]}"
                    format_detected = "DD/MM (inferred)"
        else:
            ambiguous_flag = True
            format_detected = "ambiguous (no context)"
    
    # Detect format type
    if ISO_8601_PATTERN.match(timestamp_str):
        format_detected = "ISO-8601"
    elif re.search(r'[A-Za-z]{3}, \d{1,2} [A-Za-z]{3}', timestamp_str):
        format_detected = "RFC-2822"
    elif re.search(r'\d{2}/[A-Za-z]{3}/\d{4}', timestamp_str):
        format_detected = "Apache/Common Log"
    elif re.search(r'[A-Za-z]{3} \d{1,2} \d{2}:\d{2}:\d{2}', timestamp_str):
        format_detected = "Syslog (RFC-3164)"
    elif re.match(r'^\d{10,13}$', timestamp_str):
        format_detected = "Unix timestamp"
    elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', timestamp_str):
        format_detected = "Windows Event Log"
    
    parsed = parse_timestamp(timestamp_str, source_ip)
    
    # Apply timezone offset if provided
    if parsed and time_delta:
        # If parsed datetime already has timezone, convert it
        # Otherwise, assume it's in the detected timezone and adjust
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) == timedelta(0):
            # No timezone or UTC, apply the offset
            parsed = parsed - time_delta  # Subtract to convert to UTC
        else:
            # Has timezone, just ensure UTC
            parsed = parsed.astimezone(timezone.utc)
    
    if parsed:
        parsed = parsed.astimezone(timezone.utc)
        normalized_iso = parsed.isoformat()
    else:
        normalized_iso = None
    
    return {
        "normalized": parsed,
        "normalized_iso": normalized_iso,
        "original": original,
        "format_detected": format_detected,
        "ambiguous": is_ambiguous_date(original),
        "ambiguous_flag": ambiguous_flag,
        "timezone_detected": timezone_detected
    }

