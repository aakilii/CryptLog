#!/usr/bin/env python3
"""
NFLIP Multi-Agent Demo Script

Demonstrates the complete multi-agent report automation pipeline
with a realistic forensic investigation scenario.

Usage:
    python scripts/demo_agents.py
    python scripts/demo_agents.py --provider gemini
    python scripts/demo_agents.py --quick

Author: NFLIP Development Team
Version: 1.0.0
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from operation_room.config import settings
from operation_room.services.llm_service import get_llm_service
from operation_room.services.agent_runner import get_runner_service
from operation_room.agents.research.knowledge_base import knowledge_base
from operation_room.agents.integration_layer import PipelineExecutor


# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_SCENARIOS = {
    "ransomware": """
INCIDENT REPORT: Suspected Ransomware Attack
Date: 2024-03-15
Affected Systems: Finance Department Servers (FS-01, FS-02, FS-03)

Summary:
At 03:45 AM, the Security Operations Center detected multiple file encryption 
activities on finance department servers. Files were being renamed with .locked 
extension and ransom notes (README_DECRYPT.txt) were appearing in affected directories.

Initial Indicators:
- Suspicious PowerShell execution with encoded commands at 03:30 AM
- Outbound C2 traffic to 185.141.63.0/24 range
- SMB lateral movement between FS-01, FS-02, FS-03
- Volume Shadow Copy deletion commands executed
- Scheduled task created for persistence (name: WindowsUpdate)

Affected User Account: svc_backup (service account with elevated privileges)
Initial Entry Point: Suspected phishing email to user mwilson@company.com

Evidence Collected:
- Memory dumps from all three servers
- Network packet captures (02:00-05:00 AM)
- Windows Event Logs (Security, System, PowerShell)
- Email gateway logs
- Firewall logs
""",

    "data_breach": """
INCIDENT REPORT: Data Exfiltration Investigation
Date: 2024-03-10
Classification: Confidential

Summary:
DLP alerts triggered on March 10 indicating large outbound data transfers from
the R&D department. Investigation revealed potential theft of intellectual property
including product designs and customer database exports.

Timeline:
- March 8, 14:00: User jchen accesses engineering file share (normal)
- March 9, 22:30: jchen's account active outside business hours
- March 9, 23:00-02:00: Multiple ZIP file creations in temp folder
- March 10, 02:15: Outbound transfer to personal cloud storage (Dropbox)
- March 10, 02:45: DLP alert triggered on sensitive file patterns
- March 10, 08:00: Security team begins investigation

Key Evidence:
- 2.3GB transferred to personal Dropbox account
- Files include: product_roadmap_2024.xlsx, customer_contracts.zip
- User accessed files outside their normal job function
- No MFA bypass detected - legitimate credentials used
- USB device was connected on March 8 (device ID captured)

User Profile:
- Name: Jason Chen, Senior Engineer
- Department: R&D - Product Development
- Employment: 3 years, no prior incidents
- Notice: Submitted resignation on March 5
""",

    "apt_intrusion": """
INCIDENT REPORT: Advanced Persistent Threat Investigation
Classification: Top Secret
Date Range: January 15 - March 20, 2024

Executive Summary:
Nation-state threat actor (attributed to APT29) compromised corporate network 
through supply chain attack. Attackers maintained persistent access for 
approximately 65 days before detection.

Initial Compromise:
- Supply chain attack via compromised software update (BuildMaster v3.2.1)
- Trojanized update deployed to 15 developer workstations on Jan 15
- Cobalt Strike beacon established communication with C2 infrastructure

Lateral Movement:
- Kerberoasting attack against service accounts (Jan 18)
- Golden Ticket created using krbtgt hash (Jan 20)
- Domain Admin credentials obtained (Jan 22)
- Accessed Domain Controllers DC-01, DC-02

