"""
Hypothesis Analysis Agent — LangGraph Pipeline for Scenario Decomposition.

The Hypothesis Analysis Agent is the first specialized agent in the pipeline.
It receives scenario descriptions and decomposes them into:
1. Testable hypotheses with confidence weights
2. Entity extraction (users, systems, IPs, resources)
3. Relationship mapping between entities
4. Attack vector identification
5. Evidence requirements per hypothesis

Pipeline Architecture:
─────────────────────────────────────────────────────────────────────────────────
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                     HYPOTHESIS ANALYSIS PIPELINE                         │
   │                                                                          │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │  PARSE   │──▶│ EXTRACT  │──▶│ GENERATE │──▶│  BUILD   │             │
   │  │ SCENARIO │   │ ENTITIES │   │HYPOTHESES│   │   TREE   │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   │                                                    │                    │
   │                                                    ▼                    │
   │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐             │
   │  │  OUTPUT  │◀──│   RANK   │◀──│   MAP    │◀──│ IDENTIFY │             │
   │  │  SCHEMA  │   │ PRIORITY │   │ EVIDENCE │   │ VECTORS  │             │
   │  └──────────┘   └──────────┘   └──────────┘   └──────────┘             │
   └──────────────────────────────────────────────────────────────────────────┘
─────────────────────────────────────────────────────────────────────────────────

Research Integration (25+ methodologies):
- Cyber Kill Chain (Lockheed Martin)
- MITRE ATT&CK Framework
- Diamond Model of Intrusion Analysis
- OODA Loop (Observe, Orient, Decide, Act)
- Structured Analytic Techniques (SATs)

Author: NFLIP Development Team
Version: 1.0.0
"""

import json
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import TypedDict, Optional, Any, Dict, List, Literal
from dataclasses import dataclass, field
from enum import Enum

from langgraph.graph import StateGraph, END

from operation_room.agents.base import BaseAgent, BaseAgentState, AgentStatus, registry
from operation_room.services.llm_provider import get_llm
from operation_room.services.audit_service import record_coc_event
from operation_room.database import open_vault

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisType(str, Enum):
    """Types of forensic hypotheses."""
    ATTACK_ORIGIN = "attack_origin"
    DATA_EXFILTRATION = "data_exfiltration"
    LATERAL_MOVEMENT = "lateral_movement"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PERSISTENCE = "persistence"
    CREDENTIAL_THEFT = "credential_theft"
    INSIDER_THREAT = "insider_threat"
    MALWARE_INFECTION = "malware_infection"
    RANSOMWARE = "ransomware"
    BUSINESS_EMAIL_COMPROMISE = "bec"
    SUPPLY_CHAIN = "supply_chain"


class ConfidenceLevel(str, Enum):
    """Confidence levels for hypotheses."""
    VERY_HIGH = "very_high"  # 0.9 - 1.0
    HIGH = "high"            # 0.7 - 0.9
    MEDIUM = "medium"        # 0.5 - 0.7
    LOW = "low"              # 0.3 - 0.5
    VERY_LOW = "very_low"    # 0.0 - 0.3


@dataclass
class Entity:
    """
    An entity extracted from the scenario.
    
    Entities are actors, systems, resources, or other objects
    involved in the incident.
    """
    entity_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    entity_type: str = ""  # user, system, ip, resource, file, database, etc.
    name: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_text: str = ""  # Original text where entity was found
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source_text": self.source_text
        }


@dataclass
class Relationship:
    """
    A relationship between two entities.
    """
    source_entity_id: str = ""
    target_entity_id: str = ""
    relationship_type: str = ""  # accessed, connected_to, executed, modified, etc.
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_entity_id": self.source_entity_id,
            "target_entity_id": self.target_entity_id,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "evidence": self.evidence
        }


