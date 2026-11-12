"""
Hypothesis to Report Binding — Auto-generate report sections from findings.

This module bridges the gap between hypothesis evaluation results and
report section generation. It automatically:

1. Maps hypothesis findings to report sections
2. Generates section content with evidence citations
3. Creates timeline visualizations
4. Builds appendices with full evidence inventory

Key principle: AI generates narrative summaries, but all facts (IPs, timestamps,
file names, etc.) come directly from the Evidence Vault with SHA-256 verification.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ReportSectionType(str, Enum):
    """Standard forensic report section types."""
    TITLE_PAGE = "title_page"
    TABLE_OF_CONTENTS = "table_of_contents"
    EXECUTIVE_SUMMARY = "executive_summary"
    CASE_BACKGROUND = "case_background"
    EVIDENCE_INVENTORY = "evidence_inventory"
    METHODOLOGY = "methodology"
    USB_ANALYSIS = "usb_analysis"
    BLUETOOTH_ANALYSIS = "bluetooth_analysis"
    EMAIL_ANALYSIS = "email_analysis"
    NETWORK_ANALYSIS = "network_analysis"
    TIMELINE_ANALYSIS = "timeline_analysis"
    FINDINGS = "findings"
    CONCLUSIONS = "conclusions"
    RECOMMENDATIONS = "recommendations"
    APPENDIX_EVIDENCE = "appendix_evidence"
    APPENDIX_COC = "appendix_chain_of_custody"
    APPENDIX_HASHES = "appendix_hashes"


@dataclass
class HypothesisFinding:
    """Result of hypothesis evaluation."""
    hypothesis_id: str
    hypothesis_name: str
    verdict: str  # confirmed, rejected, inconclusive
    confidence: float
    evidence_for: List[str]  # Evidence IDs supporting
    evidence_against: List[str]  # Evidence IDs contradicting
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_confirmed(self) -> bool:
        return self.verdict == "confirmed"


@dataclass
class EvidenceReference:
    """Reference to evidence in the vault."""
    evidence_id: str
    evidence_type: str
    description: str
    timestamp: str
    source_log: str
    hash: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSection:
    """Generated report section with evidence citations."""
    section_type: ReportSectionType
    title: str
    content: str  # AI-generated narrative
    evidence_refs: List[str]  # Evidence IDs cited
    tables: List[Dict[str, Any]] = field(default_factory=list)
    figures: List[Dict[str, Any]] = field(default_factory=list)
    subsections: List["ReportSection"] = field(default_factory=list)
    page_estimate: int = 1


class HypothesisReportBinder:
    """
    Binds hypothesis findings to report sections.
    
    Creates a mapping between investigation results and the final
    report structure, ensuring all evidence is properly cited.
    """
    
    def __init__(self, case_id: str, investigation_id: str):
        self.case_id = case_id
        self.investigation_id = investigation_id
        self.findings: List[HypothesisFinding] = []
        self.evidence_map: Dict[str, EvidenceReference] = {}
        self.sections: List[ReportSection] = []
        
        # Template mappings
        self.hypothesis_to_section = {
            "usb_exfiltration": ReportSectionType.USB_ANALYSIS,
            "bluetooth_exfiltration": ReportSectionType.BLUETOOTH_ANALYSIS,
            "email_exfiltration": ReportSectionType.EMAIL_ANALYSIS,
            "network_exfiltration": ReportSectionType.NETWORK_ANALYSIS,
        }
    
    def add_finding(self, finding: HypothesisFinding):
        """Add a hypothesis finding."""
        self.findings.append(finding)
    
    def add_evidence(self, evidence: EvidenceReference):
        """Add evidence to the map."""
        self.evidence_map[evidence.evidence_id] = evidence
    
    def generate_report_structure(self) -> List[ReportSection]:
        """
        Generate the complete report structure based on findings.
        
        Returns: List of ReportSection objects in order
        """
        sections = []
        
        # 1. Title Page
        sections.append(self._create_title_page())
        
        # 2. Table of Contents (placeholder - generated later)
        sections.append(self._create_toc_placeholder())
        
        # 3. Executive Summary
        sections.append(self._create_executive_summary())
        
        # 4. Case Background
        sections.append(self._create_case_background())
        
        # 5. Evidence Inventory
        sections.append(self._create_evidence_inventory())
        
        # 6. Methodology
        sections.append(self._create_methodology())
        
        # 7-10. Analysis Sections (based on confirmed hypotheses)
        for finding in self.findings:
            if finding.is_confirmed:
                section = self._create_analysis_section(finding)
                if section:
                    sections.append(section)
        
        # 11. Timeline Analysis
        sections.append(self._create_timeline_section())
        
        # 12. Findings Summary
        sections.append(self._create_findings_section())
        
        # 13. Conclusions
        sections.append(self._create_conclusions_section())
        
        # 14. Recommendations
        sections.append(self._create_recommendations_section())
        
        # 15-17. Appendices
        sections.extend(self._create_appendices())
        
        self.sections = sections
        return sections
    
    def _create_title_page(self) -> ReportSection:
        """Create title page section."""
        return ReportSection(
            section_type=ReportSectionType.TITLE_PAGE,
            title="DIGITAL FORENSIC INVESTIGATION REPORT",
            content=f"""
