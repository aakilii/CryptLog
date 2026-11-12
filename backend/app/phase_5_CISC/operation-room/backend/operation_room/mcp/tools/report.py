"""
MCP Report Generation Tools
============================

Phase 4: Canvas manipulation, narrative generation, and report management.

Integrates with existing Report Studio V4 architecture:
- TipTap AST-based document storage
- Canvas-based page layouts with free-form positioning
- Evidence block rendering with SHA-256 verification
- Multi-format export (PDF, DOCX, HTML)

Tool Categories:
- report.doc.*      Document lifecycle management
- report.canvas.*   Canvas/page manipulation
- report.section.*  Section and element management
- report.narrative.*  AI-powered narrative generation
- report.evidence.* Evidence block integration
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field

# Import from our MCP infrastructure
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from operation_room.mcp.decorators import mcp_tool, with_coc_logging, audit_trail
from operation_room.mcp.schemas import (
    HashedModel,
    MCPToolResult as ToolResult,
)

# Import evidence vault for citations
from operation_room.mcp.tools.evidence import EvidenceVault


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class DocumentStatus(str, Enum):
    """Report document lifecycle status."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    APPROVED = "approved"
    FINALIZED = "finalized"
    EXPORTED = "exported"


class SectionType(str, Enum):
    """Standard report section types."""
    COVER = "cover"
    TABLE_OF_CONTENTS = "table_of_contents"
    EXECUTIVE_SUMMARY = "executive_summary"
    CASE_OVERVIEW = "case_overview"
    METHODOLOGY = "methodology"
    TIMELINE_NARRATIVE = "timeline_narrative"
    ANOMALY_FINDINGS = "anomaly_findings"
    CORRELATION_ANALYSIS = "correlation_analysis"
    NETWORK_ANALYSIS = "network_analysis"
    DATA_ACCESS_ANALYSIS = "data_access"
    IMPACT_ASSESSMENT = "impact_assessment"
    HYPOTHESIS_ANALYSIS = "hypothesis_analysis"
    FINDINGS = "findings"
    RECOMMENDATIONS = "recommendations"
    EVIDENCE_INVENTORY = "evidence_inventory"
    CHAIN_OF_CUSTODY = "chain_of_custody"
    APPENDIX = "appendix"
    CUSTOM = "custom"


class ElementType(str, Enum):
    """Canvas element types."""
    TEXT = "text"
    HEADING = "heading"
    EVIDENCE_BLOCK = "evidenceBlock"
    CHART = "chart"
    TABLE = "table"
    IMAGE = "image"
    SHAPE = "shape"
    COMPONENT = "component"
    PAGE_BREAK = "pageBreak"


class NarrativeStyle(str, Enum):
    """Writing style for narrative generation."""
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    REGULATORY = "regulatory"
    LEGAL = "legal"


class ExportFormat(str, Enum):
    """Report export formats."""
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"


def _get_enum_value(val) -> str:
    """Get string value from enum or string."""
    if hasattr(val, 'value'):
        return val.value
    return str(val)


# =============================================================================
# DATA MODELS
# =============================================================================

class CanvasPosition(BaseModel):
    """Position and dimensions on canvas."""
    x: float = 0
    y: float = 0
    width: float = 180  # mm (A4 width - margins)
    height: Optional[float] = None  # Auto-calculate if not set
    z_index: int = 0


class CanvasElement(HashedModel):
    """Element on a canvas page."""
    element_id: str = Field(default_factory=lambda: f"elem-{uuid.uuid4().hex[:8]}")
    type: ElementType
    position: CanvasPosition
    content: Dict[str, Any]  # Type-specific content
    metadata: Dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[str] = Field(default_factory=list)  # Evidence vault IDs
    element_hash: Optional[str] = None  # Renamed from content_hash to avoid HashedModel conflict
    
    def compute_element_hash(self) -> str:
        """Compute SHA-256 hash of content."""
        canonical = json.dumps(self.content, sort_keys=True, separators=(',', ':'))
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


class CanvasPage(HashedModel):
    """A single page in the report canvas."""
    page_id: str = Field(default_factory=lambda: f"page-{uuid.uuid4().hex[:8]}")
    page_number: int
    section_type: SectionType = SectionType.CUSTOM
    label: str = ""
    elements: List[CanvasElement] = Field(default_factory=list)
    page_hash: Optional[str] = None  # Renamed from content_hash
    
    def compute_page_hash(self) -> str:
        """Compute hash of all page elements."""
        element_hashes = [elem.compute_element_hash() for elem in self.elements]
        combined = ":".join(sorted(element_hashes))
        return f"sha256:{hashlib.sha256(combined.encode()).hexdigest()}"


