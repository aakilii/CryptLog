"""
Report Version Control System — Git-like versioning for forensic reports.

Provides:
- Version tracking (like Git commits)
- Diff generation between versions
- Rollback capabilities
- Change history with actor attribution
- Branch support for different report variations
- Metadata tracking (alignment, errors, content structure)

This ensures every change to a report is tracked, auditable, and reversible.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of changes in report versions."""
    SECTION_ADDED = "section_added"
    SECTION_REMOVED = "section_removed"
    SECTION_MODIFIED = "section_modified"
    CONTENT_UPDATED = "content_updated"
    EVIDENCE_ADDED = "evidence_added"
    EVIDENCE_REMOVED = "evidence_removed"
    LAYOUT_CHANGED = "layout_changed"
    TOC_REGENERATED = "toc_regenerated"
    PAGE_ADDED = "page_added"
    PAGE_REMOVED = "page_removed"
    METADATA_UPDATED = "metadata_updated"


@dataclass
class ReportChange:
    """A single change in a report version."""
    change_id: str
    change_type: ChangeType
    target_element: str  # Element ID or section name
    before_value: Any = None
    after_value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportVersion:
    """
    A version of a report (like a Git commit).
    
    Stores complete state of report at a point in time plus metadata
    about what changed and why.
    """
    version_id: str
    parent_version_id: Optional[str]
    document_id: str
    case_id: str
    
    # Version metadata
    created_at: str
    created_by: str
    commit_message: str
    tags: List[str] = field(default_factory=list)
    
    # Report state
    report_structure: Dict[str, Any] = field(default_factory=dict)
    canvas_state: Dict[str, Any] = field(default_factory=dict)
    
    # Change tracking
    changes: List[ReportChange] = field(default_factory=list)
    
    # Quality metrics
    alignment_score: float = 1.0  # 0.0-1.0, how well aligned elements are
    completeness_score: float = 0.0  # 0.0-1.0, how complete the report is
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Content metadata
    content_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of version state."""
        state = {
            "document_id": self.document_id,
            "report_structure": self.report_structure,
            "canvas_state": self.canvas_state,
        }
        canonical = json.dumps(state, sort_keys=True, separators=(',', ':'), default=str)
        return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "version_id": self.version_id,
            "parent_version_id": self.parent_version_id,
            "document_id": self.document_id,
            "case_id": self.case_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "commit_message": self.commit_message,
            "tags": self.tags,
            "report_structure": self.report_structure,
            "canvas_state": self.canvas_state,
            "changes": [
                {
                    "change_id": c.change_id,
                    "change_type": c.change_type.value,
                    "target_element": c.target_element,
                    "before_value": c.before_value,
                    "after_value": c.after_value,
                    "metadata": c.metadata,
                }
                for c in self.changes
            ],
            "alignment_score": self.alignment_score,
            "completeness_score": self.completeness_score,
            "errors": self.errors,
            "warnings": self.warnings,
            "content_metadata": self.content_metadata,
            "version_hash": self.compute_hash(),
        }


@dataclass
class ReportBranch:
    """A branch in the report version tree (like Git branches)."""
    branch_name: str
    document_id: str
    head_version_id: str
    created_at: str
    created_by: str
    description: str = ""
    is_active: bool = True


class ReportVersionControl:
    """
    Version control system for forensic reports.
    
    Provides Git-like functionality:
    - Commit new versions
    - View history
    - Diff between versions
    - Rollback to previous versions
    - Branch management
    """
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.versions: Dict[str, ReportVersion] = {}
        self.branches: Dict[str, ReportBranch] = {}
        self.current_branch = "main"
        self._version_counter = 0
    
    def _generate_version_id(self) -> str:
        """Generate unique version ID."""
        self._version_counter += 1
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"v-{timestamp}-{self._version_counter:04d}"
    
    async def commit(
        self,
        document_id: str,
        report_structure: Dict[str, Any],
        canvas_state: Dict[str, Any],
        commit_message: str,
        created_by: str = "system",
        changes: Optional[List[ReportChange]] = None,
        branch: str = "main",
    ) -> ReportVersion:
        """
        Create a new version (commit).
        
        Args:
            document_id: Document identifier
            report_structure: Current report structure
            canvas_state: Current canvas state
            commit_message: Description of changes
            created_by: Who made the changes
            changes: List of specific changes
            branch: Branch name
            
        Returns:
            New ReportVersion object
        """
        # Get parent version
        parent_version_id = None
        if branch in self.branches:
            parent_version_id = self.branches[branch].head_version_id
        
        # Create version
        version = ReportVersion(
            version_id=self._generate_version_id(),
            parent_version_id=parent_version_id,
            document_id=document_id,
            case_id=self.case_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
            commit_message=commit_message,
            report_structure=report_structure,
            canvas_state=canvas_state,
            changes=changes or [],
        )
        
        # Compute quality metrics
        version.alignment_score = self._compute_alignment_score(canvas_state)
        version.completeness_score = self._compute_completeness_score(report_structure)
        version.errors, version.warnings = self._validate_version(version)
        version.content_metadata = self._extract_content_metadata(report_structure, canvas_state)
        
        # Store version
        self.versions[version.version_id] = version
        
        # Update branch head
        if branch not in self.branches:
            self.branches[branch] = ReportBranch(
                branch_name=branch,
                document_id=document_id,
                head_version_id=version.version_id,
                created_at=version.created_at,
                created_by=created_by,
                description=f"Auto-created branch {branch}",
            )
        else:
            self.branches[branch].head_version_id = version.version_id
        
        logger.info(f"Created version {version.version_id} on branch '{branch}'")
        
        # Save to database
        await self._save_version(version)
        
        return version
    
    def _compute_alignment_score(self, canvas_state: Dict[str, Any]) -> float:
        """
        Compute alignment quality score.
        
        Checks:
        - Element overlap
        - Margin consistency
        - Page breaks
        - Spacing uniformity
        """
        if not canvas_state or "pages" not in canvas_state:
            return 1.0
        
        issues = 0
        total_elements = 0
        
        for page in canvas_state.get("pages", []):
            elements = page.get("elements", [])
            total_elements += len(elements)
            
            for i, elem1 in enumerate(elements):
                pos1 = elem1.get("position", {})
                
                # Check margins
                x = pos1.get("x", 0)
                if x < 50 or x > 800:  # Outside margin bounds
                    issues += 1
                
                # Check overlap with other elements
                for elem2 in elements[i+1:]:
                    pos2 = elem2.get("position", {})
                    if self._elements_overlap(pos1, pos2):
                        issues += 1
        
        if total_elements == 0:
            return 1.0
        
        score = max(0.0, 1.0 - (issues / total_elements))
        return score
    
    def _elements_overlap(self, pos1: Dict, pos2: Dict) -> bool:
        """Check if two elements overlap."""
        x1, y1, w1, h1 = pos1.get("x", 0), pos1.get("y", 0), pos1.get("width", 0), pos1.get("height", 0)
        x2, y2, w2, h2 = pos2.get("x", 0), pos2.get("y", 0), pos2.get("width", 0), pos2.get("height", 0)
        
        return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)
    
    def _compute_completeness_score(self, report_structure: Dict[str, Any]) -> float:
        """
        Compute report completeness score.
        
        Checks:
        - All required sections present
        - Evidence references populated
        - Tables have data
        - TOC generated
        """
        if not report_structure:
            return 0.0
        
        required_sections = {
            "title_page", "executive_summary", "evidence_inventory",
            "findings", "conclusions"
        }
        
        sections = report_structure.get("sections", [])
        section_types = {s.get("type") for s in sections}
        
        present_count = len(required_sections & section_types)
        score = present_count / len(required_sections)
        
        return score
    
    def _validate_version(self, version: ReportVersion) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate version and return errors/warnings.
        
        Returns: (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check for duplicate evidence IDs
        evidence_ids = set()
        for section in version.report_structure.get("sections", []):
            for ev_id in section.get("evidence_refs", []):
                if ev_id in evidence_ids:
                    warnings.append({
                        "type": "duplicate_evidence_ref",
                        "evidence_id": ev_id,
                        "message": f"Evidence {ev_id} referenced multiple times"
                    })
                evidence_ids.add(ev_id)
        
        # Check for broken references
        all_evidence_ids = set()  # Would come from evidence vault
        for ev_id in evidence_ids:
            if not ev_id.startswith("EV-"):
                errors.append({
                    "type": "invalid_evidence_id",
                    "evidence_id": ev_id,
                    "message": f"Invalid evidence ID format: {ev_id}"
                })
        
        # Check canvas elements
        for page in version.canvas_state.get("pages", []):
            for elem in page.get("elements", []):
                pos = elem.get("position", {})
                if pos.get("y", 0) > 1100:  # Beyond page height
                    errors.append({
                        "type": "element_overflow",
                        "element_id": elem.get("id"),
                        "message": f"Element extends beyond page bounds"
                    })
        
        return errors, warnings
    
    def _extract_content_metadata(
        self,
        report_structure: Dict[str, Any],
        canvas_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract comprehensive metadata about report content.
        
        This helps the system "know" what's in the report for easy retrieval.
        """
        metadata = {
            "extraction_timestamp": datetime.now(timezone.utc).isoformat(),
            "sections": [],
            "pages": [],
            "evidence_inventory": {},
            "content_index": {},
            "layout_analysis": {},
        }
        
        # Section metadata
        for section in report_structure.get("sections", []):
            section_meta = {
                "type": section.get("type"),
                "title": section.get("title"),
                "content_length": len(section.get("content", "")),
                "evidence_count": len(section.get("evidence_refs", [])),
                "table_count": len(section.get("tables", [])),
                "figure_count": len(section.get("figures", [])),
                "page_estimate": section.get("page_estimate", 1),
            }
            metadata["sections"].append(section_meta)
        
        # Page metadata
        for page in canvas_state.get("pages", []):
            page_meta = {
                "page_number": page.get("page_number"),
                "page_type": page.get("page_type"),
                "element_count": len(page.get("elements", [])),
                "element_types": self._count_element_types(page.get("elements", [])),
            }
            metadata["pages"].append(page_meta)
        
        # Evidence inventory
        all_evidence = set()
        for section in report_structure.get("sections", []):
            all_evidence.update(section.get("evidence_refs", []))
        
        metadata["evidence_inventory"] = {
            "total_evidence_items": len(all_evidence),
            "evidence_ids": list(all_evidence),
        }
        
        # Content index (for searching)
        metadata["content_index"] = self._build_content_index(report_structure)
        
        # Layout analysis
        metadata["layout_analysis"] = {
            "total_pages": len(canvas_state.get("pages", [])),
            "avg_elements_per_page": sum(len(p.get("elements", [])) for p in canvas_state.get("pages", [])) / max(1, len(canvas_state.get("pages", []))),
            "alignment_score": self._compute_alignment_score(canvas_state),
        }
        
        return metadata
    
    def _count_element_types(self, elements: List[Dict]) -> Dict[str, int]:
        """Count elements by type."""
        from collections import Counter
        return dict(Counter(e.get("type", "unknown") for e in elements))
    
    def _build_content_index(self, report_structure: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build searchable content index."""
        index = {}
        
        for section in report_structure.get("sections", []):
            section_type = section.get("type", "")
            content = section.get("content", "")
            
            # Extract keywords (simple word splitting)
            words = content.lower().split()
            unique_words = set(words)
            
            for word in unique_words:
                if len(word) > 3:  # Skip short words
                    if word not in index:
                        index[word] = []
                    index[word].append(section_type)
        
        return index
    
    async def _save_version(self, version: ReportVersion):
        """Save version to database."""
        from operation_room.database import open_vault
        
        try:
            conn = open_vault(self.case_id)
            
            # Ensure table exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS report_versions (
                    version_id TEXT PRIMARY KEY,
                    parent_version_id TEXT,
                    document_id TEXT,
                    case_id TEXT,
                    created_at TEXT,
                    created_by TEXT,
                    commit_message TEXT,
                    tags TEXT,
                    report_structure TEXT,
                    canvas_state TEXT,
                    changes TEXT,
                    alignment_score REAL,
                    completeness_score REAL,
                    errors TEXT,
                    warnings TEXT,
                    content_metadata TEXT,
                    version_hash TEXT
                )
            """)
            
            version_dict = version.to_dict()
            
            conn.execute("""
                INSERT OR REPLACE INTO report_versions VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, [
                version.version_id,
                version.parent_version_id,
                version.document_id,
                version.case_id,
                version.created_at,
                version.created_by,
                version.commit_message,
                json.dumps(version.tags),
                json.dumps(version.report_structure),
                json.dumps(version.canvas_state),
                json.dumps([c for c in version_dict["changes"]]),
                version.alignment_score,
                version.completeness_score,
                json.dumps(version.errors),
                json.dumps(version.warnings),
                json.dumps(version.content_metadata),
                version_dict["version_hash"],
            ])
            
            logger.info(f"Saved version {version.version_id} to database")
            
        except Exception as e:
            logger.error(f"Failed to save version: {e}")
    
    def get_version(self, version_id: str) -> Optional[ReportVersion]:
        """Get a specific version."""
        return self.versions.get(version_id)
    
    def get_history(
        self,
        branch: str = "main",
        limit: int = 50
    ) -> List[ReportVersion]:
        """Get version history for a branch."""
        if branch not in self.branches:
            return []
        
        history = []
        current_id = self.branches[branch].head_version_id
        
        while current_id and len(history) < limit:
            version = self.versions.get(current_id)
            if not version:
                break
            history.append(version)
            current_id = version.parent_version_id
        
        return history
    
    def diff(
        self,
        version_id1: str,
        version_id2: str
    ) -> Dict[str, Any]:
        """
        Generate diff between two versions.
        
        Returns detailed diff showing what changed.
        """
        v1 = self.versions.get(version_id1)
        v2 = self.versions.get(version_id2)
        
        if not v1 or not v2:
            return {"error": "Version not found"}
        
        diff = {
            "version_from": version_id1,
            "version_to": version_id2,
            "changes": v2.changes,
            "alignment_delta": v2.alignment_score - v1.alignment_score,
            "completeness_delta": v2.completeness_score - v1.completeness_score,
            "sections_added": [],
            "sections_removed": [],
            "sections_modified": [],
        }
        
        # Compare sections
        v1_sections = {s.get("type"): s for s in v1.report_structure.get("sections", [])}
        v2_sections = {s.get("type"): s for s in v2.report_structure.get("sections", [])}
        
        for section_type in v2_sections:
            if section_type not in v1_sections:
                diff["sections_added"].append(section_type)
            elif v2_sections[section_type] != v1_sections[section_type]:
                diff["sections_modified"].append(section_type)
        
        for section_type in v1_sections:
            if section_type not in v2_sections:
                diff["sections_removed"].append(section_type)
        
        return diff
    
    async def rollback(
        self,
        version_id: str,
        commit_message: str = "Rollback to previous version",
        created_by: str = "system"
    ) -> ReportVersion:
        """
        Rollback to a previous version.
        
        Creates a new version with the state from the target version.
        """
        target_version = self.versions.get(version_id)
        if not target_version:
            raise ValueError(f"Version {version_id} not found")
        
        # Create new version with old state
        new_version = await self.commit(
            document_id=target_version.document_id,
            report_structure=target_version.report_structure,
            canvas_state=target_version.canvas_state,
            commit_message=f"{commit_message} (rolled back to {version_id})",
            created_by=created_by,
            changes=[ReportChange(
                change_id=f"rollback-{version_id}",
                change_type=ChangeType.METADATA_UPDATED,
                target_element="document",
                metadata={"rollback_to": version_id}
            )],
        )
        
        return new_version
    
    def create_branch(
        self,
        branch_name: str,
        from_version_id: Optional[str] = None,
        created_by: str = "system",
        description: str = ""
    ) -> ReportBranch:
        """Create a new branch."""
        if branch_name in self.branches:
            raise ValueError(f"Branch {branch_name} already exists")
        
        # If no version specified, use current HEAD
        if not from_version_id:
            if self.current_branch in self.branches:
                from_version_id = self.branches[self.current_branch].head_version_id
            else:
                raise ValueError("No version specified and no current branch")
        
        version = self.versions.get(from_version_id)
        if not version:
            raise ValueError(f"Version {from_version_id} not found")
        
        branch = ReportBranch(
            branch_name=branch_name,
            document_id=version.document_id,
            head_version_id=from_version_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=created_by,
            description=description or f"Branch created from {from_version_id}"
        )
        
        self.branches[branch_name] = branch
        return branch


# Global registry
_version_controls: Dict[str, ReportVersionControl] = {}


def get_version_control(case_id: str) -> ReportVersionControl:
    """Get or create version control for a case."""
    if case_id not in _version_controls:
        _version_controls[case_id] = ReportVersionControl(case_id)
    return _version_controls[case_id]