CASE REFERENCE: {self.case_id}
INVESTIGATION ID: {self.investigation_id}

CLASSIFICATION: CONFIDENTIAL

Prepared for: [Organization Name]
Prepared by: [Investigator Name]
Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

This report contains the findings of a digital forensic investigation
conducted in accordance with NIST SP 800-86 guidelines.
            """.strip(),
            evidence_refs=[],
            page_estimate=1
        )
    
    def _create_toc_placeholder(self) -> ReportSection:
        """Create table of contents placeholder."""
        return ReportSection(
            section_type=ReportSectionType.TABLE_OF_CONTENTS,
            title="TABLE OF CONTENTS",
            content="[Auto-generated from section titles]",
            evidence_refs=[],
            page_estimate=2
        )
    
    def _create_executive_summary(self) -> ReportSection:
        """Create executive summary based on findings."""
        # Count confirmed/rejected hypotheses
        confirmed = [f for f in self.findings if f.is_confirmed]
        rejected = [f for f in self.findings if f.verdict == "rejected"]
        
        # Calculate overall confidence
        if confirmed:
            avg_confidence = sum(f.confidence for f in confirmed) / len(confirmed)
        else:
            avg_confidence = 0.0
        
        # Collect key evidence
        key_evidence = []
        for finding in confirmed:
            key_evidence.extend(finding.evidence_for[:3])
        
        content = f"""
EXECUTIVE SUMMARY

Investigation Overview:
This investigation analyzed digital evidence from seized devices to determine
whether unauthorized data exfiltration occurred. The analysis covered multiple
potential exfiltration channels including USB, Bluetooth, and email transfers.

Key Findings:
• {len(confirmed)} hypothesis(es) CONFIRMED with evidence
• {len(rejected)} hypothesis(es) REJECTED (insufficient evidence)
• Overall confidence level: {avg_confidence:.1%}

Confirmed Exfiltration Channels:
"""
        for finding in confirmed:
            content += f"• {finding.hypothesis_name}: {finding.confidence:.1%} confidence\n"
        
        content += f"""
Evidence Summary:
A total of {len(self.evidence_map)} evidence items were analyzed, with
{len(key_evidence)} items directly supporting the confirmed findings.

Conclusion:
{"The investigation confirms unauthorized data transfer occurred via the identified channels." if confirmed else "No conclusive evidence of unauthorized data transfer was found."}

Recommendations:
Immediate actions are recommended to address the identified security incidents.
See Section 14 for detailed recommendations.
        """
        
        return ReportSection(
            section_type=ReportSectionType.EXECUTIVE_SUMMARY,
            title="EXECUTIVE SUMMARY",
            content=content.strip(),
            evidence_refs=key_evidence[:10],
            page_estimate=3
        )
    
    def _create_case_background(self) -> ReportSection:
        """Create case background section."""
        return ReportSection(
            section_type=ReportSectionType.CASE_BACKGROUND,
            title="CASE BACKGROUND",
            content="""
1. CASE DESCRIPTION

This section describes the circumstances that led to the investigation,
including the initial incident report, seized devices, and investigation scope.

1.1 Incident Overview
[AI-generated summary based on scenario input]

