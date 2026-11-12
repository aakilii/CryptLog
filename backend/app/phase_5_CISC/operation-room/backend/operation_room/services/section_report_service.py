"""
Section-by-Section Report Generation Service

Generates forensic reports section-by-section with:
1. Key-value replacement for findings references
2. User approval per section before moving on
3. Integration with Report Studio canvas
4. Support for regeneration with different parameters
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

from operation_room.database import open_vault
from operation_room.config import settings
from operation_room.services.llm_provider import get_llm
from operation_room.services.key_placeholder_service import KeyPlaceholderService
from operation_room.services.findings_vault import get_findings_vault

logger = logging.getLogger(__name__)


class SectionType(str, Enum):
    """Types of report sections."""
    EXECUTIVE_SUMMARY = "executive_summary"
    INCIDENT_OVERVIEW = "incident_overview"
    TIMELINE_ANALYSIS = "timeline_analysis"
    FINDINGS = "findings"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    TECHNICAL_DETAILS = "technical_details"
    IMPACT_ASSESSMENT = "impact_assessment"
    ACTOR_ANALYSIS = "actor_analysis"
    RECOMMENDATIONS = "recommendations"
    APPENDIX = "appendix"


class SectionStatus(str, Enum):
    """Status of a report section."""
    PENDING = "pending"
    GENERATING = "generating"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    SKIPPED = "skipped"


@dataclass
class ReportSection:
    """A single section of the report."""
    section_id: str
    section_type: SectionType
    title: str
    order: int
    status: SectionStatus = SectionStatus.PENDING
    content: str = ""
    content_with_keys: str = ""  # Content with key placeholders
    key_references: Dict[str, str] = field(default_factory=dict)  # key -> value mapping
    revision_notes: str = ""
    revision_count: int = 0
    generated_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None


@dataclass
class ReportDraft:
    """A complete report draft with all sections."""
    draft_id: str
    case_id: str
    investigation_id: str
    title: str
    sections: List[ReportSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""


class SectionReportService:
    """
    Service for generating reports section-by-section.
    
    Features:
    - Generate sections using LLM with findings keys
    - User approval per section
    - Regeneration with feedback
    - Key-value replacement system
    - Integration with Report Studio
    """
    
    # Standard section templates
    SECTION_TEMPLATES = {
        SectionType.EXECUTIVE_SUMMARY: {
            "title": "Executive Summary",
            "order": 1,
            "prompt_template": """Generate an executive summary for this forensic investigation.

Investigation Context:
- Case ID: {case_id}
- Scenario: {scenario}
- Timeline: {timeline}
- Key Findings Count: {findings_count}

Key Findings to Reference (use the FINDING KEYS in your response):
{findings_summary}

Requirements:
- 2-3 paragraphs maximum
- Highlight the most critical findings
- Reference findings using their keys like {{key:ANOM_XYZ_001}}
- Keep language professional and factual
- Include confidence level summary

Generate the executive summary:"""
        },
        SectionType.INCIDENT_OVERVIEW: {
            "title": "Incident Overview",
            "order": 2,
            "prompt_template": """Generate an incident overview section.

Investigation Context:
- Scenario: {scenario}
- Incident Type: {incident_type}
- Severity: {severity}
- Actors Involved: {actors}
- Systems Affected: {systems}

Requirements:
- Describe the incident objectively
- Include timeline overview
- Reference findings using their keys
- Maintain investigative neutrality

Generate the incident overview:"""
        },
        SectionType.TIMELINE_ANALYSIS: {
            "title": "Timeline Analysis",
            "order": 3,
            "prompt_template": """Generate a timeline analysis section.

Timeline Data (use FINDING KEYS to reference):
{timeline_findings}

Event Sequence:
{event_sequence}

Requirements:
- Chronological narrative
- Reference specific events using their keys
- Highlight anomalous patterns
- Connect events logically

Generate the timeline analysis:"""
        },
        SectionType.FINDINGS: {
            "title": "Key Findings",
            "order": 4,
            "prompt_template": """Generate the key findings section.

All Findings (organized by module):
{all_findings}

Confidence Scores:
{confidence_summary}

Requirements:
- Group findings by category
- Include evidence references using keys
- State confidence levels for each finding
- Use bullet points for clarity

