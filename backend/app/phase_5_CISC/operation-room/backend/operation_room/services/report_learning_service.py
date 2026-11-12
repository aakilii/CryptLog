"""
Report Learning Service - Intelligent Report Generation Phase 1.

Learns from uploaded forensic reports to:
- Extract document structure patterns (headings, subheadings, chart positions)
- Store learned patterns in ChromaDB for similarity search
- Recommend report structures for new investigations
- Track what works well via feedback loop
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from operation_room.config import settings
from operation_room.services.vector_store import get_vector_store, VectorDocument
from operation_room.services.embedding_service import get_embedding_service
from operation_room.services.document_parser.pdf_parser import PDFParser, DocumentLayout, ElementType
from operation_room.services.document_parser.docx_parser import DOCXParser

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# COLLECTION NAMES FOR LEARNING
# ═══════════════════════════════════════════════════════════════════════════════

class LearningCollection(str, Enum):
    """ChromaDB collections for report learning."""
    REPORT_STRUCTURES = "learned_report_structures"    # Full report hierarchies
    SECTION_PATTERNS = "learned_section_patterns"      # Individual section styles
    CHART_PATTERNS = "learned_chart_patterns"          # Chart usage patterns
    TERMINOLOGY = "learned_terminology"                 # Domain terminology
    FEEDBACK = "learning_feedback"                      # User feedback entries


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SectionInfo:
    """Information about a document section."""
    section_id: str
    title: str
    level: int                          # 1 = H1, 2 = H2, etc.
    position: int                       # Order in document
    page_start: int
    page_end: int
    word_count: int
    has_charts: bool = False
    has_tables: bool = False
    has_images: bool = False
    chart_types: List[str] = field(default_factory=list)
    subsections: List["SectionInfo"] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "level": self.level,
            "position": self.position,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "word_count": self.word_count,
            "has_charts": self.has_charts,
            "has_tables": self.has_tables,
            "has_images": self.has_images,
            "chart_types": self.chart_types,
            "subsections": [s.to_dict() for s in self.subsections]
        }


@dataclass
class ReportStructure:
    """Learned structure from a report."""
    report_id: str
    title: str
    case_type: str                      # ransomware, data_exfiltration, fraud, etc.
    total_pages: int
    total_words: int
    sections: List[SectionInfo]
    chart_summary: Dict[str, int]       # chart_type -> count
    metadata: Dict[str, Any] = field(default_factory=dict)
    learned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    quality_rating: float = 0.0         # User feedback 0-5
    times_referenced: int = 0           # How often this structure was used
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "title": self.title,
            "case_type": self.case_type,
            "total_pages": self.total_pages,
            "total_words": self.total_words,
            "sections": [s.to_dict() for s in self.sections],
            "chart_summary": self.chart_summary,
            "metadata": self.metadata,
            "learned_at": self.learned_at.isoformat(),
            "quality_rating": self.quality_rating,
            "times_referenced": self.times_referenced
        }
    
    def to_embedding_text(self) -> str:
        """Generate text for embedding."""
        section_titles = " > ".join([s.title for s in self.sections])
        return f"Case type: {self.case_type}. Report structure: {section_titles}. Pages: {self.total_pages}. Charts: {', '.join(self.chart_summary.keys())}"


@dataclass
class StructureRecommendation:
    """Recommended report structure based on learning."""
    recommended_sections: List[Dict[str, Any]]
    estimated_pages: int
    chart_suggestions: List[Dict[str, Any]]
    similar_reports: List[str]          # IDs of similar reports
    confidence: float                   # 0-1 confidence score
    reasoning: str                      # Why this structure
    
    @property
    def confidence_score(self) -> float:
        """Alias for confidence to match API expectations."""
        return self.confidence
    
    @property
    def sections(self) -> List[Dict[str, Any]]:
        """
        Convert recommended_sections to expected format.
        
        Returns sections with:
        - title: str
        - level: int
        - content_types: List[str]
        - chart_suggestions: List[str]
        """
        result = []
        for sec in self.recommended_sections:
            content_types = []
            if sec.get("suggested_word_count", 0) > 100:
                content_types.append("text")
            if sec.get("suggest_charts"):
                content_types.append("chart")
            if sec.get("suggest_tables"):
                content_types.append("table")
            
            # Find chart suggestions for this section
            section_charts = [
                cs["chart_type"] for cs in self.chart_suggestions
                if cs.get("suggested_section") == sec.get("title")
            ]
            
            result.append({
                "title": sec.get("title", "Untitled"),
                "level": sec.get("level", 2),
                "content_types": content_types or ["text"],
                "chart_suggestions": section_charts
            })
        return result


@dataclass
class LearningFeedback:
    """Feedback on a generated report for learning."""
    feedback_id: str
    report_id: str
    case_id: str
    rating: int                         # 1-5 stars
    structure_feedback: str             # "good" | "too_long" | "missing_sections" | etc.
    specific_issues: List[str]
    suggestions: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
# REPORT LEARNING SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class ReportLearningService:
    """
    Service for learning from uploaded forensic reports.
    
    Capabilities:
    - Parse PDF/DOCX reports and extract structure
    - Store patterns in vector database
    - Query similar reports for structure recommendations
    - Collect feedback for continuous improvement
    """
    
    def __init__(self):
        """Initialize the learning service."""
        self._vector_store = None
        self._embedding_service = None
        self._pdf_parser = PDFParser()
        self._docx_parser = DOCXParser()
        
        # Ensure learning data directory exists
        self._learning_dir = settings.DATA_DIR / "learning"
        self._learning_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("ReportLearningService initialized")
    
    @property
    def vector_store(self):
        """Lazy load vector store."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store
    
    @property
    def embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service
    
    # ───────────────────────────────────────────────────────────────────────────
    # DOCUMENT PARSING
    # ───────────────────────────────────────────────────────────────────────────
    
    def parse_document(
        self,
        file_path: str,
        file_type: Optional[str] = None
    ) -> DocumentLayout:
        """
        Parse a document and extract layout.
        
        Args:
            file_path: Path to the document
            file_type: Optional type override ("pdf" or "docx")
            
        Returns:
            DocumentLayout with extracted elements
        """
        path = Path(file_path)
        
        if file_type is None:
            file_type = path.suffix.lower().replace(".", "")
        
        if file_type == "pdf":
            return self._pdf_parser.parse(path)
        elif file_type in ("docx", "doc"):
            if not self._docx_parser.is_available:
                raise RuntimeError("python-docx not installed for DOCX parsing")
            return self._docx_parser.parse(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def extract_structure(
        self,
        layout: DocumentLayout,
        case_type: str = "general",
        title: Optional[str] = None
    ) -> ReportStructure:
        """
        Extract structure from a parsed document layout.
        
        Args:
            layout: Parsed document layout
            case_type: Type of case (for categorization)
            title: Report title (extracted if not provided)
            
        Returns:
            ReportStructure with sections, charts, etc.
        """
        report_id = f"RPT-{uuid.uuid4().hex[:8].upper()}"
        
        # Extract sections from headings
        sections = self._extract_sections_from_layout(layout)
        
        # Count charts
        chart_summary = self._count_charts(layout)
        
        # Extract title if not provided
        if title is None:
            title = self._extract_title(layout)
        
        # Calculate totals
        total_words = sum(
            len(elem.content.split()) if elem.content else 0
            for page in layout.pages
            for elem in page.elements
            if elem.element_type == ElementType.TEXT
        )
        
        return ReportStructure(
            report_id=report_id,
            title=title or "Untitled Report",
            case_type=case_type,
            total_pages=layout.page_count,
            total_words=total_words,
            sections=sections,
            chart_summary=chart_summary,
            metadata={
                "source_format": "pdf" if hasattr(layout, 'source_format') else "unknown",
                "extracted_at": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def _extract_sections_from_layout(self, layout: DocumentLayout) -> List[SectionInfo]:
        """Extract sections from document layout."""
        sections = []
        current_section = None
        section_position = 0
        
        for page_idx, page in enumerate(layout.pages):
            for elem in page.elements:
                if elem.element_type == ElementType.HEADING:
                    # New section detected
                    if current_section:
                        current_section.page_end = page_idx + 1
                        sections.append(current_section)
                    
                    section_position += 1
                    level = self._detect_heading_level(elem)
                    
                    current_section = SectionInfo(
                        section_id=f"SEC-{uuid.uuid4().hex[:6].upper()}",
                        title=elem.content.strip() if elem.content else "Untitled",
                        level=level,
                        position=section_position,
                        page_start=page_idx + 1,
                        page_end=page_idx + 1,
                        word_count=0
                    )
                
                elif elem.element_type == ElementType.TEXT and current_section:
                    current_section.word_count += len(elem.content.split()) if elem.content else 0
                
                elif elem.element_type == ElementType.TABLE and current_section:
                    current_section.has_tables = True
                
                elif elem.element_type == ElementType.IMAGE and current_section:
                    current_section.has_images = True
                    # Check if it's a chart (heuristic)
                    if self._is_chart_image(elem):
                        current_section.has_charts = True
                        chart_type = self._detect_chart_type(elem)
                        if chart_type:
                            current_section.chart_types.append(chart_type)
        
        # Don't forget the last section
        if current_section:
            current_section.page_end = layout.page_count
            sections.append(current_section)
        
        return sections
    
    def _detect_heading_level(self, elem) -> int:
        """Detect heading level based on font size and style."""
        if elem.style and elem.style.font_size:
            size = elem.style.font_size
            if size >= 18:
                return 1
            elif size >= 14:
                return 2
            elif size >= 12:
                return 3
            else:
                return 4
        return 2  # Default to H2
    
    def _is_chart_image(self, elem) -> bool:
        """Heuristic to detect if an image is a chart."""
        # Check metadata or alt text for chart indicators
        if elem.metadata:
            desc = elem.metadata.get("description", "").lower()
            if any(word in desc for word in ["chart", "graph", "plot", "diagram", "timeline"]):
                return True
        return False
    
    def _detect_chart_type(self, elem) -> Optional[str]:
        """Try to detect chart type from metadata."""
        if elem.metadata:
            desc = elem.metadata.get("description", "").lower()
            chart_types = {
                "bar": "bar_chart",
                "pie": "pie_chart",
                "line": "line_chart",
                "scatter": "scatter_plot",
                "timeline": "timeline",
                "sankey": "sankey",
                "heatmap": "heatmap",
                "area": "area_chart",
                "gauge": "gauge"
            }
            for keyword, chart_type in chart_types.items():
                if keyword in desc:
                    return chart_type
        return "unknown_chart"
    
    def _count_charts(self, layout: DocumentLayout) -> Dict[str, int]:
        """Count charts by type in document."""
        chart_counts: Dict[str, int] = {}
        
        for page in layout.pages:
            for elem in page.elements:
                if elem.element_type == ElementType.IMAGE and self._is_chart_image(elem):
                    chart_type = self._detect_chart_type(elem) or "unknown"
                    chart_counts[chart_type] = chart_counts.get(chart_type, 0) + 1
        
        return chart_counts
    
    def _extract_title(self, layout: DocumentLayout) -> str:
        """Extract report title from first page."""
        if layout.pages:
            first_page = layout.pages[0]
            # Find the first large heading
            for elem in first_page.elements:
                if elem.element_type == ElementType.HEADING:
                    if elem.style and elem.style.font_size and elem.style.font_size >= 16:
                        return elem.content.strip() if elem.content else ""
        return "Untitled Report"
    
    # ───────────────────────────────────────────────────────────────────────────
    # LEARNING STORAGE (VECTOR DB)
    # ───────────────────────────────────────────────────────────────────────────
    
    def store_learned_structure(self, structure: ReportStructure) -> str:
        """
        Store a learned report structure in vector database.
        
        Args:
            structure: Extracted report structure
            
        Returns:
            Document ID in vector store
        """
        # Generate embedding from structure summary
        embedding_text = structure.to_embedding_text()
        embedding = self.embedding_service.embed(embedding_text)
        
        # ChromaDB rejects empty list metadata values, so include chart_types only when present.
        metadata = {
            "case_type": structure.case_type,
            "total_pages": structure.total_pages,
            "total_words": structure.total_words,
            "section_count": len(structure.sections),
            "has_charts": len(structure.chart_summary) > 0,
            "learned_at": structure.learned_at.isoformat(),
            "full_structure": json.dumps(structure.to_dict())
        }
        chart_types = list(structure.chart_summary.keys())
        if chart_types:
            metadata["chart_types"] = chart_types

        # Create vector document
        doc = VectorDocument(
            id=structure.report_id,
            content=embedding_text,
            embedding=embedding,
            metadata=metadata
        )
        
        # Store in vector database
        collection_name = LearningCollection.REPORT_STRUCTURES.value
        self.vector_store.add_documents(
            collection_name=collection_name,
            documents=[doc]
        )
        
        # Also store individual sections for fine-grained matching
        self._store_section_patterns(structure)
        
        logger.info(f"Stored learned structure: {structure.report_id} ({structure.case_type})")
        
        return structure.report_id
    
    def _store_section_patterns(self, structure: ReportStructure) -> None:
        """Store individual section patterns for matching."""
        section_docs = []
        
        for section in structure.sections:
            # Create embedding text for this section
            section_text = f"Section: {section.title}. Level: {section.level}. Words: {section.word_count}. Has charts: {section.has_charts}. Has tables: {section.has_tables}."
            embedding = self.embedding_service.embed(section_text)
            
            section_metadata = {
                "report_id": structure.report_id,
                "case_type": structure.case_type,
                "title": section.title,
                "level": section.level,
                "position": section.position,
                "word_count": section.word_count,
                "has_charts": section.has_charts,
                "has_tables": section.has_tables,
            }
            if section.chart_types:
                section_metadata["chart_types"] = section.chart_types

            doc = VectorDocument(
                id=section.section_id,
                content=section_text,
                embedding=embedding,
                metadata=section_metadata
            )
            section_docs.append(doc)
        
        if section_docs:
            self.vector_store.add_documents(
                collection_name=LearningCollection.SECTION_PATTERNS.value,
                documents=section_docs
            )
    
    # ───────────────────────────────────────────────────────────────────────────
    # STRUCTURE RECOMMENDATION
    # ───────────────────────────────────────────────────────────────────────────
    
    def recommend_structure(
        self,
        case_type: str,
        scenario_description: str,
        evidence_volume: Optional[Dict[str, int]] = None,
        n_similar: int = 5
    ) -> StructureRecommendation:
        """
        Recommend a report structure based on learned patterns.
        
        Args:
            case_type: Type of case (ransomware, data_exfiltration, etc.)
            scenario_description: Text description of the scenario
            evidence_volume: Optional dict of evidence type -> count
            n_similar: Number of similar reports to consider
            
        Returns:
            StructureRecommendation with suggested sections
        """
        # Build query for similarity search
        query_text = f"Case type: {case_type}. Scenario: {scenario_description}"
        
        # Search for similar report structures
        similar_results = self.vector_store.search(
            collection_name=LearningCollection.REPORT_STRUCTURES.value,
            query=query_text,
            n_results=n_similar,
            where={"case_type": case_type} if case_type != "general" else None
        )
        
        if not similar_results:
            # No learned patterns, return default structure
            return self._get_default_structure(case_type, evidence_volume)
        
        # Aggregate patterns from similar reports
        aggregated_sections = self._aggregate_section_patterns(similar_results)
        
        # Estimate pages based on similar reports
        avg_pages = sum(
            r.metadata.get("total_pages", 30) 
            for r in similar_results
        ) // len(similar_results)
        
        # Suggest charts based on patterns
        chart_suggestions = self._suggest_charts(similar_results, aggregated_sections)
        
        # Calculate confidence based on similarity scores
        avg_score = sum(r.score for r in similar_results) / len(similar_results)
        confidence = min(avg_score, 1.0)
        
        return StructureRecommendation(
            recommended_sections=aggregated_sections,
            estimated_pages=avg_pages,
            chart_suggestions=chart_suggestions,
            similar_reports=[r.id for r in similar_results],
            confidence=confidence,
            reasoning=f"Based on {len(similar_results)} similar {case_type} reports with average {avg_pages} pages."
        )
    
    def _aggregate_section_patterns(
        self,
        similar_results: List
    ) -> List[Dict[str, Any]]:
        """Aggregate section patterns from similar reports."""
        section_counts: Dict[str, Dict[str, Any]] = {}
        
        for result in similar_results:
            full_structure = result.metadata.get("full_structure")
            if full_structure:
                structure_dict = json.loads(full_structure)
                for section in structure_dict.get("sections", []):
                    title = section["title"]
                    if title not in section_counts:
                        section_counts[title] = {
                            "title": title,
                            "level": section.get("level", 2),
                            "avg_position": 0,
                            "avg_word_count": 0,
                            "has_charts_pct": 0,
                            "has_tables_pct": 0,
                            "occurrences": 0
                        }
                    
                    sc = section_counts[title]
                    sc["occurrences"] += 1
                    sc["avg_position"] += section.get("position", 0)
                    sc["avg_word_count"] += section.get("word_count", 0)
                    if section.get("has_charts"):
                        sc["has_charts_pct"] += 1
                    if section.get("has_tables"):
                        sc["has_tables_pct"] += 1
        
        # Calculate averages
        aggregated = []
        for title, data in section_counts.items():
            n = data["occurrences"]
            aggregated.append({
                "title": title,
                "level": data["level"],
                "suggested_position": data["avg_position"] // n,
                "suggested_word_count": data["avg_word_count"] // n,
                "suggest_charts": data["has_charts_pct"] / n > 0.5,
                "suggest_tables": data["has_tables_pct"] / n > 0.5,
                "frequency": n / len(similar_results)
            })
        
        # Sort by position and filter to frequent sections
        aggregated.sort(key=lambda x: x["suggested_position"])
        return [s for s in aggregated if s["frequency"] >= 0.4]
    
    def _suggest_charts(
        self,
        similar_results: List,
        sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Suggest charts based on patterns."""
        chart_usage: Dict[str, int] = {}
        
        for result in similar_results:
            chart_types = result.metadata.get("chart_types", [])
            for ct in chart_types:
                chart_usage[ct] = chart_usage.get(ct, 0) + 1
        
        suggestions = []
        for chart_type, count in sorted(chart_usage.items(), key=lambda x: -x[1]):
            frequency = count / len(similar_results)
            if frequency >= 0.3:
                suggestions.append({
                    "chart_type": chart_type,
                    "frequency": frequency,
                    "suggested_section": self._find_section_for_chart(chart_type, sections),
                    "description": self._get_chart_description(chart_type)
                })
        
        return suggestions
    
    def _find_section_for_chart(
        self,
        chart_type: str,
        sections: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Find best section for a chart type."""
        chart_section_mapping = {
            "timeline": ["Timeline", "Chronology", "Events"],
            "bar_chart": ["Summary", "Statistics", "Overview"],
            "pie_chart": ["Distribution", "Breakdown", "Categories"],
            "sankey": ["Data Flow", "Transfer", "Network"],
            "heatmap": ["Analysis", "Correlation", "Patterns"],
            "scatter_plot": ["Anomaly", "Detection", "Outliers"]
        }
        
        keywords = chart_section_mapping.get(chart_type, [])
        for section in sections:
            for keyword in keywords:
                if keyword.lower() in section["title"].lower():
                    return section["title"]
        
        return None
    
    def _get_chart_description(self, chart_type: str) -> str:
        """Get description for chart type."""
        descriptions = {
            "timeline": "Chronological visualization of events",
            "bar_chart": "Comparison of quantities across categories",
            "pie_chart": "Proportional distribution of categories",
            "line_chart": "Trends over time",
            "scatter_plot": "Relationship between two variables",
            "sankey": "Flow of data between entities",
            "heatmap": "Density or correlation matrix",
            "area_chart": "Cumulative values over time",
            "gauge": "Single metric against a target"
        }
        return descriptions.get(chart_type, "Visual representation of data")
    
    def _get_default_structure(
        self,
        case_type: str,
        evidence_volume: Optional[Dict[str, int]] = None
    ) -> StructureRecommendation:
        """Return default structure when no learned patterns exist."""
        # Default forensic report structure
        default_sections = [
            {"title": "Executive Summary", "level": 1, "suggested_position": 1, "suggest_charts": False},
            {"title": "Case Background", "level": 1, "suggested_position": 2, "suggest_charts": False},
            {"title": "Methodology", "level": 1, "suggested_position": 3, "suggest_charts": False},
            {"title": "Evidence Analysis", "level": 1, "suggested_position": 4, "suggest_charts": True},
            {"title": "Timeline of Events", "level": 1, "suggested_position": 5, "suggest_charts": True},
            {"title": "Key Findings", "level": 1, "suggested_position": 6, "suggest_charts": True},
            {"title": "Conclusions", "level": 1, "suggested_position": 7, "suggest_charts": False},
            {"title": "Recommendations", "level": 1, "suggested_position": 8, "suggest_charts": False},
            {"title": "Appendices", "level": 1, "suggested_position": 9, "suggest_charts": False},
        ]
        
        # Estimate pages based on evidence volume
        base_pages = 25
        if evidence_volume:
            total_evidence = sum(evidence_volume.values())
            base_pages += min(total_evidence // 100, 20)  # Add pages for evidence
        
        return StructureRecommendation(
            recommended_sections=default_sections,
            estimated_pages=base_pages,
            chart_suggestions=[
                {"chart_type": "timeline", "suggested_section": "Timeline of Events"},
                {"chart_type": "bar_chart", "suggested_section": "Evidence Analysis"},
            ],
            similar_reports=[],
            confidence=0.3,
            reasoning="Default forensic report structure (no learned patterns available yet)."
        )
    
    # ───────────────────────────────────────────────────────────────────────────
    # FEEDBACK & LEARNING
    # ───────────────────────────────────────────────────────────────────────────
    
    def submit_feedback(
        self,
        report_id: str,
        case_id: str,
        rating: int,
        structure_feedback: str = "good",
        specific_issues: Optional[List[str]] = None,
        suggestions: str = ""
    ) -> str:
        """
        Submit feedback on a generated report for learning.
        
        Args:
            report_id: ID of the report
            case_id: ID of the case
            rating: 1-5 star rating
            structure_feedback: "good", "too_long", "too_short", "missing_sections"
            specific_issues: List of specific issues
            suggestions: Free text suggestions
            
        Returns:
            Feedback ID
        """
        feedback_id = f"FB-{uuid.uuid4().hex[:8].upper()}"
        
        feedback = LearningFeedback(
            feedback_id=feedback_id,
            report_id=report_id,
            case_id=case_id,
            rating=rating,
            structure_feedback=structure_feedback,
            specific_issues=specific_issues or [],
            suggestions=suggestions
        )
        
        # Store feedback
        feedback_text = f"Report feedback: rating {rating}/5, structure: {structure_feedback}, issues: {', '.join(specific_issues or [])}"
        embedding = self.embedding_service.embed(feedback_text)
        
        doc = VectorDocument(
            id=feedback_id,
            content=feedback_text,
            embedding=embedding,
            metadata={
                "report_id": report_id,
                "case_id": case_id,
                "rating": rating,
                "structure_feedback": structure_feedback,
                "specific_issues": specific_issues or [],
                "suggestions": suggestions,
                "created_at": feedback.created_at.isoformat()
            }
        )
        
        self.vector_store.add_documents(
            collection_name=LearningCollection.FEEDBACK.value,
            documents=[doc]
        )
        
        # Update the source report's quality rating if it exists
        self._update_quality_rating(report_id, rating)
        
        logger.info(f"Stored feedback {feedback_id} for report {report_id}: {rating}/5")
        
        return feedback_id
    
    def _update_quality_rating(self, report_id: str, new_rating: int) -> None:
        """Update quality rating for a learned report."""
        # This would update the metadata in vector store
        # For now, log the update
        logger.info(f"Quality rating update for {report_id}: {new_rating}/5")
    
    # ───────────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ───────────────────────────────────────────────────────────────────────────
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learned patterns."""
        try:
            structures_count = self.vector_store.count(
                LearningCollection.REPORT_STRUCTURES.value
            )
            sections_count = self.vector_store.count(
                LearningCollection.SECTION_PATTERNS.value
            )
            feedback_count = self.vector_store.count(
                LearningCollection.FEEDBACK.value
            )
        except Exception:
            structures_count = 0
            sections_count = 0
            feedback_count = 0
        
        return {
            "learned_reports": structures_count,
            "learned_sections": sections_count,
            "feedback_entries": feedback_count,
            "learning_active": structures_count > 0
        }
    
    def list_learned_reports(
        self,
        case_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List learned report structures."""
        try:
            results = self.vector_store.get_all(
                collection_name=LearningCollection.REPORT_STRUCTURES.value,
                where={"case_type": case_type} if case_type else None,
                limit=limit
            )
            
            return [
                {
                    "report_id": r.id,
                    "case_type": r.metadata.get("case_type"),
                    "total_pages": r.metadata.get("total_pages"),
                    "section_count": r.metadata.get("section_count"),
                    "learned_at": r.metadata.get("learned_at")
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Error listing learned reports: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_learning_service: Optional[ReportLearningService] = None


def get_report_learning_service() -> ReportLearningService:
    """Get the singleton ReportLearningService instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = ReportLearningService()
    return _learning_service
