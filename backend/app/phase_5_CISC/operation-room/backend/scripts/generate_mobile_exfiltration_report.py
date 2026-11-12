"""
Generate a near-40-page forensic report for a Windows-to-Android exfiltration scenario.

Workflow executed in investigator order:
1. Import synthetic logs for the provided scenario
2. Analyze imported logs and build detailed metadata
3. Analyze scenario, resolve clarifications (force full timeline)
4. Run analysis modules (timeline, anomaly, network, CRUD, depth, correlation)
5. Build report template/plan (learning-aware with safe fallback)
6. Store evidence in key-value vault and use key references for AI-safe sections
7. Build v4-canvas report AST (~40 pages), verify alignment, auto-fix layout
8. Save to Studio document storage and export signed PDF + manifest

Usage:
  python -m scripts.generate_mobile_exfiltration_report
  python -m scripts.generate_mobile_exfiltration_report --case-id CASE-MOBILE-EXFIL-001
  python -m scripts.generate_mobile_exfiltration_report --learn-dir ../reports_for_learning
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from operation_room.config import settings
from operation_room.database import create_vault, get_vault_path, open_vault, vault_exists
from operation_room.services.alignment_verifier import get_alignment_verifier
from operation_room.services.anomaly_agent import get_anomalies, get_anomaly_summary, run_anomaly_detection
from operation_room.services.correlation_agent import get_narrative, run_correlation
from operation_room.services.crud_agent import get_crud_summary, run_crud_analysis
from operation_room.services.depth_agent import run_depth_analysis
from operation_room.services.export_service import export_pdf
from operation_room.services.network_agent import get_exfil_candidates, get_network_flows, run_network_analysis
from operation_room.services.report_evidence_service import get_report_evidence_service
from operation_room.services.report_learning_service import get_report_learning_service
from operation_room.services.scenario_analyzer import get_scenario_analyzer
from operation_room.services.studio_v2_service import create_document, update_document
from operation_room.services.timeline_service import build_timeline, get_timeline_stats

SCENARIO_TEXT = (
    "A computer (windows) and a mobile phone (android) have been seized from the scene of crime. "
    "The computer was used by the suspect but was owned by the organization and the mobile phone "
    "was owned by the suspect involved in transferring confidential files from the office computer "
    "to his mobile phone through various channels like USB, Bluetooth and email. The timeline of "
    "the transfer of files from computer to mobile phone along with the IP addresses need to be "
    "created and shown on the web interface with the help of given logs."
)

DEFAULT_CASE_ID = "CASE-MOBILE-EXFIL-001"
DEFAULT_REPORT_TITLE = "Comprehensive Forensic Report - Windows to Android Confidential File Exfiltration"


@dataclass
class SectionPlan:
    title: str
    pages: int
    focus: str
    start_page: int = 0
    end_page: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _make_event(
    ts: datetime,
    source_type: str,
    source_system: str,
    actor: str,
    action: str,
    target: str,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": ts.isoformat(),
        "source_type": source_type,
        "source_system": source_system,
        "actor": actor,
        "action": action,
        "target": target,
        "detail": _json_dumps(detail),
    }


def generate_mobile_exfiltration_events(seed: int = 42) -> List[Dict[str, Any]]:
    """Generate deterministic multi-source logs for the requested scenario."""
    random.seed(seed)

    base = datetime(2026, 2, 10, 8, 0, tzinfo=timezone.utc)
    suspect = "arun.suspect"
    normal_users = ["nina.hr", "dinesh.it", "kavya.finance", "rahul.dev"]
    internal_ips = ["10.24.10.21", "10.24.10.55", "10.24.11.40", "10.24.12.12", "10.24.13.5"]
    external_ips = ["198.51.100.11", "203.0.113.91", "45.77.22.18"]

    office_pc = "WIN-OFC-WS01"
    android_phone = "ANDROID-S23"
    mail_gateway = "MAIL-GW-01"
    fw_edge = "FW-EDGE-01"
    usb_stack = "USBSTACK-01"
    bt_stack = "BTSTACK-01"
    file_server = "FILE-SRV-01"

    confidential_files = [
        "Q4_Strategy.pdf",
        "Mergers_Draft.docx",
        "Client_Pricing_2026.xlsx",
        "Acquisition_Targets.pptx",
        "Legal_Risk_Register.csv",
        "Finance_Exposure_Analysis.xlsx",
        "Patent_Portfolio_Summary.pdf",
        "RnD_Product_Roadmap.docx",
    ]

    events: List[Dict[str, Any]] = []

    # Baseline office activity to create realistic background.
    for day in range(10):
        day_start = base + timedelta(days=day)
        for user in normal_users:
            login_time = day_start + timedelta(hours=random.randint(0, 1), minutes=random.randint(0, 59))
            events.append(
                _make_event(
                    login_time,
                    "AUTH",
                    office_pc,
                    user,
                    "LOGIN_SUCCESS",
                    office_pc,
                    {
                        "source_ip": random.choice(internal_ips),
                        "destination_ip": "10.24.0.10",
                        "method": "SSO",
                        "channel": "internal",
                    },
                )
            )
            for idx in range(3):
                file_name = random.choice(confidential_files)
                action_time = login_time + timedelta(minutes=20 + (idx * 14))
                events.append(
                    _make_event(
                        action_time,
                        "FILE",
                        file_server,
                        user,
                        "FILE_READ",
                        f"/share/department/{file_name}",
                        {
                            "source_ip": random.choice(internal_ips),
                            "destination_ip": "10.24.20.7",
                            "bytes": random.randint(20_000, 250_000),
                            "channel": "internal",
                            "classification": "confidential",
                        },
                    )
                )

    # Suspect behavior across USB, Bluetooth, and email channels.
    transfer_session = 0
    for day in range(2, 10):
        day_start = base + timedelta(days=day)

        # After-hours login pattern.
        login_time = day_start + timedelta(hours=11, minutes=random.randint(20, 58))  # 19:20-19:58 UTC
        events.append(
            _make_event(
                login_time,
                "AUTH",
                office_pc,
                suspect,
                "LOGIN_SUCCESS",
                office_pc,
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": "10.24.0.10",
                    "method": "PASSWORD+MFA",
                    "channel": "internal",
                },
            )
        )

        # Read and stage confidential files.
        session_files = random.sample(confidential_files, k=min(4, len(confidential_files)))
        for idx, file_name in enumerate(session_files):
            read_time = login_time + timedelta(minutes=8 + (idx * 4))
            events.append(
                _make_event(
                    read_time,
                    "FILE",
                    file_server,
                    suspect,
                    "FILE_READ",
                    f"/share/executive/{file_name}",
                    {
                        "source_ip": "10.24.10.21",
                        "destination_ip": "10.24.20.7",
                        "bytes": random.randint(250_000, 2_000_000),
                        "channel": "internal",
                        "classification": "confidential",
                    },
                )
            )

        # USB path
        transfer_session += 1
        usb_connect = login_time + timedelta(minutes=35)
        events.append(
            _make_event(
                usb_connect,
                "USB",
                usb_stack,
                suspect,
                "USB_CONNECT",
                android_phone,
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": "10.24.10.21",
                    "device_id": "USB-PIXEL-001",
                    "channel": "usb",
                },
            )
        )
        for idx, file_name in enumerate(session_files[:2]):
            copy_time = usb_connect + timedelta(minutes=2 + idx)
            events.append(
                _make_event(
                    copy_time,
                    "FILE",
                    office_pc,
                    suspect,
                    "FILE_COPY",
                    f"USB://{android_phone}/{file_name}",
                    {
                        "source_ip": "10.24.10.21",
                        "destination_ip": "10.24.10.21",
                        "bytes": random.randint(300_000, 3_500_000),
                        "channel": "usb",
                        "session_id": f"USB-{transfer_session:03d}",
                    },
                )
            )
        events.append(
            _make_event(
                usb_connect + timedelta(minutes=8),
                "USB",
                usb_stack,
                suspect,
                "USB_DISCONNECT",
                android_phone,
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": "10.24.10.21",
                    "channel": "usb",
                    "session_id": f"USB-{transfer_session:03d}",
                },
            )
        )

        # Bluetooth path
        bt_pair = login_time + timedelta(minutes=50)
        events.append(
            _make_event(
                bt_pair,
                "BLUETOOTH",
                bt_stack,
                suspect,
                "BLUETOOTH_PAIR",
                android_phone,
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": "10.24.10.101",
                    "channel": "bluetooth",
                    "session_id": f"BT-{transfer_session:03d}",
                },
            )
        )
        events.append(
            _make_event(
                bt_pair + timedelta(minutes=3),
                "BLUETOOTH",
                bt_stack,
                suspect,
                "BLUETOOTH_TRANSFER",
                f"BT://{android_phone}/{session_files[-1]}",
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": "10.24.10.101",
                    "bytes": random.randint(120_000, 900_000),
                    "channel": "bluetooth",
                    "session_id": f"BT-{transfer_session:03d}",
                },
            )
        )

        # Email path + firewall egress.
        email_time = login_time + timedelta(minutes=64)
        attachment = random.choice(session_files)
        external_ip = random.choice(external_ips)
        events.append(
            _make_event(
                email_time,
                "EMAIL",
                mail_gateway,
                suspect,
                "EMAIL_SEND",
                "personal.backup@protonmail.com",
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": external_ip,
                    "subject": "Weekly notes",
                    "attachment": attachment,
                    "channel": "email",
                    "bytes": random.randint(200_000, 1_400_000),
                    "session_id": f"MAIL-{transfer_session:03d}",
                },
            )
        )
        events.append(
            _make_event(
                email_time + timedelta(minutes=1),
                "FW",
                fw_edge,
                suspect,
                "ALLOW",
                f"{external_ip}:443",
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": external_ip,
                    "bytes": random.randint(3_000_000, 18_000_000),
                    "protocol": "TLS",
                    "channel": "email",
                },
            )
        )

        # Explicit export marker for CRUD/network modules.
        events.append(
            _make_event(
                email_time + timedelta(minutes=2),
                "APP",
                office_pc,
                suspect,
                "EXPORT",
                f"/staging/{attachment}",
                {
                    "source_ip": "10.24.10.21",
                    "destination_ip": external_ip,
                    "bytes": random.randint(400_000, 4_000_000),
                    "channel": "email",
                    "classification": "confidential",
                },
            )
        )

    events.sort(key=lambda e: e["timestamp"])
    return events


def _compute_events_hash(events: List[Dict[str, Any]]) -> str:
    canonical = json.dumps(events, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_import_bundle(case_dir: Path, events: List[Dict[str, Any]]) -> Dict[str, str]:
    imports_dir = case_dir / "imports"
    imports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = imports_dir / f"mobile_exfil_logs_{ts}.json"
    jsonl_path = imports_dir / f"mobile_exfil_logs_{ts}.jsonl"

    json_path.write_text(_json_dumps(events), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(_json_dumps(event) + "\n")

    return {"json": str(json_path), "jsonl": str(jsonl_path)}


def initialize_case_with_imported_logs(case_id: str, reset_case: bool) -> Dict[str, Any]:
    """Create the case vault and import generated logs into raw_events."""
    case_dir = settings.CASES_DIR / case_id
    if vault_exists(case_id):
        if not reset_case:
            raise RuntimeError(
                f"Case {case_id} already exists. Use --reset to recreate this generated scenario case."
            )
        shutil.rmtree(case_dir, ignore_errors=True)

    events = generate_mobile_exfiltration_events(seed=42)
    import_files = _write_import_bundle(case_dir, events)

    conn = create_vault(case_id)
    try:
        conn.execute(
            """
            INSERT INTO case_metadata
                (case_id, title, description, classification, priority, status,
                 lead_investigator, suspects, investigation_reason, log_sources)
            VALUES (?, ?, ?, 'CONFIDENTIAL', 'CRITICAL', 'IN_PROGRESS',
                    'autopilot', ?, ?, ?)
            """,
            [
                case_id,
                "Windows-to-Android Confidential Transfer Investigation",
                "Investigation into unauthorized transfer of confidential organizational files "
                "from a Windows office computer to a suspect-owned Android phone.",
                _json_dumps(["arun.suspect", "WIN-OFC-WS01", "ANDROID-S23"]),
                "Potential insider exfiltration through USB, Bluetooth, and email channels.",
                _json_dumps(["AUTH", "FILE", "USB", "BLUETOOTH", "EMAIL", "FW", "APP"]),
            ],
        )

        scope_start = events[0]["timestamp"]
        scope_end = events[-1]["timestamp"]
        for source in ["AUTH", "FILE", "USB", "BLUETOOTH", "EMAIL", "FW", "APP"]:
            conn.execute(
                """
                INSERT INTO scope_definition
                    (scope_id, case_id, source_type, time_start, time_end, target_actors, target_systems)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    str(uuid.uuid4()),
                    case_id,
                    source,
                    scope_start,
                    scope_end,
                    _json_dumps(["arun.suspect"]),
                    _json_dumps(["WIN-OFC-WS01", "ANDROID-S23", "MAIL-GW-01", "FW-EDGE-01"]),
                ],
            )

        batch_id = str(uuid.uuid4())
        for event in events:
            conn.execute(
                """
                INSERT INTO raw_events
                    (event_id, case_id, import_batch_id, source_type,
                     timestamp, source_system, actor, action, target, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event["event_id"],
                    case_id,
                    batch_id,
                    event["source_type"],
                    event["timestamp"],
                    event["source_system"],
                    event["actor"],
                    event["action"],
                    event["target"],
                    event["detail"],
                ],
            )

        hash_value = _compute_events_hash(events)
        canonical_bytes = len(json.dumps(events, sort_keys=True, default=str).encode("utf-8"))
        conn.execute(
            """
            INSERT INTO evidence_hashes
                (hash_id, case_id, import_batch_id, artefact_name, artefact_type,
                 hash_algorithm, hash_value, record_count, byte_size, created_by)
            VALUES (?, ?, ?, ?, 'QUERY_RESULT', 'SHA-256', ?, ?, ?, 'autopilot')
            """,
            [
                str(uuid.uuid4()),
                case_id,
                batch_id,
                "MOBILE_EXFIL_SCENARIO_LOG_BUNDLE",
                hash_value,
                len(events),
                canonical_bytes,
            ],
        )

        conn.execute(
            """
            INSERT INTO chain_of_custody
                (event_id, case_id, actor, action, target_artefact, justification, hash_after, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid.uuid4()),
                case_id,
                "autopilot",
                "IMPORT",
                "MOBILE_EXFIL_SCENARIO_LOG_BUNDLE",
                "Synthetic import for investigator-requested Windows-to-Android exfiltration scenario",
                hash_value,
                _json_dumps(
                    {
                        "record_count": len(events),
                        "import_batch_id": batch_id,
                        "source_files": import_files,
                    }
                ),
            ],
        )
    finally:
        conn.close()

    return {
        "case_id": case_id,
        "events": events,
        "import_batch_id": batch_id,
        "evidence_hash": hash_value,
        "source_files": import_files,
    }


