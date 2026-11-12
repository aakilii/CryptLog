"""
Widget Renderers for ReportLab PDF Generation.

Phase 3: Dedicated renderers for all widget/component types.
Separates rendering logic from main PDF service for maintainability.
"""

import io
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

from operation_room.services.coordinate_mapper import BoundingBox
from operation_room.services.font_manager import NFLIPColors, FontStyles, FontManager
from operation_room.services.chart_renderer import get_pdf_chart_renderer, ChartRenderer

logger = logging.getLogger(__name__)


@dataclass
class RenderContext:
    """Context passed to all widget renderers."""
    canvas: Canvas
    focus_mode: str  # 'review', 'story', 'evidence', 'redact'
    vault_keys: Dict[str, str] = None  # For redact mode: key -> value mapping
    styles: Dict[str, ParagraphStyle] = None
    chart_renderer: ChartRenderer = None
    font_family: str = 'Helvetica'
    graph_style: str = 'light'
    table_style: str = 'clean'
    selected_graphs: List[str] = None
    
    def __post_init__(self):
        if self.vault_keys is None:
            self.vault_keys = {}
        if self.selected_graphs is None:
            self.selected_graphs = []
        if self.chart_renderer is None:
            self.chart_renderer = get_pdf_chart_renderer(style=self.graph_style)


class WidgetRenderer(ABC):
    """Base class for all widget renderers."""
    
    @abstractmethod
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        """Render the widget to the PDF canvas."""
        pass
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters for ReportLab Paragraph."""
        if not text:
            return ""
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
    
    def _apply_redaction(self, text: str, ctx: RenderContext) -> str:
        """Apply redaction if in redact mode - replace values with keys."""
        if ctx.focus_mode != 'redact' or not ctx.vault_keys:
            return text
        
        # Replace known values with their keys
        result = text
        for key, value in ctx.vault_keys.items():
            if value and value in result:
                result = result.replace(value, f"[{key}]")
        return result


class TextRenderer(WidgetRenderer):
    """Renders text elements with rich formatting."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        content = data.get('content', data.get('text', ''))
        style_data = data.get('style', {})
        
        if not content:
            return
        
        # Apply redaction if needed
        content = self._apply_redaction(content, ctx)
        
        # Get font properties
        font_size = style_data.get('fontSize', 12)
        font_weight = style_data.get('fontWeight', 'normal')
        text_align = style_data.get('textAlign', 'left')
        color = style_data.get('color', NFLIPColors.TEXT_PRIMARY)
        
        font_manager = FontManager()
        font_name = font_manager.get_font_name(
            family=ctx.font_family,
            weight='bold' if font_weight == 'bold' else 'normal',
            style='italic' if style_data.get('fontStyle') == 'italic' else 'normal'
        )
        
        # Create paragraph style
        alignment = {'left': TA_LEFT, 'center': TA_CENTER, 'right': TA_RIGHT}.get(text_align, TA_LEFT)
        
        para_style = ParagraphStyle(
            'TextStyle',
            fontName=font_name,
            fontSize=font_size,
            leading=font_size * 1.3,
            textColor=HexColor(color) if isinstance(color, str) else color,
            alignment=alignment,
        )
        
        # Render paragraph
        para = Paragraph(self._escape_html(content), para_style)
        w, h = para.wrap(bbox.width, bbox.height)
        para.drawOn(ctx.canvas, bbox.x, bbox.y + bbox.height - h)


