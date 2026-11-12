import pytest
import hashlib
import uuid
from operation_room.services.export_manifest import generate_cryptographic_export
from operation_room.services.case_service import create_case

def test_export_reproducibility(tmp_path):
    """
    Phase 3: Dual-Pass QA Job.
    Ensures that generating the cryptographic zip array on the identical DuckDB set
    produces the exact same SHA-256 hash. RFC 8785 Canonicalisation must not drift.
    """
    case_payload = {
        "title": "QA Reproducibility Test",
        "description": "Ghost timelines and clock drift tests",
        "priority": "HIGH",
        "scope": [{"source_type": "host", "target_systems": ["test-dc"]}]
    }

    import operation_room.services.export_manifest as em
    from unittest.mock import patch
    
    # Create Case Vault
    case = create_case(case_payload)
    case_id = case["case_id"]

    class MockKey:
        def sign(self, *args, **kwargs): return b"MOCK_SIG"
    class MockPubKey:
        def public_bytes(self, *args, **kwargs): return b"MOCK_PUB"

    em._PRIVATE_KEY = MockKey()
    em._PUBLIC_KEY = MockPubKey()

    # Pass 1: Generate Export A
    export_A_path = generate_cryptographic_export(case_id)
    with open(export_A_path, "rb") as f:
        hash_A = hashlib.sha256(f.read()).hexdigest()

    # Pass 2: Generate Export B on an identical container thread emulation  
    export_B_path = generate_cryptographic_export(case_id)
    with open(export_B_path, "rb") as f:
        hash_B = hashlib.sha256(f.read()).hexdigest()

    # Explicitly Assert Mathematical Determinism
    assert hash_A == hash_B, f"Canonical Reproducibility Drift Detected! {hash_A} != {hash_B}"

    # Cleanup QA test case
    import shutil
    import operation_room.config
    case_path = app.config.settings.CASES_DIR / case_id
    if case_path.exists():
        shutil.rmtree(case_path, ignore_errors=True)

