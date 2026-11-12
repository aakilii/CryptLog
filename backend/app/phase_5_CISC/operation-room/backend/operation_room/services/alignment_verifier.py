"""
Alignment Verification Service - Intelligent Report Generation Phase 6.

Verifies and auto-fixes report section alignment:
- Position tracking for all elements
- Overlap detection
- Spacing verification
- Auto-fix for common issues
- Human approval workflow support
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from operation_room.config import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ElementType(str, Enum):
    """Types of elements in a report."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CHART = "chart"
    TABLE = "table"
    IMAGE = "image"
    LIST = "list"
    SPACER = "spacer"


class VerificationStatus(str, Enum):
    """Status of verification check."""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    FIXED = "fixed"


class IssueType(str, Enum):
    """Types of alignment issues."""
    OVERLAP = "overlap"
    INSUFFICIENT_SPACING = "insufficient_spacing"
    EXCESSIVE_SPACING = "excessive_spacing"
    OVERFLOW = "overflow"
    ORPHAN = "orphan"            # Single line at bottom of page
    WIDOW = "widow"             # Single line at top of page
    MISALIGNED = "misaligned"
    WRONG_ORDER = "wrong_order"


@dataclass
class ElementPosition:
    """Position of an element in the report."""
    element_id: str
    element_type: ElementType
    section_id: str
    
    # Position (in PDF points, origin at top-left)
    x: float
    y: float
    width: float
    height: float
    
    # Page info
    page_number: int
    
    # Content reference
    content_preview: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value,
            "section_id": self.section_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "page_number": self.page_number,
            "content_preview": self.content_preview
        }
    
    @property
    def bottom(self) -> float:
        return self.y + self.height
    
    @property
    def right(self) -> float:
        return self.x + self.width
    
    def overlaps(self, other: "ElementPosition") -> bool:
        """Check if this element overlaps with another."""
        if self.page_number != other.page_number:
            return False
        
        return (
            self.x < other.right and
            self.right > other.x and
            self.y < other.bottom and
            self.bottom > other.y
        )


@dataclass
class AlignmentIssue:
    """An alignment issue detected during verification."""
    issue_id: str
    issue_type: IssueType
    severity: str  # "error", "warning", "info"
    element_ids: List[str]
    description: str
    suggested_fix: str
    auto_fixable: bool = False
    fixed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_type": self.issue_type.value,
            "severity": self.severity,
            "element_ids": self.element_ids,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "auto_fixable": self.auto_fixable,
            "fixed": self.fixed
        }


@dataclass
class VerificationResult:
    """Result of alignment verification."""
    verification_id: str
    section_id: str
    status: VerificationStatus
    
    # Elements verified
    element_count: int
    elements: List[ElementPosition] = field(default_factory=list)
    
    # Issues found
    issues: List[AlignmentIssue] = field(default_factory=list)
    
    # Metrics
    total_height: float = 0
    page_count: int = 1
    
    # Timestamps
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "section_id": self.section_id,
            "status": self.status.value,
            "element_count": self.element_count,
            "elements": [e.to_dict() for e in self.elements],
            "issues": [i.to_dict() for i in self.issues],
            "total_height": self.total_height,
            "page_count": self.page_count,
            "verified_at": self.verified_at.isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ALIGNMENT VERIFIER
# ═══════════════════════════════════════════════════════════════════════════════

