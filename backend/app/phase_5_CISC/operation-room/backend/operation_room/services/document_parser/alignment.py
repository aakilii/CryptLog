"""
Alignment Verifier for Document Layout Comparison.

Compares document layouts to:
- Verify alignment with reference documents
- Detect layout deviations
- Auto-align elements to reference
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import math

from .pdf_parser import (
    DocumentLayout,
    PageLayout,
    DocumentElement,
    ElementType,
    BoundingBox,
)


class AlignmentIssueType(str, Enum):
    """Types of alignment issues."""
    POSITION_MISMATCH = "position_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    MISSING_ELEMENT = "missing_element"
    EXTRA_ELEMENT = "extra_element"
    TYPE_MISMATCH = "type_mismatch"
    ORDER_MISMATCH = "order_mismatch"
    MARGIN_VIOLATION = "margin_violation"


@dataclass
class AlignmentIssue:
    """A single alignment issue."""
    issue_type: AlignmentIssueType
    page_number: int
    element_index: Optional[int] = None
    expected: Optional[Dict[str, Any]] = None
    actual: Optional[Dict[str, Any]] = None
    severity: str = "warning"  # info, warning, error
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "issue_type": self.issue_type.value,
            "page_number": self.page_number,
            "element_index": self.element_index,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class AlignmentSuggestion:
    """A suggested correction for an element."""
    element_index: int
    page_number: int
    current_bbox: BoundingBox
    suggested_bbox: BoundingBox
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "element_index": self.element_index,
            "page_number": self.page_number,
            "current": self.current_bbox.to_dict(),
            "suggested": self.suggested_bbox.to_dict(),
            "reason": self.reason,
        }


@dataclass
class AlignmentResult:
    """Result of alignment verification."""
    is_aligned: bool = True
    score: float = 1.0  # 0.0 to 1.0
    issues: List[AlignmentIssue] = field(default_factory=list)
    suggestions: List[AlignmentSuggestion] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_aligned": self.is_aligned,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": [s.to_dict() for s in self.suggestions],
            "issue_counts": self._count_by_type(),
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count issues by type."""
        counts = {}
        for issue in self.issues:
            key = issue.issue_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts


class AlignmentVerifier:
    """
    Verifies and corrects document alignment.
    
    Features:
    - Compare layouts against reference
    - Detect alignment issues
    - Suggest corrections
    - Auto-align elements
    """
    
    # Tolerance for position matching (in points)
    POSITION_TOLERANCE = 5.0
    SIZE_TOLERANCE = 10.0
    
    def __init__(
        self,
        position_tolerance: float = 5.0,
        size_tolerance: float = 10.0,
    ):
        """
        Initialize verifier.
        
        Args:
            position_tolerance: Tolerance for position matching (points)
            size_tolerance: Tolerance for size matching (points)
        """
        self.position_tolerance = position_tolerance
        self.size_tolerance = size_tolerance
    
    def verify(
        self,
        document: DocumentLayout,
        reference: DocumentLayout,
    ) -> AlignmentResult:
        """
        Verify document alignment against reference.
        
        Args:
            document: Document to verify
            reference: Reference document
            
        Returns:
            AlignmentResult with issues and suggestions
        """
        result = AlignmentResult()
        
        # Compare page counts
        if document.page_count != reference.page_count:
            result.issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.EXTRA_ELEMENT if document.page_count > reference.page_count else AlignmentIssueType.MISSING_ELEMENT,
                page_number=0,
                expected={"page_count": reference.page_count},
                actual={"page_count": document.page_count},
                severity="warning",
                message=f"Page count mismatch: expected {reference.page_count}, got {document.page_count}",
            ))
        
        # Compare each page
        for i, (doc_page, ref_page) in enumerate(zip(document.pages, reference.pages)):
            page_issues, page_suggestions = self._compare_pages(doc_page, ref_page)
            result.issues.extend(page_issues)
            result.suggestions.extend(page_suggestions)
        
        # Calculate alignment score
        if result.issues:
            error_count = sum(1 for i in result.issues if i.severity == "error")
            warning_count = sum(1 for i in result.issues if i.severity == "warning")
            total_elements = sum(len(p.elements) for p in reference.pages)
            
            if total_elements > 0:
                result.score = max(0, 1.0 - (error_count * 0.1 + warning_count * 0.05))
            else:
                result.score = 1.0 if not result.issues else 0.5
            
            result.is_aligned = result.score >= 0.9
        
        return result
    
    def _compare_pages(
        self,
        doc_page: PageLayout,
        ref_page: PageLayout,
    ) -> Tuple[List[AlignmentIssue], List[AlignmentSuggestion]]:
        """Compare two pages."""
        issues = []
        suggestions = []
        
        # Check margins
        margin_issues = self._check_margins(doc_page, ref_page)
        issues.extend(margin_issues)
        
        # Compare elements by matching
        matched_doc, matched_ref, unmatched_doc, unmatched_ref = self._match_elements(
            doc_page.elements, ref_page.elements
        )
        
        # Check matched elements
        for doc_elem, ref_elem in zip(matched_doc, matched_ref):
            elem_issues, elem_suggestions = self._compare_elements(
                doc_elem, ref_elem, doc_page.page_number
            )
            issues.extend(elem_issues)
            suggestions.extend(elem_suggestions)
        
        # Report unmatched elements
        for elem in unmatched_doc:
            issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.EXTRA_ELEMENT,
                page_number=doc_page.page_number,
                actual={"type": elem.element_type.value, "content": elem.content[:50]},
                severity="warning",
                message=f"Extra element not in reference: {elem.element_type.value}",
            ))
        
        for elem in unmatched_ref:
            issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.MISSING_ELEMENT,
                page_number=ref_page.page_number,
                expected={"type": elem.element_type.value, "content": elem.content[:50]},
                severity="warning",
                message=f"Missing element from reference: {elem.element_type.value}",
            ))
        
        return issues, suggestions
    
    def _check_margins(
        self,
        doc_page: PageLayout,
        ref_page: PageLayout,
    ) -> List[AlignmentIssue]:
        """Check margin alignment."""
        issues = []
        
        margin_checks = [
            ("top", doc_page.margin_top, ref_page.margin_top),
            ("bottom", doc_page.margin_bottom, ref_page.margin_bottom),
            ("left", doc_page.margin_left, ref_page.margin_left),
            ("right", doc_page.margin_right, ref_page.margin_right),
        ]
        
        for name, doc_val, ref_val in margin_checks:
            if abs(doc_val - ref_val) > self.position_tolerance:
                issues.append(AlignmentIssue(
                    issue_type=AlignmentIssueType.MARGIN_VIOLATION,
                    page_number=doc_page.page_number,
                    expected={f"margin_{name}": ref_val},
                    actual={f"margin_{name}": doc_val},
                    severity="info",
                    message=f"Margin {name} differs: expected {ref_val:.1f}, got {doc_val:.1f}",
                ))
        
        return issues
    
    def _match_elements(
        self,
        doc_elements: List[DocumentElement],
        ref_elements: List[DocumentElement],
    ) -> Tuple[List[DocumentElement], List[DocumentElement], List[DocumentElement], List[DocumentElement]]:
        """Match elements between document and reference."""
        matched_doc = []
        matched_ref = []
        used_ref_indices = set()
        
        # Try to match by type and position
        for doc_elem in doc_elements:
            best_match = None
            best_score = 0
            
            for i, ref_elem in enumerate(ref_elements):
                if i in used_ref_indices:
                    continue
                
                score = self._element_similarity(doc_elem, ref_elem)
                if score > best_score:
                    best_score = score
                    best_match = (i, ref_elem)
            
            if best_match and best_score > 0.5:
                matched_doc.append(doc_elem)
                matched_ref.append(best_match[1])
                used_ref_indices.add(best_match[0])
        
        # Find unmatched
        unmatched_doc = [e for e in doc_elements if e not in matched_doc]
        unmatched_ref = [e for i, e in enumerate(ref_elements) if i not in used_ref_indices]
        
        return matched_doc, matched_ref, unmatched_doc, unmatched_ref
    
    def _element_similarity(
        self,
        elem1: DocumentElement,
        elem2: DocumentElement,
    ) -> float:
        """Calculate similarity between two elements (0-1)."""
        score = 0.0
        
        # Type match
        if elem1.element_type == elem2.element_type:
            score += 0.4
        
        # Position proximity
        dist = self._bbox_distance(elem1.bbox, elem2.bbox)
        if dist < self.position_tolerance:
            score += 0.3
        elif dist < self.position_tolerance * 5:
            score += 0.15
        
        # Content similarity (simple overlap)
        content1 = elem1.content.lower()[:100]
        content2 = elem2.content.lower()[:100]
        if content1 and content2:
            common_words = set(content1.split()) & set(content2.split())
            all_words = set(content1.split()) | set(content2.split())
            if all_words:
                score += 0.3 * (len(common_words) / len(all_words))
        
        return score
    
    def _bbox_distance(self, bbox1: BoundingBox, bbox2: BoundingBox) -> float:
        """Calculate distance between bbox centers."""
        c1 = bbox1.center
        c2 = bbox2.center
        return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)
    
    def _compare_elements(
        self,
        doc_elem: DocumentElement,
        ref_elem: DocumentElement,
        page_number: int,
    ) -> Tuple[List[AlignmentIssue], List[AlignmentSuggestion]]:
        """Compare two matched elements."""
        issues = []
        suggestions = []
        
        # Check type
        if doc_elem.element_type != ref_elem.element_type:
            issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.TYPE_MISMATCH,
                page_number=page_number,
                expected={"type": ref_elem.element_type.value},
                actual={"type": doc_elem.element_type.value},
                severity="warning",
                message=f"Element type mismatch: expected {ref_elem.element_type.value}",
            ))
        
        # Check position
        pos_diff_x = abs(doc_elem.bbox.x - ref_elem.bbox.x)
        pos_diff_y = abs(doc_elem.bbox.y - ref_elem.bbox.y)
        
        if pos_diff_x > self.position_tolerance or pos_diff_y > self.position_tolerance:
            issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.POSITION_MISMATCH,
                page_number=page_number,
                expected={"x": ref_elem.bbox.x, "y": ref_elem.bbox.y},
                actual={"x": doc_elem.bbox.x, "y": doc_elem.bbox.y},
                severity="info",
                message=f"Position offset: ({pos_diff_x:.1f}, {pos_diff_y:.1f}) points",
            ))
            
            # Suggest correction
            suggestions.append(AlignmentSuggestion(
                element_index=0,  # Would need proper indexing
                page_number=page_number,
                current_bbox=doc_elem.bbox,
                suggested_bbox=ref_elem.bbox,
                reason="Align with reference element",
            ))
        
        # Check size
        size_diff_w = abs(doc_elem.bbox.width - ref_elem.bbox.width)
        size_diff_h = abs(doc_elem.bbox.height - ref_elem.bbox.height)
        
        if size_diff_w > self.size_tolerance or size_diff_h > self.size_tolerance:
            issues.append(AlignmentIssue(
                issue_type=AlignmentIssueType.SIZE_MISMATCH,
                page_number=page_number,
                expected={"width": ref_elem.bbox.width, "height": ref_elem.bbox.height},
                actual={"width": doc_elem.bbox.width, "height": doc_elem.bbox.height},
                severity="info",
                message=f"Size difference: ({size_diff_w:.1f}, {size_diff_h:.1f}) points",
            ))
        
        return issues, suggestions
    
    def auto_align(
        self,
        document: DocumentLayout,
        reference: DocumentLayout,
    ) -> DocumentLayout:
        """
        Auto-align document to reference.
        
        Args:
            document: Document to align
            reference: Reference document
            
        Returns:
            Aligned document copy
        """
        # For now, just apply margin corrections
        # Full implementation would adjust element positions
        
        import copy
        aligned = copy.deepcopy(document)
        
        if reference.pages and aligned.pages:
            ref_page = reference.pages[0]
            for page in aligned.pages:
                page.margin_top = ref_page.margin_top
                page.margin_bottom = ref_page.margin_bottom
                page.margin_left = ref_page.margin_left
                page.margin_right = ref_page.margin_right
        
        return aligned
    
    def get_alignment_grid(
        self,
        reference: DocumentLayout,
    ) -> Dict[str, Any]:
        """
        Extract alignment grid from reference.
        
        Returns common positions that elements align to.
        
        Args:
            reference: Reference document
            
        Returns:
            Alignment grid specification
        """
        x_positions = []
        y_positions = []
        widths = []
        
        for page in reference.pages:
            for elem in page.elements:
                x_positions.append(elem.bbox.x)
                y_positions.append(elem.bbox.y)
                widths.append(elem.bbox.width)
        
        # Find common alignment points
        grid = {
            "margins": {
                "top": reference.pages[0].margin_top if reference.pages else 72,
                "bottom": reference.pages[0].margin_bottom if reference.pages else 72,
                "left": reference.pages[0].margin_left if reference.pages else 72,
                "right": reference.pages[0].margin_right if reference.pages else 72,
            },
            "x_guides": sorted(set(round(x, 0) for x in x_positions)),
            "y_guides": sorted(set(round(y, 0) for y in y_positions)),
            "common_widths": sorted(set(round(w, 0) for w in widths)),
        }
        
        return grid
