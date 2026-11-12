"""
Script to create a comprehensive 40-page forensic investigation report.
"""
import sys
sys.path.insert(0, '.')
import json
import uuid
from datetime import datetime
from operation_room.database import open_vault

case_id = 'DEMO-RANSOMWARE-001'
doc_id = 'report_' + str(uuid.uuid4())[:8]

print(f'Creating report document: {doc_id}')

# Build comprehensive 40-page report AST
pages = []

def make_page(page_num, elements):
    return {
        "id": str(uuid.uuid4())[:8],
        "pageNumber": page_num,
        "elements": elements
    }

# ===== PAGE 1: Cover =====
pages.append(make_page(1, [
    {"id": "e1", "type": "text", "x": 200, "y": 180, "width": 394, "height": 80,
     "content": "<h1 style='text-align:center;color:#1e40af'>FORENSIC INVESTIGATION REPORT</h1>",
     "fontSize": 28, "fontWeight": "bold", "textAlign": "center"},
    {"id": "e2", "type": "text", "x": 200, "y": 280, "width": 394, "height": 50,
     "content": "<h2 style='text-align:center'>TechCorp Ransomware Incident</h2>",
     "fontSize": 20, "textAlign": "center"},
    {"id": "e3", "type": "text", "x": 200, "y": 350, "width": 394, "height": 30,
     "content": "<p style='text-align:center'>Case ID: DEMO-RANSOMWARE-001</p>",
     "fontSize": 14, "textAlign": "center"},
    {"id": "e4", "type": "text", "x": 200, "y": 400, "width": 394, "height": 30,
     "content": "<p style='text-align:center'>Date: March 15, 2026</p>",
     "fontSize": 14, "textAlign": "center"},
    {"id": "e5", "type": "text", "x": 200, "y": 800, "width": 394, "height": 50,
     "content": "<p style='text-align:center;color:#666'>CONFIDENTIAL - Law Enforcement Sensitive</p>",
     "fontSize": 12, "textAlign": "center", "color": "#666"}
]))

# ===== PAGE 2: Executive Summary =====
exec_summary = """<p>On March 15, 2026, TechCorp experienced a sophisticated ransomware attack that resulted in the encryption of 47 workstations and 3 servers, affecting approximately 265,000 files. The attack was attributed to a variant of LockBit 3.0 ransomware.</p>
<p>Our investigation determined that the attack originated from a spear-phishing email targeting a finance department employee. The threat actor demonstrated advanced capabilities including credential harvesting, lateral movement, and data exfiltration totaling approximately 2.3TB before deploying ransomware.</p>
<p><strong>Key Findings:</strong></p>
<ul>
<li>Initial compromise via malicious Excel macro at 09:47 UTC</li>
<li>Credential harvesting using Mimikatz affected 12 domain accounts</li>
<li>2.3TB of sensitive data exfiltrated to external servers</li>
<li>Ransomware deployed at 17:30 UTC, demanding 50 BTC</li>
</ul>"""

pages.append(make_page(2, [
    {"id": "e21", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>Executive Summary</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e22", "type": "text", "x": 40, "y": 100, "width": 714, "height": 200,
     "content": exec_summary, "fontSize": 12},
    {"id": "e23", "type": "metric", "x": 40, "y": 340, "width": 160, "height": 100,
     "value": "47", "label": "Systems Affected", "trend": "critical", "color": "#ef4444"},
    {"id": "e24", "type": "metric", "x": 220, "y": 340, "width": 160, "height": 100,
     "value": "2.3 TB", "label": "Data Exfiltrated", "trend": "critical", "color": "#ef4444"},
    {"id": "e25", "type": "metric", "x": 400, "y": 340, "width": 160, "height": 100,
     "value": "265K", "label": "Files Encrypted", "trend": "critical", "color": "#ef4444"},
    {"id": "e26", "type": "metric", "x": 580, "y": 340, "width": 160, "height": 100,
     "value": "7h 43m", "label": "Attack Duration", "trend": "warning", "color": "#f59e0b"}
]))

# ===== PAGE 3: Table of Contents =====
toc = """<table style='width:100%;border-collapse:collapse'>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>1. Executive Summary</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>2</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>2. Incident Overview</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>4</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>3. Timeline Analysis</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>6</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>4. Anomaly Detection Results</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>10</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>5. Network Traffic Analysis</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>15</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>6. Correlation Analysis</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>20</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>7. MITRE ATT&CK Mapping</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>25</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>8. Depth Assessment</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>28</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>9. Hypothesis Analysis</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>32</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>10. Recommendations</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>36</td></tr>
<tr><td style='padding:8px;border-bottom:1px solid #ddd'>11. Appendices</td><td style='text-align:right;padding:8px;border-bottom:1px solid #ddd'>38</td></tr>
</table>"""

pages.append(make_page(3, [
    {"id": "e31", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>Table of Contents</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e32", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": toc, "fontSize": 12}
]))

# ===== PAGE 4: Incident Overview =====
incident_overview = """<h2>2.1 Background</h2>
<p>TechCorp is a mid-sized technology company with approximately 500 employees across 3 locations. The organization operates a hybrid Active Directory environment with Windows 10/11 workstations and Windows Server 2019 domain controllers.</p>

<h2>2.2 Initial Detection</h2>
<p>The incident was initially detected at 18:15 UTC when the IT helpdesk received multiple calls about encrypted files with ".lockbit3" extensions. The Security Operations Center (SOC) was immediately notified and initiated incident response procedures.</p>

<h2>2.3 Scope of Impact</h2>
<p>The following assets were confirmed as affected:</p>
<ul>
<li><strong>Workstations:</strong> 47 Windows 10/11 systems across Finance, HR, and Engineering departments</li>
<li><strong>Servers:</strong> 3 servers including FileServer-01, partially DC-01 shadow copies</li>
<li><strong>Data:</strong> CustomerDB (150,000 PII records), FinanceDB (50,000 financial records), R&D project files (2,500 proprietary documents)</li>
</ul>

<h2>2.4 Threat Actor Profile</h2>
<p>Based on TTPs observed, the attack is attributed to an affiliate of the LockBit ransomware-as-a-service (RaaS) operation. The threat actor demonstrated advanced capabilities consistent with a well-resourced criminal organization.</p>"""

pages.append(make_page(4, [
    {"id": "e41", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>2. Incident Overview</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e42", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": incident_overview, "fontSize": 12}
]))