class MetricRenderer(WidgetRenderer):
    """Renders metric cards with large value display."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        value = data.get('value', data.get('metric', '0'))
        label = data.get('label', data.get('title', ''))
        unit = data.get('unit', '')
        trend = data.get('trend', None)  # 'up', 'down', or None
        
        # Apply redaction
        value = self._apply_redaction(str(value), ctx)
        label = self._apply_redaction(str(label), ctx)
        
        canvas = ctx.canvas
        
        # Value (large)
        canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        canvas.setFont('Helvetica-Bold', 28)
        
        value_text = f"{value}{unit}" if unit else str(value)
        canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 36, value_text)
        
        # Trend indicator
        if trend:
            trend_color = NFLIPColors.SUCCESS if trend == 'up' else NFLIPColors.DANGER
            canvas.setFillColor(HexColor(trend_color))
            canvas.setFont('Helvetica', 12)
            arrow = '↑' if trend == 'up' else '↓'
            canvas.drawString(bbox.x + 8 + canvas.stringWidth(value_text, 'Helvetica-Bold', 28) + 8, 
                            bbox.y + bbox.height - 36, arrow)
        
        # Label (small)
        canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        canvas.setFont('Helvetica', 10)
        canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 54, label)


class FindingRenderer(WidgetRenderer):
    """Renders finding cards with severity indicator."""
    
    SEVERITY_LABELS = {
        'critical': ('CRITICAL', NFLIPColors.DANGER),
        'high': ('HIGH', '#dc2626'),
        'medium': ('MEDIUM', NFLIPColors.WARNING),
        'low': ('LOW', NFLIPColors.SUCCESS),
        'info': ('INFO', NFLIPColors.TEXT_SECONDARY),
    }
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        severity = data.get('severity', 'info').lower()
        title = data.get('title', '')
        summary = data.get('summary', data.get('content', ''))
        
        # Apply redaction
        title = self._apply_redaction(title, ctx)
        summary = self._apply_redaction(summary, ctx)
        
        canvas = ctx.canvas
        
        # Get severity styling
        label, color = self.SEVERITY_LABELS.get(severity, ('INFO', NFLIPColors.TEXT_SECONDARY))
        
        # Severity indicator bar on left
        canvas.setFillColor(HexColor(color))
        canvas.rect(bbox.x, bbox.y, 4, bbox.height, fill=1, stroke=0)
        
        # Severity badge
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(bbox.x + 10, bbox.y + bbox.height - 16, label)
        
        # Title
        if title:
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            canvas.setFont('Helvetica-Bold', 11)
            canvas.drawString(bbox.x + 10, bbox.y + bbox.height - 32, title[:50])
        
        # Summary text
        if summary and ctx.styles:
            style = ctx.styles.get('NFLIPBody', ParagraphStyle('Body', fontSize=9))
            para = Paragraph(self._escape_html(summary), style)
            w, h = para.wrap(bbox.width - 16, bbox.height - 40)
            para.drawOn(ctx.canvas, bbox.x + 10, bbox.y + bbox.height - 40 - h)


class TableRenderer(WidgetRenderer):
    """Renders data tables with alternating row colors."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        rows = data.get('rows', data.get('data', []))
        headers = data.get('headers', [])
        
        if not rows:
            self._render_empty(bbox, ctx, "No data")
            return
        
        # Build table data
        table_data = []
        
        if headers:
            table_data.append(headers)
        elif rows and isinstance(rows[0], dict):
            headers = list(rows[0].keys())
            table_data.append(headers)
        
        # Add rows (limit to fit)
        max_rows = min(len(rows), 15)
        for row in rows[:max_rows]:
            if isinstance(row, dict):
                row_data = [self._apply_redaction(str(row.get(h, '')), ctx)[:30] for h in headers]
            else:
                row_data = [self._apply_redaction(str(v), ctx)[:30] for v in row]
            table_data.append(row_data)
        
        if not table_data:
            self._render_empty(bbox, ctx, "No data")
            return
        
        # Calculate column widths
        col_count = len(table_data[0]) if table_data else 1
        col_width = (bbox.width - 16) / col_count
        
        # Create table
        table = Table(table_data, colWidths=[col_width] * col_count)
        
        # Style table
        header_bg = '#e5e7eb'
        row_bgs = [HexColor('#ffffff'), HexColor('#f9fafb')]
        grid_color = '#d1d5db'
        if ctx.table_style == 'dense':
            header_bg = '#dbeafe'
            row_bgs = [HexColor('#ffffff'), HexColor('#eff6ff')]
            grid_color = '#bfdbfe'
        elif ctx.table_style == 'executive':
            header_bg = '#111827'
            row_bgs = [HexColor('#ffffff'), HexColor('#f3f4f6')]
            grid_color = '#9ca3af'

        font_manager = FontManager()
        header_font = font_manager.get_font_name(ctx.font_family, 'bold', 'normal')

        style = TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), header_font),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TEXTCOLOR', (0, 0), (-1, -1), HexColor(NFLIPColors.TEXT_PRIMARY)),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor(header_bg)),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), row_bgs),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor(grid_color)),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ])
        table.setStyle(style)
        
        # Draw table
        w, h = table.wrap(bbox.width - 16, bbox.height - 24)
        table.drawOn(ctx.canvas, bbox.x + 8, bbox.y + bbox.height - 20 - h)
    
    def _render_empty(self, bbox: BoundingBox, ctx: RenderContext, message: str) -> None:
        ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        ctx.canvas.setFont('Helvetica-Oblique', 10)
        ctx.canvas.drawString(bbox.x + 8, bbox.y + bbox.height / 2, message)


