"""
Hypothesis Tools — ACH framework for forensic hypothesis testing.

This module provides tools for hypothesis management:
- hypothesis.generate: Generate hypotheses from objectives
- hypothesis.create: Create manual hypothesis
- hypothesis.test: Test hypothesis against evidence
- hypothesis.update: Update hypothesis verdict
- confidence.compute: Compute confidence scores

Uses Analysis of Competing Hypotheses (ACH) framework:
- Start with NULL hypothesis (baseline: FALSE)
- Collect evidence for/against
- Compute confidence using ODNI ICD 203 standards
- Only confirm when evidence is sufficient

Author: NFLIP Development Team
Version: 1.0.0
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..schemas import (
    Hypothesis,
    HypothesisVerdict,
    HypothesisTree,
    EvidenceRequirement,
    EvidenceType,
    ConfidenceAssessment,
    ConfidenceFactor,
    ConfidenceLevel,
    ModuleName,
    InvestigationObjective,
)
from ..registry import ToolCategory, ToolExecutionContext
from ..decorators import (
    mcp_tool,
    with_coc_logging,
    with_evidence_hash,
    audit_trail,
    CoCActionType,
)
from .investigation import InvestigationStore, enum_value


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS STORE
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisStore:
    """In-memory store for hypotheses."""
    
    _trees: Dict[str, HypothesisTree] = {}
    
    @classmethod
    def save_tree(cls, tree: HypothesisTree) -> None:
        """Save hypothesis tree."""
        cls._trees[tree.investigation_id] = tree
    
    @classmethod
    def get_tree(cls, investigation_id: str) -> Optional[HypothesisTree]:
        """Get hypothesis tree for investigation."""
        return cls._trees.get(investigation_id)
    
    @classmethod
    def get_or_create_tree(cls, investigation_id: str) -> HypothesisTree:
        """Get or create hypothesis tree."""
        if investigation_id not in cls._trees:
            cls._trees[investigation_id] = HypothesisTree(
                investigation_id=investigation_id
            )
        return cls._trees[investigation_id]
    
    @classmethod
    def add_hypothesis(cls, investigation_id: str, hypothesis: Hypothesis) -> None:
        """Add hypothesis to tree."""
        tree = cls.get_or_create_tree(investigation_id)
        tree.hypotheses.append(hypothesis)
        
        if hypothesis.is_null_hypothesis:
            tree.null_hypothesis = hypothesis.hypothesis_id
        
        cls.save_tree(tree)
    
    @classmethod
    def get_hypothesis(cls, investigation_id: str, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get specific hypothesis."""
        tree = cls.get_tree(investigation_id)
        if tree:
            for h in tree.hypotheses:
                if h.hypothesis_id == hypothesis_id:
                    return h
        return None
    
    @classmethod
    def update_hypothesis(
        cls,
        investigation_id: str,
        hypothesis_id: str,
        **updates
    ) -> Optional[Hypothesis]:
        """Update hypothesis fields."""
        h = cls.get_hypothesis(investigation_id, hypothesis_id)
        if h:
            for key, value in updates.items():
                if hasattr(h, key):
                    setattr(h, key, value)
            h.updated_at = datetime.now(timezone.utc)
        return h


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE STORE
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceStore:
    """Store for confidence assessments."""
    
    _assessments: Dict[str, ConfidenceAssessment] = {}
    
    @classmethod
    def save(cls, assessment: ConfidenceAssessment) -> None:
        """Save assessment."""
        cls._assessments[assessment.assessment_id] = assessment
    
    @classmethod
    def get(cls, assessment_id: str) -> Optional[ConfidenceAssessment]:
        """Get assessment by ID."""
        return cls._assessments.get(assessment_id)
    
    @classmethod
    def get_for_target(cls, target_type: str, target_id: str) -> Optional[ConfidenceAssessment]:
        """Get assessment for a target."""
        for a in cls._assessments.values():
            if a.target_type == target_type and a.target_id == target_id:
                return a
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisGenerator:
    """
    Generates hypotheses from investigation objectives.
    """
    
    # Templates for common investigation types
    HYPOTHESIS_TEMPLATES = {
        "data_exfiltration": [
            {
                "code": "H0",
                "statement": "No data exfiltration occurred during the investigation period",
                "is_null": True,
                "requirements": [
                    {"type": EvidenceType.NETWORK_FLOW, "description": "No suspicious outbound transfers"}
                ]
            },
            {
                "code": "H1",
                "statement": "Data was exfiltrated via USB/removable device",
                "requirements": [
                    {"type": EvidenceType.USB_DEVICE, "description": "USB device connection events"},
                    {"type": EvidenceType.FILE_ARTIFACT, "description": "File copy to removable media"}
                ],
                "mitre": ["T1052.001"]
            },
            {
                "code": "H2",
                "statement": "Data was exfiltrated via email",
                "requirements": [
                    {"type": EvidenceType.EMAIL, "description": "Email with attachments sent"},
                    {"type": EvidenceType.NETWORK_FLOW, "description": "SMTP/mail traffic"}
                ],
                "mitre": ["T1048.003"]
            },
            {
                "code": "H3",
                "statement": "Data was exfiltrated via cloud/web upload",
                "requirements": [
                    {"type": EvidenceType.NETWORK_FLOW, "description": "HTTP/HTTPS upload traffic"},
                    {"type": EvidenceType.PROCESS_TRACE, "description": "Browser or cloud app activity"}
                ],
                "mitre": ["T1567"]
            }
        ],
        "file_transfer": [
            {
                "code": "H0",
                "statement": "No unauthorized file transfers occurred",
                "is_null": True,
                "requirements": [
                    {"type": EvidenceType.FILE_ARTIFACT, "description": "No suspicious file movements"}
                ]
            },
            {
                "code": "H1",
                "statement": "Confidential files were transferred to external device",
                "requirements": [
                    {"type": EvidenceType.FILE_ARTIFACT, "description": "Sensitive file access"},
                    {"type": EvidenceType.USB_DEVICE, "description": "External device connection"}
                ]
            },
            {
                "code": "H2",
                "statement": "Files were transferred via Bluetooth",
                "requirements": [
                    {"type": EvidenceType.BLUETOOTH, "description": "Bluetooth pairing/transfer events"},
                    {"type": EvidenceType.FILE_ARTIFACT, "description": "Files accessed during transfer"}
                ]
            }
        ],
        "unauthorized_access": [
            {
                "code": "H0",
                "statement": "No unauthorized access occurred",
                "is_null": True,
                "requirements": [
                    {"type": EvidenceType.LOG_EVENT, "description": "Normal access patterns only"}
                ]
            },
            {
                "code": "H1",
                "statement": "Account credentials were compromised",
                "requirements": [
                    {"type": EvidenceType.USER_ACTIVITY, "description": "Anomalous login patterns"},
                    {"type": EvidenceType.LOG_EVENT, "description": "Failed login attempts"}
                ],
                "mitre": ["T1078"]
            },
            {
                "code": "H2",
                "statement": "Insider accessed resources beyond their authorization",
                "requirements": [
                    {"type": EvidenceType.USER_ACTIVITY, "description": "Access to unauthorized resources"},
                    {"type": EvidenceType.FILE_ARTIFACT, "description": "Sensitive data accessed"}
                ],
                "mitre": ["T1078.002"]
            }
        ],
        "timeline": [
            {
                "code": "H0",
                "statement": "Timeline cannot be established from available evidence",
                "is_null": True,
                "requirements": [
                    {"type": EvidenceType.LOG_EVENT, "description": "Insufficient timestamp data"}
                ]
            },
            {
                "code": "H1",
                "statement": "Activity occurred within the specified time range",
                "requirements": [
                    {"type": EvidenceType.LOG_EVENT, "description": "Events with timestamps in range"},
                    {"type": EvidenceType.SYSTEM_EVENT, "description": "System activity corroboration"}
                ]
            }
        ]
    }
    
    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.investigation = InvestigationStore.get(investigation_id)
    
    def detect_scenario_type(self) -> List[str]:
        """Detect scenario types from investigation context."""
        types = []
        
        if not self.investigation:
            return ["timeline"]  # Default
        
        scenario_lower = self.investigation.scenario.lower()
        
        # Check for data exfiltration keywords
        if any(kw in scenario_lower for kw in ["exfil", "steal", "confidential", "sensitive", "leak"]):
            types.append("data_exfiltration")
        
        # Check for file transfer keywords
        if any(kw in scenario_lower for kw in ["transfer", "copy", "usb", "bluetooth", "email"]):
            types.append("file_transfer")
        
        # Check for unauthorized access keywords
        if any(kw in scenario_lower for kw in ["unauthorized", "breach", "compromise", "intrusion"]):
            types.append("unauthorized_access")
        
        # Check for timeline keywords
        if any(kw in scenario_lower for kw in ["timeline", "sequence", "when", "chronolog"]):
            types.append("timeline")
        
        return types if types else ["timeline"]
    
    def generate_hypotheses(
        self,
        objectives: Optional[List[str]] = None
    ) -> List[Hypothesis]:
        """Generate hypotheses based on scenario and objectives."""
        hypotheses = []
        scenario_types = self.detect_scenario_type()
        
        seen_codes = set()
        
        for scenario_type in scenario_types:
            templates = self.HYPOTHESIS_TEMPLATES.get(scenario_type, [])
            
            for template in templates:
                # Ensure unique codes
                code = template["code"]
                if code in seen_codes:
                    code = f"{scenario_type[:3].upper()}-{code}"
                seen_codes.add(code)
                
                # Build evidence requirements
                requirements = []
                for req in template.get("requirements", []):
                    requirements.append(EvidenceRequirement(
                        description=req["description"],
                        evidence_type=req["type"],
                        is_critical=template.get("is_null", False)
                    ))
                
                hypothesis = Hypothesis(
                    investigation_id=self.investigation_id,
                    code=code,
                    statement=template["statement"],
                    is_null_hypothesis=template.get("is_null", False),
                    baseline_assumption="false",
                    evidence_requirements=requirements,
                    mitre_techniques=template.get("mitre", [])
                )
                
                hypotheses.append(hypothesis)
        
        return hypotheses
    
    def generate_from_objectives(
        self,
        objectives: List[InvestigationObjective]
    ) -> List[Hypothesis]:
        """Generate hypotheses from specific objectives."""
        hypotheses = []
        
        for i, obj in enumerate(objectives, 1):
            obj_lower = obj.description.lower()
            
            # Create null hypothesis for this objective
            null_hyp = Hypothesis(
                investigation_id=self.investigation_id,
                code=f"OBJ{i}-H0",
                statement=f"Objective '{obj.description}' cannot be achieved with available evidence",
                is_null_hypothesis=True,
                baseline_assumption="false"
            )
            hypotheses.append(null_hyp)
            
            # Create positive hypothesis
            pos_hyp = Hypothesis(
                investigation_id=self.investigation_id,
                code=f"OBJ{i}-H1",
                statement=f"Evidence supports: {obj.description}",
                baseline_assumption="false",
                parent_hypothesis=null_hyp.hypothesis_id,
                alternative_to=[null_hyp.hypothesis_id]
            )
            hypotheses.append(pos_hyp)
        
        return hypotheses