# ===== PAGE 5: Incident Overview (continued) =====
incident_cont = """<h2>2.5 Attack Vector Analysis</h2>
<p>The initial compromise vector was a spear-phishing email sent to jsmith@techcorp.com in the Finance department. The email contained a malicious Microsoft Excel attachment named "invoice_Q1_2026.xlsx" which contained an embedded macro.</p>

<p>Upon opening the attachment and enabling macros, the following malicious activities were executed:</p>
<ol>
<li>PowerShell script downloaded from staging server</li>
<li>Cobalt Strike beacon established for persistent access</li>
<li>Initial reconnaissance of local system and network</li>
<li>Credential harvesting via Mimikatz</li>
</ol>

<h2>2.6 Investigation Methodology</h2>
<p>This investigation employed the following methodologies:</p>
<ul>
<li>Memory forensics on affected systems</li>
<li>Timeline analysis of Windows Event Logs</li>
<li>Network traffic analysis including PCAP review</li>
<li>Malware reverse engineering</li>
<li>OSINT research on threat actor infrastructure</li>
</ul>"""

pages.append(make_page(5, [
    {"id": "e51", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>2. Incident Overview (continued)</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e52", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": incident_cont, "fontSize": 12}
]))

# ===== PAGE 6-9: Timeline Analysis =====
timeline_intro = """<p>The following timeline represents the complete attack sequence as reconstructed from multiple data sources including Windows Event Logs, network traffic captures, and endpoint detection telemetry.</p>

<h2>3.1 Attack Phase Summary</h2>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'><th style='padding:8px;text-align:left;border:1px solid #ddd'>Phase</th><th style='padding:8px;text-align:left;border:1px solid #ddd'>Time (UTC)</th><th style='padding:8px;text-align:left;border:1px solid #ddd'>Duration</th></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Initial Access</td><td style='padding:8px;border:1px solid #ddd'>09:47 - 09:52</td><td style='padding:8px;border:1px solid #ddd'>5 min</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Credential Harvesting</td><td style='padding:8px;border:1px solid #ddd'>10:15 - 10:45</td><td style='padding:8px;border:1px solid #ddd'>30 min</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Lateral Movement</td><td style='padding:8px;border:1px solid #ddd'>11:00 - 12:30</td><td style='padding:8px;border:1px solid #ddd'>90 min</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Data Access</td><td style='padding:8px;border:1px solid #ddd'>12:30 - 13:00</td><td style='padding:8px;border:1px solid #ddd'>30 min</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Exfiltration</td><td style='padding:8px;border:1px solid #ddd'>13:00 - 16:00</td><td style='padding:8px;border:1px solid #ddd'>3 hours</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Ransomware Deployment</td><td style='padding:8px;border:1px solid #ddd'>17:30 - 18:15</td><td style='padding:8px;border:1px solid #ddd'>45 min</td></tr>
</table>"""

pages.append(make_page(6, [
    {"id": "e61", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>3. Timeline Analysis</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e62", "type": "text", "x": 40, "y": 100, "width": 714, "height": 400,
     "content": timeline_intro, "fontSize": 12},
    {"id": "e63", "type": "chart", "x": 40, "y": 520, "width": 714, "height": 280,
     "chartType": "timeline", "chartTitle": "Attack Timeline",
     "data": {
         "phases": [
             {"name": "Initial Access", "start": "09:47", "end": "09:52", "severity": "critical"},
             {"name": "Credential Harvesting", "start": "10:15", "end": "10:45", "severity": "critical"},
             {"name": "Lateral Movement", "start": "11:00", "end": "12:30", "severity": "high"},
             {"name": "Data Access", "start": "12:30", "end": "13:00", "severity": "high"},
             {"name": "Exfiltration", "start": "13:00", "end": "16:00", "severity": "critical"},
             {"name": "Ransomware", "start": "17:30", "end": "18:15", "severity": "critical"}
         ]
     }}
]))

# PAGE 7: Detailed Timeline Events
timeline_events = """<h2>3.2 Detailed Event Timeline</h2>

<h3>09:47:23 - Phishing Email Received</h3>
<p>User jsmith@techcorp.com received a spear-phishing email purportedly from a known vendor. The email contained an Excel attachment with embedded malicious macro.</p>

<h3>09:48:15 - Malicious Macro Executed</h3>
<p>Upon opening the attachment and enabling macros, a PowerShell download cradle was executed, establishing initial foothold.</p>

<h3>09:52:00 - C2 Beacon Established</h3>
<p>Cobalt Strike beacon connected to C2 server at 185.220.101.45. Initial beacon interval set to 20 minutes with 30% jitter.</p>

<h3>10:15:43 - Mimikatz Execution</h3>
<p>Attacker executed Mimikatz to dump credentials from memory. NTLM hashes for 12 domain accounts were captured including service account svc_backup.</p>

<h3>10:45:00 - Privilege Escalation</h3>
<p>Using harvested credentials, attacker gained Domain Admin privileges via Pass-the-Hash attack against the Domain Admins group.</p>

<h3>11:00:00 - Lateral Movement Begins</h3>
<p>Attacker began systematic lateral movement using SMB, RDP, and PSExec. First target: DC-01.</p>"""

pages.append(make_page(7, [
    {"id": "e71", "type": "text", "x": 40, "y": 40, "width": 714, "height": 800,
     "content": timeline_events, "fontSize": 12}
]))

# PAGE 8: More Timeline Events
timeline_events_2 = """<h3>11:30:00 - DC-01 Compromised</h3>
<p>Domain Controller DC-01 was fully compromised. Attacker installed persistent backdoor and began Active Directory reconnaissance.</p>

<h3>12:00:00 - DC-02 Compromised</h3>
<p>Second Domain Controller DC-02 compromised via RDP using harvested Domain Admin credentials.</p>

<h3>12:30:00 - Data Discovery</h3>
<p>Attacker used built-in Windows tools (dir, net view, nltest) to discover network shares and sensitive data locations.</p>

<h3>13:00:00 - Exfiltration Begins</h3>
<p>Using compromised service account svc_backup, attacker began systematic data exfiltration to external server 185.220.101.46.</p>

<h3>14:30:00 - CustomerDB Exfiltration Complete</h3>
<p>Approximately 1.5GB of CustomerDB data containing 150,000 PII records was exfiltrated.</p>

<h3>15:15:00 - FinanceDB Exfiltration Complete</h3>
<p>Approximately 500MB of FinanceDB data containing 50,000 financial records was exfiltrated.</p>

<h3>16:00:00 - R&D Data Exfiltration Complete</h3>
<p>Approximately 300MB of R&D project files (2,500 proprietary documents) exfiltrated. Total exfiltration: 2.3TB.</p>"""

pages.append(make_page(8, [
    {"id": "e81", "type": "text", "x": 40, "y": 40, "width": 714, "height": 800,
     "content": timeline_events_2, "fontSize": 12}
]))