@dataclass
class Hypothesis:
    """
    A testable hypothesis derived from the scenario.
    """
    hypothesis_id: str = field(default_factory=lambda: f"H{uuid.uuid4().hex[:6].upper()}")
    hypothesis_type: HypothesisType = HypothesisType.ATTACK_ORIGIN
    statement: str = ""
    description: str = ""
    confidence: float = 0.5
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    
    # Evidence mapping
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    
    # Entity links
    involved_entities: List[str] = field(default_factory=list)
    
    # Hierarchy
    parent_hypothesis_id: Optional[str] = None
    child_hypothesis_ids: List[str] = field(default_factory=list)
    
    # Metadata
    mitre_tactics: List[str] = field(default_factory=list)
    kill_chain_phase: Optional[str] = None
    priority: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_type": self.hypothesis_type.value,
            "statement": self.statement,
            "description": self.description,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "required_evidence": self.required_evidence,
            "involved_entities": self.involved_entities,
            "parent_hypothesis_id": self.parent_hypothesis_id,
            "child_hypothesis_ids": self.child_hypothesis_ids,
            "mitre_tactics": self.mitre_tactics,
            "kill_chain_phase": self.kill_chain_phase,
            "priority": self.priority
        }


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS STATE SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisState(TypedDict, total=False):
    """State schema for the hypothesis analysis pipeline."""
    # Input
    case_id: str
    run_id: str
    scenario: str
    context: Dict[str, Any]
    llm_provider: str
    
    # Extraction results
    parsed_scenario: Dict[str, Any]
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    
    # Hypothesis generation
    hypotheses: List[Dict[str, Any]]
    hypothesis_tree: Dict[str, Any]
    
    # Attack analysis
    attack_vectors: List[Dict[str, Any]]
    kill_chain_mapping: Dict[str, List[str]]
    mitre_mapping: Dict[str, List[str]]
    
    # Evidence requirements
    evidence_requirements: List[Dict[str, Any]]
    
    # Priority ranking
    ranked_hypotheses: List[Dict[str, Any]]
    
    # Output
    output: Dict[str, Any]
    
    # Metadata
    status: str
    hash_value: str
    coc_event_id: str
    error: Optional[str]
    reasoning_steps: List[Dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH-BACKED PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

SCENARIO_PARSE_PROMPT = """You are a senior forensic analyst. Parse the following incident scenario and extract structured information.

SCENARIO:
{scenario}

ANALYSIS FRAMEWORKS TO APPLY:
1. **Cyber Kill Chain** (Lockheed Martin): Identify which phases are described
   - Reconnaissance, Weaponization, Delivery, Exploitation, Installation, C2, Actions on Objectives
2. **Diamond Model**: Extract Adversary, Capability, Infrastructure, Victim relationships
3. **5W1H Analysis**: Who, What, When, Where, Why, How

OUTPUT (JSON):
{{
    "incident_type": "ransomware|data_breach|insider_threat|apt|bec|other",
    "severity_estimate": "critical|high|medium|low",
    "time_indicators": ["list of temporal references"],
    "location_indicators": ["list of systems/networks mentioned"],
    "kill_chain_phases": ["phases identified"],
    "diamond_model": {{
        "adversary": "description",
        "capability": "description", 
        "infrastructure": "description",
        "victim": "description"
    }},
    "key_assertions": ["list of factual claims in the scenario"],
    "ambiguities": ["unclear or unspecified aspects"]
}}"""

ENTITY_EXTRACTION_PROMPT = """Extract all entities from this forensic scenario. Be exhaustive.

SCENARIO:
{scenario}

PARSED CONTEXT:
{parsed_context}

ENTITY TYPES TO IDENTIFY:
- **Users/Actors**: usernames, email addresses, employee IDs, threat actors
- **Systems**: hostnames, servers, workstations, cloud instances
- **Network**: IP addresses, domains, URLs, ports, protocols
- **Data/Resources**: files, databases, tables, S3 buckets, shares
- **Applications**: software, services, processes
- **Credentials**: accounts mentioned, auth methods

OUTPUT (JSON):
{{
    "entities": [
        {{
            "entity_type": "user|system|ip|domain|file|database|application|credential",
            "name": "identifier",
            "attributes": {{"key": "value"}},
            "confidence": 0.0-1.0,
            "source_text": "original text mentioning this entity"
        }}
    ],
    "relationships": [
        {{
            "source": "entity_name",
            "target": "entity_name",
            "relationship": "accessed|connected|executed|modified|owns|authenticated_as",
            "confidence": 0.0-1.0
        }}
    ]
}}"""

HYPOTHESIS_GENERATION_PROMPT = """Generate testable forensic hypotheses based on the scenario and extracted entities.

SCENARIO:
{scenario}

ENTITIES:
{entities}

RELATIONSHIPS:
{relationships}

HYPOTHESIS GENERATION RULES (Structured Analytic Techniques):
1. **Analysis of Competing Hypotheses (ACH)**: Generate multiple plausible explanations
2. **Devil's Advocacy**: Include at least one counter-hypothesis
3. **Red Team Analysis**: Consider attacker perspective
4. **Indicators & Warnings**: What would confirm/deny each hypothesis?

For each hypothesis:
- Make it specific and testable
- Identify required evidence
- Link to MITRE ATT&CK tactics
- Estimate initial confidence

OUTPUT (JSON):
{{
    "hypotheses": [
        {{
            "statement": "Specific testable statement",
            "hypothesis_type": "attack_origin|data_exfiltration|lateral_movement|privilege_escalation|persistence|credential_theft|insider_threat|malware|ransomware",
            "description": "Detailed explanation",
            "initial_confidence": 0.0-1.0,
            "required_evidence": ["specific evidence needed"],
            "supporting_indicators": ["what would increase confidence"],
            "contradicting_indicators": ["what would decrease confidence"],
            "involved_entities": ["entity names"],
            "mitre_tactics": ["TA00XX:Name"],
            "kill_chain_phase": "phase name",
            "priority": 1-5
        }}
    ],
    "hypothesis_tree": {{
        "root": "primary hypothesis",
        "branches": [
            {{
                "parent": "primary",
                "child": "sub-hypothesis",
                "relationship": "supports|refines|contradicts"
            }}
        ]
    }}
}}"""

ATTACK_VECTOR_PROMPT = """Analyze the scenario for attack vectors based on the hypotheses generated.

SCENARIO:
{scenario}

HYPOTHESES:
{hypotheses}

ATTACK VECTOR ANALYSIS:
Map to known attack patterns from:
- MITRE ATT&CK Enterprise Matrix
- OWASP Top 10
- CWE/CVE patterns

OUTPUT (JSON):
{{
    "attack_vectors": [
        {{
            "vector_id": "AV001",
            "name": "attack vector name",
            "description": "how the attack works",
            "entry_point": "initial access method",
            "techniques": ["MITRE technique IDs"],
            "affected_entities": ["entity names"],
            "likelihood": "high|medium|low",
            "impact": "high|medium|low"
        }}
    ],
    "attack_chain": [
        {{
            "step": 1,
            "phase": "kill chain phase",
            "action": "what happened",
            "techniques": ["ATT&CK IDs"],
            "indicators": ["what to look for"]
        }}
    ]
}}"""

EVIDENCE_MAPPING_PROMPT = """Map evidence requirements for each hypothesis to available forensic modules.

HYPOTHESES:
{hypotheses}

AVAILABLE MODULES:
- **timeline**: Event sequence reconstruction, temporal analysis
- **anomaly**: ML-based anomaly detection, SHAP explainability
- **correlation**: Entity correlation, attack chain mapping
- **crud**: Data access patterns, CRUD operation analysis
- **network**: Network flows, exfiltration detection
- **depth**: Blast radius, impact assessment

OUTPUT (JSON):
{{
    "evidence_requirements": [
        {{
            "hypothesis_id": "H001",
            "required_evidence": [
                {{
                    "evidence_type": "description",
                    "primary_module": "module name",
                    "secondary_modules": ["backup modules"],
                    "specific_queries": ["what to search for"],
                    "criticality": "essential|important|nice_to_have"
                }}
            ]
        }}
    ],
    "module_priorities": {{
        "timeline": {{"priority": 1, "reason": "..."}},
        "anomaly": {{"priority": 2, "reason": "..."}},
        ...
    }}
}}"""


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE NODES
# ═══════════════════════════════════════════════════════════════════════════════

def parse_scenario(state: HypothesisState) -> dict:
    """
    Node 1: Parse the scenario text using structured analysis.
    """
    run_id = state.get("run_id", str(uuid.uuid4()))
    scenario = state.get("scenario", "")
    
    logger.info(f"[{run_id}] Parsing scenario")
    
    # Basic parsing without LLM
    parsed = {
        "word_count": len(scenario.split()),
        "sentence_count": len(re.split(r'[.!?]+', scenario)),
        "contains_ip": bool(re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', scenario)),
        "contains_timestamp": bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}', scenario)),
        "contains_email": bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', scenario)),
        "key_terms": _extract_key_terms(scenario)
    }
    
    return {
        "run_id": run_id,
        "status": "parsing",
        "parsed_scenario": parsed,
        "reasoning_steps": [{
            "step": "parse_scenario",
            "description": "Initial scenario parsing completed",
            "timestamp": _now_iso(),
            "details": parsed
        }]
    }


def _extract_key_terms(text: str) -> List[str]:
    """Extract security-relevant terms from text."""
    security_terms = {
        "ransomware", "malware", "phishing", "breach", "exfiltration", "lateral",
        "privilege", "escalation", "credential", "password", "authentication",
        "vpn", "firewall", "database", "server", "admin", "root", "sudo",
        "suspicious", "anomaly", "unauthorized", "compromised", "attack"
    }
    
    words = set(text.lower().split())
    return list(words & security_terms)


async def extract_entities(state: HypothesisState) -> dict:
    """
    Node 2: Extract entities using LLM + regex patterns.
    """
    run_id = state["run_id"]
    scenario = state["scenario"]
    parsed = state.get("parsed_scenario", {})
    llm_provider = state.get("llm_provider", "ollama")
    
    logger.info(f"[{run_id}] Extracting entities")
    
    entities = []
    relationships = []
    
    # Pattern-based extraction
    # IPs
    for match in re.finditer(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', scenario):
        entities.append(Entity(
            entity_type="ip",
            name=match.group(1),
            source_text=scenario[max(0, match.start()-20):min(len(scenario), match.end()+20)]
        ).to_dict())
    
    # Emails
    for match in re.finditer(r'\b([\w.-]+@[\w.-]+\.\w+)\b', scenario):
        entities.append(Entity(
            entity_type="user",
            name=match.group(1),
            source_text=scenario[max(0, match.start()-20):min(len(scenario), match.end()+20)]
        ).to_dict())
    
    # Domains
    for match in re.finditer(r'\b([a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b', scenario):
        if not re.match(r'.*@', scenario[max(0, match.start()-1):match.start()]):
            entities.append(Entity(
                entity_type="domain",
                name=match.group(1),
                source_text=scenario[max(0, match.start()-20):min(len(scenario), match.end()+20)]
            ).to_dict())
    
    # LLM-based extraction for more nuanced entities
    try:
        llm = get_llm(provider=llm_provider)
        prompt = ENTITY_EXTRACTION_PROMPT.format(
            scenario=scenario,
            parsed_context=json.dumps(parsed, indent=2)
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a forensic analyst. Extract entities precisely. Output valid JSON only.",
            temperature=0.1
        )
        
        # Parse LLM response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            llm_result = json.loads(json_match.group())
            entities.extend(llm_result.get("entities", []))
            relationships.extend(llm_result.get("relationships", []))
            
    except Exception as e:
        logger.warning(f"[{run_id}] LLM entity extraction failed: {e}")
    
    # Deduplicate entities by name
    seen_names = set()
    unique_entities = []
    for e in entities:
        if e["name"] not in seen_names:
            seen_names.add(e["name"])
            unique_entities.append(e)
    
    return {
        "entities": unique_entities,
        "relationships": relationships,
        "status": "entities_extracted",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "extract_entities",
            "description": f"Extracted {len(unique_entities)} entities and {len(relationships)} relationships",
            "timestamp": _now_iso(),
            "details": {
                "entity_count": len(unique_entities),
                "entity_types": list(set(e["entity_type"] for e in unique_entities)),
                "relationship_count": len(relationships)
            }
        }]
    }


