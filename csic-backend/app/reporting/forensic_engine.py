import io
import os
import base64
from datetime import datetime
from typing import Any, Dict, List, Tuple

from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def _get_cover_b64() -> str:
    path = os.path.join(os.path.dirname(__file__), "assets", "cover.png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def _parse_iso(s: Any):
    if not s or not isinstance(s, str):
        return None
    try:
        x = s.replace("Z", "+00:00")
        return datetime.fromisoformat(x)
    except Exception:
        return None

def _fmt_dt(dt: Any) -> str:
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        dtp = _parse_iso(dt)
        if not dtp:
            return dt
        dt = dtp
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"

def _human_bytes(n: Any) -> str:
    try:
        b = int(n)
    except Exception:
        return "N/A"
    if b < 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(b)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    if i == 0:
        return f"{int(v)} {units[i]}"
    return f"{v:.2f} {units[i]}"

def _short_hash(h: Any, n: int = 12) -> str:
    if not h or not isinstance(h, str):
        return "N/A"
    if len(h) <= n:
        return h
    return h[:n] + "…"

def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []

def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}

def _b64_png_from_buf(buf: io.BytesIO) -> str:
    return base64.b64encode(buf.getvalue()).decode("utf-8")

class GraphEngine:
    @staticmethod
    def _save_fig(dpi=150) -> io.BytesIO:
        buf = io.BytesIO()
        # bbox_inches='tight' can sometimes mess up aspect ratio if not careful,
        # but usually good for removing whitespace. We keep it but fix aspect ratio in ReportLab.
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=dpi)
        buf.seek(0)
        plt.close()
        return buf

    @staticmethod
    def pie_chart(data: Dict[str, int], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        if len(items) > 7:
            top = items[:6]
            other = sum(v for _, v in items[6:])
            items = top + [("other", other)]
        labels = [k for k, _ in items]
        values = [v for _, v in items]
        # Adjusted figsize to be wider to prevent squeezing
        plt.figure(figsize=(7, 4))
        plt.pie(values, labels=labels, autopct="%1.1f%%" if sum(values) > 0 else None, startangle=140, textprops={"fontsize": 8})
        plt.title(title, fontsize=10, fontweight="bold")
        return GraphEngine._save_fig()

    @staticmethod
    def bar_chart(data: Dict[str, float], title: str, xlabel: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        xs = [k for k, _ in items]
        ys = [v for _, v in items]
        plt.figure(figsize=(7, 3.5))
        plt.bar(xs, ys, width=0.6)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel(xlabel, fontsize=8)
        plt.xticks(rotation=35, ha="right", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def line_chart(timeline: List[Dict[str, Any]], title: str) -> io.BytesIO:
        scores = []
        for t in timeline:
            try:
                scores.append(float(t.get("risk_score", 0)))
            except Exception:
                scores.append(0.0)
        plt.figure(figsize=(7, 3.5))
        plt.plot(range(len(scores)), scores, linewidth=2)
        if scores:
            plt.fill_between(range(len(scores)), scores, alpha=0.12)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.ylabel("Risk Score", fontsize=8)
        plt.grid(True, alpha=0.25)
        return GraphEngine._save_fig()

    @staticmethod
    def horizontal_bar(data: Dict[str, float], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [k for k, _ in items][::-1]
        vals = [v for _, v in items][::-1]
        plt.figure(figsize=(7, 3.5))
        plt.barh(labels, vals)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel("Score", fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(axis="x", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def hist_chart(values: List[float], title: str) -> io.BytesIO:
        plt.figure(figsize=(7, 3.5))
        plt.hist(values, bins=18)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel("Anomaly Score", fontsize=8)
        plt.ylabel("Count", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

# ... [KEEP _extract_stats, _verdict, _recommended_actions, _num, _present_path, _expected_fields, _coverage_table_for, _missing_fields_for, _availability_paragraphs, _extra_paragraphs, _enforce_no_blank_sections, _build_pages EXACTLY AS THEY WERE] ...
# (I am omitting them here to save space, but you MUST keep them. If you copy-paste, ensure you don't delete the logic functions!)

# --- COPY THE LOGIC FUNCTIONS HERE FROM PREVIOUS CODE ---
# _extract_stats, _verdict, _recommended_actions, _num, _present_path, _expected_fields...
# ...
# ...

# RE-INSERTING SMALL HELPERS JUST IN CASE:
def _num(x: Any) -> float:
    try: return float(x)
    except: return 0.0

def _safe_list(x): return x if isinstance(x, list) else []
def _safe_dict(x): return x if isinstance(x, dict) else {}


def _b64_png_from_buf(buf: io.BytesIO) -> str:
    return base64.b64encode(buf.getvalue()).decode("utf-8")


class GraphEngine:
    @staticmethod
    def _save_fig(dpi=150) -> io.BytesIO:
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=dpi)
        buf.seek(0)
        plt.close()
        return buf

    @staticmethod
    def pie_chart(data: Dict[str, int], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        if len(items) > 7:
            top = items[:6]
            other = sum(v for _, v in items[6:])
            items = top + [("other", other)]

        labels = [k for k, _ in items]
        values = [v for _, v in items]

        plt.figure(figsize=(4.8, 3.6))
        plt.pie(
            values,
            labels=labels,
            autopct="%1.1f%%" if sum(values) > 0 else None,
            startangle=140,
            textprops={"fontsize": 8},
        )
        plt.title(title, fontsize=10, fontweight="bold")
        return GraphEngine._save_fig()

    @staticmethod
    def bar_chart(data: Dict[str, float], title: str, xlabel: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        xs = [k for k, _ in items]
        ys = [v for _, v in items]

        plt.figure(figsize=(6.4, 3.2))
        plt.bar(xs, ys, width=0.6)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel(xlabel, fontsize=8)
        plt.xticks(rotation=35, ha="right", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def line_chart(timeline: List[Dict[str, Any]], title: str) -> io.BytesIO:
        scores = []
        for t in timeline:
            try:
                scores.append(float(t.get("risk_score", 0)))
            except Exception:
                scores.append(0.0)

        plt.figure(figsize=(6.4, 3.2))
        plt.plot(range(len(scores)), scores, linewidth=2)
        if scores:
            plt.fill_between(range(len(scores)), scores, alpha=0.12)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.ylabel("Risk Score", fontsize=8)
        plt.grid(True, alpha=0.25)
        return GraphEngine._save_fig()

    @staticmethod
    def horizontal_bar(data: Dict[str, float], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [k for k, _ in items][::-1]
        vals = [v for _, v in items][::-1]

        plt.figure(figsize=(6.4, 3.2))
        plt.barh(labels, vals)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel("Score", fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(axis="x", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def hist_chart(values: List[float], title: str) -> io.BytesIO:
        plt.figure(figsize=(6.4, 3.2))
        plt.hist(values, bins=18)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel("Anomaly Score", fontsize=8)
        plt.ylabel("Count", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()


def _extract_stats(raw: Dict[str, Any]) -> Dict[str, Any]:
    ev = _safe_list(raw.get("evidence_list"))
    alerts = _safe_list(raw.get("alerts"))
    timeline = _safe_list(raw.get("timeline"))

    file_types: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    total_size = 0
    times: List[datetime] = []

    for f in ev:
        if not isinstance(f, dict):
            continue

        ft = f.get("file_type") or "unknown"
        file_types[ft] = file_types.get(ft, 0) + 1

        st = (f.get("verification_status") or "UNKNOWN").upper()
        status_counts[st] = status_counts.get(st, 0) + 1

        sb = f.get("size_bytes")
        try:
            total_size += int(sb)
        except Exception:
            pass

        ut = f.get("upload_time")
        dt = _parse_iso(ut) if isinstance(ut, str) else None
        if dt:
            times.append(dt)

    times.sort()
    earliest = times[0] if times else None
    latest = times[-1] if times else None

    corrupted = [
        f for f in ev
        if isinstance(f, dict) and (str(f.get("verification_status", "")).upper() in ["CORRUPTED", "INVALID", "FAIL"])
    ]

    largest = sorted(
        [f for f in ev if isinstance(f, dict)],
        key=lambda x: int(x.get("size_bytes", 0) or 0),
        reverse=True
    )[:10]

    parsing = _safe_dict(raw.get("parsing_summary"))
    hot = _safe_dict(raw.get("hot_store"))
    signals = _safe_dict(raw.get("signals"))
    anomaly = _safe_dict(raw.get("anomaly_detection"))

    hash_chain = _safe_dict(raw.get("hash_chain"))
    if not hash_chain:
        hash_chain = _safe_dict(raw.get("chain_of_custody"))

    return {
        "ev": ev,
        "alerts": alerts,
        "timeline": timeline,
        "file_types": file_types,
        "status_counts": status_counts,
        "total_size": total_size,
        "earliest": earliest,
        "latest": latest,
        "corrupted": corrupted,
        "largest": largest,
        "parsing": parsing,
        "hot": hot,
        "signals": signals,
        "anomaly": anomaly,
        "hash_chain": hash_chain,
    }


def _verdict(stats: Dict[str, Any]) -> Tuple[str, str]:
    anomaly = _safe_dict(stats.get("anomaly"))
    alerts = _safe_list(stats.get("alerts"))
    status_counts = _safe_dict(stats.get("status_counts"))

    try:
        flagged = int(anomaly.get("anomalies_flagged", 0) or 0)
    except Exception:
        flagged = 0

    hi = 0
    for a in alerts:
        if isinstance(a, dict):
            try:
                if float(a.get("risk_score", 0) or 0) >= 90:
                    hi += 1
            except Exception:
                pass

    corrupted = 0
    for k, v in status_counts.items():
        if str(k).upper() in ["CORRUPTED", "INVALID", "FAIL"]:
            try:
                corrupted += int(v)
            except Exception:
                pass

    if hi >= 1 or flagged >= 50:
        return "MALICIOUS ACTIVITY LIKELY", "High-risk entities and elevated anomaly concentration observed."
    if flagged >= 10:
        return "SUSPICIOUS ACTIVITY POSSIBLE", "Moderate anomaly concentration; targeted validation recommended."
    if corrupted >= 1:
        return "INTEGRITY REVIEW REQUIRED", "Some artifacts failed integrity verification; isolate and re-check."
    return "NO STRONG INDICATORS", "No high-confidence malicious indicators detected in the provided dataset."


def _recommended_actions(stats: Dict[str, Any]) -> List[str]:
    signals = _safe_dict(stats.get("signals"))
    alerts = _safe_list(stats.get("alerts"))

    triggers = set()
    for a in alerts:
        if isinstance(a, dict):
            for t in _safe_list(a.get("triggers")):
                if isinstance(t, str):
                    triggers.add(t.lower())

    sig_keys = set(str(k).lower() for k in signals.keys())

    rec: List[str] = []
    if "password_spray" in sig_keys or "password_spray" in triggers or "login_velocity_spike" in sig_keys:
        rec.append("Enforce password reset for affected accounts; enable MFA for all privileged users; review lockout policy.")
    if "privilege_escalation" in sig_keys or "privilege_escalation" in triggers:
        rec.append("Audit recent privilege changes and group membership updates; rotate admin credentials; validate sudo/admin use.")
    if "dns_dga_pattern" in sig_keys or "dns_dga_pattern" in triggers:
        rec.append("Block suspicious domains at resolver and perimeter; check endpoints for beaconing; review DNS logs for related subdomains.")
    if "suspicious_outbound" in sig_keys or "large_data_transfer" in sig_keys:
        rec.append("Inspect outbound traffic for data exfil paths; quarantine endpoints showing repeated high-volume transfers; validate destinations.")
    if "persistence_attempt" in sig_keys or "rare_process_spawn" in sig_keys:
        rec.append("Review scheduled tasks/services/startup entries; inspect script execution history; collect EDR triage for impacted hosts.")
    if "log_tamper" in sig_keys or "log_tamper" in triggers:
        rec.append("Preserve original logs; verify collector integrity; compare against upstream sources; expand timeline window for gaps.")
    if not rec:
        rec.append("Maintain monitoring and validate anomalies with spot checks on top entities and peak timeline windows.")
    rec.append("Document all actions with timestamps and operator identity to preserve auditability.")
    return rec


def _num(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _present_path(raw: Dict[str, Any], spec: str) -> bool:
    if not spec:
        return False

    alts = [s.strip() for s in spec.split("|") if s.strip()]
    for s in alts:
        if "[]" in s:
            left, right = s.split("[]", 1)
            left = left.strip(".")
            right = right.strip(".")
            base = raw.get(left)
            if not isinstance(base, list) or not base:
                continue
            for it in base:
                if not isinstance(it, dict):
                    continue
                v = it.get(right) if right else it
                if v is None:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                if isinstance(v, (list, dict)) and len(v) == 0:
                    continue
                return True
        else:
            cur: Any = raw
            ok = True
            for p in s.split("."):
                p = p.strip()
                if not p:
                    continue
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if not ok:
                continue
            if cur is None:
                continue
            if isinstance(cur, str) and not cur.strip():
                continue
            if isinstance(cur, (list, dict)) and len(cur) == 0:
                continue
            return True
    return False


def _expected_fields() -> List[List[Tuple[str, str]]]:
    return [
        [
            ("case_id", "case_id"),
            ("evidence_list", "evidence_list"),
            ("evidence file_type", "evidence_list[].file_type"),
            ("evidence size_bytes", "evidence_list[].size_bytes"),
            ("evidence upload_time", "evidence_list[].upload_time"),
        ],
        [
            ("evidence_list", "evidence_list"),
            ("filename", "evidence_list[].filename"),
            ("file_type", "evidence_list[].file_type"),
            ("size_bytes", "evidence_list[].size_bytes"),
            ("upload_time", "evidence_list[].upload_time"),
        ],
        [
            ("evidence_list", "evidence_list"),
            ("filename", "evidence_list[].filename"),
            ("hash", "evidence_list[].sha256|evidence_list[].file_hash"),
            ("verification_status", "evidence_list[].verification_status"),
        ],
        [
            ("hash_chain", "hash_chain|chain_of_custody"),
            ("hash_chain.status", "hash_chain.status|chain_of_custody.status"),
            ("hash_chain.breaks", "hash_chain.breaks|chain_of_custody.breaks"),
            ("hash_chain.first_break_at", "hash_chain.first_break_at|chain_of_custody.first_break_at"),
        ],
        [
            ("parsing_summary", "parsing_summary"),
            ("total_records", "parsing_summary.total_records"),
            ("parsed_records", "parsing_summary.parsed_records"),
            ("unparsed_records", "parsing_summary.unparsed_records"),
            ("errors", "parsing_summary.errors"),
        ],
        [
            ("hot_store", "hot_store"),
            ("tables", "hot_store.tables"),
        ],
        [
            ("signals", "signals"),
        ],
        [
            ("anomaly_detection", "anomaly_detection"),
            ("scored_records", "anomaly_detection.scored_records"),
            ("anomalies_flagged", "anomaly_detection.anomalies_flagged"),
            ("score_min", "anomaly_detection.score_min"),
            ("score_max", "anomaly_detection.score_max"),
            ("scores", "anomaly_detection.scores"),
        ],
        [
            ("alerts", "alerts"),
            ("entity", "alerts[].entity"),
            ("risk_score", "alerts[].risk_score"),
            ("risk_level", "alerts[].risk_level"),
            ("triggers", "alerts[].triggers"),
        ],
        [
            ("timeline", "timeline"),
            ("timestamp", "timeline[].timestamp"),
            ("risk_score", "timeline[].risk_score"),
            ("summary", "timeline[].summary"),
            ("signals", "signals"),
            ("alerts", "alerts"),
        ],
    ]


def _coverage_table_for(idx: int, raw: Dict[str, Any], exp: List[List[Tuple[str, str]]]) -> Dict[str, Any]:
    rows: List[List[str]] = []
    if 0 <= idx < len(exp):
        for label, path in exp[idx]:
            rows.append([label, "Yes" if _present_path(raw, path) else "No"])
    if not rows:
        rows = [["N/A", "No"]]
    return {
        "title": "Data Coverage",
        "columns": ["Expected Field", "Present"],
        "rows": rows
    }


def _missing_fields_for(idx: int, raw: Dict[str, Any], exp: List[List[Tuple[str, str]]]) -> List[str]:
    miss: List[str] = []
    if 0 <= idx < len(exp):
        for label, path in exp[idx]:
            if not _present_path(raw, path):
                miss.append(label)
    return miss


def _availability_paragraphs(missing: List[str]) -> List[str]:
    if not missing:
        return []
    m = ", ".join(missing[:12])
    p = []
    p.append(f"Data availability note: the following expected fields were not present in the input payload: {m}.")
    p.append("Because these fields are missing, some summaries in this section may be incomplete or conservative, and specific conclusions may require re-ingestion or source-side validation.")
    p.append("If you can provide the missing fields on the next run, this section will automatically expand with stronger evidence-backed statements.")
    return p


def _extra_paragraphs(idx: int, stats: Dict[str, Any]) -> List[str]:
    ev = _safe_list(stats.get("ev"))
    sc = _safe_dict(stats.get("status_counts"))
    parsing = _safe_dict(stats.get("parsing"))
    hot = _safe_dict(stats.get("hot"))
    signals = _safe_dict(stats.get("signals"))
    anomaly = _safe_dict(stats.get("anomaly"))
    alerts = _safe_list(stats.get("alerts"))
    timeline = _safe_list(stats.get("timeline"))
    hash_chain = _safe_dict(stats.get("hash_chain"))

    file_count = len(ev)
    total_size = _human_bytes(stats.get("total_size", 0))
    earliest = _fmt_dt(stats.get("earliest"))
    latest = _fmt_dt(stats.get("latest"))

    extra: List[str] = []
    if idx == 0:
        extra.append(f"Evidence volume summary: {file_count} artifacts totaling {total_size}, observed between {earliest} and {latest}.")
        extra.append("This snapshot is intended to be a quick orientation layer before drilling into integrity, custody continuity, parsing coverage, and detection outputs.")
    elif idx == 1:
        largest = _safe_list(stats.get("largest"))
        if largest and isinstance(largest[0], dict):
            extra.append(f"Largest artifact observed: {largest[0].get('filename', 'N/A')} at {_human_bytes(largest[0].get('size_bytes'))}.")
        extra.append("Large artifacts often dominate runtime and are good candidates for prioritized indexing and targeted extraction.")
    elif idx == 2:
        valid = int(sc.get("VALID", 0) or 0)
        bad = 0
        for k, v in sc.items():
            if str(k).upper() in ["CORRUPTED", "INVALID", "FAIL"]:
                try:
                    bad += int(v)
                except Exception:
                    pass
        extra.append(f"Integrity roll-up: VALID={valid}, CORRUPTED/FAIL={bad}.")
        extra.append("Any failures should be isolated to avoid contaminating derived signals and anomaly scoring.")
    elif idx == 3:
        extra.append(f"Custody continuity indicator: status={hash_chain.get('status', 'N/A')}, breaks={hash_chain.get('breaks', 'N/A')}.")
        extra.append("If custody breaks exist, treat post-break artifacts as disputed until independently validated.")
    elif idx == 4:
        extra.append(f"Parsing coverage: total={parsing.get('total_records', 'N/A')}, parsed={parsing.get('parsed_records', 'N/A')}, unparsed={parsing.get('unparsed_records', 'N/A')}.")
        extra.append("Reducing dominant parse errors typically increases downstream correlation quality and lowers investigation blind spots.")
    elif idx == 5:
        tables = _safe_dict(hot.get("tables"))
        if tables:
            top = sorted(tables.items(), key=lambda x: _num(x[1]), reverse=True)[:3]
            extra.append("DuckDB materialization sanity check: " + ", ".join([f"{k}={v}" for k, v in top]) + ".")
        extra.append("Missing or near-empty tables usually indicate upstream parsing/mapping issues rather than a true absence of activity.")
    elif idx == 6:
        if signals:
            items = []
            for k, v in signals.items():
                if isinstance(v, dict):
                    items.append((k, _num(v.get("count", 0))))
                else:
                    items.append((k, _num(v)))
            items = sorted(items, key=lambda x: x[1], reverse=True)[:5]
            extra.append("Most frequent signals: " + ", ".join([f"{k}({int(v)})" for k, v in items]) + ".")
        extra.append("Signals are best interpreted as pivots: use them to jump into the exact event slices and supporting artifacts.")
    elif idx == 7:
        extra.append(f"Anomaly scoring summary: scored={anomaly.get('scored_records', 'N/A')}, flagged={anomaly.get('anomalies_flagged', 'N/A')}.")
        extra.append("Flagged records are triage candidates; corroborate them using integrity, custody continuity, and correlated telemetry.")
    elif idx == 8:
        if alerts:
            extra.append(f"Alert volume: {len(alerts)} alert rows available for ranking and triage.")
        extra.append("Entity aggregation helps reduce noise by focusing effort on the smallest set of principals accounting for most risk.")
    elif idx == 9:
        if timeline:
            peaks = sorted(
                [t for t in timeline if isinstance(t, dict)],
                key=lambda x: _num(x.get("risk_score", 0)),
                reverse=True
            )[:2]
            if peaks:
                extra.append(f"Top peak window example: {_fmt_dt(peaks[0].get('timestamp'))} with risk {peaks[0].get('risk_score', 'N/A')}.")
        extra.append("Recommended actions are generated from dominant triggers and should be logged with operator identity and timestamps.")
    return extra


def _enforce_no_blank_sections(preview: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    pv = _safe_dict(preview)
    pages = pv.get("pages")
    if not isinstance(pages, list):
        return pv

    exp = _expected_fields()
    stats = _extract_stats(raw)

    for idx in range(len(pages)):
        sec = pages[idx]
        if not isinstance(sec, dict):
            continue

        paras = []
        for p in _safe_list(sec.get("paragraphs")):
            if isinstance(p, str) and p.strip():
                paras.append(p.strip())
        sec["paragraphs"] = paras

        chs = []
        for c in _safe_list(sec.get("charts")):
            if isinstance(c, dict) and c.get("b64"):
                chs.append(c)
        sec["charts"] = chs

        tbs = []
        for tb in _safe_list(sec.get("tables")):
            if not isinstance(tb, dict):
                continue
            cols = tb.get("columns")
            rows = tb.get("rows")
            cols_ok = isinstance(cols, list) and len(cols) > 0
            rows_ok = isinstance(rows, list) and len(rows) > 0
            if not cols_ok and not rows_ok:
                continue
            tbs.append(tb)
        sec["tables"] = tbs

        lss = []
        for ls in _safe_list(sec.get("lists")):
            if not isinstance(ls, dict):
                continue
            items = ls.get("items")
            if not isinstance(items, list) or len(items) == 0:
                continue
            clean_items = []
            for it in items:
                if it is None:
                    continue
                s = str(it)
                if s.strip():
                    clean_items.append(s.strip())
            if len(clean_items) == 0:
                continue
            ls["items"] = clean_items
            lss.append(ls)
        sec["lists"] = lss

        if len(sec["paragraphs"]) < 3:
            for p in _extra_paragraphs(idx, stats):
                if len(sec["paragraphs"]) >= 3:
                    break
                if isinstance(p, str) and p.strip():
                    sec["paragraphs"].append(p.strip())

        if len(sec["paragraphs"]) < 3:
            missing = _missing_fields_for(idx, raw, exp)
            for p in _availability_paragraphs(missing):
                if len(sec["paragraphs"]) >= 3:
                    break
                if isinstance(p, str) and p.strip():
                    sec["paragraphs"].append(p.strip())

        if len(sec["paragraphs"]) == 0:
            sec["paragraphs"] = ["No narrative content could be generated for this section from the provided payload."]

        if len(sec.get("charts", [])) == 0 and len(sec.get("tables", [])) == 0 and len(sec.get("lists", [])) == 0:
            sec["tables"] = _safe_list(sec.get("tables")) + [_coverage_table_for(idx, raw, exp)]

        pages[idx] = sec

    pv["pages"] = pages
    return pv


def _build_pages(raw: Dict[str, Any]) -> Dict[str, Any]:
    stats = _extract_stats(raw)
    case_id = raw.get("case_id", "CASE-UNKNOWN")
    generated_at = raw.get("generated_at", datetime.now().isoformat())

    verdict_text, verdict_reason = _verdict(stats)

    ev = _safe_list(stats.get("ev"))
    file_count = len(ev)
    total_size = _human_bytes(stats.get("total_size", 0))
    earliest = _fmt_dt(stats.get("earliest"))
    latest = _fmt_dt(stats.get("latest"))

    ft_sorted = sorted(_safe_dict(stats.get("file_types")).items(), key=lambda x: x[1], reverse=True)
    top_types = ", ".join([f"{k}({v})" for k, v in ft_sorted[:5]]) if ft_sorted else "N/A"

    p1 = [
        f"Case {case_id} was processed to summarize evidence intake, integrity, custody continuity, normalization quality, behavioral signals, and anomaly outcomes.",
        f"The dataset contains {file_count} artifacts with a combined size of {total_size}. The observed upload window spans from {earliest} to {latest}.",
        f"Most frequent formats in this dataset: {top_types}. These distributions help anticipate which parsers and correlation paths will contribute most to the investigation."
    ]

    largest_rows = []
    for f in _safe_list(stats.get("largest")):
        if not isinstance(f, dict):
            continue
        largest_rows.append([
            f.get("filename", "N/A"),
            (f.get("file_type") or "unknown"),
            _human_bytes(f.get("size_bytes")),
            _fmt_dt(f.get("upload_time")),
        ])

    p2 = [
        "Evidence intake summarizes what was received, when it was received, and how it was categorized for downstream processing.",
        "Artifacts are grouped by format and size to identify heavy sources (for example, memory dumps or PCAP segments) and to verify that the expected telemetry types are present.",
        "The table below highlights the largest artifacts, which typically dominate processing time and often hold high-value forensic context."
    ]

    sc = _safe_dict(stats.get("status_counts"))
    valid = int(sc.get("VALID", 0) or 0)
    corrupted = 0
    for k, v in sc.items():
        if str(k).upper() in ["CORRUPTED", "INVALID", "FAIL"]:
            try:
                corrupted += int(v)
            except Exception:
                pass

    integrity_rows = []
    for f in _safe_list(ev)[:20]:
        if isinstance(f, dict):
            integrity_rows.append([
                f.get("filename", "N/A"),
                _short_hash(f.get("sha256") or f.get("file_hash")),
                (f.get("verification_status") or "UNKNOWN").upper()
            ])

    p3 = [
        "Per-file integrity verification ensures evidence remains bit-consistent from intake through processing.",
        f"Overall distribution: VALID={valid}, CORRUPTED/FAIL={corrupted}.",
        "Any corrupted or failed artifacts should be isolated for re-acquisition or manual handling to avoid contaminating downstream analytics."
    ]

    hc = _safe_dict(stats.get("hash_chain"))
    hc_status = (hc.get("status") or "N/A")
    hc_breaks = hc.get("breaks", "N/A")
    hc_first_break = hc.get("first_break_at", None)

    p4 = [
        "Chain-of-custody status summarizes whether custody continuity was preserved across the evidence lifecycle.",
        f"Hash chain status: {hc_status}. Breaks observed: {hc_breaks}. First break: {_fmt_dt(hc_first_break)}.",
        "If breaks are present, evidence after the first break should be treated as disputed until independently validated."
    ]

    parsing = _safe_dict(stats.get("parsing"))
    total_records = parsing.get("total_records", None)
    parsed_records = parsing.get("parsed_records", None)
    unparsed_records = parsing.get("unparsed_records", None)
    err = _safe_dict(parsing.get("errors"))

    err_items = sorted(err.items(), key=lambda x: _num(x[1]), reverse=True)[:6]
    err_text = ", ".join([f"{k}={v}" for k, v in err_items]) if err_items else "N/A"

    p5 = [
        "Parsing and normalization summarize how much raw telemetry could be converted into structured records ready for correlation.",
        f"Records: total={total_records if total_records is not None else 'N/A'}, parsed={parsed_records if parsed_records is not None else 'N/A'}, unparsed={unparsed_records if unparsed_records is not None else 'N/A'}.",
        f"Top parse error reasons: {err_text}. Addressing dominant error types typically improves coverage and reduces blind spots."
    ]

    hot = _safe_dict(stats.get("hot"))
    tables = _safe_dict(hot.get("tables"))
    hot_rows = [[k, str(v)] for k, v in sorted(tables.items(), key=lambda x: _num(x[1]), reverse=True)] if tables else []

    p6 = [
        "Hot store ingestion summarizes which normalized datasets were materialized for fast querying and analytics.",
        "DuckDB table counts are a quick sanity check: they confirm that event streams, entities, indicators, and alerts were actually persisted after parsing.",
        "If any expected table is missing or near-empty, it usually indicates an upstream parsing or mapping issue."
    ]

    signals = _safe_dict(stats.get("signals"))
    sig_items: Dict[str, float] = {}
    for k, v in signals.items():
        if isinstance(v, dict):
            sig_items[k] = _num(v.get("count", 0))
        else:
            sig_items[k] = _num(v)

    p7 = [
        "Behavioral features describe what signals were computed from normalized records (for example: login velocity spikes, impossible travel, privilege escalations).",
        "Signal counts give a quick view of coverage: higher counts often represent broad, low-confidence indicators; smaller counts can represent high-precision detections.",
        "The chart below highlights the most frequent signals in this dataset."
    ]

    anomaly = _safe_dict(stats.get("anomaly"))
    scored = anomaly.get("scored_records", None)
    flagged = anomaly.get("anomalies_flagged", None)
    smin = anomaly.get("score_min", None)
    smax = anomaly.get("score_max", None)
    scores_list = anomaly.get("scores", [])
    scores_vals: List[float] = []
    for x in _safe_list(scores_list):
        try:
            scores_vals.append(float(x))
        except Exception:
            pass

    p8 = [
        "Anomaly detection summarizes how many records were scored and how many were flagged above the anomaly threshold.",
        f"Scored={scored if scored is not None else 'N/A'}, flagged={flagged if flagged is not None else 'N/A'}, score range={smin if smin is not None else 'N/A'} to {smax if smax is not None else 'N/A'}.",
        "A tight score range usually indicates stable behavior; sharp peaks or long tails typically indicate bursty or staged activity."
    ]

    entity_risks: Dict[str, float] = {}
    for a in _safe_list(stats.get("alerts")):
        if not isinstance(a, dict):
            continue
        e = a.get("entity", "unknown")
        rs = _num(a.get("risk_score", 0))
        entity_risks[e] = max(entity_risks.get(e, 0.0), rs)

    top_entities = sorted(entity_risks.items(), key=lambda x: x[1], reverse=True)[:10]

    alert_rows = []
    for a in _safe_list(stats.get("alerts"))[:15]:
        if isinstance(a, dict):
            tr = a.get("triggers")
            if isinstance(tr, list):
                tr_s = ", ".join([str(x) for x in tr if x is not None])
            else:
                tr_s = str(tr or "")
            alert_rows.append([
                a.get("entity", "N/A"),
                str(a.get("risk_score", "N/A")),
                str(a.get("risk_level", "N/A")),
                tr_s[:80]
            ])

    p9 = [
        "High-risk entities consolidate alerts by principal (user, host, IP, domain) and provide a ranked view of the most concerning actors.",
        "A small number of entities frequently account for most high-confidence risk, making them good candidates for triage and containment checks.",
        "The table below lists the highest-risk items and the triggers that caused scoring."
    ]

    tl = _safe_list(stats.get("timeline"))
    peaks = sorted(
        [t for t in tl if isinstance(t, dict)],
        key=lambda x: _num(x.get("risk_score", 0)),
        reverse=True
    )[:5]

    peak_lines = []
    for t in peaks:
        peak_lines.append(f"{_fmt_dt(t.get('timestamp'))} — risk {t.get('risk_score', 'N/A')} — {t.get('summary', 'Peak activity window.')}")

    rec_actions = _recommended_actions(stats)

    p10 = [
        "Timeline highlights summarize how risk evolved over the observed window and identify the most important time slices for deeper artifact correlation.",
        "Peak windows are the best starting point for reconstruction: pivot from the timestamp into supporting logs, process events, DNS, and network captures.",
        "Recommended actions are derived from the dominant triggers observed in signals and entity alerts."
    ]

    charts = {
        "file_types": _b64_png_from_buf(GraphEngine.pie_chart(_safe_dict(stats.get("file_types")), "Evidence File Type Distribution")) if _safe_dict(stats.get("file_types")) else None,
        "integrity": _b64_png_from_buf(GraphEngine.bar_chart({k: _num(v) for k, v in _safe_dict(stats.get("status_counts")).items()}, "Integrity Verification Results", "Status")) if _safe_dict(stats.get("status_counts")) else None,
        "signals": _b64_png_from_buf(GraphEngine.bar_chart(sig_items, "Top Behavioral Signals", "Signal")) if sig_items else None,
        "top_entities": _b64_png_from_buf(GraphEngine.horizontal_bar(dict(top_entities), "Top High-Risk Entities")) if top_entities else None,
        "timeline": _b64_png_from_buf(GraphEngine.line_chart(tl, "Risk Score Over Time")) if tl else None,
        "scores": _b64_png_from_buf(GraphEngine.hist_chart(scores_vals, "Anomaly Score Distribution")) if scores_vals else None,
        "parse_errors": _b64_png_from_buf(GraphEngine.bar_chart({k: _num(v) for k, v in err.items()}, "Top Parse Error Reasons", "Error Type")) if err else None,
        "duckdb": _b64_png_from_buf(GraphEngine.bar_chart({k: _num(v) for k, v in tables.items()}, "DuckDB Table Row Counts", "Table")) if tables else None,
    }

    toc = [
        "Case Snapshot and Dataset Overview",
        "Evidence Intake Summary (Files, Formats, Sizes, Upload Times)",
        "Integrity Status (Per-File Hash Verification Results)",
        "Chain-of-Custody Status (Hash Chain Verification Results)",
        "Parsing and Normalization Summary (Parsed vs Unparsed Records)",
        "Hot Store Ingestion Summary (DuckDB Tables and Row Counts)",
        "Behavioral Feature Summary (Signals Generated and Coverage)",
        "Anomaly Detection Summary (Total Scored, Anomalies Flagged, Score Range)",
        "High-Risk Entities and Alerts (Users/IPs, Risk Levels, Key Triggers)",
        "Investigation Timeline Highlights and Recommended Actions"
    ]

    pages = [
        {"title": toc[0], "paragraphs": p1, "tables": [], "charts": [{"b64": charts["file_types"]}] if charts["file_types"] else [], "lists": []},
        {"title": toc[1], "paragraphs": p2, "tables": [{"title": "Largest Artifacts (Top 10)", "columns": ["Filename", "Type", "Size", "Upload Time"], "rows": largest_rows}] if largest_rows else [], "charts": [{"b64": charts["file_types"]}] if charts["file_types"] else [], "lists": []},
        {"title": toc[2], "paragraphs": p3, "tables": [{"title": "Integrity Status (First 20)", "columns": ["Filename", "SHA-256 (short)", "Status"], "rows": integrity_rows}] if integrity_rows else [], "charts": [{"b64": charts["integrity"]}] if charts["integrity"] else [], "lists": []},
        {"title": toc[3], "paragraphs": p4, "tables": [{"title": "Hash Chain Summary", "columns": ["Status", "Breaks", "First Break"], "rows": [[str(hc_status), str(hc_breaks), _fmt_dt(hc_first_break)]]}], "charts": [], "lists": []},
        {"title": toc[4], "paragraphs": p5, "tables": [], "charts": ([{"b64": charts["parse_errors"]}] if charts["parse_errors"] else []), "lists": []},
        {"title": toc[5], "paragraphs": p6, "tables": [{"title": "DuckDB Materialization", "columns": ["Table", "Rows"], "rows": hot_rows}] if hot_rows else [], "charts": ([{"b64": charts["duckdb"]}] if charts["duckdb"] else []), "lists": []},
        {"title": toc[6], "paragraphs": p7, "tables": [], "charts": ([{"b64": charts["signals"]}] if charts["signals"] else []), "lists": []},
        {"title": toc[7], "paragraphs": p8, "tables": [], "charts": ([{"b64": charts["scores"]}] if charts["scores"] else []), "lists": []},
        {"title": toc[8], "paragraphs": p9, "tables": [{"title": "Top Alerts (First 15)", "columns": ["Entity", "Risk Score", "Risk Level", "Key Triggers"], "rows": alert_rows}] if alert_rows else [], "charts": ([{"b64": charts["top_entities"]}] if charts["top_entities"] else []), "lists": []},
        {"title": toc[9], "paragraphs": p10, "tables": [], "charts": ([{"b64": charts["timeline"]}] if charts["timeline"] else []), "lists": [{"title": "Peak Windows (Top 5)", "items": peak_lines} if peak_lines else {"title": "Peak Windows", "items": ["N/A"]}, {"title": "Recommended Actions", "items": rec_actions}]},
    ]

  

    return {
        "meta": {
            "case_id": case_id, 
            "generated_at": generated_at, 
            "verdict": verdict_text, 
            "verdict_reason": verdict_reason,
            "cover_b64": _get_cover_b64()  # <--- ADD THIS LINE
        },
        "toc": [{"no": i + 1, "title": toc[i], "page": i + 3} for i in range(len(toc))],
        "pages": pages
    }

def _draw_cover(canvas, doc):
    cover_path = os.path.join(os.path.dirname(__file__), "assets", "cover.png")
    if os.path.exists(cover_path):
        w, h = A4
        canvas.saveState()
        canvas.drawImage(ImageReader(cover_path), 0, 0, width=w, height=h, mask="auto")
        canvas.restoreState()


def build_report_preview(raw_data_object):
    raw = _safe_dict(raw_data_object)
    preview = _build_pages(raw)
    return _enforce_no_blank_sections(preview, raw)


def generate_forensic_report(raw_data_object: Dict[str, Any], language="English", custom_color=None) -> str:
    preview = build_report_preview(raw_data_object)

    case_id = preview["meta"]["case_id"]
    filename = f"FULL_REPORT_{case_id}.pdf"

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        topMargin=40,
        bottomMargin=40,
        leftMargin=40,
        rightMargin=40
    )

    theme_color = colors.HexColor(custom_color) if custom_color else colors.HexColor("#003366")
    styles = getSampleStyleSheet()
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, textColor=theme_color, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_JUSTIFY)

    story: List[Any] = []

    # Page 1: cover template (image drawn via onFirstPage). We must place at least one flowable on page 1.
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # Page 2: TOC
    story.append(Paragraph("TABLE OF CONTENTS", h2))
    toc_rows = [["#", "SECTION TITLE", "PAGE"]]
    for r in _safe_list(preview.get("toc")):
        if isinstance(r, dict):
            toc_rows.append([str(r.get("no", "")), str(r.get("title", "")), str(r.get("page", ""))])

    tt = Table(toc_rows, colWidths=[30, 380, 50])
    tt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tt)
    story.append(PageBreak())

    # Pages 3+: sections
    pages = _safe_list(preview.get("pages"))
    for i, sec in enumerate(pages, start=1):
        if not isinstance(sec, dict):
            continue

        story.append(Paragraph(f"{i}. {sec.get('title', 'Untitled')}", h2))

        for para in _safe_list(sec.get("paragraphs")):
            story.append(Paragraph(str(para), body))
            story.append(Spacer(1, 8))

        for ch in _safe_list(sec.get("charts")):
            if not isinstance(ch, dict):
                continue
            b64 = ch.get("b64")
            if not b64:
                continue
            img_bytes = base64.b64decode(str(b64).encode("utf-8"))
            buf = io.BytesIO(img_bytes)
            story.append(Image(buf, width=6.2 * inch, height=3.1 * inch))
            story.append(Spacer(1, 10))

        for tb in _safe_list(sec.get("tables")):
            if not isinstance(tb, dict):
                continue

            story.append(Paragraph(
                tb.get("title", ""),
                ParagraphStyle("TBH", parent=styles["Normal"], fontSize=10, textColor=theme_color, spaceBefore=6, spaceAfter=6)
            ))

            cols = tb.get("columns", [])
            rows = tb.get("rows", [])
            cols = cols if isinstance(cols, list) else []
            rows = rows if isinstance(rows, list) else []
            table_data = [cols] + rows if cols else rows

            col_widths = None
            if cols and len(cols) == 4:
                col_widths = [220, 60, 70, 120]
            elif cols and len(cols) == 3:
                col_widths = [260, 140, 80]
            elif cols and len(cols) == 2:
                col_widths = [300, 150]

            rt = Table(table_data, colWidths=col_widths)
            rt.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), theme_color if cols else colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(rt)
            story.append(Spacer(1, 10))

        for ls in _safe_list(sec.get("lists")):
            if not isinstance(ls, dict):
                continue
            story.append(Paragraph(
                ls.get("title", ""),
                ParagraphStyle("LSH", parent=styles["Normal"], fontSize=10, textColor=theme_color, spaceBefore=6, spaceAfter=4)
            ))
            for item in _safe_list(ls.get("items")):
                story.append(Paragraph("• " + str(item), body))
            story.append(Spacer(1, 6))

        if i != len(pages):
            story.append(PageBreak())

    doc.build(story, onFirstPage=_draw_cover)
    return filename