# PAGE 9: Ransomware Deployment
timeline_events_3 = """<h3>17:30:00 - Ransomware Deployment Initiated</h3>
<p>Attacker deployed LockBit 3.0 ransomware via Group Policy Object (GPO) to all domain-joined machines. The deployment script targeted:</p>
<ul>
<li>All workstations in Finance, HR, and Engineering OUs</li>
<li>FileServer-01 containing shared network drives</li>
<li>Backup server (backups were encrypted)</li>
</ul>

<h3>17:45:00 - Encryption in Progress</h3>
<p>Ransomware encryption spread rapidly across the network. Files were encrypted with .lockbit3 extension. Shadow copies were deleted.</p>

<h3>18:15:00 - Encryption Complete</h3>
<p>Approximately 265,000 files encrypted across 47 workstations and 3 servers. Ransom note dropped demanding 50 BTC (approximately $2.3M USD at time of incident).</p>

<h3>18:15:00 - Incident Detected</h3>
<p>IT helpdesk began receiving calls about encrypted files. SOC notified and incident response initiated.</p>

<h2>3.3 Event Volume Analysis</h2>
<p>A total of 503 timeline events were analyzed during the investigation period. Event distribution by severity:</p>"""

pages.append(make_page(9, [
    {"id": "e91", "type": "text", "x": 40, "y": 40, "width": 714, "height": 500,
     "content": timeline_events_3, "fontSize": 12},
    {"id": "e92", "type": "chart", "x": 40, "y": 560, "width": 350, "height": 220,
     "chartType": "pie",
     "chartTitle": "Events by Severity",
     "data": [
         {"name": "LOW", "value": 200, "color": "#22c55e"},
         {"name": "HIGH", "value": 185, "color": "#f59e0b"},
         {"name": "CRITICAL", "value": 118, "color": "#ef4444"}
     ]},
    {"id": "e93", "type": "chart", "x": 410, "y": 560, "width": 350, "height": 220,
     "chartType": "bar",
     "chartTitle": "Events by Phase",
     "data": [
         {"name": "Initial Access", "value": 45},
         {"name": "Credential", "value": 65},
         {"name": "Lateral", "value": 120},
         {"name": "Data Access", "value": 85},
         {"name": "Exfiltration", "value": 100},
         {"name": "Ransomware", "value": 88}
     ]}
]))

# ===== PAGES 10-14: Anomaly Detection =====
anomaly_intro = """<p>This section presents the results of anomaly detection analysis using SHAP (SHapley Additive exPlanations) methodology to identify and explain anomalous events in the timeline data.</p>

<h2>4.1 Anomaly Detection Methodology</h2>
<p>Our analysis employed a machine learning-based anomaly detection model trained on baseline network behavior. The model uses the following features:</p>
<ul>
<li>Event frequency and timing patterns</li>
<li>User behavior baselines</li>
<li>Network traffic volume and patterns</li>
<li>Process execution anomalies</li>
<li>Authentication pattern deviations</li>
</ul>

<h2>4.2 Overall Anomaly Statistics</h2>
<p>Of 503 total timeline events analyzed, 256 (50.9%) were flagged as anomalous based on a threshold score of 0.7.</p>"""

pages.append(make_page(10, [
    {"id": "e101", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>4. Anomaly Detection Results</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e102", "type": "text", "x": 40, "y": 100, "width": 714, "height": 300,
     "content": anomaly_intro, "fontSize": 12},
    {"id": "e103", "type": "chart", "x": 40, "y": 420, "width": 714, "height": 300,
     "chartType": "scatter",
     "chartTitle": "Anomaly Score Distribution",
     "data": {"x_label": "Event Index", "y_label": "Anomaly Score", "threshold": 0.7}}
]))

# PAGE 11: SHAP Analysis
shap_content = """<h2>4.3 SHAP Feature Contribution Analysis</h2>
<p>The SHAP waterfall chart below shows the contribution of each feature to the anomaly score for the highest-scoring event (Event #247 - Mimikatz execution).</p>

<h3>Key Contributing Factors:</h3>
<ul>
<li><strong>Process Name (lsass.exe access):</strong> +0.35 contribution - Accessing LSASS is a strong indicator of credential dumping</li>
<li><strong>Time of Day (off-hours):</strong> +0.18 contribution - Event occurred outside normal business hours</li>
<li><strong>User Account (service account):</strong> +0.15 contribution - Service account used for interactive logon</li>
<li><strong>Source IP (internal):</strong> -0.08 contribution - Event originated from known internal IP</li>
<li><strong>Event Volume:</strong> +0.12 contribution - Unusually high number of related events</li>
</ul>"""

pages.append(make_page(11, [
    {"id": "e111", "type": "text", "x": 40, "y": 40, "width": 714, "height": 280,
     "content": shap_content, "fontSize": 12},
    {"id": "e112", "type": "chart", "x": 40, "y": 340, "width": 714, "height": 350,
     "chartType": "shap-waterfall",
     "chartTitle": "SHAP Feature Contributions (Event #247)",
     "data": {
         "base_value": 0.15,
         "features": [
             {"name": "Process (lsass.exe)", "contribution": 0.35, "value": "lsass.exe"},
             {"name": "Time of Day", "contribution": 0.18, "value": "10:15 UTC"},
             {"name": "User Account", "contribution": 0.15, "value": "svc_backup"},
             {"name": "Event Volume", "contribution": 0.12, "value": "45 events/min"},
             {"name": "Source IP", "contribution": -0.08, "value": "10.0.1.50"}
         ],
         "output_value": 0.87
     }}
]))

