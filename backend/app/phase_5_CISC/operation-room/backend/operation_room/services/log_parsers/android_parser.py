"""
Android Log Parser — Parse Android device logs for forensic analysis.

Supports parsing:
- logcat output (text and JSON formats)
- Bluetooth OPP transfer logs
- MTP (Media Transfer Protocol) logs
- System event logs
- Application logs

These logs are typically extracted using:
- ADB (Android Debug Bridge)
- Mobile forensic tools (Cellebrite, MSAB XRY, Oxygen)
- Manual extraction from /data/log directories
"""

import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from .unified_parser import (
    UnifiedEvent, EventType, EventSeverity, normalize_timestamp
)

logger = logging.getLogger(__name__)


# Android log priority levels
LOG_PRIORITIES = {
    'V': EventSeverity.INFO,      # Verbose
    'D': EventSeverity.INFO,      # Debug
    'I': EventSeverity.LOW,       # Info
    'W': EventSeverity.MEDIUM,    # Warning
    'E': EventSeverity.HIGH,      # Error
    'F': EventSeverity.CRITICAL,  # Fatal
    'S': EventSeverity.INFO,      # Silent
}

# Common Android components for forensic analysis
FORENSIC_COMPONENTS = {
    'BluetoothOppService': 'bluetooth_transfer',
    'BluetoothOppUtility': 'bluetooth_transfer',
    'BluetoothShare': 'bluetooth_transfer',
    'BluetoothAdapter': 'bluetooth_connect',
    'BluetoothBondStateMachine': 'bluetooth_pair',
    'MtpService': 'usb_transfer',
    'MtpServer': 'usb_transfer',
    'UsbDeviceManager': 'usb_connect',
    'DownloadManager': 'file_download',
    'Gmail': 'email',
    'Email': 'email',
    'ActivityManager': 'process',
    'PackageManager': 'app_install',
}


