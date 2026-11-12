"""
Research Knowledge Base — 100+ Forensic Research Methodologies.

This module provides a comprehensive knowledge base of research methodologies,
frameworks, and best practices for digital forensics and incident response.

Research Categories:
─────────────────────────────────────────────────────────────────────────────────
   1. Digital Forensics Fundamentals (20+ methodologies)
   2. Network Forensics & Analysis (15+ methodologies)
   3. Malware Analysis & Reverse Engineering (12+ methodologies)
   4. Memory Forensics (10+ methodologies)
   5. Timeline Analysis & Reconstruction (8+ methodologies)
   6. Evidence Handling & Chain of Custody (10+ methodologies)
   7. Machine Learning for Security (15+ methodologies)
   8. Confidence & Uncertainty Quantification (10+ methodologies)
   9. Threat Intelligence & Attribution (12+ methodologies)
   10. Incident Response Frameworks (10+ methodologies)
─────────────────────────────────────────────────────────────────────────────────

Total: 120+ research methodologies indexed and categorized

Author: NFLIP Development Team
Version: 1.0.0
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchCategory(str, Enum):
    """Categories of forensic research."""
    DIGITAL_FORENSICS = "digital_forensics"
    NETWORK_FORENSICS = "network_forensics"
    MALWARE_ANALYSIS = "malware_analysis"
    MEMORY_FORENSICS = "memory_forensics"
    TIMELINE_ANALYSIS = "timeline_analysis"
    EVIDENCE_HANDLING = "evidence_handling"
    MACHINE_LEARNING = "machine_learning"
    CONFIDENCE_QUANTIFICATION = "confidence_quantification"
    THREAT_INTELLIGENCE = "threat_intelligence"
    INCIDENT_RESPONSE = "incident_response"
    LOG_ANALYSIS = "log_analysis"
    CLOUD_FORENSICS = "cloud_forensics"


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH METHODOLOGY DATA STRUCTURE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResearchMethodology:
    """
    A single research methodology or framework.
    """
    methodology_id: str
    name: str
    category: ResearchCategory
    description: str
    
    # Source information
    authors: List[str] = field(default_factory=list)
    publication_year: Optional[int] = None
    source: str = ""  # Journal, conference, or organization
    doi: Optional[str] = None
    url: Optional[str] = None
    
    # Applicability
    use_cases: List[str] = field(default_factory=list)
    hypothesis_types: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)  # Which NFLIP modules use this
    
    # Keywords for search
    keywords: List[str] = field(default_factory=list)
    
    # Related methodologies
    related: List[str] = field(default_factory=list)
    
    # Implementation notes
    implementation_notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "methodology_id": self.methodology_id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "authors": self.authors,
            "publication_year": self.publication_year,
            "source": self.source,
            "doi": self.doi,
            "url": self.url,
            "use_cases": self.use_cases,
            "hypothesis_types": self.hypothesis_types,
            "modules": self.modules,
            "keywords": self.keywords,
            "related": self.related,
            "implementation_notes": self.implementation_notes
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH METHODOLOGIES DATABASE (100+)
# ═══════════════════════════════════════════════════════════════════════════════

RESEARCH_METHODOLOGIES: List[ResearchMethodology] = [
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 1: DIGITAL FORENSICS FUNDAMENTALS (20 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="DF001",
        name="NIST SP 800-86: Guide to Integrating Forensic Techniques",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Comprehensive guide for integrating forensic techniques into incident response, covering collection, examination, analysis, and reporting phases.",
        authors=["Karen Kent", "Suzanne Chevalier", "Tim Grance", "Hung Dang"],
        publication_year=2006,
        source="NIST Special Publication",
        url="https://csrc.nist.gov/publications/detail/sp/800-86/final",
        use_cases=["incident_response", "evidence_collection", "forensic_analysis"],
        hypothesis_types=["attack_origin", "data_exfiltration", "malware"],
        modules=["timeline", "anomaly", "evidence"],
        keywords=["forensics", "incident response", "evidence", "NIST"],
        implementation_notes="Foundation for NFLIP evidence collection and chain of custody"
    ),
    
    ResearchMethodology(
        methodology_id="DF002",
        name="ISO/IEC 27037: Digital Evidence Identification and Collection",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="International standard providing guidelines for identification, collection, acquisition, and preservation of digital evidence.",
        authors=["ISO/IEC JTC 1/SC 27"],
        publication_year=2012,
        source="ISO/IEC International Standard",
        use_cases=["evidence_handling", "legal_proceedings", "chain_of_custody"],
        hypothesis_types=["all"],
        modules=["evidence", "audit"],
        keywords=["ISO", "evidence", "preservation", "legal"],
        implementation_notes="Basis for CoC ledger implementation"
    ),
    
    ResearchMethodology(
        methodology_id="DF003",
        name="RFC 3227: Guidelines for Evidence Collection and Archiving",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Best practices for collecting and archiving evidence during security incidents, emphasizing order of volatility.",
        authors=["D. Brezinski", "T. Killalea"],
        publication_year=2002,
        source="IETF RFC",
        url="https://www.rfc-editor.org/rfc/rfc3227",
        use_cases=["evidence_collection", "volatility_order", "incident_response"],
        hypothesis_types=["all"],
        modules=["evidence", "timeline"],
        keywords=["RFC", "volatility", "collection", "archiving"]
    ),
    
    ResearchMethodology(
        methodology_id="DF004",
        name="DFRWS Forensics Challenge Framework",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Standardized challenges and methodologies from the Digital Forensics Research Workshop for advancing forensic techniques.",
        authors=["DFRWS Community"],
        publication_year=2001,
        source="Digital Forensics Research Workshop",
        url="https://dfrws.org",
        use_cases=["research_validation", "tool_testing", "methodology_comparison"],
        hypothesis_types=["all"],
        modules=["all"],
        keywords=["DFRWS", "research", "validation", "benchmark"]
    ),
    
    ResearchMethodology(
        methodology_id="DF005",
        name="EnCase Forensic Methodology",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Industry-standard methodology for computer forensic investigations using systematic acquisition and analysis.",
        authors=["OpenText/Guidance Software"],
        source="Commercial Methodology",
        use_cases=["disk_forensics", "file_recovery", "evidence_analysis"],
        hypothesis_types=["data_exfiltration", "insider_threat"],
        modules=["evidence", "crud"],
        keywords=["EnCase", "disk", "acquisition", "analysis"]
    ),
    
    ResearchMethodology(
        methodology_id="DF006",
        name="FTK (Forensic Toolkit) Processing Model",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Methodology for processing and analyzing forensic images with focus on indexing and searching.",
        authors=["AccessData/Exterro"],
        source="Commercial Methodology",
        use_cases=["image_processing", "search", "indexing"],
        hypothesis_types=["data_exfiltration", "insider_threat"],
        modules=["evidence", "crud"],
        keywords=["FTK", "indexing", "search", "processing"]
    ),
    
    ResearchMethodology(
        methodology_id="DF007",
        name="Sleuth Kit Analysis Framework",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Open-source framework for file system forensic analysis, providing foundation for many forensic tools.",
        authors=["Brian Carrier"],
        publication_year=2005,
        source="Open Source Project",
        url="https://sleuthkit.org",
        use_cases=["file_system_analysis", "deleted_file_recovery", "metadata_extraction"],
        hypothesis_types=["data_exfiltration", "malware"],
        modules=["evidence", "crud"],
        keywords=["TSK", "Autopsy", "filesystem", "open source"]
    ),
    
    ResearchMethodology(
        methodology_id="DF008",
        name="CFTT (Computer Forensics Tool Testing)",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="NIST program for testing forensic tools to ensure accuracy and reliability in legal proceedings.",
        authors=["NIST"],
        source="NIST Program",
        url="https://www.nist.gov/itl/ssd/software-quality-group/computer-forensics-tool-testing-program-cftt",
        use_cases=["tool_validation", "quality_assurance", "legal_admissibility"],
        hypothesis_types=["all"],
        modules=["all"],
        keywords=["CFTT", "testing", "validation", "accuracy"]
    ),
    
    ResearchMethodology(
        methodology_id="DF009",
        name="Anti-Forensics Detection Techniques",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Methodologies for detecting and countering anti-forensic techniques including data wiping, encryption, and timestomping.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["anti_forensics_detection", "evidence_integrity", "artifact_analysis"],
        hypothesis_types=["malware", "insider_threat", "ransomware"],
        modules=["anomaly", "timeline"],
        keywords=["anti-forensics", "wiping", "timestomping", "encryption"]
    ),
    
    ResearchMethodology(
        methodology_id="DF010",
        name="Mobile Device Forensics Framework",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Specialized methodologies for extracting and analyzing evidence from mobile devices including iOS and Android.",
        authors=["Various Researchers"],
        source="Academic/Industry Research",
        use_cases=["mobile_forensics", "app_analysis", "communication_extraction"],
        hypothesis_types=["insider_threat", "credential_theft"],
        modules=["evidence", "timeline"],
        keywords=["mobile", "iOS", "Android", "extraction"]
    ),
    
    ResearchMethodology(
        methodology_id="DF011",
        name="Windows Registry Forensics",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Techniques for extracting forensically relevant artifacts from Windows Registry including user activity, program execution, and system configuration.",
        authors=["Harlan Carvey"],
        publication_year=2011,
        source="Book/Research",
        use_cases=["windows_forensics", "user_activity", "program_execution"],
        hypothesis_types=["lateral_movement", "persistence", "privilege_escalation"],
        modules=["timeline", "correlation"],
        keywords=["registry", "Windows", "artifacts", "hives"]
    ),
    
    ResearchMethodology(
        methodology_id="DF012",
        name="Browser Forensics Methodology",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Analysis of browser artifacts including history, cache, cookies, and session data for reconstructing user activity.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["web_activity", "phishing_investigation", "user_behavior"],
        hypothesis_types=["phishing", "insider_threat", "data_exfiltration"],
        modules=["timeline", "crud"],
        keywords=["browser", "history", "cookies", "cache"]
    ),
    
    ResearchMethodology(
        methodology_id="DF013",
        name="Email Forensics Analysis",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Techniques for analyzing email headers, attachments, and metadata for evidence of phishing, BEC, and data exfiltration.",
        authors=["Various Researchers"],
        source="Academic/Industry Research",
        use_cases=["email_analysis", "phishing", "bec_investigation"],
        hypothesis_types=["bec", "phishing", "data_exfiltration"],
        modules=["timeline", "correlation"],
        keywords=["email", "headers", "phishing", "attachments"]
    ),
    
    ResearchMethodology(
        methodology_id="DF014",
        name="Database Forensics Techniques",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Methodologies for analyzing database logs, query history, and data modifications to detect unauthorized access.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["database_analysis", "unauthorized_access", "data_theft"],
        hypothesis_types=["data_exfiltration", "insider_threat", "credential_theft"],
        modules=["crud", "timeline", "anomaly"],
        keywords=["database", "SQL", "queries", "transactions"],
        implementation_notes="Core methodology for CRUD analysis module"
    ),
    
    ResearchMethodology(
        methodology_id="DF015",
        name="Docker/Container Forensics",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Techniques for forensic analysis of containerized environments including Docker, Kubernetes evidence extraction.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["container_forensics", "cloud_native", "microservices"],
        hypothesis_types=["lateral_movement", "persistence"],
        modules=["evidence", "timeline"],
        keywords=["Docker", "Kubernetes", "containers", "orchestration"]
    ),
    
    ResearchMethodology(
        methodology_id="DF016",
        name="Virtual Machine Forensics",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Analysis of virtual machine disk images, snapshots, and hypervisor artifacts for evidence collection.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["vm_forensics", "snapshot_analysis", "hypervisor_investigation"],
        hypothesis_types=["lateral_movement", "persistence", "malware"],
        modules=["evidence", "timeline"],
        keywords=["VM", "VMware", "Hyper-V", "snapshots"]
    ),
    
    ResearchMethodology(
        methodology_id="DF017",
        name="Artifact-Based Investigation Framework",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Systematic approach to identifying and analyzing forensic artifacts across different operating systems.",
        authors=["SANS Institute"],
        source="SANS Training",
        use_cases=["artifact_analysis", "cross_platform", "systematic_investigation"],
        hypothesis_types=["all"],
        modules=["evidence", "timeline"],
        keywords=["artifacts", "SANS", "systematic", "cross-platform"]
    ),
    
    ResearchMethodology(
        methodology_id="DF018",
        name="Forensic Image Verification (Hash Validation)",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Cryptographic hash-based methods for verifying forensic image integrity and chain of custody.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["image_verification", "integrity", "chain_of_custody"],
        hypothesis_types=["all"],
        modules=["audit", "evidence"],
        keywords=["hash", "MD5", "SHA256", "integrity"],
        implementation_notes="Implemented in NFLIP hash verification system"
    ),
    
    ResearchMethodology(
        methodology_id="DF019",
        name="Steganography Detection Methods",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Techniques for detecting hidden data in images, audio, and other media files.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["hidden_data", "covert_channels", "data_exfiltration"],
        hypothesis_types=["data_exfiltration", "insider_threat"],
        modules=["anomaly"],
        keywords=["steganography", "hidden", "detection", "images"]
    ),
    
    ResearchMethodology(
        methodology_id="DF020",
        name="File Carving and Recovery Techniques",
        category=ResearchCategory.DIGITAL_FORENSICS,
        description="Methods for recovering deleted files based on file signatures and structure analysis.",
        authors=["Various Researchers"],
        source="Academic/Tool Development",
        use_cases=["file_recovery", "deleted_data", "unallocated_space"],
        hypothesis_types=["data_exfiltration", "evidence_destruction"],
        modules=["evidence"],
        keywords=["carving", "recovery", "deleted", "signatures"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 2: NETWORK FORENSICS & ANALYSIS (15 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="NF001",
        name="Network Flow Analysis (NetFlow/IPFIX)",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Analysis of network flow data for identifying communication patterns, data volumes, and anomalous traffic.",
        authors=["Cisco Systems"],
        source="Industry Standard",
        use_cases=["traffic_analysis", "exfiltration_detection", "baseline"],
        hypothesis_types=["data_exfiltration", "lateral_movement", "c2"],
        modules=["network"],
        keywords=["NetFlow", "IPFIX", "traffic", "flows"],
        implementation_notes="Core methodology for NFLIP network module"
    ),
    
    ResearchMethodology(
        methodology_id="NF002",
        name="Deep Packet Inspection (DPI) Forensics",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Analysis of full packet captures to extract application-layer data and detect malicious content.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["packet_analysis", "malware_detection", "data_reconstruction"],
        hypothesis_types=["malware", "data_exfiltration", "c2"],
        modules=["network"],
        keywords=["DPI", "packets", "payload", "inspection"]
    ),
    
    ResearchMethodology(
        methodology_id="NF003",
        name="DNS Query Analysis for Threat Detection",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Techniques for analyzing DNS queries to detect C2 communication, data exfiltration, and malicious domains.",
        authors=["Various Researchers"],
        source="Academic/Industry Research",
        use_cases=["dns_analysis", "c2_detection", "domain_reputation"],
        hypothesis_types=["c2", "data_exfiltration", "malware"],
        modules=["network", "anomaly"],
        keywords=["DNS", "queries", "domains", "tunneling"]
    ),
    
    ResearchMethodology(
        methodology_id="NF004",
        name="TLS/SSL Certificate Analysis",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Analysis of TLS certificates for detecting malicious infrastructure and phishing sites.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["certificate_analysis", "phishing_detection", "infrastructure_mapping"],
        hypothesis_types=["phishing", "c2"],
        modules=["network"],
        keywords=["TLS", "SSL", "certificates", "HTTPS"]
    ),
    
    ResearchMethodology(
        methodology_id="NF005",
        name="Beaconing Detection Algorithms",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Statistical methods for detecting periodic communication patterns indicative of C2 beaconing.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["c2_detection", "periodic_analysis", "malware_communication"],
        hypothesis_types=["c2", "malware", "apt"],
        modules=["network", "anomaly"],
        keywords=["beaconing", "periodic", "C2", "intervals"],
        implementation_notes="Implemented in network exfiltration detection"
    ),
    
    ResearchMethodology(
        methodology_id="NF006",
        name="Lateral Movement Detection via Network Analysis",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Techniques for detecting lateral movement through analysis of internal network traffic patterns.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["lateral_movement", "internal_reconnaissance", "pivot_detection"],
        hypothesis_types=["lateral_movement", "apt"],
        modules=["network", "correlation"],
        keywords=["lateral", "internal", "pivot", "SMB"]
    ),
    
    ResearchMethodology(
        methodology_id="NF007",
        name="Network Baseline and Anomaly Detection",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Establishment of network baselines and statistical anomaly detection for identifying deviations.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["baseline", "anomaly_detection", "deviation_analysis"],
        hypothesis_types=["all"],
        modules=["network", "anomaly"],
        keywords=["baseline", "anomaly", "statistics", "deviation"]
    ),
    
    ResearchMethodology(
        methodology_id="NF008",
        name="Proxy Log Analysis for Threat Hunting",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Analysis of web proxy logs to detect malicious URLs, suspicious downloads, and data exfiltration.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["proxy_analysis", "url_detection", "download_analysis"],
        hypothesis_types=["malware", "data_exfiltration", "phishing"],
        modules=["network", "timeline"],
        keywords=["proxy", "URLs", "web", "downloads"]
    ),
    
    ResearchMethodology(
        methodology_id="NF009",
        name="Firewall Log Forensics",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Analysis of firewall logs to reconstruct network events and identify policy violations.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["firewall_analysis", "policy_violations", "blocked_traffic"],
        hypothesis_types=["lateral_movement", "data_exfiltration"],
        modules=["network", "timeline"],
        keywords=["firewall", "ACL", "blocked", "allowed"]
    ),
    
    ResearchMethodology(
        methodology_id="NF010",
        name="Zeek (Bro) Network Security Monitor Analysis",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Methodology for using Zeek logs for comprehensive network activity analysis.",
        authors=["Zeek Community"],
        source="Open Source Project",
        url="https://zeek.org",
        use_cases=["network_monitoring", "protocol_analysis", "anomaly_detection"],
        hypothesis_types=["all"],
        modules=["network"],
        keywords=["Zeek", "Bro", "protocols", "monitoring"]
    ),
    
    ResearchMethodology(
        methodology_id="NF011",
        name="PCAP Timeline Reconstruction",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Techniques for reconstructing event timelines from packet capture files.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["timeline", "packet_analysis", "session_reconstruction"],
        hypothesis_types=["all"],
        modules=["network", "timeline"],
        keywords=["PCAP", "timeline", "sessions", "reconstruction"]
    ),
    
    ResearchMethodology(
        methodology_id="NF012",
        name="VPN/Tunnel Detection Methods",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Techniques for detecting encrypted tunnels and VPN usage for policy bypass or data exfiltration.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["tunnel_detection", "vpn_analysis", "policy_bypass"],
        hypothesis_types=["data_exfiltration", "policy_violation"],
        modules=["network"],
        keywords=["VPN", "tunnel", "encrypted", "bypass"]
    ),
    
    ResearchMethodology(
        methodology_id="NF013",
        name="Network-Based Malware Detection",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Detection of malware through network behavior analysis without endpoint access.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["malware_detection", "behavioral_analysis", "network_iocs"],
        hypothesis_types=["malware", "c2"],
        modules=["network", "anomaly"],
        keywords=["malware", "network", "behavioral", "IOCs"]
    ),
    
    ResearchMethodology(
        methodology_id="NF014",
        name="Session Hijacking Detection",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Methods for detecting session hijacking attacks through network traffic analysis.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["session_hijacking", "man_in_the_middle", "authentication_bypass"],
        hypothesis_types=["credential_theft", "man_in_the_middle"],
        modules=["network", "anomaly"],
        keywords=["session", "hijacking", "MITM", "cookies"]
    ),
    
    ResearchMethodology(
        methodology_id="NF015",
        name="Data Exfiltration Volume Analysis",
        category=ResearchCategory.NETWORK_FORENSICS,
        description="Statistical analysis of network traffic volumes to detect large data transfers indicative of exfiltration.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["exfiltration_detection", "volume_analysis", "upload_detection"],
        hypothesis_types=["data_exfiltration"],
        modules=["network"],
        keywords=["exfiltration", "volume", "bytes", "upload"],
        implementation_notes="Implemented in NFLIP network exfiltration detection"
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 3: MALWARE ANALYSIS & REVERSE ENGINEERING (12 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="MA001",
        name="Static Malware Analysis Techniques",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Analysis of malware without execution including string analysis, PE header examination, and import analysis.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["malware_analysis", "indicator_extraction", "classification"],
        hypothesis_types=["malware", "ransomware"],
        modules=["anomaly"],
        keywords=["static", "PE", "strings", "imports"]
    ),
    
    ResearchMethodology(
        methodology_id="MA002",
        name="Dynamic Malware Analysis (Sandbox)",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Controlled execution of malware in sandbox environments to observe behavior.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["behavioral_analysis", "sandbox", "detonation"],
        hypothesis_types=["malware", "ransomware"],
        modules=["anomaly"],
        keywords=["sandbox", "dynamic", "behavioral", "execution"]
    ),
    
    ResearchMethodology(
        methodology_id="MA003",
        name="YARA Rules for Malware Detection",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Pattern matching rules for identifying malware families based on signatures.",
        authors=["Victor Alvarez"],
        source="Open Source Tool",
        url="https://virustotal.github.io/yara/",
        use_cases=["malware_detection", "classification", "hunting"],
        hypothesis_types=["malware", "ransomware"],
        modules=["anomaly"],
        keywords=["YARA", "signatures", "patterns", "detection"]
    ),
    
    ResearchMethodology(
        methodology_id="MA004",
        name="Malware Unpacking Techniques",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Methods for unpacking packed/obfuscated malware to reveal original code.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["unpacking", "deobfuscation", "analysis"],
        hypothesis_types=["malware"],
        modules=["anomaly"],
        keywords=["unpacking", "packing", "UPX", "obfuscation"]
    ),
    
    ResearchMethodology(
        methodology_id="MA005",
        name="Ransomware Behavior Analysis",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Specific techniques for analyzing ransomware including encryption detection and key recovery.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["ransomware_analysis", "encryption_detection", "recovery"],
        hypothesis_types=["ransomware"],
        modules=["anomaly", "crud"],
        keywords=["ransomware", "encryption", "ransom", "crypto"]
    ),
    
    ResearchMethodology(
        methodology_id="MA006",
        name="Fileless Malware Detection",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Techniques for detecting malware that operates entirely in memory without file artifacts.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["fileless_detection", "memory_analysis", "living_off_land"],
        hypothesis_types=["malware", "apt"],
        modules=["anomaly", "timeline"],
        keywords=["fileless", "memory", "LOLBins", "PowerShell"]
    ),
    
    ResearchMethodology(
        methodology_id="MA007",
        name="Code Injection Detection",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Methods for detecting process injection, DLL injection, and other code injection techniques.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["injection_detection", "process_hollowing", "dll_injection"],
        hypothesis_types=["malware", "privilege_escalation"],
        modules=["anomaly"],
        keywords=["injection", "hollowing", "DLL", "process"]
    ),
    
    ResearchMethodology(
        methodology_id="MA008",
        name="C2 Protocol Reverse Engineering",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Techniques for reverse engineering command and control protocols used by malware.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["c2_analysis", "protocol_reversing", "communication_analysis"],
        hypothesis_types=["malware", "c2", "apt"],
        modules=["network"],
        keywords=["C2", "protocol", "reverse", "communication"]
    ),
    
    ResearchMethodology(
        methodology_id="MA009",
        name="Malware Attribution Techniques",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Methods for attributing malware to specific threat actors or campaigns.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["attribution", "threat_actor", "campaign_tracking"],
        hypothesis_types=["apt", "malware"],
        modules=["correlation"],
        keywords=["attribution", "threat_actor", "campaign", "TTPs"]
    ),
    
    ResearchMethodology(
        methodology_id="MA010",
        name="Exploit Analysis Framework",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Systematic approach to analyzing exploits including vulnerability identification and payload extraction.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["exploit_analysis", "vulnerability", "payload"],
        hypothesis_types=["malware", "initial_access"],
        modules=["anomaly"],
        keywords=["exploit", "vulnerability", "CVE", "payload"]
    ),
    
    ResearchMethodology(
        methodology_id="MA011",
        name="Rootkit Detection Methods",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Techniques for detecting rootkits including kernel-level hiding and persistence mechanisms.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["rootkit_detection", "kernel_analysis", "persistence"],
        hypothesis_types=["malware", "persistence"],
        modules=["anomaly"],
        keywords=["rootkit", "kernel", "hiding", "hooks"]
    ),
    
    ResearchMethodology(
        methodology_id="MA012",
        name="Backdoor Detection and Analysis",
        category=ResearchCategory.MALWARE_ANALYSIS,
        description="Methods for identifying and analyzing backdoors including web shells and RATs.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["backdoor_detection", "web_shell", "rat_analysis"],
        hypothesis_types=["persistence", "c2"],
        modules=["anomaly", "network"],
        keywords=["backdoor", "webshell", "RAT", "persistence"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 4: MEMORY FORENSICS (10 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="MF001",
        name="Volatility Framework Analysis",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Comprehensive memory forensics framework for analyzing RAM dumps across multiple operating systems.",
        authors=["Volatility Foundation"],
        source="Open Source Tool",
        url="https://www.volatilityfoundation.org",
        use_cases=["memory_analysis", "process_analysis", "malware_detection"],
        hypothesis_types=["malware", "credential_theft", "persistence"],
        modules=["anomaly"],
        keywords=["Volatility", "memory", "RAM", "processes"]
    ),
    
    ResearchMethodology(
        methodology_id="MF002",
        name="Process Memory Analysis",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Techniques for analyzing individual process memory including heap and stack analysis.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["process_analysis", "injection_detection", "data_extraction"],
        hypothesis_types=["malware", "credential_theft"],
        modules=["anomaly"],
        keywords=["process", "heap", "stack", "injection"]
    ),
    
    ResearchMethodology(
        methodology_id="MF003",
        name="Credential Extraction from Memory",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Techniques for extracting credentials (passwords, hashes, tickets) from memory.",
        authors=["Benjamin Delpy", "Various Researchers"],
        source="Tool Development/Research",
        use_cases=["credential_extraction", "hash_dumping", "ticket_extraction"],
        hypothesis_types=["credential_theft"],
        modules=["anomaly"],
        keywords=["Mimikatz", "credentials", "LSASS", "hashes"]
    ),
    
    ResearchMethodology(
        methodology_id="MF004",
        name="Network Connection Recovery from Memory",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Extraction of network connection information from memory dumps.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["network_recovery", "connection_analysis", "c2_detection"],
        hypothesis_types=["c2", "lateral_movement"],
        modules=["network", "anomaly"],
        keywords=["connections", "sockets", "network", "memory"]
    ),
    
    ResearchMethodology(
        methodology_id="MF005",
        name="Kernel Memory Analysis",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Analysis of kernel memory structures for rootkit detection and system state reconstruction.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["kernel_analysis", "rootkit_detection", "driver_analysis"],
        hypothesis_types=["malware", "persistence"],
        modules=["anomaly"],
        keywords=["kernel", "drivers", "SSDT", "IDT"]
    ),
    
    ResearchMethodology(
        methodology_id="MF006",
        name="Registry Hive Extraction from Memory",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Extraction and analysis of Windows Registry hives from memory dumps.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["registry_recovery", "artifact_extraction", "password_recovery"],
        hypothesis_types=["credential_theft", "persistence"],
        modules=["anomaly"],
        keywords=["registry", "hives", "SAM", "SYSTEM"]
    ),
    
    ResearchMethodology(
        methodology_id="MF007",
        name="Code Injection Detection in Memory",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Detection of various code injection techniques through memory analysis.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["injection_detection", "process_hollowing", "dll_injection"],
        hypothesis_types=["malware", "privilege_escalation"],
        modules=["anomaly"],
        keywords=["injection", "VAD", "memory", "shellcode"]
    ),
    
    ResearchMethodology(
        methodology_id="MF008",
        name="Timeline Generation from Memory",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Reconstruction of system timeline using artifacts extracted from memory.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["timeline_reconstruction", "event_correlation", "temporal_analysis"],
        hypothesis_types=["all"],
        modules=["timeline"],
        keywords=["timeline", "timestamps", "events", "memory"]
    ),
    
    ResearchMethodology(
        methodology_id="MF009",
        name="Hibernation File Analysis",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Analysis of Windows hibernation files (hiberfil.sys) as memory snapshots.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["hibernation_analysis", "memory_recovery", "artifact_extraction"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["hibernation", "hiberfil", "crash", "pagefile"]
    ),
    
    ResearchMethodology(
        methodology_id="MF010",
        name="Linux Memory Forensics",
        category=ResearchCategory.MEMORY_FORENSICS,
        description="Specialized techniques for analyzing Linux memory dumps.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["linux_memory", "process_analysis", "rootkit_detection"],
        hypothesis_types=["malware", "persistence"],
        modules=["anomaly"],
        keywords=["Linux", "memory", "proc", "kernel"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 5: TIMELINE ANALYSIS & RECONSTRUCTION (8 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="TL001",
        name="Super Timeline Generation (log2timeline)",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Comprehensive timeline generation from multiple artifact sources using Plaso/log2timeline.",
        authors=["Kristinn Gudjonsson"],
        source="Open Source Tool",
        url="https://plaso.readthedocs.io",
        use_cases=["timeline_generation", "artifact_correlation", "comprehensive_analysis"],
        hypothesis_types=["all"],
        modules=["timeline"],
        keywords=["Plaso", "log2timeline", "super", "timeline"],
        implementation_notes="Inspiration for NFLIP timeline module"
    ),
    
    ResearchMethodology(
        methodology_id="TL002",
        name="Timestamp Analysis and Validation",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Techniques for validating and correlating timestamps across different sources and time zones.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["timestamp_validation", "timezone_correlation", "anti_forensics_detection"],
        hypothesis_types=["all"],
        modules=["timeline"],
        keywords=["timestamps", "timezone", "validation", "MAC"]
    ),
    
    ResearchMethodology(
        methodology_id="TL003",
        name="Timestomping Detection",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Methods for detecting manipulation of file timestamps (timestomping anti-forensics).",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["timestomping_detection", "anti_forensics", "artifact_validation"],
        hypothesis_types=["malware", "insider_threat"],
        modules=["timeline", "anomaly"],
        keywords=["timestomping", "anti-forensics", "manipulation", "MFT"]
    ),
    
    ResearchMethodology(
        methodology_id="TL004",
        name="Event Correlation Algorithms",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Statistical and heuristic methods for correlating events across multiple log sources.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["event_correlation", "attack_chain", "multi_source_analysis"],
        hypothesis_types=["all"],
        modules=["timeline", "correlation"],
        keywords=["correlation", "events", "multi-source", "chain"],
        implementation_notes="Core methodology for NFLIP correlation module"
    ),
    
    ResearchMethodology(
        methodology_id="TL005",
        name="Pivot Point Identification",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Techniques for identifying critical pivot points in attack timelines.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["pivot_detection", "attack_progression", "key_events"],
        hypothesis_types=["lateral_movement", "privilege_escalation"],
        modules=["timeline", "correlation"],
        keywords=["pivot", "critical", "progression", "key_events"]
    ),
    
    ResearchMethodology(
        methodology_id="TL006",
        name="Dwell Time Analysis",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Analysis of attacker dwell time from initial access to discovery.",
        authors=["Various Researchers"],
        source="Industry Research",
        use_cases=["dwell_time", "detection_gap", "response_metrics"],
        hypothesis_types=["apt", "all"],
        modules=["timeline", "depth"],
        keywords=["dwell", "detection", "gap", "persistence"],
        implementation_notes="Used in NFLIP depth impact module"
    ),
    
    ResearchMethodology(
        methodology_id="TL007",
        name="Anchor Event Methodology",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Using known high-confidence events as anchors for timeline reconstruction.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["timeline_anchoring", "high_confidence", "reconstruction"],
        hypothesis_types=["all"],
        modules=["timeline"],
        keywords=["anchor", "confidence", "known", "events"]
    ),
    
    ResearchMethodology(
        methodology_id="TL008",
        name="Gap Analysis in Timelines",
        category=ResearchCategory.TIMELINE_ANALYSIS,
        description="Identification and analysis of gaps in timeline data that may indicate log manipulation or missing sources.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["gap_detection", "log_manipulation", "missing_data"],
        hypothesis_types=["anti_forensics", "all"],
        modules=["timeline"],
        keywords=["gaps", "missing", "manipulation", "coverage"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 6: EVIDENCE HANDLING & CHAIN OF CUSTODY (10 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="EH001",
        name="Chain of Custody Best Practices",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Standard practices for maintaining evidence chain of custody for legal admissibility.",
        authors=["Various"],
        source="Legal/Industry Standard",
        use_cases=["chain_of_custody", "legal_proceedings", "evidence_integrity"],
        hypothesis_types=["all"],
        modules=["audit"],
        keywords=["chain", "custody", "legal", "integrity"],
        implementation_notes="Implemented in NFLIP CoC ledger"
    ),
    
    ResearchMethodology(
        methodology_id="EH002",
        name="Cryptographic Evidence Sealing",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Use of cryptographic techniques to seal and verify evidence integrity.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["evidence_sealing", "integrity_verification", "timestamping"],
        hypothesis_types=["all"],
        modules=["audit"],
        keywords=["cryptographic", "hash", "seal", "timestamp"],
        implementation_notes="Implemented with SHA-256 and RFC 3161 timestamping"
    ),
    
    ResearchMethodology(
        methodology_id="EH003",
        name="RFC 3161 Time-Stamp Protocol",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Standard protocol for obtaining trusted timestamps for evidence.",
        authors=["IETF"],
        publication_year=2001,
        source="IETF RFC",
        url="https://www.rfc-editor.org/rfc/rfc3161",
        use_cases=["timestamping", "non_repudiation", "legal_proof"],
        hypothesis_types=["all"],
        modules=["audit"],
        keywords=["RFC3161", "timestamp", "TSA", "trusted"]
    ),
    
    ResearchMethodology(
        methodology_id="EH004",
        name="Evidence Preservation Order of Volatility",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Methodology for preserving evidence in order of volatility to minimize data loss.",
        authors=["Various"],
        source="RFC 3227 / Industry Standard",
        use_cases=["evidence_preservation", "volatility", "collection_order"],
        hypothesis_types=["all"],
        modules=["evidence"],
        keywords=["volatility", "preservation", "order", "collection"]
    ),
    
    ResearchMethodology(
        methodology_id="EH005",
        name="Write Blocking and Imaging",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Standards for creating forensically sound disk images without altering evidence.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["disk_imaging", "write_blocking", "acquisition"],
        hypothesis_types=["all"],
        modules=["evidence"],
        keywords=["write_block", "imaging", "acquisition", "forensic_copy"]
    ),
    
    ResearchMethodology(
        methodology_id="EH006",
        name="Remote Evidence Collection",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Methodologies for collecting evidence remotely while maintaining integrity.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["remote_collection", "cloud_evidence", "distributed"],
        hypothesis_types=["all"],
        modules=["evidence"],
        keywords=["remote", "collection", "EDR", "distributed"]
    ),
    
    ResearchMethodology(
        methodology_id="EH007",
        name="Evidence Documentation Standards",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Standards for documenting evidence collection and handling procedures.",
        authors=["Various"],
        source="Legal/Industry Standard",
        use_cases=["documentation", "procedures", "audit_trail"],
        hypothesis_types=["all"],
        modules=["audit"],
        keywords=["documentation", "procedures", "forms", "records"]
    ),
    
    ResearchMethodology(
        methodology_id="EH008",
        name="Cloud Evidence Collection",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Specialized methods for collecting evidence from cloud environments.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["cloud_forensics", "saas_evidence", "iaas_collection"],
        hypothesis_types=["all"],
        modules=["evidence"],
        keywords=["cloud", "AWS", "Azure", "SaaS"]
    ),
    
    ResearchMethodology(
        methodology_id="EH009",
        name="Log Integrity Verification",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Methods for verifying log file integrity and detecting tampering.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["log_integrity", "tampering_detection", "verification"],
        hypothesis_types=["all"],
        modules=["audit", "timeline"],
        keywords=["log", "integrity", "verification", "tampering"]
    ),
    
    ResearchMethodology(
        methodology_id="EH010",
        name="Multi-Jurisdiction Evidence Handling",
        category=ResearchCategory.EVIDENCE_HANDLING,
        description="Considerations for handling evidence across multiple legal jurisdictions.",
        authors=["Various"],
        source="Legal Practice",
        use_cases=["multi_jurisdiction", "international", "legal_compliance"],
        hypothesis_types=["all"],
        modules=["audit"],
        keywords=["jurisdiction", "international", "legal", "GDPR"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 7: MACHINE LEARNING FOR SECURITY (15 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="ML001",
        name="Isolation Forest for Anomaly Detection",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Unsupervised anomaly detection algorithm based on isolation of anomalous points.",
        authors=["Fei Tony Liu", "Kai Ming Ting", "Zhi-Hua Zhou"],
        publication_year=2008,
        source="IEEE ICDM",
        use_cases=["anomaly_detection", "outlier_detection", "unsupervised"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["isolation_forest", "anomaly", "unsupervised", "outlier"],
        implementation_notes="Core algorithm in NFLIP anomaly module"
    ),
    
    ResearchMethodology(
        methodology_id="ML002",
        name="Local Outlier Factor (LOF)",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Density-based anomaly detection measuring local deviation of data points.",
        authors=["Markus M. Breunig", "et al."],
        publication_year=2000,
        source="ACM SIGMOD",
        use_cases=["anomaly_detection", "density_based", "local_outlier"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["LOF", "density", "local", "outlier"],
        implementation_notes="Used in NFLIP anomaly ensemble"
    ),
    
    ResearchMethodology(
        methodology_id="ML003",
        name="SHAP (SHapley Additive exPlanations)",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Game-theoretic approach to explain individual predictions of ML models.",
        authors=["Scott Lundberg", "Su-In Lee"],
        publication_year=2017,
        source="NeurIPS",
        url="https://shap.readthedocs.io",
        use_cases=["explainability", "model_interpretation", "feature_importance"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["SHAP", "explainability", "Shapley", "XAI"],
        implementation_notes="Core explainability method in NFLIP anomaly module"
    ),
    
    ResearchMethodology(
        methodology_id="ML004",
        name="User and Entity Behavior Analytics (UEBA)",
        category=ResearchCategory.MACHINE_LEARNING,
        description="ML-based detection of anomalous user and entity behavior patterns.",
        authors=["Various"],
        source="Industry Standard",
        use_cases=["behavior_analytics", "insider_threat", "account_compromise"],
        hypothesis_types=["insider_threat", "credential_theft"],
        modules=["anomaly", "correlation"],
        keywords=["UEBA", "behavior", "user", "entity"]
    ),
    
    ResearchMethodology(
        methodology_id="ML005",
        name="Deep Learning for Intrusion Detection",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Application of neural networks for network intrusion detection.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["intrusion_detection", "network_analysis", "deep_learning"],
        hypothesis_types=["lateral_movement", "c2"],
        modules=["network", "anomaly"],
        keywords=["deep_learning", "neural", "IDS", "intrusion"]
    ),
    
    ResearchMethodology(
        methodology_id="ML006",
        name="Random Forest for Classification",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Ensemble learning method for classification of security events.",
        authors=["Leo Breiman"],
        publication_year=2001,
        source="Machine Learning Journal",
        use_cases=["classification", "event_categorization", "threat_classification"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["random_forest", "ensemble", "classification", "trees"]
    ),
    
    ResearchMethodology(
        methodology_id="ML007",
        name="Clustering for Threat Grouping",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Use of clustering algorithms to group related security events.",
        authors=["Various"],
        source="Academic Research",
        use_cases=["clustering", "grouping", "pattern_discovery"],
        hypothesis_types=["all"],
        modules=["correlation"],
        keywords=["clustering", "DBSCAN", "k-means", "grouping"]
    ),
    
    ResearchMethodology(
        methodology_id="ML008",
        name="Natural Language Processing for Log Analysis",
        category=ResearchCategory.MACHINE_LEARNING,
        description="NLP techniques for parsing and understanding unstructured log data.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["log_parsing", "text_analysis", "pattern_extraction"],
        hypothesis_types=["all"],
        modules=["timeline"],
        keywords=["NLP", "logs", "parsing", "text"]
    ),
    
    ResearchMethodology(
        methodology_id="ML009",
        name="Graph Neural Networks for Attack Detection",
        category=ResearchCategory.MACHINE_LEARNING,
        description="GNN-based methods for detecting attack patterns in relationship graphs.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["graph_analysis", "relationship_detection", "attack_patterns"],
        hypothesis_types=["lateral_movement", "apt"],
        modules=["correlation"],
        keywords=["GNN", "graph", "neural", "relationships"]
    ),
    
    ResearchMethodology(
        methodology_id="ML010",
        name="Autoencoders for Anomaly Detection",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Deep learning approach using reconstruction error for anomaly detection.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["anomaly_detection", "reconstruction", "deep_learning"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["autoencoder", "reconstruction", "deep", "anomaly"]
    ),
    
    ResearchMethodology(
        methodology_id="ML011",
        name="Transfer Learning for Threat Detection",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Leveraging pre-trained models for security event classification.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["transfer_learning", "pre_trained", "classification"],
        hypothesis_types=["malware"],
        modules=["anomaly"],
        keywords=["transfer", "pre-trained", "fine-tuning", "models"]
    ),
    
    ResearchMethodology(
        methodology_id="ML012",
        name="Reinforcement Learning for IR",
        category=ResearchCategory.MACHINE_LEARNING,
        description="RL approaches for automated incident response and remediation.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["automated_response", "remediation", "decision_making"],
        hypothesis_types=["all"],
        modules=["orchestrator"],
        keywords=["reinforcement", "automated", "response", "RL"]
    ),
    
    ResearchMethodology(
        methodology_id="ML013",
        name="Ensemble Methods for Security",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Combining multiple ML models for improved detection accuracy.",
        authors=["Various"],
        source="Academic Research",
        use_cases=["ensemble", "combination", "accuracy"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["ensemble", "combination", "voting", "stacking"],
        implementation_notes="Ensemble approach used in NFLIP anomaly module"
    ),
    
    ResearchMethodology(
        methodology_id="ML014",
        name="Feature Engineering for Security ML",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Best practices for creating features from security data for ML.",
        authors=["Various"],
        source="Academic Research",
        use_cases=["feature_engineering", "data_preparation", "modeling"],
        hypothesis_types=["all"],
        modules=["anomaly"],
        keywords=["features", "engineering", "extraction", "selection"],
        implementation_notes="Feature engineering in NFLIP anomaly agent"
    ),
    
    ResearchMethodology(
        methodology_id="ML015",
        name="Adversarial Machine Learning",
        category=ResearchCategory.MACHINE_LEARNING,
        description="Understanding and defending against adversarial attacks on ML models.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["adversarial", "robustness", "evasion_detection"],
        hypothesis_types=["malware", "apt"],
        modules=["anomaly"],
        keywords=["adversarial", "evasion", "robustness", "attacks"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 8: CONFIDENCE & UNCERTAINTY QUANTIFICATION (10 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="CQ001",
        name="Analysis of Competing Hypotheses (ACH)",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Structured analytic technique for evaluating multiple hypotheses against evidence.",
        authors=["Richards J. Heuer Jr."],
        publication_year=1999,
        source="CIA/Intelligence Community",
        use_cases=["hypothesis_evaluation", "competing_analysis", "bias_reduction"],
        hypothesis_types=["all"],
        modules=["hypothesis", "confidence"],
        keywords=["ACH", "competing", "hypotheses", "evidence"],
        implementation_notes="Core methodology for NFLIP hypothesis agent"
    ),
    
    ResearchMethodology(
        methodology_id="CQ002",
        name="Bayesian Inference Networks",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Probabilistic reasoning for updating beliefs based on evidence.",
        authors=["Judea Pearl"],
        publication_year=1988,
        source="Book: Probabilistic Reasoning in Intelligent Systems",
        use_cases=["probability_update", "evidence_weighting", "belief_networks"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["Bayesian", "probability", "belief", "inference"],
        implementation_notes="Bayesian updating in NFLIP confidence agent"
    ),
    
    ResearchMethodology(
        methodology_id="CQ003",
        name="Dempster-Shafer Theory of Evidence",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Mathematical theory for combining evidence from multiple sources.",
        authors=["Glenn Shafer"],
        publication_year=1976,
        source="Book: A Mathematical Theory of Evidence",
        use_cases=["evidence_combination", "uncertainty", "belief_functions"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["Dempster-Shafer", "belief", "combination", "uncertainty"]
    ),
    
    ResearchMethodology(
        methodology_id="CQ004",
        name="ODNI ICD 203 Analytic Standards",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="US Intelligence Community standards for expressing confidence in analytic judgments.",
        authors=["ODNI"],
        source="Intelligence Community Directive",
        use_cases=["confidence_expression", "analytic_standards", "intelligence"],
        hypothesis_types=["all"],
        modules=["confidence", "synthesis"],
        keywords=["ICD203", "confidence", "intelligence", "standards"],
        implementation_notes="Confidence levels aligned with ICD 203"
    ),
    
    ResearchMethodology(
        methodology_id="CQ005",
        name="Fuzzy Logic for Security Assessment",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Application of fuzzy logic for handling uncertainty in security assessments.",
        authors=["Various Researchers"],
        source="Academic Research",
        use_cases=["fuzzy_assessment", "uncertainty_handling", "risk_scoring"],
        hypothesis_types=["all"],
        modules=["confidence", "depth"],
        keywords=["fuzzy", "uncertainty", "membership", "linguistics"]
    ),
    
    ResearchMethodology(
        methodology_id="CQ006",
        name="Likelihood Ratios for Digital Evidence",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Application of likelihood ratios for evaluating digital evidence strength.",
        authors=["Various Researchers"],
        source="Forensic Science Research",
        use_cases=["evidence_strength", "likelihood", "forensic_statistics"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["likelihood", "ratio", "strength", "evidence"],
        implementation_notes="Used in NFLIP Bayesian confidence update"
    ),
    
    ResearchMethodology(
        methodology_id="CQ007",
        name="Monte Carlo Simulation for Risk",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Simulation methods for quantifying uncertainty in risk assessments.",
        authors=["Various"],
        source="Risk Management",
        use_cases=["risk_simulation", "uncertainty", "probability_distribution"],
        hypothesis_types=["all"],
        modules=["depth"],
        keywords=["Monte_Carlo", "simulation", "risk", "distribution"]
    ),
    
    ResearchMethodology(
        methodology_id="CQ008",
        name="Calibration of Confidence Judgments",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Methods for calibrating analyst confidence to improve accuracy.",
        authors=["Various Researchers"],
        source="Decision Science Research",
        use_cases=["calibration", "accuracy", "training"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["calibration", "accuracy", "overconfidence", "training"]
    ),
    
    ResearchMethodology(
        methodology_id="CQ009",
        name="Structured Probability Elicitation",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Methods for systematically eliciting probability estimates from experts.",
        authors=["Various Researchers"],
        source="Decision Science",
        use_cases=["elicitation", "expert_judgment", "probability"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["elicitation", "expert", "probability", "structured"]
    ),
    
    ResearchMethodology(
        methodology_id="CQ010",
        name="Multi-Factor Confidence Scoring",
        category=ResearchCategory.CONFIDENCE_QUANTIFICATION,
        description="Weighted combination of multiple factors for overall confidence assessment.",
        authors=["Various"],
        source="NFLIP Development",
        use_cases=["confidence_scoring", "multi_factor", "weighted"],
        hypothesis_types=["all"],
        modules=["confidence"],
        keywords=["multi-factor", "weighted", "scoring", "confidence"],
        implementation_notes="Core methodology for NFLIP confidence scoring"
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 9: THREAT INTELLIGENCE & ATTRIBUTION (12 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="TI001",
        name="MITRE ATT&CK Framework",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Comprehensive knowledge base of adversary tactics and techniques.",
        authors=["MITRE Corporation"],
        source="MITRE",
        url="https://attack.mitre.org",
        use_cases=["tactic_mapping", "technique_identification", "threat_modeling"],
        hypothesis_types=["all"],
        modules=["correlation", "hypothesis"],
        keywords=["MITRE", "ATT&CK", "tactics", "techniques"],
        implementation_notes="Core framework for NFLIP correlation module"
    ),
    
    ResearchMethodology(
        methodology_id="TI002",
        name="Cyber Kill Chain (Lockheed Martin)",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Framework describing stages of cyber attacks from reconnaissance to actions on objectives.",
        authors=["Eric M. Hutchins", "et al."],
        publication_year=2011,
        source="Lockheed Martin",
        use_cases=["attack_stages", "defense_mapping", "gap_analysis"],
        hypothesis_types=["all"],
        modules=["hypothesis", "correlation"],
        keywords=["Kill_Chain", "stages", "Lockheed", "attack"],
        implementation_notes="Used in NFLIP hypothesis agent"
    ),
    
    ResearchMethodology(
        methodology_id="TI003",
        name="Diamond Model of Intrusion Analysis",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Framework relating adversary, capability, infrastructure, and victim.",
        authors=["Sergio Caltagirone", "Andrew Pendergast", "Christopher Betz"],
        publication_year=2013,
        source="Center for Cyber Intelligence Analysis and Threat Research",
        use_cases=["intrusion_analysis", "relationship_mapping", "threat_modeling"],
        hypothesis_types=["all"],
        modules=["hypothesis", "correlation"],
        keywords=["Diamond", "adversary", "capability", "victim"],
        implementation_notes="Used in NFLIP hypothesis parsing"
    ),
    
    ResearchMethodology(
        methodology_id="TI004",
        name="STIX/TAXII Threat Intelligence Sharing",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Standards for representing and sharing threat intelligence.",
        authors=["OASIS"],
        source="OASIS Standard",
        url="https://oasis-open.github.io/cti-documentation/",
        use_cases=["threat_sharing", "ioc_exchange", "standardization"],
        hypothesis_types=["all"],
        modules=["evidence"],
        keywords=["STIX", "TAXII", "sharing", "CTI"]
    ),
    
    ResearchMethodology(
        methodology_id="TI005",
        name="Threat Actor Profiling",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Methodologies for characterizing threat actor capabilities, motivations, and TTPs.",
        authors=["Various"],
        source="Intelligence Community",
        use_cases=["actor_profiling", "attribution", "threat_modeling"],
        hypothesis_types=["apt"],
        modules=["correlation"],
        keywords=["threat_actor", "profiling", "APT", "attribution"]
    ),
    
    ResearchMethodology(
        methodology_id="TI006",
        name="Indicator of Compromise (IOC) Analysis",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Systematic analysis and correlation of indicators of compromise.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["ioc_analysis", "detection", "hunting"],
        hypothesis_types=["malware", "c2"],
        modules=["evidence", "anomaly"],
        keywords=["IOC", "indicators", "detection", "signatures"]
    ),
    
    ResearchMethodology(
        methodology_id="TI007",
        name="YARA-Based Threat Hunting",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Using YARA rules for proactive threat hunting across evidence.",
        authors=["Various"],
        source="Tool Development",
        use_cases=["threat_hunting", "malware_detection", "pattern_matching"],
        hypothesis_types=["malware"],
        modules=["evidence"],
        keywords=["YARA", "hunting", "patterns", "rules"]
    ),
    
    ResearchMethodology(
        methodology_id="TI008",
        name="Threat Intelligence Platform Integration",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Integration of TIP data for enrichment and correlation.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["enrichment", "correlation", "context"],
        hypothesis_types=["all"],
        modules=["evidence", "correlation"],
        keywords=["TIP", "integration", "enrichment", "context"]
    ),
    
    ResearchMethodology(
        methodology_id="TI009",
        name="Attribution Methodology",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Systematic approach to attributing attacks to specific actors or groups.",
        authors=["Various"],
        source="Intelligence Community",
        use_cases=["attribution", "confidence", "evidence_analysis"],
        hypothesis_types=["apt"],
        modules=["correlation"],
        keywords=["attribution", "actor", "evidence", "confidence"]
    ),
    
    ResearchMethodology(
        methodology_id="TI010",
        name="Campaign Analysis",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Analysis of related attack activities as part of coordinated campaigns.",
        authors=["Various"],
        source="Intelligence Community",
        use_cases=["campaign_tracking", "clustering", "attribution"],
        hypothesis_types=["apt"],
        modules=["correlation"],
        keywords=["campaign", "clustering", "related", "coordinated"]
    ),
    
    ResearchMethodology(
        methodology_id="TI011",
        name="Infrastructure Analysis",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Analysis of attacker infrastructure including domains, IPs, and hosting.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["infrastructure", "pivoting", "tracking"],
        hypothesis_types=["c2", "apt"],
        modules=["network"],
        keywords=["infrastructure", "domains", "hosting", "pivot"]
    ),
    
    ResearchMethodology(
        methodology_id="TI012",
        name="Threat Modeling (STRIDE/PASTA)",
        category=ResearchCategory.THREAT_INTELLIGENCE,
        description="Systematic threat modeling methodologies for identifying potential attacks.",
        authors=["Microsoft/Various"],
        source="Industry Standard",
        use_cases=["threat_modeling", "risk_assessment", "security_design"],
        hypothesis_types=["all"],
        modules=["hypothesis"],
        keywords=["STRIDE", "PASTA", "modeling", "threats"]
    ),
    
    # ─────────────────────────────────────────────────────────────────────────
    # CATEGORY 10: INCIDENT RESPONSE FRAMEWORKS (10 methodologies)
    # ─────────────────────────────────────────────────────────────────────────
    
    ResearchMethodology(
        methodology_id="IR001",
        name="NIST SP 800-61 Incident Handling Guide",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Comprehensive guide for computer security incident handling.",
        authors=["Paul Cichonski", "et al."],
        publication_year=2012,
        source="NIST Special Publication",
        url="https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final",
        use_cases=["incident_handling", "response_procedures", "documentation"],
        hypothesis_types=["all"],
        modules=["all"],
        keywords=["NIST", "incident", "handling", "800-61"]
    ),
    
    ResearchMethodology(
        methodology_id="IR002",
        name="SANS Incident Response Process",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Six-phase incident response methodology: Preparation, Identification, Containment, Eradication, Recovery, Lessons Learned.",
        authors=["SANS Institute"],
        source="SANS Training",
        use_cases=["incident_response", "process", "phases"],
        hypothesis_types=["all"],
        modules=["all"],
        keywords=["SANS", "phases", "PICERL", "process"]
    ),
    
    ResearchMethodology(
        methodology_id="IR003",
        name="NIST Cybersecurity Framework",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Framework for improving critical infrastructure cybersecurity.",
        authors=["NIST"],
        source="NIST Framework",
        url="https://www.nist.gov/cyberframework",
        use_cases=["security_framework", "risk_management", "maturity"],
        hypothesis_types=["all"],
        modules=["depth", "synthesis"],
        keywords=["NIST", "CSF", "framework", "risk"],
        implementation_notes="Used in NFLIP recommendations mapping"
    ),
    
    ResearchMethodology(
        methodology_id="IR004",
        name="ISO 27035 Incident Management",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="International standard for information security incident management.",
        authors=["ISO/IEC"],
        source="ISO Standard",
        use_cases=["incident_management", "process", "standards"],
        hypothesis_types=["all"],
        modules=["all"],
        keywords=["ISO", "27035", "incident", "management"]
    ),
    
    ResearchMethodology(
        methodology_id="IR005",
        name="Playbook-Based Response",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Predefined response playbooks for specific incident types.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["playbooks", "automation", "standardization"],
        hypothesis_types=["all"],
        modules=["orchestrator"],
        keywords=["playbook", "automation", "SOAR", "response"]
    ),
    
    ResearchMethodology(
        methodology_id="IR006",
        name="Threat Hunting Methodology",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Proactive search for threats that evade existing security controls.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["threat_hunting", "proactive", "detection"],
        hypothesis_types=["all"],
        modules=["anomaly", "correlation"],
        keywords=["hunting", "proactive", "hypothesis", "search"]
    ),
    
    ResearchMethodology(
        methodology_id="IR007",
        name="Root Cause Analysis (RCA)",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Systematic process for identifying the root causes of incidents.",
        authors=["Various"],
        source="Quality Management",
        use_cases=["root_cause", "analysis", "prevention"],
        hypothesis_types=["all"],
        modules=["correlation", "synthesis"],
        keywords=["RCA", "root", "cause", "analysis"],
        implementation_notes="Used in NFLIP correlation RCA narrative"
    ),
    
    ResearchMethodology(
        methodology_id="IR008",
        name="OODA Loop for IR",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Observe-Orient-Decide-Act loop applied to incident response.",
        authors=["John Boyd"],
        source="Military Strategy",
        use_cases=["decision_making", "rapid_response", "iteration"],
        hypothesis_types=["all"],
        modules=["orchestrator"],
        keywords=["OODA", "loop", "decision", "rapid"],
        implementation_notes="Used in NFLIP hypothesis iteration"
    ),
    
    ResearchMethodology(
        methodology_id="IR009",
        name="Containment Strategies",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Strategies for containing incidents to prevent further damage.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["containment", "isolation", "damage_control"],
        hypothesis_types=["all"],
        modules=["synthesis"],
        keywords=["containment", "isolation", "quarantine", "control"]
    ),
    
    ResearchMethodology(
        methodology_id="IR010",
        name="Post-Incident Review Process",
        category=ResearchCategory.INCIDENT_RESPONSE,
        description="Structured process for learning from incidents and improving defenses.",
        authors=["Various"],
        source="Industry Practice",
        use_cases=["lessons_learned", "improvement", "review"],
        hypothesis_types=["all"],
        modules=["synthesis"],
        keywords=["PIR", "lessons", "improvement", "review"]
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH KNOWLEDGE BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class ResearchKnowledgeBase:
    """
    Research Knowledge Base for forensic methodologies.
    
    Provides search, lookup, and recommendation capabilities for
    100+ research methodologies across forensic domains.
    """
    
    def __init__(self):
        self._methodologies = {m.methodology_id: m for m in RESEARCH_METHODOLOGIES}
        self._by_category = self._index_by_category()
        self._by_keyword = self._index_by_keyword()
        self._by_module = self._index_by_module()
        self._by_hypothesis = self._index_by_hypothesis()
    
    def _index_by_category(self) -> Dict[str, List[str]]:
        """Build category index."""
        index = {}
        for m in RESEARCH_METHODOLOGIES:
            cat = m.category.value
            if cat not in index:
                index[cat] = []
            index[cat].append(m.methodology_id)
        return index
    
    def _index_by_keyword(self) -> Dict[str, List[str]]:
        """Build keyword index."""
        index = {}
        for m in RESEARCH_METHODOLOGIES:
            for kw in m.keywords:
                kw_lower = kw.lower()
                if kw_lower not in index:
                    index[kw_lower] = []
                index[kw_lower].append(m.methodology_id)
        return index
    
    def _index_by_module(self) -> Dict[str, List[str]]:
        """Build module index."""
        index = {}
        for m in RESEARCH_METHODOLOGIES:
            for mod in m.modules:
                if mod not in index:
                    index[mod] = []
                index[mod].append(m.methodology_id)
        return index
    
    def _index_by_hypothesis(self) -> Dict[str, List[str]]:
        """Build hypothesis type index."""
        index = {}
        for m in RESEARCH_METHODOLOGIES:
            for h_type in m.hypothesis_types:
                if h_type not in index:
                    index[h_type] = []
                index[h_type].append(m.methodology_id)
        return index
    
    @property
    def total_methodologies(self) -> int:
        """Total number of methodologies in the knowledge base."""
        return len(self._methodologies)
    
    def get(self, methodology_id: str) -> Optional[ResearchMethodology]:
        """Get a methodology by ID."""
        return self._methodologies.get(methodology_id)
    
    def get_by_category(self, category: ResearchCategory) -> List[ResearchMethodology]:
        """Get all methodologies in a category."""
        ids = self._by_category.get(category.value, [])
        return [self._methodologies[mid] for mid in ids]
    
    def get_by_module(self, module: str) -> List[ResearchMethodology]:
        """Get all methodologies relevant to a module."""
        ids = self._by_module.get(module, [])
        return [self._methodologies[mid] for mid in ids]
    
    def get_by_hypothesis_type(self, hypothesis_type: str) -> List[ResearchMethodology]:
        """Get methodologies relevant to a hypothesis type."""
        ids = self._by_hypothesis.get(hypothesis_type, [])
        # Also include 'all' type
        ids = list(set(ids + self._by_hypothesis.get("all", [])))
        return [self._methodologies[mid] for mid in ids]
    
    def search(self, query: str) -> List[ResearchMethodology]:
        """Search methodologies by keyword."""
        query_lower = query.lower()
        matching_ids = set()
        
        # Search keywords
        for kw, ids in self._by_keyword.items():
            if query_lower in kw:
                matching_ids.update(ids)
        
        # Search names and descriptions
        for m in RESEARCH_METHODOLOGIES:
            if query_lower in m.name.lower() or query_lower in m.description.lower():
                matching_ids.add(m.methodology_id)
        
        return [self._methodologies[mid] for mid in matching_ids]
    
    def get_recommendations(
        self,
        hypothesis_types: List[str] = None,
        modules: List[str] = None,
        limit: int = 10
    ) -> List[ResearchMethodology]:
        """Get recommended methodologies based on context."""
        scores = {}
        
        for m in RESEARCH_METHODOLOGIES:
            score = 0
            
            # Score by hypothesis type match
            if hypothesis_types:
                for h_type in hypothesis_types:
                    if h_type in m.hypothesis_types or "all" in m.hypothesis_types:
                        score += 2
            
            # Score by module match
            if modules:
                for mod in modules:
                    if mod in m.modules or "all" in m.modules:
                        score += 1
            
            if score > 0:
                scores[m.methodology_id] = score
        
        # Sort by score and return top N
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [self._methodologies[mid] for mid in sorted_ids[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the knowledge base."""
        return {
            "total_methodologies": self.total_methodologies,
            "categories": {cat.value: len(ids) for cat, ids in 
                         [(c, self._by_category.get(c.value, [])) for c in ResearchCategory]},
            "modules_covered": list(self._by_module.keys()),
            "hypothesis_types_covered": list(self._by_hypothesis.keys()),
            "sources": list(set(m.source for m in RESEARCH_METHODOLOGIES if m.source))
        }
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all methodologies."""
        return [m.to_dict() for m in RESEARCH_METHODOLOGIES]
    
    def list_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """List methodologies grouped by category."""
        result = {}
        for cat in ResearchCategory:
            methodologies = self.get_by_category(cat)
            if methodologies:
                result[cat.value] = [m.to_dict() for m in methodologies]
        return result


# Singleton instance
knowledge_base = ResearchKnowledgeBase()
