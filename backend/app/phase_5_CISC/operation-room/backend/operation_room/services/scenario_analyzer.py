"""
Scenario Analysis Engine - Intelligent Report Generation Phase 2.

Analyzes investigator-provided scenario descriptions to:
- Extract structured information (entities, devices, channels, objectives)
- Detect missing information and generate clarification questions
- Determine timeline scope and focus areas
- Match scenario to learned patterns
"""

import logging
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from operation_room.services.llm_service import get_llm
from operation_room.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class CaseType(str, Enum):
    """Standard forensic case types."""
    DATA_EXFILTRATION = "data_exfiltration"
    RANSOMWARE = "ransomware"
    FRAUD = "fraud"
    INSIDER_THREAT = "insider_threat"
    NETWORK_INTRUSION = "network_intrusion"
    MALWARE = "malware"
    PHISHING = "phishing"
    IP_THEFT = "ip_theft"
    COMPLIANCE = "compliance"
    GENERAL = "general"


class DeviceType(str, Enum):
    """Types of devices in investigations."""
    WINDOWS_PC = "windows_pc"
    MAC = "mac"
    LINUX = "linux"
    ANDROID = "android"
    IOS = "ios"
    SERVER = "server"
    NETWORK_DEVICE = "network_device"
    STORAGE = "storage"
    UNKNOWN = "unknown"


class TransferChannel(str, Enum):
    """Data transfer channels."""
    USB = "usb"
    BLUETOOTH = "bluetooth"
    EMAIL = "email"
    CLOUD = "cloud"
    NETWORK_SHARE = "network_share"
    FTP = "ftp"
    HTTP = "http"
    REMOVABLE_MEDIA = "removable_media"
    MESSAGING = "messaging"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """Information about a seized device."""
    device_id: str
    device_type: DeviceType
    description: str
    owner: str  # "suspect", "victim", "organization", "unknown"
    identifier: Optional[str] = None  # hostname, serial, etc.
    os_version: Optional[str] = None
    seized_from: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "description": self.description,
            "owner": self.owner,
            "identifier": self.identifier,
            "os_version": self.os_version,
            "seized_from": self.seized_from
        }


@dataclass
class EntityInfo:
    """Information about an entity (person, organization, IP, etc.)."""
    entity_id: str
    entity_type: str  # "person", "organization", "ip_address", "domain", "file"
    name: str
    role: str  # "suspect", "victim", "witness", "unknown"
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "role": self.role,
            "attributes": self.attributes
        }


@dataclass
class ClarificationQuestion:
    """A question to clarify missing information."""
    question_id: str
    question_text: str
    category: str  # "timeline", "entities", "scope", "files", "network", "methodology"
    priority: int  # 1 = critical, 2 = important, 3 = optional
    options: List[str] = field(default_factory=list)
    default_option: Optional[str] = None
    answered: bool = False
    answer: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "category": self.category,
            "priority": self.priority,
            "options": self.options,
            "default_option": self.default_option,
            "answered": self.answered,
            "answer": self.answer
        }