Persistence Mechanisms:
- WMI event subscriptions
- Scheduled tasks (disguised as Windows updates)
- BITS jobs for file transfers
- Registry Run keys

Data Access:
- Email servers accessed (Exchange 2019)
- SharePoint document libraries
- Executive mailboxes (CEO, CFO, CTO)
- M&A documents and financial projections

C2 Infrastructure:
- Primary: cdn-update[.]cloudfront[.]net (CDN fronting)
- Secondary: update-service[.]azure-cdn[.]net
- Tertiary: s3-static[.]amazonaws[.]com (data exfil)

IOCs Collected:
- 47 unique file hashes
- 12 C2 domains
- 8 IP addresses
- Custom malware samples (2)
"""
}


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner():
    """Print demo banner."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ███╗   ██╗███████╗██╗     ██╗██████╗                                        ║
║   ████╗  ██║██╔════╝██║     ██║██╔══██╗                                       ║
║   ██╔██╗ ██║█████╗  ██║     ██║██████╔╝                                       ║
║   ██║╚██╗██║██╔══╝  ██║     ██║██╔═══╝                                        ║
║   ██║ ╚████║██║     ███████╗██║██║                                            ║
║   ╚═╝  ╚═══╝╚═╝     ╚══════╝╚═╝╚═╝                                            ║
║                                                                               ║
║   Multi-Agent Report Automation System                                        ║
║   Demonstration Script                                                        ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
    """)


def print_section(title: str):
    """Print section header."""
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}\n")


async def demo_research_knowledge_base():
    """Demonstrate research knowledge base."""
    print_section("Research Knowledge Base (120+ Methodologies)")
    
    stats = knowledge_base.get_statistics()
    
    print(f"Total Methodologies: {stats['total_methodologies']}")
    print(f"\nCategories:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1])[:6]:
        print(f"  • {cat}: {count} methodologies")
        
    print(f"\nSample Search - 'memory forensics':")
    results = knowledge_base.search("memory forensics")[:3]
    for r in results:
        if hasattr(r, 'to_dict'):
            r = r.to_dict()
        print(f"  → {r.get('name')} ({r.get('category')})")
        
    print(f"\nSample Search - 'bayesian':")
    results = knowledge_base.search("bayesian")[:3]
    for r in results:
        if hasattr(r, 'to_dict'):
            r = r.to_dict()
        print(f"  → {r.get('name')} ({r.get('category')})")


async def demo_llm_service(provider: str):
    """Demonstrate LLM service."""
    print_section(f"LLM Service ({provider})")
    
    llm = get_llm_service(provider)
    
    print(f"Provider: {llm.provider_name}")
    print(f"Testing connection...")
    
    response = await llm.generate(
        "Respond with exactly: 'LLM connection successful'",
        temperature=0.1,
        max_tokens=50
    )
    
    if response.success:
        print(f"✓ Connection successful!")
        print(f"  Response: {response.content[:100]}")
        print(f"  Latency: {response.latency_ms:.0f}ms")
        print(f"  Model: {response.model}")
    else:
        print(f"✗ Connection failed: {response.error}")
        return False
        
    return True


async def demo_hypothesis_analysis(scenario: str, provider: str):
    """Demonstrate hypothesis analysis."""
    print_section("Hypothesis Analysis")
    
    llm = get_llm_service(provider)
    
    print("Analyzing scenario for hypotheses...")
    print(f"Scenario excerpt: {scenario[:200]}...\n")
    
    response = await llm.analyze_hypothesis(scenario)
    
    if response.success and response.parsed_json:
        result = response.parsed_json
        
        hypotheses = result.get('hypotheses', [])
        print(f"Generated {len(hypotheses)} hypotheses:\n")
        
        for i, h in enumerate(hypotheses, 1):
            print(f"  H{i}: {h.get('statement', 'N/A')}")
            print(f"      Probability: {h.get('initial_probability', 0):.0%}")
            print(f"      Attack Vectors: {', '.join(h.get('attack_vectors', []))}")
            print()
            
        entities = result.get('entities', [])
        if entities:
            print(f"Extracted {len(entities)} entities:")
            for e in entities[:5]:
                print(f"  • {e.get('name', 'N/A')} ({e.get('type', 'unknown')})")
                
        return result
    else:
        print(f"Analysis failed: {response.error}")
        return None


async def demo_confidence_scoring():
    """Demonstrate confidence scoring concepts."""
    print_section("Confidence Scoring Framework")
    
    print("""
