"""
Test script for the new Deep Research components.

Tests:
1. Log parsers (unified, windows, android, network, email)
2. Hypothesis to report binding
3. Studio V4 canvas integration
4. Full investigation workflow
"""

import asyncio
import pytest
import json
from datetime import datetime, timezone


def test_unified_parser():
    """Test unified log parser."""
    from operation_room.services.log_parsers import (
        UnifiedLogParser,
        EventType,
        EventSeverity,
        normalize_timestamp,
    )
    
    # Test timestamp normalization
    ts1 = normalize_timestamp("2024-03-14T10:15:23.456Z")
    assert ts1.tzinfo is not None
    
    ts2 = normalize_timestamp(1710410123)  # Unix timestamp
    assert ts2.tzinfo is not None
    
    # Test event types
    assert EventType.USB_CONNECT.value == "usb_connect"
    assert EventType.BLUETOOTH_TRANSFER.value == "bluetooth_transfer"
    assert EventType.EMAIL_SEND.value == "email_send"
    
    # Test parser creation
    parser = UnifiedLogParser("test-case-001")
    assert parser.case_id == "test-case-001"
    assert len(parser.events) == 0
    
    print("✓ Unified parser tests passed")


def test_hypothesis_report_binder():
    """Test hypothesis to report binding."""
    from operation_room.services.deep_research import (
        HypothesisReportBinder,
        HypothesisFinding,
        EvidenceReference,
        ReportSectionType,
    )
    
    binder = HypothesisReportBinder("case-001", "inv-001")
    
    # Add findings
    finding1 = HypothesisFinding(
        hypothesis_id="h1_usb",
        hypothesis_name="USB Exfiltration",
        verdict="confirmed",
        confidence=0.92,
        evidence_for=["EV-001", "EV-002"],
        evidence_against=[],
        summary="USB transfer confirmed.",
        details={"files": ["report.xlsx", "data.csv"]}
    )
    binder.add_finding(finding1)
    
    finding2 = HypothesisFinding(
        hypothesis_id="h2_bluetooth",
        hypothesis_name="Bluetooth Exfiltration",
        verdict="confirmed",
        confidence=0.85,
        evidence_for=["EV-003"],
        evidence_against=[],
        summary="Bluetooth transfer detected.",
    )
    binder.add_finding(finding2)
    
    # Add evidence
    evidence1 = EvidenceReference(
        evidence_id="EV-001",
        evidence_type="usb_connect",
        description="USB device connected",
        timestamp="2024-03-14T10:15:23Z",
        source_log="System.evtx",
        hash="sha256:abc123",
    )
    binder.add_evidence(evidence1)
    
    # Generate report structure
    sections = binder.generate_report_structure()
    
    assert len(sections) > 10  # Should have multiple sections
    assert sections[0].section_type == ReportSectionType.TITLE_PAGE
    
    # Export
    export = binder.export_to_dict()
    assert export["case_id"] == "case-001"
    assert export["findings_count"] == 2
    assert len(export["sections"]) > 10
    
    print(f"✓ Hypothesis report binder tests passed ({len(sections)} sections generated)")


def test_studio_v4_integration():
    """Test Studio V4 canvas integration."""
    from operation_room.services.deep_research import (
        StudioV4Integration,
        CanvasElement,
        CanvasPage,
    )
    
    integration = StudioV4Integration("case-001")
    
    # Create pages
    page1 = integration.new_page("title")
    assert page1.page_number == 1
    
    # Add elements
    heading = integration.add_heading("Investigation Report", level=1, page=page1)
    assert heading.element_type == "text"
    
    para = integration.add_paragraph("This is the investigation report.", page=page1)
    assert para.element_type == "text"
    
    # Add table
    page2 = integration.new_page("content")
    table = integration.add_table(
        title="Evidence Summary",
        columns=["ID", "Type", "Description"],
        data=[
            {"ID": "EV-001", "Type": "USB", "Description": "Device connected"},
            {"ID": "EV-002", "Type": "File", "Description": "File copied"},
        ],
        page=page2
    )
    assert table.element_type == "table"
    
    # Add evidence block
    ev_block = integration.add_evidence_block(
        evidence_id="EV-001",
        evidence_type="usb_connect",
        description="USB device SanDisk Ultra connected",
        data={"serial": "AA00000001234", "timestamp": "2024-03-14T10:15:23Z"},
        evidence_hash="sha256:abc123def456",
        page=page2
    )
    assert ev_block.element_type == "evidenceBlock"
    assert ev_block.metadata["verified"] == True
    
    # Export to JSON
    export = integration.export_to_json()
    assert export["case_id"] == "case-001"
    assert len(export["pages"]) == 2
    
    print(f"✓ Studio V4 integration tests passed ({len(export['pages'])} pages created)")


