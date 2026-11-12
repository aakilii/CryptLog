"""
Network Log Parser — Parse firewall, proxy, and network flow logs.

Supports:
- Windows Firewall logs
- Linux iptables logs
- Proxy server logs (Squid, nginx)
- NetFlow/sFlow data
- SMTP logs (for email transfer tracking)
- Generic syslog format

These logs are critical for tracking data exfiltration via network channels.
"""

import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import ipaddress

from .unified_parser import (
    UnifiedEvent, EventType, EventSeverity, normalize_timestamp
)

logger = logging.getLogger(__name__)


# Common ports for forensic analysis
SUSPICIOUS_PORTS = {
    20: "FTP-DATA",
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    465: "SMTPS",
    587: "SMTP-MSA",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    8080: "HTTP-Proxy",
    8443: "HTTPS-Alt",
}

# Protocols
PROTOCOLS = {
    1: "ICMP",
    6: "TCP",
    17: "UDP",
    47: "GRE",
    50: "ESP",
    51: "AH",
}


class NetworkLogParser:
    """
    Parser for network log files.
    
    Supports multiple formats including Windows Firewall, iptables,
    proxy logs, and generic network flow data.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[UnifiedEvent] = []
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"NET-{self.case_id}-{self._event_counter:05d}"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse a network log file.
        
        Auto-detects format based on content.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        # Try to detect format
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.readline().strip()
                sample = f.readline().strip()
            
            # Windows Firewall log starts with #Version
            if header.startswith('#Version:') or header.startswith('#Fields:'):
                return self._parse_windows_firewall(file_path, source_device)
            
            # iptables usually has kernel marker
            if 'kernel:' in header or 'iptables' in header.lower():
                return self._parse_iptables(file_path, source_device)
            
            # JSON format
            if header.startswith('{') or header.startswith('['):
                return self._parse_json_netflow(file_path, source_device)
            
            # CSV with headers
            if ',' in header and any(kw in header.lower() for kw in ['src', 'dst', 'ip', 'port']):
                return self._parse_csv_network(file_path, source_device)
            
            # Generic syslog
            return self._parse_syslog_network(file_path, source_device)
            
        except Exception as e:
            logger.error(f"Error parsing network log {file_path}: {e}")
            return []
    
    def _parse_windows_firewall(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Parse Windows Firewall log format.
        
        Format:
        #Version: 1.5
        #Fields: date time action protocol src-ip dst-ip src-port dst-port size ...
        2024-03-14 10:15:23 ALLOW TCP 192.168.1.45 198.51.100.25 52341 443 0 - - - - - - -
        """
        events = []
        fields = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    
                    # Parse header
                    if line.startswith('#Fields:'):
                        fields = line.replace('#Fields:', '').strip().split()
                        continue
                    
                    # Skip other comments
                    if line.startswith('#') or not line:
                        continue
                    
                    # Parse data line
                    values = line.split()
                    if len(values) < 8:
                        continue
                    
                    # Map to fields or use positional
                    if fields:
                        data = dict(zip(fields, values))
                    else:
                        data = {
                            'date': values[0],
                            'time': values[1],
                            'action': values[2],
                            'protocol': values[3],
                            'src-ip': values[4],
                            'dst-ip': values[5],
                            'src-port': values[6],
                            'dst-port': values[7],
                        }
                    
                    # Parse timestamp
                    ts_str = f"{data.get('date', '')} {data.get('time', '')}"
                    try:
                        timestamp = normalize_timestamp(ts_str)
                    except Exception:
                        timestamp = datetime.now(timezone.utc)
                    
                    # Determine event type and severity
                    action = data.get('action', 'ALLOW').upper()
                    dst_port = int(data.get('dst-port', 0))
                    
                    event_type = EventType.NETWORK_CONNECT
                    severity = EventSeverity.INFO
                    
                    if action == 'DROP' or action == 'DENY':
                        severity = EventSeverity.MEDIUM
                    
                    # Check for data transfer on suspicious ports
                    if dst_port in (25, 465, 587):  # SMTP
                        event_type = EventType.EMAIL_SEND
                        severity = EventSeverity.MEDIUM
                    elif dst_port in (20, 21):  # FTP
                        event_type = EventType.NETWORK_DATA_TRANSFER
                        severity = EventSeverity.HIGH
                    
                    # Check if external destination
                    dst_ip = data.get('dst-ip', '')
                    if self._is_external_ip(dst_ip):
                        severity = EventSeverity.MEDIUM
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="network",
                        source_ip=data.get('src-ip'),
                        dest_ip=dst_ip,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"{action} {data.get('protocol', 'TCP')} {data.get('src-ip')}:{data.get('src-port')} -> {dst_ip}:{dst_port}",
                        raw_data=data,
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing Windows Firewall log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_iptables(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Parse Linux iptables log format.
        
        Format:
        Mar 14 10:15:23 hostname kernel: [123456.789] IN=eth0 OUT= SRC=192.168.1.100 DST=10.0.0.1 LEN=52 ...
        """
        events = []
        
        # iptables log pattern
        pattern = re.compile(
            r'(?P<timestamp>\w+\s+\d+\s+\d{2}:\d{2}:\d{2})\s+'
            r'(?P<hostname>\S+)\s+'
            r'kernel:\s*\[\s*\d+\.\d+\]\s*'
            r'(?P<chain>\w+)?\s*'
            r'(?:IN=(?P<in>\S*)\s*)?'
            r'(?:OUT=(?P<out>\S*)\s*)?'
            r'(?:SRC=(?P<src>\S+)\s*)?'
            r'(?:DST=(?P<dst>\S+)\s*)?'
            r'(?:LEN=(?P<len>\d+)\s*)?'
            r'(?:.*PROTO=(?P<proto>\S+)\s*)?'
            r'(?:.*SPT=(?P<spt>\d+)\s*)?'
            r'(?:.*DPT=(?P<dpt>\d+)\s*)?',
            re.I
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                year = datetime.now().year
                
                for line in f:
                    match = pattern.search(line)
                    if not match:
                        continue
                    
                    data = match.groupdict()
                    
                    # Parse timestamp (add year)
                    ts_str = f"{year} {data.get('timestamp', '')}"
                    try:
                        timestamp = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S")
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except Exception:
                        timestamp = datetime.now(timezone.utc)
                    
                    # Determine severity
                    chain = data.get('chain', '').upper()
                    dst_port = int(data.get('dpt', 0)) if data.get('dpt') else 0
                    
                    severity = EventSeverity.INFO
                    event_type = EventType.NETWORK_CONNECT
                    
                    if 'DROP' in chain or 'REJECT' in chain:
                        severity = EventSeverity.MEDIUM
                    
                    if dst_port in (25, 465, 587):
                        event_type = EventType.EMAIL_SEND
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="network",
                        source_ip=data.get('src'),
                        dest_ip=data.get('dst'),
                        source_hostname=data.get('hostname'),
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"{data.get('proto', 'TCP')} {data.get('src')}:{data.get('spt')} -> {data.get('dst')}:{data.get('dpt')}",
                        raw_data=data,
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing iptables log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_json_netflow(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse JSON format network flow data."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if content.startswith('['):
                records = json.loads(content)
            else:
                records = [json.loads(line) for line in content.split('\n') if line.strip()]
            
            for record in records:
                # Extract fields (various naming conventions)
                src_ip = record.get('src_ip', record.get('source_ip', record.get('SRC', '')))
                dst_ip = record.get('dst_ip', record.get('dest_ip', record.get('DST', '')))
                src_port = record.get('src_port', record.get('source_port', record.get('SPT', 0)))
                dst_port = record.get('dst_port', record.get('dest_port', record.get('DPT', 0)))
                protocol = record.get('protocol', record.get('proto', 'TCP'))
                bytes_sent = record.get('bytes', record.get('bytes_sent', record.get('in_bytes', 0)))
                
                # Timestamp
                ts = record.get('timestamp', record.get('@timestamp', record.get('time', '')))
                timestamp = normalize_timestamp(ts) if ts else datetime.now(timezone.utc)
                
                # Classify
                event_type = EventType.NETWORK_DATA_TRANSFER if bytes_sent > 0 else EventType.NETWORK_CONNECT
                severity = self._classify_network_severity(dst_ip, dst_port, bytes_sent)
                
                event = UnifiedEvent(
                    event_id=self._generate_event_id(),
                    timestamp=timestamp,
                    event_type=event_type,
                    severity=severity,
                    actor_type="network",
                    source_ip=src_ip,
                    dest_ip=dst_ip,
                    source_log=file_path.name,
                    source_device=source_device,
                    description=f"{protocol} {src_ip}:{src_port} -> {dst_ip}:{dst_port} ({bytes_sent} bytes)",
                    file_size=bytes_sent,
                    raw_data=record,
                )
                events.append(event)
                
        except Exception as e:
            logger.error(f"Error parsing JSON netflow {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_csv_network(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse CSV format network logs."""
        import csv
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Normalize field names
                    row_lower = {k.lower(): v for k, v in row.items()}
                    
                    src_ip = row_lower.get('src_ip', row_lower.get('source', row_lower.get('src', '')))
                    dst_ip = row_lower.get('dst_ip', row_lower.get('destination', row_lower.get('dst', '')))
                    src_port = int(row_lower.get('src_port', row_lower.get('sport', 0)) or 0)
                    dst_port = int(row_lower.get('dst_port', row_lower.get('dport', 0)) or 0)
                    
                    # Timestamp
                    ts = row_lower.get('timestamp', row_lower.get('time', row_lower.get('datetime', '')))
                    timestamp = normalize_timestamp(ts) if ts else datetime.now(timezone.utc)
                    
                    event_type = EventType.NETWORK_CONNECT
                    severity = self._classify_network_severity(dst_ip, dst_port, 0)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="network",
                        source_ip=src_ip,
                        dest_ip=dst_ip,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"{src_ip}:{src_port} -> {dst_ip}:{dst_port}",
                        raw_data=dict(row),
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing CSV network log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_syslog_network(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse generic syslog format with network events."""
        events = []
        
        # IP address pattern
        ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                year = datetime.now().year
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Try to extract timestamp
                    timestamp = datetime.now(timezone.utc)
                    ts_match = re.match(r'^(\w+\s+\d+\s+\d{2}:\d{2}:\d{2})', line)
                    if ts_match:
                        try:
                            timestamp = datetime.strptime(f"{year} {ts_match.group(1)}", "%Y %b %d %H:%M:%S")
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        except Exception:
                            pass
                    
                    # Extract IP addresses
                    ips = re.findall(ip_pattern, line)
                    if len(ips) < 2:
                        continue
                    
                    src_ip, dst_ip = ips[0], ips[1]
                    
                    # Extract ports if present
                    port_match = re.findall(r':(\d+)', line)
                    src_port = int(port_match[0]) if len(port_match) > 0 else 0
                    dst_port = int(port_match[1]) if len(port_match) > 1 else 0
                    
                    severity = self._classify_network_severity(dst_ip, dst_port, 0)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=EventType.NETWORK_CONNECT,
                        severity=severity,
                        actor_type="network",
                        source_ip=src_ip,
                        dest_ip=dst_ip,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=line,
                        raw_data={"raw_line": line},
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing syslog network {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def parse_smtp_log(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse SMTP server logs to track email transfers.
        
        Common formats:
        - Postfix maillog
        - Exchange transport logs
        - sendmail logs
        """
        events = []
        file_path = Path(file_path)
        
        # Postfix pattern
        postfix_pattern = re.compile(
            r'(?P<timestamp>\w+\s+\d+\s+\d{2}:\d{2}:\d{2})\s+'
            r'(?P<hostname>\S+)\s+'
            r'postfix/(?P<component>\w+)\[(?P<pid>\d+)\]:\s+'
            r'(?P<queue_id>[A-F0-9]+):\s*'
            r'(?P<message>.*)',
            re.I
        )
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                year = datetime.now().year
                
                for line in f:
                    match = postfix_pattern.search(line)
                    if not match:
                        continue
                    
                    data = match.groupdict()
                    message = data.get('message', '')
                    
                    # Extract email details
                    from_match = re.search(r'from=<([^>]+)>', message)
                    to_match = re.search(r'to=<([^>]+)>', message)
                    size_match = re.search(r'size=(\d+)', message)
                    status_match = re.search(r'status=(\w+)', message)
                    
                    # Skip non-email events
                    if not from_match and not to_match:
                        continue
                    
                    # Parse timestamp
                    ts_str = f"{year} {data.get('timestamp', '')}"
                    try:
                        timestamp = datetime.strptime(ts_str, "%Y %b %d %H:%M:%S")
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except Exception:
                        timestamp = datetime.now(timezone.utc)
                    
                    # Determine event type
                    event_type = EventType.EMAIL_SEND
                    if 'sent' in message.lower():
                        event_type = EventType.EMAIL_SEND
                    elif 'received' in message.lower():
                        event_type = EventType.EMAIL_RECEIVE
                    
                    severity = EventSeverity.LOW
                    if status_match and status_match.group(1).lower() != 'sent':
                        severity = EventSeverity.MEDIUM
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="email",
                        actor_id=from_match.group(1) if from_match else None,
                        actor_name=from_match.group(1) if from_match else None,
                        target_id=to_match.group(1) if to_match else None,
                        target_name=to_match.group(1) if to_match else None,
                        source_log=file_path.name,
                        source_device=source_device,
                        source_hostname=data.get('hostname'),
                        description=message,
                        file_size=int(size_match.group(1)) if size_match else None,
                        raw_data=data,
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing SMTP log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _is_external_ip(self, ip: str) -> bool:
        """Check if IP address is external (not RFC1918 private)."""
        try:
            addr = ipaddress.ip_address(ip)
            return not addr.is_private and not addr.is_loopback
        except Exception:
            return False
    
    def _classify_network_severity(
        self,
        dst_ip: str,
        dst_port: int,
        bytes_transferred: int
    ) -> EventSeverity:
        """Classify network event severity based on destination and volume."""
        
        # External IP with high data volume
        if self._is_external_ip(dst_ip):
            if bytes_transferred > 10_000_000:  # 10MB
                return EventSeverity.HIGH
            if bytes_transferred > 1_000_000:  # 1MB
                return EventSeverity.MEDIUM
            return EventSeverity.MEDIUM
        
        # Internal but high-risk ports
        if dst_port in (22, 3389, 1433, 3306, 5432):  # SSH, RDP, databases
            return EventSeverity.MEDIUM
        
        # SMTP traffic
        if dst_port in (25, 465, 587):
            return EventSeverity.MEDIUM
        
        return EventSeverity.INFO


def parse_firewall_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse firewall log file."""
    parser = NetworkLogParser(case_id)
    return parser.parse_file(file_path, source_device)


def parse_smtp_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse SMTP mail server log."""
    parser = NetworkLogParser(case_id)
    return parser.parse_smtp_log(file_path, source_device)


def parse_network_flows(
    events: List[UnifiedEvent],
    external_only: bool = False
) -> List[UnifiedEvent]:
    """
    Filter network flow events.
    
    Args:
        events: List of UnifiedEvent
        external_only: If True, only return flows to external IPs
    """
    flow_types = {EventType.NETWORK_CONNECT, EventType.NETWORK_DATA_TRANSFER}
    
    filtered = [e for e in events if e.event_type in flow_types]
    
    if external_only:
        parser = NetworkLogParser("")
        filtered = [e for e in filtered if parser._is_external_ip(e.dest_ip or '')]
    
    return filtered