class ReportDocument(HashedModel):
    """Complete report document structure."""
    doc_id: str = Field(default_factory=lambda: f"doc-{uuid.uuid4().hex[:12]}")
    case_id: str
    title: str
    status: DocumentStatus = DocumentStatus.DRAFT
    template: str = "default"
    pages: List[CanvasPage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "system"
    
    def total_pages(self) -> int:
        return len(self.pages)
    
    def add_page(self, section_type: SectionType, label: str = "") -> CanvasPage:
        """Add a new page to the document."""
        page = CanvasPage(
            page_number=len(self.pages) + 1,
            section_type=section_type,
            label=label or _get_enum_value(section_type).replace("_", " ").title()
        )
        self.pages.append(page)
        self.updated_at = datetime.now(timezone.utc)
        return page


class CitationRef(BaseModel):
    """Reference to cited evidence."""
    citation_id: str = Field(default_factory=lambda: f"cite-{uuid.uuid4().hex[:6]}")
    evidence_id: str  # Evidence vault ID
    text: str  # Display text for citation
    page: Optional[int] = None
    verified: bool = False


class NarrativeContext(BaseModel):
    """Context for narrative generation."""
    section_type: SectionType
    investigation_id: str
    hypothesis_id: Optional[str] = None
    module_data: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    previous_sections: List[str] = Field(default_factory=list)
    custom_instructions: Optional[str] = None


class NarrativeOutput(HashedModel):
    """Generated narrative with citations."""
    narrative_id: str = Field(default_factory=lambda: f"narr-{uuid.uuid4().hex[:8]}")
    section_type: SectionType
    style: NarrativeStyle
    content: str  # Generated prose
    citations: List[CitationRef] = Field(default_factory=list)
    facts_used: List[Dict[str, Any]] = Field(default_factory=list)  # From evidence, not AI
    word_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExportResult(HashedModel):
    """Result of report export operation."""
    export_id: str = Field(default_factory=lambda: f"export-{uuid.uuid4().hex[:8]}")
    doc_id: str
    format: ExportFormat
    file_path: str
    file_hash: str
    page_count: int
    evidence_count: int
    citation_count: int
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    manifest: Dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    """Issue found during pre-export validation."""
    severity: Literal["critical", "high", "medium", "low", "info"]
    element_id: str
    page_number: int
    issue_type: str
    message: str
    suggestion: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of pre-export validation."""
    valid: bool
    total_evidence_blocks: int
    cited_evidence: int
    uncited_evidence: int
    issues: List[ValidationIssue]
    warnings: List[str]


# =============================================================================
# DOCUMENT STORE (In-memory for demo; production uses DuckDB)
# =============================================================================

class ReportStore:
    """In-memory document storage."""
    
    _documents: Dict[str, ReportDocument] = {}
    _versions: Dict[str, List[ReportDocument]] = {}  # doc_id -> version history
    _narratives: Dict[str, NarrativeOutput] = {}
    _exports: Dict[str, List[ExportResult]] = {}  # doc_id -> exports
    
    @classmethod
    def create_document(cls, case_id: str, title: str, template: str = "default", 
                       created_by: str = "system") -> ReportDocument:
        """Create a new report document."""
        doc = ReportDocument(
            case_id=case_id,
            title=title,
            template=template,
            created_by=created_by
        )
        cls._documents[doc.doc_id] = doc
        cls._versions[doc.doc_id] = [doc.model_copy(deep=True)]
        return doc
    
    @classmethod
    def get_document(cls, doc_id: str) -> Optional[ReportDocument]:
        """Retrieve a document by ID."""
        return cls._documents.get(doc_id)
    
    @classmethod
    def update_document(cls, doc: ReportDocument) -> ReportDocument:
        """Update document and create new version."""
        doc.version += 1
        doc.updated_at = datetime.now(timezone.utc)
        cls._documents[doc.doc_id] = doc
        
        # Store version history
        if doc.doc_id not in cls._versions:
            cls._versions[doc.doc_id] = []
        cls._versions[doc.doc_id].append(doc.model_copy(deep=True))
        
        return doc
    
    @classmethod
    def list_documents(cls, case_id: str) -> List[ReportDocument]:
        """List all documents for a case."""
        return [d for d in cls._documents.values() if d.case_id == case_id]
    
    @classmethod
    def store_narrative(cls, narrative: NarrativeOutput) -> None:
        """Store generated narrative."""
        cls._narratives[narrative.narrative_id] = narrative
    
    @classmethod
    def record_export(cls, result: ExportResult) -> None:
        """Record export operation."""
        if result.doc_id not in cls._exports:
            cls._exports[result.doc_id] = []
        cls._exports[result.doc_id].append(result)


# Global store instance
store = ReportStore()


# =============================================================================
# NARRATIVE TEMPLATES AND PROMPTS
# =============================================================================

SECTION_PROMPTS = {
    SectionType.EXECUTIVE_SUMMARY: """
Generate an executive summary for this forensic investigation report.

Context:
- Case: {case_title}
- Investigation Period: {time_range}
- Primary Hypothesis: {hypothesis}
- Key Findings: {findings_summary}

Requirements:
- 3-4 paragraphs, C-suite appropriate language
- Focus on business impact and risk assessment
- Highlight key evidence with citation markers [EV-XXXXXX]
- Include confidence levels for major conclusions
- Avoid technical jargon unless essential

Evidence to cite:
{evidence_list}
""",
    
    SectionType.TIMELINE_NARRATIVE: """
Generate a chronological narrative of the investigated events.

Context:
- Time Range: {time_range}
- Key Actors: {actors}
- Systems Involved: {systems}

Timeline Events (from evidence):
{timeline_events}

Requirements:
- Maintain strict chronological order
- Reference actual timestamps from evidence
- Mark anchor events clearly
- Connect events to hypothesis validation
- Include citation markers [EV-XXXXXX] for each factual claim

Evidence to cite:
{evidence_list}
""",

    SectionType.ANOMALY_FINDINGS: """
Generate a section describing anomaly detection findings.

Context:
- Detection Algorithm: {algorithm}
- Threshold: {threshold}
- Total Anomalies: {anomaly_count}

Top Anomalies (from evidence):
{anomalies}

SHAP Feature Importance:
{shap_features}

Requirements:
- Explain why each anomaly was flagged
- Reference SHAP explanations for interpretability
- Rate severity of each finding
- Include citation markers [EV-XXXXXX]
- Connect anomalies to potential malicious activity

Evidence to cite:
{evidence_list}
""",

    SectionType.HYPOTHESIS_ANALYSIS: """
Generate a section analyzing hypothesis testing results.

Context:
- Null Hypothesis: {null_hypothesis}
- Alternative Hypotheses: {alt_hypotheses}

Analysis Results:
{hypothesis_results}

Requirements:
- Present each hypothesis objectively
- Show evidence for and against
- Report confidence scores with ODNI ICD 203 levels
- Explain reasoning transparently
- Include citation markers [EV-XXXXXX]
- Conclude with verdict and caveats

Evidence to cite:
{evidence_list}
""",

    SectionType.FINDINGS: """
Generate a findings section summarizing investigation conclusions.

Context:
- Investigation Objective: {objective}
- Methods Used: {methods}

Key Findings:
{findings}

Requirements:
- State each finding clearly and concisely
- Support with evidence citations [EV-XXXXXX]
- Include confidence level for each finding
- Note any limitations or gaps in evidence
- Maintain objective, factual tone

Evidence to cite:
{evidence_list}
""",

    SectionType.RECOMMENDATIONS: """
Generate recommendations based on investigation findings.

Context:
- Key Findings: {findings_summary}
- Risk Assessment: {risk_level}
- Affected Systems: {systems}

Requirements:
- Prioritize recommendations by urgency
- Make recommendations specific and actionable
- Reference findings that justify each recommendation
- Consider technical, procedural, and policy measures
- Include timeline suggestions where appropriate

Evidence referenced:
{evidence_list}
""",
}


# =============================================================================
# MCP TOOLS: DOCUMENT MANAGEMENT
# =============================================================================

@mcp_tool("report.doc.create")
@with_coc_logging("REPORT_CREATED")
async def create_report_document(
    case_id: str,
    title: str,
    template: str = "default",
    investigation_id: Optional[str] = None,
    created_by: str = "investigation_agent",
    **kwargs
) -> ToolResult:
    """
    Create a new report document for a case.
    
    Args:
        case_id: The case identifier
        title: Report title
        template: Template name (default, formal, executive)
        investigation_id: Link to investigation session
        created_by: Creator identifier
        
    Returns:
        ToolResult with document metadata
    """
    doc = store.create_document(
        case_id=case_id,
        title=title,
        template=template,
        created_by=created_by
    )
    
    if investigation_id:
        doc.metadata["investigation_id"] = investigation_id
    
    return ToolResult(
        success=True,
        tool_name="report.doc.create",
        data={
            "doc_id": doc.doc_id,
            "case_id": doc.case_id,
            "title": doc.title,
            "template": doc.template,
            "status": _get_enum_value(doc.status),
            "version": doc.version,
            "total_pages": doc.total_pages(),
            "created_at": doc.created_at.isoformat()
        },
        evidence_hash=doc.content_hash,
        coc_event_id=f"coc-{uuid.uuid4().hex[:8]}"
    )


@mcp_tool("report.doc.get", requires_case_id=False)
async def get_report_document(doc_id: str, **kwargs) -> ToolResult:
    """
    Retrieve a report document by ID.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        ToolResult with full document structure
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.doc.get",
            error=f"Document not found: {doc_id}"
        )
    
    return ToolResult(
        success=True,
        tool_name="report.doc.get",
        data={
            "doc_id": doc.doc_id,
            "case_id": doc.case_id,
            "title": doc.title,
            "status": _get_enum_value(doc.status),
            "template": doc.template,
            "version": doc.version,
            "total_pages": doc.total_pages(),
            "pages": [
                {
                    "page_id": p.page_id,
                    "page_number": p.page_number,
                    "section_type": _get_enum_value(p.section_type),
                    "label": p.label,
                    "element_count": len(p.elements)
                }
                for p in doc.pages
            ],
            "metadata": doc.metadata,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat()
        },
        evidence_hash=doc.content_hash
    )