Generate the key findings section:"""
        },
        SectionType.EVIDENCE_ANALYSIS: {
            "title": "Evidence Analysis",
            "order": 5,
            "prompt_template": """Generate the evidence analysis section.

Evidence Items:
{evidence_items}

Analysis Results:
{analysis_results}

Requirements:
- Detail how evidence supports findings
- Reference specific evidence using keys
- Maintain chain of custody awareness
- Include any gaps or limitations

Generate the evidence analysis:"""
        },
        SectionType.TECHNICAL_DETAILS: {
            "title": "Technical Details",
            "order": 6,
            "prompt_template": """Generate the technical details section.

Technical Findings:
{technical_findings}

System Information:
{system_info}

Requirements:
- Include specific technical indicators
- Reference log sources and artifacts
- Use precise technical language
- Include relevant IOCs

Generate the technical details section:"""
        },
        SectionType.IMPACT_ASSESSMENT: {
            "title": "Impact Assessment",
            "order": 7,
            "prompt_template": """Generate the impact assessment section.

Impact Analysis:
{impact_analysis}

Affected Assets:
{affected_assets}

Requirements:
- Quantify impact where possible
- Assess business impact
- Include data exposure risks
- Reference supporting findings with keys

Generate the impact assessment:"""
        },
        SectionType.ACTOR_ANALYSIS: {
            "title": "Actor Analysis",
            "order": 8,
            "prompt_template": """Generate the actor analysis section.

Actor Information:
{actor_info}

Attribution Analysis:
{attribution}

Requirements:
- Profile identified actors
- Analyze behavior patterns
- Assess intent and capability
- Reference evidence using keys

Generate the actor analysis:"""
        },
        SectionType.RECOMMENDATIONS: {
            "title": "Recommendations",
            "order": 9,
            "prompt_template": """Generate the recommendations section.

Investigation Summary:
{investigation_summary}

Key Findings:
{key_findings}

Requirements:
- Prioritized actionable recommendations
- Short-term and long-term actions
- Reference findings that support each recommendation
- Include remediation steps

Generate the recommendations:"""
        },
        SectionType.APPENDIX: {
            "title": "Appendix",
            "order": 10,
            "prompt_template": """Generate the appendix section.

Supporting Data:
{supporting_data}

Evidence Inventory:
{evidence_inventory}

Requirements:
- List all evidence items with keys
- Include methodology notes
- Add any technical appendices
- Reference source documents

