import json
import hashlib
from datetime import datetime
from operation_room.database import open_vault

# Create comprehensive report AST with proper content
def create_report_ast():
    pages = []
    
    # Page 1: Cover Page
    pages.append({
        "pageNumber": 1,
        "elements": [
            {"id": "cover_title", "type": "text", "x": 100, "y": 200, "width": 600, "height": 60,
             "content": "FORENSIC INVESTIGATION REPORT", "fontSize": 32, "fontWeight": "bold", "textAlign": "center"},
            {"id": "cover_subtitle", "type": "text", "x": 100, "y": 280, "width": 600, "height": 40,
             "content": "TechCorp Ransomware Incident Analysis", "fontSize": 20, "textAlign": "center"},
            {"id": "cover_case", "type": "text", "x": 100, "y": 350, "width": 600, "height": 30,
             "content": "Case ID: DEMO-RANSOMWARE-001", "fontSize": 14, "textAlign": "center"},
            {"id": "cover_date", "type": "text", "x": 100, "y": 390, "width": 600, "height": 30,
             "content": "Date: April 8, 2026", "fontSize": 14, "textAlign": "center"},
            {"id": "cover_class", "type": "text", "x": 100, "y": 450, "width": 600, "height": 30,
             "content": "Classification: CONFIDENTIAL", "fontSize": 12, "textAlign": "center"}
        ]
    })
    
    # Page 2: Executive Summary
    exec_summary = '''This investigation analyzed a sophisticated ransomware attack against TechCorp's corporate network infrastructure. 
    
The attack began on March 15, 2026 at 02:14 UTC with initial access gained through a phishing email containing malicious macro-enabled document. The threat actor, assessed to be affiliated with APT-SHADOW-CREW, demonstrated advanced tactics including living-off-the-land techniques, lateral movement via compromised credentials, and deployment of custom ransomware variant designated "DARKLOCK-V3".

Key findings indicate that 847 systems were affected across 12 network segments. Data exfiltration of approximately 2.3TB was detected prior to encryption. The estimated financial impact exceeds 4.2 million dollars including recovery costs, business interruption, and potential regulatory fines.

Immediate containment actions were implemented within 4 hours of detection, limiting the spread to 23% of the total network infrastructure. Recovery operations are ongoing with 67% of critical systems restored as of this report date.'''
    
    pages.append({
        "pageNumber": 2,
        "elements": [
            {"id": "exec_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "EXECUTIVE SUMMARY", "fontSize": 24, "fontWeight": "bold"},
            {"id": "exec_body", "type": "text", "x": 50, "y": 110, "width": 700, "height": 500,
             "content": exec_summary, "fontSize": 11, "textAlign": "justify"}
        ]
    })
    
    # Page 3: Key Metrics
    pages.append({
        "pageNumber": 3,
        "elements": [
            {"id": "metrics_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "KEY METRICS OVERVIEW", "fontSize": 24, "fontWeight": "bold"},
            {"id": "metric1", "type": "metric", "x": 50, "y": 120, "width": 160, "height": 100,
             "value": "503", "label": "Timeline Events", "trend": "neutral", "color": "#3b82f6"},
            {"id": "metric2", "type": "metric", "x": 230, "y": 120, "width": 160, "height": 100,
             "value": "256", "label": "Anomalies Flagged", "trend": "critical", "color": "#ef4444"},
            {"id": "metric3", "type": "metric", "x": 410, "y": 120, "width": 160, "height": 100,
             "value": "847", "label": "Systems Affected", "trend": "warning", "color": "#f59e0b"},
            {"id": "metric4", "type": "metric", "x": 590, "y": 120, "width": 160, "height": 100,
             "value": "2.3 TB", "label": "Data Exfiltrated", "trend": "critical", "color": "#ef4444"}
        ]
    })
    
    # Page 4: Attack Timeline
    timeline_text = '''The attack progressed through seven distinct phases over a 72-hour period:

Phase 1 - Initial Access (T+0h): Spear-phishing email delivered to finance department containing DARKLOCK dropper disguised as invoice spreadsheet.

Phase 2 - Execution (T+0.5h): User enabled macros, triggering PowerShell-based payload download from compromised legitimate website.

Phase 3 - Persistence (T+2h): Registry run keys and scheduled tasks established. Service installed under SYSTEM context.

Phase 4 - Credential Access (T+4h): Mimikatz variant deployed. Domain admin credentials harvested from memory of compromised workstation.

Phase 5 - Lateral Movement (T+8h): WMI and PSExec used to spread across internal network. RDP connections to critical servers initiated.

Phase 6 - Exfiltration (T+24h): Data staged to attacker-controlled cloud storage. 2.3TB transferred over 18-hour period using encrypted channels.

Phase 7 - Impact (T+72h): DARKLOCK-V3 ransomware deployed. AES-256 encryption applied to 847 systems. Ransom note demanding 500 BTC.'''
    
    pages.append({
        "pageNumber": 4,
        "elements": [
            {"id": "timeline_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "ATTACK TIMELINE ANALYSIS", "fontSize": 24, "fontWeight": "bold"},
            {"id": "timeline_body", "type": "text", "x": 50, "y": 110, "width": 700, "height": 550,
             "content": timeline_text, "fontSize": 10, "textAlign": "left"}
        ]
    })
    
    # Page 5: Severity Distribution Chart
    pages.append({
        "pageNumber": 5,
        "elements": [
            {"id": "severity_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "SEVERITY DISTRIBUTION", "fontSize": 24, "fontWeight": "bold"},
            {"id": "severity_chart", "type": "chart", "x": 50, "y": 110, "width": 350, "height": 250,
             "chartType": "pie", "chartTitle": "Events by Severity Level",
             "data": [
                 {"name": "Critical", "value": 45, "color": "#ef4444"},
                 {"name": "High", "value": 127, "color": "#f59e0b"},
                 {"name": "Medium", "value": 201, "color": "#3b82f6"},
                 {"name": "Low", "value": 130, "color": "#22c55e"}
             ]},
            {"id": "phase_chart", "type": "chart", "x": 420, "y": 110, "width": 350, "height": 250,
             "chartType": "bar", "chartTitle": "Events by Attack Phase",
             "data": [
                 {"name": "Initial Access", "value": 23, "color": "#3b82f6"},
                 {"name": "Execution", "value": 45, "color": "#22c55e"},
                 {"name": "Persistence", "value": 67, "color": "#f59e0b"},
                 {"name": "Credential Access", "value": 89, "color": "#ef4444"},
                 {"name": "Lateral Movement", "value": 156, "color": "#8b5cf6"},
                 {"name": "Exfiltration", "value": 78, "color": "#06b6d4"},
                 {"name": "Impact", "value": 45, "color": "#ec4899"}
             ]}
        ]
    })
    
    # Page 6: Anomaly Analysis
    anomaly_text = '''The anomaly detection system identified 256 significant deviations from baseline behavior across the monitored network infrastructure.

Statistical Analysis:
- Mean anomaly score: 0.67 (scale 0-1)
- Standard deviation: 0.23
- 95th percentile threshold: 0.89
- Maximum observed score: 0.98

Top Anomaly Categories:
1. Unusual process execution patterns (87 events)
2. Abnormal network traffic volumes (64 events)
3. Suspicious authentication attempts (45 events)
4. File system modification anomalies (38 events)
5. Privilege escalation indicators (22 events)

The clustering analysis revealed three distinct attack patterns correlating with known APT-SHADOW-CREW TTPs. Machine learning models achieved 94.2% precision in distinguishing malicious from benign anomalies.'''
    
    pages.append({
        "pageNumber": 6,
        "elements": [
            {"id": "anomaly_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "ANOMALY DETECTION ANALYSIS", "fontSize": 24, "fontWeight": "bold"},
            {"id": "anomaly_body", "type": "text", "x": 50, "y": 110, "width": 380, "height": 400,
             "content": anomaly_text, "fontSize": 10, "textAlign": "left"},
            {"id": "anomaly_gauge", "type": "chart", "x": 450, "y": 110, "width": 300, "height": 180,
             "chartType": "gauge", "chartTitle": "Overall Threat Score",
             "data": {"value": 78, "max": 100, "thresholds": {"low": 30, "medium": 60, "high": 80}}}
        ]
    })
    
    # Page 7: Network Analysis
    network_text = '''Network flow analysis captured 200 distinct connection sessions during the attack window.

Traffic Distribution:
- Internal-to-internal: 150 flows (75%)
- Internal-to-external: 50 flows (25%)

Suspicious External Connections:
1. 185.234.xx.xx (C2 server, Russia) - 23 connections
2. 91.121.xx.xx (Exfil staging, Netherlands) - 15 connections
3. 45.77.xx.xx (Backup C2, Singapore) - 8 connections
4. 104.21.xx.xx (Cloudflare tunnel) - 4 connections

Data Transfer Analysis:
- Total egress during attack: 2.3 TB
- Peak transfer rate: 450 Mbps
- Primary exfil protocol: HTTPS (port 443)
- Secondary channel: DNS tunneling detected'''
    
    pages.append({
        "pageNumber": 7,
        "elements": [
            {"id": "network_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "NETWORK TRAFFIC ANALYSIS", "fontSize": 24, "fontWeight": "bold"},
            {"id": "network_body", "type": "text", "x": 50, "y": 110, "width": 700, "height": 300,
             "content": network_text, "fontSize": 10, "textAlign": "left"},
            {"id": "network_chart", "type": "chart", "x": 50, "y": 430, "width": 350, "height": 200,
             "chartType": "pie", "chartTitle": "Network Flow Distribution",
             "data": [
                 {"name": "Internal", "value": 150, "color": "#22c55e"},
                 {"name": "External", "value": 50, "color": "#ef4444"}
             ]},
            {"id": "data_chart", "type": "chart", "x": 420, "y": 430, "width": 350, "height": 200,
             "chartType": "bar", "chartTitle": "Data Volume by Protocol",
             "data": [
                 {"name": "HTTPS", "value": 1800, "color": "#3b82f6"},
                 {"name": "SMB", "value": 350, "color": "#22c55e"},
                 {"name": "DNS", "value": 120, "color": "#f59e0b"},
                 {"name": "RDP", "value": 30, "color": "#8b5cf6"}
             ]}
        ]
    })
    
    # Page 8: Recommendations
    recs_text = '''Based on the investigation findings, the following remediation and hardening measures are recommended:

IMMEDIATE ACTIONS (0-48 hours):
1. Complete isolation of remaining compromised systems
2. Reset all domain credentials with new password policy
3. Block identified C2 IP addresses at network perimeter
4. Deploy updated endpoint detection signatures

SHORT-TERM ACTIONS (1-2 weeks):
1. Conduct full forensic imaging of affected systems
2. Implement network segmentation between critical zones
3. Enable advanced logging across all security controls
4. Deploy additional monitoring for lateral movement indicators

LONG-TERM IMPROVEMENTS (1-3 months):
1. Implement zero-trust architecture principles
2. Deploy privileged access management solution
3. Conduct organization-wide security awareness training
4. Establish threat hunting program
5. Review and update incident response procedures'''
    
    pages.append({
        "pageNumber": 8,
        "elements": [
            {"id": "recs_title", "type": "text", "x": 50, "y": 50, "width": 700, "height": 40,
             "content": "RECOMMENDATIONS", "fontSize": 24, "fontWeight": "bold"},
            {"id": "recs_body", "type": "text", "x": 50, "y": 110, "width": 700, "height": 550,
             "content": recs_text, "fontSize": 10, "textAlign": "left"}
        ]
    })
    
    return {"pages": pages, "meta": {"title": "TechCorp Ransomware Investigation", "version": "2.0"}}

# Create the AST
ast = create_report_ast()
ast_json = json.dumps(ast)
content_hash = hashlib.sha256(ast_json.encode()).hexdigest()[:16]

# Update in database
conn = open_vault('DEMO-RANSOMWARE-001')
conn.execute("UPDATE studio_documents SET ast_json = ?, content_hash = ?, updated_at = ? WHERE doc_id = ?",
    [ast_json, content_hash, datetime.now().isoformat(), 'report_56252386'])
conn.commit()

print(f"Updated report with {len(ast['pages'])} pages")
print(f"Total elements: {sum(len(p['elements']) for p in ast['pages'])}")
conn.close()