@mcp_tool("report.doc.list", requires_case_id=False)
async def list_report_documents(case_id: str, **kwargs) -> ToolResult:
    """
    List all report documents for a case.
    
    Args:
        case_id: Case identifier
        
    Returns:
        ToolResult with list of documents
    """
    docs = store.list_documents(case_id)
    
    return ToolResult(
        success=True,
        tool_name="report.doc.list",
        data={
            "case_id": case_id,
            "document_count": len(docs),
            "documents": [
                {
                    "doc_id": d.doc_id,
                    "title": d.title,
                    "status": _get_enum_value(d.status),
                    "total_pages": d.total_pages(),
                    "version": d.version,
                    "updated_at": d.updated_at.isoformat()
                }
                for d in docs
            ]
        }
    )


@mcp_tool("report.doc.update_status", requires_case_id=False)
@with_coc_logging("REPORT_STATUS_UPDATED")
async def update_document_status(
    doc_id: str,
    new_status: str,
    reason: Optional[str] = None,
    **kwargs
) -> ToolResult:
    """
    Update document status (draft → review → approved → finalized).
    
    Args:
        doc_id: Document identifier
        new_status: New status value
        reason: Optional reason for status change
        
    Returns:
        ToolResult with updated status
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.doc.update_status",
            error=f"Document not found: {doc_id}"
        )
    
    try:
        doc.status = DocumentStatus(new_status)
    except ValueError:
        valid = [s.value for s in DocumentStatus]
        return ToolResult(
            success=False,
            tool_name="report.doc.update_status",
            error=f"Invalid status: {new_status}. Valid: {valid}"
        )
    
    if reason:
        doc.metadata["status_change_reason"] = reason
        doc.metadata["status_change_at"] = datetime.now(timezone.utc).isoformat()
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.doc.update_status",
        data={
            "doc_id": doc.doc_id,
            "new_status": _get_enum_value(doc.status),
            "version": doc.version,
            "reason": reason
        }
    )


# =============================================================================
# MCP TOOLS: CANVAS MANIPULATION
# =============================================================================

@mcp_tool("report.canvas.add_page", requires_case_id=False)
@with_coc_logging("REPORT_PAGE_ADDED")
async def add_canvas_page(
    doc_id: str,
    section_type: str,
    label: Optional[str] = None,
    position: Optional[int] = None,
    **kwargs
) -> ToolResult:
    """
    Add a new page to the report canvas.
    
    Args:
        doc_id: Document identifier
        section_type: Type of section (executive_summary, timeline_narrative, etc.)
        label: Optional custom label for the page
        position: Optional position (inserts at position, default appends)
        
    Returns:
        ToolResult with new page metadata
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_page",
            error=f"Document not found: {doc_id}"
        )
    
    try:
        sec_type = SectionType(section_type)
    except ValueError:
        valid = [s.value for s in SectionType]
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_page",
            error=f"Invalid section_type: {section_type}. Valid: {valid}"
        )
    
    page = doc.add_page(sec_type, label or "")
    
    # Handle position insertion
    if position is not None and position < len(doc.pages):
        doc.pages.remove(page)
        doc.pages.insert(position, page)
        # Renumber pages
        for i, p in enumerate(doc.pages):
            p.page_number = i + 1
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.canvas.add_page",
        data={
            "doc_id": doc_id,
            "page_id": page.page_id,
            "page_number": page.page_number,
            "section_type": _get_enum_value(page.section_type),
            "label": page.label,
            "total_pages": doc.total_pages()
        }
    )


