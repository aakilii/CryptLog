"""
Unified Log Parser — Common schema for all forensic log sources.

Normalizes events from multiple log sources into a unified event structure
that integrates with the Evidence Vault and Timeline modules.

Every event includes:
- Normalized timestamp (UTC)
- Event type categorization
- Actor/subject information
- Target/object information
- Source log reference
- SHA-256 hash for integrity
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Categorized event types for forensic analysis."""
    # File Operations
    FILE_CREATE = "file_create"
    FILE_DELETE = "file_delete"
    FILE_MODIFY = "file_modify"
    FILE_COPY = "file_copy"
    FILE_MOVE = "file_move"
    FILE_READ = "file_read"
    FILE_RENAME = "file_rename"
    
    # USB Events
    USB_CONNECT = "usb_connect"
    USB_DISCONNECT = "usb_disconnect"
    USB_TRANSFER = "usb_transfer"
    USB_DEVICE_INSTALL = "usb_device_install"
    
    # Bluetooth Events
    BLUETOOTH_PAIR = "bluetooth_pair"
    BLUETOOTH_CONNECT = "bluetooth_connect"
    BLUETOOTH_DISCONNECT = "bluetooth_disconnect"
    BLUETOOTH_TRANSFER = "bluetooth_transfer"
    
    # Email Events
    EMAIL_SEND = "email_send"
    EMAIL_RECEIVE = "email_receive"
    EMAIL_ATTACH = "email_attach"
    EMAIL_OPEN = "email_open"
    
    # Authentication
    AUTH_LOGON = "auth_logon"
    AUTH_LOGOFF = "auth_logoff"
    AUTH_FAILED = "auth_failed"
    AUTH_PRIVILEGE_ESCALATION = "auth_privilege_escalation"
    
    # Network
    NETWORK_CONNECT = "network_connect"
    NETWORK_DISCONNECT = "network_disconnect"
    NETWORK_DATA_TRANSFER = "network_data_transfer"
    NETWORK_DNS_QUERY = "network_dns_query"
    
    # Process
    PROCESS_START = "process_start"
    PROCESS_END = "process_end"
    PROCESS_INJECTION = "process_injection"
    
    # System
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    
    # Generic
    OTHER = "other"


class EventSeverity(str, Enum):
    """Severity levels for forensic events."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class UnifiedEvent:
    """
    Unified event structure for all log sources.
    
    This is the canonical representation of a forensic event that can be
    stored in the Evidence Vault and used in Timeline analysis.
    """
    # Core identifiers
    event_id: str
    timestamp: datetime
    event_type: EventType
    severity: EventSeverity
    
    # Actor (who/what caused the event)
    actor_type: str  # user, process, system, device
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_domain: Optional[str] = None
    
    # Target (what was affected)
    target_type: str = ""  # file, device, network, process
    target_id: Optional[str] = None
    target_name: Optional[str] = None
    target_path: Optional[str] = None
    
    # Source information
    source_log: str = ""
    source_device: Optional[str] = None
    source_ip: Optional[str] = None
    source_hostname: Optional[str] = None
    
    # Destination (for transfers)
    dest_device: Optional[str] = None
    dest_ip: Optional[str] = None
    dest_hostname: Optional[str] = None
    dest_path: Optional[str] = None
    
    # Detailed data
    description: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    classification: Optional[str] = None  # CONFIDENTIAL, RESTRICTED, PUBLIC
    
    # Integrity
    event_hash: str = ""  # SHA-256 of the event data
    
    def __post_init__(self):
        """Compute event hash after initialization."""
        if not self.event_hash:
            self.event_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of event data."""
        data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "source_log": self.source_log,
            "description": self.description,
        }
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "severity": self.severity.value if isinstance(self.severity, Enum) else self.severity,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_domain": self.actor_domain,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "target_path": self.target_path,
            "source_log": self.source_log,
            "source_device": self.source_device,
            "source_ip": self.source_ip,
            "source_hostname": self.source_hostname,
            "dest_device": self.dest_device,
            "dest_ip": self.dest_ip,
            "dest_hostname": self.dest_hostname,
            "dest_path": self.dest_path,
            "description": self.description,
            "raw_data": self.raw_data,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "classification": self.classification,
            "event_hash": self.event_hash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnifiedEvent":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        event_type = data.get("event_type", "other")
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type)
            except ValueError:
                event_type = EventType.OTHER
        
        severity = data.get("severity", "info")
        if isinstance(severity, str):
            try:
                severity = EventSeverity(severity)
            except ValueError:
                severity = EventSeverity.INFO
        
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=timestamp,
            event_type=event_type,
            severity=severity,
            actor_type=data.get("actor_type", "unknown"),
            actor_id=data.get("actor_id"),
            actor_name=data.get("actor_name"),
            actor_domain=data.get("actor_domain"),
            target_type=data.get("target_type", ""),
            target_id=data.get("target_id"),
            target_name=data.get("target_name"),
            target_path=data.get("target_path"),
            source_log=data.get("source_log", ""),
            source_device=data.get("source_device"),
            source_ip=data.get("source_ip"),
            source_hostname=data.get("source_hostname"),
            dest_device=data.get("dest_device"),
            dest_ip=data.get("dest_ip"),
            dest_hostname=data.get("dest_hostname"),
            dest_path=data.get("dest_path"),
            description=data.get("description", ""),
            raw_data=data.get("raw_data", {}),
            file_size=data.get("file_size"),
            file_hash=data.get("file_hash"),
            classification=data.get("classification"),
            event_hash=data.get("event_hash", ""),
        )


