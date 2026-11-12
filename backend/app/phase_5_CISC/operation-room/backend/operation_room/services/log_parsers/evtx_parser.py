"""
Windows Event Log Parser — EVTX and EVT format parsing.

Parses Windows Event Log files (.evtx, .evt) and extracts forensically
relevant events for USB, Bluetooth, authentication, file operations, etc.

Supports:
- Security.evtx (authentication, audit events)
- System.evtx (USB devices, system events)
- Microsoft-Windows-Bluetooth%4Operational.evtx
- Custom event logs

Note: For actual EVTX parsing in production, this uses the python-evtx library.
For demo/testing, it can also parse pre-extracted JSON exports.
"""

import re
import hashlib
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from .unified_parser import (
    UnifiedEvent, EventType, EventSeverity, normalize_timestamp
)

logger = logging.getLogger(__name__)


# Windows Event IDs and their meanings
SECURITY_EVENTS = {
    # Logon/Logoff
    4624: ("AUTH_LOGON", EventSeverity.INFO, "An account was successfully logged on"),
    4625: ("AUTH_FAILED", EventSeverity.HIGH, "An account failed to log on"),
    4634: ("AUTH_LOGOFF", EventSeverity.INFO, "An account was logged off"),
    4647: ("AUTH_LOGOFF", EventSeverity.INFO, "User initiated logoff"),
    4648: ("AUTH_LOGON", EventSeverity.MEDIUM, "A logon was attempted using explicit credentials"),
    4672: ("AUTH_PRIVILEGE_ESCALATION", EventSeverity.MEDIUM, "Special privileges assigned to new logon"),
    
    # Object Access (File Auditing)
    4663: ("FILE_READ", EventSeverity.INFO, "An attempt was made to access an object"),
    4656: ("FILE_READ", EventSeverity.INFO, "A handle to an object was requested"),
    4658: ("FILE_READ", EventSeverity.INFO, "The handle to an object was closed"),
    4660: ("FILE_DELETE", EventSeverity.MEDIUM, "An object was deleted"),
    4670: ("FILE_MODIFY", EventSeverity.INFO, "Permissions on an object were changed"),
    
    # Process Events
    4688: ("PROCESS_START", EventSeverity.INFO, "A new process has been created"),
    4689: ("PROCESS_END", EventSeverity.INFO, "A process has exited"),
}

SYSTEM_EVENTS = {
    # System Power
    6005: ("SYSTEM_STARTUP", EventSeverity.INFO, "Event log service was started"),
    6006: ("SYSTEM_SHUTDOWN", EventSeverity.INFO, "Event log service was stopped"),
    6008: ("SYSTEM_CRASH", EventSeverity.HIGH, "Unexpected shutdown"),
    
    # USB Device Events (PnP)
    2003: ("USB_CONNECT", EventSeverity.MEDIUM, "USB device connected"),
    2100: ("USB_DISCONNECT", EventSeverity.INFO, "USB device disconnected"),
    2102: ("USB_DEVICE_INSTALL", EventSeverity.MEDIUM, "USB device driver installed"),
    10000: ("USB_CONNECT", EventSeverity.MEDIUM, "Device connected"),
    10001: ("USB_DISCONNECT", EventSeverity.INFO, "Device disconnected"),
    
    # Service Events
    7045: ("PROCESS_START", EventSeverity.MEDIUM, "A service was installed"),
}

BLUETOOTH_EVENTS = {
    100: ("BLUETOOTH_PAIR", EventSeverity.MEDIUM, "Bluetooth device paired"),
    101: ("BLUETOOTH_CONNECT", EventSeverity.INFO, "Bluetooth device connected"),
    102: ("BLUETOOTH_DISCONNECT", EventSeverity.INFO, "Bluetooth device disconnected"),
    200: ("BLUETOOTH_TRANSFER", EventSeverity.MEDIUM, "Bluetooth file transfer"),
}