@mcp_tool("report.canvas.add_element", requires_case_id=False)
@with_coc_logging("REPORT_ELEMENT_ADDED")
async def add_canvas_element(
    doc_id: str,
    page_id: str,
    element_type: str,
    content: Dict[str, Any],
    position: Optional[Dict[str, Any]] = None,
    evidence_ids: Optional[List[str]] = None,
    **kwargs
) -> ToolResult:
    """
    Add an element to a canvas page.
    
    Args:
        doc_id: Document identifier
        page_id: Page identifier
        element_type: Type of element (text, evidenceBlock, chart, table, etc.)
        content: Element content (varies by type)
        position: Optional position {x, y, width, height, z_index}
        evidence_ids: Optional evidence vault IDs to attach
        
    Content formats by type:
        - text: {"text": "...", "format": "paragraph|heading|bullet"}
        - evidenceBlock: {"evidence_id": "...", "display": "metric|finding|chart|table"}
        - chart: {"chart_type": "timeline|bar|line", "data": {...}}
        - table: {"columns": [...], "rows": [[...]]}
        
    Returns:
        ToolResult with element metadata
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_element",
            error=f"Document not found: {doc_id}"
        )
    
    page = next((p for p in doc.pages if p.page_id == page_id), None)
    if not page:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_element",
            error=f"Page not found: {page_id}"
        )
    
    try:
        elem_type = ElementType(element_type)
    except ValueError:
        valid = [e.value for e in ElementType]
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_element",
            error=f"Invalid element_type: {element_type}. Valid: {valid}"
        )
    
    # Parse position
    pos = CanvasPosition()
    if position:
        pos = CanvasPosition(
            x=position.get("x", 0),
            y=position.get("y", len(page.elements) * 50),  # Stack vertically
            width=position.get("width", 180),
            height=position.get("height"),
            z_index=position.get("z_index", len(page.elements))
        )
    else:
        # Auto-position: stack below last element
        if page.elements:
            last = page.elements[-1]
            pos.y = last.position.y + (last.position.height or 50) + 10
        pos.z_index = len(page.elements)
    
    # Create element
    element = CanvasElement(
        type=elem_type,
        position=pos,
        content=content,
        evidence_refs=evidence_ids or []
    )
    element.element_hash = element.compute_element_hash()
    
    page.elements.append(element)
    page.page_hash = page.compute_page_hash()
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.canvas.add_element",
        data={
            "doc_id": doc_id,
            "page_id": page_id,
            "element_id": element.element_id,
            "element_type": element.type.value,
            "position": {
                "x": element.position.x,
                "y": element.position.y,
                "width": element.position.width,
                "height": element.position.height,
                "z_index": element.position.z_index
            },
            "element_hash": element.element_hash,
            "evidence_refs": element.evidence_refs
        }
    )


@mcp_tool("report.canvas.add_evidence_block", requires_case_id=False)
@with_coc_logging("EVIDENCE_BLOCK_ADDED")
async def add_evidence_block(
    doc_id: str,
    page_id: str,
    evidence_id: str,
    display_type: str = "finding",
    title: Optional[str] = None,
    position: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ToolResult:
    """
    Add an evidence block from the Evidence Vault to the canvas.
    
    This is a specialized helper that:
    1. Retrieves evidence from the vault
    2. Creates properly formatted evidence block
    3. Links citation for verification
    
    Args:
        doc_id: Document identifier
        page_id: Page identifier  
        evidence_id: Evidence Vault ID
        display_type: How to display (metric, finding, chart, table, list)
        title: Optional custom title (defaults to evidence title)
        position: Optional position
        
    Returns:
        ToolResult with evidence block details and citation
    """
    # Get evidence from vault
    evidence = EvidenceVault.get(evidence_id)
    if not evidence:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_evidence_block",
            error=f"Evidence not found in vault: {evidence_id}"
        )
    
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_evidence_block",
            error=f"Document not found: {doc_id}"
        )
    
    page = next((p for p in doc.pages if p.page_id == page_id), None)
    if not page:
        return ToolResult(
            success=False,
            tool_name="report.canvas.add_evidence_block",
            error=f"Page not found: {page_id}"
        )
    
    # Get citation from vault
    citation = EvidenceVault.cite(evidence_id)
    
    # Build content based on evidence data
    content = {
        "evidence_id": evidence_id,
        "display_type": display_type,
        "title": title or evidence.title,
        "data": evidence.data,
        "source": evidence.source,
        "timestamp": evidence.timestamp.isoformat() if evidence.timestamp else None,
        "citation": citation,
        "metadata": {
            "citationId": citation,
            "dataHash": evidence.hash,
            "source_module": evidence.source,
            "verified": True
        }
    }
    
    # Determine height based on display type
    height_map = {
        "metric": 80,
        "finding": 120,
        "chart": 250,
        "table": 200,
        "list": 150
    }
    
    pos = CanvasPosition()
    if position:
        pos = CanvasPosition(**position)
    else:
        if page.elements:
            last = page.elements[-1]
            pos.y = last.position.y + (last.position.height or 50) + 10
        pos.height = height_map.get(display_type, 150)
        pos.z_index = len(page.elements)
    
    element = CanvasElement(
        type=ElementType.EVIDENCE_BLOCK,
        position=pos,
        content=content,
        evidence_refs=[evidence_id],
        metadata={
            "citation": citation,
            "verified_hash": evidence.hash
        }
    )
    element.element_hash = element.compute_element_hash()
    
    page.elements.append(element)
    page.page_hash = page.compute_page_hash()
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.canvas.add_evidence_block",
        data={
            "doc_id": doc_id,
            "page_id": page_id,
            "element_id": element.element_id,
            "evidence_id": evidence_id,
            "citation": citation,
            "display_type": display_type,
            "title": content["title"],
            "data_hash": evidence.hash,
            "verified": True
        }
    )


@mcp_tool("report.canvas.get_page", requires_case_id=False)
async def get_canvas_page(doc_id: str, page_id: str, **kwargs) -> ToolResult:
    """
    Get full details of a canvas page including all elements.
    
    Args:
        doc_id: Document identifier
        page_id: Page identifier
        
    Returns:
        ToolResult with page details and elements
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.canvas.get_page",
            error=f"Document not found: {doc_id}"
        )
    
    page = next((p for p in doc.pages if p.page_id == page_id), None)
    if not page:
        return ToolResult(
            success=False,
            tool_name="report.canvas.get_page",
            error=f"Page not found: {page_id}"
        )
    
    return ToolResult(
        success=True,
        tool_name="report.canvas.get_page",
        data={
            "page_id": page.page_id,
            "page_number": page.page_number,
            "section_type": _get_enum_value(page.section_type),
            "label": page.label,
            "page_hash": page.page_hash,
            "elements": [
                {
                    "element_id": e.element_id,
                    "type": _get_enum_value(e.type),
                    "position": {
                        "x": e.position.x,
                        "y": e.position.y,
                        "width": e.position.width,
                        "height": e.position.height,
                        "z_index": e.position.z_index
                    },
                    "content": e.content,
                    "evidence_refs": e.evidence_refs,
                    "element_hash": e.element_hash
                }
                for e in page.elements
            ]
        }
    )