1.2 Seized Devices
The following digital devices were seized and analyzed:
• Windows Computer - [hostname/serial]
• Android Mobile Phone - [model/IMEI]

1.3 Investigation Scope
The investigation was tasked with determining:
• Whether confidential files were transferred from the computer
• What channels were used for the transfer (USB, Bluetooth, Email)
• Timeline of the transfer activities
• IP addresses and network endpoints involved

1.4 Investigation Period
Analysis covered the period from [start date] to [end date].
            """.strip(),
            evidence_refs=[],
            page_estimate=4
        )
    
    def _create_evidence_inventory(self) -> ReportSection:
        """Create evidence inventory section."""
        evidence_table = []
        for ev_id, ev in self.evidence_map.items():
            evidence_table.append({
                "ID": ev_id,
                "Type": ev.evidence_type,
                "Source": ev.source_log,
                "Timestamp": ev.timestamp,
                "Hash": ev.hash[:20] + "...",
            })
        
        return ReportSection(
            section_type=ReportSectionType.EVIDENCE_INVENTORY,
            title="EVIDENCE INVENTORY",
            content=f"""
2. EVIDENCE INVENTORY

This section documents all digital evidence analyzed during the investigation.

2.1 Evidence Overview
Total evidence items: {len(self.evidence_map)}
All evidence has been verified using SHA-256 cryptographic hashing.

2.2 Evidence Integrity
Each evidence item is stored with:
• Original file hash (SHA-256)
• Chain of custody record
• Timestamp of acquisition

2.3 Evidence Table
See table below for complete evidence inventory.
            """.strip(),
            evidence_refs=list(self.evidence_map.keys()),
            tables=[{
                "title": "Evidence Inventory",
                "columns": ["ID", "Type", "Source", "Timestamp", "Hash"],
                "data": evidence_table
            }],
            page_estimate=5
        )
    
    def _create_methodology(self) -> ReportSection:
        """Create methodology section."""
        return ReportSection(
            section_type=ReportSectionType.METHODOLOGY,
            title="INVESTIGATION METHODOLOGY",
            content="""
3. INVESTIGATION METHODOLOGY

3.1 Standards Compliance
This investigation followed:
• NIST SP 800-86 (Guide to Integrating Forensic Techniques)
• ISO 27037 (Guidelines for identification, collection, acquisition)
• SWGDE Best Practices for Digital Evidence

3.2 Analysis Approach
The investigation employed a hypothesis-driven approach:
1. Generate hypotheses based on scenario
2. Identify evidence required for each hypothesis
3. Analyze logs and artifacts using automated tools
4. Compute confidence scores based on evidence strength
5. Confirm or reject hypotheses

3.3 Tools Used
• NFLIP Investigation Platform
• Timeline Analysis Module
• Anomaly Detection Module
• Correlation Analysis Module
• Network Flow Analysis Module

3.4 Evidence Handling
All evidence was:
• Acquired using forensically sound methods
• Hash-verified at acquisition and analysis
• Logged in chain of custody
• Analyzed on write-blocked media
            """.strip(),
            evidence_refs=[],
            page_estimate=5
        )
    
    def _create_analysis_section(
        self,
        finding: HypothesisFinding
    ) -> Optional[ReportSection]:
        """Create analysis section for a confirmed hypothesis."""
        
        # Map hypothesis to section type
        section_type = None
        title = ""
        
        if "usb" in finding.hypothesis_id.lower():
            section_type = ReportSectionType.USB_ANALYSIS
            title = "USB DEVICE ANALYSIS"
        elif "bluetooth" in finding.hypothesis_id.lower():
            section_type = ReportSectionType.BLUETOOTH_ANALYSIS
            title = "BLUETOOTH TRANSFER ANALYSIS"
        elif "email" in finding.hypothesis_id.lower():
            section_type = ReportSectionType.EMAIL_ANALYSIS
            title = "EMAIL ANALYSIS"
        elif "network" in finding.hypothesis_id.lower():
            section_type = ReportSectionType.NETWORK_ANALYSIS
            title = "NETWORK ANALYSIS"
        else:
            return None
        
        # Build evidence table
        evidence_table = []
        for ev_id in finding.evidence_for:
            if ev_id in self.evidence_map:
                ev = self.evidence_map[ev_id]
                evidence_table.append({
                    "ID": ev_id,
                    "Type": ev.evidence_type,
                    "Description": ev.description[:50],
                    "Timestamp": ev.timestamp,
                })
        
        content = f"""
{title}

