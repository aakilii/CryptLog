"""
Seed script — creates a permanent forensic test case with rich, multi-source data.

Run:  python -m scripts.seed_case
From:  c:\\CISC\\operation-room\\backend\\

Creates a case titled "CASE-FORENSIC-001 — Insider Threat Investigation"
with ~300 events across 7 log sources telling a coherent attack story:
  Phase 1 (Recon):  AUTH failed logins, VPN connections from unusual IPs
  Phase 2 (Access): DB queries on sensitive tables, APP requests
  Phase 3 (Exfil):  FILE copies, large FW outbound, EPP alerts
"""

import sys, os, json, uuid, random, hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from operation_room.database import create_vault, open_vault, vault_exists
from operation_room.config import settings

# ── Constants ────────────────────────────────────────────────────────────

CASE_ID = "CASE-FORENSIC-001"
TITLE = "Insider Threat — John Doe Data Exfiltration"
DESCRIPTION = (
    "Investigation into suspected data exfiltration by employee John Doe (jdoe). "
    "SOC detected unusual after-hours VPN sessions and bulk database queries "
    "targeting customer PII tables. Endpoint alerts fired when jdoe attempted "
    "to copy encrypted archives to a USB drive."
)

ACTORS = {
    "jdoe":       {"role": "suspect",   "dept": "Engineering"},
    "asmith":     {"role": "witness",   "dept": "Finance"},
    "mjones":     {"role": "witness",   "dept": "HR"},
    "klee":       {"role": "normal",    "dept": "Engineering"},
    "admin":      {"role": "admin",     "dept": "IT"},
    "svc_backup": {"role": "service",   "dept": "IT"},
}

SYSTEMS = ["dc01", "vpn-gw", "fw-ext", "db-prod-01", "app-web-03", "file-srv", "edr-console"]
IPS = ["10.0.1.42", "10.0.2.15", "192.168.1.100", "172.16.0.5", "203.0.113.77", "198.51.100.22", "45.33.32.99"]

START = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
END   = datetime(2025, 6, 15, 23, 59, 59, tzinfo=timezone.utc)
SPAN  = (END - START).total_seconds()


def ts(day, hour, minute=0):
    """Helper to make timestamps within the investigation window."""
    return (START + timedelta(days=day, hours=hour, minutes=minute)).isoformat()


def rand_ts():
    return (START + timedelta(seconds=random.uniform(0, SPAN))).isoformat()


def ev(source, timestamp, actor, action, target, system, detail=None):
    return {
        "event_id": str(uuid.uuid4()),
        "source_type": source,
        "timestamp": timestamp,
        "source_system": system,
        "actor": actor,
        "action": action,
        "target": target,
        "detail": json.dumps(detail or {
            "source_ip": random.choice(IPS),
            "dest_ip": random.choice(IPS),
            "bytes": random.randint(100, 500000),
            "session_id": str(uuid.uuid4())[:8],
        }),
    }