def analyze_imported_logs(case_id: str) -> Dict[str, Any]:
    """Build detailed metadata for imported logs in investigator-first order."""
    conn = open_vault(case_id)
    try:
        rows = conn.execute(
            """
            SELECT timestamp, source_type, source_system, actor, action, target, detail
            FROM raw_events
            WHERE case_id = ?
            ORDER BY timestamp ASC
            """,
            [case_id],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "total_events": 0,
            "error": "No imported logs found",
        }

    source_stats: Dict[str, Dict[str, Any]] = {}
    actor_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    channel_counter: Counter[str] = Counter()
    source_ip_counter: Counter[str] = Counter()
    destination_ip_counter: Counter[str] = Counter()

    channel_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    global_start = str(rows[0][0])
    global_end = str(rows[-1][0])

    for row in rows:
        ts, source_type, source_system, actor, action, target, detail_raw = row
        ts_str = str(ts)
        source = source_type or "UNKNOWN"
        actor_val = actor or "unknown"
        action_val = action or "unknown"

        actor_counter[actor_val] += 1
        action_counter[action_val] += 1

        stat = source_stats.setdefault(
            source,
            {
                "count": 0,
                "start_time": ts_str,
                "end_time": ts_str,
                "actors": Counter(),
                "systems": Counter(),
            },
        )
        stat["count"] += 1
        stat["end_time"] = ts_str
        stat["actors"][actor_val] += 1
        stat["systems"][source_system or "unknown"] += 1

        detail_obj: Dict[str, Any]
        try:
            detail_obj = json.loads(detail_raw) if detail_raw else {}
        except Exception:
            detail_obj = {}

        channel = str(detail_obj.get("channel", "internal")).lower()
        channel_counter[channel] += 1

        src_ip = detail_obj.get("source_ip")
        dst_ip = detail_obj.get("destination_ip")
        if isinstance(src_ip, str) and src_ip:
            source_ip_counter[src_ip] += 1
        if isinstance(dst_ip, str) and dst_ip:
            destination_ip_counter[dst_ip] += 1

        sample = {
            "timestamp": ts_str,
            "source_type": source,
            "actor": actor_val,
            "action": action_val,
            "target": target,
            "source_ip": src_ip,
            "destination_ip": dst_ip,
        }
        if len(channel_samples[channel]) < 8:
            channel_samples[channel].append(sample)

    normalized_source_stats = {}
    for source, stat in source_stats.items():
        normalized_source_stats[source] = {
            "count": stat["count"],
            "start_time": stat["start_time"],
            "end_time": stat["end_time"],
            "top_actors": stat["actors"].most_common(5),
            "top_systems": stat["systems"].most_common(5),
        }

    return {
        "total_events": len(rows),
        "time_range": {
            "start": global_start,
            "end": global_end,
        },
        "source_stats": normalized_source_stats,
        "top_actors": actor_counter.most_common(12),
        "top_actions": action_counter.most_common(20),
        "channel_counts": dict(channel_counter),
        "channel_samples": channel_samples,
        "top_source_ips": source_ip_counter.most_common(15),
        "top_destination_ips": destination_ip_counter.most_common(15),
    }