class AndroidLogParser:
    """
    Parser for Android log files.
    
    Supports multiple formats:
    - Standard logcat text output
    - JSON logcat output (--format=json)
    - Dumpsys output
    - Extracted database exports
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[UnifiedEvent] = []
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"AND-{self.case_id}-{self._event_counter:05d}"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse an Android log file.
        
        Auto-detects format based on content.
        
        Args:
            file_path: Path to log file
            source_device: Device identifier (e.g., IMEI, serial)
            
        Returns:
            List of UnifiedEvent objects
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Detect format from content
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
            
            if first_line.startswith('{') or first_line.startswith('['):
                return self._parse_json_logcat(file_path, source_device)
            elif self._is_logcat_format(first_line):
                return self._parse_text_logcat(file_path, source_device)
            else:
                # Try generic parsing
                return self._parse_generic_log(file_path, source_device)
                
        except Exception as e:
            logger.error(f"Error parsing Android log {file_path}: {e}")
            return []
    
    def _is_logcat_format(self, line: str) -> bool:
        """Check if line matches logcat format."""
        # Standard logcat: "03-14 10:15:23.456  1234  5678 I TAG: message"
        # Brief format: "I/TAG(1234): message"
        # Thread format: "03-14 10:15:23.456 1234 I TAG: message"
        patterns = [
            r'^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[VDIWEFS]\s+',
            r'^[VDIWEFS]/[^:]+\(\s*\d+\):\s+',
            r'^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+[VDIWEFS]\s+',
        ]
        return any(re.match(p, line) for p in patterns)
    
    def _parse_text_logcat(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse standard logcat text output."""
        events = []
        
        # Logcat patterns
        patterns = [
            # Threadtime format: "03-14 10:15:23.456  1234  5678 I TagName: message"
            re.compile(
                r'^(?P<month>\d{2})-(?P<day>\d{2})\s+'
                r'(?P<time>\d{2}:\d{2}:\d{2})\.(?P<ms>\d+)\s+'
                r'(?P<pid>\d+)\s+(?P<tid>\d+)\s+'
                r'(?P<priority>[VDIWEFS])\s+'
                r'(?P<tag>[^:]+):\s*'
                r'(?P<message>.*)$'
            ),
            # Brief format: "I/TagName(1234): message"
            re.compile(
                r'^(?P<priority>[VDIWEFS])/(?P<tag>[^\(]+)\(\s*(?P<pid>\d+)\):\s*(?P<message>.*)$'
            ),
            # Time format: "03-14 10:15:23.456 I/TagName: message"
            re.compile(
                r'^(?P<month>\d{2})-(?P<day>\d{2})\s+'
                r'(?P<time>\d{2}:\d{2}:\d{2})\.(?P<ms>\d+)\s+'
                r'(?P<priority>[VDIWEFS])/(?P<tag>[^:]+):\s*'
                r'(?P<message>.*)$'
            ),
        ]
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                year = datetime.now().year
                
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    for pattern in patterns:
                        match = pattern.match(line)
                        if match:
                            data = match.groupdict()
                            
                            # Parse timestamp
                            if 'month' in data and 'time' in data:
                                ts_str = f"{year}-{data['month']}-{data['day']} {data['time']}"
                                if 'ms' in data:
                                    ts_str += f".{data['ms'][:3]}"
                                timestamp = normalize_timestamp(ts_str)
                            else:
                                timestamp = datetime.now(timezone.utc)
                            
                            # Classify event
                            tag = data.get('tag', '').strip()
                            message = data.get('message', '')
                            event_type, target_type = self._classify_android_event(tag, message)
                            
                            # Priority to severity
                            priority = data.get('priority', 'I')
                            severity = LOG_PRIORITIES.get(priority, EventSeverity.INFO)
                            
                            event = UnifiedEvent(
                                event_id=self._generate_event_id(),
                                timestamp=timestamp,
                                event_type=event_type,
                                severity=severity,
                                actor_type="process",
                                actor_id=data.get('pid'),
                                actor_name=tag,
                                target_type=target_type,
                                source_log=file_path.name,
                                source_device=source_device,
                                description=message,
                                raw_data={
                                    "line_number": line_num,
                                    "tag": tag,
                                    "priority": priority,
                                    "pid": data.get('pid'),
                                    "tid": data.get('tid'),
                                    "message": message,
                                },
                            )
                            events.append(event)
                            break
                            
        except Exception as e:
            logger.error(f"Error parsing logcat {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_json_logcat(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse JSON format logcat output."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Handle JSON array or newline-delimited JSON
            if content.startswith('['):
                records = json.loads(content)
            else:
                records = [json.loads(line) for line in content.split('\n') if line.strip()]
            
            for record in records:
                timestamp = normalize_timestamp(
                    record.get('timestamp', record.get('time', datetime.now().isoformat()))
                )
                
                tag = record.get('tag', record.get('component', ''))
                message = record.get('message', record.get('msg', ''))
                event_type, target_type = self._classify_android_event(tag, message)
                
                priority = record.get('priority', record.get('level', 'I'))
                severity = LOG_PRIORITIES.get(priority[0].upper(), EventSeverity.INFO)
                
                event = UnifiedEvent(
                    event_id=self._generate_event_id(),
                    timestamp=timestamp,
                    event_type=event_type,
                    severity=severity,
                    actor_type="process",
                    actor_id=str(record.get('pid', '')),
                    actor_name=tag,
                    target_type=target_type,
                    source_log=file_path.name,
                    source_device=source_device,
                    description=message,
                    raw_data=record,
                )
                events.append(event)
                
        except Exception as e:
            logger.error(f"Error parsing JSON logcat {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_generic_log(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse generic Android log format."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Try to extract timestamp and message
                    timestamp = datetime.now(timezone.utc)
                    message = line
                    
                    # Common timestamp patterns
                    ts_patterns = [
                        r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+(.*)$',
                        r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.*)$',
                    ]
                    
                    for pattern in ts_patterns:
                        match = re.match(pattern, line)
                        if match:
                            try:
                                timestamp = normalize_timestamp(match.group(1))
                                message = match.group(2)
                            except Exception:
                                pass
                            break
                    
                    event_type, target_type = self._classify_android_event('', message)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=EventSeverity.INFO,
                        actor_type="system",
                        source_log=file_path.name,
                        source_device=source_device,
                        description=message,
                        raw_data={"line_number": line_num, "raw_line": line},
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing generic log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _classify_android_event(
        self,
        tag: str,
        message: str
    ) -> tuple:
        """
        Classify Android event based on tag and message.
        
        Returns: (EventType, target_type)
        """
        tag_lower = tag.lower()
        msg_lower = message.lower()
        
        # Bluetooth events
        if 'bluetooth' in tag_lower or 'bt' in tag_lower:
            if any(kw in msg_lower for kw in ['transfer', 'receive', 'send', 'opp']):
                return EventType.BLUETOOTH_TRANSFER, 'file'
            if any(kw in msg_lower for kw in ['pair', 'bond', 'bonded']):
                return EventType.BLUETOOTH_PAIR, 'device'
            if any(kw in msg_lower for kw in ['connect', 'connected']):
                return EventType.BLUETOOTH_CONNECT, 'device'
            if any(kw in msg_lower for kw in ['disconnect', 'disconnected']):
                return EventType.BLUETOOTH_DISCONNECT, 'device'
            return EventType.BLUETOOTH_CONNECT, 'device'
        
        # USB/MTP events
        if any(kw in tag_lower for kw in ['mtp', 'usb']):
            if any(kw in msg_lower for kw in ['transfer', 'file', 'copy']):
                return EventType.USB_TRANSFER, 'file'
            if any(kw in msg_lower for kw in ['connect', 'attached']):
                return EventType.USB_CONNECT, 'device'
            if any(kw in msg_lower for kw in ['disconnect', 'detached']):
                return EventType.USB_DISCONNECT, 'device'
            return EventType.USB_CONNECT, 'device'
        
        # Email events
        if any(kw in tag_lower for kw in ['email', 'gmail', 'mail']):
            if any(kw in msg_lower for kw in ['send', 'sent', 'outgoing']):
                return EventType.EMAIL_SEND, 'email'
            if any(kw in msg_lower for kw in ['receive', 'received', 'incoming', 'download']):
                return EventType.EMAIL_RECEIVE, 'email'
            if any(kw in msg_lower for kw in ['attach', 'attachment']):
                return EventType.EMAIL_ATTACH, 'file'
            return EventType.EMAIL_RECEIVE, 'email'
        
        # File operations
        if any(kw in tag_lower for kw in ['download', 'file']):
            if any(kw in msg_lower for kw in ['complete', 'finished', 'saved']):
                return EventType.FILE_CREATE, 'file'
            if any(kw in msg_lower for kw in ['delete', 'removed']):
                return EventType.FILE_DELETE, 'file'
            return EventType.FILE_CREATE, 'file'
        
        # Process events
        if 'activitymanager' in tag_lower:
            if any(kw in msg_lower for kw in ['start', 'starting', 'launch']):
                return EventType.PROCESS_START, 'process'
            if any(kw in msg_lower for kw in ['stop', 'kill', 'died']):
                return EventType.PROCESS_END, 'process'
        
        # Network events
        if any(kw in tag_lower for kw in ['network', 'wifi', 'connectivity']):
            if any(kw in msg_lower for kw in ['connect', 'connected']):
                return EventType.NETWORK_CONNECT, 'network'
            if any(kw in msg_lower for kw in ['disconnect', 'disconnected']):
                return EventType.NETWORK_DISCONNECT, 'network'
        
        return EventType.OTHER, ''
    
    def parse_bluetooth_opp_log(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse Bluetooth OPP (Object Push Profile) transfer log.
        
        These logs show Bluetooth file transfers received by the device.
        """
        events = []
        file_path = Path(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Look for transfer records
                    # Format varies, common patterns:
                    # "Received file: filename.ext from AA:BB:CC:DD:EE:FF"
                    # "Transfer complete: filename.ext (12345 bytes)"
                    
                    if 'receive' in line.lower() or 'transfer' in line.lower():
                        # Extract file name
                        file_match = re.search(r'(?:file[:\s]+)?([^\s]+\.[a-z0-9]+)', line, re.I)
                        file_name = file_match.group(1) if file_match else None
                        
                        # Extract MAC address
                        mac_match = re.search(r'([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})', line, re.I)
                        mac_addr = mac_match.group(1) if mac_match else None
                        
                        # Extract file size
                        size_match = re.search(r'\((\d+)\s*bytes?\)', line, re.I)
                        file_size = int(size_match.group(1)) if size_match else None
                        
                        event = UnifiedEvent(
                            event_id=self._generate_event_id(),
                            timestamp=datetime.now(timezone.utc),  # Would need actual timestamp
                            event_type=EventType.BLUETOOTH_TRANSFER,
                            severity=EventSeverity.MEDIUM,
                            actor_type="device",
                            actor_id=mac_addr,
                            target_type="file",
                            target_name=file_name,
                            source_log=file_path.name,
                            source_device=source_device,
                            description=line,
                            file_size=file_size,
                            raw_data={
                                "line_number": line_num,
                                "raw_line": line,
                                "mac_address": mac_addr,
                                "file_name": file_name,
                            },
                        )
                        events.append(event)
                        
        except Exception as e:
            logger.error(f"Error parsing Bluetooth OPP log {file_path}: {e}")
        
        self.events.extend(events)
        return events


def parse_android_system_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Android system log file."""
    parser = AndroidLogParser(case_id)
    return parser.parse_file(file_path, source_device)


def parse_bluetooth_opp_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Bluetooth OPP transfer log."""
    parser = AndroidLogParser(case_id)
    return parser.parse_bluetooth_opp_log(file_path, source_device)


def parse_mtp_transfers(
    events: List[UnifiedEvent]
) -> List[UnifiedEvent]:
    """Filter MTP (USB) transfer events from a list."""
    return [e for e in events if e.event_type in (EventType.USB_TRANSFER, EventType.USB_CONNECT)]