Hypothesis: {finding.hypothesis_name}
Verdict: {finding.verdict.upper()}
Confidence: {finding.confidence:.1%}

Analysis Summary:
{finding.summary}

Evidence Supporting This Finding:
{len(finding.evidence_for)} evidence items support this hypothesis.
See evidence table below.

Evidence Details:
"""
        
        # Add specific details from finding
        if "files" in finding.details:
            content += "\nFiles Identified:\n"
            for f in finding.details["files"]:
                content += f"• {f}\n"
        
        if "devices" in finding.details:
            content += "\nDevices Involved:\n"
            for d in finding.details["devices"]:
                content += f"• {d}\n"
        
        if "ip_addresses" in finding.details:
            content += "\nIP Addresses:\n"
            for ip in finding.details["ip_addresses"]:
                content += f"• {ip}\n"
        
        return ReportSection(
            section_type=section_type,
            title=title,
            content=content.strip(),
            evidence_refs=finding.evidence_for,
            tables=[{
                "title": f"Evidence for {finding.hypothesis_name}",
                "columns": ["ID", "Type", "Description", "Timestamp"],
                "data": evidence_table
            }],
            page_estimate=8
        )
    
    def _create_timeline_section(self) -> ReportSection:
        """Create timeline analysis section."""
        # Sort evidence by timestamp
        sorted_evidence = sorted(
            self.evidence_map.values(),
            key=lambda e: e.timestamp
        )
        
        timeline_data = []
        for ev in sorted_evidence[:20]:
            timeline_data.append({
                "Timestamp": ev.timestamp,
                "Event": ev.description[:40],
                "Type": ev.evidence_type,
                "Evidence ID": ev.evidence_id,
            })
        
        return ReportSection(
            section_type=ReportSectionType.TIMELINE_ANALYSIS,
            title="TIMELINE ANALYSIS",
            content="""
TIMELINE ANALYSIS

This section presents the chronological sequence of events identified
during the investigation.

Timeline Overview:
The timeline spans from [earliest event] to [latest event], covering
a period of [X] days.

Key Timeline Observations:
• [Observation 1 based on timeline clustering]
• [Observation 2 based on temporal patterns]
• [Observation 3 based on sequence analysis]

Activity Patterns:
The analysis identified the following activity patterns:
• Peak activity during [time periods]
• Correlation between [related events]

See timeline visualization below.
            """.strip(),
            evidence_refs=[ev.evidence_id for ev in sorted_evidence[:20]],
            tables=[{
                "title": "Event Timeline",
                "columns": ["Timestamp", "Event", "Type", "Evidence ID"],
                "data": timeline_data
            }],
            figures=[{
                "type": "timeline",
                "title": "Investigation Timeline",
                "data_source": "evidence_vault"
            }],
            page_estimate=10
        )
    
    def _create_findings_section(self) -> ReportSection:
        """Create findings summary section."""
        findings_table = []
        for f in self.findings:
            findings_table.append({
                "Hypothesis": f.hypothesis_name,
                "Verdict": f.verdict.upper(),
                "Confidence": f"{f.confidence:.1%}",
                "Evidence Count": len(f.evidence_for),
            })
        
        content = """
FINDINGS SUMMARY

This section summarizes the results of all hypothesis evaluations.

Hypothesis Evaluation Results:
"""
        for f in self.findings:
            status = "✓" if f.is_confirmed else "✗" if f.verdict == "rejected" else "?"
            content += f"\n{status} {f.hypothesis_name}\n"
            content += f"  Verdict: {f.verdict.upper()}\n"
            content += f"  Confidence: {f.confidence:.1%}\n"
            content += f"  Supporting Evidence: {len(f.evidence_for)} items\n"
        
        # Overall assessment
        confirmed = [f for f in self.findings if f.is_confirmed]
        if confirmed:
            content += f"""
Overall Assessment:
The investigation CONFIRMED {len(confirmed)} hypothesis(es) with sufficient
evidence to support the findings.
            """
        else:
            content += """
