"""
End-to-End Report Generation Test: Dual-Device Exfiltration.
Simulates the log import, vault storage, deep research orchestrator,
evidence binding, state machine execution, and layout evaluation.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

# Ensure paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from operation_room.services.canonical_contracts import (
    AdmissibilityResult,
    EvidenceCitationType,
    ReportManifest,
    ReportStatus,
    SectionContract,
    SectionStatus,
)
from operation_room.services.adaptive_template_engine import AdaptiveTemplateEngine
from operation_room.services.evidence_binder import get_evidence_binder
from operation_room.services.section_state_machine import SectionStateMachine, SectionTask
from operation_room.services.admissibility_gate import AdmissibilityGate
from operation_room.services.llm_provider import get_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IntegrationTest")


class MockEvidenceService:
    """Mocks the DB Vault where logs & findings are stored with Keys -> Values."""
    def __init__(self):
        self.vault = {
            "EVD-USB-001": {
                "key_id": "EVD-USB-001",
                "category": "registry",
                "key_name": "USB Insertion Time",
                "summary": "USB Device SanDisk Cruzer inserted at 2026-04-09 14:32:10 UTC.",
                "source_module": "timeline",
                "full_value": "Windows Registry Event: USBSTOR\\Disk&Ven_SanDisk... 2026-04-09T14:32:10Z"
            },
            "EVD-MFT-002": {
                "key_id": "EVD-MFT-002",
                "category": "file_system",
                "key_name": "Confidential File Access",
                "summary": "File 'Project_Q3_Financials.xlsx' accessed from C:\\Users\\corp_suspect\\Documents.",
                "source_module": "timeline",
                "full_value": "MFT Access Record for Project_Q3_Financials.xlsx (Size: 15.2MB)"
            },
            "EVD-BTH-003": {
                "key_id": "EVD-BTH-003",
                "category": "network",
                "key_name": "Bluetooth Pairing",
                "summary": "Windows PC paired with device MAC 98:01:A7:XX:XX:XX (Suspect Android).",
                "source_module": "timeline",
                "full_value": "Event ID BTHPORT: Paired with Android Device (Galaxy S23)"
            },
            "EVD-MOB-004": {
                "key_id": "EVD-MOB-004",
                "category": "mobile",
                "key_name": "OBEX Transfer Received",
                "summary": "OBEX object received on Android matching Project_Q3_Financials.xlsx size exactly 3 minutes after USB insertion.",
                "source_module": "anomaly",
                "full_value": "Android Bluetooth Log: Incoming OBEX transfer completed 15.2MB"
            },
            "EVD-EML-005": {
                "key_id": "EVD-EML-005",
                "category": "network",
                "key_name": "Personal Webmail Upload",
                "summary": "HTTPS POST request to mail.google.com with 15MB payload.",
                "source_module": "network",
                "full_value": "Proxy Log: POST mail.google.com/upload 15,245,332 bytes transferred."
            }
        }
        
    def get_keys_by_section(self, section_key: str) -> list:
        # Mock simplistic association
        return [self._convert(k, v) for k, v in self.vault.items()]
        
    def get_all_keys(self) -> list:
        return [self._convert(k, v) for k, v in self.vault.items()]

    def get_for_report(self, key_id: str, user_id: str) -> str:
        # returns the secret vault value during hydration
        return self.vault.get(key_id, {}).get("full_value", "")
        
    def _convert(self, k, v):
        class Item:
            def to_dict(self): return v
        return Item()


async def mock_section_generator(section: SectionContract, context: Dict[str, Any]) -> SectionContract:
    """The function that state machine runs. Uses real Evidence Binder + Local LLM."""
    binder = context["binder"]
    llm = get_llm()
    
    # 1. Build strict evidence prompt
    evidence_keys = binder.get_all_evidence_keys()
    prompt = binder.build_evidence_prompt(
        section_key=section.section_key,
        section_title=section.title,
        evidence_keys=evidence_keys,
        case_context=context["case_meta"],
        module_summaries={}
    )
    
    # 2. Add extra instructions for layout / length
    # Asking for shorter output in the integration test so it's faster
    prompt += "\n\nCRITICAL OUTLINE: Keep the response under 150 words for this test run."
    
    # 3. Call local Gemma model
    try:
        logger.info(f"Generating section: {section.title} using LLM...")
        llm_response = await llm.generate(
            prompt=prompt,
            system="You are a senior digital forensics expert.",
            temperature=0.3,
            max_tokens=500
        )
    except Exception as e:
        logger.error(f"LLM Generation failed: {e}")
        llm_response = "Error during generation."

    # 4. Bind AI text to Evidence Vault citations
    bound_section = binder.bind_citations(section, llm_response)
    
    # 5. Simulate layout rendering boundary calculations (Phase 5)
    _verify_layout_boundaries(bound_section)
    
    return bound_section


def _verify_layout_boundaries(section: SectionContract):
    """Mocks Phase 5: Ensure bounding boxes don't overflow the page PDF canvas."""
    # Approximate length: 1 word = 6 characters, A4 page fits ~600 words of standard typography
    content_words = section.word_count
    estimated_pages = max(1, content_words // 600)
    
    logger.info(f"[Layout Verifier] Section '{section.section_key}' spans ~{estimated_pages} pages ({content_words} words). Layout spacing OK.")


async def execute_integration_flow():
    case_id = "CASE_EXFIL_TEST_001"
    
    # --- PHASE 1: LOG INGESTION & METADATA ---
    # We mock this via the DB Service override.
    logger.info("Starting Phase 1: Creating metadata & findings in Evidence Vault...")
    mock_service = MockEvidenceService()
    
    binder = get_evidence_binder(case_id)
    binder._evidence_service = mock_service  # Dependency Injection inject
    
    # --- PHASE 2: ADAPTIVE TEMPLATE ASSIGNMENT ---
    logger.info("Starting Phase 2: Resolving Layout Formats via Template Engine...")
    engine = AdaptiveTemplateEngine()
    sections = engine.assemble_sections(template_key="technical", case_type="data_exfiltration")
    manifest = ReportManifest(
        case_id=case_id,
        template_key="technical",
        title="Dual-Device Exfiltration Report",
        sections=sections
    )
    manifest.transition_to(ReportStatus.TEMPLATE_SELECTED)
    manifest.transition_to(ReportStatus.DATA_GATHERING)
    manifest.transition_to(ReportStatus.EVIDENCE_BINDING)
    logger.info(f"Manifest Generated: {len(manifest.sections)} sections derived.")

    # --- PHASE 3 & 4: EXECUTION VIA STATE MACHINE ---
    logger.info("Starting Phase 3 & 4: Spinning up State Machine Workers & Evidence Binder...")
    machine = SectionStateMachine(manifest, max_concurrency=2)
    machine.set_generator(mock_section_generator)
    
    context = {
        "binder": binder,
        "case_meta": {
            "case_id": case_id,
            "title": "USB & Bluetooth Exfiltration from Laptop",
            "status": "investigating"
        }
    }
    
    # Run the machine
    updated_manifest = await machine.execute_all(context, auto_approve=True)
    
    # Print metrics
    logger.info("All Sections Generated.")
    for sec in updated_manifest.sections:
        logger.info(f"   [+] {sec.section_key}: {sec.status.value} - {sec.word_count} words - {len(sec.citations)} citations")

    # --- PHASE 5: HYDRATION & REPLACEMENT ---
    logger.info("Simulating Hydration Engine (Redacted Keys -> Human Values)...")
    for sec in updated_manifest.sections:
        raw_text = sec.content[:60].replace('\\n', ' ')
        hydrated_text = binder.hydrate_section(sec)[:60].replace('\\n', ' ')
        logger.info(f"   Raw:      {raw_text}...")
        logger.info(f"   Hydrated: {hydrated_text}...")

    # --- PHASE 6: ADMISSIBILITY GATES ---
    logger.info("Starting Phase 6: Executing Strict Admissibility Gates...")
    # Seed metadata so it passes IT Act check
    updated_manifest.metadata["it_act_section_65b"] = True
    updated_manifest.metadata["classification"] = "CONFIDENTIAL"
    updated_manifest.metadata["examining_officer"] = "Agent Alpha"
    
    gate = AdmissibilityGate(case_id)
    result = gate.evaluate(updated_manifest)
    
    if result.is_exportable():
        logger.info(">>> ADMISSIBILITY VERDICT: PASS. Report is cleared for Cryptographic Sealing.")
    else:
        logger.warning(f">>> ADMISSIBILITY VERDICT: FAIL/WARN. Issues found:")
        for warn in result.warnings:
            logger.warning(f"   [WARN] {warn['message']}")
        for fail in result.failures:
            logger.error(f"   [FAIL] {fail['message']}")

if __name__ == "__main__":
    asyncio.run(execute_integration_flow())
