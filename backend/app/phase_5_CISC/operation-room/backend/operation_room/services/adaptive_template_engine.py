"""
Adaptive Template Engine — Phase 2.

Scenario-aware template selection and assembly. Maps ScenarioContext
(from scenario_analyzer.py) to the optimal report structure, enforcing
court-admissible section ordering and mandatory sections per case type.
"""

import logging
import copy
from typing import Any, Dict, List, Optional

from operation_room.services.canonical_contracts import (
    SectionContract,
    SectionStatus,
    ConfidenceLevel,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Master catalogue of all possible report sections
SECTION_CATALOGUE: Dict[str, Dict[str, Any]] = {
    "cover_page": {
        "title": "Cover Page",
        "sort_order": 0,
        "mandatory": True,
        "dependencies": [],
        "description": "Case metadata, classification, and report identification.",
    },
    "exec_summary": {
        "title": "Executive Summary",
        "sort_order": 1,
        "mandatory": True,
        "dependencies": [],
        "description": "High-level overview of findings for decision-makers.",
    },
    "case_overview": {
        "title": "Case Overview & Scope",
        "sort_order": 2,
        "mandatory": True,
        "dependencies": [],
        "description": "Investigation scope, systems analysed, and legal authority.",
    },
    "investigation_hypothesis": {
        "title": "Investigation Hypothesis",
        "sort_order": 3,
        "mandatory": False,
        "dependencies": [],
        "description": "Null and alternative hypotheses tested during investigation.",
    },
    "methodology": {
        "title": "Forensic Methodology",
        "sort_order": 4,
        "mandatory": True,
        "dependencies": [],
        "description": "Tools, techniques, and standards applied (ISO 27037, NIST SP 800-86).",
    },
    "timeline": {
        "title": "Event Timeline Analysis",
        "sort_order": 5,
        "mandatory": True,
        "dependencies": [],
        "description": "Chronological reconstruction of events with cluster analysis.",
    },
    "actor_analysis": {
        "title": "Actor Behavioral Analysis",
        "sort_order": 6,
        "mandatory": False,
        "dependencies": ["timeline"],
        "description": "Per-actor activity profiles and behavioral anomalies.",
    },
    "anomalies": {
        "title": "Anomaly Detection Findings",
        "sort_order": 7,
        "mandatory": False,
        "dependencies": ["timeline"],
        "description": "Statistical anomalies with SHAP explanations.",
    },
    "attack_chain": {
        "title": "Attack Chain & Correlation",
        "sort_order": 8,
        "mandatory": False,
        "dependencies": ["timeline", "anomalies"],
        "description": "Entity correlation graph and MITRE ATT&CK mapping.",
    },
    "data_access": {
        "title": "CRUD & Data Access Analysis",
        "sort_order": 9,
        "mandatory": False,
        "dependencies": ["timeline"],
        "description": "File operations, sensitivity classification, and access patterns.",
    },
    "network": {
        "title": "Network & Exfiltration Analysis",
        "sort_order": 10,
        "mandatory": False,
        "dependencies": ["timeline"],
        "description": "Network flows, suspicious destinations, and data volumes.",
    },
    "depth_impact": {
        "title": "Depth & Impact Assessment",
        "sort_order": 11,
        "mandatory": False,
        "dependencies": ["timeline"],
        "description": "Four-axis depth scoring: Account, System, Data, Control.",
    },
    "key_findings": {
        "title": "Key Findings",
        "sort_order": 12,
        "mandatory": True,
        "dependencies": [],
        "description": "Consolidated critical findings with evidence citations.",
    },
    "remediation": {
        "title": "Remediation & Recommendations",
        "sort_order": 13,
        "mandatory": True,
        "dependencies": ["key_findings"],
        "description": "Prioritised containment, short-term, and long-term actions.",
    },
    "legal_compliance": {
        "title": "Legal & Regulatory Compliance",
        "sort_order": 14,
        "mandatory": False,
        "dependencies": [],
        "description": "India IT Act 2000 references, GDPR/HIPAA applicability.",
    },
    "chain_of_custody": {
        "title": "Chain of Custody & Integrity",
        "sort_order": 15,
        "mandatory": True,
        "dependencies": [],
        "description": "Evidence hashes, access logs, and forensic integrity records.",
    },
    "evidence_appendix": {
        "title": "Evidence Appendix",
        "sort_order": 16,
        "mandatory": True,
        "dependencies": [],
        "description": "Full evidence key manifest with SHA-256 hashes.",
    },
    "glossary": {
        "title": "Glossary & Abbreviations",
        "sort_order": 17,
        "mandatory": False,
        "dependencies": [],
        "description": "Technical terms and acronyms used in this report.",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE PRESETS
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_PRESETS: Dict[str, Dict[str, Any]] = {
    "technical": {
        "title": "Technical Incident Report",
        "description": "Full-depth technical forensic report for IR teams.",
        "sections": [
            "cover_page", "exec_summary", "case_overview",
            "investigation_hypothesis", "methodology", "timeline",
            "actor_analysis", "anomalies", "attack_chain",
            "data_access", "network", "depth_impact",
            "key_findings", "remediation", "chain_of_custody",
            "evidence_appendix", "glossary",
        ],
    },
    "executive": {
        "title": "Executive Incident Summary",
        "description": "High-level summary for C-suite and board.",
        "sections": [
            "cover_page", "exec_summary", "case_overview",
            "key_findings", "depth_impact", "remediation",
            "chain_of_custody",
        ],
    },
    "regulatory": {
        "title": "Regulatory Compliance Report",
        "description": "Compliance-focused report for regulators.",
        "sections": [
            "cover_page", "exec_summary", "case_overview",
            "methodology", "timeline", "data_access",
            "depth_impact", "key_findings", "remediation",
            "legal_compliance", "chain_of_custody", "evidence_appendix",
        ],
    },
    "india_court": {
        "title": "Court-Admissible Forensic Report (India)",
        "description": "IT Act 2000 §65B compliant forensic report.",
        "sections": [
            "cover_page", "exec_summary", "case_overview",
            "methodology", "timeline", "actor_analysis",
            "anomalies", "attack_chain", "data_access", "network",
            "depth_impact", "key_findings", "remediation",
            "legal_compliance", "chain_of_custody", "evidence_appendix",
            "glossary",
        ],
    },
    "comprehensive": {
        "title": "Comprehensive Forensic Investigation Report",
        "description": "All sections enabled — 30+ page deep report.",
        "sections": list(SECTION_CATALOGUE.keys()),
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO → TEMPLATE MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

# Maps case types from ScenarioAnalyzer to optimal templates
CASE_TYPE_TEMPLATE_MAP: Dict[str, str] = {
    "data_exfiltration": "technical",
    "ransomware": "technical",
    "fraud": "regulatory",
    "insider_threat": "comprehensive",
    "network_intrusion": "technical",
    "malware": "technical",
    "phishing": "technical",
    "ip_theft": "india_court",
    "compliance": "regulatory",
    "general": "comprehensive",
}

# Additional sections to enable based on scenario signals
SCENARIO_SECTION_OVERRIDES: Dict[str, List[str]] = {
    "data_exfiltration": ["network", "data_access"],
    "ransomware": ["network", "attack_chain"],
    "fraud": ["data_access", "legal_compliance"],
    "insider_threat": ["actor_analysis", "data_access", "anomalies"],
    "network_intrusion": ["network", "attack_chain"],
    "malware": ["attack_chain", "anomalies"],
    "phishing": ["actor_analysis", "attack_chain"],
    "ip_theft": ["data_access", "legal_compliance"],
    "compliance": ["legal_compliance", "data_access"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE TEMPLATE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class AdaptiveTemplateEngine:
    """
    Selects and assembles report templates based on scenario context.
    
    The engine:
    1. Maps CaseType → template preset
    2. Ensures all mandatory sections are present
    3. Adds scenario-specific sections (e.g., network for exfiltration)
    4. Resolves section dependency ordering
    5. Generates SectionContract DTOs for the pipeline
    """

    def __init__(self):
        self._catalogue = SECTION_CATALOGUE
        self._presets = TEMPLATE_PRESETS
        self._case_type_map = CASE_TYPE_TEMPLATE_MAP

    def select_template(
        self,
        case_type: str = "general",
        template_override: Optional[str] = None,
        scenario_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Select the optimal template for the given case type.
        
        Args:
            case_type: CaseType value from ScenarioAnalyzer
            template_override: Explicit template choice (overrides auto-select)
            scenario_context: Full ScenarioContext dict for signal-based overrides
            
        Returns:
            Template key
        """
        if template_override and template_override in self._presets:
            return template_override
        
        return self._case_type_map.get(case_type, "comprehensive")

    def assemble_sections(
        self,
        template_key: str,
        case_type: str = "general",
        available_modules: Optional[List[str]] = None,
        force_sections: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
    ) -> List[SectionContract]:
        """
        Assemble the ordered list of SectionContract DTOs.
        
        Args:
            template_key: Template preset key
            case_type: CaseType for scenario-based overrides
            available_modules: Modules that have run (to skip sections without data)
            force_sections: Additional sections to include
            exclude_sections: Sections to exclude
            
        Returns:
            Ordered list of SectionContract DTOs
        """
        preset = self._presets.get(template_key, self._presets["comprehensive"])
        section_keys = list(preset["sections"])

        # Add scenario-specific overrides
        overrides = SCENARIO_SECTION_OVERRIDES.get(case_type, [])
        for key in overrides:
            if key not in section_keys:
                section_keys.append(key)

        # Add forced sections
        if force_sections:
            for key in force_sections:
                if key not in section_keys and key in self._catalogue:
                    section_keys.append(key)

        # Add mandatory sections that might be missing
        for key, spec in self._catalogue.items():
            if spec.get("mandatory") and key not in section_keys:
                section_keys.append(key)

        # Remove excluded sections (except mandatory ones)
        if exclude_sections:
            section_keys = [
                k for k in section_keys
                if k not in exclude_sections or self._catalogue[k].get("mandatory")
            ]

        # Deduplicate while preserving order
        seen = set()
        unique_keys = []
        for k in section_keys:
            if k not in seen and k in self._catalogue:
                seen.add(k)
                unique_keys.append(k)

        # Resolve dependency ordering
        ordered = self._topological_sort(unique_keys)

        # Build SectionContract DTOs
        contracts = []
        for i, key in enumerate(ordered):
            spec = self._catalogue[key]
            contract = SectionContract(
                section_key=key,
                section_title=spec["title"],
                sort_order=i,
                status=SectionStatus.PENDING,
                dependencies=[d for d in spec.get("dependencies", []) if d in ordered],
            )
            contracts.append(contract)

        logger.info(
            f"[TemplateEngine] Assembled {len(contracts)} sections "
            f"for template '{template_key}' (case_type={case_type})"
        )
        return contracts

    def _topological_sort(self, keys: List[str]) -> List[str]:
        """Sort section keys respecting dependency ordering."""
        key_set = set(keys)
        in_degree = {k: 0 for k in keys}
        adj: Dict[str, List[str]] = {k: [] for k in keys}

        for key in keys:
            deps = self._catalogue.get(key, {}).get("dependencies", [])
            for dep in deps:
                if dep in key_set:
                    adj[dep].append(key)
                    in_degree[key] += 1

        # Kahn's algorithm with sort_order as tiebreaker
        queue = sorted(
            [k for k in keys if in_degree[k] == 0],
            key=lambda k: self._catalogue.get(k, {}).get("sort_order", 99),
        )
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort(key=lambda k: self._catalogue.get(k, {}).get("sort_order", 99))

        # Append any remaining (circular deps fallback)
        for k in keys:
            if k not in result:
                result.append(k)

        return result

    def get_template_info(self, template_key: str) -> Dict[str, Any]:
        """Get metadata about a template."""
        preset = self._presets.get(template_key)
        if not preset:
            return {"error": f"Unknown template: {template_key}"}
        return {
            "key": template_key,
            "title": preset["title"],
            "description": preset.get("description", ""),
            "section_count": len(preset["sections"]),
            "sections": [
                {
                    "key": k,
                    "title": self._catalogue.get(k, {}).get("title", k),
                    "mandatory": self._catalogue.get(k, {}).get("mandatory", False),
                }
                for k in preset["sections"]
            ],
        }

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [
            self.get_template_info(k)
            for k in self._presets
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_engine: Optional[AdaptiveTemplateEngine] = None


def get_template_engine() -> AdaptiveTemplateEngine:
    global _engine
    if _engine is None:
        _engine = AdaptiveTemplateEngine()
    return _engine