def normalize_timestamp(
    ts: Union[str, datetime, int, float],
    timezone_str: Optional[str] = None
) -> datetime:
    """
    Normalize various timestamp formats to UTC datetime.
    
    Args:
        ts: Timestamp in various formats (ISO string, datetime, unix epoch)
        timezone_str: Optional timezone for naive datetimes
        
    Returns:
        datetime in UTC
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            # Naive datetime - assume UTC
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)
    
    if isinstance(ts, (int, float)):
        # Unix timestamp
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    
    if isinstance(ts, str):
        # Try various formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S %p",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(ts, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        
        # Try ISO format with fromisoformat
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
        
        raise ValueError(f"Unable to parse timestamp: {ts}")
    
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


class UnifiedLogParser:
    """
    Unified log parser that delegates to format-specific parsers.
    
    Automatically detects log format and parses to UnifiedEvent schema.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[UnifiedEvent] = []
        self.parsers = {}
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"EV-{self.case_id}-{self._event_counter:05d}"
    
    def detect_format(self, file_path: Path) -> str:
        """
        Detect log format from file extension and content.
        
        Returns: Format identifier (evtx, csv, json, syslog, etc.)
        """
        suffix = file_path.suffix.lower()
        
        format_map = {
            ".evtx": "evtx",
            ".evt": "evt",
            ".log": "syslog",
            ".csv": "csv",
            ".json": "json",
            ".xml": "xml",
            ".txt": "text",
        }
        
        if suffix in format_map:
            return format_map[suffix]
        
        # Try to detect from content
        try:
            with open(file_path, 'rb') as f:
                header = f.read(32)
                # EVTX magic
                if header[:8] == b'ElfFile\x00':
                    return "evtx"
                # JSON
                if header.strip().startswith(b'{') or header.strip().startswith(b'['):
                    return "json"
                # XML
                if header.strip().startswith(b'<?xml') or header.strip().startswith(b'<'):
                    return "xml"
        except Exception:
            pass
        
        return "unknown"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None,
        time_range: Optional[tuple] = None
    ) -> List[UnifiedEvent]:
        """
        Parse a log file and return unified events.
        
        Args:
            file_path: Path to log file
            source_device: Device identifier (e.g., hostname)
            time_range: Optional (start, end) datetime tuple for filtering
            
        Returns:
            List of UnifiedEvent objects
        """
        file_path = Path(file_path)
        format_type = self.detect_format(file_path)
        
        logger.info(f"Parsing {file_path} as {format_type}")
        
        events = []
        
        if format_type == "evtx":
            from .evtx_parser import WindowsEventLogParser
            parser = WindowsEventLogParser(self.case_id)
            events = parser.parse_file(file_path, source_device)
        
        elif format_type == "json":
            events = self._parse_json_log(file_path, source_device)
        
        elif format_type == "csv":
            events = self._parse_csv_log(file_path, source_device)
        
        elif format_type in ("syslog", "text"):
            events = self._parse_text_log(file_path, source_device)
        
        # Filter by time range if specified
        if time_range and len(time_range) == 2:
            start, end = time_range
            events = [
                e for e in events
                if start <= e.timestamp <= end
            ]
        
        self.events.extend(events)
        return events
    
    def _parse_json_log(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse JSON formatted logs."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                
                # Handle JSON Lines format
                if content.startswith('['):
                    data = json.loads(content)
                else:
                    data = [json.loads(line) for line in content.split('\n') if line.strip()]
                
                for item in data:
                    event = self._json_to_event(item, file_path.name, source_device)
                    if event:
                        events.append(event)
        
        except Exception as e:
            logger.error(f"Error parsing JSON log {file_path}: {e}")
        
        return events
    
    def _json_to_event(
        self,
        data: Dict[str, Any],
        source_log: str,
        source_device: Optional[str]
    ) -> Optional[UnifiedEvent]:
        """Convert JSON record to UnifiedEvent."""
        try:
            # Try to extract timestamp from common fields
            ts_fields = ['timestamp', '@timestamp', 'time', 'datetime', 'date', 'ts']
            timestamp = None
            for field in ts_fields:
                if field in data:
                    timestamp = normalize_timestamp(data[field])
                    break
            
            if not timestamp:
                timestamp = datetime.now(timezone.utc)
            
            # Determine event type
            event_type = self._classify_event(data)
            
            # Determine severity
            severity = self._classify_severity(data)
            
            return UnifiedEvent(
                event_id=self._generate_event_id(),
                timestamp=timestamp,
                event_type=event_type,
                severity=severity,
                actor_type=data.get("actor_type", "unknown"),
                actor_id=data.get("user", data.get("actor_id", data.get("subject_user"))),
                actor_name=data.get("user_name", data.get("actor_name")),
                target_type=data.get("target_type", ""),
                target_id=data.get("object_name", data.get("target_id")),
                target_name=data.get("target_name"),
                target_path=data.get("file_path", data.get("object_path")),
                source_log=source_log,
                source_device=source_device,
                source_ip=data.get("source_ip", data.get("src_ip")),
                dest_ip=data.get("dest_ip", data.get("dst_ip")),
                description=data.get("message", data.get("description", "")),
                raw_data=data,
            )
        
        except Exception as e:
            logger.error(f"Error converting JSON to event: {e}")
            return None
    
    def _parse_csv_log(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse CSV formatted logs."""
        import csv
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    event = self._json_to_event(row, file_path.name, source_device)
                    if event:
                        events.append(event)
        
        except Exception as e:
            logger.error(f"Error parsing CSV log {file_path}: {e}")
        
        return events
    
    def _parse_text_log(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse plain text/syslog formatted logs."""
        import re
        events = []
        
        # Common syslog patterns
        syslog_patterns = [
            # Standard syslog: Mar 14 10:15:23 hostname process[pid]: message
            r'^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<process>\S+)(?:\[(?P<pid>\d+)\])?:\s+(?P<message>.*)$',
            # ISO timestamp: 2024-03-14T10:15:23.000Z hostname process: message
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<host>\S+)\s+(?P<process>\S+):\s+(?P<message>.*)$',
        ]
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    for pattern in syslog_patterns:
                        match = re.match(pattern, line)
                        if match:
                            data = match.groupdict()
                            
                            # Parse timestamp
                            if 'timestamp' in data:
                                timestamp = normalize_timestamp(data['timestamp'])
                            else:
                                # Construct from month/day/time (assume current year)
                                year = datetime.now().year
                                ts_str = f"{year} {data.get('month', 'Jan')} {data.get('day', '1')} {data.get('time', '00:00:00')}"
                                try:
                                    timestamp = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S")
                                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                                except ValueError:
                                    timestamp = datetime.now(timezone.utc)
                            
                            event = UnifiedEvent(
                                event_id=self._generate_event_id(),
                                timestamp=timestamp,
                                event_type=EventType.OTHER,
                                severity=EventSeverity.INFO,
                                actor_type="process",
                                actor_name=data.get('process', 'unknown'),
                                source_log=file_path.name,
                                source_device=source_device or data.get('host'),
                                source_hostname=data.get('host'),
                                description=data.get('message', line),
                                raw_data={"line_number": line_num, "raw_line": line},
                            )
                            events.append(event)
                            break
        
        except Exception as e:
            logger.error(f"Error parsing text log {file_path}: {e}")
        
        return events
    
    def _classify_event(self, data: Dict[str, Any]) -> EventType:
        """Classify event type from data fields."""
        # Check for explicit event type
        if "event_type" in data:
            try:
                return EventType(data["event_type"])
            except ValueError:
                pass
        
        # Check for Windows Event IDs
        event_id = data.get("EventID", data.get("event_id"))
        if event_id:
            return self._windows_event_to_type(event_id)
        
        # Check message for keywords
        message = str(data.get("message", data.get("description", ""))).lower()
        
        if any(kw in message for kw in ["usb", "removable", "storage device"]):
            if any(kw in message for kw in ["connect", "insert", "arrive"]):
                return EventType.USB_CONNECT
            if any(kw in message for kw in ["disconnect", "remove", "eject"]):
                return EventType.USB_DISCONNECT
        
        if "bluetooth" in message:
            if "pair" in message:
                return EventType.BLUETOOTH_PAIR
            if "transfer" in message:
                return EventType.BLUETOOTH_TRANSFER
        
        if any(kw in message for kw in ["email", "mail", "smtp"]):
            if "sent" in message:
                return EventType.EMAIL_SEND
            if "received" in message:
                return EventType.EMAIL_RECEIVE
        
        if any(kw in message for kw in ["logon", "login", "authentication"]):
            if "failed" in message:
                return EventType.AUTH_FAILED
            return EventType.AUTH_LOGON
        
        if any(kw in message for kw in ["logoff", "logout"]):
            return EventType.AUTH_LOGOFF
        
        if any(kw in message for kw in ["created", "create"]):
            return EventType.FILE_CREATE
        
        if any(kw in message for kw in ["deleted", "delete"]):
            return EventType.FILE_DELETE
        
        if any(kw in message for kw in ["modified", "modify", "changed", "change"]):
            return EventType.FILE_MODIFY
        
        if any(kw in message for kw in ["copied", "copy"]):
            return EventType.FILE_COPY
        
        return EventType.OTHER
    
    def _windows_event_to_type(self, event_id: int) -> EventType:
        """Map Windows Event ID to EventType."""
        mapping = {
            # Security events
            4624: EventType.AUTH_LOGON,
            4625: EventType.AUTH_FAILED,
            4634: EventType.AUTH_LOGOFF,
            4647: EventType.AUTH_LOGOFF,
            4648: EventType.AUTH_LOGON,
            4672: EventType.AUTH_PRIVILEGE_ESCALATION,
            4663: EventType.FILE_READ,
            4656: EventType.FILE_READ,
            4658: EventType.FILE_READ,
            4660: EventType.FILE_DELETE,
            4670: EventType.FILE_MODIFY,
            # System events
            7045: EventType.PROCESS_START,
            6005: EventType.SYSTEM_STARTUP,
            6006: EventType.SYSTEM_SHUTDOWN,
            # USB events
            2003: EventType.USB_CONNECT,
            2100: EventType.USB_DISCONNECT,
            # Process events
            4688: EventType.PROCESS_START,
            4689: EventType.PROCESS_END,
        }
        return mapping.get(event_id, EventType.OTHER)
    
    def _classify_severity(self, data: Dict[str, Any]) -> EventSeverity:
        """Classify event severity from data fields."""
        # Check for explicit severity
        severity = data.get("severity", data.get("level", data.get("Level", ""))).lower()
        
        severity_map = {
            "critical": EventSeverity.CRITICAL,
            "error": EventSeverity.HIGH,
            "warning": EventSeverity.MEDIUM,
            "warn": EventSeverity.MEDIUM,
            "info": EventSeverity.LOW,
            "information": EventSeverity.LOW,
            "debug": EventSeverity.INFO,
            "verbose": EventSeverity.INFO,
        }
        
        if severity in severity_map:
            return severity_map[severity]
        
        # Check for audit events
        keywords = data.get("Keywords", "")
        if "Audit Failure" in str(keywords):
            return EventSeverity.HIGH
        if "Audit Success" in str(keywords):
            return EventSeverity.LOW
        
        return EventSeverity.INFO
    
    def get_events_by_type(self, event_type: EventType) -> List[UnifiedEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_in_range(
        self,
        start: datetime,
        end: datetime
    ) -> List[UnifiedEvent]:
        """Get events within a time range."""
        return [
            e for e in self.events
            if start <= e.timestamp <= end
        ]
    
    def get_events_by_actor(self, actor_id: str) -> List[UnifiedEvent]:
        """Get all events by a specific actor."""
        return [e for e in self.events if e.actor_id == actor_id]
    
    def export_to_json(self) -> str:
        """Export all events to JSON."""
        return json.dumps(
            [e.to_dict() for e in self.events],
            indent=2,
            default=str
        )


async def parse_all_logs(
    case_id: str,
    log_paths: List[Union[str, Path]],
    source_device: Optional[str] = None,
    time_range: Optional[tuple] = None
) -> List[UnifiedEvent]:
    """
    Parse multiple log files asynchronously.
    
    Args:
        case_id: Case identifier
        log_paths: List of paths to log files
        source_device: Device identifier
        time_range: Optional (start, end) datetime tuple
        
    Returns:
        List of UnifiedEvent objects from all logs
    """
    parser = UnifiedLogParser(case_id)
    all_events = []
    
    for path in log_paths:
        events = parser.parse_file(path, source_device, time_range)
        all_events.extend(events)
    
    # Sort by timestamp
    all_events.sort(key=lambda e: e.timestamp)
    
    return all_events