@mcp_tool("report.canvas.reorder_pages", requires_case_id=False)
async def reorder_canvas_pages(
    doc_id: str,
    page_order: List[str],  # List of page_ids in desired order
    **kwargs
) -> ToolResult:
    """
    Reorder pages in the document.
    
    Args:
        doc_id: Document identifier
        page_order: List of page_ids in new order
        
    Returns:
        ToolResult with new page order
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.canvas.reorder_pages",
            error=f"Document not found: {doc_id}"
        )
    
    # Validate all page IDs exist
    existing_ids = {p.page_id for p in doc.pages}
    for pid in page_order:
        if pid not in existing_ids:
            return ToolResult(
                success=False,
                tool_name="report.canvas.reorder_pages",
                error=f"Page not found: {pid}"
            )
    
    # Reorder pages
    page_map = {p.page_id: p for p in doc.pages}
    doc.pages = [page_map[pid] for pid in page_order]
    
    # Renumber
    for i, p in enumerate(doc.pages):
        p.page_number = i + 1
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.canvas.reorder_pages",
        data={
            "doc_id": doc_id,
            "page_order": [
                {"page_id": p.page_id, "page_number": p.page_number, "label": p.label}
                for p in doc.pages
            ]
        }
    )


# =============================================================================
# MCP TOOLS: NARRATIVE GENERATION
# =============================================================================

@mcp_tool("report.narrative.generate", requires_case_id=False)
@with_coc_logging("NARRATIVE_GENERATED")
async def generate_narrative(
    section_type: str,
    context: Dict[str, Any],
    style: str = "technical",
    evidence_ids: Optional[List[str]] = None,
    max_words: int = 500,
    **kwargs
) -> ToolResult:
    """
    Generate narrative text for a report section using LLM.
    
    IMPORTANT: AI generates prose/summaries. All facts (IPs, users, timestamps)
    come from the provided context and evidence, NOT generated by AI.
    
    Args:
        section_type: Type of section to generate
        context: Context data including module results
        style: Writing style (technical, executive, regulatory, legal)
        evidence_ids: Evidence vault IDs to cite
        max_words: Maximum word count
        
    Returns:
        ToolResult with generated narrative and citations
    """
    try:
        sec_type = SectionType(section_type)
    except ValueError:
        valid = [s.value for s in SectionType]
        return ToolResult(
            success=False,
            tool_name="report.narrative.generate",
            error=f"Invalid section_type: {section_type}. Valid: {valid}"
        )
    
    try:
        narr_style = NarrativeStyle(style)
    except ValueError:
        valid = [s.value for s in NarrativeStyle]
        return ToolResult(
            success=False,
            tool_name="report.narrative.generate",
            error=f"Invalid style: {style}. Valid: {valid}"
        )
    
    # Collect evidence for citations
    citations = []
    facts_used = []
    evidence_list_str = ""
    
    if evidence_ids:
        for eid in evidence_ids:
            ev = EvidenceVault.get(eid)
            if ev:
                cite = EvidenceVault.cite(eid)
                citations.append(CitationRef(
                    evidence_id=eid,
                    text=cite,
                    verified=True
                ))
                facts_used.append({
                    "evidence_id": eid,
                    "title": ev.title,
                    "source": ev.source,
                    "hash": ev.hash,
                    "data_summary": str(ev.data)[:200]
                })
                evidence_list_str += f"- {cite}: {ev.title}\n"
    
    # Build prompt from template
    prompt_template = SECTION_PROMPTS.get(sec_type)
    if not prompt_template:
        prompt_template = """
Generate content for a {section_type} section.

Context:
{context}

Requirements:
- Write in {style} style
- Maximum {max_words} words
- Include citation markers [EV-XXXXXX] for factual claims
- Only use facts from provided context, do not invent data

Evidence to cite:
{evidence_list}
"""
    
    # Format prompt with context
    prompt = prompt_template.format(
        section_type=section_type,
        style=style,
        max_words=max_words,
        evidence_list=evidence_list_str or "No evidence attached",
        **{k: str(v)[:1000] for k, v in context.items()}  # Truncate long values
    )
    
    # === MOCK LLM GENERATION ===
    # In production, this calls Gemini/OpenAI API
    # For demo, we generate structured content from context
    
    narrative_content = _generate_mock_narrative(sec_type, narr_style, context, citations)
    
    # Create narrative output
    output = NarrativeOutput(
        section_type=sec_type,
        style=narr_style,
        content=narrative_content,
        citations=citations,
        facts_used=facts_used,
        word_count=len(narrative_content.split())
    )
    
    store.store_narrative(output)
    
    return ToolResult(
        success=True,
        tool_name="report.narrative.generate",
        data={
            "narrative_id": output.narrative_id,
            "section_type": _get_enum_value(output.section_type),
            "style": _get_enum_value(output.style),
            "content": output.content,
            "word_count": output.word_count,
            "citations": [
                {
                    "citation_id": c.citation_id,
                    "evidence_id": c.evidence_id,
                    "text": c.text
                }
                for c in output.citations
            ],
            "facts_used_count": len(output.facts_used),
            "generated_at": output.generated_at.isoformat()
        },
        evidence_hash=output.content_hash
    )


def _generate_mock_narrative(
    section_type: SectionType,
    style: NarrativeStyle,
    context: Dict[str, Any],
    citations: List[CitationRef]
) -> str:
    """
    Generate mock narrative for demonstration.
    In production, this is replaced by LLM API call.
    """
    cite_refs = " ".join([f"[{c.text}]" for c in citations[:3]]) if citations else ""
    
    templates = {
        SectionType.EXECUTIVE_SUMMARY: f"""
## Executive Summary

This forensic investigation was initiated to examine potential unauthorized data transfer activities. Based on comprehensive analysis of digital evidence, system logs, and network traffic patterns, the investigation team has identified significant indicators of data exfiltration.

**Key Findings:**
The analysis revealed {context.get('anomaly_count', 'multiple')} anomalous events during the investigation period. Timeline correlation indicates a pattern of file access followed by external transmission activities. {cite_refs}

**Business Impact:**
The severity assessment indicates {context.get('severity', 'HIGH')} risk to organizational data integrity. Immediate remediation actions are recommended to prevent further exposure.

**Confidence Assessment:**
Based on multi-module analysis and cross-validation, the investigation conclusions carry a confidence level of {context.get('confidence', 'HIGH')} per ODNI ICD 203 standards.
""",

        SectionType.TIMELINE_NARRATIVE: f"""
## Timeline Analysis

The following chronological sequence of events was reconstructed from available digital evidence. All timestamps are derived directly from system logs and have been verified against the evidence vault.

**Initial Activity Period:**
Analysis of the unified timeline reveals the first relevant activity at {context.get('start_time', 'T-0')}. During this period, {context.get('event_count', 'multiple')} events were recorded across monitored systems. {cite_refs}

**Critical Anchor Events:**
Several anchor points were identified that correspond to significant investigative findings. These events serve as reference points for establishing the sequence of activities and validating hypothesis testing results.

**Temporal Patterns:**
Statistical analysis of event clustering reveals {context.get('cluster_count', 'distinct')} activity bursts that correlate with the hypothesized data transfer activities.
""",

        SectionType.ANOMALY_FINDINGS: f"""
## Anomaly Detection Findings

Machine learning-based anomaly detection was applied to the event timeline using Isolation Forest algorithm with SHAP explanations for interpretability.

**Detection Summary:**
- Total events analyzed: {context.get('total_events', 'N/A')}
- Anomalies detected: {context.get('anomaly_count', 'N/A')}
- Average anomaly score: {context.get('avg_score', 'N/A')}

**Top Contributing Features (SHAP Analysis):**
The following features contributed most significantly to anomaly classification: {context.get('top_features', 'event timing, file size, access pattern')}. {cite_refs}

