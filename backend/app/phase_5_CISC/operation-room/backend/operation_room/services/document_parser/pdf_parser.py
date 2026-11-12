"""
PDF Document Parser for Layout Extraction.

Extracts layout information from PDF documents:
- Text blocks with positions
- Headers and sections
- Tables (basic detection)
- Images/figures
- Page dimensions

Used for:
- Reference document import
- Template extraction
- Layout verification
"""

import io
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import re


class ElementType(str, Enum):
    """Types of document elements."""
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    LIST = "list"
    FOOTER = "footer"
    HEADER = "header"
    PAGE_NUMBER = "page_number"
    UNKNOWN = "unknown"


@dataclass
class BoundingBox:
    """Bounding box for an element."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    
    @property
    def x2(self) -> float:
        """Right edge x coordinate."""
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        """Bottom edge y coordinate."""
        return self.y + self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        """Center point."""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    def intersects(self, other: "BoundingBox") -> bool:
        """Check if boxes intersect."""
        return not (
            self.x2 < other.x or
            other.x2 < self.x or
            self.y2 < other.y or
            other.y2 < self.y
        )
    
    def contains(self, other: "BoundingBox") -> bool:
        """Check if this box contains other."""
        return (
            self.x <= other.x and
            self.y <= other.y and
            self.x2 >= other.x2 and
            self.y2 >= other.y2
        )
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "BoundingBox":
        """Create from dictionary."""
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )


@dataclass
class TextStyle:
    """Text styling information."""
    font_name: str = ""
    font_size: float = 12.0
    is_bold: bool = False
    is_italic: bool = False
    color: str = "#000000"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "font_name": self.font_name,
            "font_size": self.font_size,
            "is_bold": self.is_bold,
            "is_italic": self.is_italic,
            "color": self.color,
        }


@dataclass
class DocumentElement:
    """A single element in the document."""
    element_type: ElementType = ElementType.TEXT
    content: str = ""
    bbox: BoundingBox = field(default_factory=BoundingBox)
    style: TextStyle = field(default_factory=TextStyle)
    page_number: int = 1
    heading_level: int = 0  # 1-6 for headings, 0 for non-headings
    children: List["DocumentElement"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "element_type": self.element_type.value,
            "content": self.content,
            "bbox": self.bbox.to_dict(),
            "style": self.style.to_dict(),
            "page_number": self.page_number,
            "heading_level": self.heading_level,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }


@dataclass
class PageLayout:
    """Layout information for a single page."""
    page_number: int = 1
    width: float = 612.0  # Letter size default
    height: float = 792.0
    elements: List[DocumentElement] = field(default_factory=list)
    
    # Margins (detected or specified)
    margin_top: float = 72.0
    margin_bottom: float = 72.0
    margin_left: float = 72.0
    margin_right: float = 72.0
    
    def get_content_area(self) -> BoundingBox:
        """Get the content area (excluding margins)."""
        return BoundingBox(
            x=self.margin_left,
            y=self.margin_top,
            width=self.width - self.margin_left - self.margin_right,
            height=self.height - self.margin_top - self.margin_bottom,
        )
    
    def get_elements_by_type(self, element_type: ElementType) -> List[DocumentElement]:
        """Get elements of a specific type."""
        return [e for e in self.elements if e.element_type == element_type]
    
    def get_headings(self) -> List[DocumentElement]:
        """Get all headings."""
        return [e for e in self.elements if e.element_type == ElementType.HEADING]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "elements": [e.to_dict() for e in self.elements],
            "margin_top": self.margin_top,
            "margin_bottom": self.margin_bottom,
            "margin_left": self.margin_left,
            "margin_right": self.margin_right,
        }


@dataclass
class DocumentLayout:
    """Complete document layout."""
    pages: List[PageLayout] = field(default_factory=list)
    title: str = ""
    author: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def page_count(self) -> int:
        """Number of pages."""
        return len(self.pages)
    
    def get_all_headings(self) -> List[DocumentElement]:
        """Get all headings across all pages."""
        headings = []
        for page in self.pages:
            headings.extend(page.get_headings())
        return headings
    
    def get_table_of_contents(self) -> List[Dict[str, Any]]:
        """Extract table of contents from headings."""
        toc = []
        for page in self.pages:
            for element in page.get_headings():
                toc.append({
                    "title": element.content,
                    "level": element.heading_level,
                    "page": page.page_number,
                })
        return toc
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pages": [p.to_dict() for p in self.pages],
            "title": self.title,
            "author": self.author,
            "metadata": self.metadata,
            "page_count": self.page_count,
            "toc": self.get_table_of_contents(),
        }


class PDFParser:
    """
    PDF document parser.
    
    Extracts layout information from PDF files using pdfminer.
    """
    
    def __init__(self):
        """Initialize the parser."""
        self._pdfminer_available = False
        try:
            from pdfminer.high_level import extract_pages
            from pdfminer.layout import LAParams
            self._pdfminer_available = True
        except ImportError:
            pass
    
    @property
    def is_available(self) -> bool:
        """Check if pdfminer is available."""
        return self._pdfminer_available
    
    def parse(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
    ) -> DocumentLayout:
        """
        Parse a PDF document.
        
        Args:
            source: File path, bytes, or BytesIO
            
        Returns:
            DocumentLayout with extracted elements
        """
        if not self._pdfminer_available:
            raise ImportError(
                "pdfminer.six is required for PDF parsing. "
                "Install with: pip install pdfminer.six"
            )
        
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import (
            LAParams,
            LTTextBox,
            LTTextLine,
            LTChar,
            LTFigure,
            LTImage,
            LTPage,
        )
        
        # Handle different input types
        if isinstance(source, (str, Path)):
            source = open(source, "rb")
        elif isinstance(source, bytes):
            source = io.BytesIO(source)
        
        layout = DocumentLayout()
        laparams = LAParams(
            detect_vertical=True,
            all_texts=True,
        )
        
        try:
            for page_num, page_layout in enumerate(extract_pages(source, laparams=laparams), 1):
                page = self._process_page(page_layout, page_num)
                layout.pages.append(page)
        finally:
            if hasattr(source, "close"):
                source.close()
        
        return layout
    
    def _process_page(self, page_layout: Any, page_num: int) -> PageLayout:
        """Process a single page."""
        from pdfminer.layout import (
            LTTextBox,
            LTTextLine,
            LTChar,
            LTFigure,
            LTImage,
            LTAnno,
        )
        
        page = PageLayout(
            page_number=page_num,
            width=page_layout.width,
            height=page_layout.height,
        )
        
        # Detect margins from elements
        min_x, min_y = page.width, page.height
        max_x, max_y = 0, 0
        
        for element in page_layout:
            doc_element = self._process_element(element, page_num)
            if doc_element:
                page.elements.append(doc_element)
                
                # Update margin detection
                if doc_element.bbox.x < min_x:
                    min_x = doc_element.bbox.x
                if doc_element.bbox.y < min_y:
                    min_y = doc_element.bbox.y
                if doc_element.bbox.x2 > max_x:
                    max_x = doc_element.bbox.x2
                if doc_element.bbox.y2 > max_y:
                    max_y = doc_element.bbox.y2
        
        # Set detected margins
        if page.elements:
            page.margin_left = max(0, min_x)
            page.margin_right = max(0, page.width - max_x)
            page.margin_top = max(0, page.height - max_y)
            page.margin_bottom = max(0, min_y)
        
        # Classify elements (headers, footers, etc.)
        self._classify_elements(page)
        
        return page
    
    def _process_element(self, element: Any, page_num: int) -> Optional[DocumentElement]:
        """Process a single layout element."""
        from pdfminer.layout import (
            LTTextBox,
            LTTextLine,
            LTChar,
            LTFigure,
            LTImage,
        )
        
        if isinstance(element, LTTextBox):
            # Extract text and style
            text = element.get_text().strip()
            if not text:
                return None
            
            # Get dominant style from characters
            style = self._extract_style(element)
            
            # Determine element type
            element_type, heading_level = self._classify_text(text, style)
            
            return DocumentElement(
                element_type=element_type,
                content=text,
                bbox=BoundingBox(
                    x=element.x0,
                    y=element.y0,
                    width=element.width,
                    height=element.height,
                ),
                style=style,
                page_number=page_num,
                heading_level=heading_level,
            )
        
        elif isinstance(element, (LTFigure, LTImage)):
            return DocumentElement(
                element_type=ElementType.IMAGE,
                content="[Image]",
                bbox=BoundingBox(
                    x=element.x0,
                    y=element.y0,
                    width=element.width,
                    height=element.height,
                ),
                page_number=page_num,
            )
        
        return None
    
    def _extract_style(self, text_element: Any) -> TextStyle:
        """Extract dominant text style from element."""
        from pdfminer.layout import LTChar
        
        # Collect all character styles
        font_sizes = []
        font_names = []
        
        def collect_chars(element):
            if isinstance(element, LTChar):
                font_sizes.append(element.size)
                font_names.append(element.fontname)
            elif hasattr(element, "__iter__"):
                for child in element:
                    collect_chars(child)
        
        collect_chars(text_element)
        
        style = TextStyle()
        
        if font_sizes:
            # Use most common font size
            style.font_size = max(set(font_sizes), key=font_sizes.count)
        
        if font_names:
            font_name = max(set(font_names), key=font_names.count)
            style.font_name = font_name
            style.is_bold = "bold" in font_name.lower() or "heavy" in font_name.lower()
            style.is_italic = "italic" in font_name.lower() or "oblique" in font_name.lower()
        
        return style
    
    def _classify_text(self, text: str, style: TextStyle) -> Tuple[ElementType, int]:
        """Classify text element type and heading level."""
        # Check for list patterns
        if re.match(r"^[\u2022\u2023\u25E6\u2043\u2219•●○◦‣⁃]\s", text):
            return ElementType.LIST, 0
        if re.match(r"^\d+\.\s", text):
            return ElementType.LIST, 0
        if re.match(r"^[a-z]\)\s", text, re.IGNORECASE):
            return ElementType.LIST, 0
        
        # Check for headings based on style
        if style.font_size >= 18 and style.is_bold:
            return ElementType.HEADING, 1
        if style.font_size >= 16 and style.is_bold:
            return ElementType.HEADING, 2
        if style.font_size >= 14 and style.is_bold:
            return ElementType.HEADING, 3
        if style.is_bold and len(text) < 100:
            return ElementType.HEADING, 4
        
        return ElementType.TEXT, 0
    
    def _classify_elements(self, page: PageLayout) -> None:
        """Classify elements based on position (headers, footers, page numbers)."""
        content_area = page.get_content_area()
        header_threshold = page.height - page.margin_top - 50
        footer_threshold = page.margin_bottom + 50
        
        for element in page.elements:
            # Check for header
            if element.bbox.y2 > header_threshold:
                if element.element_type == ElementType.TEXT:
                    element.element_type = ElementType.HEADER
            
            # Check for footer
            elif element.bbox.y < footer_threshold:
                if element.element_type == ElementType.TEXT:
                    # Check for page number
                    if re.match(r"^\d+$", element.content.strip()):
                        element.element_type = ElementType.PAGE_NUMBER
                    else:
                        element.element_type = ElementType.FOOTER
    
    def extract_text(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
    ) -> str:
        """
        Extract plain text from PDF.
        
        Args:
            source: File path, bytes, or BytesIO
            
        Returns:
            Extracted text
        """
        if not self._pdfminer_available:
            raise ImportError("pdfminer.six is required")
        
        from pdfminer.high_level import extract_text
        
        if isinstance(source, bytes):
            source = io.BytesIO(source)
        
        return extract_text(source)
    
    def get_metadata(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
    ) -> Dict[str, Any]:
        """
        Extract PDF metadata.
        
        Args:
            source: File path, bytes, or BytesIO
            
        Returns:
            Metadata dictionary
        """
        if not self._pdfminer_available:
            raise ImportError("pdfminer.six is required")
        
        from pdfminer.pdfparser import PDFParser as PMParser
        from pdfminer.pdfdocument import PDFDocument
        
        if isinstance(source, (str, Path)):
            source = open(source, "rb")
        elif isinstance(source, bytes):
            source = io.BytesIO(source)
        
        try:
            parser = PMParser(source)
            doc = PDFDocument(parser)
            
            metadata = {}
            if doc.info:
                for info in doc.info:
                    for key, value in info.items():
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8")
                            except UnicodeDecodeError:
                                value = value.decode("latin-1")
                        metadata[key] = value
            
            return metadata
        finally:
            if hasattr(source, "close"):
                source.close()