class ChartRenderer(WidgetRenderer):
    """Renders chart components via matplotlib."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        chart_type = data.get('chartType', data.get('type', 'bar'))
        chart_data = data.get('data', data.get('chartData', []))
        title = data.get('title', data.get('label', ''))
        config = data.get('config', {})
        threshold = config.get('threshold', 0.7)
        
        try:
            # Render chart to buffer
            chart_width = int(bbox.width * 1.5)
            chart_height = int(bbox.height * 1.5)
            
            chart_buffer = ctx.chart_renderer.render_to_buffer(
                chart_type=chart_type,
                data=chart_data,
                width=chart_width,
                height=chart_height,
                title=title,
                threshold=threshold
            )
            
            # Embed in PDF
            img = ImageReader(chart_buffer)
            padding = 4
            ctx.canvas.drawImage(
                img,
                bbox.x + padding,
                bbox.y + padding,
                width=bbox.width - (padding * 2),
                height=bbox.height - (padding * 2),
                preserveAspectRatio=True,
                mask='auto'
            )
            
        except Exception as e:
            logger.error(f"Chart render error: {e}")
            self._render_placeholder(bbox, ctx, chart_type, str(e))
    
    def _render_placeholder(self, bbox: BoundingBox, ctx: RenderContext, 
                           chart_type: str, error: str = None) -> None:
        ctx.canvas.setFillColor(HexColor('#e2e8f0'))
        ctx.canvas.roundRect(bbox.x + 8, bbox.y + 8, bbox.width - 16, bbox.height - 32,
                            radius=4, fill=1, stroke=0)
        
        ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        ctx.canvas.setFont('Helvetica', 10)
        label = f"[{chart_type.upper()} CHART]"
        label_width = ctx.canvas.stringWidth(label, 'Helvetica', 10)
        ctx.canvas.drawString(bbox.x + (bbox.width - label_width) / 2,
                             bbox.y + bbox.height / 2, label)


class TimelineEventRenderer(WidgetRenderer):
    """Renders individual timeline event cards."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        timestamp = data.get('timestamp', data.get('normalised_ts', ''))
        source = data.get('source_type', '')
        action = data.get('action', '')
        actor = data.get('actor', '')
        severity = data.get('severity', 'INFO')
        
        # Apply redaction
        actor = self._apply_redaction(actor, ctx)
        action = self._apply_redaction(action, ctx)
        
        canvas = ctx.canvas
        
        # Severity color bar
        severity_color = NFLIPColors.get_severity_color(severity)
        canvas.setFillColor(HexColor(severity_color))
        canvas.rect(bbox.x, bbox.y, 3, bbox.height, fill=1, stroke=0)
        
        y_pos = bbox.y + bbox.height - 16
        
        # Timestamp
        canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
        canvas.setFont('Courier', 8)
        ts_display = timestamp[:19] if timestamp else ''
        canvas.drawString(bbox.x + 8, y_pos, ts_display)
        
        y_pos -= 14
        
        # Source badge
        canvas.setFillColor(HexColor(NFLIPColors.PRIMARY))
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(bbox.x + 8, y_pos, source)
        
        y_pos -= 12
        
        # Action
        canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        canvas.setFont('Helvetica', 9)
        canvas.drawString(bbox.x + 8, y_pos, action[:40] if action else '')
        
        y_pos -= 12
        
        # Actor
        if actor:
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            canvas.setFont('Helvetica', 8)
            canvas.drawString(bbox.x + 8, y_pos, f"Actor: {actor[:30]}")