async def generate_hypotheses(state: HypothesisState) -> dict:
    """
    Node 3: Generate testable hypotheses using ACH methodology.
    """
    run_id = state["run_id"]
    scenario = state["scenario"]
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    llm_provider = state.get("llm_provider", "ollama")
    
    logger.info(f"[{run_id}] Generating hypotheses")
    
    hypotheses = []
    hypothesis_tree = {"root": None, "branches": []}
    
    try:
        llm = get_llm(provider=llm_provider)
        prompt = HYPOTHESIS_GENERATION_PROMPT.format(
            scenario=scenario,
            entities=json.dumps(entities, indent=2),
            relationships=json.dumps(relationships, indent=2)
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a senior forensic investigator using Analysis of Competing Hypotheses. Output valid JSON only.",
            temperature=0.3
        )
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            hypotheses = result.get("hypotheses", [])
            hypothesis_tree = result.get("hypothesis_tree", hypothesis_tree)
            
    except Exception as e:
        logger.warning(f"[{run_id}] LLM hypothesis generation failed: {e}")
        
        # Generate default hypotheses based on key terms
        key_terms = state.get("parsed_scenario", {}).get("key_terms", [])
        
        if "ransomware" in key_terms:
            hypotheses.append({
                "hypothesis_id": "H001",
                "statement": "The incident involves ransomware deployment",
                "hypothesis_type": "ransomware",
                "initial_confidence": 0.7,
                "priority": 1
            })
        if "exfiltration" in key_terms or "breach" in key_terms:
            hypotheses.append({
                "hypothesis_id": "H002",
                "statement": "Data exfiltration occurred during the incident",
                "hypothesis_type": "data_exfiltration",
                "initial_confidence": 0.6,
                "priority": 2
            })
        if "lateral" in key_terms:
            hypotheses.append({
                "hypothesis_id": "H003",
                "statement": "Attacker performed lateral movement within the network",
                "hypothesis_type": "lateral_movement",
                "initial_confidence": 0.5,
                "priority": 3
            })
    
    return {
        "hypotheses": hypotheses,
        "hypothesis_tree": hypothesis_tree,
        "status": "hypotheses_generated",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "generate_hypotheses",
            "description": f"Generated {len(hypotheses)} hypotheses",
            "timestamp": _now_iso(),
            "details": {
                "hypothesis_count": len(hypotheses),
                "hypothesis_types": list(set(h.get("hypothesis_type", "unknown") for h in hypotheses))
            }
        }]
    }