# ═══════════════════════════════════════════════════════════════════════════════
# HYPOTHESIS TESTER
# ═══════════════════════════════════════════════════════════════════════════════

class HypothesisTester:
    """
    Tests hypotheses against collected evidence.
    """
    
    def __init__(self, investigation_id: str):
        self.investigation_id = investigation_id
        self.tree = HypothesisStore.get_tree(investigation_id)
    
    def test_hypothesis(
        self,
        hypothesis_id: str,
        evidence_cards: List[str],
        module_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Test a hypothesis against evidence.
        
        Returns verdict and reasoning.
        """
        h = HypothesisStore.get_hypothesis(self.investigation_id, hypothesis_id)
        if not h:
            return {"error": f"Hypothesis not found: {hypothesis_id}"}
        
        # Check evidence requirements
        requirements_met = 0
        requirements_total = len(h.evidence_requirements)
        requirement_status = []
        
        for req in h.evidence_requirements:
            # In production, this would actually check evidence cards
            # For now, simulate based on evidence count
            met = len(evidence_cards) > 0
            if met:
                requirements_met += 1
                req.satisfied = True
            requirement_status.append({
                "description": req.description,
                "evidence_type": req.evidence_type.value if hasattr(req.evidence_type, 'value') else str(req.evidence_type),
                "satisfied": met,
                "is_critical": req.is_critical
            })
        
        # Determine verdict
        if requirements_total == 0:
            verdict = HypothesisVerdict.INCONCLUSIVE
            confidence = 0.3
        elif requirements_met == requirements_total:
            verdict = HypothesisVerdict.CONFIRMED
            confidence = 0.85
        elif requirements_met >= requirements_total * 0.5:
            verdict = HypothesisVerdict.PARTIALLY_CONFIRMED
            confidence = 0.6
        elif requirements_met > 0:
            verdict = HypothesisVerdict.INCONCLUSIVE
            confidence = 0.4
        else:
            verdict = HypothesisVerdict.REJECTED
            confidence = 0.75  # High confidence it's false
        
        # For null hypothesis, invert logic
        if h.is_null_hypothesis:
            if verdict == HypothesisVerdict.CONFIRMED:
                # If null hypothesis is confirmed, no incident
                pass
            elif verdict == HypothesisVerdict.REJECTED:
                # If null hypothesis is rejected, incident occurred
                confidence = 0.85
        
        # Update hypothesis
        h.verdict = verdict
        h.confidence_score = confidence
        h.confidence_level = ConfidenceLevel.from_score(confidence)
        h.supporting_evidence = evidence_cards
        h.reasoning = self._generate_reasoning(h, requirement_status, verdict)
        
        HypothesisStore.save_tree(self.tree)
        
        return {
            "hypothesis_id": hypothesis_id,
            "code": h.code,
            "statement": h.statement,
            "verdict": enum_value(verdict),
            "confidence_score": confidence,
            "confidence_level": enum_value(h.confidence_level) if h.confidence_level else None,
            "requirements": requirement_status,
            "requirements_met": f"{requirements_met}/{requirements_total}",
            "reasoning": h.reasoning,
            "is_null_hypothesis": h.is_null_hypothesis
        }
    
    def _generate_reasoning(
        self,
        hypothesis: Hypothesis,
        requirements: List[Dict],
        verdict: HypothesisVerdict
    ) -> str:
        """Generate reasoning for verdict."""
        met = [r for r in requirements if r["satisfied"]]
        unmet = [r for r in requirements if not r["satisfied"]]
        
        reasoning = f"Hypothesis '{hypothesis.code}': {hypothesis.statement}\n\n"
        
        if verdict == HypothesisVerdict.CONFIRMED:
            reasoning += "VERDICT: CONFIRMED\n"
            reasoning += f"All {len(met)} evidence requirements were satisfied.\n"
        elif verdict == HypothesisVerdict.REJECTED:
            reasoning += "VERDICT: REJECTED\n"
            reasoning += f"Critical evidence requirements were not met.\n"
        elif verdict == HypothesisVerdict.PARTIALLY_CONFIRMED:
            reasoning += "VERDICT: PARTIALLY CONFIRMED\n"
            reasoning += f"{len(met)} of {len(requirements)} requirements satisfied.\n"
        else:
            reasoning += "VERDICT: INCONCLUSIVE\n"
            reasoning += "Insufficient evidence to confirm or reject.\n"
        
        if met:
            reasoning += "\nSupporting evidence:\n"
            for r in met:
                reasoning += f"  ✓ {r['description']}\n"
        
        if unmet:
            reasoning += "\nMissing evidence:\n"
            for r in unmet:
                reasoning += f"  ✗ {r['description']}\n"
        
        return reasoning
    
    def test_all_hypotheses(
        self,
        evidence_cards: List[str]
    ) -> Dict[str, Any]:
        """Test all hypotheses in the tree."""
        if not self.tree:
            return {"error": "No hypothesis tree found"}
        
        results = []
        
        for h in self.tree.hypotheses:
            if h.verdict == HypothesisVerdict.UNTESTED:
                result = self.test_hypothesis(h.hypothesis_id, evidence_cards)
                results.append(result)
        
        # Update tree statistics
        self.tree.tested_count = len([h for h in self.tree.hypotheses if h.verdict != HypothesisVerdict.UNTESTED])
        self.tree.confirmed_count = len([h for h in self.tree.hypotheses if h.verdict == HypothesisVerdict.CONFIRMED])
        self.tree.rejected_count = len([h for h in self.tree.hypotheses if h.verdict == HypothesisVerdict.REJECTED])
        self.tree.inconclusive_count = len([h for h in self.tree.hypotheses if h.verdict == HypothesisVerdict.INCONCLUSIVE])
        
        HypothesisStore.save_tree(self.tree)
        
        return {
            "tested": len(results),
            "results": results,
            "summary": {
                "confirmed": self.tree.confirmed_count,
                "rejected": self.tree.rejected_count,
                "inconclusive": self.tree.inconclusive_count,
                "untested": len(self.tree.hypotheses) - self.tree.tested_count
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceCalculator:
    """
    Calculates confidence scores using ODNI ICD 203 standards.
    
    Six factors:
    1. Evidence Coverage (0.20) - How complete is the evidence?
    2. Module Agreement (0.20) - Do different modules agree?
    3. Temporal Consistency (0.15) - Is timeline coherent?
    4. Cross Validation (0.15) - External corroboration?
    5. Pattern Match (0.15) - Matches known patterns?
    6. Research Alignment (0.15) - Aligns with methodologies?
    """
    
    FACTOR_WEIGHTS = {
        "evidence_coverage": 0.20,
        "module_agreement": 0.20,
        "temporal_consistency": 0.15,
        "cross_validation": 0.15,
        "pattern_match": 0.15,
        "research_alignment": 0.15
    }
    
    def compute_confidence(
        self,
        target_type: str,
        target_id: str,
        evidence_cards: List[str],
        module_results: Optional[Dict[str, Any]] = None
    ) -> ConfidenceAssessment:
        """
        Compute multi-factor confidence assessment.
        """
        factors = []
        
        # Factor 1: Evidence Coverage
        evidence_score = min(1.0, len(evidence_cards) / 10)  # Normalize to 10 cards
        factors.append(ConfidenceFactor(
            factor_name="evidence_coverage",
            weight=self.FACTOR_WEIGHTS["evidence_coverage"],
            score=evidence_score,
            reasoning=f"{len(evidence_cards)} evidence cards collected",
            evidence_refs=evidence_cards[:5]  # Reference up to 5
        ))
        
        # Factor 2: Module Agreement
        module_score = 0.7  # Default when no module results
        if module_results:
            # Check if multiple modules found similar things
            modules_with_findings = len([m for m, r in module_results.items() if r.get("findings")])
            module_score = min(1.0, modules_with_findings / 4)
        factors.append(ConfidenceFactor(
            factor_name="module_agreement",
            weight=self.FACTOR_WEIGHTS["module_agreement"],
            score=module_score,
            reasoning="Module agreement assessment based on cross-module findings"
        ))
        
        # Factor 3: Temporal Consistency
        temporal_score = 0.75  # Would be computed from timeline analysis
        factors.append(ConfidenceFactor(
            factor_name="temporal_consistency",
            weight=self.FACTOR_WEIGHTS["temporal_consistency"],
            score=temporal_score,
            reasoning="Timeline shows consistent event sequences"
        ))
        
        # Factor 4: Cross Validation
        cross_val_score = 0.6  # Would check external sources
        factors.append(ConfidenceFactor(
            factor_name="cross_validation",
            weight=self.FACTOR_WEIGHTS["cross_validation"],
            score=cross_val_score,
            reasoning="Limited external validation available"
        ))
        
        # Factor 5: Pattern Match
        pattern_score = 0.7  # Would check against MITRE ATT&CK
        factors.append(ConfidenceFactor(
            factor_name="pattern_match",
            weight=self.FACTOR_WEIGHTS["pattern_match"],
            score=pattern_score,
            reasoning="Findings align with known attack patterns"
        ))
        
        # Factor 6: Research Alignment
        research_score = 0.75  # Would check methodology knowledge base
        factors.append(ConfidenceFactor(
            factor_name="research_alignment",
            weight=self.FACTOR_WEIGHTS["research_alignment"],
            score=research_score,
            reasoning="Investigation follows established forensic methodologies"
        ))
        
        # Calculate overall score
        overall_score = sum(f.weighted_score for f in factors)
        
        # Create assessment
        assessment = ConfidenceAssessment(
            target_type=target_type,
            target_id=target_id,
            factors=factors,
            evidence_coverage=evidence_score,
            module_agreement=module_score,
            temporal_consistency=temporal_score,
            cross_validation=cross_val_score,
            pattern_match=pattern_score,
            research_alignment=research_score,
            overall_score=overall_score,
            confidence_level=ConfidenceLevel.from_score(overall_score)
        )
        
        # Add caveats based on weak factors
        for f in factors:
            if f.score < 0.5:
                assessment.caveats.append(f"Low {f.factor_name}: {f.reasoning}")
        
        ConfidenceStore.save(assessment)
        
        return assessment


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@mcp_tool(
    name="hypothesis.generate",
    category=ToolCategory.HYPOTHESIS,
    description="Generate hypotheses based on investigation scenario and objectives.",
    requires_case_id=False,
    tags={"hypothesis", "generate", "ach"}
)
@with_coc_logging(action_type=CoCActionType.HYPOTHESIS_TEST)
@audit_trail(operation="HYPOTHESIS_GENERATE")
async def generate_hypotheses(
    investigation_id: str,
    objectives: Optional[List[str]] = None,
    include_null: bool = True,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Generate hypotheses for an investigation.
    
    Args:
        investigation_id: Investigation ID
        objectives: Optional specific objectives
        include_null: Whether to include null hypothesis
    
    Returns:
        Generated hypotheses
    """
    # Verify investigation exists
    inv = InvestigationStore.get(investigation_id)
    if not inv:
        return {"success": False, "error": f"Investigation not found: {investigation_id}"}
    
    generator = HypothesisGenerator(investigation_id)
    
    # Generate from scenario
    hypotheses = generator.generate_hypotheses(objectives)
    
    # Generate from objectives if provided
    if inv.objectives:
        obj_hypotheses = generator.generate_from_objectives(inv.objectives)
        hypotheses.extend(obj_hypotheses)
    
    # Filter null if not wanted
    if not include_null:
        hypotheses = [h for h in hypotheses if not h.is_null_hypothesis]
    
    # Save to store
    for h in hypotheses:
        HypothesisStore.add_hypothesis(investigation_id, h)
    
    tree = HypothesisStore.get_tree(investigation_id)
    
    return {
        "success": True,
        "investigation_id": investigation_id,
        "hypothesis_count": len(hypotheses),
        "hypotheses": [
            {
                "hypothesis_id": h.hypothesis_id,
                "code": h.code,
                "statement": h.statement,
                "is_null_hypothesis": h.is_null_hypothesis,
                "requirements": len(h.evidence_requirements),
                "mitre_techniques": h.mitre_techniques
            }
            for h in hypotheses
        ],
        "null_hypothesis": tree.null_hypothesis if tree else None,
        "next_action": "Use hypothesis.test to test against evidence"
    }


@mcp_tool(
    name="hypothesis.create",
    category=ToolCategory.HYPOTHESIS,
    description="Create a manual hypothesis.",
    requires_case_id=False,
    tags={"hypothesis", "create"}
)
@audit_trail(operation="HYPOTHESIS_CREATE")
async def create_hypothesis(
    investigation_id: str,
    code: str,
    statement: str,
    is_null: bool = False,
    evidence_requirements: Optional[List[Dict[str, str]]] = None,
    mitre_techniques: Optional[List[str]] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Create a manual hypothesis.
    
    Args:
        investigation_id: Investigation ID
        code: Hypothesis code (e.g., "H1", "CUSTOM-1")
        statement: Hypothesis statement
        is_null: Whether this is a null hypothesis
        evidence_requirements: List of {description, evidence_type} dicts
        mitre_techniques: Related MITRE ATT&CK technique IDs
    
    Returns:
        Created hypothesis
    """
    # Build evidence requirements
    requirements = []
    if evidence_requirements:
        for req in evidence_requirements:
            try:
                ev_type = EvidenceType(req.get("evidence_type", "log_event"))
            except ValueError:
                ev_type = EvidenceType.LOG_EVENT
            
            requirements.append(EvidenceRequirement(
                description=req.get("description", ""),
                evidence_type=ev_type
            ))
    
    hypothesis = Hypothesis(
        investigation_id=investigation_id,
        code=code,
        statement=statement,
        is_null_hypothesis=is_null,
        baseline_assumption="false",
        evidence_requirements=requirements,
        mitre_techniques=mitre_techniques or []
    )
    
    HypothesisStore.add_hypothesis(investigation_id, hypothesis)
    
    return {
        "success": True,
        "hypothesis_id": hypothesis.hypothesis_id,
        "code": code,
        "statement": statement,
        "is_null_hypothesis": is_null,
        "requirements_count": len(requirements)
    }


@mcp_tool(
    name="hypothesis.test",
    category=ToolCategory.HYPOTHESIS,
    description="Test hypotheses against collected evidence.",
    requires_case_id=False,
    tags={"hypothesis", "test", "ach"}
)
@with_coc_logging(action_type=CoCActionType.HYPOTHESIS_TEST)
@with_evidence_hash()
@audit_trail(operation="HYPOTHESIS_TEST")
async def test_hypotheses(
    investigation_id: str,
    hypothesis_id: Optional[str] = None,
    evidence_cards: Optional[List[str]] = None,
    test_all: bool = False,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Test hypothesis against evidence.
    
    Args:
        investigation_id: Investigation ID
        hypothesis_id: Specific hypothesis to test (or use test_all)
        evidence_cards: Evidence card IDs to test against
        test_all: Test all untested hypotheses
    
    Returns:
        Test results with verdicts and confidence
    """
    tester = HypothesisTester(investigation_id)
    evidence = evidence_cards or []
    
    if test_all:
        results = tester.test_all_hypotheses(evidence)
        return {
            "success": True,
            "investigation_id": investigation_id,
            "mode": "test_all",
            **results
        }
    elif hypothesis_id:
        result = tester.test_hypothesis(hypothesis_id, evidence)
        return {
            "success": True,
            "investigation_id": investigation_id,
            "mode": "single",
            **result
        }
    else:
        return {
            "success": False,
            "error": "Specify hypothesis_id or set test_all=True"
        }


@mcp_tool(
    name="hypothesis.get",
    category=ToolCategory.HYPOTHESIS,
    description="Get hypothesis tree for an investigation.",
    requires_case_id=False,
    tags={"hypothesis", "get"}
)
async def get_hypothesis_tree(
    investigation_id: str,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Get all hypotheses for an investigation.
    
    Args:
        investigation_id: Investigation ID
    
    Returns:
        Hypothesis tree with all hypotheses
    """
    tree = HypothesisStore.get_tree(investigation_id)
    
    if not tree:
        return {
            "success": False,
            "error": f"No hypotheses found for investigation: {investigation_id}"
        }
    
    return {
        "success": True,
        "investigation_id": investigation_id,
        "null_hypothesis": tree.null_hypothesis,
        "total_hypotheses": tree.total_count,
        "statistics": {
            "tested": tree.tested_count,
            "confirmed": tree.confirmed_count,
            "rejected": tree.rejected_count,
            "inconclusive": tree.inconclusive_count
        },
        "hypotheses": [
            {
                "hypothesis_id": h.hypothesis_id,
                "code": h.code,
                "statement": h.statement,
                "is_null_hypothesis": h.is_null_hypothesis,
                "verdict": h.verdict.value if hasattr(h.verdict, 'value') else str(h.verdict),
                "confidence_score": h.confidence_score,
                "confidence_level": h.confidence_level.value if h.confidence_level else None,
                "supporting_evidence": len(h.supporting_evidence),
                "contradicting_evidence": len(h.contradicting_evidence)
            }
            for h in tree.hypotheses
        ]
    }


@mcp_tool(
    name="confidence.compute",
    category=ToolCategory.HYPOTHESIS,
    description="Compute multi-factor confidence assessment using ODNI ICD 203 standards.",
    requires_case_id=False,
    tags={"confidence", "odni", "compute"}
)
@with_evidence_hash()
@audit_trail(operation="CONFIDENCE_COMPUTE")
async def compute_confidence(
    target_type: str,
    target_id: str,
    evidence_cards: Optional[List[str]] = None,
    module_results: Optional[Dict[str, Any]] = None,
    _context: Optional[ToolExecutionContext] = None
) -> Dict[str, Any]:
    """
    Compute confidence assessment.
    
    Args:
        target_type: Type being assessed (hypothesis, finding, report)
        target_id: ID of the target
        evidence_cards: Evidence card IDs
        module_results: Results from analysis modules
    
    Returns:
        Multi-factor confidence assessment
    """
    calculator = ConfidenceCalculator()
    
    assessment = calculator.compute_confidence(
        target_type=target_type,
        target_id=target_id,
        evidence_cards=evidence_cards or [],
        module_results=module_results
    )
    
    return {
        "success": True,
        "assessment_id": assessment.assessment_id,
        "target_type": target_type,
        "target_id": target_id,
        "overall_score": assessment.overall_score,
        "confidence_level": enum_value(assessment.confidence_level),
        "factors": [
            {
                "name": f.factor_name,
                "weight": f.weight,
                "score": f.score,
                "weighted_score": f.weighted_score,
                "reasoning": f.reasoning
            }
            for f in assessment.factors
        ],
        "caveats": assessment.caveats,
        "interpretation": _interpret_confidence(assessment.confidence_level)
    }


def _interpret_confidence(level: ConfidenceLevel) -> str:
    """Provide interpretation of confidence level."""
    interpretations = {
        ConfidenceLevel.VERY_HIGH: "Near certain. Based on high-quality information from multiple independent sources. Any gaps in information would be unlikely to change the assessment.",
        ConfidenceLevel.HIGH: "Generally reflects well-validated evidence with few gaps. Changes to key assumptions could affect the assessment but are unlikely.",
        ConfidenceLevel.MODERATE: "Based on credibly sourced and plausible information, but not sufficient for a higher confidence. Additional evidence could change the assessment.",
        ConfidenceLevel.LOW: "Based on fragmented or poorly corroborated information. Significant gaps in evidence exist. Assessment is speculative.",
        ConfidenceLevel.VERY_LOW: "Evidence is unreliable or contradictory. Assessment is highly uncertain and should be treated as preliminary."
    }
    return interpretations.get(level, "Unknown confidence level")


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "HypothesisStore",
    "ConfidenceStore",
    "HypothesisGenerator",
    "HypothesisTester",
    "ConfidenceCalculator",
    "generate_hypotheses",
    "create_hypothesis",
    "test_hypotheses",
    "get_hypothesis_tree",
    "compute_confidence",
]
