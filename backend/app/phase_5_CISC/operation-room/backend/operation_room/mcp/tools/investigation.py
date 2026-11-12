"""
Investigation Control Tools — Core investigation lifecycle management.

This module provides the primary tools for starting and managing investigations:
- investigation.start: Initialize investigation from scenario
- investigation.context: Get/update investigation context
- investigation.sources: List and select data sources

These tools handle:
- Scenario parsing and entity extraction
- Data source discovery
- Investigation mode selection
- Context initialization

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from ..schemas import (
    InvestigationContext,
    InvestigationStatus,
    InvestigationObjective,
    EntityReference,
    TimeRange,
    TraversalStrategy,
    ClarificationQuestion,
    ClarificationPriority,
    ModuleName,
)
from ..registry import ToolCategory, ToolExecutionContext, get_registry
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    with_evidence_hash,
    audit_trail,
    CoCActionType,
)


def enum_value(obj: Any) -> str:
    """Safely extract value from Enum or return string as-is."""
    if hasattr(obj, 'value'):
        return obj.value
    return str(obj)


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

# IP Address patterns
IP_V4_PATTERN = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
)

IP_V6_PATTERN = re.compile(
    r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b|'
    r'\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b|'
    r'\b(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}\b'
)

# MAC Address pattern
MAC_PATTERN = re.compile(
    r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
)

# Email pattern
EMAIL_PATTERN = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# File path patterns
WINDOWS_PATH_PATTERN = re.compile(
    r'\b[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*\b'
)

UNIX_PATH_PATTERN = re.compile(
    r'\b/(?:[^/\0]+/)*[^/\0]+\b'
)

# Domain pattern
DOMAIN_PATTERN = re.compile(
    r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b'
)

# USB/Device patterns
USB_KEYWORDS = ["usb", "removable", "thumb drive", "flash drive", "external"]
BLUETOOTH_KEYWORDS = ["bluetooth", "bt", "paired device", "wireless"]

# System type keywords
WINDOWS_KEYWORDS = ["windows", "win10", "win11", "workstation", "pc", "computer"]
ANDROID_KEYWORDS = ["android", "mobile", "phone", "smartphone", "tablet"]
IOS_KEYWORDS = ["ios", "iphone", "ipad", "apple"]
LINUX_KEYWORDS = ["linux", "ubuntu", "centos", "debian", "server"]

# Role keywords
SUSPECT_KEYWORDS = ["suspect", "accused", "attacker", "malicious", "perpetrator", "threat actor"]
VICTIM_KEYWORDS = ["victim", "target", "compromised", "affected", "breached"]

# Investigation mode keywords
BRUTE_FORCE_KEYWORDS = ["comprehensive", "full", "complete", "all", "thorough", "brute"]
FOCUSED_KEYWORDS = ["focused", "targeted", "specific", "limited", "narrow"]


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO PARSER
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioParser:
    """
    Parses investigation scenarios to extract entities, systems, and context.
    """
    
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.scenario_lower = scenario.lower()
    
    def extract_entities(self) -> List[EntityReference]:
        """Extract all entities from scenario."""
        entities = []
        
        # Extract IPs
        for ip in IP_V4_PATTERN.findall(self.scenario):
            entities.append(EntityReference(
                entity_type="ip_address",
                entity_value=ip,
                role="unknown"
            ))
        
        for ip in IP_V6_PATTERN.findall(self.scenario):
            entities.append(EntityReference(
                entity_type="ip_address",
                entity_value=ip,
                role="unknown"
            ))
        
        # Extract MACs
        for mac in MAC_PATTERN.findall(self.scenario):
            entities.append(EntityReference(
                entity_type="mac_address",
                entity_value=mac.upper(),
                role="unknown"
            ))
        
        # Extract emails
        for email in EMAIL_PATTERN.findall(self.scenario):
            entities.append(EntityReference(
                entity_type="email",
                entity_value=email.lower(),
                role="unknown"
            ))
        
        # Extract file paths
        for path in WINDOWS_PATH_PATTERN.findall(self.scenario):
            entities.append(EntityReference(
                entity_type="file_path",
                entity_value=path,
                role="unknown"
            ))
        
        for path in UNIX_PATH_PATTERN.findall(self.scenario):
            if not path.startswith("/usr") and len(path) > 5:
                entities.append(EntityReference(
                    entity_type="file_path",
                    entity_value=path,
                    role="unknown"
                ))
        
        # Extract domains
        for domain in DOMAIN_PATTERN.findall(self.scenario):
            if domain not in ["example.com", "test.com"]:
                entities.append(EntityReference(
                    entity_type="domain",
                    entity_value=domain.lower(),
                    role="unknown"
                ))
        
        return entities
    
    def extract_systems(self) -> List[EntityReference]:
        """Extract system references from scenario."""
        systems = []
        
        # Detect Windows systems
        if any(kw in self.scenario_lower for kw in WINDOWS_KEYWORDS):
            systems.append(EntityReference(
                entity_type="system",
                entity_value="Windows Computer",
                role="unknown",
                metadata={"os": "windows", "type": "computer"}
            ))
        
        # Detect Android devices
        if any(kw in self.scenario_lower for kw in ANDROID_KEYWORDS):
            systems.append(EntityReference(
                entity_type="system",
                entity_value="Android Mobile",
                role="unknown",
                metadata={"os": "android", "type": "mobile"}
            ))
        
        # Detect iOS devices
        if any(kw in self.scenario_lower for kw in IOS_KEYWORDS):
            systems.append(EntityReference(
                entity_type="system",
                entity_value="iOS Mobile",
                role="unknown",
                metadata={"os": "ios", "type": "mobile"}
            ))
        
        # Detect Linux systems
        if any(kw in self.scenario_lower for kw in LINUX_KEYWORDS):
            systems.append(EntityReference(
                entity_type="system",
                entity_value="Linux Server",
                role="unknown",
                metadata={"os": "linux", "type": "server"}
            ))
        
        return systems
    
    def detect_channels(self) -> List[str]:
        """Detect transfer/communication channels mentioned."""
        channels = []
        
        if any(kw in self.scenario_lower for kw in USB_KEYWORDS):
            channels.append("USB")
        
        if any(kw in self.scenario_lower for kw in BLUETOOTH_KEYWORDS):
            channels.append("Bluetooth")
        
        if "email" in self.scenario_lower or "mail" in self.scenario_lower:
            channels.append("Email")
        
        if "network" in self.scenario_lower or "lan" in self.scenario_lower:
            channels.append("Network")
        
        if "cloud" in self.scenario_lower or "upload" in self.scenario_lower:
            channels.append("Cloud")
        
        if "ftp" in self.scenario_lower:
            channels.append("FTP")
        
        if "http" in self.scenario_lower or "web" in self.scenario_lower:
            channels.append("HTTP/Web")
        
        return channels
    
    def detect_investigation_mode(self) -> str:
        """Detect investigation mode from keywords."""
        if any(kw in self.scenario_lower for kw in BRUTE_FORCE_KEYWORDS):
            return "brute_force"
        elif any(kw in self.scenario_lower for kw in FOCUSED_KEYWORDS):
            return "focused"
        else:
            return "hybrid"
    
    def detect_objectives(self) -> List[str]:
        """Extract investigation objectives from scenario."""
        objectives = []
        
        # Timeline creation
        if "timeline" in self.scenario_lower:
            objectives.append("Create timeline of events")
        
        # File transfer
        if "transfer" in self.scenario_lower or "copy" in self.scenario_lower:
            objectives.append("Track file transfer activities")
        
        # Data exfiltration
        if "exfil" in self.scenario_lower or "steal" in self.scenario_lower or "confidential" in self.scenario_lower:
            objectives.append("Identify data exfiltration attempts")
        
        # Network analysis
        if "ip address" in self.scenario_lower or "network" in self.scenario_lower:
            objectives.append("Analyze network connections and IP addresses")
        
        # Device connection
        if any(kw in self.scenario_lower for kw in USB_KEYWORDS + BLUETOOTH_KEYWORDS):
            objectives.append("Track device connections (USB/Bluetooth)")
        
        # User activity
        if "user" in self.scenario_lower or "suspect" in self.scenario_lower:
            objectives.append("Analyze user activities")
        
        # Default objective
        if not objectives:
            objectives.append("Conduct comprehensive forensic analysis")
        
        return objectives
    
    def generate_clarification_questions(
        self,
        entities: List[EntityReference],
        systems: List[EntityReference],
        channels: List[str]
    ) -> List[ClarificationQuestion]:
        """Generate clarification questions based on parsed scenario."""
        questions = []
        
        # Time range question
        questions.append(ClarificationQuestion(
            question="What is the time range for this investigation?",
            context="Understanding the time scope helps focus the analysis on relevant events.",
            priority=ClarificationPriority.BLOCKING,
            options=[
                "Last 24 hours",
                "Last 7 days",
                "Last 30 days",
                "Custom range (specify dates)"
            ],
            default_value="Last 7 days"
        ))
        
        # If systems detected, ask about ownership
        if systems:
            for system in systems[:2]:  # Limit to first 2
                questions.append(ClarificationQuestion(
                    question=f"Who owns/controls the {system.entity_value}?",
                    context="Device ownership affects legal handling and data access.",
                    priority=ClarificationPriority.HIGH,
                    options=[
                        "Suspect",
                        "Organization",
                        "Victim",
                        "Unknown"
                    ]
                ))
        
        # If no channels detected, ask
        if not channels:
            questions.append(ClarificationQuestion(
                question="What transfer channels should be investigated?",
                context="Knowing the channels helps prioritize which logs to analyze.",
                priority=ClarificationPriority.HIGH,
                options=[
                    "USB/Removable devices",
                    "Network/Email",
                    "Bluetooth",
                    "All available channels"
                ],
                default_value="All available channels"
            ))
        
        # Suspect identification
        if not any(e.role == "suspect" for e in entities + systems):
            questions.append(ClarificationQuestion(
                question="Is there a known suspect or user of interest?",
                context="Having a specific user helps narrow the investigation focus.",
                priority=ClarificationPriority.MEDIUM,
                options=[
                    "Yes (provide username/ID)",
                    "No specific suspect yet"
                ]
            ))
        
        # Investigation depth
        questions.append(ClarificationQuestion(
            question="What level of investigation depth is required?",
            context="This affects how thorough vs. how fast the investigation will be.",
            priority=ClarificationPriority.MEDIUM,
            options=[
                "Quick triage (highlights only)",
                "Standard investigation",
                "Deep forensic analysis"
            ],
            default_value="Standard investigation"
        ))
        
        return questions
    
    def parse(self) -> Dict[str, Any]:
        """Parse the complete scenario."""
        entities = self.extract_entities()
        systems = self.extract_systems()
        channels = self.detect_channels()
        mode = self.detect_investigation_mode()
        objectives = self.detect_objectives()
        questions = self.generate_clarification_questions(entities, systems, channels)
        
        return {
            "entities": entities,
            "systems": systems,
            "channels": channels,
            "mode": mode,
            "objectives": objectives,
            "clarification_questions": questions,
            "summary": {
                "entity_count": len(entities),
                "system_count": len(systems),
                "channel_count": len(channels),
                "objective_count": len(objectives),
                "question_count": len(questions)
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DATA SOURCE DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

class DataSourceDiscovery:
    """
    Discovers available data sources for a case.
    """
    
    # Known log types and their analysis capabilities
    LOG_TYPE_MAPPING = {
        "windows_event": {
            "display": "Windows Event Logs",
            "modules": [ModuleName.TIMELINE, ModuleName.ANOMALY, ModuleName.CORRELATION],
            "evidence_types": ["login", "process", "service", "audit"]
        },
        "sysmon": {
            "display": "Sysmon Logs",
            "modules": [ModuleName.TIMELINE, ModuleName.ANOMALY, ModuleName.CORRELATION, ModuleName.NETWORK],
            "evidence_types": ["process", "network", "file", "registry"]
        },
        "android": {
            "display": "Android Logs",
            "modules": [ModuleName.TIMELINE, ModuleName.CRUD],
            "evidence_types": ["app_usage", "calls", "messages", "location"]
        },
        "network": {
            "display": "Network Traffic",
            "modules": [ModuleName.NETWORK, ModuleName.CORRELATION],
            "evidence_types": ["flow", "dns", "http", "connection"]
        },
        "usb": {
            "display": "USB Device History",
            "modules": [ModuleName.TIMELINE, ModuleName.CRUD],
            "evidence_types": ["device_connect", "file_transfer"]
        },
        "email": {
            "display": "Email Logs",
            "modules": [ModuleName.TIMELINE, ModuleName.NETWORK],
            "evidence_types": ["sent", "received", "attachment"]
        },
        "file_system": {
            "display": "File System Events",
            "modules": [ModuleName.TIMELINE, ModuleName.CRUD, ModuleName.DEPTH],
            "evidence_types": ["create", "modify", "delete", "access"]
        },
        "bluetooth": {
            "display": "Bluetooth Activity",
            "modules": [ModuleName.TIMELINE, ModuleName.CORRELATION],
            "evidence_types": ["pair", "connect", "transfer"]
        }
    }
    
    @classmethod
    async def discover_sources(cls, case_id: str) -> List[Dict[str, Any]]:
        """
        Discover available data sources for a case.
        
        In production, this would query the case's DuckDB vault.
        For now, returns simulated discovery based on common patterns.
        """
        # TODO: Integrate with actual case database
        # This would query: SELECT DISTINCT source_type FROM unified_timeline
        
        # Simulated discovery
        sources = []
        
        # Check for common source types
        for source_type, info in cls.LOG_TYPE_MAPPING.items():
            sources.append({
                "source_type": source_type,
                "display_name": info["display"],
                "available_modules": [m.value for m in info["modules"]],
                "evidence_types": info["evidence_types"],
                "estimated_records": 0,  # Would come from COUNT(*)
                "time_range": None  # Would come from MIN/MAX timestamp
            })
        
        return sources
    
    @classmethod
    def recommend_sources(
        cls,
        channels: List[str],
        systems: List[EntityReference]
    ) -> List[str]:
        """Recommend sources based on investigation context."""
        recommended = set()
        
        # Map channels to source types
        channel_mapping = {
            "USB": ["usb", "file_system", "windows_event"],
            "Bluetooth": ["bluetooth", "android"],
            "Email": ["email", "network"],
            "Network": ["network", "sysmon"],
            "Cloud": ["network", "file_system"],
            "FTP": ["network"],
            "HTTP/Web": ["network", "sysmon"]
        }
        
        for channel in channels:
            if channel in channel_mapping:
                recommended.update(channel_mapping[channel])
        
        # Map systems to source types
        for system in systems:
            os_type = system.metadata.get("os") if system.metadata else None
            if os_type == "windows":
                recommended.update(["windows_event", "sysmon", "usb", "file_system"])
            elif os_type == "android":
                recommended.update(["android", "bluetooth"])
            elif os_type == "ios":
                recommended.update(["file_system"])
            elif os_type == "linux":
                recommended.update(["file_system", "network"])
        
        return list(recommended)


# ═══════════════════════════════════════════════════════════════════════════════
# INVESTIGATION STATE STORE
# ═══════════════════════════════════════════════════════════════════════════════

class InvestigationStore:
    """
    In-memory store for active investigations.
    
    In production, this would persist to a database.
    """
    
    _investigations: Dict[str, InvestigationContext] = {}
    
    @classmethod
    def save(cls, context: InvestigationContext) -> None:
        """Save investigation context."""
        cls._investigations[context.investigation_id] = context
    
    @classmethod
    def get(cls, investigation_id: str) -> Optional[InvestigationContext]:
        """Get investigation context."""
        return cls._investigations.get(investigation_id)
    
    @classmethod
    def get_by_case(cls, case_id: str) -> Optional[InvestigationContext]:
        """Get investigation by case ID."""
        for inv in cls._investigations.values():
            if inv.case_id == case_id:
                return inv
        return None
    
    @classmethod
    def update(cls, investigation_id: str, **updates) -> Optional[InvestigationContext]:
        """Update investigation context fields."""
        inv = cls.get(investigation_id)
        if inv:
            for key, value in updates.items():
                if hasattr(inv, key):
                    setattr(inv, key, value)
            inv.updated_at = datetime.now(timezone.utc)
            cls.save(inv)
        return inv
    
    @classmethod
    def list_active(cls) -> List[InvestigationContext]:
        """List all active investigations."""
        return [
            inv for inv in cls._investigations.values()
            if inv.status not in [InvestigationStatus.COMPLETED, InvestigationStatus.FAILED]
        ]
    
    @classmethod
    def delete(cls, investigation_id: str) -> bool:
        """Delete an investigation."""
        if investigation_id in cls._investigations:
            del cls._investigations[investigation_id]
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="investigation.start",
    category=ToolCategory.INVESTIGATION,
    description="Start a new investigation from a scenario description. Parses the scenario to extract entities, systems, and generates clarification questions.",
    requires_case_id=True,
    tags={"investigation", "start", "scenario"}
)
@with_coc_logging(action_type=CoCActionType.INVESTIGATION_EVENT)
@audit_trail(operation="INVESTIGATION_START")
async def start_investigation(
    case_id: str,
    scenario: str,
    objectives: Optional[List[str]] = None,
    mode: Optional[str] = None,
    llm_provider: str = "gemini",
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Start a new investigation from a scenario description.
    
    This tool:
    1. Parses the scenario to extract entities (IPs, emails, paths)
    2. Identifies systems (Windows, Android, etc.)
    3. Detects transfer channels (USB, Bluetooth, Email)
    4. Generates clarification questions
    5. Creates the investigation context
    
    Args:
        case_id: Target case ID
        scenario: Natural language description of the investigation
        objectives: Optional explicit objectives (auto-detected if not provided)
        mode: Investigation mode: "brute_force", "focused", or "hybrid"
        llm_provider: LLM provider to use (default: "gemini")
    
    Returns:
        Investigation context with extracted entities and clarification questions
    """
    logger.info(f"Starting investigation for case {case_id}")
    
    # Check if investigation already exists for this case
    existing = InvestigationStore.get_by_case(case_id)
    if existing and existing.status not in [InvestigationStatus.COMPLETED, InvestigationStatus.FAILED]:
        return {
            "success": False,
            "error": f"Active investigation already exists: {existing.investigation_id}",
            "existing_investigation_id": existing.investigation_id
        }
    
    # Parse scenario
    parser = ScenarioParser(scenario)
    parsed = parser.parse()
    
    # Discover available data sources
    available_sources = await DataSourceDiscovery.discover_sources(case_id)
    
    # Recommend sources based on context
    recommended_sources = DataSourceDiscovery.recommend_sources(
        parsed["channels"],
        parsed["systems"]
    )
    
    # Create investigation objectives
    inv_objectives = []
    objective_texts = objectives or parsed["objectives"]
    for i, obj_text in enumerate(objective_texts, 1):
        inv_objectives.append(InvestigationObjective(
            description=obj_text,
            priority=i
        ))
    
    # Create investigation context
    investigation = InvestigationContext(
        case_id=case_id,
        scenario=scenario,
        status=InvestigationStatus.AWAITING_CLARIFICATION,
        objectives=inv_objectives,
        entities=parsed["entities"] + parsed["systems"],
        available_sources=[s["source_type"] for s in available_sources],
        selected_sources=recommended_sources,
        mode=mode or parsed["mode"],
        traversal_strategy=TraversalStrategy.HYBRID,
        clarification_questions=parsed["clarification_questions"],
        llm_provider=llm_provider
    )
    
    # Save to store
    InvestigationStore.save(investigation)
    
    logger.info(f"Investigation {investigation.investigation_id} created with {len(parsed['entities'])} entities")
    
    return {
        "success": True,
        "investigation_id": investigation.investigation_id,
        "status": enum_value(investigation.status),
        "case_id": case_id,
        "parsed_scenario": {
            "entities": [e.model_dump() for e in parsed["entities"]],
            "systems": [s.model_dump() for s in parsed["systems"]],
            "channels": parsed["channels"],
            "detected_mode": parsed["mode"],
            "objectives": parsed["objectives"]
        },
        "data_sources": {
            "available": [s["source_type"] for s in available_sources],
            "recommended": recommended_sources
        },
        "clarification_questions": [q.model_dump() for q in parsed["clarification_questions"]],
        "summary": parsed["summary"],
        "next_action": "Use investigation.clarify to answer questions before proceeding"
    }


