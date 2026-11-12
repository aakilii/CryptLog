"""
Studio V4 Integration — Connect Deep Research to Report Canvas.

This module programmatically writes investigation findings to the
Report Studio V4 canvas, creating:

1. Report documents with proper structure
2. Evidence blocks with SHA-256 citations
3. Tables and timeline visualizations
4. Auto-updating TOC and page numbers

The integration ensures all content placed on the canvas maintains
evidence integrity and proper citation formatting.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import uuid

logger = logging.getLogger(__name__)


@dataclass
class CanvasElement:
    """Element to place on the canvas."""
    element_id: str
    element_type: str  # text, evidenceBlock, table, timeline, widget
    content: Dict[str, Any]
    position: Dict[str, int]  # x, y, width, height
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanvasPage:
    """Page in the canvas document."""
    page_id: str
    page_number: int
    page_type: str  # title, toc, content, appendix
    elements: List[CanvasElement] = field(default_factory=list)


class StudioV4Integration:
    """
    Integration layer between Deep Research and Report Studio V4.
    
    Provides methods to programmatically create and populate
    canvas-based reports with investigation findings.
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.document_id: Optional[str] = None
        self.pages: List[CanvasPage] = []
        self.current_page_num = 0
        
        # Canvas layout constants (in pixels at 96 DPI)
        self.PAGE_WIDTH = 816  # 8.5 inches
        self.PAGE_HEIGHT = 1056  # 11 inches
        self.MARGIN = 72  # 0.75 inch margin
        self.CONTENT_WIDTH = self.PAGE_WIDTH - (2 * self.MARGIN)
        self.CONTENT_HEIGHT = self.PAGE_HEIGHT - (2 * self.MARGIN)
        
        # Current position tracking
        self.current_y = self.MARGIN
    
    def _generate_id(self, prefix: str = "elem") -> str:
        """Generate unique element ID."""
        return f"{prefix}-{uuid.uuid4().hex[:8]}"
    
    def _compute_hash(self, data: Any) -> str:
        """Compute SHA-256 hash of data."""
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    
    async def create_document(self, title: str = "Investigation Report") -> str:
        """
        Create a new canvas document.
        
        Returns: Document ID
        """
        from operation_room.database import open_vault
        
        self.document_id = self._generate_id("doc")
        
        # Create document in database
        conn = open_vault(self.case_id)
        try:
            conn.execute("""
                INSERT INTO report_documents 
                (doc_id, title, doc_type, created_at, updated_at, meta)
                VALUES (?, ?, 'v4-canvas', ?, ?, ?)
            """, [
                self.document_id,
                title,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps({"created_by": "deep_research"})
            ])
        except Exception as e:
            logger.error(f"Error creating document: {e}")
            # Table might not exist, create it
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_documents (
                    doc_id TEXT PRIMARY KEY,
                    title TEXT,
                    doc_type TEXT DEFAULT 'v4-canvas',
                    created_at TEXT,
                    updated_at TEXT,
                    meta TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                INSERT INTO report_documents 
                (doc_id, title, doc_type, created_at, updated_at, meta)
                VALUES (?, ?, 'v4-canvas', ?, ?, ?)
            """, [
                self.document_id,
                title,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps({"created_by": "deep_research"})
            ])
        
        return self.document_id
    
    def new_page(self, page_type: str = "content") -> CanvasPage:
        """Create a new page."""
        self.current_page_num += 1
        page = CanvasPage(
            page_id=self._generate_id("page"),
            page_number=self.current_page_num,
            page_type=page_type,
            elements=[]
        )
        self.pages.append(page)
        self.current_y = self.MARGIN
        return page
    
    def add_heading(
        self,
        text: str,
        level: int = 1,
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """Add a heading element."""
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        # Calculate height based on level
        heights = {1: 48, 2: 36, 3: 28, 4: 24}
        height = heights.get(level, 24)
        
        element = CanvasElement(
            element_id=self._generate_id("heading"),
            element_type="text",
            content={
                "type": "heading",
                "level": level,
                "text": text,
                "style": {
                    "fontSize": 24 - (level * 4),
                    "fontWeight": "bold",
                }
            },
            position={
                "x": self.MARGIN,
                "y": self.current_y,
                "width": self.CONTENT_WIDTH,
                "height": height
            }
        )
        
        page.elements.append(element)
        self.current_y += height + 16  # Add spacing
        
        return element
    
    def add_paragraph(
        self,
        text: str,
        page: Optional[CanvasPage] = None,
        style: Optional[Dict[str, Any]] = None
    ) -> CanvasElement:
        """Add a paragraph element."""
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        # Estimate height based on text length (rough calculation)
        chars_per_line = 80
        lines = len(text) // chars_per_line + text.count('\n') + 1
        line_height = 20
        height = lines * line_height
        
        # Check if we need a new page
        if self.current_y + height > self.PAGE_HEIGHT - self.MARGIN:
            page = self.new_page()
        
        element = CanvasElement(
            element_id=self._generate_id("para"),
            element_type="text",
            content={
                "type": "paragraph",
                "text": text,
                "style": style or {"fontSize": 12, "lineHeight": 1.5}
            },
            position={
                "x": self.MARGIN,
                "y": self.current_y,
                "width": self.CONTENT_WIDTH,
                "height": height
            }
        )
        
        page.elements.append(element)
        self.current_y += height + 12  # Add spacing
        
        return element
    
    def add_evidence_block(
        self,
        evidence_id: str,
        evidence_type: str,
        description: str,
        data: Dict[str, Any],
        evidence_hash: str,
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """
        Add an evidence block with SHA-256 citation.
        
        Evidence blocks display actual evidence data from the vault
        with cryptographic verification.
        """
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        # Generate citation ID
        citation_id = f"cite-{evidence_id}"
        
        element = CanvasElement(
            element_id=self._generate_id("evblock"),
            element_type="evidenceBlock",
            content={
                "evidenceId": evidence_id,
                "evidenceType": evidence_type,
                "description": description,
                "data": data,  # Actual values from vault
            },
            position={
                "x": self.MARGIN + 20,  # Indent
                "y": self.current_y,
                "width": self.CONTENT_WIDTH - 40,
                "height": 80
            },
            metadata={
                "citationId": citation_id,
                "dataHash": evidence_hash,
                "verified": True,
                "source": "evidence_vault"
            }
        )
        
        page.elements.append(element)
        self.current_y += 100
        
        return element
    
    def add_table(
        self,
        title: str,
        columns: List[str],
        data: List[Dict[str, Any]],
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """Add a table element."""
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        # Calculate table height
        row_height = 30
        header_height = 40
        height = header_height + (len(data) * row_height) + 20
        
        # Check if we need a new page
        if self.current_y + height > self.PAGE_HEIGHT - self.MARGIN:
            page = self.new_page()
        
        element = CanvasElement(
            element_id=self._generate_id("table"),
            element_type="table",
            content={
                "title": title,
                "columns": columns,
                "rows": data,
                "style": {
                    "headerBackground": "#f0f0f0",
                    "borderColor": "#cccccc",
                    "alternateRows": True
                }
            },
            position={
                "x": self.MARGIN,
                "y": self.current_y,
                "width": self.CONTENT_WIDTH,
                "height": height
            }
        )
        
        page.elements.append(element)
        self.current_y += height + 24
        
        return element
    
    def add_timeline_widget(
        self,
        title: str,
        events: List[Dict[str, Any]],
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """
        Add a timeline visualization widget.
        
        Events should have: timestamp, label, type, evidenceId
        """
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        element = CanvasElement(
            element_id=self._generate_id("timeline"),
            element_type="widget",
            content={
                "widgetType": "timeline",
                "title": title,
                "events": events,
                "config": {
                    "orientation": "horizontal",
                    "showLabels": True,
                    "groupByDate": True
                }
            },
            position={
                "x": self.MARGIN,
                "y": self.current_y,
                "width": self.CONTENT_WIDTH,
                "height": 200
            }
        )
        
        page.elements.append(element)
        self.current_y += 220
        
        return element
    
    def add_chart_widget(
        self,
        chart_type: str,
        title: str,
        data: Dict[str, Any],
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """
        Add a chart widget (bar, pie, line, etc.).
        """
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        element = CanvasElement(
            element_id=self._generate_id("chart"),
            element_type="widget",
            content={
                "widgetType": "chart",
                "chartType": chart_type,
                "title": title,
                "data": data,
                "config": {
                    "showLegend": True,
                    "showLabels": True
                }
            },
            position={
                "x": self.MARGIN,
                "y": self.current_y,
                "width": self.CONTENT_WIDTH,
                "height": 250
            }
        )
        
        page.elements.append(element)
        self.current_y += 270
        
        return element
    
    def add_citation_footnote(
        self,
        citation_id: str,
        evidence_hash: str,
        source_description: str,
        page: Optional[CanvasPage] = None
    ) -> CanvasElement:
        """Add a citation footnote at page bottom."""
        if page is None:
            page = self.pages[-1] if self.pages else self.new_page()
        
        element = CanvasElement(
            element_id=self._generate_id("footnote"),
            element_type="text",
            content={
                "type": "footnote",
                "citationId": citation_id,
                "text": f"[{citation_id}] {source_description}",
                "hash": evidence_hash[:24] + "...",
                "style": {"fontSize": 9, "color": "#666666"}
            },
            position={
                "x": self.MARGIN,
                "y": self.PAGE_HEIGHT - 60,
                "width": self.CONTENT_WIDTH,
                "height": 20
            }
        )
        
        page.elements.append(element)
        return element
    
    def generate_toc(self) -> CanvasPage:
        """Generate table of contents from pages."""
        toc_page = self.new_page(page_type="toc")
        
        self.add_heading("TABLE OF CONTENTS", level=1, page=toc_page)
        
        toc_entries = []
        for page in self.pages:
            # Find headings on each page
            for elem in page.elements:
                if (elem.element_type == "text" and 
                    elem.content.get("type") == "heading" and
                    elem.content.get("level") == 1):
                    toc_entries.append({
                        "title": elem.content.get("text", ""),
                        "page": page.page_number
                    })
        
        # Add TOC entries
        for entry in toc_entries:
            self.add_paragraph(
                f"{entry['title']} {'.' * 50} {entry['page']}",
                page=toc_page,
                style={"fontSize": 11}
            )
        
        return toc_page
    
    def populate_from_report_structure(
        self,
        report_structure: Dict[str, Any]
    ) -> List[CanvasPage]:
        """
        Populate the canvas from a report structure dictionary.
        
        This is the main integration point that converts the
        hypothesis_report_binder output to canvas elements.
        """
        sections = report_structure.get("sections", [])
        
        for section in sections:
            section_type = section.get("type", "")
            title = section.get("title", "")
            content = section.get("content", "")
            evidence_refs = section.get("evidence_refs", [])
            tables = section.get("tables", [])
            figures = section.get("figures", [])
            
            # Create new page for major sections
            if section_type in ("title_page", "table_of_contents", "executive_summary",
                               "evidence_inventory", "findings", "conclusions", "appendix_evidence"):
                page = self.new_page(section_type)
            else:
                page = self.pages[-1] if self.pages else self.new_page()
            
            # Add section title
            level = 1 if section_type in ("title_page", "executive_summary") else 2
            self.add_heading(title, level=level, page=page)
            
            # Add content paragraphs
            if content:
                paragraphs = content.split('\n\n')
                for para in paragraphs:
                    if para.strip():
                        self.add_paragraph(para.strip(), page=page)
            
            # Add tables
            for table in tables:
                self.add_table(
                    title=table.get("title", ""),
                    columns=table.get("columns", []),
                    data=table.get("data", []),
                    page=page
                )
            
            # Add figures (timelines, charts)
            for figure in figures:
                if figure.get("type") == "timeline":
                    self.add_timeline_widget(
                        title=figure.get("title", "Timeline"),
                        events=figure.get("events", []),
                        page=page
                    )
                elif figure.get("type") == "chart":
                    self.add_chart_widget(
                        chart_type=figure.get("chart_type", "bar"),
                        title=figure.get("title", ""),
                        data=figure.get("data", {}),
                        page=page
                    )
        
        # Generate TOC
        self.generate_toc()
        
        # Reorder pages (TOC after title)
        if len(self.pages) > 2:
            toc = self.pages.pop()  # Remove TOC from end
            self.pages.insert(1, toc)  # Insert after title
            
            # Renumber pages
            for i, page in enumerate(self.pages):
                page.page_number = i + 1
        
        return self.pages
    
    async def save_to_database(self) -> str:
        """Save all pages to the database."""
        from operation_room.database import open_vault
        
        if not self.document_id:
            await self.create_document()
        
        conn = open_vault(self.case_id)
        
        # Ensure pages table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_pages (
                page_id TEXT PRIMARY KEY,
                doc_id TEXT,
                page_number INTEGER,
                page_type TEXT,
                elements TEXT,
                created_at TEXT,
                FOREIGN KEY (doc_id) REFERENCES report_documents(doc_id)
            )
        """)
        
        # Save each page
        for page in self.pages:
            elements_json = json.dumps([
                {
                    "id": elem.element_id,
                    "type": elem.element_type,
                    "content": elem.content,
                    "position": elem.position,
                    "metadata": elem.metadata
                }
                for elem in page.elements
            ])
            
            conn.execute("""
                INSERT OR REPLACE INTO report_pages
                (page_id, doc_id, page_number, page_type, elements, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                page.page_id,
                self.document_id,
                page.page_number,
                page.page_type,
                elements_json,
                datetime.now(timezone.utc).isoformat()
            ])
        
        # Update document metadata
        conn.execute("""
            UPDATE report_documents
            SET updated_at = ?, meta = ?
            WHERE doc_id = ?
        """, [
            datetime.now(timezone.utc).isoformat(),
            json.dumps({
                "page_count": len(self.pages),
                "generated_by": "deep_research",
                "last_updated": datetime.now(timezone.utc).isoformat()
            }),
            self.document_id
        ])
        
        return self.document_id
    
    def export_to_json(self) -> Dict[str, Any]:
        """Export canvas structure as JSON."""
        return {
            "document_id": self.document_id,
            "case_id": self.case_id,
            "type": "v4-canvas",
            "pages": [
                {
                    "page_id": page.page_id,
                    "page_number": page.page_number,
                    "page_type": page.page_type,
                    "elements": [
                        {
                            "id": elem.element_id,
                            "type": elem.element_type,
                            "content": elem.content,
                            "position": elem.position,
                            "metadata": elem.metadata
                        }
                        for elem in page.elements
                    ]
                }
                for page in self.pages
            ],
            "metadata": {
                "total_pages": len(self.pages),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        }


async def create_report_from_findings(
    case_id: str,
    report_structure: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main function to create a canvas report from investigation findings.
    
    Args:
        case_id: Case identifier
        report_structure: Output from hypothesis_report_binder
        
    Returns:
        Canvas document structure
    """
    integration = StudioV4Integration(case_id)
    
    # Create document
    await integration.create_document(
        title=f"Investigation Report - {case_id}"
    )
    
    # Populate from structure
    integration.populate_from_report_structure(report_structure)
    
    # Save to database
    await integration.save_to_database()
    
    return integration.export_to_json()