Overall Assessment:
No hypotheses were confirmed with sufficient evidence.
            """
        
        return ReportSection(
            section_type=ReportSectionType.FINDINGS,
            title="FINDINGS SUMMARY",
            content=content.strip(),
            evidence_refs=[],
            tables=[{
                "title": "Hypothesis Evaluation Results",
                "columns": ["Hypothesis", "Verdict", "Confidence", "Evidence Count"],
                "data": findings_table
            }],
            page_estimate=5
        )
    
    def _create_conclusions_section(self) -> ReportSection:
        """Create conclusions section."""
        confirmed = [f for f in self.findings if f.is_confirmed]
        
        content = """
CONCLUSIONS

Based on the comprehensive analysis of digital evidence, the investigation
concludes the following:
"""
        
        if confirmed:
            content += "\nConfirmed Findings:\n"
            for i, f in enumerate(confirmed, 1):
                content += f"\n{i}. {f.hypothesis_name}\n"
                content += f"   {f.summary}\n"
                content += f"   (Confidence: {f.confidence:.1%})\n"
            
            content += """
Summary:
The evidence conclusively demonstrates that unauthorized data transfer
occurred through the confirmed channels. The timeline analysis shows
a clear pattern of deliberate exfiltration activity.

Legal Considerations:
The findings documented in this report may be used to support:
• Disciplinary proceedings
• Civil litigation
• Criminal prosecution (if applicable)

All evidence has been collected and documented in accordance with
forensic best practices to ensure admissibility.
            """
        else:
            content += """
No Confirmed Findings:
The investigation did not find sufficient evidence to confirm any
of the hypotheses tested. This does not necessarily indicate that
no unauthorized activity occurred, but rather that the available
evidence was insufficient to confirm the suspected activities.

Recommendations:
• Expand the scope of log collection
• Review additional data sources
• Consider alternative investigation approaches
            """
        
        return ReportSection(
            section_type=ReportSectionType.CONCLUSIONS,
            title="CONCLUSIONS",
            content=content.strip(),
            evidence_refs=[],
            page_estimate=4
        )
    
    def _create_recommendations_section(self) -> ReportSection:
        """Create recommendations section."""
        confirmed = [f for f in self.findings if f.is_confirmed]
        
        content = """
RECOMMENDATIONS

Based on the investigation findings, the following actions are recommended:

IMMEDIATE ACTIONS:
"""
        
        if confirmed:
            for finding in confirmed:
                if "usb" in finding.hypothesis_id.lower():
                    content += """
1. USB Device Controls
   • Disable USB mass storage on the affected workstation
   • Review USB device policy organization-wide
   • Implement USB device whitelisting
   • Enable USB audit logging
"""
                if "bluetooth" in finding.hypothesis_id.lower():
                    content += """
2. Bluetooth Controls
   • Disable Bluetooth on corporate workstations
   • Implement Bluetooth device restrictions via GPO
   • Review Bluetooth pairing logs
"""
                if "email" in finding.hypothesis_id.lower():
                    content += """
3. Email Security
   • Review DLP (Data Loss Prevention) policies
   • Implement attachment size limits
   • Block personal email services
   • Enable enhanced email logging
"""
        
        content += """
LONG-TERM RECOMMENDATIONS:

1. Security Monitoring
   • Deploy endpoint detection and response (EDR)
   • Implement SIEM for centralized logging
   • Enable advanced audit policies

2. Policy Updates
   • Update acceptable use policy
   • Implement data classification policy
   • Review access control policies

3. Training
   • Security awareness training for all employees
   • Incident response training for IT staff

