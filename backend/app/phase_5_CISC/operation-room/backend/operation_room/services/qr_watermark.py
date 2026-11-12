"""
Cryptographic QR Watermark for Court-Ready PDFs.

Embeds a compact QR code in the PDF header/footer containing:
- SHA-256 hash of the ReportManifest
- Case ID and report ID
- Deep-link URI back to the platform
- Signature timestamp

This allows a judge to scan a printout and verify the original
digital record via the NFLIP platform.

Usage:
    from operation_room.services.qr_watermark import QRWatermark
    
    qr = QRWatermark(platform_url="https://nflip.example.com")
    qr.add_to_pdf(
        pdf_path="report.pdf",
        case_id="CASE-001",
        report_id="RPT-001",
        manifest_hash="sha256:abc123...",
    )
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class QRWatermark:
    """Generates and embeds cryptographic QR codes into PDF reports."""

    def __init__(
        self,
        platform_url: str = "https://nflip.forensic.local",
        qr_size_mm: int = 15,
    ) -> None:
        self.platform_url = platform_url.rstrip("/")
        self.qr_size_mm = qr_size_mm

    def generate_qr_data(
        self,
        case_id: str,
        report_id: str,
        manifest_hash: str,
        signer_identity: str = "",
    ) -> str:
        """
        Generate the payload to embed in the QR code.
        
        Returns a JSON string containing the verification data.
        """
        deep_link = f"{self.platform_url}/verify/{case_id}/{report_id}"
        payload = {
            "v": 1,  # schema version
            "case": case_id,
            "report": report_id,
            "hash": manifest_hash[:24] if len(manifest_hash) > 24 else manifest_hash,
            "url": deep_link,
            "ts": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "sig": signer_identity[:32] if signer_identity else "",
        }
        return json.dumps(payload, separators=(",", ":"))

    def add_to_pdf(
        self,
        pdf_path: str,
        case_id: str,
        report_id: str,
        manifest_hash: str,
        signer_identity: str = "",
        output_path: Optional[str] = None,
        position: str = "footer_right",  # "header_right", "footer_right", "footer_left"
    ) -> Optional[str]:
        """
        Add a cryptographic QR code to a PDF file.
        
        Args:
            pdf_path: Path to the input PDF
            case_id: Case identifier
            report_id: Report identifier
            manifest_hash: SHA-256 hash of the report manifest
            signer_identity: Name/ID of the signer
            output_path: Output path (defaults to overwriting input)
            position: Where to place the QR code
        
        Returns:
            Path to the watermarked PDF, or None on failure
        """
        try:
            import qrcode
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas as rl_canvas
            from PyPDF2 import PdfReader, PdfWriter
            import io
            import tempfile

            qr_data = self.generate_qr_data(
                case_id=case_id,
                report_id=report_id,
                manifest_hash=manifest_hash,
                signer_identity=signer_identity,
            )

            # Generate QR image
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=3,
                border=1,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Save QR to temp file
            qr_temp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            qr_img.save(qr_temp.name)
            qr_temp.close()

            # Calculate position
            page_width, page_height = A4
            qr_size_pts = self.qr_size_mm * mm

            if position == "footer_right":
                x = page_width - qr_size_pts - 15 * mm
                y = 10 * mm
            elif position == "footer_left":
                x = 15 * mm
                y = 10 * mm
            elif position == "header_right":
                x = page_width - qr_size_pts - 15 * mm
                y = page_height - qr_size_pts - 10 * mm
            else:
                x = page_width - qr_size_pts - 15 * mm
                y = 10 * mm

            # Create overlay PDF with QR code
            overlay_buffer = io.BytesIO()
            c = rl_canvas.Canvas(overlay_buffer, pagesize=A4)
            c.drawImage(qr_temp.name, x, y, qr_size_pts, qr_size_pts)
            c.setFont("Helvetica", 5)
            c.drawString(x, y - 6, f"Verify: {case_id[:16]}")
            c.save()
            overlay_buffer.seek(0)

            # Merge overlay onto first page of PDF
            reader = PdfReader(pdf_path)
            overlay_reader = PdfReader(overlay_buffer)
            writer = PdfWriter()

            for i, page in enumerate(reader.pages):
                if i == 0:
                    page.merge_page(overlay_reader.pages[0])
                writer.add_page(page)

            out = output_path or pdf_path
            with open(out, "wb") as f:
                writer.write(f)

            # Clean up temp
            import os
            os.unlink(qr_temp.name)

            logger.info(f"[QRWatermark] Added verification QR to {out}")
            return out

        except ImportError as e:
            logger.warning(
                f"[QRWatermark] Optional dependencies not available ({e}). "
                f"Install: pip install qrcode[pil] PyPDF2 reportlab"
            )
            return None
        except Exception as e:
            logger.error(f"[QRWatermark] Failed to add QR watermark: {e}")
            return None
