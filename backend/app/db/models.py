import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Float, Text
from app.db.base import Base


# ---------------------------------------------------------------------------
# Original audit ledger — NOT modified; backward-compatible additions only
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    sha256_hash = Column(String, nullable=False)
    previous_hash = Column(String, nullable=True)
    merkle_root = Column(String, nullable=True)          # NEW: Merkle seal
    upload_time = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer, nullable=False)
    uploader = Column(String, nullable=True)
    source_ip = Column(String, nullable=True)             # NEW: origin IP
    ingestion_mode = Column(String, nullable=True)        # NEW: manual/cloud/agent
    status = Column(String, default="ingested")


# ---------------------------------------------------------------------------
# JIT Ephemeral Session Table
# ---------------------------------------------------------------------------

class IngestionSession(Base):
    """
    Short-lived session record created at ingestion entry.
    Enforces IP binding, TTL, and burn-on-use semantics.
    """
    __tablename__ = "ingestion_sessions"

    session_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    bound_ip = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    mode = Column(String, nullable=False)                 # manual | cloud | agent
    created_at = Column(DateTime, default=datetime.utcnow)
    audit_id = Column(String, nullable=True)              # linked after ledger commit


# ---------------------------------------------------------------------------
# Quarantine Log Table
# ---------------------------------------------------------------------------

class QuarantineLog(Base):
    """
    Records files that failed sandbox triage.
    Legally traceable quarantine chain-of-custody.
    """
    __tablename__ = "quarantine_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String, nullable=False)
    quarantine_path = Column(String, nullable=False)
    sha256_hash = Column(String, nullable=True)
    reason = Column(String, nullable=False)               # ZIP_BOMB | MAGIC_MISMATCH | MALWARE | ENTROPY_HIGH
    risk_score = Column(Float, nullable=True)
    details = Column(Text, nullable=True)                 # JSON-encoded detail blob
    detected_at = Column(DateTime, default=datetime.utcnow)
    source_ip = Column(String, nullable=True)
    ingestion_mode = Column(String, nullable=True)
    session_id = Column(String, nullable=True)


# ---------------------------------------------------------------------------
# Phase 2: Hybrid Parsing & Data Normalization Tables
# ---------------------------------------------------------------------------

class TemplateRegistry(Base):
    """
    DRAIN3 template registry for log parsing.
    Stores event templates and extracted variables.
    """
    __tablename__ = "template_registry"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id = Column(String, nullable=True)
    template = Column(Text, nullable=False)
    variables = Column(Text, nullable=True)  # JSON-encoded
    cache_key = Column(String, unique=True, nullable=True)
    template_word_category = Column(Text, nullable=True)  # Category description (min 150 words)
    learned_patterns = Column(Text, nullable=True)  # JSON-encoded learned patterns from AI parsing
    pattern_hash = Column(String, nullable=True)  # Hash of template structure for similarity matching
    match_count = Column(Integer, default=1)  # Number of times this template matched
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class StagingArea(Base):
    """
    Human-in-the-loop staging area for processed data.
    Data remains here until human confirmation.
    """
    __tablename__ = "staging_area"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id = Column(String, nullable=False)
    row_hash = Column(String, nullable=False)
    immutable_pointer = Column(String, nullable=True)
    decoded_payload = Column(Text, nullable=True)  # JSON-encoded
    decode_trace = Column(Text, nullable=True)  # JSON-encoded
    template_id = Column(String, nullable=True)
    extracted_variables = Column(Text, nullable=True)  # JSON-encoded
    ner_tags = Column(Text, nullable=True)  # JSON-encoded
    normalized_timestamp = Column(DateTime, nullable=True)
    human_overrides = Column(Text, nullable=True)  # JSON-encoded
    status = Column(String, default="pending")  # pending | confirmed | committed | rejected
    created_at = Column(DateTime, default=datetime.utcnow)


class LineageAnchor(Base):
    """
    Immutable pointers linking processed rows to source files.
    Creates tamper-evident lineage chain.
    """
    __tablename__ = "lineage_anchors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    audit_id = Column(String, nullable=False)
    source_file_hash = Column(String, nullable=False)
    byte_offset = Column(Integer, nullable=False)
    row_hash = Column(String, nullable=False)
    duckdb_row_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
