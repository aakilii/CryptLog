"""
ReportLab PDF Service for NFLIP Report Generation.

Core PDF generation engine using ReportLab instead of Playwright.
Provides pixel-perfect rendering with cryptographic integrity.
"""

import io
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import HexColor, Color, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

from operation_room.services.coordinate_mapper import CoordinateMapper, BoundingBox, create_a4_mapper
from operation_room.services.font_manager import FontManager, FontStyles, NFLIPColors, initialize_fonts
from operation_room.services.chart_renderer import get_pdf_chart_renderer, ChartRenderer, CHART_TYPE_MAP
from operation_room.services.widget_renderers import (
    RenderContext, get_widget_renderer, render_widget, WIDGET_RENDERERS
)
from operation_room.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PDFGenerationContext:
    """Context for PDF generation session."""
    case_id: str
    doc_id: str
    focus_mode: str = 'review'  # review, story, evidence, redact
    page_size: str = 'A4'
    title: str = ''
    author: str = 'NFLIP System'
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Hashing for integrity
    element_hashes: List[str] = field(default_factory=list)
    merkle_root: Optional[str] = None


@dataclass
class RenderedElement:
    """Represents a rendered element with its hash."""
    element_id: str
    element_type: str
    content_hash: str
    page_number: int
    bounds: BoundingBox


