"""
Generate comprehensive demo data for DEMO-RANSOMWARE-001 case.
This creates 500+ events across all analysis modules.
"""

import sys
sys.path.insert(0, '.')

import json
import uuid
import random
import hashlib
from datetime import datetime, timezone, timedelta

from operation_room.database import open_vault

def main():
    case_id = 'DEMO-RANSOMWARE-001'
    db = open_vault(case_id)
    
    # Base timestamp for the incident
    base_time = datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    
    # Demo actors
    actors = [
        'jsmith@techcorp.com',
        'mwilliams@techcorp.com', 
        'admin@techcorp.com',
        'svc_backup@techcorp.com',
        'SYSTEM',
        'NT AUTHORITY\\SYSTEM',
        'TECHCORP\\Domain Admins',
        'unknown_attacker'
    ]
    
    # Demo IPs
    internal_ips = ['10.0.1.50', '10.0.1.51', '10.0.1.100', '10.0.2.10', '10.0.2.11', '192.168.1.5']
    external_ips = ['185.220.101.45', '185.220.101.46', '45.33.32.156', '198.51.100.1']
    dc_ips = ['10.0.0.1', '10.0.0.2', '10.0.0.3']
    
    # Event sources
    sources = ['Windows Security', 'AWS CloudTrail', 'Firewall', 'AD Audit', 'EDR', 'Database Audit']
    
    print('Generating timeline events...')
    events = []
    event_id = 0
    
    # Phase 1: Initial Access (March 15, 08:00-09:00)
    for i in range(5):
        event_id += 1
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=8, minutes=i*10)).isoformat(),
            'event_type': 'EMAIL_OPEN',
            'source': 'Exchange Audit',
            'actor': 'jsmith@techcorp.com',
            'target': 'invoice_Q1_2026.xlsx',
            'action': 'OPEN_ATTACHMENT',
            'details': json.dumps({'sender': 'billing@supp1iers.com', 'subject': 'Q1 Invoice - Urgent'}),
            'severity': 'HIGH',
            'anomaly_score': 0.85
        })
    
    # Macro execution
    event_id += 1
    events.append({
        'id': f'evt_{event_id:05d}',
        'timestamp': (base_time + timedelta(hours=8, minutes=32)).isoformat(),
        'event_type': 'PROCESS_CREATE',
        'source': 'Windows Security',
        'actor': 'jsmith@techcorp.com',
        'target': 'powershell.exe',
        'action': 'EXECUTE',
        'details': json.dumps({'parent': 'excel.exe', 'cmdline': 'powershell.exe -enc <base64>'}),
        'severity': 'CRITICAL',
        'anomaly_score': 0.95
    })
    
    # Phase 2: Credential Harvesting (09:00-11:00)
    for i in range(20):
        event_id += 1
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=9, minutes=i*3)).isoformat(),
            'event_type': 'CREDENTIAL_ACCESS',
            'source': 'EDR',
            'actor': 'unknown_attacker',
            'target': random.choice(actors[:4]),
            'action': 'LSASS_DUMP',
            'details': json.dumps({'technique': 'Mimikatz', 'success': i < 15}),
            'severity': 'CRITICAL',
            'anomaly_score': 0.92 + random.uniform(0, 0.08)
        })
    
    # Phase 3: Lateral Movement (11:00-18:00)
    for i in range(80):
        event_id += 1
        src_ip = random.choice(internal_ips)
        dst_ip = random.choice(internal_ips + dc_ips)
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=11, minutes=i*5)).isoformat(),
            'event_type': 'LATERAL_MOVEMENT',
            'source': 'Windows Security',
            'actor': random.choice(['unknown_attacker', 'TECHCORP\\Domain Admins']),
            'target': dst_ip,
            'action': random.choice(['SMB_LOGIN', 'RDP_SESSION', 'PSEXEC', 'WMIC']),
            'details': json.dumps({'src_ip': src_ip, 'dst_ip': dst_ip, 'technique': 'Pass-the-Hash'}),
            'severity': 'HIGH',
            'anomaly_score': 0.75 + random.uniform(0, 0.2)
        })
    
    # Phase 4: Data Discovery & Collection (18:00-23:00)
    databases = ['CustomerDB', 'FinanceDB', 'HR_Records', 'R&D_Projects', 'Contracts']
    for i in range(100):
        event_id += 1
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=18, minutes=i*3)).isoformat(),
            'event_type': 'DATA_ACCESS',
            'source': 'Database Audit',
            'actor': 'svc_backup@techcorp.com',
            'target': random.choice(databases),
            'action': 'SELECT',
            'details': json.dumps({'rows_accessed': random.randint(1000, 50000), 'tables': random.randint(5, 20)}),
            'severity': 'HIGH',
            'anomaly_score': 0.7 + random.uniform(0, 0.25)
        })
    
    # Phase 5: Exfiltration (23:00 - March 16 02:00)
    for i in range(50):
        event_id += 1
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=23, minutes=i*4)).isoformat(),
            'event_type': 'DATA_EXFILTRATION',
            'source': 'Firewall',
            'actor': 'unknown_attacker',
            'target': random.choice(external_ips),
            'action': 'OUTBOUND_TRANSFER',
            'details': json.dumps({'bytes': random.randint(100000000, 500000000), 'protocol': 'HTTPS'}),
            'severity': 'CRITICAL',
            'anomaly_score': 0.95 + random.uniform(0, 0.05)
        })
    
    # Phase 6: Ransomware Deployment (02:30-03:30)
    for i in range(47):
        event_id += 1
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=26, minutes=30 + i)).isoformat(),
            'event_type': 'RANSOMWARE',
            'source': 'EDR',
            'actor': 'unknown_attacker',
            'target': f'WS-{100+i:03d}',
            'action': 'FILE_ENCRYPT',
            'details': json.dumps({'variant': 'LockBit 3.0', 'files_encrypted': random.randint(5000, 20000)}),
            'severity': 'CRITICAL',
            'anomaly_score': 0.99
        })
    
    # Phase 7: Normal background activity
    for i in range(200):
        event_id += 1
        hour = random.randint(0, 23)
        events.append({
            'id': f'evt_{event_id:05d}',
            'timestamp': (base_time + timedelta(hours=hour, minutes=random.randint(0, 59))).isoformat(),
            'event_type': random.choice(['LOGIN', 'LOGOUT', 'FILE_ACCESS', 'NETWORK_CONNECTION']),
            'source': random.choice(sources),
            'actor': random.choice(actors[:4]),
            'target': random.choice(['FileServer', 'SharePoint', 'Email', 'VPN']),
            'action': random.choice(['READ', 'WRITE', 'CONNECT', 'DISCONNECT']),
            'details': json.dumps({'normal_activity': True}),
            'severity': 'LOW',
            'anomaly_score': random.uniform(0.1, 0.4)
        })
    
    print(f'Generated {len(events)} timeline events')
    
    # Insert into unified_timeline
    print('Inserting into unified_timeline...')
    for evt in events:
        try:
            db.execute('''
                INSERT INTO unified_timeline (id, timestamp, event_type, source, actor, target, action, details, severity, anomaly_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [evt['id'], evt['timestamp'], evt['event_type'], evt['source'], evt['actor'], 
                  evt['target'], evt['action'], evt['details'], evt['severity'], evt['anomaly_score']])
        except Exception as e:
            pass  # Skip duplicates
    
    db.commit()
    
    # Generate network flows
    print('Generating network flows...')
    flow_id = 0
    flows = []
    
    # Normal traffic
    for i in range(150):
        flow_id += 1
        flows.append({
            'id': f'flow_{flow_id:05d}',
            'timestamp': (base_time + timedelta(hours=random.randint(0, 24), minutes=random.randint(0, 59))).isoformat(),
            'src_ip': random.choice(internal_ips),
            'src_port': random.randint(49152, 65535),
            'dst_ip': random.choice(['8.8.8.8', '1.1.1.1', '208.67.222.222']),
            'dst_port': random.choice([80, 443, 53]),
            'protocol': random.choice(['TCP', 'UDP']),
            'bytes_sent': random.randint(100, 10000),
            'bytes_recv': random.randint(100, 50000),
            'duration_ms': random.randint(10, 5000),
            'is_beaconing': False,
            'is_exfiltration': False
        })
    
    # C2 beaconing traffic
    for i in range(30):
        flow_id += 1
        flows.append({
            'id': f'flow_{flow_id:05d}',
            'timestamp': (base_time + timedelta(hours=10 + i//3, minutes=(i % 3) * 20)).isoformat(),
            'src_ip': '10.0.1.50',
            'src_port': random.randint(49152, 65535),
            'dst_ip': '185.220.101.45',
            'dst_port': 443,
            'protocol': 'TCP',
            'bytes_sent': random.randint(200, 500),
            'bytes_recv': random.randint(100, 300),
            'duration_ms': random.randint(50, 150),
            'is_beaconing': True,
            'is_exfiltration': False
        })
    
    # Exfiltration traffic
    for i in range(20):
        flow_id += 1
        flows.append({
            'id': f'flow_{flow_id:05d}',
            'timestamp': (base_time + timedelta(hours=23, minutes=i*10)).isoformat(),
            'src_ip': random.choice(internal_ips),
            'src_port': random.randint(49152, 65535),
            'dst_ip': random.choice(external_ips[:2]),
            'dst_port': 443,
            'protocol': 'TCP',
            'bytes_sent': random.randint(100000000, 200000000),
            'bytes_recv': random.randint(1000, 5000),
            'duration_ms': random.randint(60000, 300000),
            'is_beaconing': False,
            'is_exfiltration': True
        })
    
    print(f'Generated {len(flows)} network flows')
    
    for flow in flows:
        try:
            db.execute('''
                INSERT INTO network_flows (id, timestamp, src_ip, src_port, dst_ip, dst_port, protocol, bytes_sent, bytes_recv, duration_ms, is_beaconing, is_exfiltration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [flow['id'], flow['timestamp'], flow['src_ip'], flow['src_port'], flow['dst_ip'], 
                  flow['dst_port'], flow['protocol'], flow['bytes_sent'], flow['bytes_recv'],
                  flow['duration_ms'], flow['is_beaconing'], flow['is_exfiltration']])
        except:
            pass
    
    db.commit()
    
    # Generate CRUD analysis
    print('Generating CRUD analysis...')
    crud_id = 0
    crud_ops = []
    
    for i in range(100):
        crud_id += 1
        is_anomalous = i > 70  # Last 30 are anomalous
        crud_ops.append({
            'id': f'crud_{crud_id:05d}',
            'timestamp': (base_time + timedelta(hours=18, minutes=i*3)).isoformat(),
            'operation': 'SELECT' if i < 80 else random.choice(['SELECT', 'DELETE', 'UPDATE']),
            'table_name': random.choice(['customers', 'transactions', 'employees', 'contracts', 'financial_reports']),
            'row_count': random.randint(100, 50000) if is_anomalous else random.randint(1, 100),
            'actor': 'svc_backup@techcorp.com' if is_anomalous else random.choice(actors[:4]),
            'source_ip': random.choice(internal_ips),
            'is_anomalous': is_anomalous
        })
    
    print(f'Generated {len(crud_ops)} CRUD operations')
    
    for crud in crud_ops:
        try:
            db.execute('''
                INSERT INTO crud_analysis (id, timestamp, operation, table_name, row_count, actor, source_ip, is_anomalous)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', [crud['id'], crud['timestamp'], crud['operation'], crud['table_name'],
                  crud['row_count'], crud['actor'], crud['source_ip'], crud['is_anomalous']])
        except:
            pass
    
    db.commit()
    
    # Generate depth assessment
    print('Generating depth assessment...')
    depths = [
        {
            'id': 'depth_account',
            'dimension': 'Account Depth',
            'score': 0.95,
            'description': 'Attacker achieved Domain Admin privileges. Compromised 4 service accounts and 12 user accounts.',
            'evidence_refs': json.dumps(['evt_00007', 'evt_00015', 'evt_00020'])
        },
        {
            'id': 'depth_system',
            'dimension': 'System Depth',
            'score': 0.87,
            'description': 'Lateral movement across 3 VLANs. 47 workstations and 3 domain controllers compromised.',
            'evidence_refs': json.dumps(['evt_00027', 'evt_00050', 'evt_00100'])
        },
        {
            'id': 'depth_data',
            'dimension': 'Data Depth',
            'score': 0.92,
            'description': 'Access to PII (CustomerDB), financial records (FinanceDB), and trade secrets (R&D_Projects).',
            'evidence_refs': json.dumps(['evt_00107', 'evt_00150', 'evt_00200'])
        },
        {
            'id': 'depth_control',
            'dimension': 'Control Depth',
            'score': 0.78,
            'description': 'EDR alerts bypassed for 6 hours. Firewall rules modified. Security logs deleted on 12 systems.',
            'evidence_refs': json.dumps(['evt_00250', 'evt_00300'])
        }
    ]
    
    for depth in depths:
        try:
            db.execute('''
                INSERT INTO depth_assessment (id, dimension, score, description, evidence_refs)
                VALUES (?, ?, ?, ?, ?)
            ''', [depth['id'], depth['dimension'], depth['score'], depth['description'], depth['evidence_refs']])
        except:
            pass
    
    db.commit()
    
    # Verify counts
    print('\n' + '='*60)
    print('DATA IMPORT SUMMARY')
    print('='*60)
    
    result = db.execute('SELECT COUNT(*) FROM unified_timeline').fetchone()
    print(f'Timeline events: {result[0]}')
    
    result = db.execute('SELECT COUNT(*) FROM network_flows').fetchone()
    print(f'Network flows: {result[0]}')
    
    result = db.execute('SELECT COUNT(*) FROM crud_analysis').fetchone()
    print(f'CRUD operations: {result[0]}')
    
    result = db.execute('SELECT COUNT(*) FROM depth_assessment').fetchone()
    print(f'Depth assessments: {result[0]}')
    
    # Summary by severity
    print('\nTimeline by severity:')
    for row in db.execute('SELECT severity, COUNT(*) as cnt FROM unified_timeline GROUP BY severity ORDER BY cnt DESC').fetchall():
        print(f'  {row[0]}: {row[1]}')
    
    db.close()
    print('\nPhase 2 complete!')

if __name__ == '__main__':
    main()