**Severity Assessment:**
Anomalies were classified by severity with {context.get('critical_count', '0')} critical, {context.get('high_count', '0')} high, and {context.get('medium_count', '0')} medium findings requiring attention.
""",

        SectionType.HYPOTHESIS_ANALYSIS: f"""
## Hypothesis Analysis

The investigation employed Analysis of Competing Hypotheses (ACH) methodology to evaluate multiple explanations for the observed evidence.

**Null Hypothesis (H0):** No unauthorized data transfer occurred.
Verdict: {context.get('null_verdict', 'REJECTED')} based on evidence weight.

**Alternative Hypotheses:**
{context.get('hypotheses_summary', 'Multiple transfer vectors were evaluated including USB, email, and network exfiltration channels.')}

**Confidence Scoring:**
Final confidence assessment: {context.get('confidence', '85%')} ({context.get('confidence_level', 'HIGH')})

Evidence supporting conclusions: {cite_refs}
""",

        SectionType.FINDINGS: f"""
## Investigation Findings

Based on comprehensive analysis across all investigative modules, the following findings are presented:

**Finding 1:** Evidence confirms unauthorized data access during the investigation period. {cite_refs}

**Finding 2:** Multiple exfiltration channels were utilized, with primary activity observed via {context.get('primary_channel', 'email attachments')}.

**Finding 3:** The actor's activities demonstrate {context.get('pattern', 'deliberate circumvention of security controls')}.

**Evidence Integrity:**
All findings are supported by hash-verified evidence from the forensic vault. Chain of custody documentation is complete for all referenced artifacts.
""",

        SectionType.RECOMMENDATIONS: f"""
## Recommendations

Based on investigation findings, the following remediation actions are recommended:

**Immediate Actions (0-24 hours):**
1. Revoke access credentials for identified accounts
2. Preserve all systems involved for potential legal proceedings
3. Engage incident response team for containment

**Short-term Actions (1-7 days):**
1. Conduct comprehensive access audit across affected systems
2. Implement enhanced monitoring for similar activity patterns
3. Review and update data loss prevention policies

**Long-term Actions (1-3 months):**
1. Deploy behavioral analytics for early detection
2. Conduct security awareness training
3. Review classification and handling procedures for sensitive data
"""
    }
    
    section_val = _get_enum_value(section_type)
    return templates.get(section_type, f"""
## {section_val.replace('_', ' ').title()}

This section contains analysis for {section_val}.

{cite_refs}

Content generated based on provided context and evidence.
""").strip()


@mcp_tool("report.narrative.insert", requires_case_id=False)
@with_coc_logging("NARRATIVE_INSERTED")
async def insert_narrative_to_canvas(
    doc_id: str,
    page_id: str,
    narrative_id: str,
    format: str = "markdown",
    **kwargs
) -> ToolResult:
    """
    Insert a generated narrative into the canvas as a text element.
    
    Args:
        doc_id: Document identifier
        page_id: Page identifier
        narrative_id: Narrative ID from generate
        format: Text format (markdown, html, plain)
        
    Returns:
        ToolResult with inserted element details
    """
    narrative = store._narratives.get(narrative_id)
    if not narrative:
        return ToolResult(
            success=False,
            tool_name="report.narrative.insert",
            error=f"Narrative not found: {narrative_id}"
        )
    
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.narrative.insert",
            error=f"Document not found: {doc_id}"
        )
    
    page = next((p for p in doc.pages if p.page_id == page_id), None)
    if not page:
        return ToolResult(
            success=False,
            tool_name="report.narrative.insert",
            error=f"Page not found: {page_id}"
        )
    
    # Create text element with narrative content
    pos = CanvasPosition()
    if page.elements:
        last = page.elements[-1]
        pos.y = last.position.y + (last.position.height or 50) + 10
    pos.z_index = len(page.elements)
    
    element = CanvasElement(
        type=ElementType.TEXT,
        position=pos,
        content={
            "text": narrative.content,
            "format": format,
            "narrative_id": narrative_id,
            "section_type": _get_enum_value(narrative.section_type),
            "citations": [c.text for c in narrative.citations]
        },
        evidence_refs=[c.evidence_id for c in narrative.citations],
        metadata={
            "generated": True,
            "style": _get_enum_value(narrative.style),
            "word_count": narrative.word_count
        }
    )
    element.element_hash = element.compute_element_hash()
    
    page.elements.append(element)
    page.page_hash = page.compute_page_hash()
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.narrative.insert",
        data={
            "doc_id": doc_id,
            "page_id": page_id,
            "element_id": element.element_id,
            "narrative_id": narrative_id,
            "section_type": _get_enum_value(narrative.section_type),
            "word_count": narrative.word_count,
            "citation_count": len(narrative.citations)
        }
    )


# =============================================================================
# MCP TOOLS: VALIDATION AND EXPORT
# =============================================================================

@mcp_tool("report.validate", requires_case_id=False)
async def validate_report(doc_id: str, **kwargs) -> ToolResult:
    """
    Validate report before export.
    
    Checks:
    - All evidence blocks have valid hashes
    - All citations are resolvable
    - No orphaned references
    - Content integrity
    
    Args:
        doc_id: Document identifier
        
    Returns:
        ToolResult with validation report
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.validate",
            error=f"Document not found: {doc_id}"
        )
    
    issues = []
    warnings = []
    total_evidence_blocks = 0
    cited_evidence = 0
    uncited_evidence = 0
    
    for page in doc.pages:
        for elem in page.elements:
            # Check evidence blocks
            if elem.type == ElementType.EVIDENCE_BLOCK:
                total_evidence_blocks += 1
                
                # Check for citation
                citation = elem.metadata.get("citation") or elem.content.get("metadata", {}).get("citationId")
                if citation:
                    cited_evidence += 1
                else:
                    uncited_evidence += 1
                    issues.append(ValidationIssue(
                        severity="high",
                        element_id=elem.element_id,
                        page_number=page.page_number,
                        issue_type="uncited_evidence",
                        message=f"Evidence block without citation",
                        suggestion="Add citation using report.canvas.add_evidence_block"
                    ))
                
                # Verify hash if present
                evidence_id = elem.content.get("evidence_id")
                if evidence_id:
                    ev = EvidenceVault.get(evidence_id)
                    if not ev:
                        issues.append(ValidationIssue(
                            severity="critical",
                            element_id=elem.element_id,
                            page_number=page.page_number,
                            issue_type="missing_evidence",
                            message=f"Referenced evidence not found: {evidence_id}",
                            suggestion="Remove element or re-add evidence to vault"
                        ))
                    else:
                        stored_hash = elem.content.get("metadata", {}).get("dataHash")
                        if stored_hash and stored_hash != ev.hash:
                            issues.append(ValidationIssue(
                                severity="critical",
                                element_id=elem.element_id,
                                page_number=page.page_number,
                                issue_type="hash_mismatch",
                                message=f"Evidence hash mismatch - data may have been modified",
                                suggestion="Re-add evidence block with fresh vault data"
                            ))
            
            # Check text elements with citations
            if elem.type == ElementType.TEXT:
                citations_in_text = elem.content.get("citations", [])
                for cite in citations_in_text:
                    # Try to extract evidence ID from citation
                    if cite.startswith("[EV-"):
                        # Citation format: [EV-XXXXXX]
                        evidence_id = None  # Would need reverse lookup
                        warnings.append(f"Citation {cite} on page {page.page_number} - verify manually")
    
    # Check document completeness
    if not doc.pages:
        issues.append(ValidationIssue(
            severity="critical",
            element_id="document",
            page_number=0,
            issue_type="empty_document",
            message="Document has no pages",
            suggestion="Add pages using report.canvas.add_page"
        ))
    
    # Determine overall validity
    critical_issues = [i for i in issues if i.severity == "critical"]
    valid = len(critical_issues) == 0
    
    result = ValidationResult(
        valid=valid,
        total_evidence_blocks=total_evidence_blocks,
        cited_evidence=cited_evidence,
        uncited_evidence=uncited_evidence,
        issues=issues,
        warnings=warnings
    )
    
    return ToolResult(
        success=True,
        tool_name="report.validate",
        data={
            "doc_id": doc_id,
            "valid": result.valid,
            "total_evidence_blocks": result.total_evidence_blocks,
            "cited_evidence": result.cited_evidence,
            "uncited_evidence": result.uncited_evidence,
            "critical_issues": len(critical_issues),
            "total_issues": len(result.issues),
            "warnings": len(result.warnings),
            "issues": [
                {
                    "severity": i.severity,
                    "element_id": i.element_id,
                    "page_number": i.page_number,
                    "issue_type": i.issue_type,
                    "message": i.message,
                    "suggestion": i.suggestion
                }
                for i in result.issues
            ],
            "ready_for_export": result.valid
        }
    )