class AlignmentVerifier:
    """
    Verifies alignment and positioning of report elements.
    
    Checks:
    - No overlapping elements
    - Consistent spacing between elements
    - No orphan/widow lines
    - Elements within page bounds
    - Correct element order
    """
    
    # Standard spacing settings (in points)
    MIN_ELEMENT_SPACING = 10      # Minimum space between elements
    MAX_ELEMENT_SPACING = 50      # Maximum before warning
    HEADING_SPACING_BEFORE = 20   # Space before headings
    HEADING_SPACING_AFTER = 10    # Space after headings
    PARAGRAPH_SPACING = 12        # Space between paragraphs
    CHART_SPACING = 15            # Space around charts
    
    # Page settings
    PAGE_WIDTH = 595.28           # A4 width in points
    PAGE_HEIGHT = 841.89          # A4 height in points
    MARGIN_LEFT = 72              # 1 inch
    MARGIN_RIGHT = 72
    MARGIN_TOP = 72
    MARGIN_BOTTOM = 72
    
    # Content area
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    
    def __init__(self):
        self._verifications: Dict[str, VerificationResult] = {}
        state_dir = settings.DATA_DIR / "deep_research_state"
        state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = state_dir / "alignment_verifications.json"
        self._load_verifications()

    def _load_verifications(self) -> None:
        """Load persisted verification state from disk."""
        if not self._state_file.exists():
            return

        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read alignment verification state: %s", exc)
            return

        raw_verifications = payload.get("verifications") if isinstance(payload, dict) else None
        if not isinstance(raw_verifications, list):
            return

        restored: Dict[str, VerificationResult] = {}
        for item in raw_verifications:
            if not isinstance(item, dict):
                continue
            try:
                verification = self._verification_from_dict(item)
                restored[verification.verification_id] = verification
            except Exception as exc:
                logger.warning("Skipping invalid verification during restore: %s", exc)

        self._verifications = restored

    def _persist_verifications(self) -> None:
        """Persist verification state for restart resilience."""
        try:
            payload = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "verifications": [item.to_dict() for item in self._verifications.values()],
            }
            self._state_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to persist alignment verification state: %s", exc)

    def _verification_from_dict(self, data: Dict[str, Any]) -> VerificationResult:
        """Hydrate VerificationResult from serialized state."""
        def _parse_datetime(value: Optional[str]) -> datetime:
            if not value:
                return datetime.now(timezone.utc)
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.now(timezone.utc)

        raw_status = str(data.get("status", VerificationStatus.WARNING.value))
        try:
            status = VerificationStatus(raw_status)
        except ValueError:
            status = VerificationStatus.WARNING

        elements: List[ElementPosition] = []
        for elem_data in data.get("elements", []):
            if not isinstance(elem_data, dict):
                continue

            raw_type = str(elem_data.get("element_type", ElementType.PARAGRAPH.value))
            try:
                element_type = ElementType(raw_type)
            except ValueError:
                element_type = ElementType.PARAGRAPH

            try:
                element = ElementPosition(
                    element_id=str(elem_data.get("element_id", elem_data.get("id", ""))),
                    element_type=element_type,
                    section_id=str(elem_data.get("section_id", data.get("section_id", ""))),
                    x=float(elem_data.get("x", self.MARGIN_LEFT)),
                    y=float(elem_data.get("y", 0)),
                    width=float(elem_data.get("width", self.CONTENT_WIDTH)),
                    height=float(elem_data.get("height", 20)),
                    page_number=int(elem_data.get("page_number", 1)),
                    content_preview=str(elem_data.get("content_preview", "")),
                )
            except Exception:
                continue

            elements.append(element)

        issues: List[AlignmentIssue] = []
        for issue_data in data.get("issues", []):
            if not isinstance(issue_data, dict):
                continue

            raw_issue_type = str(issue_data.get("issue_type", IssueType.MISALIGNED.value))
            try:
                issue_type = IssueType(raw_issue_type)
            except ValueError:
                issue_type = IssueType.MISALIGNED

            try:
                issue = AlignmentIssue(
                    issue_id=str(issue_data.get("issue_id", "")),
                    issue_type=issue_type,
                    severity=str(issue_data.get("severity", "warning")),
                    element_ids=[str(item) for item in issue_data.get("element_ids", [])],
                    description=str(issue_data.get("description", "")),
                    suggested_fix=str(issue_data.get("suggested_fix", "")),
                    auto_fixable=bool(issue_data.get("auto_fixable", False)),
                    fixed=bool(issue_data.get("fixed", False)),
                )
            except Exception:
                continue

            issues.append(issue)

        return VerificationResult(
            verification_id=str(data.get("verification_id", f"VER-{uuid.uuid4().hex[:6].upper()}")),
            section_id=str(data.get("section_id", "")),
            status=status,
            element_count=int(data.get("element_count", len(elements))),
            elements=elements,
            issues=issues,
            total_height=float(data.get("total_height", 0)),
            page_count=int(data.get("page_count", 1)),
            verified_at=_parse_datetime(data.get("verified_at")),
        )
    
    def verify_section(
        self,
        section_id: str,
        elements: List[Dict[str, Any]]
    ) -> VerificationResult:
        """
        Verify alignment of a section's elements.
        
        Args:
            section_id: ID of the section
            elements: List of element dicts with position info
            
        Returns:
            VerificationResult with any issues found
        """
        verification_id = f"VER-{uuid.uuid4().hex[:6].upper()}"
        
        # Convert to ElementPosition objects
        positions = self._parse_elements(section_id, elements)
        
        # Run verification checks
        issues = []
        
        # Check overlaps
        overlap_issues = self._check_overlaps(positions)
        issues.extend(overlap_issues)
        
        # Check spacing
        spacing_issues = self._check_spacing(positions)
        issues.extend(spacing_issues)
        
        # Check page bounds
        bounds_issues = self._check_bounds(positions)
        issues.extend(bounds_issues)
        
        # Check order
        order_issues = self._check_order(positions)
        issues.extend(order_issues)
        
        # Check orphans/widows (text elements only)
        text_issues = self._check_text_issues(positions)
        issues.extend(text_issues)
        
        # Determine overall status
        if any(i.severity == "error" for i in issues):
            status = VerificationStatus.FAILED
        elif any(i.severity == "warning" for i in issues):
            status = VerificationStatus.WARNING
        else:
            status = VerificationStatus.PASSED
        
        # Calculate metrics
        total_height = max(e.bottom for e in positions) if positions else 0
        page_count = max(e.page_number for e in positions) if positions else 1
        
        result = VerificationResult(
            verification_id=verification_id,
            section_id=section_id,
            status=status,
            element_count=len(positions),
            elements=positions,
            issues=issues,
            total_height=total_height,
            page_count=page_count
        )
        
        self._verifications[verification_id] = result
        self._persist_verifications()
        
        logger.info(f"Verified section {section_id}: {status.value} ({len(issues)} issues)")
        
        return result
    
    def _parse_elements(
        self,
        section_id: str,
        elements: List[Dict[str, Any]]
    ) -> List[ElementPosition]:
        """Parse element dicts into ElementPosition objects."""
        positions = []
        
        for elem in elements:
            try:
                pos = ElementPosition(
                    element_id=elem.get("id", f"EL-{uuid.uuid4().hex[:6]}"),
                    element_type=ElementType(elem.get("type", "paragraph")),
                    section_id=section_id,
                    x=float(elem.get("x", self.MARGIN_LEFT)),
                    y=float(elem.get("y", 0)),
                    width=float(elem.get("width", self.CONTENT_WIDTH)),
                    height=float(elem.get("height", 20)),
                    page_number=int(elem.get("page", 1)),
                    content_preview=str(elem.get("content", ""))[:50]
                )
                positions.append(pos)
            except (ValueError, KeyError) as e:
                logger.warning(f"Could not parse element: {e}")
        
        return positions
    
    def _check_overlaps(self, positions: List[ElementPosition]) -> List[AlignmentIssue]:
        """Check for overlapping elements."""
        issues = []
        
        for i, elem1 in enumerate(positions):
            for elem2 in positions[i + 1:]:
                if elem1.overlaps(elem2):
                    issue = AlignmentIssue(
                        issue_id=f"OVL-{uuid.uuid4().hex[:6]}",
                        issue_type=IssueType.OVERLAP,
                        severity="error",
                        element_ids=[elem1.element_id, elem2.element_id],
                        description=f"Elements overlap on page {elem1.page_number}",
                        suggested_fix="Adjust vertical position of second element",
                        auto_fixable=True
                    )
                    issues.append(issue)
        
        return issues
    
    def _check_spacing(self, positions: List[ElementPosition]) -> List[AlignmentIssue]:
        """Check spacing between elements."""
        issues = []
        
        # Sort by page and y position
        sorted_pos = sorted(positions, key=lambda e: (e.page_number, e.y))
        
        for i in range(len(sorted_pos) - 1):
            elem1 = sorted_pos[i]
            elem2 = sorted_pos[i + 1]
            
            # Only check elements on same page
            if elem1.page_number != elem2.page_number:
                continue
            
            spacing = elem2.y - elem1.bottom
            
            if spacing < self.MIN_ELEMENT_SPACING:
                issue = AlignmentIssue(
                    issue_id=f"SPC-{uuid.uuid4().hex[:6]}",
                    issue_type=IssueType.INSUFFICIENT_SPACING,
                    severity="warning",
                    element_ids=[elem1.element_id, elem2.element_id],
                    description=f"Insufficient spacing ({spacing:.1f}pt) between elements",
                    suggested_fix=f"Increase spacing to at least {self.MIN_ELEMENT_SPACING}pt",
                    auto_fixable=True
                )
                issues.append(issue)
            
            elif spacing > self.MAX_ELEMENT_SPACING:
                issue = AlignmentIssue(
                    issue_id=f"SPC-{uuid.uuid4().hex[:6]}",
                    issue_type=IssueType.EXCESSIVE_SPACING,
                    severity="info",
                    element_ids=[elem1.element_id, elem2.element_id],
                    description=f"Large gap ({spacing:.1f}pt) between elements",
                    suggested_fix="Consider reducing spacing or adding content",
                    auto_fixable=False
                )
                issues.append(issue)
        
        return issues
    
    def _check_bounds(self, positions: List[ElementPosition]) -> List[AlignmentIssue]:
        """Check elements are within page bounds."""
        issues = []
        
        for elem in positions:
            out_of_bounds = []
            
            if elem.x < self.MARGIN_LEFT:
                out_of_bounds.append("left margin")
            if elem.right > self.PAGE_WIDTH - self.MARGIN_RIGHT:
                out_of_bounds.append("right margin")
            
            # Check vertical bounds (relative to page)
            y_on_page = (elem.y % self.PAGE_HEIGHT)
            
            if y_on_page < self.MARGIN_TOP:
                out_of_bounds.append("top margin")
            if y_on_page + elem.height > self.PAGE_HEIGHT - self.MARGIN_BOTTOM:
                out_of_bounds.append("bottom margin")
            
            if out_of_bounds:
                issue = AlignmentIssue(
                    issue_id=f"BND-{uuid.uuid4().hex[:6]}",
                    issue_type=IssueType.OVERFLOW,
                    severity="error",
                    element_ids=[elem.element_id],
                    description=f"Element extends beyond {', '.join(out_of_bounds)}",
                    suggested_fix="Reposition element within margins",
                    auto_fixable=True
                )
                issues.append(issue)
        
        return issues
    
    def _check_order(self, positions: List[ElementPosition]) -> List[AlignmentIssue]:
        """Check elements are in correct order."""
        issues = []
        
        # Sort by expected reading order (page, y, x)
        expected_order = sorted(positions, key=lambda e: (e.page_number, e.y, e.x))
        
        for i, elem in enumerate(positions):
            expected_idx = expected_order.index(elem)
            if i != expected_idx and abs(i - expected_idx) > 2:
                issue = AlignmentIssue(
                    issue_id=f"ORD-{uuid.uuid4().hex[:6]}",
                    issue_type=IssueType.WRONG_ORDER,
                    severity="warning",
                    element_ids=[elem.element_id],
                    description=f"Element may be in wrong reading order",
                    suggested_fix="Verify element sequence matches intended order",
                    auto_fixable=False
                )
                issues.append(issue)
                break  # Only report first order issue
        
        return issues
    
    def _check_text_issues(self, positions: List[ElementPosition]) -> List[AlignmentIssue]:
        """Check for orphan/widow text issues."""
        issues = []
        
        for elem in positions:
            if elem.element_type != ElementType.PARAGRAPH:
                continue
            
            # Estimate lines based on height
            line_height = 14  # Approximate
            lines = int(elem.height / line_height)
            
            # Check for orphan (single line at bottom)
            y_on_page = elem.y % self.PAGE_HEIGHT
            space_to_bottom = self.PAGE_HEIGHT - self.MARGIN_BOTTOM - y_on_page
            
            if lines > 1 and space_to_bottom < line_height * 2:
                issue = AlignmentIssue(
                    issue_id=f"ORP-{uuid.uuid4().hex[:6]}",
                    issue_type=IssueType.ORPHAN,
                    severity="warning",
                    element_ids=[elem.element_id],
                    description="Paragraph may create orphan line at page break",
                    suggested_fix="Adjust paragraph position or reflow text",
                    auto_fixable=True
                )
                issues.append(issue)
        
        return issues
    
    def auto_fix_issues(
        self,
        verification_id: str
    ) -> Tuple[List[Dict[str, Any]], List[AlignmentIssue]]:
        """
        Attempt to auto-fix alignment issues.
        
        Returns:
            Tuple of (position_adjustments, remaining_issues)
        """
        result = self._verifications.get(verification_id)
        if not result:
            return [], []
        
        adjustments = []
        remaining_issues = []
        
        # Build element lookup
        elem_lookup = {e.element_id: e for e in result.elements}
        
        for issue in result.issues:
            if not issue.auto_fixable:
                remaining_issues.append(issue)
                continue
            
            fix_applied = False
            
            if issue.issue_type == IssueType.OVERLAP:
                # Move second element down
                if len(issue.element_ids) >= 2:
                    elem1 = elem_lookup.get(issue.element_ids[0])
                    elem2 = elem_lookup.get(issue.element_ids[1])
                    
                    if elem1 and elem2:
                        new_y = elem1.bottom + self.MIN_ELEMENT_SPACING
                        adjustments.append({
                            "element_id": elem2.element_id,
                            "adjustment": "move",
                            "new_y": new_y,
                            "delta_y": new_y - elem2.y
                        })
                        fix_applied = True
            
            elif issue.issue_type == IssueType.INSUFFICIENT_SPACING:
                # Increase spacing
                if len(issue.element_ids) >= 2:
                    elem1 = elem_lookup.get(issue.element_ids[0])
                    elem2 = elem_lookup.get(issue.element_ids[1])
                    
                    if elem1 and elem2:
                        new_y = elem1.bottom + self.MIN_ELEMENT_SPACING
                        adjustments.append({
                            "element_id": elem2.element_id,
                            "adjustment": "move",
                            "new_y": new_y,
                            "delta_y": new_y - elem2.y
                        })
                        fix_applied = True
            
            elif issue.issue_type == IssueType.OVERFLOW:
                # Reposition within bounds
                elem = elem_lookup.get(issue.element_ids[0])
                if elem:
                    new_x = max(self.MARGIN_LEFT, min(elem.x, self.PAGE_WIDTH - self.MARGIN_RIGHT - elem.width))
                    adjustments.append({
                        "element_id": elem.element_id,
                        "adjustment": "move",
                        "new_x": new_x,
                        "delta_x": new_x - elem.x
                    })
                    fix_applied = True
            
            elif issue.issue_type == IssueType.ORPHAN:
                # Move paragraph to next page
                elem = elem_lookup.get(issue.element_ids[0])
                if elem:
                    next_page_y = (elem.page_number) * self.PAGE_HEIGHT + self.MARGIN_TOP
                    adjustments.append({
                        "element_id": elem.element_id,
                        "adjustment": "page_break",
                        "new_y": next_page_y,
                        "new_page": elem.page_number + 1
                    })
                    fix_applied = True
            
            if fix_applied:
                issue.fixed = True
            else:
                remaining_issues.append(issue)

        self._persist_verifications()
        
        logger.info(f"Auto-fixed {len(adjustments)} issues, {len(remaining_issues)} remaining")
        
        return adjustments, remaining_issues
    
    def get_verification(self, verification_id: str) -> Optional[VerificationResult]:
        """Get a verification result by ID."""
        return self._verifications.get(verification_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESSOR
# ═══════════════════════════════════════════════════════════════════════════════

_alignment_verifier: Optional[AlignmentVerifier] = None


def get_alignment_verifier() -> AlignmentVerifier:
    """Get the singleton AlignmentVerifier instance."""
    global _alignment_verifier
    if _alignment_verifier is None:
        _alignment_verifier = AlignmentVerifier()
    return _alignment_verifier