class AnomalyRenderer(WidgetRenderer):
    """Renders anomaly detection score displays."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        score = data.get('anomaly_score', data.get('score', 0))
        is_anomaly = data.get('is_anomaly', score >= 0.65)
        model_type = data.get('model_type', '')
        
        canvas = ctx.canvas
        
        # Score color
        score_color = NFLIPColors.DANGER if is_anomaly else NFLIPColors.SUCCESS
        
        canvas.setFillColor(HexColor(score_color))
        canvas.setFont('Helvetica-Bold', 24)
        score_text = f"{score:.3f}"
        canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 34, score_text)
        
        # Status label
        status = "ANOMALY" if is_anomaly else "NORMAL"
        canvas.setFont('Helvetica', 10)
        canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 50, status)
        
        # Model type
        if model_type:
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            canvas.setFont('Helvetica', 8)
            canvas.drawString(bbox.x + 8, bbox.y + bbox.height - 64, f"Model: {model_type}")


class NetworkFlowRenderer(WidgetRenderer):
    """Renders network flow visualization."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        flows = data.get('flows', data.get('data', []))
        
        if not flows:
            ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
            ctx.canvas.setFont('Helvetica-Oblique', 10)
            ctx.canvas.drawString(bbox.x + 8, bbox.y + bbox.height / 2, "No network flows")
            return
        
        # Check if we have enough data for a chart
        if len(flows) >= 2 and bbox.height > 150:
            # Render as chart
            try:
                chart_buffer = ctx.chart_renderer.render_to_buffer(
                    chart_type='network-flow',
                    data=flows,
                    width=int(bbox.width * 1.5),
                    height=int(bbox.height * 1.5),
                    title='Network Traffic'
                )
                img = ImageReader(chart_buffer)
                ctx.canvas.drawImage(img, bbox.x + 4, bbox.y + 4,
                                    width=bbox.width - 8, height=bbox.height - 8,
                                    preserveAspectRatio=True, mask='auto')
                return
            except Exception as e:
                logger.warning(f"Network flow chart fallback: {e}")
        
        # Fallback: Simple list
        canvas = ctx.canvas
        y_pos = bbox.y + bbox.height - 20
        canvas.setFont('Helvetica', 8)
        
        for flow in flows[:5]:
            src = flow.get('source_ip', flow.get('src', ''))
            dst = flow.get('dest_ip', flow.get('dst', ''))
            bytes_val = flow.get('bytes_sent', flow.get('bytes', 0))
            
            src = self._apply_redaction(src, ctx)
            dst = self._apply_redaction(dst, ctx)
            
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            canvas.drawString(bbox.x + 8, y_pos, f"{src} → {dst}")
            
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            canvas.drawString(bbox.x + bbox.width - 70, y_pos, f"{bytes_val:,} B")
            
            y_pos -= 14


class SHAPRenderer(WidgetRenderer):
    """Renders SHAP explanation visualizations."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        contributions = data.get('feature_contributions', data.get('shap_factors', []))
        
        if not contributions:
            ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
            ctx.canvas.setFont('Helvetica-Oblique', 10)
            ctx.canvas.drawString(bbox.x + 8, bbox.y + bbox.height / 2, "No SHAP data")
            return
        
        # If enough space and data, render as chart
        if len(contributions) >= 3 and bbox.height > 150:
            try:
                chart_buffer = ctx.chart_renderer.render_to_buffer(
                    chart_type='shap-waterfall',
                    data=contributions,
                    width=int(bbox.width * 1.5),
                    height=int(bbox.height * 1.5),
                    title='Feature Impact'
                )
                img = ImageReader(chart_buffer)
                ctx.canvas.drawImage(img, bbox.x + 4, bbox.y + 4,
                                    width=bbox.width - 8, height=bbox.height - 8,
                                    preserveAspectRatio=True, mask='auto')
                return
            except Exception as e:
                logger.warning(f"SHAP chart fallback: {e}")
        
        # Fallback: Simple bar display
        canvas = ctx.canvas
        y_pos = bbox.y + bbox.height - 24
        bar_max_width = bbox.width * 0.4
        
        for contrib in contributions[:5]:
            feature = contrib.get('feature', contrib.get('factor', ''))
            value = contrib.get('shap_value', contrib.get('contribution', 0))
            
            feature = self._apply_redaction(feature, ctx)
            
            # Feature name
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
            canvas.setFont('Helvetica', 8)
            canvas.drawString(bbox.x + 8, y_pos, feature[:20])
            
            # Bar
            bar_width = abs(value) * bar_max_width
            bar_color = NFLIPColors.DANGER if value > 0 else NFLIPColors.SUCCESS
            
            canvas.setFillColor(HexColor(bar_color))
            canvas.rect(bbox.x + bbox.width * 0.4, y_pos - 2, bar_width, 10, fill=1, stroke=0)
            
            # Value
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            canvas.setFont('Helvetica', 7)
            canvas.drawString(bbox.x + bbox.width * 0.4 + bar_width + 4, y_pos, f"{value:.3f}")
            
            y_pos -= 16


class CorrelationRenderer(WidgetRenderer):
    """Renders correlation/network graph visualizations."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        nodes = data.get('nodes', [])
        edges = data.get('edges', data.get('links', []))
        
        if not nodes:
            ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
            ctx.canvas.setFont('Helvetica-Oblique', 10)
            ctx.canvas.drawString(bbox.x + 8, bbox.y + bbox.height / 2, "No correlation data")
            return
        
        try:
            chart_buffer = ctx.chart_renderer.render_to_buffer(
                chart_type='correlation-graph',
                data={'nodes': nodes, 'edges': edges},
                width=int(bbox.width * 1.5),
                height=int(bbox.height * 1.5),
                title=data.get('title', 'Entity Correlation')
            )
            img = ImageReader(chart_buffer)
            ctx.canvas.drawImage(img, bbox.x + 4, bbox.y + 4,
                                width=bbox.width - 8, height=bbox.height - 8,
                                preserveAspectRatio=True, mask='auto')
        except Exception as e:
            logger.error(f"Correlation graph error: {e}")
            ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
            ctx.canvas.setFont('Helvetica', 10)
            ctx.canvas.drawString(bbox.x + bbox.width / 2 - 60, bbox.y + bbox.height / 2,
                                 "[CORRELATION GRAPH]")