async def identify_attack_vectors(state: HypothesisState) -> dict:
    """
    Node 4: Identify attack vectors and map to MITRE ATT&CK.
    """
    run_id = state["run_id"]
    scenario = state["scenario"]
    hypotheses = state.get("hypotheses", [])
    llm_provider = state.get("llm_provider", "ollama")
    
    logger.info(f"[{run_id}] Identifying attack vectors")
    
    attack_vectors = []
    kill_chain_mapping = {}
    mitre_mapping = {}
    
    try:
        llm = get_llm(provider=llm_provider)
        prompt = ATTACK_VECTOR_PROMPT.format(
            scenario=scenario,
            hypotheses=json.dumps(hypotheses, indent=2)
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a threat intelligence analyst. Map attacks to MITRE ATT&CK. Output valid JSON only.",
            temperature=0.2
        )
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            attack_vectors = result.get("attack_vectors", [])
            attack_chain = result.get("attack_chain", [])
            
            # Build mappings
            for step in attack_chain:
                phase = step.get("phase", "unknown")
                if phase not in kill_chain_mapping:
                    kill_chain_mapping[phase] = []
                kill_chain_mapping[phase].append(step.get("action", ""))
                
                for technique in step.get("techniques", []):
                    if technique not in mitre_mapping:
                        mitre_mapping[technique] = []
                    mitre_mapping[technique].append(step.get("action", ""))
                    
    except Exception as e:
        logger.warning(f"[{run_id}] Attack vector analysis failed: {e}")
    
    return {
        "attack_vectors": attack_vectors,
        "kill_chain_mapping": kill_chain_mapping,
        "mitre_mapping": mitre_mapping,
        "status": "vectors_identified",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "identify_attack_vectors",
            "description": f"Identified {len(attack_vectors)} attack vectors",
            "timestamp": _now_iso(),
            "details": {
                "vector_count": len(attack_vectors),
                "kill_chain_phases": list(kill_chain_mapping.keys()),
                "mitre_techniques": list(mitre_mapping.keys())
            }
        }]
    }