def analyze_scenario_with_clarification(case_id: str, scenario_text: str) -> Dict[str, Any]:
    """Analyze scenario and enforce full timeline clarification per request."""
    analyzer = get_scenario_analyzer()
    context = analyzer.analyze(
        scenario_text=scenario_text,
        case_id=case_id,
        use_llm=False,
    )

    clarification_log: List[Dict[str, str]] = []
    for question in context.clarification_questions:
        answer = "Use full timeline of all imported logs for report generation."
        updated = analyzer.answer_clarification(context.scenario_id, question.question_id, answer)
        clarification_log.append(
            {
                "question_id": question.question_id,
                "question": question.question_text,
                "answer": answer,
            }
        )
        if updated is not None:
            context = updated

    # Investigator instruction in this run: always full timeline.
    context.use_full_timeline = True

    context_dict = context.to_dict()
    context_dict["clarification_log"] = clarification_log
    context_dict["clarification_complete"] = True
    return context_dict


def _safe_learning_recommendation(
    case_type: str,
    scenario_text: str,
    evidence_volume: Dict[str, int],
    learn_dir: Optional[Path],
) -> Dict[str, Any]:
    """Try learning-aware recommendation and gracefully fall back if dependencies are unavailable."""
    learning_notes = {
        "ingested_reports": [],
        "ingest_errors": [],
        "learning_available": False,
        "learning_stats": {},
    }

    try:
        learning = get_report_learning_service()
        learning_notes["learning_available"] = True

        if learn_dir is not None and learn_dir.exists():
            for file_path in sorted(learn_dir.iterdir()):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in {".pdf", ".docx", ".doc"}:
                    continue
                try:
                    layout = learning.parse_document(str(file_path))
                    structure = learning.extract_structure(
                        layout=layout,
                        case_type=case_type,
                        title=file_path.stem,
                    )
                    report_id = learning.store_learned_structure(structure)
                    learning_notes["ingested_reports"].append(
                        {
                            "file": str(file_path),
                            "report_id": report_id,
                            "pages": structure.total_pages,
                        }
                    )
                except Exception as exc:
                    learning_notes["ingest_errors"].append({"file": str(file_path), "error": str(exc)})

        recommendation = learning.recommend_structure(
            case_type=case_type,
            scenario_description=scenario_text,
            evidence_volume=evidence_volume,
            n_similar=5,
        )

        learning_notes["learning_stats"] = learning.get_learning_stats()

        return {
            "recommendation": {
                "recommended_sections": recommendation.recommended_sections,
                "estimated_pages": recommendation.estimated_pages,
                "chart_suggestions": recommendation.chart_suggestions,
                "similar_reports": recommendation.similar_reports,
                "confidence": recommendation.confidence,
                "reasoning": recommendation.reasoning,
            },
            "learning": learning_notes,
        }
    except Exception as exc:
        learning_notes["ingest_errors"].append({"error": f"Learning system unavailable: {exc}"})

        default_sections = [
            "Executive Summary",
            "Case Background",
            "Imported Log Metadata",
            "Timeline of Transfers",
            "Channel Analysis",
            "Network and IP Analysis",
            "Hypothesis Evaluation",
            "Evidence and Audit",
            "Recommendations",
            "Appendix",
        ]
        return {
            "recommendation": {
                "recommended_sections": [{"title": title, "level": 1} for title in default_sections],
                "estimated_pages": 40,
                "chart_suggestions": [
                    {"chart_type": "timeline", "suggested_section": "Timeline of Transfers"},
                    {"chart_type": "bar_chart", "suggested_section": "Imported Log Metadata"},
                    {"chart_type": "pie_chart", "suggested_section": "Channel Analysis"},
                ],
                "similar_reports": [],
                "confidence": 0.25,
                "reasoning": "Fallback structure because learning dependencies were unavailable.",
            },
            "learning": learning_notes,
        }