def generate_story_events():
    """Generate ~300 events telling a coherent insider-threat story."""
    events = []

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: RECONNAISSANCE (Days 1–3)
    # jdoe probes the network, fails some logins, connects VPN late
    # ═══════════════════════════════════════════════════════════════════

    # Normal background traffic from other users
    for day in range(15):
        for actor in ["asmith", "mjones", "klee", "admin"]:
            events.append(ev("AUTH", ts(day, random.randint(8,17), random.randint(0,59)),
                             actor, "LOGIN_SUCCESS", "dc01", "dc01",
                             {"source_ip": "10.0.1.15", "method": "SSO"}))
            if random.random() < 0.3:
                events.append(ev("APP", ts(day, random.randint(9,16), random.randint(0,59)),
                                 actor, random.choice(["HTTP_GET", "HTTP_POST"]),
                                 f"/api/{random.choice(['dashboard','reports','users'])}",
                                 "app-web-03"))

    # svc_backup daily routine
    for day in range(15):
        events.append(ev("DB", ts(day, 2, 0), "svc_backup", "SELECT",
                         "/data/backup_manifest", "db-prod-01",
                         {"query": "SELECT * FROM backup_log", "rows": random.randint(100,500)}))
        events.append(ev("FILE", ts(day, 2, 15), "svc_backup", "FILE_WRITE",
                         "/backup/daily_snapshot.tar.gz", "file-srv",
                         {"bytes": random.randint(1000000, 5000000)}))

    # jdoe Phase 1 — recon
    events.append(ev("AUTH", ts(0, 23, 15), "jdoe", "LOGIN_FAILED", "dc01", "dc01",
                     {"source_ip": "203.0.113.77", "reason": "bad_password", "method": "RDP"}))
    events.append(ev("AUTH", ts(0, 23, 16), "jdoe", "LOGIN_FAILED", "dc01", "dc01",
                     {"source_ip": "203.0.113.77", "reason": "bad_password", "method": "RDP"}))
    events.append(ev("AUTH", ts(0, 23, 18), "jdoe", "LOGIN_SUCCESS", "dc01", "dc01",
                     {"source_ip": "203.0.113.77", "method": "RDP"}))
    events.append(ev("VPN", ts(0, 23, 10), "jdoe", "VPN_CONNECT", "vpn-gw", "vpn-gw",
                     {"source_ip": "203.0.113.77", "protocol": "IKEv2", "location": "External"}))

    for day in [1, 2]:
        events.append(ev("AUTH", ts(day, 22, random.randint(0,30)), "jdoe", "LOGIN_SUCCESS",
                         "dc01", "dc01", {"source_ip": "203.0.113.77", "method": "RDP"}))
        events.append(ev("VPN", ts(day, 22, random.randint(0,30)), "jdoe", "VPN_CONNECT",
                         "vpn-gw", "vpn-gw", {"source_ip": "203.0.113.77"}))
        events.append(ev("APP", ts(day, 22, random.randint(30,50)), "jdoe", "HTTP_GET",
                         "/api/users?role=admin", "app-web-03",
                         {"status": 200, "response_bytes": 4500}))
        events.append(ev("FW", ts(day, 22, random.randint(45,59)), "jdoe", "ALLOW",
                         "db-prod-01:5432", "fw-ext",
                         {"source_ip": "10.0.1.42", "dest_ip": "10.0.2.15", "port": 5432}))

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: ACCESS (Days 4–8)
    # jdoe queries sensitive DB tables, accesses customer data
    # ═══════════════════════════════════════════════════════════════════

    sensitive_tables = ["customers", "credit_cards", "employee_ssn", "payroll", "contracts"]
    for day in range(3, 8):
        events.append(ev("VPN", ts(day, 21, random.randint(0,20)), "jdoe", "VPN_CONNECT",
                         "vpn-gw", "vpn-gw", {"source_ip": "203.0.113.77"}))
        events.append(ev("AUTH", ts(day, 21, random.randint(20,40)), "jdoe", "LOGIN_SUCCESS",
                         "dc01", "dc01", {"source_ip": "10.0.1.42"}))

        for i in range(random.randint(3, 6)):
            table = random.choice(sensitive_tables)
            events.append(ev("DB", ts(day, 21 + (i // 4), random.randint(0,59)), "jdoe",
                             random.choice(["SELECT", "EXPORT"]),
                             f"/data/{table}", "db-prod-01",
                             {"query": f"SELECT * FROM {table} LIMIT 10000",
                              "rows": random.randint(5000, 50000),
                              "bytes": random.randint(500000, 5000000)}))

        events.append(ev("APP", ts(day, 22, random.randint(0,30)), "jdoe", "HTTP_GET",
                         "/api/customers/export?format=csv", "app-web-03",
                         {"status": 200, "response_bytes": random.randint(1000000, 10000000)}))

        # Firewall sees large outbound
        events.append(ev("FW", ts(day, 22, random.randint(30,55)), "jdoe", "ALLOW",
                         "198.51.100.22:443", "fw-ext",
                         {"source_ip": "10.0.1.42", "dest_ip": "198.51.100.22",
                          "bytes": random.randint(5000000, 50000000), "protocol": "TLS"}))

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: EXFILTRATION (Days 9–14)
    # jdoe copies files, EPP detects, large outbound transfers
    # ═══════════════════════════════════════════════════════════════════

    for day in range(8, 14):
        events.append(ev("VPN", ts(day, 20, random.randint(0,15)), "jdoe", "VPN_CONNECT",
                         "vpn-gw", "vpn-gw", {"source_ip": "45.33.32.99"}))
        events.append(ev("AUTH", ts(day, 20, random.randint(15,30)), "jdoe",
                         random.choice(["LOGIN_SUCCESS", "MFA_CHALLENGE"]),
                         "dc01", "dc01", {"source_ip": "10.0.1.42"}))

        # File operations
        for i in range(random.randint(2, 5)):
            events.append(ev("FILE", ts(day, 20 + (i // 3), random.randint(0,59)), "jdoe",
                             random.choice(["FILE_READ", "FILE_COPY", "FILE_WRITE"]),
                             f"/data/exports/customer_dump_{day}_{i}.csv.enc", "file-srv",
                             {"bytes": random.randint(1000000, 20000000),
                              "destination": "/media/usb0/" if random.random() < 0.3 else "/data/staging/"}))

        # EPP detections
        if day >= 10:
            events.append(ev("EPP", ts(day, 21, random.randint(0,30)), "jdoe",
                             random.choice(["MALWARE_DETECTED", "PROCESS_BLOCKED", "QUARANTINE"]),
                             "file-srv", "edr-console",
                             {"threat": "Suspicious.Archiver",
                              "process": "7z.exe",
                              "path": f"/data/staging/archive_{day}.7z"}))

        # Large outbound FW
        events.append(ev("FW", ts(day, 22, random.randint(0,30)), "jdoe",
                         random.choice(["ALLOW", "DENY", "DROP"]),
                         "45.33.32.99:443", "fw-ext",
                         {"source_ip": "10.0.1.42", "dest_ip": "45.33.32.99",
                          "bytes": random.randint(10000000, 100000000)}))

        # APP suspicious
        events.append(ev("APP", ts(day, 22, random.randint(30,55)), "jdoe",
                         random.choice(["HTTP_POST", "HTTP_DELETE"]),
                         f"/api/audit-logs/{day}", "app-web-03",
                         {"status": random.choice([200, 403, 500])}))

    # Day 14: Account locked, VPN killed
    events.append(ev("AUTH", ts(13, 14, 0), "admin", "ACCOUNT_LOCKED", "jdoe", "dc01",
                     {"reason": "Security investigation", "locked_by": "admin"}))
    events.append(ev("VPN", ts(13, 14, 1), "jdoe", "VPN_DISCONNECT", "vpn-gw", "vpn-gw",
                     {"reason": "forced_disconnect", "initiated_by": "admin"}))
    events.append(ev("EPP", ts(13, 14, 5), "admin", "SCAN_COMPLETE", "edr-console", "edr-console",
                     {"scan_type": "full", "threats_found": 3, "target": "file-srv"}))

    # Sprinkle random FW allow/deny for background noise
    for _ in range(30):
        actor = random.choice(list(ACTORS.keys()))
        events.append(ev("FW", rand_ts(), actor,
                         random.choice(["ALLOW", "DENY", "DROP"]),
                         f"{random.choice(IPS)}:{random.choice([80,443,22,3389,5432])}",
                         "fw-ext"))

    events.sort(key=lambda e: e["timestamp"])
    return events


def seed():
    """Create the test case and populate it."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.CASES_DIR.mkdir(parents=True, exist_ok=True)

    # Create vault
    if vault_exists(CASE_ID):
        print(f"⚠️  Case {CASE_ID} already exists. Deleting and re-creating.")
        import shutil
        shutil.rmtree(settings.CASES_DIR / CASE_ID, ignore_errors=True)

    conn = create_vault(CASE_ID)

    # Insert case metadata
    suspects_json = json.dumps(["jdoe", "10.0.1.42"])
    sources_json = json.dumps(["AUTH", "VPN", "FW", "DB", "APP", "EPP", "FILE"])
    conn.execute("""
        INSERT INTO case_metadata
            (case_id, title, description, classification, priority, status,
             lead_investigator, suspects, investigation_reason, log_sources)
        VALUES (?, ?, ?, 'CONFIDENTIAL', 'CRITICAL', 'IN_PROGRESS',
                'analyst', ?, 'SOC detected unusual after-hours activity', ?)
    """, [CASE_ID, TITLE, DESCRIPTION, suspects_json, sources_json])

    # Insert scope
    for src in ["AUTH", "VPN", "FW", "DB", "APP", "EPP", "FILE"]:
        conn.execute("""
            INSERT INTO scope_definition
                (scope_id, case_id, source_type, time_start, time_end,
                 target_actors, target_systems)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [str(uuid.uuid4()), CASE_ID, src,
              START.isoformat(), END.isoformat(),
              json.dumps(list(ACTORS.keys())),
              json.dumps(SYSTEMS)])

    # Generate and insert events
    events = generate_story_events()
    print(f"📦 Inserting {len(events)} events...")

    batch_id = str(uuid.uuid4())
    for e in events:
        conn.execute("""
            INSERT INTO raw_events
                (event_id, case_id, import_batch_id, source_type, timestamp,
                 source_system, actor, action, target, detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [e["event_id"], CASE_ID, batch_id, e["source_type"],
              e["timestamp"], e["source_system"], e["actor"],
              e["action"], e["target"], e["detail"]])

    # Hash
    canonical = json.dumps(events, sort_keys=True, separators=(",", ":"))
    hash_val = hashlib.sha256(canonical.encode()).hexdigest()
    conn.execute("""
        INSERT INTO evidence_hashes
            (hash_id, case_id, artefact_name, artefact_type,
             hash_algorithm, hash_value, record_count, byte_size, created_by)
        VALUES (?, ?, 'SEED_ALL_SOURCES', 'SEED', 'SHA-256', ?, ?, ?, 'seed_script')
    """, [str(uuid.uuid4()), CASE_ID, hash_val, len(events), len(canonical)])

    # CoC
    conn.execute("""
        INSERT INTO chain_of_custody
            (event_id, case_id, actor, action, target_artefact,
             justification, hash_after)
        VALUES (?, ?, 'seed_script', 'IMPORT', 'SEED_ALL_SOURCES',
                'Seeded realistic multi-source test data', ?)
    """, [str(uuid.uuid4()), CASE_ID, hash_val])

    print(f"✅ Case {CASE_ID} created with {len(events)} events")
    print(f"   Hash: {hash_val[:24]}...")
    print(f"   Sources: AUTH, VPN, FW, DB, APP, EPP, FILE")
    print(f"   Actors: {', '.join(ACTORS.keys())}")

    # Build timeline
    print("\n🔨 Building timeline...")
    from operation_room.services.timeline_service import build_timeline
    result = build_timeline(CASE_ID, {"force_rebuild": True})
    print(f"   Events: {result['total_events']}, Anchors: {result['anchors_detected']}")
    print(f"   Timeline hash: {result['hash_value'][:24]}...")
    
    # Cleanly close the seed connection after timeline is built
    conn.close()

    print(f"\n🎉 Seed complete! Open http://localhost:3000/cases/{CASE_ID}")


if __name__ == "__main__":
    seed()