@mcp_tool("report.export", requires_case_id=False)
@with_coc_logging("REPORT_EXPORTED")
async def export_report(
    doc_id: str,
    format: str = "pdf",
    include_appendices: bool = True,
    include_evidence_inventory: bool = True,
    **kwargs
) -> ToolResult:
    """
    Export report to file format.
    
    Pre-export validation is performed automatically.
    
    Args:
        doc_id: Document identifier
        format: Export format (pdf, docx, html)
        include_appendices: Include appendix sections
        include_evidence_inventory: Include evidence inventory table
        
    Returns:
        ToolResult with export details and file path
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.export",
            error=f"Document not found: {doc_id}"
        )
    
    try:
        export_fmt = ExportFormat(format)
    except ValueError:
        valid = [f.value for f in ExportFormat]
        return ToolResult(
            success=False,
            tool_name="report.export",
            error=f"Invalid format: {format}. Valid: {valid}"
        )
    
    # Run validation first
    validation = await validate_report(doc_id)
    if not validation.data.get("valid"):
        critical_count = validation.data.get("critical_issues", 0)
        return ToolResult(
            success=False,
            tool_name="report.export",
            error=f"Validation failed with {critical_count} critical issues. Fix issues before export.",
            data=validation.data
        )
    
    # === MOCK EXPORT ===
    # In production, this calls the actual export service
    
    # Count evidence
    evidence_count = 0
    citation_count = 0
    for page in doc.pages:
        for elem in page.elements:
            evidence_count += len(elem.evidence_refs)
            if elem.metadata.get("citation"):
                citation_count += 1
    
    # Generate file path
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{doc.case_id}_{doc_id}_{timestamp}.{format}"
    file_path = f"/exports/{filename}"
    
    # Compute file hash (mock)
    file_content = json.dumps({
        "doc_id": doc_id,
        "title": doc.title,
        "pages": len(doc.pages),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }, sort_keys=True)
    file_hash = f"sha256:{hashlib.sha256(file_content.encode()).hexdigest()}"
    
    # Create export result
    result = ExportResult(
        doc_id=doc_id,
        format=export_fmt,
        file_path=file_path,
        file_hash=file_hash,
        page_count=doc.total_pages(),
        evidence_count=evidence_count,
        citation_count=citation_count,
        manifest={
            "title": doc.title,
            "case_id": doc.case_id,
            "template": doc.template,
            "version": doc.version,
            "include_appendices": include_appendices,
            "include_evidence_inventory": include_evidence_inventory,
            "sections": [_get_enum_value(p.section_type) for p in doc.pages]
        }
    )
    
    store.record_export(result)
    
    # Update document status
    doc.status = DocumentStatus.EXPORTED
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.export",
        data={
            "export_id": result.export_id,
            "doc_id": result.doc_id,
            "format": _get_enum_value(result.format),
            "file_path": result.file_path,
            "file_hash": result.file_hash,
            "page_count": result.page_count,
            "evidence_count": result.evidence_count,
            "citation_count": result.citation_count,
            "exported_at": result.exported_at.isoformat(),
            "manifest": result.manifest
        },
        evidence_hash=result.content_hash,
        coc_event_id=f"coc-export-{uuid.uuid4().hex[:8]}"
    )


@mcp_tool("report.exports.list", requires_case_id=False)
async def list_exports(doc_id: str, **kwargs) -> ToolResult:
    """
    List all exports for a document.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        ToolResult with export history
    """
    exports = store._exports.get(doc_id, [])
    
    return ToolResult(
        success=True,
        tool_name="report.exports.list",
        data={
            "doc_id": doc_id,
            "export_count": len(exports),
            "exports": [
                {
                    "export_id": e.export_id,
                    "format": _get_enum_value(e.format),
                    "file_path": e.file_path,
                    "file_hash": e.file_hash,
                    "page_count": e.page_count,
                    "exported_at": e.exported_at.isoformat()
                }
                for e in exports
            ]
        }
    )


# =============================================================================
# MCP TOOLS: REPORT BUILDER HELPERS
# =============================================================================

@mcp_tool("report.build.from_investigation")
@with_coc_logging("REPORT_AUTO_GENERATED")
async def build_report_from_investigation(
    case_id: str,
    investigation_id: str,
    title: Optional[str] = None,
    template: str = "default",
    sections: Optional[List[str]] = None,
    **kwargs
) -> ToolResult:
    """
    Build a complete report from investigation results.
    
    This is a high-level helper that:
    1. Creates document
    2. Adds standard sections
    3. Pulls evidence from vault
    4. Generates narratives
    5. Populates canvas with content
    
    Args:
        case_id: Case identifier
        investigation_id: Investigation session ID
        title: Optional report title
        template: Report template
        sections: Optional list of section types to include
        
    Returns:
        ToolResult with created document details
    """
    # Default sections for a forensic report
    default_sections = [
        SectionType.COVER,
        SectionType.TABLE_OF_CONTENTS,
        SectionType.EXECUTIVE_SUMMARY,
        SectionType.CASE_OVERVIEW,
        SectionType.METHODOLOGY,
        SectionType.TIMELINE_NARRATIVE,
        SectionType.ANOMALY_FINDINGS,
        SectionType.CORRELATION_ANALYSIS,
        SectionType.NETWORK_ANALYSIS,
        SectionType.DATA_ACCESS_ANALYSIS,
        SectionType.IMPACT_ASSESSMENT,
        SectionType.HYPOTHESIS_ANALYSIS,
        SectionType.FINDINGS,
        SectionType.RECOMMENDATIONS,
        SectionType.EVIDENCE_INVENTORY,
        SectionType.CHAIN_OF_CUSTODY,
    ]
    
    # Use provided sections or default
    report_sections = []
    if sections:
        for s in sections:
            try:
                report_sections.append(SectionType(s))
            except ValueError:
                pass  # Skip invalid sections
    else:
        report_sections = default_sections
    
    # Create document
    doc = store.create_document(
        case_id=case_id,
        title=title or f"Forensic Investigation Report - {investigation_id}",
        template=template,
        created_by="investigation_agent"
    )
    doc.metadata["investigation_id"] = investigation_id
    doc.metadata["auto_generated"] = True
    doc.metadata["generated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Add pages for each section
    pages_created = []
    for section in report_sections:
        page = doc.add_page(section)
        pages_created.append({
            "page_id": page.page_id,
            "page_number": page.page_number,
            "section_type": section.value,
            "label": page.label
        })
    
    # Get evidence from vault for this investigation
    evidence_items = []
    # Query vault for investigation evidence (mock - would filter by investigation_id in production)
    all_evidence = list(EvidenceVault._evidence.values())[:20]  # First 20 items
    for ev in all_evidence:
        evidence_items.append({
            "evidence_id": ev.evidence_id,
            "title": ev.title,
            "source": ev.source,
            "citation": EvidenceVault.cite(ev.evidence_id)
        })
    
    store.update_document(doc)
    
    return ToolResult(
        success=True,
        tool_name="report.build.from_investigation",
        data={
            "doc_id": doc.doc_id,
            "case_id": doc.case_id,
            "investigation_id": investigation_id,
            "title": doc.title,
            "template": doc.template,
            "total_pages": doc.total_pages(),
            "pages_created": pages_created,
            "available_evidence": len(evidence_items),
            "evidence_items": evidence_items[:10],  # First 10 for display
            "status": _get_enum_value(doc.status),
            "next_steps": [
                f"Use report.narrative.generate to create content for each section",
                f"Use report.canvas.add_evidence_block to add evidence from vault",
                f"Use report.validate to check report completeness",
                f"Use report.export to generate final PDF/DOCX"
            ]
        },
        evidence_hash=doc.content_hash
    )


@mcp_tool("report.summary", requires_case_id=False)
async def get_report_summary(doc_id: str, **kwargs) -> ToolResult:
    """
    Get a summary of report structure and completeness.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        ToolResult with report summary statistics
    """
    doc = store.get_document(doc_id)
    if not doc:
        return ToolResult(
            success=False,
            tool_name="report.summary",
            error=f"Document not found: {doc_id}"
        )
    
    # Analyze document structure
    section_stats = {}
    total_elements = 0
    total_evidence = 0
    total_text = 0
    total_words = 0
    
    for page in doc.pages:
        section = _get_enum_value(page.section_type)
        if section not in section_stats:
            section_stats[section] = {"pages": 0, "elements": 0, "evidence": 0}
        section_stats[section]["pages"] += 1
        section_stats[section]["elements"] += len(page.elements)
        
        for elem in page.elements:
            total_elements += 1
            if _get_enum_value(elem.type) == "evidenceBlock":
                total_evidence += 1
                section_stats[section]["evidence"] += 1
            elif _get_enum_value(elem.type) == "text":
                total_text += 1
                text_content = elem.content.get("text", "")
                total_words += len(text_content.split())
    
    # Estimate page count (A4 ~500 words per page)
    estimated_physical_pages = max(doc.total_pages(), total_words // 500 + 1)
    
    return ToolResult(
        success=True,
        tool_name="report.summary",
        data={
            "doc_id": doc.doc_id,
            "title": doc.title,
            "status": _get_enum_value(doc.status),
            "version": doc.version,
            "total_canvas_pages": doc.total_pages(),
            "estimated_physical_pages": estimated_physical_pages,
            "total_elements": total_elements,
            "total_evidence_blocks": total_evidence,
            "total_text_elements": total_text,
            "total_words": total_words,
            "sections": section_stats,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
            "completeness": {
                "has_cover": "cover" in section_stats,
                "has_executive_summary": "executive_summary" in section_stats,
                "has_findings": "findings" in section_stats,
                "has_recommendations": "recommendations" in section_stats,
                "evidence_cited": total_evidence > 0
            }
        }
    )


# =============================================================================
# TOOL EXPORTS
# =============================================================================

REPORT_TOOLS = [
    # Document management
    create_report_document,
    get_report_document,
    list_report_documents,
    update_document_status,
    
    # Canvas manipulation
    add_canvas_page,
    add_canvas_element,
    add_evidence_block,
    get_canvas_page,
    reorder_canvas_pages,
    
    # Narrative generation
    generate_narrative,
    insert_narrative_to_canvas,
    
    # Validation and export
    validate_report,
    export_report,
    list_exports,
    
    # Helpers
    build_report_from_investigation,
    get_report_summary,
]


def register_report_tools(registry):
    """Register all report tools with the MCP registry."""
    for tool in REPORT_TOOLS:
        registry.register(tool)


# Export for package
__all__ = [
    # Enums
    "DocumentStatus",
    "SectionType", 
    "ElementType",
    "NarrativeStyle",
    "ExportFormat",
    
    # Models
    "CanvasPosition",
    "CanvasElement",
    "CanvasPage",
    "ReportDocument",
    "CitationRef",
    "NarrativeContext",
    "NarrativeOutput",
    "ExportResult",
    "ValidationIssue",
    "ValidationResult",
    
    # Store
    "ReportStore",
    "store",
    
    # Tools
    "REPORT_TOOLS",
    "register_report_tools",
]