class WindowsEventLogParser:
    """
    Parser for Windows Event Log files (EVTX/EVT format).
    
    Can parse:
    1. Actual EVTX files using python-evtx
    2. Pre-extracted XML exports
    3. JSON exports from other tools (e.g., EvtxExport)
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[UnifiedEvent] = []
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"WIN-{self.case_id}-{self._event_counter:05d}"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse a Windows Event Log file.
        
        Args:
            file_path: Path to .evtx, .evt, .xml, or .json file
            source_device: Hostname/identifier of source computer
            
        Returns:
            List of UnifiedEvent objects
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.evtx':
            return self._parse_evtx(file_path, source_device)
        elif suffix == '.xml':
            return self._parse_xml_export(file_path, source_device)
        elif suffix == '.json':
            return self._parse_json_export(file_path, source_device)
        else:
            logger.warning(f"Unknown format: {suffix}")
            return []
    
    def _parse_evtx(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Parse actual EVTX file using python-evtx library.
        
        Falls back to simulated parsing if library not available.
        """
        events = []
        
        try:
            # Try to use python-evtx
            from Evtx.Evtx import Evtx
            from Evtx.Views import evtx_file_xml_view
            
            with Evtx(str(file_path)) as evtx:
                for record in evtx.records():
                    try:
                        xml_str = record.xml()
                        event = self._parse_event_xml(xml_str, file_path.name, source_device)
                        if event:
                            events.append(event)
                    except Exception as e:
                        logger.debug(f"Error parsing record: {e}")
                        continue
            
            logger.info(f"Parsed {len(events)} events from {file_path}")
            
        except ImportError:
            logger.warning("python-evtx not installed, using fallback parsing")
            events = self._fallback_evtx_parse(file_path, source_device)
        
        except Exception as e:
            logger.error(f"Error parsing EVTX {file_path}: {e}")
            events = self._fallback_evtx_parse(file_path, source_device)
        
        self.events.extend(events)
        return events
    
    def _fallback_evtx_parse(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Fallback parser when python-evtx is not available.
        
        Attempts to extract data by scanning for XML-like patterns
        or returns simulated data for demo purposes.
        """
        events = []
        
        # Try to read as binary and extract XML patterns
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            # Look for event XML patterns
            xml_pattern = rb'<Event[^>]*>.*?</Event>'
            matches = re.findall(xml_pattern, content, re.DOTALL)
            
            for match in matches[:1000]:  # Limit to prevent memory issues
                try:
                    xml_str = match.decode('utf-16-le', errors='ignore')
                    if not xml_str.strip():
                        xml_str = match.decode('utf-8', errors='ignore')
                    
                    event = self._parse_event_xml(xml_str, file_path.name, source_device)
                    if event:
                        events.append(event)
                except Exception:
                    continue
            
            if events:
                logger.info(f"Extracted {len(events)} events from {file_path} (fallback)")
                return events
                
        except Exception as e:
            logger.debug(f"Binary extraction failed: {e}")
        
        # If no events extracted, return empty list
        # The demo scenario generator will provide synthetic data
        logger.info(f"No events extracted from {file_path}, use demo generator for sample data")
        return events
    
    def _parse_event_xml(
        self,
        xml_str: str,
        source_log: str,
        source_device: Optional[str]
    ) -> Optional[UnifiedEvent]:
        """
        Parse a single Windows Event from XML.
        
        Expected format:
        <Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">
            <System>
                <Provider Name="..." />
                <EventID>4624</EventID>
                <TimeCreated SystemTime="2024-03-14T10:15:23.456Z" />
                <Computer>DESKTOP-ABC123</Computer>
            </System>
            <EventData>
                <Data Name="SubjectUserSid">S-1-5-18</Data>
                <Data Name="TargetUserName">jsmith</Data>
                ...
            </EventData>
        </Event>
        """
        try:
            # Remove namespace for easier parsing
            xml_str = re.sub(r'\sxmlns[^"]*"[^"]*"', '', xml_str)
            root = ET.fromstring(xml_str)
            
            # Extract System info
            system = root.find('System')
            if system is None:
                return None
            
            # Event ID
            event_id_elem = system.find('EventID')
            if event_id_elem is None:
                return None
            event_id = int(event_id_elem.text or 0)
            
            # Timestamp
            time_elem = system.find('TimeCreated')
            timestamp = datetime.now(timezone.utc)
            if time_elem is not None:
                time_str = time_elem.get('SystemTime', '')
                if time_str:
                    timestamp = normalize_timestamp(time_str)
            
            # Computer name
            computer_elem = system.find('Computer')
            computer = computer_elem.text if computer_elem is not None else source_device
            
            # Provider
            provider_elem = system.find('Provider')
            provider = provider_elem.get('Name', '') if provider_elem is not None else ''
            
            # Extract EventData
            event_data = {}
            event_data_elem = root.find('EventData')
            if event_data_elem is not None:
                for data_elem in event_data_elem.findall('Data'):
                    name = data_elem.get('Name', '')
                    value = data_elem.text or ''
                    if name:
                        event_data[name] = value
            
            # Classify event
            event_info = self._classify_windows_event(event_id, provider, event_data)
            
            return UnifiedEvent(
                event_id=self._generate_event_id(),
                timestamp=timestamp,
                event_type=event_info['type'],
                severity=event_info['severity'],
                actor_type="user",
                actor_id=event_data.get('SubjectUserSid', event_data.get('TargetUserSid')),
                actor_name=event_data.get('SubjectUserName', event_data.get('TargetUserName')),
                actor_domain=event_data.get('SubjectDomainName', event_data.get('TargetDomainName')),
                target_type=event_info.get('target_type', ''),
                target_id=event_data.get('ObjectName', event_data.get('TargetSid')),
                target_name=event_data.get('ObjectType'),
                target_path=event_data.get('ObjectName'),
                source_log=source_log,
                source_device=source_device or computer,
                source_hostname=computer,
                source_ip=event_data.get('IpAddress', event_data.get('SourceNetworkAddress')),
                description=event_info['description'],
                raw_data={
                    "EventID": event_id,
                    "Provider": provider,
                    "EventData": event_data,
                },
            )
            
        except ET.ParseError as e:
            logger.debug(f"XML parse error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None
    
    def _classify_windows_event(
        self,
        event_id: int,
        provider: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify a Windows event based on ID and provider."""
        
        # Check Security events
        if event_id in SECURITY_EVENTS:
            type_str, severity, desc = SECURITY_EVENTS[event_id]
            return {
                'type': EventType(type_str.lower()),
                'severity': severity,
                'description': desc,
                'target_type': 'file' if 'FILE' in type_str else 'user',
            }
        
        # Check System events
        if event_id in SYSTEM_EVENTS:
            type_str, severity, desc = SYSTEM_EVENTS[event_id]
            return {
                'type': EventType(type_str.lower()),
                'severity': severity,
                'description': desc,
                'target_type': 'device' if 'USB' in type_str else 'system',
            }
        
        # Check Bluetooth events
        if 'Bluetooth' in provider or event_id in BLUETOOTH_EVENTS:
            if event_id in BLUETOOTH_EVENTS:
                type_str, severity, desc = BLUETOOTH_EVENTS[event_id]
            else:
                type_str, severity, desc = ("BLUETOOTH_CONNECT", EventSeverity.MEDIUM, "Bluetooth event")
            return {
                'type': EventType(type_str.lower()),
                'severity': severity,
                'description': desc,
                'target_type': 'device',
            }
        
        # Default
        return {
            'type': EventType.OTHER,
            'severity': EventSeverity.INFO,
            'description': f"Windows Event {event_id}",
            'target_type': '',
        }
    
    def _parse_xml_export(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse XML-exported Windows Events."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Handle multi-event exports
            if '<Events>' in content or '<QueryList>' in content:
                # Wrap if needed
                if not content.strip().startswith('<'):
                    content = f'<Events>{content}</Events>'
                
                root = ET.fromstring(content)
                for event_elem in root.findall('.//Event'):
                    xml_str = ET.tostring(event_elem, encoding='unicode')
                    event = self._parse_event_xml(xml_str, file_path.name, source_device)
                    if event:
                        events.append(event)
            else:
                # Single event
                event = self._parse_event_xml(content, file_path.name, source_device)
                if event:
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing XML export {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_json_export(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse JSON-exported Windows Events (e.g., from EvtxExport)."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict) and 'Records' in data:
                records = data['Records']
            else:
                records = [data]
            
            for record in records:
                event = self._json_record_to_event(record, file_path.name, source_device)
                if event:
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing JSON export {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _json_record_to_event(
        self,
        record: Dict[str, Any],
        source_log: str,
        source_device: Optional[str]
    ) -> Optional[UnifiedEvent]:
        """Convert a JSON event record to UnifiedEvent."""
        try:
            # Common field mappings from various JSON formats
            event_id = record.get('EventID', record.get('event_id', record.get('Id', 0)))
            if isinstance(event_id, dict):
                event_id = event_id.get('Value', 0)
            event_id = int(event_id)
            
            # Timestamp
            ts_fields = ['TimeCreated', 'timestamp', '@timestamp', 'SystemTime']
            timestamp = None
            for field in ts_fields:
                if field in record:
                    ts = record[field]
                    if isinstance(ts, dict):
                        ts = ts.get('SystemTime', ts.get('#text', ''))
                    timestamp = normalize_timestamp(ts)
                    break
            
            if not timestamp:
                timestamp = datetime.now(timezone.utc)
            
            # Computer
            computer = record.get('Computer', record.get('MachineName', source_device))
            
            # Provider
            provider = record.get('Provider', record.get('ProviderName', ''))
            if isinstance(provider, dict):
                provider = provider.get('Name', '')
            
            # Event data
            event_data = record.get('EventData', record.get('Properties', {}))
            if isinstance(event_data, list):
                # Convert list to dict
                event_data = {f"Data{i}": v for i, v in enumerate(event_data)}
            
            # Classify
            event_info = self._classify_windows_event(event_id, provider, event_data)
            
            return UnifiedEvent(
                event_id=self._generate_event_id(),
                timestamp=timestamp,
                event_type=event_info['type'],
                severity=event_info['severity'],
                actor_type="user",
                actor_id=event_data.get('SubjectUserSid'),
                actor_name=event_data.get('SubjectUserName', event_data.get('TargetUserName')),
                actor_domain=event_data.get('SubjectDomainName', event_data.get('TargetDomainName')),
                target_type=event_info.get('target_type', ''),
                target_path=event_data.get('ObjectName'),
                source_log=source_log,
                source_device=source_device or computer,
                source_hostname=computer,
                source_ip=event_data.get('IpAddress'),
                description=event_info['description'],
                raw_data=record,
            )
            
        except Exception as e:
            logger.debug(f"Error converting JSON record: {e}")
            return None


def parse_security_events(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Windows Security.evtx log."""
    parser = WindowsEventLogParser(case_id)
    return parser.parse_file(file_path, source_device)


def parse_system_events(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Windows System.evtx log."""
    parser = WindowsEventLogParser(case_id)
    return parser.parse_file(file_path, source_device)


def parse_usb_events(
    events: List[UnifiedEvent]
) -> List[UnifiedEvent]:
    """Filter USB-related events from a list."""
    usb_types = {
        EventType.USB_CONNECT,
        EventType.USB_DISCONNECT,
        EventType.USB_TRANSFER,
        EventType.USB_DEVICE_INSTALL,
    }
    return [e for e in events if e.event_type in usb_types]


def parse_bluetooth_events(
    events: List[UnifiedEvent]
) -> List[UnifiedEvent]:
    """Filter Bluetooth-related events from a list."""
    bt_types = {
        EventType.BLUETOOTH_PAIR,
        EventType.BLUETOOTH_CONNECT,
        EventType.BLUETOOTH_DISCONNECT,
        EventType.BLUETOOTH_TRANSFER,
    }
    return [e for e in events if e.event_type in bt_types]