# PAGE 12: Top Anomalies
top_anomalies = """<h2>4.4 Top 10 Anomalous Events</h2>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Rank</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Event ID</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Time</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Description</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Score</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>1</td><td style='padding:8px;border:1px solid #ddd'>EVT-247</td><td style='padding:8px;border:1px solid #ddd'>10:15:43</td><td style='padding:8px;border:1px solid #ddd'>Mimikatz execution detected</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.97</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>2</td><td style='padding:8px;border:1px solid #ddd'>EVT-312</td><td style='padding:8px;border:1px solid #ddd'>11:30:22</td><td style='padding:8px;border:1px solid #ddd'>PSExec lateral movement</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.95</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>3</td><td style='padding:8px;border:1px solid #ddd'>EVT-445</td><td style='padding:8px;border:1px solid #ddd'>13:15:00</td><td style='padding:8px;border:1px solid #ddd'>Large data transfer initiated</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.94</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>4</td><td style='padding:8px;border:1px solid #ddd'>EVT-501</td><td style='padding:8px;border:1px solid #ddd'>17:30:00</td><td style='padding:8px;border:1px solid #ddd'>Ransomware deployment via GPO</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.93</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>5</td><td style='padding:8px;border:1px solid #ddd'>EVT-156</td><td style='padding:8px;border:1px solid #ddd'>09:48:15</td><td style='padding:8px;border:1px solid #ddd'>Macro execution from email</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.92</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>6</td><td style='padding:8px;border:1px solid #ddd'>EVT-289</td><td style='padding:8px;border:1px solid #ddd'>10:52:00</td><td style='padding:8px;border:1px solid #ddd'>C2 beacon established</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.89</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>7</td><td style='padding:8px;border:1px solid #ddd'>EVT-378</td><td style='padding:8px;border:1px solid #ddd'>12:15:30</td><td style='padding:8px;border:1px solid #ddd'>RDP to domain controller</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.87</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>8</td><td style='padding:8px;border:1px solid #ddd'>EVT-412</td><td style='padding:8px;border:1px solid #ddd'>12:45:00</td><td style='padding:8px;border:1px solid #ddd'>Database query spike</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.85</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>9</td><td style='padding:8px;border:1px solid #ddd'>EVT-489</td><td style='padding:8px;border:1px solid #ddd'>15:30:00</td><td style='padding:8px;border:1px solid #ddd'>Shadow copy deletion</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.83</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>10</td><td style='padding:8px;border:1px solid #ddd'>EVT-267</td><td style='padding:8px;border:1px solid #ddd'>10:30:15</td><td style='padding:8px;border:1px solid #ddd'>Pass-the-Hash detected</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.81</td></tr>
</table>"""

pages.append(make_page(12, [
    {"id": "e121", "type": "text", "x": 40, "y": 40, "width": 714, "height": 700,
     "content": top_anomalies, "fontSize": 11}
]))

# PAGE 13-14: Anomaly Distribution Charts
pages.append(make_page(13, [
    {"id": "e131", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h2>4.5 Anomaly Score Distribution by Phase</h2>", "fontSize": 18, "fontWeight": "bold"},
    {"id": "e132", "type": "chart", "x": 40, "y": 100, "width": 714, "height": 300,
     "chartType": "heatmap",
     "chartTitle": "Anomaly Heatmap by Time and Category",
     "data": {"rows": ["Initial Access", "Credential", "Lateral", "Data Access", "Exfil", "Ransomware"],
              "cols": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]}},
    {"id": "e133", "type": "text", "x": 40, "y": 420, "width": 714, "height": 100,
     "content": "<h2>4.6 Anomaly Trends</h2><p>The analysis shows clear clustering of high-severity anomalies around key attack phases. The credential harvesting phase (10:00-11:00) and ransomware deployment phase (17:00-18:00) show the highest concentration of anomalous activity.</p>", "fontSize": 12},
    {"id": "e134", "type": "chart", "x": 40, "y": 540, "width": 714, "height": 250,
     "chartType": "area-chart",
     "chartTitle": "Anomaly Score Over Time",
     "data": {"x_label": "Time (UTC)", "y_label": "Avg Anomaly Score"}}
]))

# PAGE 14: Anomaly Summary
anomaly_summary = """<h2>4.7 Anomaly Detection Summary</h2>

<h3>Key Findings:</h3>
<ul>
<li>50.9% of all events (256 of 503) exceeded the anomaly threshold of 0.7</li>
<li>The highest anomaly scores were associated with credential harvesting and ransomware deployment</li>
<li>SHAP analysis identified process execution patterns as the strongest predictor of malicious activity</li>
<li>Off-hours activity contributed significantly to anomaly scores</li>
</ul>

<h3>Detection Performance:</h3>
<ul>
<li>True Positive Rate: 94.7%</li>
<li>False Positive Rate: 8.2%</li>
<li>Precision: 0.92</li>
<li>Recall: 0.95</li>
<li>F1 Score: 0.93</li>
</ul>

<h3>Recommendations:</h3>
<p>Based on the anomaly detection results, we recommend:</p>
<ol>
<li>Implementing real-time monitoring of LSASS access patterns</li>
<li>Establishing behavioral baselines for service account activity</li>
<li>Deploying EDR with credential dumping detection capabilities</li>
<li>Implementing network segmentation to limit lateral movement</li>
</ol>"""

pages.append(make_page(14, [
    {"id": "e141", "type": "text", "x": 40, "y": 40, "width": 714, "height": 600,
     "content": anomaly_summary, "fontSize": 12}
]))

# ===== PAGES 15-19: Network Traffic Analysis =====
network_intro = """<p>This section provides detailed analysis of network traffic patterns during the incident. A total of 200 network flows were analyzed, with 50 flows (25%) identified as suspicious.</p>

<h2>5.1 Traffic Overview</h2>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Category</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Flows</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Percentage</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Data Volume</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Normal Traffic</td><td style='padding:8px;border:1px solid #ddd'>150</td><td style='padding:8px;border:1px solid #ddd'>75%</td><td style='padding:8px;border:1px solid #ddd'>1.2 GB</td></tr>
<tr style='background:#fef2f2'><td style='padding:8px;border:1px solid #ddd'>C2 Beacons</td><td style='padding:8px;border:1px solid #ddd'>30</td><td style='padding:8px;border:1px solid #ddd'>15%</td><td style='padding:8px;border:1px solid #ddd'>45 MB</td></tr>
<tr style='background:#fef2f2'><td style='padding:8px;border:1px solid #ddd'>Data Exfiltration</td><td style='padding:8px;border:1px solid #ddd'>20</td><td style='padding:8px;border:1px solid #ddd'>10%</td><td style='padding:8px;border:1px solid #ddd'>2.3 TB</td></tr>
</table>"""

pages.append(make_page(15, [
    {"id": "e151", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>5. Network Traffic Analysis</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e152", "type": "text", "x": 40, "y": 100, "width": 714, "height": 300,
     "content": network_intro, "fontSize": 12},
    {"id": "e153", "type": "chart", "x": 40, "y": 420, "width": 350, "height": 300,
     "chartType": "pie",
     "chartTitle": "Network Flow Distribution",
     "data": [
         {"name": "Normal", "value": 150, "color": "#22c55e"},
         {"name": "C2 Beacon", "value": 30, "color": "#f59e0b"},
         {"name": "Exfiltration", "value": 20, "color": "#ef4444"}
     ]},
    {"id": "e154", "type": "chart", "x": 410, "y": 420, "width": 350, "height": 300,
     "chartType": "bar",
     "chartTitle": "Data Volume by Type",
     "data": [
         {"name": "Normal", "value": 1200},
         {"name": "C2", "value": 45},
         {"name": "Exfil", "value": 2300000}
     ]}
]))

