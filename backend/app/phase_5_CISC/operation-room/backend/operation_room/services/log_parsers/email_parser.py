"""
Email Log Parser — Parse email server and client logs.

Supports:
- Microsoft Exchange transport logs
- Outlook OST/PST export logs
- Office 365 audit logs
- Generic IMAP/SMTP logs

Critical for tracking email-based data exfiltration with attachments.
"""

import re
import json
import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
import hashlib

from .unified_parser import (
    UnifiedEvent, EventType, EventSeverity, normalize_timestamp
)

logger = logging.getLogger(__name__)


# Suspicious email indicators
SUSPICIOUS_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'protonmail.com',
    'aol.com', 'icloud.com', 'mail.ru', 'yandex.ru', 'qq.com', '163.com',
}

SENSITIVE_KEYWORDS = {
    'confidential', 'secret', 'restricted', 'internal', 'proprietary',
    'financial', 'salary', 'customer', 'client', 'password', 'credential',
    'source code', 'architecture', 'roadmap', 'strategy', 'contract',
}


class EmailLogParser:
    """
    Parser for email server and client logs.
    
    Extracts email send/receive events, attachment information,
    and recipient details for forensic analysis.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.events: List[UnifiedEvent] = []
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"EML-{self.case_id}-{self._event_counter:05d}"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        source_device: Optional[str] = None
    ) -> List[UnifiedEvent]:
        """
        Parse an email log file.
        
        Auto-detects format based on content and filename.
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []
        
        name_lower = file_path.name.lower()
        
        # Exchange message tracking log
        if 'msgtrk' in name_lower or 'tracking' in name_lower:
            return self._parse_exchange_tracking(file_path, source_device)
        
        # Office 365 audit log
        if 'audit' in name_lower and file_path.suffix == '.json':
            return self._parse_o365_audit(file_path, source_device)
        
        # CSV export (generic)
        if file_path.suffix == '.csv':
            return self._parse_csv_email(file_path, source_device)
        
        # JSON format
        if file_path.suffix == '.json':
            return self._parse_json_email(file_path, source_device)
        
        # Generic text log
        return self._parse_text_email(file_path, source_device)
    
    def _parse_exchange_tracking(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Parse Microsoft Exchange Message Tracking logs.
        
        Format: CSV with headers like:
        date-time,client-ip,client-hostname,server-ip,server-hostname,source-context,
        connector-id,source,event-id,internal-message-id,message-id,network-message-id,
        recipient-address,recipient-status,total-bytes,recipient-count,
        related-recipient-address,reference,message-subject,sender-address,
        return-path,message-info,directionality,tenant-id,original-client-ip,
        original-server-ip,custom-data,transport-traffic-type,log-id,schema-version
        """
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Skip non-email events
                    event_type_raw = row.get('event-id', row.get('EventId', ''))
                    if not event_type_raw:
                        continue
                    
                    # Parse timestamp
                    ts = row.get('date-time', row.get('DateTime', ''))
                    timestamp = normalize_timestamp(ts) if ts else datetime.now(timezone.utc)
                    
                    # Determine event type
                    event_type = self._classify_exchange_event(event_type_raw)
                    
                    # Extract key fields
                    sender = row.get('sender-address', row.get('Sender', ''))
                    recipient = row.get('recipient-address', row.get('Recipients', ''))
                    subject = row.get('message-subject', row.get('Subject', ''))
                    size = int(row.get('total-bytes', row.get('TotalBytes', 0)) or 0)
                    client_ip = row.get('client-ip', row.get('ClientIP', ''))
                    
                    # Check for suspicious activity
                    severity = self._classify_email_severity(sender, recipient, subject, size)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="email",
                        actor_id=sender,
                        actor_name=sender,
                        target_id=recipient,
                        target_name=recipient,
                        source_ip=client_ip,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"Subject: {subject[:100]}..." if len(subject) > 100 else f"Subject: {subject}",
                        file_size=size,
                        raw_data=dict(row),
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing Exchange tracking log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_o365_audit(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """
        Parse Office 365 Unified Audit Log (JSON format).
        
        Contains email send/receive, attachment access, and mailbox operations.
        """
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if content.startswith('['):
                records = json.loads(content)
            else:
                records = [json.loads(line) for line in content.split('\n') if line.strip()]
            
            for record in records:
                # Get operation type
                operation = record.get('Operation', record.get('operation', ''))
                if not operation:
                    continue
                
                # Filter to email-related operations
                email_ops = {
                    'Send', 'SendAs', 'SendOnBehalf', 'MailItemsAccessed',
                    'Create', 'Update', 'SoftDelete', 'HardDelete',
                    'MoveToDeletedItems', 'Forward', 'Reply', 'ReplyAll'
                }
                if operation not in email_ops and 'mail' not in operation.lower():
                    continue
                
                # Parse timestamp
                ts = record.get('CreationTime', record.get('creationTime', ''))
                timestamp = normalize_timestamp(ts) if ts else datetime.now(timezone.utc)
                
                # Determine event type
                event_type = EventType.EMAIL_SEND if operation in ('Send', 'SendAs', 'SendOnBehalf', 'Forward') else EventType.OTHER
                
                # Extract details
                user_id = record.get('UserId', record.get('userId', ''))
                client_ip = record.get('ClientIP', record.get('clientIP', ''))
                
                # Get extended properties for subject/recipients
                subject = ''
                recipients = []
                extended_props = record.get('ExtendedProperties', [])
                if isinstance(extended_props, list):
                    for prop in extended_props:
                        if prop.get('Name') == 'Subject':
                            subject = prop.get('Value', '')
                        elif prop.get('Name') == 'Recipients':
                            recipients = prop.get('Value', '').split(';')
                
                # Get affected items
                affected_items = record.get('AffectedItems', [])
                if affected_items and isinstance(affected_items, list):
                    for item in affected_items:
                        if 'Subject' in item:
                            subject = item['Subject']
                
                # Check for attachments
                has_attachment = any(
                    'attachment' in str(record).lower()
                    or record.get('HasAttachment', False)
                )
                
                severity = self._classify_email_severity(user_id, ';'.join(recipients), subject, 0)
                
                event = UnifiedEvent(
                    event_id=self._generate_event_id(),
                    timestamp=timestamp,
                    event_type=event_type,
                    severity=severity,
                    actor_type="email",
                    actor_id=user_id,
                    actor_name=user_id,
                    target_id=';'.join(recipients) if recipients else None,
                    source_ip=client_ip,
                    source_log=file_path.name,
                    source_device=source_device,
                    description=f"Operation: {operation}, Subject: {subject[:50]}",
                    raw_data=record,
                )
                events.append(event)
                
                # Create separate event for attachments if present
                if has_attachment:
                    attach_event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=EventType.EMAIL_ATTACH,
                        severity=EventSeverity.MEDIUM,
                        actor_type="email",
                        actor_id=user_id,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"Email with attachment - Subject: {subject[:50]}",
                        raw_data={"parent_record": record.get('Id', '')},
                    )
                    events.append(attach_event)
                    
        except Exception as e:
            logger.error(f"Error parsing O365 audit log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_csv_email(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse generic CSV email log."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Normalize field names
                    row_lower = {k.lower(): v for k, v in row.items()}
                    
                    # Extract common fields
                    sender = row_lower.get('sender', row_lower.get('from', row_lower.get('sender_address', '')))
                    recipient = row_lower.get('recipient', row_lower.get('to', row_lower.get('recipients', '')))
                    subject = row_lower.get('subject', row_lower.get('message_subject', ''))
                    
                    # Skip if no email data
                    if not sender and not recipient:
                        continue
                    
                    # Timestamp
                    ts_fields = ['timestamp', 'date', 'datetime', 'sent_date', 'received_date', 'time']
                    timestamp = None
                    for field in ts_fields:
                        if field in row_lower and row_lower[field]:
                            try:
                                timestamp = normalize_timestamp(row_lower[field])
                                break
                            except Exception:
                                continue
                    
                    if not timestamp:
                        timestamp = datetime.now(timezone.utc)
                    
                    # Size
                    size = 0
                    for size_field in ['size', 'total_bytes', 'message_size']:
                        if size_field in row_lower:
                            try:
                                size = int(row_lower[size_field])
                                break
                            except Exception:
                                pass
                    
                    # Attachments
                    attachments = row_lower.get('attachments', row_lower.get('attachment_names', ''))
                    has_attachment = bool(attachments and attachments.strip())
                    
                    # Determine event type
                    direction = row_lower.get('direction', row_lower.get('directionality', 'outbound')).lower()
                    event_type = EventType.EMAIL_SEND if 'out' in direction else EventType.EMAIL_RECEIVE
                    
                    severity = self._classify_email_severity(sender, recipient, subject, size)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=event_type,
                        severity=severity,
                        actor_type="email",
                        actor_id=sender,
                        actor_name=sender,
                        target_id=recipient,
                        target_name=recipient,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=f"Subject: {subject}",
                        file_size=size,
                        raw_data=dict(row),
                    )
                    events.append(event)
                    
                    # Attachment event
                    if has_attachment:
                        attach_event = UnifiedEvent(
                            event_id=self._generate_event_id(),
                            timestamp=timestamp,
                            event_type=EventType.EMAIL_ATTACH,
                            severity=EventSeverity.MEDIUM,
                            actor_type="email",
                            actor_id=sender,
                            target_name=attachments,
                            source_log=file_path.name,
                            source_device=source_device,
                            description=f"Attachment: {attachments}",
                            raw_data={"attachments": attachments},
                        )
                        events.append(attach_event)
                        
        except Exception as e:
            logger.error(f"Error parsing CSV email log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_json_email(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse JSON email log."""
        events = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if content.startswith('['):
                records = json.loads(content)
            else:
                records = [json.loads(line) for line in content.split('\n') if line.strip()]
            
            for record in records:
                # Extract fields
                sender = record.get('sender', record.get('from', record.get('from_address', '')))
                recipient = record.get('recipient', record.get('to', record.get('to_address', '')))
                if isinstance(recipient, list):
                    recipient = ';'.join(recipient)
                subject = record.get('subject', '')
                
                # Timestamp
                ts = record.get('timestamp', record.get('date', record.get('sent_time', '')))
                timestamp = normalize_timestamp(ts) if ts else datetime.now(timezone.utc)
                
                # Size
                size = record.get('size', record.get('bytes', 0))
                
                # Attachments
                attachments = record.get('attachments', [])
                has_attachment = bool(attachments)
                
                severity = self._classify_email_severity(sender, recipient, subject, size)
                
                event = UnifiedEvent(
                    event_id=self._generate_event_id(),
                    timestamp=timestamp,
                    event_type=EventType.EMAIL_SEND,
                    severity=severity,
                    actor_type="email",
                    actor_id=sender,
                    actor_name=sender,
                    target_id=recipient,
                    target_name=recipient,
                    source_log=file_path.name,
                    source_device=source_device,
                    description=f"Subject: {subject}",
                    file_size=size,
                    raw_data=record,
                )
                events.append(event)
                
                # Attachment events
                if isinstance(attachments, list):
                    for attach in attachments:
                        if isinstance(attach, dict):
                            attach_name = attach.get('name', attach.get('filename', ''))
                            attach_size = attach.get('size', 0)
                        else:
                            attach_name = str(attach)
                            attach_size = 0
                        
                        attach_event = UnifiedEvent(
                            event_id=self._generate_event_id(),
                            timestamp=timestamp,
                            event_type=EventType.EMAIL_ATTACH,
                            severity=EventSeverity.MEDIUM,
                            actor_type="email",
                            actor_id=sender,
                            target_name=attach_name,
                            source_log=file_path.name,
                            source_device=source_device,
                            description=f"Attachment: {attach_name}",
                            file_size=attach_size,
                            raw_data={"attachment": attach},
                        )
                        events.append(attach_event)
                        
        except Exception as e:
            logger.error(f"Error parsing JSON email log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _parse_text_email(
        self,
        file_path: Path,
        source_device: Optional[str]
    ) -> List[UnifiedEvent]:
        """Parse generic text email log."""
        events = []
        
        # Common patterns
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Find email addresses
                    emails = re.findall(email_pattern, line)
                    if len(emails) < 2:
                        continue
                    
                    sender = emails[0]
                    recipient = emails[1]
                    
                    # Try to extract timestamp
                    timestamp = datetime.now(timezone.utc)
                    ts_patterns = [
                        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})',
                        r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',
                    ]
                    for pattern in ts_patterns:
                        match = re.search(pattern, line)
                        if match:
                            try:
                                timestamp = normalize_timestamp(match.group(1))
                                break
                            except Exception:
                                pass
                    
                    severity = self._classify_email_severity(sender, recipient, line, 0)
                    
                    event = UnifiedEvent(
                        event_id=self._generate_event_id(),
                        timestamp=timestamp,
                        event_type=EventType.EMAIL_SEND,
                        severity=severity,
                        actor_type="email",
                        actor_id=sender,
                        target_id=recipient,
                        source_log=file_path.name,
                        source_device=source_device,
                        description=line[:200],
                        raw_data={"line_number": line_num, "raw_line": line},
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Error parsing text email log {file_path}: {e}")
        
        self.events.extend(events)
        return events
    
    def _classify_exchange_event(self, event_id: str) -> EventType:
        """Classify Exchange event type."""
        event_mapping = {
            'SEND': EventType.EMAIL_SEND,
            'SENDAS': EventType.EMAIL_SEND,
            'SENDONBEHALF': EventType.EMAIL_SEND,
            'RECEIVE': EventType.EMAIL_RECEIVE,
            'DELIVER': EventType.EMAIL_RECEIVE,
            'SUBMIT': EventType.EMAIL_SEND,
            'TRANSFER': EventType.EMAIL_SEND,
            'FORWARD': EventType.EMAIL_SEND,
        }
        return event_mapping.get(event_id.upper(), EventType.OTHER)
    
    def _classify_email_severity(
        self,
        sender: str,
        recipient: str,
        subject: str,
        size: int
    ) -> EventSeverity:
        """Classify email event severity based on content analysis."""
        severity = EventSeverity.LOW
        
        # Check for personal email domains in recipient
        recipient_lower = recipient.lower()
        for domain in SUSPICIOUS_DOMAINS:
            if domain in recipient_lower:
                severity = EventSeverity.MEDIUM
                break
        
        # Check subject for sensitive keywords
        subject_lower = subject.lower()
        for keyword in SENSITIVE_KEYWORDS:
            if keyword in subject_lower:
                severity = EventSeverity.HIGH
                break
        
        # Large attachments
        if size > 10_000_000:  # 10MB
            severity = EventSeverity.HIGH
        elif size > 5_000_000:  # 5MB
            if severity == EventSeverity.LOW:
                severity = EventSeverity.MEDIUM
        
        # External sender sending to external recipient (forwarding)
        sender_domain = sender.split('@')[-1].lower() if '@' in sender else ''
        recipient_domain = recipient.split('@')[-1].lower() if '@' in recipient else ''
        
        if (sender_domain in SUSPICIOUS_DOMAINS and 
            recipient_domain in SUSPICIOUS_DOMAINS and
            sender_domain != recipient_domain):
            severity = EventSeverity.HIGH
        
        return severity


def parse_exchange_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Microsoft Exchange message tracking log."""
    parser = EmailLogParser(case_id)
    return parser.parse_file(file_path, source_device)


def parse_outlook_log(
    file_path: Union[str, Path],
    case_id: str,
    source_device: Optional[str] = None
) -> List[UnifiedEvent]:
    """Parse Outlook export log."""
    parser = EmailLogParser(case_id)
    return parser.parse_file(file_path, source_device)