async def map_evidence_requirements(state: HypothesisState) -> dict:
    """
    Node 5: Map evidence requirements to forensic modules.
    """
    run_id = state["run_id"]
    hypotheses = state.get("hypotheses", [])
    llm_provider = state.get("llm_provider", "ollama")
    
    logger.info(f"[{run_id}] Mapping evidence requirements")
    
    evidence_requirements = []
    
    try:
        llm = get_llm(provider=llm_provider)
        prompt = EVIDENCE_MAPPING_PROMPT.format(
            hypotheses=json.dumps(hypotheses, indent=2)
        )
        
        response = await llm.generate(
            prompt=prompt,
            system="You are a digital forensics expert. Map evidence to modules. Output valid JSON only.",
            temperature=0.2
        )
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            result = json.loads(json_match.group())
            evidence_requirements = result.get("evidence_requirements", [])
            
    except Exception as e:
        logger.warning(f"[{run_id}] Evidence mapping failed: {e}")
        
        # Default mapping based on hypothesis types
        for h in hypotheses:
            h_type = h.get("hypothesis_type", "")
            requirement = {
                "hypothesis_id": h.get("hypothesis_id", "unknown"),
                "required_evidence": []
            }
            
            if h_type in ["data_exfiltration", "credential_theft"]:
                requirement["required_evidence"].append({
                    "evidence_type": "Data access patterns",
                    "primary_module": "crud",
                    "secondary_modules": ["network"],
                    "criticality": "essential"
                })
            if h_type in ["lateral_movement", "privilege_escalation"]:
                requirement["required_evidence"].append({
                    "evidence_type": "Authentication events",
                    "primary_module": "timeline",
                    "secondary_modules": ["anomaly"],
                    "criticality": "essential"
                })
            
            evidence_requirements.append(requirement)
    
    return {
        "evidence_requirements": evidence_requirements,
        "status": "evidence_mapped",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "map_evidence_requirements",
            "description": f"Mapped evidence for {len(evidence_requirements)} hypotheses",
            "timestamp": _now_iso()
        }]
    }


