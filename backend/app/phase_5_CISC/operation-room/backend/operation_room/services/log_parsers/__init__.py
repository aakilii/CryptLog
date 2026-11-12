"""
Log Parsers Module — Multi-format forensic log parsing for investigation.

This module provides parsers for various log formats commonly encountered
in digital forensics investigations:

- Windows Event Logs (.evtx)
- Android Logs (logcat, system)
- Network Logs (firewall, syslog)
- USB Device Logs
- Email Logs (Exchange, O365)

All parsers normalize events to a unified schema that integrates with
the Evidence Vault and Timeline analysis modules.
"""

from .evtx_parser import (
    WindowsEventLogParser,
    parse_security_events,
    parse_system_events,
    parse_usb_events,
    parse_bluetooth_events,
)

from .android_parser import (
    AndroidLogParser,
    parse_android_system_log,
    parse_bluetooth_opp_log,
    parse_mtp_transfers,
)

from .network_parser import (
    NetworkLogParser,
    parse_firewall_log,
    parse_smtp_log,
    parse_network_flows,
)

from .email_parser import (
    EmailLogParser,
    parse_exchange_log,
    parse_outlook_log,
)

from .unified_parser import (
    UnifiedLogParser,
    UnifiedEvent,
    EventType,
    EventSeverity,
    parse_all_logs,
    normalize_timestamp,
)

__all__ = [
    # Windows
    "WindowsEventLogParser",
    "parse_security_events",
    "parse_system_events",
    "parse_usb_events",
    "parse_bluetooth_events",
    # Android
    "AndroidLogParser",
    "parse_android_system_log",
    "parse_bluetooth_opp_log",
    "parse_mtp_transfers",
    # Network
    "NetworkLogParser",
    "parse_firewall_log",
    "parse_smtp_log",
    "parse_network_flows",
    # Email
    "EmailLogParser",
    "parse_exchange_log",
    "parse_outlook_log",
    # Unified
    "UnifiedLogParser",
    "UnifiedEvent",
    "EventType",
    "EventSeverity",
    "parse_all_logs",
    "normalize_timestamp",
]