Generate the appendix:"""
        }
    }
    
    def __init__(self, case_id: str, investigation_id: str):
        self.case_id = case_id
        self.investigation_id = investigation_id
        self.vault = get_findings_vault(case_id)
        self.key_service = KeyPlaceholderService(case_id)
        self.current_draft: Optional[ReportDraft] = None
        self.llm_provider = "gemini"
        
    def initialize_draft(
        self, 
        title: str,
        section_types: Optional[List[SectionType]] = None,
        metadata: Optional[Dict] = None
    ) -> ReportDraft:
        """
        Initialize a new report draft with specified sections.
        
        Args:
            title: Report title
            section_types: Which sections to include (default: all)
            metadata: Additional metadata (scenario, timeline, etc.)
        """
        if section_types is None:
            section_types = list(SectionType)
        
        sections = []
        for st in section_types:
            template = self.SECTION_TEMPLATES[st]
            section = ReportSection(
                section_id=f"{st.value}_{uuid.uuid4().hex[:8]}",
                section_type=st,
                title=template["title"],
                order=template["order"],
                status=SectionStatus.PENDING
            )
            sections.append(section)
        
        # Sort by order
        sections.sort(key=lambda s: s.order)
        
        draft = ReportDraft(
            draft_id=f"draft_{uuid.uuid4().hex[:12]}",
            case_id=self.case_id,
            investigation_id=self.investigation_id,
            title=title,
            sections=sections,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.current_draft = draft
        self._save_draft(draft)
        
        logger.info(f"Initialized draft {draft.draft_id} with {len(sections)} sections")
        return draft
    
    async def generate_section(
        self,
        section_id: str,
        context: Optional[Dict] = None,
        regenerate: bool = False
    ) -> ReportSection:
        """
        Generate content for a specific section.
        
        Args:
            section_id: ID of section to generate
            context: Additional context for generation
            regenerate: Whether this is a regeneration (uses revision notes)
        """
        if not self.current_draft:
            raise ValueError("No active draft. Call initialize_draft first.")
        
        # Find section
        section = None
        for s in self.current_draft.sections:
            if s.section_id == section_id:
                section = s
                break
        
        if not section:
            raise ValueError(f"Section {section_id} not found in draft")
        
        # Update status
        section.status = SectionStatus.GENERATING
        
        # Get findings with keys for this section type
        findings_data = self._get_findings_for_section(section.section_type)
        
        # Build prompt
        prompt = self._build_section_prompt(section, findings_data, context, regenerate)
        
        # Generate with LLM
        llm = get_llm(self.llm_provider)
        
        try:
            response = await llm.generate(prompt)
            
            # The response contains key placeholders like {{key:ANOM_XYZ}}
            content_with_keys = response
            
            # Replace keys with values for display
            key_map = self.vault.get_key_value_map(self.investigation_id)
            content_with_values = self.key_service.replace_keys_with_values(
                content_with_keys, 
                key_map
            )
            
            # Extract which keys were referenced
            referenced_keys = self.key_service.extract_keys_from_text(content_with_keys)
            key_references = {k: key_map.get(k, "[unknown]") for k in referenced_keys}
            
            # Update section
            section.content = content_with_values
            section.content_with_keys = content_with_keys
            section.key_references = key_references
            section.status = SectionStatus.AWAITING_APPROVAL
            section.generated_at = datetime.now(timezone.utc).isoformat()
            
            if regenerate:
                section.revision_count += 1
            
            self._save_draft(self.current_draft)
            
            logger.info(f"Generated section {section_id} with {len(referenced_keys)} key references")
            return section
            
        except Exception as e:
            logger.error(f"Failed to generate section {section_id}: {e}")
            section.status = SectionStatus.PENDING
            raise
    
    def approve_section(
        self,
        section_id: str,
        approved_by: str,
        edits: Optional[str] = None
    ) -> ReportSection:
        """
        Approve a section (optionally with manual edits).
        
        Args:
            section_id: Section to approve
            approved_by: Who approved it
            edits: Optional manual edits to the content
        """
        if not self.current_draft:
            raise ValueError("No active draft")
        
        section = self._get_section(section_id)
        
        if edits:
            # User made manual edits - update content
            section.content = edits
            # Re-extract key references
            referenced_keys = self.key_service.extract_keys_from_text(edits)
            key_map = self.vault.get_key_value_map(self.investigation_id)
            section.key_references = {k: key_map.get(k, "[unknown]") for k in referenced_keys}
        
        section.status = SectionStatus.APPROVED
        section.approved_at = datetime.now(timezone.utc).isoformat()
        section.approved_by = approved_by
        
        self._save_draft(self.current_draft)
        
        logger.info(f"Section {section_id} approved by {approved_by}")
        return section
    
    def request_revision(
        self,
        section_id: str,
        revision_notes: str
    ) -> ReportSection:
        """
        Request revision of a section with feedback.
        """
        if not self.current_draft:
            raise ValueError("No active draft")
        
        section = self._get_section(section_id)
        section.status = SectionStatus.NEEDS_REVISION
        section.revision_notes = revision_notes
        
        self._save_draft(self.current_draft)
        
        logger.info(f"Revision requested for section {section_id}: {revision_notes[:50]}...")
        return section
    
    def skip_section(self, section_id: str) -> ReportSection:
        """Skip a section (won't be included in final report)."""
        if not self.current_draft:
            raise ValueError("No active draft")
        
        section = self._get_section(section_id)
        section.status = SectionStatus.SKIPPED
        
        self._save_draft(self.current_draft)
        return section
    
    def get_next_pending_section(self) -> Optional[ReportSection]:
        """Get the next section that needs generation."""
        if not self.current_draft:
            return None
        
        for section in self.current_draft.sections:
            if section.status in [SectionStatus.PENDING, SectionStatus.NEEDS_REVISION]:
                return section
        
        return None
    
    def get_draft_progress(self) -> Dict:
        """Get current draft progress summary."""
        if not self.current_draft:
            return {"status": "no_draft"}
        
        total = len(self.current_draft.sections)
        by_status = {}
        for section in self.current_draft.sections:
            status = section.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        approved = by_status.get("approved", 0)
        skipped = by_status.get("skipped", 0)
        progress = (approved + skipped) / total * 100 if total > 0 else 0
        
        return {
            "draft_id": self.current_draft.draft_id,
            "title": self.current_draft.title,
            "total_sections": total,
            "by_status": by_status,
            "progress_percent": round(progress, 1),
            "is_complete": progress == 100,
            "next_section": self.get_next_pending_section()
        }
    
    def export_to_studio(self) -> Dict:
        """
        Export approved draft to Report Studio canvas format.
        
        Returns canvas AST compatible with TipTap editor.
        """
        if not self.current_draft:
            raise ValueError("No active draft")
        
        # Build TipTap document structure
        doc_content = []
        
        # Title
        doc_content.append({
            "type": "heading",
            "attrs": {"level": 1},
            "content": [{"type": "text", "text": self.current_draft.title}]
        })
        
        # Metadata paragraph
        meta_text = f"Case ID: {self.case_id} | Investigation: {self.investigation_id} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        doc_content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": meta_text, "marks": [{"type": "italic"}]}]
        })
        
        doc_content.append({"type": "horizontalRule"})
        
        # Add each approved section
        for section in self.current_draft.sections:
            if section.status != SectionStatus.APPROVED:
                continue
            
            # Section heading
            doc_content.append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": section.title}]
            })
            
            # Section content - generate HTML with hover keys
            if section.key_references:
                html_content = self.key_service.generate_html_with_hover_keys(
                    section.content,
                    section.key_references
                )
                doc_content.append({
                    "type": "keyedContent",
                    "attrs": {"keyMap": section.key_references},
                    "content": [{"type": "text", "text": section.content}]
                })
            else:
                # Plain paragraphs
                for para in section.content.split("\n\n"):
                    if para.strip():
                        doc_content.append({
                            "type": "paragraph",
                            "content": [{"type": "text", "text": para.strip()}]
                        })
            
            doc_content.append({"type": "paragraph"})  # Spacing
        
        # Create document
        document = {
            "type": "doc",
            "content": doc_content
        }
        
        return {
            "draft_id": self.current_draft.draft_id,
            "canvas": document,
            "key_map": self._get_all_key_references(),
            "exported_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_section(self, section_id: str) -> ReportSection:
        """Get section by ID, raise if not found."""
        for s in self.current_draft.sections:
            if s.section_id == section_id:
                return s
        raise ValueError(f"Section {section_id} not found")
    
    def _get_findings_for_section(self, section_type: SectionType) -> Dict:
        """Get relevant findings for a section type."""
        all_findings = self.vault.get_all_findings(self.investigation_id)
        
        # Organize findings by type
        findings_by_type = {}
        for f in all_findings:
            ftype = f.get("finding_type", "other")
            if ftype not in findings_by_type:
                findings_by_type[ftype] = []
            findings_by_type[ftype].append(f)
        
        # Format for prompt - include keys
        formatted = []
        for ftype, findings in findings_by_type.items():
            formatted.append(f"\n## {ftype.upper()}")
            for f in findings:
                key = f.get("finding_key", "unknown")
                value_summary = str(f.get("finding_value", ""))[:200]
                formatted.append(f"- Key: {{{{key:{key}}}}} = {value_summary}")
        
        return {
            "all_findings": "\n".join(formatted),
            "findings_count": len(all_findings),
            "findings_by_type": findings_by_type
        }
    
    def _build_section_prompt(
        self,
        section: ReportSection,
        findings_data: Dict,
        context: Optional[Dict],
        regenerate: bool
    ) -> str:
        """Build the LLM prompt for section generation."""
        template = self.SECTION_TEMPLATES[section.section_type]["prompt_template"]
        
        # Merge context
        full_context = {
            "case_id": self.case_id,
            "investigation_id": self.investigation_id,
            **findings_data,
            **(self.current_draft.metadata or {}),
            **(context or {})
        }
        
        # Fill in what we can
        prompt = template
        for key, value in full_context.items():
            placeholder = "{" + key + "}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))
        
        # Add revision instructions if regenerating
        if regenerate and section.revision_notes:
            prompt += f"\n\nPREVIOUS FEEDBACK (incorporate this):\n{section.revision_notes}"
            prompt += f"\n\nPREVIOUS CONTENT (improve upon this):\n{section.content[:500]}..."
        
        return prompt
    
    def _get_all_key_references(self) -> Dict[str, str]:
        """Get all key references from all sections."""
        all_refs = {}
        for section in self.current_draft.sections:
            all_refs.update(section.key_references)
        return all_refs
    
    def _save_draft(self, draft: ReportDraft):
        """Save draft to vault using canonical report_drafts schema."""
        draft.updated_at = datetime.now(timezone.utc).isoformat()
        
        with open_vault(self.case_id) as conn:
            # Prepare sections JSON (canonical format)
            sections_json = json.dumps([
                {
                    "section_id": s.section_id,
                    "section_type": s.section_type.value,
                    "title": s.title,
                    "order": s.order,
                    "status": s.status.value,
                    "content": s.content,
                    "content_with_keys": s.content_with_keys,
                    "key_references": s.key_references,
                    "revision_notes": s.revision_notes,
                    "revision_count": s.revision_count,
                    "generated_at": s.generated_at,
                    "approved_at": s.approved_at,
                    "approved_by": s.approved_by
                }
                for s in draft.sections
            ])
            
            # Prepare metadata JSON (includes investigation_id)
            metadata = draft.metadata.copy()
            metadata["investigation_id"] = draft.investigation_id
            metadata["created_at"] = draft.created_at
            metadata_json = json.dumps(metadata)
            
            # Use canonical schema columns: report_id, case_id, template, title, status, sections_json, metadata_json
            conn.execute("""
                INSERT INTO report_drafts 
                (report_id, case_id, template, title, status, sections_json, metadata_json, updated_at)
                VALUES (?, ?, 'section_based', ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    status = EXCLUDED.status,
                    sections_json = EXCLUDED.sections_json,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = EXCLUDED.updated_at
            """, (
                draft.draft_id,  # maps to report_id
                draft.case_id,
                draft.title,
                draft.status,
                sections_json,
                metadata_json,
                draft.updated_at
            ))
    
    def load_draft(self, draft_id: str) -> Optional[ReportDraft]:
        """Load an existing draft from canonical report_drafts schema."""
        with open_vault(self.case_id) as conn:
            conn.execute("""
                SELECT report_id, case_id, title, status, sections_json, metadata_json, created_at, updated_at
                FROM report_drafts 
                WHERE report_id = ? AND case_id = ?
            """, (draft_id, self.case_id))
            row = conn.fetchone()
            
            if not row:
                return None
            
            report_id, case_id, title, status, sections_json, metadata_json, created_at, updated_at = row
            
            # Parse JSON fields
            sections_data = json.loads(sections_json) if sections_json else []
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            # Reconstruct draft (investigation_id stored in metadata)
            investigation_id = metadata.pop("investigation_id", self.investigation_id or "")
            created_at_str = metadata.pop("created_at", str(created_at) if created_at else "")
            
            draft = ReportDraft(
                draft_id=report_id,
                case_id=case_id,
                investigation_id=investigation_id,
                title=title or "",
                metadata=metadata,
                status=status or "draft",
                created_at=created_at_str,
                updated_at=str(updated_at) if updated_at else ""
            )
            
            # Update service-level investigation_id if loaded from draft
            if investigation_id and not self.investigation_id:
                self.investigation_id = investigation_id
            
            # Reconstruct sections
            for s_data in sections_data:
                section = ReportSection(
                    section_id=s_data["section_id"],
                    section_type=SectionType(s_data["section_type"]),
                    title=s_data["title"],
                    order=s_data["order"],
                    status=SectionStatus(s_data["status"]),
                    content=s_data.get("content", ""),
                    content_with_keys=s_data.get("content_with_keys", ""),
                    key_references=s_data.get("key_references", {}),
                    revision_notes=s_data.get("revision_notes", ""),
                    revision_count=s_data.get("revision_count", 0),
                    generated_at=s_data.get("generated_at"),
                    approved_at=s_data.get("approved_at"),
                    approved_by=s_data.get("approved_by")
                )
                draft.sections.append(section)
            
            draft.sections.sort(key=lambda s: s.order)
            self.current_draft = draft
            return draft


def get_section_report_service(case_id: str, investigation_id: str) -> SectionReportService:
    """Factory function to get section report service."""
    return SectionReportService(case_id, investigation_id)
