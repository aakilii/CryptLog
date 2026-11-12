"""
Document Parser Module for NFLIP Deep Research Investigation Assistant.

Implements:
- PDF layout parsing
- DOCX layout parsing
- Alignment verification
- Template extraction
"""

from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .alignment import AlignmentVerifier

__all__ = [
    "PDFParser",
    "DOCXParser",
    "AlignmentVerifier",
]
