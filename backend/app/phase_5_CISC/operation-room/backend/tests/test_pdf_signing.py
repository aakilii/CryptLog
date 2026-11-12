import json

from operation_room.services.pdf_signer import PDFSigner
from operation_room.services.pdf_integrity import PDFIntegrityService


def test_pdf_sign_and_verify_roundtrip():
    signer = PDFSigner()
    payload = b"test-pdf-content"
    signed = signer.sign_bytes(payload)
    assert signed.signature_b64
    assert "BEGIN PUBLIC KEY" in signed.public_key_pem
    assert PDFSigner.verify_bytes(payload, signed.signature_b64, signed.public_key_pem) is True


def test_integrity_manifest_shape():
    integrity = PDFIntegrityService()
    manifest = integrity.build_export_manifest(
        case_id="case-1",
        doc_id="doc-1",
        actor="investigator",
        focus_mode="Review",
        generation_manifest={"engine": "ReportLab"},
        pdf_hash=integrity.hash_pdf(b"pdf-bytes"),
        signature="sig",
        signature_algorithm="RSA-PSS-SHA256",
        public_key_pem="pem",
    )
    assert manifest["case_id"] == "case-1"
    assert manifest["doc_id"] == "doc-1"
    assert manifest["pdf_sha256"]
    assert manifest["signature_algorithm"] == "RSA-PSS-SHA256"


def test_pdf_tamper_detection():
    signer = PDFSigner()
    original = b"%PDF-1.7 original bytes"
    signed = signer.sign_bytes(original)

    tampered = b"%PDF-1.7 tampered bytes"
    assert PDFSigner.verify_bytes(tampered, signed.signature_b64, signed.public_key_pem) is False