class ImageRenderer(WidgetRenderer):
    """Renders embedded images."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        image_src = data.get('src', data.get('url', ''))
        
        if not image_src:
            self._render_placeholder(bbox, ctx)
            return
        
        try:
            if image_src.startswith('data:image'):
                # Base64 encoded
                import base64
                header, encoded = image_src.split(',', 1)
                image_data = base64.b64decode(encoded)
                img = ImageReader(io.BytesIO(image_data))
            else:
                # File path or URL
                img = ImageReader(image_src)
            
            padding = 4
            ctx.canvas.drawImage(
                img,
                bbox.x + padding,
                bbox.y + padding,
                width=bbox.width - (padding * 2),
                height=bbox.height - (padding * 2),
                preserveAspectRatio=True,
                mask='auto'
            )
        except Exception as e:
            logger.error(f"Image render error: {e}")
            self._render_placeholder(bbox, ctx)
    
    def _render_placeholder(self, bbox: BoundingBox, ctx: RenderContext) -> None:
        ctx.canvas.setFillColor(HexColor('#f1f5f9'))
        ctx.canvas.rect(bbox.x + 8, bbox.y + 8, bbox.width - 16, bbox.height - 16,
                       fill=1, stroke=0)
        ctx.canvas.setFillColor(HexColor(NFLIPColors.TEXT_MUTED))
        ctx.canvas.setFont('Helvetica', 10)
        ctx.canvas.drawString(bbox.x + bbox.width / 2 - 30, bbox.y + bbox.height / 2, "[IMAGE]")


class ShapeRenderer(WidgetRenderer):
    """Renders basic shapes (rectangles, circles, lines)."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        shape_type = data.get('shapeType', data.get('shape', 'rectangle'))
        fill_color = data.get('fillColor', data.get('fill', '#e5e7eb'))
        stroke_color = data.get('strokeColor', data.get('stroke', '#6b7280'))
        stroke_width = data.get('strokeWidth', 1)
        
        canvas = ctx.canvas
        
        canvas.setStrokeColor(HexColor(stroke_color))
        canvas.setLineWidth(stroke_width)
        
        if fill_color:
            canvas.setFillColor(HexColor(fill_color))
        
        if shape_type == 'rectangle':
            canvas.rect(bbox.x, bbox.y, bbox.width, bbox.height,
                       fill=1 if fill_color else 0, stroke=1)
        elif shape_type == 'roundedRect':
            radius = data.get('radius', 4)
            canvas.roundRect(bbox.x, bbox.y, bbox.width, bbox.height,
                           radius=radius, fill=1 if fill_color else 0, stroke=1)
        elif shape_type == 'circle':
            cx = bbox.x + bbox.width / 2
            cy = bbox.y + bbox.height / 2
            radius = min(bbox.width, bbox.height) / 2
            canvas.circle(cx, cy, radius, fill=1 if fill_color else 0, stroke=1)
        elif shape_type == 'line':
            x2 = data.get('x2', bbox.x + bbox.width)
            y2 = data.get('y2', bbox.y)
            canvas.line(bbox.x, bbox.y + bbox.height, x2, y2)