# PAGE 16: C2 Analysis
c2_analysis = """<h2>5.2 Command & Control Analysis</h2>

<h3>C2 Server Details:</h3>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>IP Address</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Port</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Protocol</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Geolocation</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Purpose</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>185.220.101.45</td><td style='padding:8px;border:1px solid #ddd'>443</td><td style='padding:8px;border:1px solid #ddd'>HTTPS</td><td style='padding:8px;border:1px solid #ddd'>Russia</td><td style='padding:8px;border:1px solid #ddd'>Primary C2</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>185.220.101.46</td><td style='padding:8px;border:1px solid #ddd'>443</td><td style='padding:8px;border:1px solid #ddd'>HTTPS</td><td style='padding:8px;border:1px solid #ddd'>Russia</td><td style='padding:8px;border:1px solid #ddd'>Exfiltration</td></tr>
</table>

<h3>Beacon Characteristics:</h3>
<ul>
<li><strong>Beacon Interval:</strong> 20 minutes with 30% jitter</li>
<li><strong>Protocol:</strong> HTTPS with self-signed certificate</li>
<li><strong>Total Beacons:</strong> 230 over 7.5 hours</li>
<li><strong>Affected Hosts:</strong> 5 internal systems</li>
</ul>

<h3>Certificate Analysis:</h3>
<p>The C2 server used a self-signed certificate with the following characteristics:</p>
<ul>
<li>CN: mail.example.com (deceptive naming)</li>
<li>Valid: 2025-01-01 to 2030-01-01</li>
<li>SHA-256: a3b7c9d2e4f6a8b0c2d4e6f8a0b2c4d6...</li>
</ul>"""

pages.append(make_page(16, [
    {"id": "e161", "type": "text", "x": 40, "y": 40, "width": 714, "height": 700,
     "content": c2_analysis, "fontSize": 12}
]))

# PAGE 17: Exfiltration Analysis
exfil_analysis = """<h2>5.3 Data Exfiltration Analysis</h2>

<p>Data exfiltration occurred over a 3-hour period (13:00-16:00 UTC) using the compromised service account svc_backup.</p>

<h3>Exfiltration Timeline:</h3>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Time</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Source</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Data Type</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Volume</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>13:00-14:30</td><td style='padding:8px;border:1px solid #ddd'>CustomerDB</td><td style='padding:8px;border:1px solid #ddd'>PII</td><td style='padding:8px;border:1px solid #ddd'>1.5 GB</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>14:30-15:15</td><td style='padding:8px;border:1px solid #ddd'>FinanceDB</td><td style='padding:8px;border:1px solid #ddd'>Financial</td><td style='padding:8px;border:1px solid #ddd'>500 MB</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>15:15-16:00</td><td style='padding:8px;border:1px solid #ddd'>R&D Share</td><td style='padding:8px;border:1px solid #ddd'>IP</td><td style='padding:8px;border:1px solid #ddd'>300 MB</td></tr>
</table>

<h3>Exfiltration Method:</h3>
<ul>
<li>Data was compressed and encrypted before transmission</li>
<li>HTTPS POST requests to 185.220.101.46:443</li>
<li>Chunk size: 50MB per transfer</li>
<li>Total transfers: 47 successful uploads</li>
</ul>"""

pages.append(make_page(17, [
    {"id": "e171", "type": "text", "x": 40, "y": 40, "width": 714, "height": 400,
     "content": exfil_analysis, "fontSize": 12},
    {"id": "e172", "type": "chart", "x": 40, "y": 460, "width": 714, "height": 300,
     "chartType": "network-flow",
     "chartTitle": "Network Flow Diagram",
     "data": {
         "nodes": ["WS-100", "DC-01", "FileServer", "185.220.101.45", "185.220.101.46"],
         "flows": [
             {"from": "WS-100", "to": "185.220.101.45", "label": "C2 Beacon"},
             {"from": "DC-01", "to": "185.220.101.45", "label": "C2 Beacon"},
             {"from": "FileServer", "to": "185.220.101.46", "label": "Exfiltration"}
         ]
     }}
]))

# PAGE 18-19: Lateral Movement Analysis
lateral_analysis = """<h2>5.4 Lateral Movement Patterns</h2>

<p>The attacker employed multiple lateral movement techniques to propagate across the network:</p>

<h3>Techniques Used:</h3>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Technique</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>MITRE ATT&CK</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Count</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Targets</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>SMB/Windows Admin Shares</td><td style='padding:8px;border:1px solid #ddd'>T1021.002</td><td style='padding:8px;border:1px solid #ddd'>47</td><td style='padding:8px;border:1px solid #ddd'>All workstations</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Remote Desktop Protocol</td><td style='padding:8px;border:1px solid #ddd'>T1021.001</td><td style='padding:8px;border:1px solid #ddd'>8</td><td style='padding:8px;border:1px solid #ddd'>Servers, DCs</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>PSExec</td><td style='padding:8px;border:1px solid #ddd'>T1570</td><td style='padding:8px;border:1px solid #ddd'>12</td><td style='padding:8px;border:1px solid #ddd'>Critical servers</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Pass-the-Hash</td><td style='padding:8px;border:1px solid #ddd'>T1550.002</td><td style='padding:8px;border:1px solid #ddd'>15</td><td style='padding:8px;border:1px solid #ddd'>Domain controllers</td></tr>
</table>

<h3>Movement Timeline:</h3>
<p>The lateral movement phase occurred between 11:00 and 12:30 UTC, with the attacker systematically compromising systems in the following order:</p>
<ol>
<li>WS-100 (Patient Zero) → DC-01 via SMB</li>
<li>DC-01 → DC-02 via RDP</li>
<li>DC-01 → FileServer-01 via PSExec</li>
<li>DC-02 → DB-Server via SQL Client</li>
</ol>"""

pages.append(make_page(18, [
    {"id": "e181", "type": "text", "x": 40, "y": 40, "width": 714, "height": 500,
     "content": lateral_analysis, "fontSize": 12},
    {"id": "e182", "type": "chart", "x": 40, "y": 560, "width": 714, "height": 240,
     "chartType": "correlation-graph",
     "chartTitle": "Lateral Movement Path",
     "data": {
         "nodes": [
             {"id": "ws100", "label": "WS-100", "type": "workstation"},
             {"id": "dc01", "label": "DC-01", "type": "server"},
             {"id": "dc02", "label": "DC-02", "type": "server"},
             {"id": "fs01", "label": "FileServer", "type": "server"},
             {"id": "db01", "label": "DB-Server", "type": "server"}
         ],
         "edges": [
             {"source": "ws100", "target": "dc01", "label": "SMB"},
             {"source": "dc01", "target": "dc02", "label": "RDP"},
             {"source": "dc01", "target": "fs01", "label": "PSExec"},
             {"source": "dc02", "target": "db01", "label": "SQL"}
         ]
     }}
]))