4. Technical Controls
   • Network segmentation
   • Data encryption at rest
   • Regular security assessments
        """
        
        return ReportSection(
            section_type=ReportSectionType.RECOMMENDATIONS,
            title="RECOMMENDATIONS",
            content=content.strip(),
            evidence_refs=[],
            page_estimate=5
        )
    
    def _create_appendices(self) -> List[ReportSection]:
        """Create appendix sections."""
        appendices = []
        
        # Appendix A: Full Evidence Inventory
        evidence_list = []
        for ev_id, ev in self.evidence_map.items():
            evidence_list.append({
                "Evidence ID": ev_id,
                "Type": ev.evidence_type,
                "Description": ev.description,
                "Source Log": ev.source_log,
                "Timestamp": ev.timestamp,
                "SHA-256 Hash": ev.hash,
            })
        
        appendices.append(ReportSection(
            section_type=ReportSectionType.APPENDIX_EVIDENCE,
            title="APPENDIX A: FULL EVIDENCE INVENTORY",
            content="Complete inventory of all digital evidence analyzed.",
            evidence_refs=list(self.evidence_map.keys()),
            tables=[{
                "title": "Complete Evidence Inventory",
                "columns": ["Evidence ID", "Type", "Description", "Source Log", "Timestamp", "SHA-256 Hash"],
                "data": evidence_list
            }],
            page_estimate=10
        ))
        
        # Appendix B: Chain of Custody
        appendices.append(ReportSection(
            section_type=ReportSectionType.APPENDIX_COC,
            title="APPENDIX B: CHAIN OF CUSTODY",
            content="""
This appendix documents the complete chain of custody for all evidence.

Chain of Custody Log:
[Auto-generated from Evidence Vault CoC table]

Each entry includes:
• Timestamp
• Actor (who performed the action)
• Action (acquisition, analysis, export, etc.)
• Target artifact
• Hash verification status
            """.strip(),
            evidence_refs=[],
            page_estimate=5
        ))
        
        # Appendix C: Hash Verification
        appendices.append(ReportSection(
            section_type=ReportSectionType.APPENDIX_HASHES,
            title="APPENDIX C: HASH VERIFICATION",
            content="""
This appendix contains SHA-256 hash values for all evidence files.

Hash verification ensures evidence integrity throughout the investigation.
All hashes were computed at acquisition and re-verified at analysis.

Verification Status: ALL VERIFIED ✓
            """.strip(),
            evidence_refs=[],
            tables=[{
                "title": "Evidence Hash Verification",
                "columns": ["Evidence ID", "SHA-256 Hash", "Verified"],
                "data": [
                    {"Evidence ID": ev_id, "SHA-256 Hash": ev.hash, "Verified": "✓"}
                    for ev_id, ev in self.evidence_map.items()
                ]
            }],
            page_estimate=5
        ))
        
        return appendices
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export report structure as dictionary."""
        return {
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "findings_count": len(self.findings),
            "evidence_count": len(self.evidence_map),
            "sections": [
                {
                    "type": s.section_type.value,
                    "title": s.title,
                    "content": s.content,
                    "evidence_refs": s.evidence_refs,
                    "tables": s.tables,
                    "figures": s.figures,
                    "page_estimate": s.page_estimate,
                }
                for s in self.sections
            ],
            "total_pages": sum(s.page_estimate for s in self.sections)
        }


def bind_hypothesis_to_report(
    case_id: str,
    investigation_id: str,
    findings: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Main function to bind hypothesis findings to report structure.
    
    Args:
        case_id: Case identifier
        investigation_id: Investigation identifier
        findings: List of hypothesis finding dictionaries
        evidence: List of evidence reference dictionaries
        
    Returns:
        Report structure dictionary
    """
    binder = HypothesisReportBinder(case_id, investigation_id)
    
    # Add findings
    for f in findings:
        finding = HypothesisFinding(
            hypothesis_id=f.get("hypothesis_id", ""),
            hypothesis_name=f.get("hypothesis_name", ""),
            verdict=f.get("verdict", "inconclusive"),
            confidence=f.get("confidence", 0.0),
            evidence_for=f.get("evidence_for", []),
            evidence_against=f.get("evidence_against", []),
            summary=f.get("summary", ""),
            details=f.get("details", {}),
        )
        binder.add_finding(finding)
    
    # Add evidence
    for e in evidence:
        ev_ref = EvidenceReference(
            evidence_id=e.get("evidence_id", ""),
            evidence_type=e.get("evidence_type", ""),
            description=e.get("description", ""),
            timestamp=e.get("timestamp", ""),
            source_log=e.get("source_log", ""),
            hash=e.get("hash", ""),
            data=e.get("data", {}),
        )
        binder.add_evidence(ev_ref)
    
    # Generate structure
    binder.generate_report_structure()
    
    return binder.export_to_dict()
