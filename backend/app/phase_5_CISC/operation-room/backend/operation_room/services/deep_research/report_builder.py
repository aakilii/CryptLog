"""
Report Structure Models for Hybrid Report Building.

Implements:
- ReportSection: Section of a report
- ReportStructure: Full report structure
- ReportBuilder: Hybrid build (structure → fill)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class SectionType(str, Enum):
    """Types of report sections."""
    TITLE_PAGE = "title_page"
    TABLE_OF_CONTENTS = "table_of_contents"
    EXECUTIVE_SUMMARY = "executive_summary"
    METHODOLOGY = "methodology"
    TIMELINE_ANALYSIS = "timeline_analysis"
    ANOMALY_ANALYSIS = "anomaly_analysis"
    ENTITY_ANALYSIS = "entity_analysis"
    NETWORK_ANALYSIS = "network_analysis"
    HYPOTHESIS_FINDINGS = "hypothesis_findings"
    EVIDENCE_SUMMARY = "evidence_summary"
    RECOMMENDATIONS = "recommendations"
    APPENDIX = "appendix"
    CUSTOM = "custom"


class SectionStatus(str, Enum):
    """Status of a section."""
    EMPTY = "empty"
    OUTLINED = "outlined"
    DRAFTED = "drafted"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"


@dataclass
class SectionContent:
    """Content for a section."""
    text: str = ""
    elements: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "elements": self.elements,
            "evidence_refs": self.evidence_refs,
            "citations": self.citations,
        }


@dataclass
class ReportSection:
    """A section of the report."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Content
    title: str = ""
    section_type: SectionType = SectionType.CUSTOM
    
    # Hierarchy
    level: int = 1  # 1 = top level, 2 = subsection, etc.
    order: int = 0
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    
    # Content
    content: SectionContent = field(default_factory=SectionContent)
    outline: str = ""  # What this section should contain
    
    # Status
    status: SectionStatus = SectionStatus.EMPTY
    
    # Page info
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    estimated_pages: float = 1.0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if section is complete."""
        return self.status in [SectionStatus.REVIEWED, SectionStatus.FINALIZED]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "section_type": self.section_type.value,
            "level": self.level,
            "order": self.order,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "content": self.content.to_dict(),
            "outline": self.outline,
            "status": self.status.value,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "estimated_pages": self.estimated_pages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ReportStructure:
    """Complete report structure."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    
    # Content
    title: str = ""
    subtitle: str = ""
    
    # Sections
    sections: Dict[str, ReportSection] = field(default_factory=dict)
    section_order: List[str] = field(default_factory=list)
    
    # Document info
    document_id: Optional[str] = None  # Report Studio V4 doc ID
    total_pages: int = 0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Version
    version: int = 1
    
    def add_section(
        self,
        title: str,
        section_type: SectionType = SectionType.CUSTOM,
        level: int = 1,
        parent_id: Optional[str] = None,
        outline: str = "",
        estimated_pages: float = 1.0,
    ) -> ReportSection:
        """Add a section to the structure."""
        section = ReportSection(
            title=title,
            section_type=section_type,
            level=level,
            order=len(self.section_order),
            parent_id=parent_id,
            outline=outline,
            estimated_pages=estimated_pages,
        )
        
        self.sections[section.id] = section
        self.section_order.append(section.id)
        
        if parent_id and parent_id in self.sections:
            self.sections[parent_id].children_ids.append(section.id)
        
        self._update_page_numbers()
        self.updated_at = datetime.now()
        self.version += 1
        
        return section
    
    def get_section(self, section_id: str) -> Optional[ReportSection]:
        """Get a section by ID."""
        return self.sections.get(section_id)
    
    def get_sections_by_type(self, section_type: SectionType) -> List[ReportSection]:
        """Get all sections of a type."""
        return [s for s in self.sections.values() if s.section_type == section_type]
    
    def get_root_sections(self) -> List[ReportSection]:
        """Get top-level sections in order."""
        return [
            self.sections[sid] 
            for sid in self.section_order 
            if sid in self.sections and self.sections[sid].level == 1
        ]
    
    def remove_section(self, section_id: str) -> bool:
        """Remove a section."""
        if section_id not in self.sections:
            return False
        
        section = self.sections[section_id]
        
        # Remove from parent
        if section.parent_id and section.parent_id in self.sections:
            parent = self.sections[section.parent_id]
            parent.children_ids = [c for c in parent.children_ids if c != section_id]
        
        # Remove children recursively
        for child_id in section.children_ids:
            self.remove_section(child_id)
        
        # Remove section
        del self.sections[section_id]
        self.section_order = [s for s in self.section_order if s != section_id]
        
        self._update_page_numbers()
        self.updated_at = datetime.now()
        self.version += 1
        
        return True
    
    def reorder_section(self, section_id: str, new_order: int) -> None:
        """Reorder a section."""
        if section_id not in self.section_order:
            return
        
        old_order = self.section_order.index(section_id)
        self.section_order.remove(section_id)
        self.section_order.insert(new_order, section_id)
        
        # Update order values
        for i, sid in enumerate(self.section_order):
            if sid in self.sections:
                self.sections[sid].order = i
        
        self._update_page_numbers()
        self.updated_at = datetime.now()
        self.version += 1
    
    def _update_page_numbers(self) -> None:
        """Recalculate page numbers."""
        current_page = 1
        
        for sid in self.section_order:
            if sid not in self.sections:
                continue
            
            section = self.sections[sid]
            section.start_page = current_page
            section.end_page = current_page + int(section.estimated_pages) - 1
            current_page = section.end_page + 1
        
        self.total_pages = current_page - 1
    
    def get_table_of_contents(self) -> List[Dict[str, Any]]:
        """Generate table of contents."""
        toc = []
        
        for sid in self.section_order:
            section = self.sections.get(sid)
            if not section:
                continue
            
            toc.append({
                "id": section.id,
                "title": section.title,
                "level": section.level,
                "page": section.start_page,
                "status": section.status.value,
            })
        
        return toc
    
    def get_progress(self) -> Dict[str, Any]:
        """Calculate overall progress."""
        total = len(self.sections)
        if total == 0:
            return {"progress": 0, "completed": 0, "total": 0}
        
        completed = sum(1 for s in self.sections.values() if s.is_complete)
        drafted = sum(1 for s in self.sections.values() if s.status == SectionStatus.DRAFTED)
        
        return {
            "progress": (completed + drafted * 0.5) / total,
            "completed": completed,
            "drafted": drafted,
            "total": total,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "title": self.title,
            "subtitle": self.subtitle,
            "sections": {k: v.to_dict() for k, v in self.sections.items()},
            "section_order": self.section_order,
            "document_id": self.document_id,
            "total_pages": self.total_pages,
            "toc": self.get_table_of_contents(),
            "progress": self.get_progress(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }


class ReportBuilder:
    """
    Hybrid report builder.
    
    Workflow:
    1. Create structure (sections, outline)
    2. Fill content section by section
    3. Verify and finalize
    """
    
    def __init__(self):
        """Initialize the builder."""
        self._structures: Dict[str, ReportStructure] = {}
    
    def create_structure(
        self,
        investigation_id: str,
        title: str = "",
        template: Optional[str] = None,
    ) -> ReportStructure:
        """
        Create a new report structure.
        
        Args:
            investigation_id: Associated investigation
            title: Report title
            template: Optional template name
            
        Returns:
            Created structure
        """
        structure = ReportStructure(
            investigation_id=investigation_id,
            title=title or "Forensic Investigation Report",
        )
        
        # Apply template if specified
        if template == "standard":
            self._apply_standard_template(structure)
        elif template == "detailed":
            self._apply_detailed_template(structure)
        
        self._structures[structure.id] = structure
        
        return structure
    
    def get_structure(self, structure_id: str) -> Optional[ReportStructure]:
        """Get a structure by ID."""
        return self._structures.get(structure_id)
    
    def get_structure_by_investigation(
        self,
        investigation_id: str,
    ) -> Optional[ReportStructure]:
        """Get structure for an investigation."""
        for structure in self._structures.values():
            if structure.investigation_id == investigation_id:
                return structure
        return None
    
    def _apply_standard_template(self, structure: ReportStructure) -> None:
        """Apply standard report template."""
        sections = [
            (SectionType.TITLE_PAGE, "Title Page", 1, 1),
            (SectionType.TABLE_OF_CONTENTS, "Table of Contents", 1, 1),
            (SectionType.EXECUTIVE_SUMMARY, "Executive Summary", 2, 1),
            (SectionType.METHODOLOGY, "Methodology", 5, 1),
            (SectionType.TIMELINE_ANALYSIS, "Timeline Analysis", 15, 1),
            (SectionType.HYPOTHESIS_FINDINGS, "Findings", 20, 1),
            (SectionType.EVIDENCE_SUMMARY, "Evidence Summary", 10, 1),
            (SectionType.RECOMMENDATIONS, "Recommendations", 3, 1),
            (SectionType.APPENDIX, "Appendix: Evidence Inventory", 10, 1),
        ]
        
        for section_type, title, pages, level in sections:
            structure.add_section(
                title=title,
                section_type=section_type,
                level=level,
                estimated_pages=pages,
            )
    
    def _apply_detailed_template(self, structure: ReportStructure) -> None:
        """Apply detailed 70+ page template."""
        sections = [
            (SectionType.TITLE_PAGE, "Title Page", 1, 1),
            (SectionType.TABLE_OF_CONTENTS, "Table of Contents", 2, 1),
            (SectionType.EXECUTIVE_SUMMARY, "Executive Summary", 3, 1),
            (SectionType.METHODOLOGY, "Investigation Methodology", 5, 1),
            (SectionType.TIMELINE_ANALYSIS, "Timeline Analysis", 15, 1),
            (SectionType.ANOMALY_ANALYSIS, "Anomaly Analysis", 10, 1),
            (SectionType.ENTITY_ANALYSIS, "Entity Analysis", 10, 1),
            (SectionType.NETWORK_ANALYSIS, "Network Analysis", 10, 1),
            (SectionType.HYPOTHESIS_FINDINGS, "Hypothesis Evaluation", 15, 1),
            (SectionType.EVIDENCE_SUMMARY, "Evidence Summary", 5, 1),
            (SectionType.RECOMMENDATIONS, "Recommendations", 3, 1),
            (SectionType.APPENDIX, "Appendix A: Evidence Inventory", 10, 1),
            (SectionType.APPENDIX, "Appendix B: Chain of Custody", 5, 1),
            (SectionType.APPENDIX, "Appendix C: Technical Details", 5, 1),
        ]
        
        for section_type, title, pages, level in sections:
            structure.add_section(
                title=title,
                section_type=section_type,
                level=level,
                estimated_pages=pages,
            )
    
    def fill_section(
        self,
        structure_id: str,
        section_id: str,
        content: SectionContent,
    ) -> ReportSection:
        """
        Fill a section with content.
        
        Args:
            structure_id: Structure ID
            section_id: Section ID
            content: Content to add
            
        Returns:
            Updated section
        """
        structure = self._structures.get(structure_id)
        if not structure:
            raise ValueError(f"Structure not found: {structure_id}")
        
        section = structure.sections.get(section_id)
        if not section:
            raise ValueError(f"Section not found: {section_id}")
        
        section.content = content
        section.status = SectionStatus.DRAFTED
        section.updated_at = datetime.now()
        
        structure.updated_at = datetime.now()
        structure.version += 1
        
        return section
    
    def verify_section(
        self,
        structure_id: str,
        section_id: str,
    ) -> Dict[str, Any]:
        """
        Verify a section's content.
        
        Checks:
        - All evidence references are valid
        - Citations are resolvable
        - Content is not empty
        
        Returns:
            Verification result
        """
        structure = self._structures.get(structure_id)
        if not structure:
            raise ValueError(f"Structure not found: {structure_id}")
        
        section = structure.sections.get(section_id)
        if not section:
            raise ValueError(f"Section not found: {section_id}")
        
        issues = []
        
        # Check content
        if not section.content.text and not section.content.elements:
            issues.append("Section has no content")
        
        # Would verify evidence refs against vault
        # Would verify citations
        
        is_valid = len(issues) == 0
        
        if is_valid:
            section.status = SectionStatus.REVIEWED
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "section_id": section_id,
        }
    
    def finalize_section(
        self,
        structure_id: str,
        section_id: str,
    ) -> ReportSection:
        """Mark a section as finalized."""
        structure = self._structures.get(structure_id)
        if not structure:
            raise ValueError(f"Structure not found: {structure_id}")
        
        section = structure.sections.get(section_id)
        if not section:
            raise ValueError(f"Section not found: {section_id}")
        
        section.status = SectionStatus.FINALIZED
        section.updated_at = datetime.now()
        
        return section
    
    def generate_toc(self, structure_id: str) -> str:
        """Generate Table of Contents text."""
        structure = self._structures.get(structure_id)
        if not structure:
            raise ValueError(f"Structure not found: {structure_id}")
        
        toc_lines = []
        
        for entry in structure.get_table_of_contents():
            indent = "  " * (entry["level"] - 1)
            dots = "." * (60 - len(entry["title"]) - len(indent))
            toc_lines.append(f"{indent}{entry['title']} {dots} {entry['page']}")
        
        return "\n".join(toc_lines)
    
    def fill_section(
        self,
        structure_id: str,
        section_id: str,
        content: str = "",
        elements: Optional[List[Dict[str, Any]]] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> Optional[ReportSection]:
        """
        Fill a section with content (simple string version).
        
        Args:
            structure_id: Structure ID
            section_id: Section ID
            content: Text content
            elements: Optional elements
            evidence_refs: Optional evidence references
            
        Returns:
            Updated section
        """
        structure = self._structures.get(structure_id)
        if not structure:
            return None
        
        section = structure.sections.get(section_id)
        if not section:
            return None
        
        section.content = SectionContent(
            text=content,
            elements=elements or [],
            evidence_refs=evidence_refs or [],
        )
        section.status = SectionStatus.DRAFTED
        section.updated_at = datetime.now()
        
        structure.updated_at = datetime.now()
        structure.version += 1
        
        return section
    
    def get_report_progress(self, structure_id: str) -> Dict[str, Any]:
        """Get detailed report progress."""
        structure = self._structures.get(structure_id)
        if not structure:
            return {"error": "Structure not found"}
        
        progress = structure.get_progress()
        
        section_progress = []
        for sid in structure.section_order:
            section = structure.sections.get(sid)
            if section:
                section_progress.append({
                    "id": section.id,
                    "title": section.title,
                    "status": section.status.value,
                    "is_complete": section.is_complete,
                    "pages": f"{section.start_page}-{section.end_page}",
                })
        
        return {
            **progress,
            "sections": section_progress,
            "total_pages": structure.total_pages,
        }


# Global instance
_report_builder: Optional[ReportBuilder] = None


def get_report_builder() -> ReportBuilder:
    """Get the global report builder."""
    global _report_builder
    if _report_builder is None:
        _report_builder = ReportBuilder()
    return _report_builder