Multi-Factor Confidence Scoring:

  Factor                Weight    Description
  ─────────────────────────────────────────────────────────────────
  Evidence Coverage      25%      Completeness of evidence
  Module Agreement       20%      Cross-module consensus
  Temporal Consistency   15%      Timeline coherence
  Cross Validation       20%      External corroboration
  Pattern Match          10%      Known TTP alignment
  Research Alignment     10%      Methodology support

Confidence Levels (ODNI ICD 203):

  Level       Range        Description
  ─────────────────────────────────────────────────────────────────
  Very High   ≥90%        Virtually certain
  High        75-90%      Highly likely
  Moderate    50-75%      About even odds
  Low         25-50%      Unlikely
  Very Low    <25%        Remote possibility

Example Calculation:
  Evidence Coverage:      0.85 × 0.25 = 0.2125
  Module Agreement:       0.80 × 0.20 = 0.1600
  Temporal Consistency:   0.90 × 0.15 = 0.1350
  Cross Validation:       0.75 × 0.20 = 0.1500
  Pattern Match:          0.70 × 0.10 = 0.0700
  Research Alignment:     0.65 × 0.10 = 0.0650
  ────────────────────────────────────────
  Overall Confidence:                0.7925 (HIGH)
""")


async def demo_full_pipeline(scenario_name: str, scenario: str, provider: str, quick: bool):
    """Demonstrate full pipeline execution."""
    print_section("Full Pipeline Execution")
    
    runner = get_runner_service()
    
    print(f"Scenario: {scenario_name}")
    print(f"Provider: {provider}")
    print(f"Mode: {'Quick (hypothesis only)' if quick else 'Full Pipeline'}\n")
    
    # Create run
    run = runner.create_run(
        case_id=f"DEMO-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        scenario=scenario,
        report_type="technical",
        llm_provider=provider
    )
    
    print(f"Run ID: {run.run_id}")
    print(f"Case ID: {run.case_id}")
    print()
    
    if quick:
        # Just do hypothesis analysis
        llm = get_llm_service(provider)
        response = await llm.analyze_hypothesis(scenario)
        
        if response.success:
            print("✓ Hypothesis analysis complete!")
            if response.parsed_json:
                hypotheses = response.parsed_json.get('hypotheses', [])
                print(f"  Generated {len(hypotheses)} hypotheses")
        else:
            print(f"✗ Analysis failed: {response.error}")
    else:
        # Full pipeline
        print("Executing full pipeline...")
        print("  [This may take several minutes with LLM calls]\n")
        
        # Progress callback
        def on_progress(progress):
            pct = int(progress.percentage)
            bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
            print(f"\r  [{bar}] {pct}% - {progress.message}", end='', flush=True)
            
        try:
            run = await runner.execute_run(run, timeout=600, on_progress=on_progress)
            print()  # New line after progress bar
            
            if run.status.value == "completed":
                print("\n✓ Pipeline completed successfully!")
                
                if run.result:
                    print(f"\nResults:")
                    print(f"  Hypotheses: {len(run.result.get('hypotheses', []))}")
                    print(f"  Entities: {len(run.result.get('entities', []))}")
                    print(f"  Evidence Items: {run.result.get('evidence_count', 0)}")
                    
                    confidence = run.result.get('confidence', {})
                    if confidence:
                        print(f"\n  Overall Confidence: {confidence.get('overall_case_confidence', 0):.1%}")
                        print(f"  Confidence Level: {confidence.get('overall_confidence_level', 'N/A')}")
            else:
                print(f"\n✗ Pipeline failed: {run.error}")
                
        except Exception as e:
            print(f"\n✗ Pipeline error: {e}")


async def demo_agent_architecture():
    """Demonstrate agent architecture."""
    print_section("Agent Architecture")
    
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MASTER ORCHESTRATOR                                │
│                    (Task Decomposition & Coordination)                      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   HYPOTHESIS    │    │    EVIDENCE     │    │     MODULE      │
│    ANALYSIS     │    │   COLLECTION    │    │   EVALUATORS    │
│     AGENT       │    │     AGENT       │    │   (6 Agents)    │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │   • Entity Extraction│   • Timeline        │   • Quality Assessment
         │   • Hypothesis Gen   │   • Anomaly         │   • Finding Extraction
         │   • Attack Vectors   │   • Correlation     │   • Confidence Scoring
         │   • ACH Methodology  │   • Network         │   • Cross-Validation
         │                      │   • Depth           │
         │                      │   • CRUD            │
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │   CONFIDENCE SCORING        │
                  │        AGENT                │
                  │  (Multi-Factor Bayesian)    │
                  └─────────────┬───────────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │   SUMMARY SYNTHESIS         │
                  │        AGENT                │
                  │  (Report Generation + NLG)  │
                  └─────────────────────────────┘

Pipeline Stages:
  1. Initialization      → Load context, fetch relevant research
  2. Hypothesis Analysis → Parse scenario, generate hypotheses
  3. Evidence Collection → Query modules, build inventory
  4. Module Evaluation   → Assess findings from each module
  5. Confidence Scoring  → Multi-factor Bayesian analysis
  6. Summary Synthesis   → Generate comprehensive report
  7. Finalization        → Package results, record CoC
""")