# PAGE 19: Network Summary
network_summary = """<h2>5.5 Network Analysis Summary</h2>

<h3>Key Findings:</h3>
<ul>
<li><strong>C2 Infrastructure:</strong> Two Russian IPs used for command and control (185.220.101.45) and data exfiltration (185.220.101.46)</li>
<li><strong>Exfiltration Volume:</strong> 2.3TB of sensitive data exfiltrated over 3 hours</li>
<li><strong>Lateral Movement:</strong> Extensive use of SMB, RDP, and PSExec for network propagation</li>
<li><strong>Detection Gap:</strong> C2 traffic blended with legitimate HTTPS traffic, evading basic detection</li>
</ul>

<h3>Indicators of Compromise (IOCs):</h3>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Type</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Value</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Description</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>IP</td><td style='padding:8px;border:1px solid #ddd'>185.220.101.45</td><td style='padding:8px;border:1px solid #ddd'>C2 Server</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>IP</td><td style='padding:8px;border:1px solid #ddd'>185.220.101.46</td><td style='padding:8px;border:1px solid #ddd'>Exfil Server</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Domain</td><td style='padding:8px;border:1px solid #ddd'>mail.example.com</td><td style='padding:8px;border:1px solid #ddd'>C2 Cert CN</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Hash</td><td style='padding:8px;border:1px solid #ddd'>a3b7c9d2e4f6...</td><td style='padding:8px;border:1px solid #ddd'>Malware SHA256</td></tr>
</table>

<h3>Recommendations:</h3>
<ol>
<li>Block identified IOCs at network perimeter</li>
<li>Implement network segmentation to limit lateral movement</li>
<li>Deploy SSL/TLS inspection for outbound traffic</li>
<li>Enable enhanced logging for SMB and RDP connections</li>
</ol>"""

pages.append(make_page(19, [
    {"id": "e191", "type": "text", "x": 40, "y": 40, "width": 714, "height": 700,
     "content": network_summary, "fontSize": 12}
]))

# ===== PAGES 20-24: Correlation Analysis =====
correlation_intro = """<p>This section presents the correlation analysis results, identifying relationships between entities, events, and attack patterns.</p>

<h2>6.1 Entity Relationship Analysis</h2>
<p>Our analysis identified 15 key entities involved in the incident:</p>
<ul>
<li>4 User/Actor entities (including attacker and compromised accounts)</li>
<li>5 System entities (workstations and servers)</li>
<li>2 External IP addresses (C2 and exfiltration servers)</li>
<li>3 Data entities (databases and file shares)</li>
<li>1 Malware entity (LockBit 3.0)</li>
</ul>

<p>A total of 20 relationships were mapped between these entities, representing the complete attack chain from initial access to impact.</p>"""

pages.append(make_page(20, [
    {"id": "e201", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>6. Correlation Analysis</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e202", "type": "text", "x": 40, "y": 100, "width": 714, "height": 250,
     "content": correlation_intro, "fontSize": 12},
    {"id": "e203", "type": "chart", "x": 40, "y": 370, "width": 714, "height": 400,
     "chartType": "correlation-graph",
     "chartTitle": "Attack Correlation Graph",
     "data": {
         "nodes": [
             {"id": "attacker", "label": "Attacker", "type": "threat", "score": 0.99},
             {"id": "jsmith", "label": "jsmith", "type": "user", "score": 0.85},
             {"id": "ws100", "label": "WS-100", "type": "host", "score": 0.99},
             {"id": "dc01", "label": "DC-01", "type": "server", "score": 0.95},
             {"id": "c2", "label": "C2 Server", "type": "external", "score": 0.99},
             {"id": "exfil", "label": "Exfil Server", "type": "external", "score": 0.98},
             {"id": "lockbit", "label": "LockBit 3.0", "type": "malware", "score": 0.99}
         ],
         "edges": [
             {"source": "attacker", "target": "jsmith", "label": "PHISHED", "weight": 0.95},
             {"source": "jsmith", "target": "ws100", "label": "COMPROMISED", "weight": 0.99},
             {"source": "ws100", "target": "dc01", "label": "LATERAL", "weight": 0.90},
             {"source": "ws100", "target": "c2", "label": "C2", "weight": 0.98},
             {"source": "dc01", "target": "exfil", "label": "EXFIL", "weight": 0.97},
             {"source": "attacker", "target": "lockbit", "label": "DEPLOYED", "weight": 0.99}
         ]
     }}
]))

# Add more pages to reach 40...
# PAGE 21-24: More correlation details

for page_num in range(21, 25):
    section_content = f"""<h2>6.{page_num - 19} Correlation Details (Page {page_num})</h2>
<p>This page contains additional correlation analysis details including entity scoring, relationship strength analysis, and confidence calculations.</p>

<h3>Entity Scoring Summary</h3>
<p>Each entity in the correlation graph is assigned a threat score based on its role in the attack chain and the confidence of the evidence linking it to malicious activity.</p>

<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Entity</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Type</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Score</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Confidence</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Unknown Attacker</td><td style='padding:8px;border:1px solid #ddd'>ATTACKER</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.99</td><td style='padding:8px;border:1px solid #ddd'>High</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>LockBit 3.0</td><td style='padding:8px;border:1px solid #ddd'>MALWARE</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.99</td><td style='padding:8px;border:1px solid #ddd'>High</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>185.220.101.45</td><td style='padding:8px;border:1px solid #ddd'>IP</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.99</td><td style='padding:8px;border:1px solid #ddd'>High</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>WS-100</td><td style='padding:8px;border:1px solid #ddd'>HOST</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.99</td><td style='padding:8px;border:1px solid #ddd'>High</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>DC-01</td><td style='padding:8px;border:1px solid #ddd'>HOST</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.95</td><td style='padding:8px;border:1px solid #ddd'>High</td></tr>
</table>"""
    
    pages.append(make_page(page_num, [
        {"id": f"e{page_num}1", "type": "text", "x": 40, "y": 40, "width": 714, "height": 700,
         "content": section_content, "fontSize": 12}
    ]))

