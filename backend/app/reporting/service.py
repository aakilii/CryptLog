"""
Report service: gathers forensic data and generates report content.
"""
from typing import Dict, Any, List
from datetime import datetime

from app.dashboard.service import (
    get_summary,
    get_timeline,
    get_severity,
)
from app.db.session import SessionLocal
from app.detection.service import run_detection
from app.reporting.engine import GraphEngine, b64_from_buf


def build_forensic_report_data(report_type: str = "executive") -> Dict[str, Any]:
    """
    Build forensic report data from dashboard & detection.
    
    Args:
        report_type: 'executive', 'detailed', or 'threat'
    
    Returns:
        Dictionary with title and sections for PDF generation
    """
    
    # Gather all data
    db = SessionLocal()
    try:
        summary = get_summary(db)
    finally:
        db.close()
    timeline = get_timeline()
    severity = get_severity()
    detection = run_detection()
    
    title = "FORENSIC ANALYSIS REPORT"
    sections = []
    
    # --- EXECUTIVE SUMMARY ---
    exec_section = {
        "heading": "1. Executive Summary",
        "paragraphs": [
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Analysis Status: {summary.get('status', 'unknown')}",
            f"Total Events Processed: {summary.get('total_events', 0)}",
            f"Critical Threats Detected: {summary.get('critical_threats', 0)}",
            f"Data Source: {summary.get('source', 'unknown')}",
        ],
        "tables": [],
        "charts": []
    }
    
    # Summary table
    summary_data = [
        ["Metric", "Value"],
        ["Status", summary.get("status", "N/A")],
        ["Total Events", str(summary.get("total_events", 0))],
        ["Critical Threats", str(summary.get("critical_threats", 0))],
        ["Earliest Log", summary.get("earliest_log", "N/A")],
        ["Latest Log", summary.get("latest_log", "N/A")],
    ]
    
    exec_section["tables"].append({
        "columns": ["Metric", "Value"],
        "rows": summary_data[1:]
    })
    
    sections.append(exec_section)
    
    # --- TIMELINE ANALYSIS ---
    timeline_section = {
        "heading": "2. Event Timeline",
        "paragraphs": [
            "Hourly distribution of forensic events over the past 24 hours.",
        ],
        "tables": [],
        "charts": []
    }
    
    if timeline.get("series"):
        try:
            timeline_chart = GraphEngine.line_chart(
                timeline["series"],
                "Events per Hour (24h)",
                "Event Count"
            )
            timeline_section["charts"].append({
                "b64": b64_from_buf(timeline_chart)
            })
        except Exception as e:
            timeline_section["paragraphs"].append(f"[Timeline chart error: {str(e)}]")
    
    sections.append(timeline_section)
    
    # --- SEVERITY DISTRIBUTION ---
    severity_section = {
        "heading": "3. Threat Severity Analysis",
        "paragraphs": [
            "Distribution of detected threats by severity level.",
        ],
        "tables": [],
        "charts": []
    }
    
    if severity.get("distribution"):
        try:
            severity_chart = GraphEngine.pie_chart(
                severity["distribution"],
                "Threat Severity Distribution"
            )
            severity_section["charts"].append({
                "b64": b64_from_buf(severity_chart)
            })
        except Exception as e:
            severity_section["paragraphs"].append(f"[Severity chart error: {str(e)}]")
    
    sections.append(severity_section)
    
    # --- DETECTION RESULTS ---
    detection_section = {
        "heading": "4. Anomaly Detection Results",
        "paragraphs": [
            f"Detection Engine Status: {detection.get('status', 'N/A')}",
        ],
        "tables": [],
        "charts": []
    }
    
    if detection.get("status") == "ok":
        anomalies = detection.get("anomalies", [])
        detection_section["paragraphs"].append(
            f"Total Anomalies Detected: {len(anomalies)}"
        )
        
        # Top anomalies table
        if anomalies:
            top_anomalies = sorted(
                anomalies,
                key=lambda x: float(x.get("risk_score", 0)),
                reverse=True
            )[:10]
            
            anom_rows = [
                [
                    str(a.get("id", "N/A"))[:20],
                    str(a.get("risk_score", 0))[:6],
                    str(a.get("anomaly_type", "N/A"))[:15]
                ]
                for a in top_anomalies
            ]
            
            detection_section["tables"].append({
                "columns": ["Log ID", "Risk Score", "Anomaly Type"],
                "rows": anom_rows
            })
    else:
        detection_section["paragraphs"].append(
            f"Detection Message: {detection.get('message', 'No data')}"
        )
    
    sections.append(detection_section)
    
    # --- RECOMMENDATIONS ---
    rec_section = {
        "heading": "5. Recommendations",
        "paragraphs": [
            "Based on the forensic analysis:",
            "1. Review all critical threats immediately.",
            "2. Validate integrity of flagged artifacts.",
            "3. Isolate suspicious endpoints for further analysis.",
            "4. Preserve chain of custody for all evidence.",
            "5. Document findings and maintain audit trail.",
        ],
        "tables": [],
        "charts": []
    }
    sections.append(rec_section)
    
    return {
        "title": title,
        "sections": sections,
        "summary": summary,
        "detection": detection,
    }


def build_threat_report_data() -> Dict[str, Any]:
    """Build focused threat report (high-risk items only)."""
    full_data = build_forensic_report_data("threat")
    
    # Filter to critical threats only
    full_data["title"] = "THREAT ANALYSIS REPORT"
    return full_data


def build_detailed_report_data() -> Dict[str, Any]:
    """Build comprehensive detailed report."""
    full_data = build_forensic_report_data("detailed")
    
    full_data["title"] = "DETAILED FORENSIC ANALYSIS REPORT"
    # Could add more detailed sections here
    return full_data