async def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="NFLIP Multi-Agent Demo")
    parser.add_argument('--provider', '-p', default=settings.LLM_PROVIDER,
                       choices=['ollama', 'gemini'], help='LLM provider')
    parser.add_argument('--scenario', '-s', default='ransomware',
                       choices=['ransomware', 'data_breach', 'apt_intrusion'])
    parser.add_argument('--quick', '-q', action='store_true',
                       help='Quick mode (hypothesis only)')
    parser.add_argument('--skip-llm', action='store_true',
                       help='Skip LLM-dependent demos')
    
    args = parser.parse_args()
    
    print_banner()
    
    print(f"Configuration:")
    print(f"  LLM Provider: {args.provider}")
    print(f"  Scenario: {args.scenario}")
    print(f"  Mode: {'Quick' if args.quick else 'Full'}")
    
    # Demo 1: Research Knowledge Base
    await demo_research_knowledge_base()
    
    # Demo 2: Agent Architecture
    await demo_agent_architecture()
    
    # Demo 3: Confidence Scoring
    await demo_confidence_scoring()
    
    if not args.skip_llm:
        # Demo 4: LLM Service
        llm_ok = await demo_llm_service(args.provider)
        
        if llm_ok:
            # Demo 5: Hypothesis Analysis
            scenario = DEMO_SCENARIOS[args.scenario]
            await demo_hypothesis_analysis(scenario, args.provider)
            
            # Demo 6: Full Pipeline (optional)
            if not args.quick:
                response = input("\nRun full pipeline? This may take several minutes. (y/n): ")
                if response.lower() == 'y':
                    await demo_full_pipeline(args.scenario, scenario, args.provider, False)
    else:
        print("\n[Skipping LLM-dependent demos]")
        
    print_section("Demo Complete")
    print("For more information, see:")
    print("  • app/agents/ARCHITECTURE.md")
    print("  • python -m app.cli --help")
    print()


if __name__ == "__main__":
    asyncio.run(main())