# PAGES 25-27: MITRE ATT&CK Mapping
mitre_content = """<h2>7.1 MITRE ATT&CK Framework Mapping</h2>
<p>The following tactics and techniques were observed during this incident:</p>

<table style='width:100%;border-collapse:collapse;font-size:11px'>
<tr style='background:#f3f4f6'>
<th style='padding:6px;text-align:left;border:1px solid #ddd'>Tactic</th>
<th style='padding:6px;text-align:left;border:1px solid #ddd'>Technique</th>
<th style='padding:6px;text-align:left;border:1px solid #ddd'>ID</th>
<th style='padding:6px;text-align:left;border:1px solid #ddd'>Evidence</th>
</tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Initial Access</td><td style='padding:6px;border:1px solid #ddd'>Phishing: Spear-Phishing Attachment</td><td style='padding:6px;border:1px solid #ddd'>T1566.001</td><td style='padding:6px;border:1px solid #ddd'>Malicious Excel macro</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Execution</td><td style='padding:6px;border:1px solid #ddd'>Command and Scripting: PowerShell</td><td style='padding:6px;border:1px solid #ddd'>T1059.001</td><td style='padding:6px;border:1px solid #ddd'>Download cradle</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Persistence</td><td style='padding:6px;border:1px solid #ddd'>Boot or Logon: Registry Run Keys</td><td style='padding:6px;border:1px solid #ddd'>T1547.001</td><td style='padding:6px;border:1px solid #ddd'>Cobalt Strike persistence</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Privilege Escalation</td><td style='padding:6px;border:1px solid #ddd'>Valid Accounts: Domain Accounts</td><td style='padding:6px;border:1px solid #ddd'>T1078.002</td><td style='padding:6px;border:1px solid #ddd'>Compromised admin accounts</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Defense Evasion</td><td style='padding:6px;border:1px solid #ddd'>Indicator Removal: Clear Windows Event Logs</td><td style='padding:6px;border:1px solid #ddd'>T1070.001</td><td style='padding:6px;border:1px solid #ddd'>Log gaps detected</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Credential Access</td><td style='padding:6px;border:1px solid #ddd'>OS Credential Dumping: LSASS Memory</td><td style='padding:6px;border:1px solid #ddd'>T1003.001</td><td style='padding:6px;border:1px solid #ddd'>Mimikatz execution</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Discovery</td><td style='padding:6px;border:1px solid #ddd'>Network Share Discovery</td><td style='padding:6px;border:1px solid #ddd'>T1135</td><td style='padding:6px;border:1px solid #ddd'>net view commands</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Lateral Movement</td><td style='padding:6px;border:1px solid #ddd'>Remote Services: SMB/Windows Admin Shares</td><td style='padding:6px;border:1px solid #ddd'>T1021.002</td><td style='padding:6px;border:1px solid #ddd'>47 SMB connections</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Collection</td><td style='padding:6px;border:1px solid #ddd'>Data from Network Shared Drive</td><td style='padding:6px;border:1px solid #ddd'>T1039</td><td style='padding:6px;border:1px solid #ddd'>File server access</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Command and Control</td><td style='padding:6px;border:1px solid #ddd'>Application Layer Protocol: Web Protocols</td><td style='padding:6px;border:1px solid #ddd'>T1071.001</td><td style='padding:6px;border:1px solid #ddd'>HTTPS C2 traffic</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Exfiltration</td><td style='padding:6px;border:1px solid #ddd'>Exfiltration Over C2 Channel</td><td style='padding:6px;border:1px solid #ddd'>T1041</td><td style='padding:6px;border:1px solid #ddd'>2.3TB exfiltrated</td></tr>
<tr><td style='padding:6px;border:1px solid #ddd'>Impact</td><td style='padding:6px;border:1px solid #ddd'>Data Encrypted for Impact</td><td style='padding:6px;border:1px solid #ddd'>T1486</td><td style='padding:6px;border:1px solid #ddd'>LockBit ransomware</td></tr>
</table>"""

pages.append(make_page(25, [
    {"id": "e251", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>7. MITRE ATT&CK Mapping</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e252", "type": "text", "x": 40, "y": 100, "width": 714, "height": 700,
     "content": mitre_content, "fontSize": 11}
]))

# Pages 26-27: More MITRE details
for page_num in range(26, 28):
    pages.append(make_page(page_num, [
        {"id": f"e{page_num}1", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
         "content": f"<h2>7.{page_num - 24} MITRE ATT&CK Details (continued)</h2>", "fontSize": 18, "fontWeight": "bold"},
        {"id": f"e{page_num}2", "type": "text", "x": 40, "y": 100, "width": 714, "height": 400,
         "content": f"<p>Additional MITRE ATT&CK mapping details and analysis for page {page_num}. This includes technique variants, sub-techniques, and detection opportunities.</p>", "fontSize": 12}
    ]))

# PAGES 28-31: Depth Assessment
depth_content = """<h2>8.1 Compromise Depth Assessment</h2>
<p>The depth assessment evaluates the extent of compromise across four key dimensions:</p>

<h3>Assessment Scores:</h3>
<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Dimension</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Score</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Rating</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Description</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Account Compromise</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.95</td><td style='padding:8px;border:1px solid #ddd'>Critical</td><td style='padding:8px;border:1px solid #ddd'>Domain Admin access achieved</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>System Compromise</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.87</td><td style='padding:8px;border:1px solid #ddd'>High</td><td style='padding:8px;border:1px solid #ddd'>50+ systems affected</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Data Compromise</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>0.92</td><td style='padding:8px;border:1px solid #ddd'>Critical</td><td style='padding:8px;border:1px solid #ddd'>2.3TB exfiltrated</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Control Compromise</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>0.78</td><td style='padding:8px;border:1px solid #ddd'>High</td><td style='padding:8px;border:1px solid #ddd'>AD partially controlled</td></tr>
</table>"""

pages.append(make_page(28, [
    {"id": "e281", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>8. Depth Assessment</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e282", "type": "text", "x": 40, "y": 100, "width": 714, "height": 350,
     "content": depth_content, "fontSize": 12},
    {"id": "e283", "type": "chart", "x": 40, "y": 470, "width": 350, "height": 300,
     "chartType": "gauge",
     "chartTitle": "Overall Compromise Score",
     "data": {"value": 0.88, "max": 1.0, "thresholds": [0.3, 0.6, 0.8]}},
    {"id": "e284", "type": "chart", "x": 410, "y": 470, "width": 350, "height": 300,
     "chartType": "bar",
     "chartTitle": "Depth by Dimension",
     "data": [
         {"name": "Account", "value": 0.95},
         {"name": "System", "value": 0.87},
         {"name": "Data", "value": 0.92},
         {"name": "Control", "value": 0.78}
     ]}
]))

# Pages 29-31: Depth details
for page_num in range(29, 32):
    pages.append(make_page(page_num, [
        {"id": f"e{page_num}1", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
         "content": f"<h2>8.{page_num - 27} Depth Assessment Details</h2>", "fontSize": 18, "fontWeight": "bold"},
        {"id": f"e{page_num}2", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
         "content": f"<p>Detailed depth assessment analysis for page {page_num}.</p>", "fontSize": 12}
    ]))