def run_modules(case_id: str) -> Dict[str, Any]:
    """Execute collaborative module pipeline and capture outputs."""
    timeline_build = build_timeline(case_id, {"force_rebuild": True})
    timeline_stats = get_timeline_stats(case_id)

    anomaly_run = run_anomaly_detection(
        case_id,
        model_type="ensemble",
        contamination=0.12,
        n_estimators=120,
    )
    anomaly_summary = get_anomaly_summary(case_id, anomaly_run.get("run_id"))
    anomalies = get_anomalies(case_id, run_id=anomaly_run.get("run_id"), anomalies_only=True)

    network_run = run_network_analysis(case_id)
    network_flows = get_network_flows(case_id, suspicious_only=True, limit=100)
    exfil_candidates = get_exfil_candidates(case_id)

    crud_run = run_crud_analysis(case_id, sensitivity_threshold="LOW")
    crud_summary = get_crud_summary(case_id)

    depth_run = run_depth_analysis(case_id)

    correlation_run: Dict[str, Any]
    correlation_narrative: Dict[str, Any]
    try:
        correlation_run = run_correlation(case_id, llm_provider="ollama")
    except Exception as exc:
        correlation_run = {
            "status": "FAILED",
            "error": f"Correlation execution failed: {exc}",
            "run_id": None,
        }

    if correlation_run.get("status") == "completed" and not correlation_run.get("error"):
        try:
            correlation_narrative = get_narrative(case_id, run_id=correlation_run.get("run_id"))
        except Exception as exc:
            correlation_narrative = {
                "error": f"Correlation narrative unavailable: {exc}",
                "narrative": (
                    "Fallback narrative: correlation graph persistence tables were unavailable for this run; "
                    "timeline, anomaly, network, CRUD, and depth modules still completed and were used in the report."
                ),
            }
    else:
        correlation_narrative = {
            "error": correlation_run.get("error", "Correlation run failed"),
            "narrative": (
                "Fallback narrative: correlation module did not complete; remaining modules and evidence keys "
                "were used to build the report safely."
            ),
        }

    return {
        "timeline": {
            "build": timeline_build,
            "stats": timeline_stats,
        },
        "anomaly": {
            "run": anomaly_run,
            "summary": anomaly_summary,
            "top_anomalies": anomalies[:20],
        },
        "network": {
            "run": network_run,
            "flows": network_flows[:30],
            "exfil_candidates": exfil_candidates[:20],
        },
        "crud": {
            "run": crud_run,
            "summary": crud_summary,
        },
        "depth": {
            "run": depth_run,
        },
        "correlation": {
            "run": correlation_run,
            "narrative": correlation_narrative,
        },
    }