@dataclass
class ScenarioContext:
    """Structured context extracted from scenario."""
    scenario_id: str
    raw_scenario: str
    case_type: CaseType
    confidence: float  # Confidence in case type detection
    case_id: Optional[str] = None  # Associated case ID
    
    # Entities
    suspects: List[EntityInfo] = field(default_factory=list)
    victims: List[EntityInfo] = field(default_factory=list)
    organizations: List[EntityInfo] = field(default_factory=list)
    
    # Devices
    devices: List[DeviceInfo] = field(default_factory=list)
    
    # Transfer information
    transfer_channels: List[TransferChannel] = field(default_factory=list)
    files_of_interest: List[str] = field(default_factory=list)
    
    # Timeline
    timeline_specified: bool = False
    timeline_start: Optional[str] = None
    timeline_end: Optional[str] = None
    use_full_timeline: bool = True
    
    # Objectives
    objectives: List[str] = field(default_factory=list)
    
    # Network
    ip_addresses: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    
    # Clarifications
    clarification_questions: List[ClarificationQuestion] = field(default_factory=list)
    clarification_complete: bool = False
    
    # Metadata
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "raw_scenario": self.raw_scenario,
            "case_type": self.case_type.value,
            "confidence": self.confidence,
            "suspects": [s.to_dict() for s in self.suspects],
            "victims": [v.to_dict() for v in self.victims],
            "organizations": [o.to_dict() for o in self.organizations],
            "devices": [d.to_dict() for d in self.devices],
            "transfer_channels": [c.value for c in self.transfer_channels],
            "files_of_interest": self.files_of_interest,
            "timeline_specified": self.timeline_specified,
            "timeline_start": self.timeline_start,
            "timeline_end": self.timeline_end,
            "use_full_timeline": self.use_full_timeline,
            "objectives": self.objectives,
            "ip_addresses": self.ip_addresses,
            "domains": self.domains,
            "clarification_questions": [q.to_dict() for q in self.clarification_questions],
            "clarification_complete": self.clarification_complete,
            "analyzed_at": self.analyzed_at.isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioAnalyzer:
    """
    Analyzes investigation scenarios using NLP and pattern matching.
    
    Extracts structured information from free-text scenario descriptions
    and generates clarification questions for missing information.
    """
    
    # Keywords for case type detection
    CASE_TYPE_KEYWORDS = {
        CaseType.DATA_EXFILTRATION: [
            "exfiltration", "data theft", "transfer", "leak", "confidential files",
            "unauthorized copy", "steal data", "export data", "usb transfer",
            "email attachment", "cloud upload"
        ],
        CaseType.RANSOMWARE: [
            "ransomware", "encrypted", "ransom", "bitcoin", "decryption key",
            "locked files", "crypto", "extortion"
        ],
        CaseType.FRAUD: [
            "fraud", "embezzlement", "financial", "fake invoice", "wire transfer",
            "accounting irregularities", "misappropriation"
        ],
        CaseType.INSIDER_THREAT: [
            "insider", "employee", "terminated", "disgruntled", "unauthorized access",
            "privilege abuse", "data hoarding"
        ],
        CaseType.NETWORK_INTRUSION: [
            "intrusion", "breach", "unauthorized access", "hacked", "compromised",
            "penetration", "lateral movement", "command and control"
        ],
        CaseType.MALWARE: [
            "malware", "virus", "trojan", "backdoor", "rootkit", "keylogger",
            "spyware", "infected"
        ],
        CaseType.PHISHING: [
            "phishing", "spear phishing", "social engineering", "credential theft",
            "fake email", "impersonation"
        ],
        CaseType.IP_THEFT: [
            "intellectual property", "trade secret", "proprietary", "patent",
            "source code", "design documents"
        ],
        CaseType.COMPLIANCE: [
            "compliance", "gdpr", "hipaa", "pci", "policy violation",
            "regulatory", "audit"
        ]
    }
    
    # Keywords for transfer channel detection
    CHANNEL_KEYWORDS = {
        TransferChannel.USB: ["usb", "thumb drive", "flash drive", "external drive", "removable disk"],
        TransferChannel.BLUETOOTH: ["bluetooth", "bt transfer", "wireless transfer"],
        TransferChannel.EMAIL: ["email", "mail", "outlook", "gmail", "attachment", "sent"],
        TransferChannel.CLOUD: ["cloud", "dropbox", "google drive", "onedrive", "sharepoint", "s3", "aws"],
        TransferChannel.NETWORK_SHARE: ["network share", "smb", "shared folder", "nas", "file server"],
        TransferChannel.FTP: ["ftp", "sftp", "file transfer protocol"],
        TransferChannel.HTTP: ["http", "https", "web upload", "website"],
        TransferChannel.MESSAGING: ["slack", "teams", "whatsapp", "telegram", "discord", "chat"]
    }
    
    # Keywords for device type detection
    DEVICE_KEYWORDS = {
        DeviceType.WINDOWS_PC: ["windows", "pc", "computer", "laptop", "desktop", "workstation"],
        DeviceType.MAC: ["mac", "macbook", "imac", "macos", "apple computer"],
        DeviceType.LINUX: ["linux", "ubuntu", "centos", "debian", "fedora"],
        DeviceType.ANDROID: ["android", "samsung", "pixel", "galaxy", "mobile phone"],
        DeviceType.IOS: ["iphone", "ipad", "ios", "apple phone"],
        DeviceType.SERVER: ["server", "dc", "domain controller", "exchange", "web server"],
        DeviceType.NETWORK_DEVICE: ["router", "firewall", "switch", "proxy"],
        DeviceType.STORAGE: ["nas", "san", "storage array", "backup"]
    }
    
    def __init__(self, use_llm: bool = True):
        """Initialize the analyzer."""
        self.use_llm = use_llm
        self._llm = None
    
    @property
    def llm(self):
        """Lazy load LLM."""
        if self._llm is None and self.use_llm:
            try:
                self._llm = get_llm()
            except Exception as e:
                logger.warning(f"LLM not available: {e}")
        return self._llm
    
    def analyze(self, scenario: str) -> ScenarioContext:
        """
        Analyze a scenario description and extract structured context.
        
        Args:
            scenario: Free-text scenario description
            
        Returns:
            ScenarioContext with extracted information
        """
        scenario_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
        scenario_lower = scenario.lower()
        
        # Detect case type
        case_type, confidence = self._detect_case_type(scenario_lower)
        
        # Create context
        context = ScenarioContext(
            scenario_id=scenario_id,
            raw_scenario=scenario,
            case_type=case_type,
            confidence=confidence
        )
        
        # Extract devices
        context.devices = self._extract_devices(scenario, scenario_lower)
        
        # Extract transfer channels
        context.transfer_channels = self._extract_channels(scenario_lower)
        
        # Extract entities (people, organizations)
        suspects, victims, orgs = self._extract_entities(scenario)
        context.suspects = suspects
        context.victims = victims
        context.organizations = orgs
        
        # Extract IP addresses and domains
        context.ip_addresses = self._extract_ips(scenario)
        context.domains = self._extract_domains(scenario)
        
        # Extract file types of interest
        context.files_of_interest = self._extract_file_types(scenario_lower)
        
        # Check timeline specification
        context.timeline_specified = self._has_timeline(scenario_lower)
        if context.timeline_specified:
            context.timeline_start, context.timeline_end = self._extract_timeline(scenario)
        
        # Extract objectives
        context.objectives = self._extract_objectives(scenario)
        
        # Generate clarification questions
        context.clarification_questions = self._generate_clarifications(context)
        
        logger.info(f"Analyzed scenario {scenario_id}: {case_type.value} (confidence: {confidence:.2f})")
        
        return context
    
    def _detect_case_type(self, scenario_lower: str) -> Tuple[CaseType, float]:
        """Detect case type from scenario keywords."""
        scores = {}
        
        for case_type, keywords in self.CASE_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in scenario_lower)
            if score > 0:
                scores[case_type] = score
        
        if not scores:
            return CaseType.GENERAL, 0.3
        
        # Get highest scoring type
        best_type, max_score = max(scores.items(), key=lambda item: item[1])
        
        # Calculate confidence based on keyword matches
        confidence = min(max_score / 5, 1.0)  # Cap at 1.0
        
        return best_type, confidence
    
    def _extract_devices(self, scenario: str, scenario_lower: str) -> List[DeviceInfo]:
        """Extract device information from scenario."""
        devices = []
        
        for device_type, keywords in self.DEVICE_KEYWORDS.items():
            for kw in keywords:
                if kw in scenario_lower:
                    # Determine owner based on context
                    owner = "unknown"
                    if "suspect" in scenario_lower and kw in scenario_lower:
                        owner = "suspect"
                    elif "organization" in scenario_lower or "company" in scenario_lower:
                        owner = "organization"
                    elif "victim" in scenario_lower:
                        owner = "victim"
                    
                    # Check for ownership keywords
                    if f"suspect's {kw}" in scenario_lower or f"owned by suspect" in scenario_lower:
                        owner = "suspect"
                    if f"organization" in scenario_lower and kw in scenario_lower:
                        owner = "organization"
                    
                    devices.append(DeviceInfo(
                        device_id=f"DEV-{uuid.uuid4().hex[:6].upper()}",
                        device_type=device_type,
                        description=f"Seized {kw}",
                        owner=owner
                    ))
                    break  # One device per type
        
        return devices
    
    def _extract_channels(self, scenario_lower: str) -> List[TransferChannel]:
        """Extract data transfer channels."""
        channels = []
        
        for channel, keywords in self.CHANNEL_KEYWORDS.items():
            if any(kw in scenario_lower for kw in keywords):
                channels.append(channel)
        
        return channels
    
    def _extract_entities(
        self, scenario: str
    ) -> Tuple[List[EntityInfo], List[EntityInfo], List[EntityInfo]]:
        """Extract people and organizations from scenario."""
        suspects = []
        victims = []
        organizations = []
        
        # Simple pattern matching for names (could be enhanced with NLP)
        scenario_lower = scenario.lower()
        
        if "suspect" in scenario_lower:
            suspects.append(EntityInfo(
                entity_id=f"ENT-{uuid.uuid4().hex[:6].upper()}",
                entity_type="person",
                name="Suspect (unidentified)",
                role="suspect"
            ))
        
        # Look for organization mentions
        org_patterns = [
            r"organization(?:'s)?",
            r"company(?:'s)?",
            r"corporation",
            r"employer"
        ]
        
        for pattern in org_patterns:
            if re.search(pattern, scenario_lower):
                organizations.append(EntityInfo(
                    entity_id=f"ENT-{uuid.uuid4().hex[:6].upper()}",
                    entity_type="organization",
                    name="Target Organization",
                    role="victim"
                ))
                break
        
        return suspects, victims, organizations
    
    def _extract_ips(self, scenario: str) -> List[str]:
        """Extract IP addresses from scenario."""
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        return list(set(re.findall(ip_pattern, scenario)))
    
    def _extract_domains(self, scenario: str) -> List[str]:
        """Extract domain names from scenario."""
        domain_pattern = r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b'
        domains = re.findall(domain_pattern, scenario)
        # Filter out common non-domains
        filtered = [d for d in domains if not d.startswith(('www.', 'http'))]
        return list(set(filtered))
    
    def _extract_file_types(self, scenario_lower: str) -> List[str]:
        """Extract file types of interest."""
        file_keywords = {
            "documents": [".docx", ".doc", ".pdf", ".xlsx", ".xls", ".pptx"],
            "images": [".jpg", ".png", ".gif", ".bmp"],
            "archives": [".zip", ".rar", ".7z", ".tar"],
            "code": [".py", ".js", ".java", ".cpp", ".c"],
            "database": [".sql", ".db", ".mdb"],
            "confidential": ["confidential", "secret", "proprietary", "sensitive"]
        }
        
        found = []
        for category, keywords in file_keywords.items():
            if any(kw in scenario_lower for kw in keywords):
                found.append(category)
        
        return found if found else ["all_files"]
    
    def _has_timeline(self, scenario_lower: str) -> bool:
        """Check if scenario specifies a timeline."""
        timeline_indicators = [
            "between", "from", "during", "on date", "time period",
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}"
        ]
        
        for indicator in timeline_indicators:
            if indicator in scenario_lower or re.search(indicator, scenario_lower):
                return True
        
        return False
    
    def _extract_timeline(self, scenario: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract timeline bounds from scenario."""
        # Date patterns
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{2}/\d{2}/\d{4})',
            r'(\w+ \d{1,2},? \d{4})'
        ]
        
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, scenario))
        
        if len(dates) >= 2:
            return dates[0], dates[1]
        elif len(dates) == 1:
            return dates[0], None
        
        return None, None
    
    def _extract_objectives(self, scenario: str) -> List[str]:
        """Extract investigation objectives from scenario."""
        objectives = []
        scenario_lower = scenario.lower()
        
        # Common objective patterns
        objective_keywords = {
            "timeline": ["timeline", "chronological", "sequence of events"],
            "attribution": ["identify", "attribute", "who"],
            "impact": ["impact", "damage", "affected systems"],
            "data_loss": ["what data", "files transferred", "exfiltrated data"],
            "network": ["ip address", "network activity", "connections"],
            "methodology": ["how", "method", "technique", "attack vector"]
        }
        
        for obj_type, keywords in objective_keywords.items():
            if any(kw in scenario_lower for kw in keywords):
                objectives.append(obj_type)
        
        # Add default objectives based on case type
        if not objectives:
            objectives = ["timeline", "attribution", "impact"]
        
        return objectives
    
    def _generate_clarifications(self, context: ScenarioContext) -> List[ClarificationQuestion]:
        """Generate clarification questions for missing information."""
        questions = []
        
        # Timeline clarification
        if not context.timeline_specified:
            questions.append(ClarificationQuestion(
                question_id=f"CLR-{uuid.uuid4().hex[:6].upper()}",
                question_text="The scenario doesn't specify a time range. Should I analyze the entire log timeline or a specific period?",
                category="timeline",
                priority=1,
                options=[
                    "Use full timeline from logs",
                    "Specify a date range",
                    "Last 7 days",
                    "Last 30 days"
                ],
                default_option="Use full timeline from logs"
            ))
        
        # Device clarification if none detected
        if not context.devices:
            questions.append(ClarificationQuestion(
                question_id=f"CLR-{uuid.uuid4().hex[:6].upper()}",
                question_text="No devices were explicitly mentioned. What devices should be analyzed?",
                category="entities",
                priority=1,
                options=[
                    "Windows computers only",
                    "Mobile devices only",
                    "All available devices",
                    "Specify devices"
                ],
                default_option="All available devices"
            ))
        
        # Transfer channel clarification
        if not context.transfer_channels:
            questions.append(ClarificationQuestion(
                question_id=f"CLR-{uuid.uuid4().hex[:6].upper()}",
                question_text="No data transfer methods were specified. Which channels should I focus on?",
                category="scope",
                priority=2,
                options=[
                    "All transfer methods",
                    "USB/External storage only",
                    "Network transfers only",
                    "Email attachments only"
                ],
                default_option="All transfer methods"
            ))
        
        # File type clarification
        if "all_files" in context.files_of_interest:
            questions.append(ClarificationQuestion(
                question_id=f"CLR-{uuid.uuid4().hex[:6].upper()}",
                question_text="What types of files should be considered confidential or of interest?",
                category="files",
                priority=2,
                options=[
                    "All document types (.docx, .xlsx, .pdf)",
                    "Source code and technical files",
                    "All files over 1MB",
                    "Specific file extensions (specify)"
                ],
                default_option="All document types (.docx, .xlsx, .pdf)"
            ))
        
        # Network scope clarification
        if not context.ip_addresses and "network" in " ".join(context.objectives):
            questions.append(ClarificationQuestion(
                question_id=f"CLR-{uuid.uuid4().hex[:6].upper()}",
                question_text="Should I include external IP addresses and domains in the analysis?",
                category="network",
                priority=3,
                options=[
                    "Yes, include all network activity",
                    "Internal network only",
                    "External connections only"
                ],
                default_option="Yes, include all network activity"
            ))
        
        return questions
    
    def answer_clarification(
        self,
        context: ScenarioContext,
        question_id: str,
        answer: str
    ) -> ScenarioContext:
        """
        Record an answer to a clarification question.
        
        Args:
            context: Current scenario context
            question_id: ID of the question
            answer: User's answer
            
        Returns:
            Updated context
        """
        for q in context.clarification_questions:
            if q.question_id == question_id:
                q.answered = True
                q.answer = answer
                break
        
        # Check if all clarifications are complete
        unanswered = [q for q in context.clarification_questions if not q.answered]
        context.clarification_complete = len(unanswered) == 0
        
        # Apply answer to context
        self._apply_clarification_answer(context, question_id, answer)
        
        return context
    
    def _apply_clarification_answer(
        self,
        context: ScenarioContext,
        question_id: str,
        answer: str
    ) -> None:
        """Apply a clarification answer to update context."""
        for q in context.clarification_questions:
            if q.question_id == question_id:
                if q.category == "timeline":
                    if "full timeline" in answer.lower():
                        context.use_full_timeline = True
                    elif "7 days" in answer.lower():
                        context.use_full_timeline = False
                        # Set relative timeline
                    elif "30 days" in answer.lower():
                        context.use_full_timeline = False
                
                elif q.category == "scope" and "transfer" in q.question_text.lower():
                    if "usb" in answer.lower():
                        context.transfer_channels = [TransferChannel.USB, TransferChannel.REMOVABLE_MEDIA]
                    elif "network" in answer.lower():
                        context.transfer_channels = [TransferChannel.NETWORK_SHARE, TransferChannel.HTTP, TransferChannel.FTP]
                    elif "email" in answer.lower():
                        context.transfer_channels = [TransferChannel.EMAIL]
                    elif "all" in answer.lower():
                        context.transfer_channels = list(TransferChannel)
                
                break


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION MANAGEMENT WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioAnalyzerWithSessions:
    """
    Wrapper around ScenarioAnalyzer that manages session state.
    
    Stores analyzed scenarios by session_id for multi-turn interactions
    (clarification questions, re-analysis, etc.)
    """
    
    def __init__(self, use_llm: bool = False):
        self._analyzer = ScenarioAnalyzer(use_llm=use_llm)
        self._sessions: Dict[str, ScenarioContext] = {}
        state_dir = settings.DATA_DIR / "deep_research_state"
        state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = state_dir / "scenario_sessions.json"
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load persisted sessions from disk."""
        if not self._state_file.exists():
            return

        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read scenario session state: %s", exc)
            return

        sessions = payload.get("sessions") if isinstance(payload, dict) else None
        if not isinstance(sessions, list):
            return

        restored: Dict[str, ScenarioContext] = {}
        for raw in sessions:
            if not isinstance(raw, dict):
                continue
            try:
                context = self._context_from_dict(raw)
                restored[context.scenario_id] = context
            except Exception as exc:
                logger.warning("Skipping invalid session entry during restore: %s", exc)

        self._sessions = restored

    def _persist_sessions(self) -> None:
        """Persist sessions to disk."""
        try:
            payload = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "sessions": [ctx.to_dict() for ctx in self._sessions.values()],
            }
            self._state_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to persist scenario sessions: %s", exc)

    def _context_from_dict(self, data: Dict[str, Any]) -> ScenarioContext:
        """Hydrate ScenarioContext from a serialized dictionary."""
        def _entity(entry: Dict[str, Any]) -> EntityInfo:
            attributes_value = entry.get("attributes")
            attributes: Dict[str, Any] = cast(Dict[str, Any], attributes_value) if isinstance(attributes_value, dict) else {}

            return EntityInfo(
                entity_id=str(entry.get("entity_id", "")),
                entity_type=str(entry.get("entity_type", "unknown")),
                name=str(entry.get("name", "Unknown")),
                role=str(entry.get("role", "unknown")),
                attributes=attributes,
            )

        def _device(entry: Dict[str, Any]) -> DeviceInfo:
            raw_type = str(entry.get("device_type", DeviceType.UNKNOWN.value))
            try:
                device_type = DeviceType(raw_type)
            except ValueError:
                device_type = DeviceType.UNKNOWN

            return DeviceInfo(
                device_id=str(entry.get("device_id", "")),
                device_type=device_type,
                description=str(entry.get("description", "")),
                owner=str(entry.get("owner", "unknown")),
                identifier=entry.get("identifier"),
                os_version=entry.get("os_version"),
                seized_from=entry.get("seized_from"),
            )

        def _question(entry: Dict[str, Any]) -> ClarificationQuestion:
            options = entry.get("options")
            return ClarificationQuestion(
                question_id=str(entry.get("question_id", "")),
                question_text=str(entry.get("question_text", "")),
                category=str(entry.get("category", "scope")),
                priority=int(entry.get("priority", 2)),
                options=options if isinstance(options, list) else [],
                default_option=entry.get("default_option"),
                answered=bool(entry.get("answered", False)),
                answer=entry.get("answer"),
            )

        raw_case_type = str(data.get("case_type", CaseType.GENERAL.value))
        try:
            case_type = CaseType(raw_case_type)
        except ValueError:
            case_type = CaseType.GENERAL

        transfer_channels: List[TransferChannel] = []
        for raw_channel in data.get("transfer_channels", []):
            try:
                transfer_channels.append(TransferChannel(str(raw_channel)))
            except ValueError:
                continue

        analyzed_at_raw = data.get("analyzed_at")
        try:
            analyzed_at = datetime.fromisoformat(str(analyzed_at_raw)) if analyzed_at_raw else datetime.now(timezone.utc)
        except Exception:
            analyzed_at = datetime.now(timezone.utc)

        return ScenarioContext(
            scenario_id=str(data.get("scenario_id", "")),
            raw_scenario=str(data.get("raw_scenario", "")),
            case_type=case_type,
            confidence=float(data.get("confidence", 0.0)),
            case_id=data.get("case_id"),
            suspects=[_entity(item) for item in data.get("suspects", []) if isinstance(item, dict)],
            victims=[_entity(item) for item in data.get("victims", []) if isinstance(item, dict)],
            organizations=[_entity(item) for item in data.get("organizations", []) if isinstance(item, dict)],
            devices=[_device(item) for item in data.get("devices", []) if isinstance(item, dict)],
            transfer_channels=transfer_channels,
            files_of_interest=[str(item) for item in data.get("files_of_interest", [])],
            timeline_specified=bool(data.get("timeline_specified", False)),
            timeline_start=data.get("timeline_start"),
            timeline_end=data.get("timeline_end"),
            use_full_timeline=bool(data.get("use_full_timeline", True)),
            objectives=[str(item) for item in data.get("objectives", [])],
            ip_addresses=[str(item) for item in data.get("ip_addresses", [])],
            domains=[str(item) for item in data.get("domains", [])],
            clarification_questions=[
                _question(item)
                for item in data.get("clarification_questions", [])
                if isinstance(item, dict)
            ],
            clarification_complete=bool(data.get("clarification_complete", False)),
            analyzed_at=analyzed_at,
        )
    
    def analyze(
        self,
        scenario_text: str,
        case_id: Optional[str] = None,
        use_llm: Optional[bool] = None,
    ) -> ScenarioContext:
        """
        Analyze a scenario and store the session.
        
        Args:
            scenario_text: The investigation scenario description
            case_id: Optional associated case ID
            
        Returns:
            ScenarioContext with session_id set
        """
        analyzer = self._analyzer
        if use_llm is not None and use_llm != self._analyzer.use_llm:
            analyzer = ScenarioAnalyzer(use_llm=use_llm)

        context = analyzer.analyze(scenario_text)
        
        # Use scenario_id as session_id
        session_id = context.scenario_id
        
        # Store with case_id
        context.case_id = case_id
        self._sessions[session_id] = context
        self._persist_sessions()
        
        return context
    
    def get_session(self, session_id: str) -> Optional[ScenarioContext]:
        """Get a stored session context."""
        return self._sessions.get(session_id)
    
    def answer_clarification(
        self, 
        session_id: str, 
        question_id: str, 
        answer: str
    ) -> Optional[ScenarioContext]:
        """
        Answer a clarification question for a session.
        
        Args:
            session_id: The scenario session ID
            question_id: ID of the question being answered
            answer: User's answer
            
        Returns:
            Updated context or None if session not found
        """
        context = self._sessions.get(session_id)
        if context is None:
            return None
        
        # Use the underlying analyzer to process the answer
        updated = self._analyzer.answer_clarification(context, question_id, answer)
        self._sessions[session_id] = updated
        self._persist_sessions()
        
        return updated
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._persist_sessions()
            return True
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "session_id": ctx.scenario_id,
                "case_id": getattr(ctx, 'case_id', None),
                "case_type": ctx.case_type.value,
                "analyzed_at": ctx.analyzed_at.isoformat(),
                "clarification_complete": ctx.clarification_complete
            }
            for ctx in self._sessions.values()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_scenario_analyzer: Optional[ScenarioAnalyzerWithSessions] = None


def get_scenario_analyzer() -> ScenarioAnalyzerWithSessions:
    """Get the singleton ScenarioAnalyzer instance with session management."""
    global _scenario_analyzer
    if _scenario_analyzer is None:
        _scenario_analyzer = ScenarioAnalyzerWithSessions()
    return _scenario_analyzer