# PAGES 32-35: Hypothesis Analysis
hypothesis_content = """<h2>9.1 Investigation Hypotheses</h2>
<p>The following hypotheses were tested during the investigation:</p>

<table style='width:100%;border-collapse:collapse'>
<tr style='background:#f3f4f6'>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Hypothesis</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Predicted</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Actual</th>
<th style='padding:8px;text-align:left;border:1px solid #ddd'>Status</th>
</tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Attack originated from phishing email</td><td style='padding:8px;border:1px solid #ddd'>0.95</td><td style='padding:8px;border:1px solid #ddd'>0.98</td><td style='padding:8px;border:1px solid #ddd;color:#22c55e'>Confirmed</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>Mimikatz used for credential harvesting</td><td style='padding:8px;border:1px solid #ddd'>0.90</td><td style='padding:8px;border:1px solid #ddd'>0.95</td><td style='padding:8px;border:1px solid #ddd;color:#22c55e'>Confirmed</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>RDP used for lateral movement</td><td style='padding:8px;border:1px solid #ddd'>0.75</td><td style='padding:8px;border:1px solid #ddd'>0.60</td><td style='padding:8px;border:1px solid #ddd;color:#f59e0b'>Partial</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>DNS tunneling for exfiltration</td><td style='padding:8px;border:1px solid #ddd'>0.40</td><td style='padding:8px;border:1px solid #ddd'>0.10</td><td style='padding:8px;border:1px solid #ddd;color:#ef4444'>Rejected</td></tr>
<tr><td style='padding:8px;border:1px solid #ddd'>LockBit ransomware variant</td><td style='padding:8px;border:1px solid #ddd'>0.92</td><td style='padding:8px;border:1px solid #ddd'>0.99</td><td style='padding:8px;border:1px solid #ddd;color:#22c55e'>Confirmed</td></tr>
</table>

<h3>Calibration Score: 0.87</h3>
<p>The investigation team demonstrated good calibration between predicted confidence levels and actual outcomes.</p>"""

pages.append(make_page(32, [
    {"id": "e321", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>9. Hypothesis Analysis</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e322", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": hypothesis_content, "fontSize": 12}
]))

# Pages 33-35
for page_num in range(33, 36):
    pages.append(make_page(page_num, [
        {"id": f"e{page_num}1", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
         "content": f"<h2>9.{page_num - 31} Hypothesis Details</h2>", "fontSize": 18, "fontWeight": "bold"},
        {"id": f"e{page_num}2", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
         "content": f"<p>Detailed hypothesis analysis for page {page_num}.</p>", "fontSize": 12}
    ]))

# PAGES 36-37: Recommendations
recommendations = """<h2>10.1 Immediate Actions</h2>
<ol>
<li><strong>Network Isolation:</strong> Isolate affected systems from the network</li>
<li><strong>Password Reset:</strong> Force password reset for all compromised accounts</li>
<li><strong>IOC Blocking:</strong> Block identified C2 and exfiltration IPs at perimeter</li>
<li><strong>Forensic Preservation:</strong> Preserve evidence from affected systems</li>
</ol>

<h2>10.2 Short-term Improvements</h2>
<ol>
<li><strong>EDR Deployment:</strong> Deploy EDR solution with credential dumping detection</li>
<li><strong>MFA Implementation:</strong> Implement MFA for all privileged accounts</li>
<li><strong>Network Segmentation:</strong> Implement microsegmentation for critical systems</li>
<li><strong>Backup Review:</strong> Implement air-gapped backup solution</li>
</ol>

<h2>10.3 Long-term Strategy</h2>
<ol>
<li><strong>Security Awareness:</strong> Enhanced phishing awareness training</li>
<li><strong>Zero Trust:</strong> Implement zero trust architecture</li>
<li><strong>24/7 SOC:</strong> Establish round-the-clock security monitoring</li>
<li><strong>Incident Response Plan:</strong> Develop and test incident response procedures</li>
</ol>"""

pages.append(make_page(36, [
    {"id": "e361", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>10. Recommendations</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e362", "type": "text", "x": 40, "y": 100, "width": 714, "height": 700,
     "content": recommendations, "fontSize": 12}
]))

pages.append(make_page(37, [
    {"id": "e371", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h2>10.4 Recommendations Summary</h2>", "fontSize": 18, "fontWeight": "bold"},
    {"id": "e372", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": "<p>Additional recommendations and implementation priorities.</p>", "fontSize": 12}
]))

# PAGES 38-40: Appendices
pages.append(make_page(38, [
    {"id": "e381", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h1>11. Appendices</h1>", "fontSize": 24, "fontWeight": "bold"},
    {"id": "e382", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": "<h2>Appendix A: Indicators of Compromise</h2><p>Complete list of IOCs identified during the investigation.</p>", "fontSize": 12}
]))

pages.append(make_page(39, [
    {"id": "e391", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h2>Appendix B: Evidence Registry</h2>", "fontSize": 18, "fontWeight": "bold"},
    {"id": "e392", "type": "text", "x": 40, "y": 100, "width": 714, "height": 600,
     "content": "<p>Complete registry of all evidence collected during the investigation.</p>", "fontSize": 12}
]))

pages.append(make_page(40, [
    {"id": "e401", "type": "text", "x": 40, "y": 40, "width": 714, "height": 40,
     "content": "<h2>Appendix C: Methodology</h2>", "fontSize": 18, "fontWeight": "bold"},
    {"id": "e402", "type": "text", "x": 40, "y": 100, "width": 714, "height": 400,
     "content": "<p>Description of investigation methodology and tools used.</p><p>This report was generated using the NFLIP (Next-gen Forensic Log Investigation Platform) multi-agent architecture.</p>", "fontSize": 12},
    {"id": "e403", "type": "text", "x": 40, "y": 600, "width": 714, "height": 100,
     "content": "<p style='text-align:center;color:#666'>--- END OF REPORT ---</p><p style='text-align:center;font-size:10px'>Generated by NFLIP Report Studio | DEMO-RANSOMWARE-001</p>", "fontSize": 12, "textAlign": "center"}
]))

# Build complete AST
ast = {
    "version": "2.0",
    "documentId": doc_id,
    "caseId": case_id,
    "title": "TechCorp Ransomware Investigation Report",
    "pageSize": {"width": 794, "height": 1123},
    "pages": pages,
    "metadata": {
        "author": "NFLIP Investigation Team",
        "created": datetime.now().isoformat(),
        "status": "draft",
        "classification": "CONFIDENTIAL"
    }
}

# Insert into database
db = open_vault(case_id)
db.execute("""
    INSERT INTO report_documents (id, title, ast, meta, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, 'draft', now(), now())
""", [
    doc_id,
    "TechCorp Ransomware Investigation Report",
    json.dumps(ast),
    json.dumps({"case_id": case_id, "pages": len(pages)})
])
db.commit()
db.close()

print(f"Report document created: {doc_id}")
print(f"Total pages: {len(pages)}")
print(f"Case ID: {case_id}")
print("Status: draft")