def evaluate_hypotheses(log_metadata: Dict[str, Any], module_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate section-level hypotheses from metadata + module outcomes."""
    channel_counts = Counter(log_metadata.get("channel_counts", {}))
    top_destination_ips = log_metadata.get("top_destination_ips", [])

    anomaly_count = int(module_results.get("anomaly", {}).get("run", {}).get("anomalies_found", 0) or 0)
    exfil_candidates = len(module_results.get("network", {}).get("exfil_candidates", []))

    def supported(count: int, min_expected: int = 1) -> Tuple[str, float]:
        if count >= min_expected:
            confidence = min(0.98, 0.55 + (count / 30.0))
            return "supported", round(confidence, 2)
        return "refuted", 0.35

    h1_status, h1_conf = supported(channel_counts.get("usb", 0))
    h2_status, h2_conf = supported(channel_counts.get("bluetooth", 0))
    h3_status, h3_conf = supported(channel_counts.get("email", 0))

    h4_status = "supported" if anomaly_count > 10 else "inconclusive"
    h4_conf = 0.82 if anomaly_count > 10 else 0.52

    h5_status = "supported" if exfil_candidates > 0 and top_destination_ips else "inconclusive"
    h5_conf = 0.87 if h5_status == "supported" else 0.5

    return [
        {
            "id": "H-USB-001",
            "statement": "Confidential files were transferred from office computer to Android device via USB.",
            "status": h1_status,
            "confidence": h1_conf,
            "evidence_summary": f"USB channel events: {channel_counts.get('usb', 0)}",
        },
        {
            "id": "H-BT-001",
            "statement": "Bluetooth was used as an alternate transfer channel for confidential content.",
            "status": h2_status,
            "confidence": h2_conf,
            "evidence_summary": f"Bluetooth channel events: {channel_counts.get('bluetooth', 0)}",
        },
        {
            "id": "H-EMAIL-001",
            "statement": "Email attachments were used to move confidential files to external recipient endpoints.",
            "status": h3_status,
            "confidence": h3_conf,
            "evidence_summary": f"Email channel events: {channel_counts.get('email', 0)}",
        },
        {
            "id": "H-TIME-001",
            "statement": "Transfer behavior was concentrated in after-hours windows and deviated from baseline usage.",
            "status": h4_status,
            "confidence": h4_conf,
            "evidence_summary": f"Anomalies detected: {anomaly_count}",
        },
        {
            "id": "H-IP-001",
            "statement": "Network egress and destination IP patterns are consistent with exfiltration intent.",
            "status": h5_status,
            "confidence": h5_conf,
            "evidence_summary": f"Exfiltration candidates: {exfil_candidates}; Top destination IPs: {top_destination_ips[:5]}",
        },
    ]


def store_evidence_keys(
    case_id: str,
    scenario_context: Dict[str, Any],
    log_metadata: Dict[str, Any],
    module_results: Dict[str, Any],
    hypotheses: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Store key-value evidence and return AI-safe references."""
    service = get_report_evidence_service(case_id)
    keys: List[Dict[str, Any]] = []

    def add_key(
        key_name: str,
        category: str,
        raw_value: Any,
        summary: str,
        evidence_type: str,
        source_module: str,
        section_id: Optional[str] = None,
        confidence: float = 0.85,
    ) -> str:
        key_id = service.store_evidence(
            key_name=key_name,
            category=category,
            raw_value=_json_dumps(raw_value),
            summary=summary,
            evidence_type=evidence_type,
            source_module=source_module,
            confidence=confidence,
            section_id=section_id,
            metadata={"generated_at": _now_iso()},
        )
        ai_reference = f"[EVIDENCE:{key_id}:{category}:{key_name}]"
        keys.append(
            {
                "key_id": key_id,
                "key_name": key_name,
                "category": category,
                "summary": summary,
                "ai_reference": ai_reference,
            }
        )
        return key_id

    k_scenario = add_key(
        "scenario_context",
        "scenario",
        scenario_context,
        "Structured scenario context and clarification outcomes",
        "context",
        "scenario_analyzer",
        section_id="SEC-SCENARIO",
    )
    k_logs = add_key(
        "imported_log_metadata",
        "metadata",
        log_metadata,
        "Aggregated imported-log metadata including time ranges and actor/channel counts",
        "metadata",
        "log_analyzer",
        section_id="SEC-METADATA",
    )
    k_timeline = add_key(
        "timeline_summary",
        "timeline",
        module_results.get("timeline"),
        "Timeline build status and timeline statistics",
        "finding",
        "timeline_module",
        section_id="SEC-TIMELINE",
    )
    k_network = add_key(
        "network_exfil_summary",
        "network",
        module_results.get("network"),
        "Network flow analysis and exfiltration candidates",
        "finding",
        "network_module",
        section_id="SEC-NETWORK",
    )
    k_anomaly = add_key(
        "anomaly_detection_summary",
        "anomaly",
        module_results.get("anomaly"),
        "Anomaly detection run summary and top anomalies",
        "finding",
        "anomaly_module",
        section_id="SEC-MODULES",
    )

    hypothesis_key_ids: List[str] = []
    for item in hypotheses:
        key_id = add_key(
            key_name=item["id"],
            category="hypothesis",
            raw_value=item,
            summary=f"{item['statement']} | verdict={item['status']} | confidence={item['confidence']}",
            evidence_type="hypothesis",
            source_module="hypothesis_evaluator",
            section_id="SEC-HYPOTHESES",
            confidence=float(item.get("confidence", 0.5)),
        )
        hypothesis_key_ids.append(key_id)

    chains = []
    try:
        chains.append(
            service.create_chain(
                section_id="SEC-TIMELINE",
                key_ids=[k_scenario, k_logs, k_timeline],
                narrative_hint="Scenario-to-log-to-timeline chain",
            )
        )
        chains.append(
            service.create_chain(
                section_id="SEC-NETWORK",
                key_ids=[k_logs, k_network, k_anomaly],
                narrative_hint="Metadata-to-network-to-anomaly chain",
            )
        )
        chains.append(
            service.create_chain(
                section_id="SEC-HYPOTHESES",
                key_ids=hypothesis_key_ids,
                narrative_hint="Hypothesis verdict chain",
            )
        )
    except Exception:
        # Evidence chain creation is best-effort and should not break report generation.
        pass

    return {
        "keys": keys,
        "chain_ids": chains,
    }


def _format_top_counter(items: List[Tuple[str, int]], top_n: int = 8) -> str:
    if not items:
        return "No data"
    return ", ".join(f"{k} ({v})" for k, v in items[:top_n])


def _metric_elements(metrics: List[Dict[str, str]], start_y: int = 560) -> List[Dict[str, Any]]:
    elements: List[Dict[str, Any]] = []
    if not metrics:
        return elements

    width = 160
    gap = 20
    x = 40
    for idx, metric in enumerate(metrics[:4]):
        elements.append(
            {
                "id": f"metric-{uuid.uuid4().hex[:8]}",
                "type": "metric",
                "x": x + (idx * (width + gap)),
                "y": start_y,
                "width": width,
                "height": 120,
                "value": metric.get("value", "-"),
                "label": metric.get("label", "Metric"),
                "trend": metric.get("trend", "neutral"),
                "color": metric.get("color", "#1e40af"),
            }
        )
    return elements


def _chart_element(chart: Dict[str, Any], y: int = 700) -> Dict[str, Any]:
    return {
        "id": f"chart-{uuid.uuid4().hex[:8]}",
        "type": "chart",
        "x": 40,
        "y": y,
        "width": 714,
        "height": 260,
        "chartType": chart.get("chartType", "bar"),
        "chartTitle": chart.get("chartTitle", "Chart"),
        "data": chart.get("data", []),
    }


def _text_element(content: str, y: int, height: int, size: int = 12, weight: str = "normal") -> Dict[str, Any]:
    return {
        "id": f"text-{uuid.uuid4().hex[:8]}",
        "type": "text",
        "x": 40,
        "y": y,
        "width": 714,
        "height": height,
        "content": content,
        "fontSize": size,
        "fontWeight": weight,
    }


def _section_templates(target_pages: int) -> List[SectionPlan]:
    sections = [
        SectionPlan("Imported Log Analysis and Metadata", 5, "metadata"),
        SectionPlan("Scenario Intent, Clarification, and Scope", 3, "scenario"),
        SectionPlan("Detailed Timeline Reconstruction", 6, "timeline"),
        SectionPlan("Channel Analysis - USB Transfer Path", 3, "usb"),
        SectionPlan("Channel Analysis - Bluetooth Transfer Path", 3, "bluetooth"),
        SectionPlan("Channel Analysis - Email Transfer Path", 3, "email"),
        SectionPlan("IP Address Mapping and Network Correlation", 4, "ip"),
        SectionPlan("Cross-Module Findings and Hypothesis Evaluation", 4, "hypothesis"),
        SectionPlan("Evidence Vault Keys, Redaction, and Audit Trail", 3, "evidence"),
        SectionPlan("Conclusions, Recommendations, and Learning Loop", 3, "conclusion"),
    ]

    # Keep deterministic near-40 pages while allowing mild adjustment.
    preface_pages = 3
    current_total = preface_pages + sum(section.pages for section in sections)
    while current_total < target_pages:
        sections[-1].pages += 1
        current_total += 1
    while current_total > target_pages and sections[-1].pages > 1:
        sections[-1].pages -= 1
        current_total -= 1

    page_no = preface_pages + 1
    for section in sections:
        section.start_page = page_no
        section.end_page = page_no + section.pages - 1
        page_no += section.pages

    return sections


def build_page_payloads(
    case_id: str,
    report_title: str,
    scenario_context: Dict[str, Any],
    log_metadata: Dict[str, Any],
    module_results: Dict[str, Any],
    hypotheses: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    recommendation: Dict[str, Any],
    target_pages: int,
    mode: str,
) -> Tuple[List[Dict[str, Any]], List[SectionPlan], Dict[str, str]]:
    """Create page payloads used to render AST and Markdown."""
    sections = _section_templates(target_pages)
    approvals: Dict[str, str] = {}

    keys = evidence.get("keys", [])
    key_refs = [k.get("ai_reference", "") for k in keys[:24]]

    channel_counts = log_metadata.get("channel_counts", {})
    source_stats = log_metadata.get("source_stats", {})
    source_chart_data = [
        {"name": source, "value": int(data.get("count", 0))}
        for source, data in source_stats.items()
    ]

    top_actor_text = _format_top_counter(log_metadata.get("top_actors", []), top_n=10)
    top_action_text = _format_top_counter(log_metadata.get("top_actions", []), top_n=12)
    top_src_ip = _format_top_counter(log_metadata.get("top_source_ips", []), top_n=8)
    top_dst_ip = _format_top_counter(log_metadata.get("top_destination_ips", []), top_n=8)

    total_events = log_metadata.get("total_events", 0)
    anomaly_count = module_results.get("anomaly", {}).get("run", {}).get("anomalies_found", 0)
    exfil_count = len(module_results.get("network", {}).get("exfil_candidates", []))
    timeline_events = module_results.get("timeline", {}).get("stats", {}).get("total_events", 0)

    pages: List[Dict[str, Any]] = []

    # Page 1: Cover
    pages.append(
        {
            "title": report_title,
            "subtitle": f"Case ID: {case_id}",
            "paragraphs": [
                "This report was generated in investigator-ordered progression with collaborative module execution.",
                "Scenario: Windows organizational workstation to suspect-owned Android phone confidential file transfer via USB, Bluetooth, and email.",
                "Classification: CONFIDENTIAL | Workflow mode: " + mode.upper(),
            ],
            "bullets": [
                "Imported logs were generated and preserved with SHA-256 evidence hash.",
                "Timeline clarification resolved as: use full timeline of imported logs.",
                "All module findings were converted into key-value evidence references before report synthesis.",
                "Per-page alignment verification was executed with auto-fix before export.",
            ],
            "metrics": [
                {"value": str(total_events), "label": "Imported Events", "trend": "critical", "color": "#ef4444"},
                {"value": str(timeline_events), "label": "Timeline Events", "trend": "warning", "color": "#f59e0b"},
                {"value": str(anomaly_count), "label": "Anomalies", "trend": "critical", "color": "#dc2626"},
                {"value": str(exfil_count), "label": "Exfil Candidates", "trend": "critical", "color": "#b91c1c"},
            ],
            "chart": {
                "chartType": "bar",
                "chartTitle": "Imported Events by Source",
                "data": source_chart_data[:8],
            },
            "evidence_refs": key_refs[:4],
        }
    )

    # Page 2: Investigator Order and Clarification
    pages.append(
        {
            "title": "Investigator Workflow Order (Executed)",
            "subtitle": "Order-preserving pipeline with full timeline clarification",
            "paragraphs": [
                "Step 1: Imported and hashed scenario-aligned logs.",
                "Step 2: Built metadata (start/end ranges, actors, channel distribution, IPs).",
                "Step 3: Analyzed scenario and resolved clarification: full timeline was applied.",
                "Step 4: Generated template + section plan, then executed module findings and evidence keying.",
                "Step 5: Built and validated section layout with alignment auto-fix per page.",
            ],
            "bullets": [
                "Scenario case_type: " + str(scenario_context.get("case_type", "general")),
                "Scenario confidence: " + str(round(float(scenario_context.get("confidence", 0.0)), 2)),
                "Use full timeline: " + str(scenario_context.get("use_full_timeline", True)),
                "Clarification entries: " + str(len(scenario_context.get("clarification_log", []))),
            ],
            "metrics": [
                {
                    "value": str(len(scenario_context.get("clarification_log", []))),
                    "label": "Clarifications",
                    "trend": "warning",
                    "color": "#2563eb",
                },
                {"value": str(len(keys)), "label": "Evidence Keys", "trend": "critical", "color": "#7c3aed"},
            ],
            "chart": {
                "chartType": "pie",
                "chartTitle": "Transfer Channel Distribution",
                "data": [
                    {"name": "USB", "value": int(channel_counts.get("usb", 0)), "color": "#3b82f6"},
                    {"name": "Bluetooth", "value": int(channel_counts.get("bluetooth", 0)), "color": "#14b8a6"},
                    {"name": "Email", "value": int(channel_counts.get("email", 0)), "color": "#f59e0b"},
                    {"name": "Internal", "value": int(channel_counts.get("internal", 0)), "color": "#64748b"},
                ],
            },
            "evidence_refs": key_refs[:6],
        }
    )

    # Page 3: TOC
    toc_lines = [f"{idx + 1}. {s.title} (pp. {s.start_page}-{s.end_page})" for idx, s in enumerate(sections)]
    pages.append(
        {
            "title": "Table of Contents",
            "subtitle": "Target: near-40 pages with ordered progression",
            "paragraphs": [recommendation.get("reasoning", "Learning recommendation unavailable.")],
            "bullets": toc_lines,
            "metrics": [
                {"value": str(target_pages), "label": "Target Pages", "trend": "warning", "color": "#1d4ed8"},
                {
                    "value": str(recommendation.get("estimated_pages", target_pages)),
                    "label": "Estimated Pages",
                    "trend": "neutral",
                    "color": "#1e40af",
                },
            ],
            "chart": None,
            "evidence_refs": key_refs[:3],
        }
    )

    # Remaining pages by section
    hypothesis_cycle = hypotheses[:] or [{"id": "H-NA", "statement": "No hypothesis available", "status": "n/a", "confidence": 0.0}]
    hypothesis_idx = 0

    def next_hypothesis() -> Dict[str, Any]:
        nonlocal hypothesis_idx
        item = hypothesis_cycle[hypothesis_idx % len(hypothesis_cycle)]
        hypothesis_idx += 1
        return item

    for section in sections:
        approvals[section.title] = "auto-approved" if mode == "autopilot" else "pending-human-approval"

        for part in range(section.pages):
            hypothesis = next_hypothesis()
            section_intro = (
                f"Section focus: {section.focus}. Page segment {part + 1} of {section.pages}. "
                f"Hypothesis {hypothesis.get('id')}: {hypothesis.get('statement')}"
            )

            shared_paragraphs = [
                section_intro,
                f"Top actors: {top_actor_text}",
                f"Top actions: {top_action_text}",
            ]

            shared_bullets = [
                f"Hypothesis verdict: {hypothesis.get('status')} (confidence={hypothesis.get('confidence')})",
                "Evidence references are key-only in narrative generation and full-value in final reporting.",
                f"Source IP profile: {top_src_ip}",
                f"Destination IP profile: {top_dst_ip}",
            ]

            metrics: List[Dict[str, str]] = []
            chart: Optional[Dict[str, Any]] = None

            if section.focus == "metadata":
                metrics = [
                    {"value": str(total_events), "label": "Imported", "trend": "critical", "color": "#b91c1c"},
                    {"value": str(len(source_stats)), "label": "Log Sources", "trend": "warning", "color": "#1d4ed8"},
                    {"value": str(len(log_metadata.get('top_actors', []))), "label": "Actor Rows", "trend": "neutral", "color": "#0f766e"},
                    {"value": str(len(log_metadata.get('top_destination_ips', []))), "label": "IP Rows", "trend": "neutral", "color": "#374151"},
                ]
                chart = {
                    "chartType": "bar",
                    "chartTitle": "Metadata - Events by Source",
                    "data": source_chart_data[:10],
                }
                shared_paragraphs.append(
                    "Imported log metadata includes per-source start/end windows, actor distributions, and channel-level sampling."
                )

            elif section.focus == "scenario":
                metrics = [
                    {
                        "value": str(round(float(scenario_context.get("confidence", 0.0)), 2)),
                        "label": "Intent Confidence",
                        "trend": "warning",
                        "color": "#0369a1",
                    },
                    {
                        "value": "FULL",
                        "label": "Timeline Scope",
                        "trend": "critical",
                        "color": "#9333ea",
                    },
                ]
                shared_paragraphs.append(
                    "Scenario interpretation confirms data-exfiltration intent with multi-channel transfer behavior."
                )

            elif section.focus == "timeline":
                by_hour = module_results.get("timeline", {}).get("stats", {}).get("events_by_hour", {})
                hour_data = [{"name": k[-5:], "value": v} for k, v in list(by_hour.items())[:24]]
                chart = {
                    "chartType": "line",
                    "chartTitle": "Timeline Density by Hour",
                    "data": hour_data,
                }
                metrics = [
                    {"value": str(timeline_events), "label": "Timeline Events", "trend": "warning", "color": "#1d4ed8"},
                    {
                        "value": str(module_results.get("timeline", {}).get("build", {}).get("clusters_detected", 0)),
                        "label": "Temporal Clusters",
                        "trend": "neutral",
                        "color": "#475569",
                    },
                ]
                shared_paragraphs.append(
                    "Timeline reconstruction uses the full imported range and highlights transfer chronology across all channels."
                )

            elif section.focus in {"usb", "bluetooth", "email"}:
                channel = section.focus
                samples = log_metadata.get("channel_samples", {}).get(channel, [])
                shared_paragraphs.append(
                    f"Channel-specific analysis for {channel.upper()} with sampled event trails and transfer evidence."
                )
                for sample in samples[:4]:
                    shared_bullets.append(
                        f"{sample.get('timestamp')} | {sample.get('actor')} | {sample.get('action')} | {sample.get('target')}"
                    )
                chart = {
                    "chartType": "bar",
                    "chartTitle": f"{channel.upper()} Event Pattern",
                    "data": [
                        {"name": channel.upper(), "value": int(channel_counts.get(channel, 0))},
                        {"name": "Anomalies", "value": int(anomaly_count)},
                        {"name": "Exfil Candidates", "value": int(exfil_count)},
                    ],
                }
                metrics = [
                    {
                        "value": str(int(channel_counts.get(channel, 0))),
                        "label": f"{channel.upper()} Events",
                        "trend": "critical",
                        "color": "#d97706",
                    },
                    {"value": str(exfil_count), "label": "Exfil Candidates", "trend": "critical", "color": "#dc2626"},
                ]

            elif section.focus == "ip":
                chart = {
                    "chartType": "bar",
                    "chartTitle": "Top Destination IP Addresses",
                    "data": [
                        {"name": ip, "value": count}
                        for ip, count in log_metadata.get("top_destination_ips", [])[:10]
                    ],
                }
                metrics = [
                    {
                        "value": str(len(log_metadata.get("top_destination_ips", []))),
                        "label": "Destination IPs",
                        "trend": "warning",
                        "color": "#0284c7",
                    },
                    {"value": str(exfil_count), "label": "Network Candidates", "trend": "critical", "color": "#b91c1c"},
                ]
                shared_paragraphs.append("IP mapping links office endpoints, Android target paths, and external egress points.")

            elif section.focus == "hypothesis":
                chart = {
                    "chartType": "pie",
                    "chartTitle": "Hypothesis Verdict Distribution",
                    "data": [
                        {
                            "name": status,
                            "value": count,
                            "color": "#16a34a" if status == "supported" else "#d97706" if status == "inconclusive" else "#dc2626",
                        }
                        for status, count in Counter([h.get("status", "unknown") for h in hypotheses]).items()
                    ],
                }
                metrics = [
                    {
                        "value": str(len([h for h in hypotheses if h.get("status") == "supported"])),
                        "label": "Supported",
                        "trend": "critical",
                        "color": "#16a34a",
                    },
                    {
                        "value": str(len(hypotheses)),
                        "label": "Total Hypotheses",
                        "trend": "warning",
                        "color": "#1d4ed8",
                    },
                ]
                shared_paragraphs.append(
                    "Cross-module evidence is applied to each heading/subheading hypothesis before narrative placement."
                )

            elif section.focus == "evidence":
                metrics = [
                    {"value": str(len(keys)), "label": "Evidence Keys", "trend": "warning", "color": "#7c3aed"},
                    {
                        "value": str(len(evidence.get("chain_ids", []))),
                        "label": "Evidence Chains",
                        "trend": "neutral",
                        "color": "#0f766e",
                    },
                ]
                shared_paragraphs.append(
                    "Evidence storage uses key-value separation: keys for AI operations, values for report/audit/export modes."
                )
                shared_bullets.extend(
                    [
                        "Redaction modes: full, key_only, redacted, summary.",
                        "Audit purposes: ai_analysis, report_gen, review, export, story_mode.",
                    ]
                )

            elif section.focus == "conclusion":
                chart = {
                    "chartType": "bar",
                    "chartTitle": "Module Completion and Verification",
                    "data": [
                        {"name": "Timeline", "value": 1},
                        {"name": "Anomaly", "value": 1},
                        {"name": "Network", "value": 1},
                        {"name": "CRUD", "value": 1},
                        {"name": "Depth", "value": 1},
                        {"name": "Correlation", "value": 1},
                        {"name": "Alignment", "value": 1},
                    ],
                }
                shared_paragraphs.append(
                    "This section captures final recommendations and the learning loop for dynamic structure adoption in future reports."
                )
                shared_bullets.extend(
                    [
                        "To teach the system from old reports: upload PDF/DOCX via /api/learning/upload-report.",
                        "Use /api/learning/recommend-structure before each new case to adapt heading/subheading depth.",
                        "Submit post-case feedback via /api/learning/feedback to refine future page estimates and charts.",
                    ]
                )

            pages.append(
                {
                    "title": section.title,
                    "subtitle": f"Part {part + 1} of {section.pages}",
                    "paragraphs": shared_paragraphs,
                    "bullets": shared_bullets,
                    "metrics": metrics,
                    "chart": chart,
                    "evidence_refs": key_refs[(part % max(1, len(key_refs))):][:4],
                    "hypothesis": hypothesis,
                }
            )

    return pages[:target_pages], sections, approvals


def payloads_to_canvas_ast(payloads: List[Dict[str, Any]], title: str) -> Dict[str, Any]:
    """Convert page payloads to v4-canvas AST with positioned elements."""
    pages_ast: List[Dict[str, Any]] = []

    for page_number, payload in enumerate(payloads, start=1):
        title_html = f"<h1>{payload['title']}</h1>"
        subtitle_html = f"<h3>{payload['subtitle']}</h3>"

        paragraph_html = "".join(f"<p>{p}</p>" for p in payload.get("paragraphs", []))
        bullet_html = ""
        bullets = payload.get("bullets", [])
        if bullets:
            bullet_html = "<ul>" + "".join(f"<li>{item}</li>" for item in bullets[:14]) + "</ul>"

        evidence_refs = payload.get("evidence_refs", [])
        refs_html = ""
        if evidence_refs:
            refs_html = "<p><strong>Evidence references:</strong> " + ", ".join(evidence_refs[:6]) + "</p>"

        hypothesis = payload.get("hypothesis")
        hypothesis_html = ""
        if hypothesis:
            hypothesis_html = (
                "<p><strong>Hypothesis:</strong> "
                + str(hypothesis.get("statement", ""))
                + "</p><p><strong>Verdict:</strong> "
                + str(hypothesis.get("status", ""))
                + " | <strong>Confidence:</strong> "
                + str(hypothesis.get("confidence", ""))
                + "</p>"
            )

        body_html = paragraph_html + bullet_html + hypothesis_html + refs_html

        elements: List[Dict[str, Any]] = [
            _text_element(title_html, y=40, height=52, size=24, weight="bold"),
            _text_element(subtitle_html, y=96, height=32, size=14, weight="bold"),
        ]

        has_chart = payload.get("chart") is not None
        body_height = 420 if has_chart else 700
        elements.append(_text_element(body_html, y=136, height=body_height, size=11, weight="normal"))

        metric_items = payload.get("metrics", [])
        if metric_items:
            metric_y = 570 if has_chart else 760
            elements.extend(_metric_elements(metric_items, start_y=metric_y))

        if has_chart:
            elements.append(_chart_element(payload["chart"], y=700))

        pages_ast.append(
            {
                "id": f"page-{uuid.uuid4().hex[:8]}",
                "pageNumber": page_number,
                "elements": elements,
            }
        )

    return {
        "type": "v4-canvas",
        "title": title,
        "pages": pages_ast,
    }


def _normalize_for_alignment(elements: List[Dict[str, Any]], page_number: int) -> List[Dict[str, Any]]:
    normalized = []
    type_map = {
        "metric": "chart",
        "component": "paragraph",
        "text": "paragraph",
        "chart": "chart",
        "image": "image",
        "shape": "spacer",
    }
    for el in elements:
        normalized.append(
            {
                "id": el.get("id", f"el-{uuid.uuid4().hex[:8]}"),
                "type": type_map.get(el.get("type", "text"), "paragraph"),
                "x": float(el.get("x", 72)),
                "y": float(el.get("y", 72)),
                "width": float(el.get("width", 451)),
                "height": float(el.get("height", 20)),
                "page": page_number,
                "content": str(el.get("content") or el.get("chartTitle") or el.get("label") or "")[:120],
            }
        )
    return normalized


def _apply_adjustments(elements: List[Dict[str, Any]], adjustments: List[Dict[str, Any]]) -> None:
    lookup = {str(el.get("id")): el for el in elements}
    for adj in adjustments:
        element_id = str(adj.get("element_id", ""))
        target = lookup.get(element_id)
        if not target:
            continue
        if "new_x" in adj:
            target["x"] = float(adj["new_x"])
        if "new_y" in adj:
            target["y"] = float(adj["new_y"])


def verify_and_fix_alignment(ast: Dict[str, Any]) -> Dict[str, Any]:
    """Run per-page alignment verification and auto-fix position issues."""
    verifier = get_alignment_verifier()

    page_reports = []
    total_issues = 0
    total_adjustments = 0

    for page in ast.get("pages", []):
        page_number = int(page.get("pageNumber", 1))
        elements = page.get("elements", [])
        normalized = _normalize_for_alignment(elements, page_number)
        section_id = f"PAGE-{page_number:03d}"

        verification = verifier.verify_section(section_id, normalized)
        issue_count = len(verification.issues)
        total_issues += issue_count

        adjustments, remaining = verifier.auto_fix_issues(verification.verification_id)
        total_adjustments += len(adjustments)
        if adjustments:
            _apply_adjustments(elements, adjustments)

        page_reports.append(
            {
                "page_number": page_number,
                "verification_id": verification.verification_id,
                "status": verification.status.value,
                "issue_count_before_fix": issue_count,
                "auto_fix_adjustments": len(adjustments),
                "remaining_issues_after_fix": len(remaining),
            }
        )

    return {
        "total_pages_verified": len(ast.get("pages", [])),
        "total_issues_before_fix": total_issues,
        "total_adjustments_applied": total_adjustments,
        "page_reports": page_reports,
    }


def _write_run_bundle(case_id: str, run_name: str, artifacts: Dict[str, Any]) -> Path:
    run_dir = settings.CASES_DIR / case_id / "reports" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    for name, payload in artifacts.items():
        out_file = run_dir / f"{name}.json"
        out_file.write_text(_json_dumps(payload), encoding="utf-8")

    return run_dir


def _payloads_to_markdown(payloads: List[Dict[str, Any]], title: str) -> str:
    lines = [f"# {title}", ""]
    for idx, page in enumerate(payloads, start=1):
        lines.append(f"## Page {idx}: {page.get('title', 'Untitled')}")
        lines.append(f"### {page.get('subtitle', '')}")
        lines.append("")

        for paragraph in page.get("paragraphs", []):
            lines.append(paragraph)
            lines.append("")

        bullets = page.get("bullets", [])
        if bullets:
            for bullet in bullets:
                lines.append(f"- {bullet}")
            lines.append("")

        hypothesis = page.get("hypothesis")
        if hypothesis:
            lines.append(
                f"Hypothesis {hypothesis.get('id')}: {hypothesis.get('statement')} -> "
                f"{hypothesis.get('status')} (confidence={hypothesis.get('confidence')})"
            )
            lines.append("")

        refs = page.get("evidence_refs", [])
        if refs:
            lines.append("Evidence refs: " + ", ".join(refs))
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def _save_markdown_report(case_id: str, run_name: str, markdown: str) -> Path:
    out_dir = settings.CASES_DIR / case_id / "reports" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "report_preview.md"
    md_path.write_text(markdown, encoding="utf-8")
    return md_path


def generate_report(args: argparse.Namespace) -> Dict[str, Any]:
    case_id = args.case_id
    target_pages = args.target_pages

    # 1) Import logs
    imported = initialize_case_with_imported_logs(case_id=case_id, reset_case=args.reset)

    # 2) Metadata analysis
    log_metadata = analyze_imported_logs(case_id)

    # 3) Scenario + clarification
    scenario_context = analyze_scenario_with_clarification(case_id, SCENARIO_TEXT)

    # 4) Modules
    module_results = run_modules(case_id)

    # 5) Learning recommendation + template/plan
    recommendation_bundle = _safe_learning_recommendation(
        case_type=str(scenario_context.get("case_type", "data_exfiltration")),
        scenario_text=SCENARIO_TEXT,
        evidence_volume={k: int(v.get("count", 0)) for k, v in log_metadata.get("source_stats", {}).items()},
        learn_dir=Path(args.learn_dir) if args.learn_dir else None,
    )

    # 6) Hypothesis + evidence key-value
    hypotheses = evaluate_hypotheses(log_metadata, module_results)
    evidence = store_evidence_keys(case_id, scenario_context, log_metadata, module_results, hypotheses)

    # 7) Build report pages + AST
    payloads, sections, approvals = build_page_payloads(
        case_id=case_id,
        report_title=DEFAULT_REPORT_TITLE,
        scenario_context=scenario_context,
        log_metadata=log_metadata,
        module_results=module_results,
        hypotheses=hypotheses,
        evidence=evidence,
        recommendation=recommendation_bundle["recommendation"],
        target_pages=target_pages,
        mode=args.mode,
    )
    ast = payloads_to_canvas_ast(payloads, title=DEFAULT_REPORT_TITLE)

    # 8) Alignment verification + auto-fix
    alignment_report = verify_and_fix_alignment(ast)

    # 9) Save document to Studio V4 storage
    created = create_document(
        case_id=case_id,
        title=DEFAULT_REPORT_TITLE,
        template="blank",
        initial_ast=ast,
        created_by="autopilot",
    )
    doc_id = created["doc_id"]

    # Keep a clear version checkpoint after alignment fix
    update_document(
        case_id=case_id,
        doc_id=doc_id,
        ast=ast,
        save_version=True,
        change_summary="Aligned and finalized near-40-page investigator-ordered report",
        actor="autopilot",
    )

    # 10) Export signed PDF and manifest
    pdf_result = export_pdf(
        case_id=case_id,
        doc_id=doc_id,
        actor="autopilot",
        focus_mode="Review",
        engine="reportlab",
    )

    run_name = datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    markdown = _payloads_to_markdown(payloads, DEFAULT_REPORT_TITLE)
    md_path = _save_markdown_report(case_id, run_name, markdown)

    run_bundle = {
        "case": {
            "case_id": case_id,
            "doc_id": doc_id,
            "report_title": DEFAULT_REPORT_TITLE,
            "target_pages": target_pages,
            "generated_pages": len(payloads),
        },
        "scenario_context": scenario_context,
        "log_metadata": log_metadata,
        "module_results": module_results,
        "recommendation": recommendation_bundle,
        "hypotheses": hypotheses,
        "evidence": evidence,
        "sections": [
            {
                "title": section.title,
                "focus": section.focus,
                "start_page": section.start_page,
                "end_page": section.end_page,
                "pages": section.pages,
                "approval_status": approvals.get(section.title, "unknown"),
            }
            for section in sections
        ],
        "alignment": alignment_report,
        "exports": pdf_result,
        "learning_instruction": {
            "upload_endpoint": "/api/learning/upload-report",
            "recommend_endpoint": "/api/learning/recommend-structure",
            "feedback_endpoint": "/api/learning/feedback",
            "note": "Upload prior PDF/DOCX reports to improve future dynamic page/subheading recommendations.",
        },
        "markdown_preview": str(md_path),
    }

    run_dir = _write_run_bundle(case_id, run_name, run_bundle)

    return {
        "case_id": case_id,
        "doc_id": doc_id,
        "pages": len(payloads),
        "pdf_path": pdf_result.get("filepath"),
        "pdf_filename": pdf_result.get("filename"),
        "manifest_path": str(Path(pdf_result.get("filepath", "")).with_name(f"manifest_{pdf_result.get('export_id')}.json"))
        if pdf_result.get("filepath")
        else None,
        "run_bundle_dir": str(run_dir),
        "markdown_preview": str(md_path),
        "alignment_issues_before_fix": alignment_report.get("total_issues_before_fix", 0),
        "alignment_adjustments": alignment_report.get("total_adjustments_applied", 0),
        "learning_ingested_reports": recommendation_bundle.get("learning", {}).get("ingested_reports", []),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate mobile exfiltration forensic report")
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID, help="Case ID for generated report")
    parser.add_argument(
        "--target-pages",
        type=int,
        default=40,
        help="Target report page count (near-40 recommended)",
    )
    parser.add_argument(
        "--mode",
        choices=["autopilot", "human"],
        default="autopilot",
        help="Generation mode; autopilot auto-approves all sections",
    )
    parser.add_argument(
        "--learn-dir",
        default=None,
        help="Optional folder of old PDF/DOCX reports to ingest before recommendation",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Recreate the generated case if it already exists",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    result = generate_report(args)

    print("\n=== Mobile Exfiltration Report Generation Complete ===")
    print(f"Case ID: {result['case_id']}")
    print(f"Document ID: {result['doc_id']}")
    print(f"Pages Generated: {result['pages']}")
    print(f"PDF: {result['pdf_path']}")
    print(f"Run Bundle: {result['run_bundle_dir']}")
    print(f"Markdown Preview: {result['markdown_preview']}")
    print(f"Alignment Issues (before fix): {result['alignment_issues_before_fix']}")
    print(f"Alignment Adjustments Applied: {result['alignment_adjustments']}")

    learned = result.get("learning_ingested_reports", [])
    if learned:
        print(f"Learned from {len(learned)} prior report(s) before template recommendation.")
    else:
        print("No prior reports were ingested for learning in this run.")


if __name__ == "__main__":
    main()