def rank_hypotheses(state: HypothesisState) -> dict:
    """
    Node 6: Rank hypotheses by priority and testability.
    """
    run_id = state["run_id"]
    hypotheses = state.get("hypotheses", [])
    evidence_requirements = state.get("evidence_requirements", [])
    
    logger.info(f"[{run_id}] Ranking hypotheses")
    
    # Create evidence mapping
    evidence_by_hypothesis = {
        r["hypothesis_id"]: r["required_evidence"]
        for r in evidence_requirements
    }
    
    # Score each hypothesis
    ranked = []
    for h in hypotheses:
        h_id = h.get("hypothesis_id", "")
        
        # Scoring factors
        confidence = h.get("initial_confidence", 0.5)
        priority = h.get("priority", 3)
        evidence_count = len(evidence_by_hypothesis.get(h_id, []))
        
        # Composite score (higher is better)
        score = (confidence * 0.4) + ((6 - priority) / 5 * 0.3) + (min(evidence_count, 5) / 5 * 0.3)
        
        ranked.append({
            **h,
            "rank_score": round(score, 3),
            "evidence_count": evidence_count
        })
    
    # Sort by score descending
    ranked.sort(key=lambda x: x["rank_score"], reverse=True)
    
    # Assign ranks
    for i, h in enumerate(ranked):
        h["rank"] = i + 1
    
    return {
        "ranked_hypotheses": ranked,
        "status": "ranked",
        "reasoning_steps": state.get("reasoning_steps", []) + [{
            "step": "rank_hypotheses",
            "description": f"Ranked {len(ranked)} hypotheses",
            "timestamp": _now_iso(),
            "details": {
                "top_hypothesis": ranked[0] if ranked else None
            }
        }]
    }