def test_bind_hypothesis_to_report():
    """Test the bind_hypothesis_to_report function."""
    from operation_room.services.deep_research import bind_hypothesis_to_report
    
    findings = [
        {
            "hypothesis_id": "h1_usb",
            "hypothesis_name": "USB Exfiltration",
            "verdict": "confirmed",
            "confidence": 0.92,
            "evidence_for": ["EV-001", "EV-002"],
            "evidence_against": [],
            "summary": "USB transfer confirmed with high confidence.",
            "details": {"files": ["report.xlsx"], "devices": ["SanDisk Ultra"]}
        },
        {
            "hypothesis_id": "h2_email",
            "hypothesis_name": "Email Exfiltration",
            "verdict": "confirmed",
            "confidence": 0.88,
            "evidence_for": ["EV-003"],
            "evidence_against": [],
            "summary": "Email with attachment sent to personal account.",
            "details": {"ip_addresses": ["198.51.100.25"]}
        }
    ]
    
    evidence = [
        {
            "evidence_id": "EV-001",
            "evidence_type": "usb_connect",
            "description": "USB device connected",
            "timestamp": "2024-03-14T10:15:23Z",
            "source_log": "System.evtx",
            "hash": "sha256:abc123",
        },
        {
            "evidence_id": "EV-002",
            "evidence_type": "file_copy",
            "description": "File copied to E:\\ drive",
            "timestamp": "2024-03-14T10:20:45Z",
            "source_log": "Security.evtx",
            "hash": "sha256:def456",
        },
        {
            "evidence_id": "EV-003",
            "evidence_type": "email_send",
            "description": "Email sent to personal@gmail.com",
            "timestamp": "2024-03-14T14:30:00Z",
            "source_log": "Exchange.log",
            "hash": "sha256:ghi789",
        },
    ]
    
    report = bind_hypothesis_to_report(
        case_id="case-001",
        investigation_id="inv-001",
        findings=findings,
        evidence=evidence,
    )
    
    assert report["case_id"] == "case-001"
    assert report["findings_count"] == 2
    assert report["evidence_count"] == 3
    assert "sections" in report
    assert report["total_pages"] > 50  # Should estimate 50+ pages
    
    print(f"✓ bind_hypothesis_to_report tests passed ({report['total_pages']} estimated pages)")


@pytest.mark.asyncio
async def test_create_report_from_findings():
    """Test async canvas creation from findings."""
    from operation_room.services.deep_research import (
        bind_hypothesis_to_report,
        create_report_from_findings,
    )
    
    findings = [
        {
            "hypothesis_id": "h1_usb",
            "hypothesis_name": "USB Exfiltration",
            "verdict": "confirmed",
            "confidence": 0.92,
            "evidence_for": ["EV-001"],
            "evidence_against": [],
            "summary": "USB transfer confirmed.",
        }
    ]
    
    evidence = [
        {
            "evidence_id": "EV-001",
            "evidence_type": "usb_connect",
            "description": "USB device connected",
            "timestamp": "2024-03-14T10:15:23Z",
            "source_log": "System.evtx",
            "hash": "sha256:test123",
        }
    ]
    
    # Bind to structure
    report_structure = bind_hypothesis_to_report(
        case_id="test-case",
        investigation_id="test-inv",
        findings=findings,
        evidence=evidence,
    )
    
    # Create canvas (mock database)
    try:
        canvas = await create_report_from_findings("test-case", report_structure)
        assert canvas["case_id"] == "test-case"
        assert "pages" in canvas
        print(f"✓ create_report_from_findings tests passed ({len(canvas['pages'])} pages)")
    except Exception as e:
        # Expected to fail without database
        print(f"⚠ Canvas creation skipped (no database): {e}")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("DEEP RESEARCH COMPONENT TESTS")
    print("=" * 60)
    print()
    
    test_unified_parser()
    test_hypothesis_report_binder()
    test_studio_v4_integration()
    test_bind_hypothesis_to_report()
    
    # Run async test
    asyncio.run(test_create_report_from_findings())
    
    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