class EvidenceRenderer(WidgetRenderer):
    """Renders evidence items with hash verification display."""
    
    def render(self, data: Dict[str, Any], bbox: BoundingBox, ctx: RenderContext) -> None:
        name = data.get('name', data.get('artefact_name', 'Evidence'))
        artefact_type = data.get('type', data.get('artefact_type', 'File'))
        hash_value = data.get('hash', data.get('hash_value', ''))
        hash_algorithm = data.get('algorithm', data.get('hash_algorithm', 'SHA-256'))
        
        # Apply redaction
        name = self._apply_redaction(name, ctx)
        
        canvas = ctx.canvas
        
        # Evidence icon/badge
        canvas.setFillColor(HexColor(NFLIPColors.PRIMARY))
        canvas.rect(bbox.x, bbox.y, 4, bbox.height, fill=1, stroke=0)
        
        y_pos = bbox.y + bbox.height - 16
        
        # Type badge
        canvas.setFillColor(HexColor(NFLIPColors.INFO))
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(bbox.x + 10, y_pos, artefact_type.upper())
        
        y_pos -= 14
        
        # Name
        canvas.setFillColor(HexColor(NFLIPColors.TEXT_PRIMARY))
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(bbox.x + 10, y_pos, name[:40])
        
        y_pos -= 14
        
        # Hash
        if hash_value:
            canvas.setFillColor(HexColor(NFLIPColors.TEXT_SECONDARY))
            canvas.setFont('Courier', 7)
            hash_display = f"{hash_algorithm}: {hash_value[:32]}..."
            canvas.drawString(bbox.x + 10, y_pos, hash_display)


# Widget renderer registry
WIDGET_RENDERERS: Dict[str, WidgetRenderer] = {
    'text': TextRenderer(),
    'metric': MetricRenderer(),
    'finding': FindingRenderer(),
    'table': TableRenderer(),
    'chart': ChartRenderer(),
    'timeline-event': TimelineEventRenderer(),
    'anomaly': AnomalyRenderer(),
    'network-flow': NetworkFlowRenderer(),
    'shap-explanation': SHAPRenderer(),
    'shap': SHAPRenderer(),
    'shap-waterfall': SHAPRenderer(),
    'correlation-graph': CorrelationRenderer(),
    'correlation': CorrelationRenderer(),
    'image': ImageRenderer(),
    'shape': ShapeRenderer(),
    'evidence': EvidenceRenderer(),
    # Chart type aliases
    'area-chart': ChartRenderer(),
    'bar-chart': ChartRenderer(),
    'pie-chart': ChartRenderer(),
    'scatter': ChartRenderer(),
    'scatter-plot': ChartRenderer(),
    'heatmap': ChartRenderer(),
    'gauge': ChartRenderer(),
    'timeline': ChartRenderer(),
}


def get_widget_renderer(widget_type: str) -> WidgetRenderer:
    """Get the appropriate renderer for a widget type."""
    return WIDGET_RENDERERS.get(widget_type.lower(), WIDGET_RENDERERS.get('text'))


def render_widget(
    widget_type: str,
    data: Dict[str, Any],
    bbox: BoundingBox,
    ctx: RenderContext
) -> None:
    """Render a widget using the appropriate renderer."""
    renderer = get_widget_renderer(widget_type)
    try:
        renderer.render(data, bbox, ctx)
    except Exception as e:
        logger.error(f"Widget render error ({widget_type}): {e}")
        # Fallback: render error message
        ctx.canvas.setFillColor(HexColor(NFLIPColors.DANGER))
        ctx.canvas.setFont('Helvetica', 8)
        ctx.canvas.drawString(bbox.x + 4, bbox.y + bbox.height / 2, f"Render error: {widget_type}")
