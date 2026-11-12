from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class Redaction:
    kind: str
    start: int
    end: int


_PATTERNS: Tuple[Tuple[str, re.Pattern[str]], ...] = (
    ("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9\-\._~\+\/]+=*\b")),
    ("PASSWORD", re.compile(r"\b[Pp]assword[\s:=]+[^\s,;]{4,}\b")),
    ("IN_AADHAAR", re.compile(r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)


def find_redactions(text: str) -> Iterable[Redaction]:
    for kind, pat in _PATTERNS:
        for m in pat.finditer(text or ""):
            yield Redaction(kind=kind, start=m.start(), end=m.end())


def apply_redactions(text: str) -> Tuple[str, int]:
    """
    Returns (redacted_text, redaction_count).
    """
    if not text:
        return "", 0

    matches = sorted(find_redactions(text), key=lambda r: (r.start, r.end))
    if not matches:
        return text, 0

    # merge overlaps
    merged: list[Redaction] = []
    for r in matches:
        if not merged:
            merged.append(r)
            continue
        prev = merged[-1]
        if r.start <= prev.end:
            merged[-1] = Redaction(kind=prev.kind, start=prev.start, end=max(prev.end, r.end))
        else:
            merged.append(r)

    out = []
    last = 0
    for r in merged:
        out.append(text[last : r.start])
        out.append(f"[ENC:gcm:{r.kind}_REDACTED]")
        last = r.end
    out.append(text[last:])
    return "".join(out), len(merged)


def compute_privacy_confidence(redaction_count: int) -> float:
    """
    A simple proxy score (0..1). More redactions => higher confidence that sensitive content existed.
    """
    if redaction_count <= 0:
        return 0.0
    # saturating curve
    return min(1.0, 0.55 + 0.15 * redaction_count)


def is_privacy_bypass_enabled() -> bool:
    return os.getenv("PHASE3_PRIVACY_BYPASS", "").lower() in {"1", "true", "yes", "on"}