@mcp_tool(
    name="investigation.context",
    category=ToolCategory.INVESTIGATION,
    description="Get or update the current investigation context.",
    requires_case_id=False,
    tags={"investigation", "context", "status"}
)
@audit_trail(operation="INVESTIGATION_CONTEXT")
async def get_investigation_context(
    investigation_id: Optional[str] = None,
    case_id: Optional[str] = None,
    updates: Optional[Dict[str, Any]] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get or update investigation context.
    
    Args:
        investigation_id: Investigation ID (preferred)
        case_id: Case ID (fallback lookup)
        updates: Optional fields to update
    
    Returns:
        Current investigation context
    """
    # Find investigation
    inv = None
    if investigation_id:
        inv = InvestigationStore.get(investigation_id)
    elif case_id:
        inv = InvestigationStore.get_by_case(case_id)
    elif _context and _context.investigation_id:
        inv = InvestigationStore.get(_context.investigation_id)
    
    if not inv:
        return {
            "success": False,
            "error": "Investigation not found"
        }
    
    # Apply updates if provided
    if updates:
        for key, value in updates.items():
            if hasattr(inv, key) and key not in ["investigation_id", "case_id", "created_at"]:
                setattr(inv, key, value)
        inv.updated_at = datetime.now(timezone.utc)
        InvestigationStore.save(inv)
    
    # Build response
    return {
        "success": True,
        "investigation": {
            "investigation_id": inv.investigation_id,
            "case_id": inv.case_id,
            "status": enum_value(inv.status),
            "scenario": inv.scenario,
            "objectives": [o.model_dump() for o in inv.objectives],
            "entities": [e.model_dump() for e in inv.entities],
            "mode": inv.mode,
            "traversal_strategy": enum_value(inv.traversal_strategy),
            "available_sources": inv.available_sources,
            "selected_sources": inv.selected_sources,
            "llm_provider": inv.llm_provider,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "updated_at": inv.updated_at.isoformat() if inv.updated_at else None
        },
        "clarification": {
            "pending_questions": len([q for q in inv.clarification_questions if not q.answered]),
            "questions": [q.model_dump() for q in inv.clarification_questions]
        }
    }


@mcp_tool(
    name="investigation.sources",
    category=ToolCategory.INVESTIGATION,
    description="List available data sources and update source selection for investigation.",
    requires_case_id=True,
    tags={"investigation", "sources", "data"}
)
@audit_trail(operation="INVESTIGATION_SOURCES")
async def manage_investigation_sources(
    case_id: str,
    investigation_id: Optional[str] = None,
    action: str = "list",
    sources: Optional[List[str]] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Manage data sources for investigation.
    
    Args:
        case_id: Target case ID
        investigation_id: Investigation ID
        action: "list", "select", or "recommend"
        sources: Sources to select (for action="select")
    
    Returns:
        Available and selected sources
    """
    # Discover sources
    available = await DataSourceDiscovery.discover_sources(case_id)
    
    # Get investigation if exists
    inv = None
    if investigation_id:
        inv = InvestigationStore.get(investigation_id)
    else:
        inv = InvestigationStore.get_by_case(case_id)
    
    if action == "select" and sources and inv:
        # Validate sources
        valid_sources = [s["source_type"] for s in available]
        selected = [s for s in sources if s in valid_sources]
        inv.selected_sources = selected
        InvestigationStore.save(inv)
    
    elif action == "recommend" and inv:
        # Get recommendations
        channels = []  # Would extract from investigation context
        systems = [e for e in inv.entities if e.entity_type == "system"]
        recommended = DataSourceDiscovery.recommend_sources(channels, systems)
        
        return {
            "success": True,
            "recommended_sources": recommended,
            "available_sources": [s["source_type"] for s in available]
        }
    
    return {
        "success": True,
        "available_sources": available,
        "selected_sources": inv.selected_sources if inv else [],
        "investigation_id": inv.investigation_id if inv else None
    }


@mcp_tool(
    name="investigation.list",
    category=ToolCategory.INVESTIGATION,
    description="List all active investigations.",
    requires_case_id=False,
    tags={"investigation", "list"}
)
async def list_investigations(
    status_filter: Optional[str] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    List all investigations.
    
    Args:
        status_filter: Optional status to filter by
    
    Returns:
        List of investigations
    """
    investigations = InvestigationStore.list_active()
    
    if status_filter:
        try:
            status_enum = InvestigationStatus(status_filter)
            investigations = [inv for inv in investigations if inv.status == status_enum]
        except ValueError:
            pass
    
    return {
        "success": True,
        "count": len(investigations),
        "investigations": [
            {
                "investigation_id": inv.investigation_id,
                "case_id": inv.case_id,
                "status": enum_value(inv.status),
                "scenario_preview": inv.scenario[:100] + "..." if len(inv.scenario) > 100 else inv.scenario,
                "entity_count": len(inv.entities),
                "created_at": inv.created_at.isoformat() if inv.created_at else None
            }
            for inv in investigations
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "ScenarioParser",
    "DataSourceDiscovery",
    "InvestigationStore",
    "start_investigation",
    "get_investigation_context",
    "manage_investigation_sources",
    "list_investigations",
]
