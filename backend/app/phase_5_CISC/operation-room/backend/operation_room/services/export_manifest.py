import os
import json
import zipfile
import hashlib
import rfc3161ng
import requests
import base64
from typing import Optional
from pathlib import Path
from fastapi import HTTPException
from canonicaljson import encode_canonical_json
from operation_room.config import settings

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

# ── PKI Vault Key Mock (In prod, grab from Secret Manager) ──
_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

def generate_cryptographic_export(case_id: str, include_tsa: bool = False) -> str:
    """
    Gathers PDF, Canvas AST, and artifacts/ folder.
    Generates deterministic JSON manifest.
    Zips them and returns filepath to tamper-evident zip.
    """
    case_dir = settings.DATA_DIR / "cases" / case_id
    if not case_dir.exists():
        raise HTTPException(404, "Case vault directory not found")

    artifacts_dir = case_dir / "artifacts"
    exports_dir = case_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Read all JSON artifacts sequentially and hash their contents
    manifest_artifacts = []
    if artifacts_dir.exists():
        for filename in sorted(os.listdir(artifacts_dir)):
            filepath = artifacts_dir / filename
            if filepath.is_file() and filepath.name.endswith(".json"):
                with open(filepath, 'rb') as f:
                    file_bytes = f.read()
                manifest_artifacts.append({
                    "filename": f"artifacts/{filename}",
                    "hash": hashlib.sha256(file_bytes).hexdigest()
                })

    # We mock reading standard PDF/AST inputs if they don't explicitly exist yet
    # since we're decoupling. The Frontend may post them to backend soon.       

    manifest = {
        "docId": f"REPORT-{case_id}",
        "version": "1.0",
        "artifacts": manifest_artifacts,
        "tsa_timestamp": None,
        "tsa_signature_b64": None
    }

    # 2. Convert to canonical json using RFC 8785
    # Wait, canonicaljson encode returns bytes
    encoded_manifest = encode_canonical_json(manifest)
    manifest_hash = hashlib.sha256(encoded_manifest).hexdigest()

    # Hit external TSA Authority (RFC 3161)
    if include_tsa:
        try:
            tsa = rfc3161ng.RemoteTimestamper('https://freetsa.org/tsr')
            req = tsa.make_request(data=encoded_manifest, hashname='sha256')    
            req_data = rfc3161ng.encode_request(req)
            
            # Post manually if we want robustness, or let rfc3161ng handle it:   
            resp_data = requests.post(
                'https://freetsa.org/tsr',
                data=req_data,
                headers={'Content-Type': 'application/timestamp-query'}         
            ).content
            
            tst = rfc3161ng.decode_response(resp_data)
            tsa.check_response(req, resp_data)
            
            # Extract timestamp from signature
            # rfc3161ng gets timestamp object
            timestamp = rfc3161ng.get_timestamp(tst)
            
            manifest["tsa_timestamp"] = timestamp.isoformat()
            manifest["tsa_provider"] = "FreeTSA (https://freetsa.org/tsr)"       
            manifest["tsa_signature_b64"] = base64.b64encode(resp_data).decode('utf-8')
            
            # Need to re-encode if we mutated it
            encoded_manifest = encode_canonical_json(manifest)
            manifest_hash = hashlib.sha256(encoded_manifest).hexdigest()        
        except Exception as e:
            # Fallback or log if unreachable
            import logging
            logging.error(f"TSA Timestamping failed: {e}")
            manifest["tsa_timestamp"] = "TSA_FAILED"
            manifest["tsa_error"] = str(e)
            encoded_manifest = encode_canonical_json(manifest)
            manifest_hash = hashlib.sha256(encoded_manifest).hexdigest()        

    # Phase 5: Standard PKI Private-Key Signing
    # The system signs the canonical structure, ensuring multi-tenant robustness.
    # Note: Only the content generated up to this point is signed.
    signature = _PRIVATE_KEY.sign(
        encoded_manifest,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    manifest["pki_signature_b64"] = base64.b64encode(signature).decode('utf-8')
    manifest["pki_public_key_pem"] = _PUBLIC_KEY.public_bytes(
        encoding=__import__('cryptography').hazmat.primitives.serialization.Encoding.PEM,
        format=__import__('cryptography').hazmat.primitives.serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8').strip()

    # Final rebuild of hash post-signature insertion
    encoded_manifest = encode_canonical_json(manifest)
    manifest_hash = hashlib.sha256(encoded_manifest).hexdigest()

    manifest_path = exports_dir / "manifest.json"
    with open(manifest_path, "wb") as f:
        # Just write the canonical bytes, appending the meta-hash at the end manually
        # Canonicalization is strict so we re-serialize normally to bundle the signature.
        pass
        
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
        
    # 3. Zip it up
    export_bundle_path = exports_dir / f"export_{case_id}_{manifest_hash[:8]}.zip"
    
    def add_file_reproducible(target_zip, source_path, arcname):
        # We manually construct ZipInfo to force 1980-01-01 timestamps for determinism
        zinfo = zipfile.ZipInfo(arcname, (1980, 1, 1, 0, 0, 0))
        zinfo.compress_type = zipfile.ZIP_DEFLATED
        with open(source_path, 'rb') as src:
            target_zip.writestr(zinfo, src.read())

    with zipfile.ZipFile(export_bundle_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        add_file_reproducible(zipf, manifest_path, "manifest.json")
        if artifacts_dir.exists():
            for filename in os.listdir(artifacts_dir):
                filepath = artifacts_dir / filename
                if filepath.is_file():
                    add_file_reproducible(zipf, filepath, f"artifacts/{filename}")
                    
    return str(export_bundle_path)