class ReportLabPDFService:
    """
    PDF generation service using ReportLab.
    
    Converts canvas AST (JSON) to pixel-perfect PDF with:
    - Exact position matching (canvas pixels → PDF points)
    - Embedded fonts for cross-platform consistency
    - Cryptographic content hashing
    - Support for all widget types
    """
    
    def __init__(
        self, 
        case_id: str, 
        doc_id: str, 
        focus_mode: str = 'review',
        page_size: str = 'A4',
        font_style: Optional[str] = None,
        graph_style: Optional[str] = None,
        table_style: Optional[str] = None,
        selected_graphs: Optional[List[str]] = None,
    ):
        """
        Initialize PDF service.
        
        Args:
            case_id: Case identifier
            doc_id: Document identifier
            focus_mode: Export mode (review, story, evidence, redact)
            page_size: Page size ('A4', 'LETTER')
        """
        self.context = PDFGenerationContext(
            case_id=case_id,
            doc_id=doc_id,
            focus_mode=focus_mode,
            page_size=page_size
        )
        self._font_family = self._resolve_font_family(font_style)
        self._graph_style = self._resolve_graph_style(graph_style)
        self._table_style = table_style or "clean"
        self._selected_graphs = selected_graphs or []
        
        # Initialize coordinate mapper
        self.coord_mapper = create_a4_mapper() if page_size == 'A4' else CoordinateMapper('LETTER')
        
        # Initialize font manager
        self.font_manager = initialize_fonts()
        
        # PDF buffer and canvas
        self._buffer = io.BytesIO()
        self._canvas: Optional[canvas.Canvas] = None
        
        # Page tracking
        self._current_page = 0
        self._rendered_elements: List[RenderedElement] = []
        
        # Render context for widget renderers
        self._render_context: Optional[RenderContext] = None
        
        # Vault keys for redact mode
        self._vault_keys: Dict[str, str] = {}
        
        # Styles
        self._styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _resolve_font_family(self, font_style: Optional[str]) -> str:
        style = (font_style or "").strip().lower()
        if style in {"times", "georgia", "serif", "classic"}:
            return "Times"
        if style in {"mono", "code", "courier"}:
            return "Courier"
        return "Helvetica"

    def _resolve_graph_style(self, graph_style: Optional[str]) -> str:
        style = (graph_style or "").strip().lower()
        if style in {"dark", "contrast"}:
            return "dark"
        return "light"
    
    def _init_custom_styles(self) -> None:
        """Initialize custom paragraph styles for NFLIP."""
        
        title_font = self.font_manager.get_font_name(self._font_family, "bold", "normal")
        body_font = self.font_manager.get_font_name(self._font_family, "normal", "normal")
        code_font = self.font_manager.get_font_name("Courier", "normal", "normal")

        # Title style
        self._styles.add(ParagraphStyle(
            name='NFLIPTitle',
            fontName=title_font,
            fontSize=24,
            leading=28,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            spaceAfter=12
        ))
        
        # Heading styles
        self._styles.add(ParagraphStyle(
            name='NFLIPH1',
            fontName=title_font,
            fontSize=18,
            leading=22,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            spaceBefore=16,
            spaceAfter=8
        ))
        
        self._styles.add(ParagraphStyle(
            name='NFLIPH2',
            fontName=title_font,
            fontSize=14,
            leading=18,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            spaceBefore=12,
            spaceAfter=6
        ))
        
        self._styles.add(ParagraphStyle(
            name='NFLIPH3',
            fontName=title_font,
            fontSize=12,
            leading=16,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            spaceBefore=8,
            spaceAfter=4
        ))
        
        # Body text
        self._styles.add(ParagraphStyle(
            name='NFLIPBody',
            fontName=body_font,
            fontSize=10,
            leading=14,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            alignment=TA_JUSTIFY
        ))
        
        # Caption/label
        self._styles.add(ParagraphStyle(
            name='NFLIPCaption',
            fontName=body_font,
            fontSize=8,
            leading=10,
            textColor=HexColor(NFLIPColors.TEXT_SECONDARY)
        ))
        
        # Code block
        self._styles.add(ParagraphStyle(
            name='NFLIPCode',
            fontName=code_font,
            fontSize=9,
            leading=11,
            textColor=HexColor(NFLIPColors.TEXT_PRIMARY),
            backColor=HexColor(NFLIPColors.BACKGROUND)
        ))
    
    def set_vault_keys(self, vault_keys: Dict[str, str]) -> None:
        """
        Set vault keys for redaction mode.
        
        In redact mode, values are replaced with their keys (e.g., "John Doe" -> "[ACTOR_001]")
        
        Args:
            vault_keys: Mapping of key names to values
        """
        self._vault_keys = vault_keys or {}
    
    def convert_canvas_to_pdf(self, ast_data: Dict[str, Any], vault_keys: Dict[str, str] = None) -> bytes:
        """
        Convert canvas AST to PDF bytes.
        
        Args:
            ast_data: Canvas AST with pages and elements
            vault_keys: Optional vault key-value mapping for redaction
        
        Returns:
            PDF file as bytes
        """
        if vault_keys:
            self._vault_keys = vault_keys
            
        logger.info(f"Starting PDF generation for case {self.context.case_id}, doc {self.context.doc_id}")
        
        # Get page size
        page_size = A4 if self.context.page_size == 'A4' else LETTER
        
        # Create canvas
        self._canvas = canvas.Canvas(
            self._buffer,
            pagesize=page_size,
            initialFontName='Helvetica',
            initialFontSize=10
        )
        
        # Set document metadata
        self._set_metadata(ast_data)
        
        # Initialize render context for widget renderers
        self._render_context = RenderContext(
            canvas=self._canvas,
            focus_mode=self.context.focus_mode,
            vault_keys=self._vault_keys,
            styles=self._styles,
            chart_renderer=get_pdf_chart_renderer(style=self._graph_style),
            font_family=self._font_family,
            graph_style=self._graph_style,
            table_style=self._table_style,
            selected_graphs=self._selected_graphs,
        )
        
        # Extract pages from AST
        pages = ast_data.get('pages', [])
        if not pages:
            # Single page document (legacy format)
            pages = [{'elements': ast_data.get('elements', [])}]
        
        # Render each page
        for page_index, page_data in enumerate(pages):
            self._current_page = page_index + 1
            
            if page_index > 0:
                self._canvas.showPage()
            
            self._render_page(page_data)
        
        # Add evidence appendix if needed
        if self._rendered_elements:
            self._render_evidence_appendix()
        
        # Calculate merkle root
        self._calculate_merkle_root()
        
        # Finalize PDF
        self._canvas.save()
        
        # Get bytes
        pdf_bytes = self._buffer.getvalue()
        
        logger.info(f"PDF generation complete: {len(pdf_bytes)} bytes, {self._current_page} pages")
        
        return pdf_bytes
    
    def _set_metadata(self, ast_data: Dict[str, Any]) -> None:
        """Set PDF document metadata."""
        title = ast_data.get('title', f"NFLIP Report - {self.context.case_id}")
        
        self._canvas.setTitle(title)
        self._canvas.setAuthor(self.context.author)
        self._canvas.setSubject(f"Forensic Investigation Report - {self.context.case_id}")
        self._canvas.setCreator('NFLIP ReportLab Engine v1.0')
        self._canvas.setKeywords([
            'forensic', 'investigation', 'NFLIP', 
            self.context.case_id, str(self.context.focus_mode)
        ])
        
        self.context.title = title
    
    def _render_page(self, page_data: Dict[str, Any]) -> None:
        """
        Render a single page with all its elements.
        
        Args:
            page_data: Page data with elements list
        """
        elements = page_data.get('elements', [])
        
        # Sort by z-index for proper layering
        elements = sorted(elements, key=lambda e: e.get('zIndex', 0))
        
        # Render page background
        self._render_page_background()
        
        # Render each element
        for element in elements:
            self._render_element(element)
    
    def _render_page_background(self) -> None:
        """Render page background and any global elements."""
        # White background (already default)
        pass
    
    def _render_element(self, element: Dict[str, Any]) -> None:
        """
        Render a single canvas element.
        
        Args:
            element: Element data with type, position, size, and content
        """
        element_id = element.get('id', 'unknown')
        element_type = element.get('type', 'text')
        
        # Get canvas position and size
        canvas_x = element.get('x', 0)
        canvas_y = element.get('y', 0)
        canvas_width = element.get('width', 200)
        canvas_height = element.get('height', 100)
        
        # Convert to PDF coordinates
        bbox = self.coord_mapper.canvas_element_to_pdf_bbox(
            canvas_x, canvas_y, canvas_width, canvas_height
        )
        
        # Calculate content hash
        content_hash = self._hash_element(element)
        
        # Render based on type
        try:
            if element_type == 'text':
                self._render_text_element(element, bbox)
            elif element_type == 'component':
                self._render_component_element(element, bbox)
            elif element_type == 'image':
                self._render_image_element(element, bbox)
            elif element_type == 'shape':
                self._render_shape_element(element, bbox)
            elif element_type == 'metric':
                self._render_metric_element(element, bbox)
            elif element_type == 'chart':
                self._render_chart_element(element, bbox)
            else:
                logger.warning(f"Unknown element type: {element_type}")
                self._render_placeholder(element, bbox)
            
            # Track rendered element
            self._rendered_elements.append(RenderedElement(
                element_id=element_id,
                element_type=element_type,
                content_hash=content_hash,
                page_number=self._current_page,
                bounds=bbox
            ))
            
        except Exception as e:
            logger.error(f"Failed to render element {element_id}: {e}")
            self._render_error_placeholder(element_id, bbox, str(e))
    
    def _render_text_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a text element."""
        # Support both flat structure (content on element) and nested (data.content)
        data = element.get('data', {})
        content = element.get('content') or data.get('content', data.get('text', ''))
        
        if not content:
            return
        
        # Get text styling - check both element level and data level
        font_size = element.get('fontSize') or data.get('fontSize', 10)
        font_weight = element.get('fontWeight') or data.get('fontWeight', 'normal')
        text_align = element.get('textAlign') or data.get('textAlign', 'left')
        color = element.get('color') or data.get('color', NFLIPColors.TEXT_PRIMARY)
        
        # Map alignment
        alignment_map = {
            'left': TA_LEFT,
            'center': TA_CENTER,
            'right': TA_RIGHT,
            'justify': TA_JUSTIFY
        }
        
        # Create paragraph style
        style = ParagraphStyle(
            name='ElementText',
            fontName=self.font_manager.get_font_name(
                self._font_family,
                'bold' if font_weight == 'bold' else 'normal',
                'normal'
            ),
            fontSize=self.coord_mapper.px_to_pt(font_size),
            leading=self.coord_mapper.px_to_pt(font_size * 1.4),
            textColor=HexColor(color) if color.startswith('#') else black,
            alignment=alignment_map.get(text_align, TA_LEFT)
        )
        
        # Create and draw paragraph
        para = Paragraph(self._escape_html(content), style)
        
        # Calculate available dimensions
        available_width = bbox.width
        available_height = bbox.height
        
        # Wrap paragraph
        w, h = para.wrap(available_width, available_height)
        
        # Draw at position (adjust Y for text baseline)
        para.drawOn(self._canvas, bbox.x, bbox.y + bbox.height - h)
    
    def _render_component_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """
        Render a component element using widget renderers.
        
        Phase 3: Uses widget_renderers.py for all component types.
        """
        data = element.get('data', {})
        # Support 'componentType', 'type', and 'chartType' field names
        component_type = data.get('componentType', data.get('type', data.get('chartType', 'unknown')))
        
        # Draw component container
        self._draw_component_container(element, bbox)
        
        # Use widget renderer if available
        if self._render_context and component_type in WIDGET_RENDERERS:
            try:
                render_widget(component_type, data, bbox, self._render_context)
                return
            except Exception as e:
                logger.warning(f"Widget renderer failed for {component_type}, using fallback: {e}")
        
        # Fallback to inline renderers for backward compatibility
        chart_types = {
            'chart', 'area-chart', 'bar-chart', 'pie-chart', 'scatter', 
            'scatter-plot', 'heatmap', 'gauge', 'timeline', 'area'
        }
        
        if component_type == 'metric':
            self._render_metric_component(data, bbox)
        elif component_type == 'finding':
            self._render_finding_component(data, bbox)
        elif component_type == 'table':
            self._render_table_component(data, bbox)
        elif component_type in chart_types:
            self._render_chart_component(data, bbox)
        elif component_type == 'timeline-event':
            self._render_timeline_event_component(data, bbox)
        elif component_type == 'anomaly':
            self._render_anomaly_component(data, bbox)
        elif component_type in ('network-flow', 'sankey'):
            self._render_network_flow_component(data, bbox)
        elif component_type in ('shap-explanation', 'shap', 'shap-waterfall'):
            self._render_shap_component(data, bbox)
        elif component_type in ('correlation-graph', 'correlation', 'network-graph'):
            self._render_correlation_component(data, bbox)
        else:
            self._render_generic_component(data, bbox)
    
    def _draw_component_container(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Draw a container box for components."""
        # Light background
        self._canvas.setFillColor(HexColor(NFLIPColors.BACKGROUND))
        self._canvas.setStrokeColor(HexColor(NFLIPColors.BORDER))
        self._canvas.setLineWidth(0.5)
        
        # Rounded rectangle
        self._canvas.roundRect(
            bbox.x, bbox.y, bbox.width, bbox.height,
            radius=4,
            fill=1, stroke=1
        )
        
        # Draw title if present
        data = element.get('data', {})
        title = data.get('title', '')
        
        if title:
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            self._canvas.setFont('Helvetica-Bold', 10)
            self._canvas.drawString(
                bbox.x + 8, 
                bbox.y + bbox.height - 16, 
                title
            )
    
    def _render_metric_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a metric/KPI component."""
        value = str(data.get('value', '—'))
        label = data.get('label', '')
        trend = data.get('trend', '')
        
        # Large value
        self._canvas.setFillColor(HexColor(NFLIPColors.PRIMARY))
        self._canvas.setFont('Helvetica-Bold', 28)
        
        # Center the value
        text_width = self._canvas.stringWidth(value, 'Helvetica-Bold', 28)
        x_center = bbox.x + (bbox.width - text_width) / 2
        y_value = bbox.y + bbox.height / 2
        
        self._canvas.drawString(x_center, y_value, value)
        
        # Label below
        if label:
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            self._canvas.setFont('Helvetica', 10)
            label_width = self._canvas.stringWidth(label, 'Helvetica', 10)
            self._canvas.drawString(
                bbox.x + (bbox.width - label_width) / 2,
                y_value - 18,
                label
            )
        
        # Trend indicator
        if trend:
            trend_color = NFLIPColors.SUCCESS if trend.startswith('+') else NFLIPColors.DANGER
            self._canvas.setFillColor(HexColor(trend_color))
            self._canvas.setFont('Helvetica', 9)
            self._canvas.drawString(x_center + text_width + 4, y_value + 8, trend)
    
    def _render_finding_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a finding/insight component."""
        severity = data.get('severity', 'INFO')
        summary = data.get('summary', data.get('content', ''))
        
        # Severity badge
        severity_color = NFLIPColors.get_severity_color(severity)
        
        # Draw severity indicator bar on left
        self._canvas.setFillColor(HexColor(severity_color))
        self._canvas.rect(bbox.x, bbox.y, 4, bbox.height, fill=1, stroke=0)
        
        # Severity label
        self._canvas.setFont('Helvetica-Bold', 8)
        self._canvas.drawString(bbox.x + 10, bbox.y + bbox.height - 16, severity)
        
        # Summary text
        if summary:
            style = self._styles['NFLIPBody']
            para = Paragraph(self._escape_html(summary), style)
            w, h = para.wrap(bbox.width - 16, bbox.height - 24)
            para.drawOn(self._canvas, bbox.x + 10, bbox.y + bbox.height - 24 - h)
    
    def _render_table_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a data table component."""
        rows = data.get('rows', data.get('data', []))
        headers = data.get('headers', [])
        
        if not rows:
            self._render_empty_state(bbox, "No data")
            return
        
        # Build table data
        table_data = []
        
        if headers:
            table_data.append(headers)
        elif rows and isinstance(rows[0], dict):
            headers = list(rows[0].keys())
            table_data.append(headers)
        
        # Add rows
        for row in rows[:20]:  # Limit to 20 rows
            if isinstance(row, dict):
                table_data.append([str(row.get(h, '')) for h in headers])
            elif isinstance(row, (list, tuple)):
                table_data.append([str(v) for v in row])
        
        if not table_data:
            return
        
        # Calculate column widths
        num_cols = len(table_data[0]) if table_data else 1
        col_width = (bbox.width - 16) / num_cols
        
        # Create table
        table = Table(table_data, colWidths=[col_width] * num_cols)
        
        # Style table
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(NFLIPColors.PRIMARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor(NFLIPColors.BORDER)),
            ('BACKGROUND', (0, 1), (-1, -1), white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        
        # Draw table
        w, h = table.wrap(bbox.width - 16, bbox.height - 24)
        table.drawOn(self._canvas, bbox.x + 8, bbox.y + bbox.height - 20 - h)
    
    def _render_chart_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """
        Render a chart component using matplotlib chart renderer.
        
        Phase 2: Full chart rendering via chart_renderer.py
        """
        chart_type = data.get('chartType', data.get('type', 'bar'))
        chart_data = data.get('data', data.get('chartData', []))
        title = data.get('title', data.get('label', ''))
        
        # Extract chart-specific options
        chart_config = data.get('config', {})
        threshold = chart_config.get('threshold', 0.7)
        
        try:
            # Get PDF-optimized chart renderer (light style, 200 DPI)
            if not hasattr(self, '_chart_renderer'):
                self._chart_renderer = get_pdf_chart_renderer(style=self._graph_style)
            
            # Calculate pixel dimensions for chart (convert points back to pixels)
            # Charts are rendered at 200 DPI, then scaled to fit the bounding box
            chart_width = int(bbox.width * 1.5)  # Higher res for quality
            chart_height = int(bbox.height * 1.5)
            
            # Render chart to buffer
            chart_buffer = self._chart_renderer.render_to_buffer(
                chart_type=chart_type,
                data=chart_data,
                width=chart_width,
                height=chart_height,
                title=title,
                threshold=threshold
            )
            
            # Embed chart image in PDF
            img = ImageReader(chart_buffer)
            
            # Draw with padding
            padding = 4
            self._canvas.drawImage(
                img,
                bbox.x + padding,
                bbox.y + padding,
                width=bbox.width - (padding * 2),
                height=bbox.height - (padding * 2),
                preserveAspectRatio=True,
                mask='auto'
            )
            
            logger.debug(f"Rendered {chart_type} chart at ({bbox.x}, {bbox.y})")
            
        except Exception as e:
            logger.error(f"Error rendering chart {chart_type}: {e}")
            # Fallback to placeholder
            self._render_chart_placeholder(chart_type, bbox, str(e))
    
    def _render_chart_placeholder(self, chart_type: str, bbox: BoundingBox, error: str = None) -> None:
        """Render a placeholder when chart rendering fails."""
        self._canvas.setFillColor(HexColor('#e2e8f0'))
        self._canvas.roundRect(
            bbox.x + 8, bbox.y + 8, 
            bbox.width - 16, bbox.height - 32,
            radius=4, fill=1, stroke=0
        )
        
        # Chart type label
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        self._canvas.setFont('Helvetica', 10)
        label = f"[{chart_type.upper()} CHART]"
        if error:
            label = f"[{chart_type.upper()} - Error]"
        label_width = self._canvas.stringWidth(label, 'Helvetica', 10)
        self._canvas.drawString(
            bbox.x + (bbox.width - label_width) / 2,
            bbox.y + bbox.height / 2,
            label
        )
    
    def _render_timeline_event_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a timeline event component."""
        timestamp = data.get('timestamp', data.get('normalised_ts', ''))
        source = data.get('source_type', '')
        action = data.get('action', '')
        actor = data.get('actor', '')
        severity = data.get('severity', 'INFO')
        
        # Severity color bar
        severity_color = NFLIPColors.get_severity_color(severity)
        self._canvas.setFillColor(HexColor(severity_color))
        self._canvas.rect(bbox.x, bbox.y, 3, bbox.height, fill=1, stroke=0)
        
        y_pos = bbox.y + bbox.height - 16
        
        # Timestamp
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        self._canvas.setFont('Courier', 8)
        self._canvas.drawString(bbox.x + 8, y_pos, timestamp[:19] if timestamp else '')
        
        y_pos -= 14
        
        # Source badge
        self._canvas.setFillColor(HexColor(NFLIPColors.PRIMARY))
        self._canvas.setFont('Helvetica-Bold', 8)
        self._canvas.drawString(bbox.x + 8, y_pos, source)
        
        # Action
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        self._canvas.setFont('Helvetica', 9)
        self._canvas.drawString(bbox.x + 50, y_pos, action)
        
        y_pos -= 12
        
        # Actor
        self._canvas.setFillColor(HexColor(NFLIPColors.INFO))
        self._canvas.setFont('Helvetica', 8)
        self._canvas.drawString(bbox.x + 8, y_pos, f"Actor: {actor}")
    
    def _render_anomaly_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render an anomaly detection component."""
        score = data.get('anomaly_score', data.get('score', 0))
        is_anomaly = data.get('is_anomaly', score >= 0.65)
        
        # Score display
        score_color = NFLIPColors.DANGER if is_anomaly else NFLIPColors.SUCCESS
        
        self._canvas.setFillColor(HexColor(score_color))
        self._canvas.setFont('Helvetica-Bold', 20)
        score_text = f"{score:.3f}"
        self._canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 30, score_text)
        
        # Status label
        status = "ANOMALY" if is_anomaly else "NORMAL"
        self._canvas.setFont('Helvetica', 9)
        self._canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 44, status)
    
    def _render_network_flow_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a network flow component."""
        flows = data.get('flows', data.get('data', []))
        
        if not flows:
            self._render_empty_state(bbox, "No network flows")
            return
        
        # Render as mini table
        y_pos = bbox.y + bbox.height - 20
        
        self._canvas.setFont('Helvetica', 8)
        
        for flow in flows[:5]:  # Show first 5
            src = flow.get('source_ip', flow.get('src', ''))
            dst = flow.get('dest_ip', flow.get('dst', ''))
            bytes_val = flow.get('bytes_sent', flow.get('bytes', 0))
            
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            self._canvas.drawString(bbox.x + 8, y_pos, f"{src} → {dst}")
            
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            self._canvas.drawString(bbox.x + bbox.width - 60, y_pos, f"{bytes_val:,} B")
            
            y_pos -= 12
    
    def _render_shap_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a SHAP explanation component."""
        contributions = data.get('feature_contributions', data.get('shap_factors', []))
        
        if not contributions:
            self._render_empty_state(bbox, "No SHAP data")
            return
        
        y_pos = bbox.y + bbox.height - 24
        bar_max_width = bbox.width * 0.4
        
        for contrib in contributions[:5]:  # Show top 5
            feature = contrib.get('feature', contrib.get('factor', ''))
            value = contrib.get('shap_value', contrib.get('contribution', 0))
            
            # Feature name
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            self._canvas.setFont('Helvetica', 8)
            self._canvas.drawString(bbox.x + 8, y_pos, feature[:20])
            
            # Bar
            bar_width = abs(value) * bar_max_width
            bar_color = NFLIPColors.DANGER if value > 0 else NFLIPColors.SUCCESS
            
            self._canvas.setFillColor(HexColor(bar_color))
            self._canvas.rect(
                bbox.x + bbox.width * 0.4, 
                y_pos - 2, 
                bar_width, 
                10, 
                fill=1, stroke=0
            )
            
            # Value
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            self._canvas.setFont('Helvetica', 7)
            self._canvas.drawString(
                bbox.x + bbox.width * 0.4 + bar_width + 4, 
                y_pos, 
                f"{value:.3f}"
            )
            
            y_pos -= 16
    
    def _render_correlation_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a correlation graph component using chart renderer."""
        nodes = data.get('nodes', [])
        edges = data.get('edges', data.get('links', []))
        title = data.get('title', 'Entity Correlation')
        
        if not nodes:
            # Fallback placeholder
            self._canvas.setFillColor(HexColor('#f1f5f9'))
            self._canvas.roundRect(
                bbox.x + 8, bbox.y + 8,
                bbox.width - 16, bbox.height - 32,
                radius=4, fill=1, stroke=0
            )
            
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            self._canvas.setFont('Helvetica', 10)
            self._canvas.drawString(
                bbox.x + bbox.width / 2 - 40,
                bbox.y + bbox.height / 2,
                "[NO CORRELATION DATA]"
            )
            return
        
        try:
            if not hasattr(self, '_chart_renderer'):
                self._chart_renderer = get_pdf_chart_renderer(style=self._graph_style)
            
            # Render correlation graph
            chart_buffer = self._chart_renderer.render_to_buffer(
                chart_type='correlation',
                data={'nodes': nodes, 'edges': edges},
                width=int(bbox.width * 1.5),
                height=int(bbox.height * 1.5),
                title=title
            )
            
            img = ImageReader(chart_buffer)
            padding = 4
            self._canvas.drawImage(
                img,
                bbox.x + padding,
                bbox.y + padding,
                width=bbox.width - (padding * 2),
                height=bbox.height - (padding * 2),
                preserveAspectRatio=True,
                mask='auto'
            )
        except Exception as e:
            logger.error(f"Error rendering correlation graph: {e}")
            self._render_chart_placeholder('correlation', bbox, str(e))
    
    def _render_generic_component(self, data: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a generic/unknown component type."""
        component_type = data.get('type', 'unknown')
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.setFont('Helvetica', 9)
        self._canvas.drawString(
            bbox.x + 8,
            bbox.y + bbox.height / 2,
            f"[{component_type.upper()}]"
        )
    
    def _render_image_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render an image element."""
        data = element.get('data', {})
        image_src = data.get('src', data.get('url', ''))
        
        if not image_src:
            self._render_placeholder(element, bbox)
            return
        
        try:
            # Handle base64 or file path
            if image_src.startswith('data:image'):
                # Base64 encoded
                import base64
                header, encoded = image_src.split(',', 1)
                image_data = base64.b64decode(encoded)
                image_buffer = io.BytesIO(image_data)
                
                img = Image(image_buffer, width=bbox.width, height=bbox.height)
                img.drawOn(self._canvas, bbox.x, bbox.y)
                
            elif Path(image_src).exists():
                # File path
                img = Image(image_src, width=bbox.width, height=bbox.height)
                img.drawOn(self._canvas, bbox.x, bbox.y)
            else:
                self._render_placeholder(element, bbox)
                
        except Exception as e:
            logger.error(f"Failed to render image: {e}")
            self._render_error_placeholder(element.get('id', ''), bbox, "Image load failed")
    
    def _render_shape_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a shape element."""
        data = element.get('data', {})
        shape_type = data.get('shapeType', 'rectangle')
        fill_color = data.get('fillColor', '#e2e8f0')
        stroke_color = data.get('strokeColor', '#94a3b8')
        stroke_width = data.get('strokeWidth', 1)
        
        self._canvas.setFillColor(HexColor(fill_color))
        self._canvas.setStrokeColor(HexColor(stroke_color))
        self._canvas.setLineWidth(stroke_width)
        
        if shape_type == 'rectangle':
            self._canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height, fill=1, stroke=1)
        elif shape_type == 'roundedRect':
            radius = data.get('borderRadius', 8)
            self._canvas.roundRect(bbox.x, bbox.y, bbox.width, bbox.height, radius, fill=1, stroke=1)
        elif shape_type == 'ellipse':
            self._canvas.ellipse(bbox.x, bbox.y, bbox.x2, bbox.y2, fill=1, stroke=1)
        elif shape_type == 'line':
            self._canvas.line(bbox.x, bbox.y, bbox.x2, bbox.y2)
    
    def _render_metric_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a metric/KPI card element."""
        # Extract metric data - check both root and data dict
        value = element.get('value') or element.get('data', {}).get('value', '—')
        label = element.get('label') or element.get('data', {}).get('label', 'Metric')
        trend = element.get('trend') or element.get('data', {}).get('trend', 'neutral')
        color = element.get('color') or element.get('data', {}).get('color', NFLIPColors.PRIMARY)
        
        # Background card
        self._canvas.setFillColor(HexColor('#f8fafc'))
        self._canvas.setStrokeColor(HexColor('#e2e8f0'))
        self._canvas.roundRect(bbox.x, bbox.y, bbox.width, bbox.height, 6, fill=1, stroke=1)
        
        # Color indicator bar at top
        indicator_color = {
            'critical': NFLIPColors.DANGER,
            'warning': NFLIPColors.WARNING,
            'success': NFLIPColors.SUCCESS,
            'neutral': NFLIPColors.PRIMARY
        }.get(trend, color)
        
        self._canvas.setFillColor(HexColor(indicator_color))
        self._canvas.rect(bbox.x, bbox.y + bbox.height - 4, bbox.width, 4, fill=1, stroke=0)
        
        # Value text (large, centered)
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        value_size = min(24, bbox.height * 0.35)
        self._canvas.setFont('Helvetica-Bold', value_size)
        value_str = str(value)
        value_width = self._canvas.stringWidth(value_str, 'Helvetica-Bold', value_size)
        self._canvas.drawString(
            bbox.x + (bbox.width - value_width) / 2,
            bbox.y + bbox.height * 0.45,
            value_str
        )
        
        # Label text (smaller, below value)
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        label_size = min(10, bbox.height * 0.12)
        self._canvas.setFont('Helvetica', label_size)
        label_width = self._canvas.stringWidth(label, 'Helvetica', label_size)
        self._canvas.drawString(
            bbox.x + (bbox.width - label_width) / 2,
            bbox.y + bbox.height * 0.2,
            label
        )
    
    def _render_chart_element(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a chart element with visual representation."""
        chart_type = element.get('chartType') or element.get('data', {}).get('chartType', 'bar')
        chart_title = element.get('chartTitle') or element.get('data', {}).get('chartTitle', 'Chart')
        data = element.get('data', {})
        
        # Chart background
        self._canvas.setFillColor(HexColor('#ffffff'))
        self._canvas.setStrokeColor(HexColor('#e2e8f0'))
        self._canvas.roundRect(bbox.x, bbox.y, bbox.width, bbox.height, 4, fill=1, stroke=1)
        
        # Chart title
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        self._canvas.setFont('Helvetica-Bold', 10)
        self._canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 16, chart_title)
        
        # Chart area (excluding title)
        chart_area = BoundingBox(
            x=bbox.x + 8,
            y=bbox.y + 8,
            width=bbox.width - 16,
            height=bbox.height - 32
        )
        
        # Render based on chart type
        if chart_type == 'pie':
            self._render_pie_chart(chart_area, data)
        elif chart_type == 'bar':
            self._render_bar_chart(chart_area, data)
        elif chart_type in ['line', 'area-chart']:
            self._render_line_chart(chart_area, data)
        elif chart_type == 'gauge':
            self._render_gauge_chart(chart_area, data)
        elif chart_type in ['timeline', 'correlation-graph', 'network-flow']:
            self._render_network_diagram(chart_area, data, chart_type)
        elif chart_type in ['scatter', 'heatmap', 'shap-waterfall']:
            self._render_analysis_chart(chart_area, data, chart_type)
        else:
            # Generic chart placeholder
            self._render_chart_placeholder(chart_area, chart_type)
    
    def _render_pie_chart(self, bbox: BoundingBox, data: Any) -> None:
        """Render a simple pie chart."""
        import math
        
        # Get data items
        items = data if isinstance(data, list) else data.get('items', data.get('data', []))
        if not items:
            items = [{'name': 'A', 'value': 60, 'color': '#3b82f6'},
                     {'name': 'B', 'value': 30, 'color': '#22c55e'},
                     {'name': 'C', 'value': 10, 'color': '#f59e0b'}]
        
        total = sum(item.get('value', 0) for item in items)
        if total == 0:
            return
        
        # Center and radius
        center_x = bbox.x + bbox.width * 0.35
        center_y = bbox.y + bbox.height / 2
        radius = min(bbox.width * 0.3, bbox.height * 0.4)
        
        # Draw pie slices
        start_angle = 90
        colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
        
        for i, item in enumerate(items):
            value = item.get('value', 0)
            sweep = (value / total) * 360
            color = item.get('color', colors[i % len(colors)])
            
            # Draw wedge
            self._canvas.setFillColor(HexColor(color))
            path = self._canvas.beginPath()
            path.moveTo(center_x, center_y)
            path.arc(center_x - radius, center_y - radius, 
                    center_x + radius, center_y + radius,
                    start_angle, sweep)
            path.close()
            self._canvas.drawPath(path, fill=1, stroke=0)
            
            start_angle += sweep
        
        # Draw legend on right side
        legend_x = bbox.x + bbox.width * 0.65
        legend_y = bbox.y + bbox.height - 20
        
        self._canvas.setFont('Helvetica', 8)
        for i, item in enumerate(items[:5]):  # Max 5 items
            color = item.get('color', colors[i % len(colors)])
            name = item.get('name', f'Item {i+1}')
            value = item.get('value', 0)
            
            # Color box
            self._canvas.setFillColor(HexColor(color))
            self._canvas.rect(legend_x, legend_y - 8, 10, 10, fill=1, stroke=0)
            
            # Label
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            self._canvas.drawString(legend_x + 14, legend_y - 6, f'{name}: {value}')
            legend_y -= 16
    
    def _render_bar_chart(self, bbox: BoundingBox, data: Any) -> None:
        """Render a simple bar chart."""
        items = data if isinstance(data, list) else data.get('items', data.get('data', []))
        if not items:
            items = [{'name': 'A', 'value': 80}, {'name': 'B', 'value': 60},
                     {'name': 'C', 'value': 40}, {'name': 'D', 'value': 90}]
        
        max_val = max((item.get('value', 0) for item in items), default=1)
        if max_val == 0:
            max_val = 1
        
        # Chart dimensions
        chart_left = bbox.x + 30
        chart_bottom = bbox.y + 20
        chart_width = bbox.width - 40
        chart_height = bbox.height - 30
        
        # Draw bars
        num_bars = len(items)
        bar_width = chart_width / (num_bars * 1.5)
        bar_gap = bar_width * 0.5
        
        colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
        
        for i, item in enumerate(items[:8]):  # Max 8 bars
            value = item.get('value', 0)
            bar_height = (value / max_val) * chart_height
            bar_x = chart_left + i * (bar_width + bar_gap)
            color = colors[i % len(colors)]
            
            # Draw bar
            self._canvas.setFillColor(HexColor(color))
            self._canvas.rect(bar_x, chart_bottom, bar_width, bar_height, fill=1, stroke=0)
            
            # Label below
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
            self._canvas.setFont('Helvetica', 6)
            name = str(item.get('name', ''))[:6]
            self._canvas.drawString(bar_x, chart_bottom - 10, name)
    
    def _render_line_chart(self, bbox: BoundingBox, data: Any) -> None:
        """Render a simple line/area chart placeholder."""
        # Draw axis
        self._canvas.setStrokeColor(HexColor('#cbd5e1'))
        self._canvas.line(bbox.x + 20, bbox.y + 10, bbox.x + 20, bbox.y + bbox.height - 10)
        self._canvas.line(bbox.x + 20, bbox.y + 10, bbox.x + bbox.width - 10, bbox.y + 10)
        
        # Draw sample line
        self._canvas.setStrokeColor(HexColor(NFLIPColors.PRIMARY))
        self._canvas.setLineWidth(2)
        
        import math
        points = []
        for i in range(10):
            x = bbox.x + 25 + i * (bbox.width - 40) / 9
            y = bbox.y + 20 + (bbox.height - 40) * (0.5 + 0.3 * math.sin(i * 0.7))
            points.append((x, y))
        
        path = self._canvas.beginPath()
        path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            path.lineTo(x, y)
        self._canvas.drawPath(path, fill=0, stroke=1)
        self._canvas.setLineWidth(1)
    
    def _render_gauge_chart(self, bbox: BoundingBox, data: Any) -> None:
        """Render a gauge/dial chart."""
        import math
        
        value = data.get('value', 0.5) if isinstance(data, dict) else 0.5
        max_val = data.get('max', 1.0) if isinstance(data, dict) else 1.0
        
        center_x = bbox.x + bbox.width / 2
        center_y = bbox.y + bbox.height * 0.4
        radius = min(bbox.width, bbox.height) * 0.35
        
        # Draw arc background
        self._canvas.setStrokeColor(HexColor('#e2e8f0'))
        self._canvas.setLineWidth(8)
        self._canvas.arc(center_x - radius, center_y - radius,
                        center_x + radius, center_y + radius,
                        180, 180)
        
        # Draw value arc
        fill_angle = (value / max_val) * 180
        color = NFLIPColors.SUCCESS if value < 0.6 else (NFLIPColors.WARNING if value < 0.8 else NFLIPColors.DANGER)
        self._canvas.setStrokeColor(HexColor(color))
        self._canvas.arc(center_x - radius, center_y - radius,
                        center_x + radius, center_y + radius,
                        180, fill_angle)
        self._canvas.setLineWidth(1)
        
        # Value text
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        self._canvas.setFont('Helvetica-Bold', 16)
        val_str = f'{value:.0%}' if max_val == 1 else str(value)
        val_width = self._canvas.stringWidth(val_str, 'Helvetica-Bold', 16)
        self._canvas.drawString(center_x - val_width/2, center_y - 20, val_str)
    
    def _render_network_diagram(self, bbox: BoundingBox, data: Any, chart_type: str) -> None:
        """Render network/flow diagrams as placeholder with nodes."""
        self._canvas.setFont('Helvetica', 8)
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.drawString(bbox.x + 4, bbox.y + bbox.height - 12, f'[{chart_type} diagram]')
        
        # Draw sample nodes
        nodes = data.get('nodes', []) if isinstance(data, dict) else []
        if not nodes:
            nodes = [{'label': 'A'}, {'label': 'B'}, {'label': 'C'}]
        
        num_nodes = min(len(nodes), 5)
        for i, node in enumerate(nodes[:num_nodes]):
            x = bbox.x + 30 + i * (bbox.width - 60) / max(num_nodes - 1, 1)
            y = bbox.y + bbox.height / 2
            
            # Node circle
            self._canvas.setFillColor(HexColor('#dbeafe'))
            self._canvas.setStrokeColor(HexColor('#3b82f6'))
            self._canvas.circle(x, y, 12, fill=1, stroke=1)
            
            # Label
            label = str(node.get('label', node.get('id', i)))[:3]
            self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            self._canvas.setFont('Helvetica', 6)
            self._canvas.drawCentredString(x, y - 2, label)
        
        # Draw connecting lines
        if num_nodes > 1:
            self._canvas.setStrokeColor(HexColor('#94a3b8'))
            for i in range(num_nodes - 1):
                x1 = bbox.x + 30 + i * (bbox.width - 60) / max(num_nodes - 1, 1) + 12
                x2 = bbox.x + 30 + (i + 1) * (bbox.width - 60) / max(num_nodes - 1, 1) - 12
                y = bbox.y + bbox.height / 2
                self._canvas.line(x1, y, x2, y)
    
    def _render_analysis_chart(self, bbox: BoundingBox, data: Any, chart_type: str) -> None:
        """Render analysis charts (scatter, heatmap, SHAP)."""
        self._canvas.setFillColor(HexColor('#f8fafc'))
        self._canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height, fill=1, stroke=0)
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.setFont('Helvetica', 8)
        self._canvas.drawString(bbox.x + 4, bbox.y + bbox.height - 12, f'[{chart_type} analysis]')
        
        if chart_type == 'scatter':
            # Draw sample scatter points
            import random
            random.seed(42)
            self._canvas.setFillColor(HexColor('#3b82f6'))
            for _ in range(20):
                x = bbox.x + 20 + random.random() * (bbox.width - 40)
                y = bbox.y + 15 + random.random() * (bbox.height - 35)
                self._canvas.circle(x, y, 3, fill=1, stroke=0)
        elif chart_type == 'heatmap':
            # Draw sample heatmap grid
            colors = ['#dcfce7', '#bbf7d0', '#86efac', '#4ade80', '#22c55e']
            cell_w = (bbox.width - 20) / 5
            cell_h = (bbox.height - 30) / 3
            for row in range(3):
                for col in range(5):
                    color = colors[(row + col) % len(colors)]
                    self._canvas.setFillColor(HexColor(color))
                    self._canvas.rect(
                        bbox.x + 10 + col * cell_w,
                        bbox.y + 10 + row * cell_h,
                        cell_w - 2, cell_h - 2, fill=1, stroke=0
                    )
    
    def _render_chart_placeholder(self, bbox: BoundingBox, chart_type: str) -> None:
        """Render a chart placeholder."""
        self._canvas.setFillColor(HexColor('#f8fafc'))
        self._canvas.setStrokeColor(HexColor('#e2e8f0'))
        self._canvas.setDash(3, 2)
        self._canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height, fill=1, stroke=1)
        self._canvas.setDash()
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.setFont('Helvetica', 9)
        text = f'[{chart_type} Chart]'
        text_width = self._canvas.stringWidth(text, 'Helvetica', 9)
        self._canvas.drawString(
            bbox.x + (bbox.width - text_width) / 2,
            bbox.y + bbox.height / 2,
            text
        )
    
    def _render_placeholder(self, element: Dict[str, Any], bbox: BoundingBox) -> None:
        """Render a placeholder for unknown/unhandled elements."""
        self._canvas.setFillColor(HexColor('#f1f5f9'))
        self._canvas.setStrokeColor(HexColor('#cbd5e1'))
        self._canvas.setDash(3, 2)
        self._canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height, fill=1, stroke=1)
        self._canvas.setDash()
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.setFont('Helvetica', 8)
        self._canvas.drawString(bbox.x + 4, bbox.y + bbox.height / 2, "[Placeholder]")
    
    def _render_error_placeholder(self, element_id: str, bbox: BoundingBox, error: str) -> None:
        """Render an error placeholder."""
        self._canvas.setFillColor(HexColor('#fef2f2'))
        self._canvas.setStrokeColor(HexColor(NFLIPColors.DANGER))
        self._canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height, fill=1, stroke=1)
        
        self._canvas.setFillColor(HexColor(NFLIPColors.DANGER))
        self._canvas.setFont('Helvetica', 8)
        self._canvas.drawString(bbox.x + 4, bbox.y + bbox.height / 2, f"Error: {error[:30]}")
    
    def _render_empty_state(self, bbox: BoundingBox, message: str) -> None:
        """Render an empty state message."""
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        self._canvas.setFont('Helvetica', 9)
        text_width = self._canvas.stringWidth(message, 'Helvetica', 9)
        self._canvas.drawString(
            bbox.x + (bbox.width - text_width) / 2,
            bbox.y + bbox.height / 2,
            message
        )
    
    def _render_evidence_appendix(self) -> None:
        """Render the evidence registry appendix."""
        self._canvas.showPage()
        self._current_page += 1
        
        # Title
        y_pos = self.coord_mapper.pdf_page_size.height - 50
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        self._canvas.setFont('Helvetica-Bold', 16)
        self._canvas.drawString(50, y_pos, "Vault of Evidence")
        
        y_pos -= 24
        
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        self._canvas.setFont('Helvetica', 9)
        self._canvas.drawString(50, y_pos, f"Document: {self.context.doc_id}")
        
        y_pos -= 12
        self._canvas.drawString(50, y_pos, f"Generated: {self.context.created_at.isoformat()}")
        
        y_pos -= 24
        
        # Table header
        headers = ['ID', 'Type', 'Page', 'Hash (First 16)']
        col_widths = [100, 100, 50, 200]
        x_pos = 50
        
        self._canvas.setFillColor(HexColor(NFLIPColors.PRIMARY))
        self._canvas.rect(50, y_pos - 2, sum(col_widths), 14, fill=1, stroke=0)
        
        self._canvas.setFillColor(white)
        self._canvas.setFont('Helvetica-Bold', 8)
        
        for i, header in enumerate(headers):
            self._canvas.drawString(x_pos + 4, y_pos, header)
            x_pos += col_widths[i]
        
        y_pos -= 16
        
        # Table rows
        self._canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        self._canvas.setFont('Helvetica', 8)
        
        for elem in self._rendered_elements:
            if y_pos < 50:  # New page if needed
                self._canvas.showPage()
                self._current_page += 1
                y_pos = self.coord_mapper.pdf_page_size.height - 50
            
            x_pos = 50
            
            self._canvas.drawString(x_pos + 4, y_pos, elem.element_id[:16])
            x_pos += col_widths[0]
            
            self._canvas.drawString(x_pos + 4, y_pos, elem.element_type)
            x_pos += col_widths[1]
            
            self._canvas.drawString(x_pos + 4, y_pos, str(elem.page_number))
            x_pos += col_widths[2]
            
            self._canvas.drawString(x_pos + 4, y_pos, elem.content_hash[:16])
            
            y_pos -= 12
    
    def _hash_element(self, element: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of element content."""
        # Canonical JSON representation
        canonical = json.dumps(element, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def _calculate_merkle_root(self) -> None:
        """Calculate Merkle root from all element hashes."""
        if not self._rendered_elements:
            self.context.merkle_root = hashlib.sha256(b'empty').hexdigest()
            return
        
        hashes = [e.content_hash for e in self._rendered_elements]
        
        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last if odd
            
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            
            hashes = new_hashes
        
        self.context.merkle_root = hashes[0]
        self.context.element_hashes = [e.content_hash for e in self._rendered_elements]
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """
        Process HTML text for ReportLab Paragraph.
        
        ReportLab Paragraph supports a subset of HTML tags:
        - <b>, <i>, <u> for bold, italic, underline
        - <font>, <para> for styling
        - <br/> for line breaks
        
        We need to convert our HTML tags to ReportLab-compatible format.
        """
        if not text:
            return ''
        
        import re
        
        # Convert common HTML to ReportLab-compatible tags
        result = text
        
        # Strip HTML style attributes (ReportLab doesn't support them well)
        result = re.sub(r'<(\w+)\s+style=[\'"][^\'"]*[\'"]>', r'<\1>', result)
        
        # Convert h1-h6 to bold text
        result = re.sub(r'<h[1-6][^>]*>', '<b>', result)
        result = re.sub(r'</h[1-6]>', '</b><br/>', result)
        
        # Convert paragraphs to line breaks
        result = re.sub(r'<p[^>]*>', '', result)
        result = re.sub(r'</p>', '<br/>', result)
        
        # Remove div tags
        result = re.sub(r'</?div[^>]*>', '', result)
        
        # Remove span tags but keep content
        result = re.sub(r'</?span[^>]*>', '', result)
        
        # Convert <strong> to <b> and <em> to <i>
        result = result.replace('<strong>', '<b>').replace('</strong>', '</b>')
        result = result.replace('<em>', '<i>').replace('</em>', '</i>')
        
        # Escape actual ampersands (but not HTML entities)
        result = re.sub(r'&(?!amp;|lt;|gt;|nbsp;|#\d+;)', '&amp;', result)
        
        # Clean up multiple consecutive breaks
        result = re.sub(r'(<br\s*/?>){3,}', '<br/><br/>', result)
        
        return result
    
    def get_generation_manifest(self) -> Dict[str, Any]:
        """Get generation manifest for verification."""
        return {
            'case_id': self.context.case_id,
            'doc_id': self.context.doc_id,
            'focus_mode': self.context.focus_mode,
            'title': self.context.title,
            'author': self.context.author,
            'created_at': self.context.created_at.isoformat(),
            'page_count': self._current_page,
            'element_count': len(self._rendered_elements),
            'merkle_root': self.context.merkle_root,
            'element_hashes': self.context.element_hashes,
            'engine': 'ReportLab',
            'engine_version': '1.0.0'
        }


# Convenience function for API usage
def generate_pdf_from_ast(
    case_id: str,
    doc_id: str,
    ast_data: Dict[str, Any],
    focus_mode: str = 'review',
    vault_keys: Optional[Dict[str, str]] = None,
    font_style: Optional[str] = None,
    graph_style: Optional[str] = None,
    table_style: Optional[str] = None,
    selected_graphs: Optional[List[str]] = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Generate PDF from canvas AST.
    
    Args:
        case_id: Case identifier
        doc_id: Document identifier
        ast_data: Canvas AST data
        focus_mode: Export mode
    
    Returns:
        Tuple of (pdf_bytes, manifest_dict)
    """
    service = ReportLabPDFService(
        case_id,
        doc_id,
        focus_mode,
        font_style=font_style,
        graph_style=graph_style,
        table_style=table_style,
        selected_graphs=selected_graphs,
    )
    pdf_bytes = service.convert_canvas_to_pdf(ast_data, vault_keys=vault_keys)
    manifest = service.get_generation_manifest()
    
    return pdf_bytes, manifest