def generate_output(state: HypothesisState) -> dict:
    """
    Node 7: Generate final structured output.
    """
    run_id = state["run_id"]
    case_id = state.get("case_id", "")
    
    logger.info(f"[{run_id}] Generating output")
    
    output = {
        "case_id": case_id,
        "run_id": run_id,
        "generated_at": _now_iso(),
        "scenario_analysis": state.get("parsed_scenario", {}),
        "entities": state.get("entities", []),
        "relationships": state.get("relationships", []),
        "hypotheses": state.get("ranked_hypotheses", state.get("hypotheses", [])),
        "hypothesis_tree": state.get("hypothesis_tree", {}),
        "attack_vectors": state.get("attack_vectors", []),
        "kill_chain_mapping": state.get("kill_chain_mapping", {}),
        "mitre_mapping": state.get("mitre_mapping", {}),
        "evidence_requirements": state.get("evidence_requirements", []),
        "reasoning_trace": state.get("reasoning_steps", [])
    }
    
    # Compute hash
    import hashlib
    output_str = json.dumps(output, sort_keys=True)
    hash_value = f"sha256:{hashlib.sha256(output_str.encode()).hexdigest()}"
    
    # Record CoC
    try:
        conn = open_vault(case_id)
        coc_event_id = record_coc_event(
            conn=conn,
            case_id=case_id,
            event_type="HYPOTHESIS_ANALYSIS_COMPLETED",
            actor="hypothesis_analysis_agent",
            description=f"Generated {len(output['hypotheses'])} hypotheses for run {run_id}",
            data_hash=hash_value
        )
    except Exception as e:
        logger.warning(f"[{run_id}] Failed to record CoC: {e}")
        coc_event_id = None
    
    return {
        "output": output,
        "hash_value": hash_value,
        "coc_event_id": coc_event_id,
        "status": "completed"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD LANGGRAPH PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def build_hypothesis_graph() -> StateGraph:
    """Build the LangGraph state machine for hypothesis analysis."""
    workflow = StateGraph(HypothesisState)
    
    # Add nodes
    workflow.add_node("parse_scenario", parse_scenario)
    workflow.add_node("extract_entities", extract_entities)
    workflow.add_node("generate_hypotheses", generate_hypotheses)
    workflow.add_node("identify_attack_vectors", identify_attack_vectors)
    workflow.add_node("map_evidence_requirements", map_evidence_requirements)
    workflow.add_node("rank_hypotheses", rank_hypotheses)
    workflow.add_node("generate_output", generate_output)
    
    # Add edges (linear pipeline)
    workflow.set_entry_point("parse_scenario")
    workflow.add_edge("parse_scenario", "extract_entities")
    workflow.add_edge("extract_entities", "generate_hypotheses")
    workflow.add_edge("generate_hypotheses", "identify_attack_vectors")
    workflow.add_edge("identify_attack_vectors", "map_evidence_requirements")
    workflow.add_edge("map_evidence_requirements", "rank_hypotheses")
    workflow.add_edge("rank_hypotheses", "generate_output")
    workflow.add_edge("generate_output", END)
    
    return workflow.compile()


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS ANALYSIS AGENT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisAnalysisAgent(BaseAgent):
    """
    Hypothesis Analysis Agent.
    
    Analyzes scenarios and generates testable forensic hypotheses.
    """
    
    def __init__(self, llm_provider: str = "ollama"):
        super().__init__(llm_provider=llm_provider)
        self._graph = build_hypothesis_graph()
    
    @property
    def agent_id(self) -> str:
        return "hypothesis_analysis_agent"
    
    @property
    def agent_name(self) -> str:
        return "Hypothesis Analysis Agent"
    
    @property
    def agent_description(self) -> str:
        return "Analyzes scenarios and generates testable forensic hypotheses using ACH methodology"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "required": ["scenario"],
            "properties": {
                "case_id": {"type": "string"},
                "scenario": {"type": "string", "description": "Investigation scenario text"},
                "context": {"type": "object", "description": "Additional context"},
                "llm_provider": {"type": "string", "enum": ["ollama", "gemini"]}
            }
        }
    
    async def execute(self, state: BaseAgentState) -> BaseAgentState:
        """Execute the hypothesis analysis pipeline."""
        input_data = state.get("input_data", {})
        
        hypothesis_state: HypothesisState = {
            "case_id": input_data.get("case_id", state.get("case_id", "")),
            "run_id": state.get("run_id", str(uuid.uuid4())),
            "scenario": input_data.get("scenario", ""),
            "context": input_data.get("context", {}),
            "llm_provider": input_data.get("llm_provider", self.llm_provider)
        }
        
        # Run the graph
        result = await self._graph.ainvoke(hypothesis_state)
        
        # Update base state
        state["output_data"] = result.get("output", {})
        
        self._add_reasoning_step(
            state,
            "hypothesis_analysis_complete",
            f"Generated {len(result.get('hypotheses', []))} hypotheses"
        )
        
        return state
    
    async def analyze(
        self,
        scenario: str,
        case_id: str = "",
        context: Dict[str, Any] = None,
        llm_provider: str = None
    ) -> Dict[str, Any]:
        """
        Convenience method to analyze a scenario.
        
        Args:
            scenario: Investigation scenario text
            case_id: Optional case identifier
            context: Additional context
            llm_provider: LLM provider override
            
        Returns:
            Analysis results with hypotheses, entities, and evidence requirements
        """
        state: BaseAgentState = {
            "run_id": str(uuid.uuid4()),
            "case_id": case_id,
            "input_data": {
                "scenario": scenario,
                "case_id": case_id,
                "context": context or {},
                "llm_provider": llm_provider or self.llm_provider
            }
        }
        
        result = await self.run(state)
        return result.get("output_data", {})


# Register with global registry
registry.register(HypothesisAnalysisAgent())
