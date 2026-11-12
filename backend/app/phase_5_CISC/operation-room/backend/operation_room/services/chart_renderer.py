"""
Chart Renderer Service

Converts chart data (JSON) to PNG images for embedding in PDF reports.
Uses matplotlib for static chart generation.
"""

import logging
import io
import base64
import uuid
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import matplotlib - handle gracefully if not available
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-GUI backend for server use
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.colors import LinearSegmentedColormap
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - chart rendering will be limited")


# Chart color schemes
NFLIP_COLORS = {
    "primary": "#2563eb",      # Blue
    "secondary": "#7c3aed",    # Purple
    "success": "#10b981",      # Green
    "warning": "#f59e0b",      # Orange
    "danger": "#ef4444",       # Red
    "info": "#06b6d4",         # Cyan
    "neutral": "#6b7280",      # Gray
    "background": "#1f2937",   # Dark background
    "text": "#f3f4f6"          # Light text
}

RISK_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH": "#ef4444",
    "MEDIUM": "#f59e0b",
    "LOW": "#10b981",
    "INFO": "#6b7280"
}


@dataclass
class ChartImage:
    """Rendered chart image."""
    chart_id: str
    chart_type: str
    title: str
    image_data: bytes  # PNG bytes
    image_base64: str  # Base64 encoded
    width: int
    height: int
    content_hash: str
    created_at: datetime
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chart_id": self.chart_id,
            "chart_type": self.chart_type,
            "title": self.title,
            "image_base64": self.image_base64,
            "width": self.width,
            "height": self.height,
            "content_hash": self.content_hash,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    def get_buffer(self) -> io.BytesIO:
        """Get image data as BytesIO buffer for PDF embedding."""
        return io.BytesIO(self.image_data)


# Chart type mapping for unified rendering
CHART_TYPE_MAP = {
    'area-chart': 'timeline_area',
    'area': 'timeline_area',
    'timeline': 'timeline_area',
    'bar-chart': 'bar',
    'bar': 'bar',
    'scatter': 'scatter',
    'scatter-plot': 'scatter',
    'pie': 'pie',
    'pie-chart': 'pie',
    'heatmap': 'heatmap',
    'heat-map': 'heatmap',
    'gauge': 'gauge',
    'risk-gauge': 'gauge',
    'shap-waterfall': 'shap_waterfall',
    'shap': 'shap_waterfall',
    'waterfall': 'shap_waterfall',
    'network-flow': 'network_flow',
    'sankey': 'network_flow',
    'correlation-graph': 'correlation',
    'correlation': 'correlation',
    'network-graph': 'correlation',
    'top-anomalies': 'top_anomalies',
    'anomalies': 'top_anomalies',
    'exfiltration': 'exfiltration',
}


class ChartRenderer:
    """
    Service for rendering chart data to PNG images.
    
    Supports high-DPI rendering for print-quality PDF embedding.
    Phase 2: Enhanced with all chart types and buffer output.
    """
    
    # Default DPI settings
    SCREEN_DPI = 150   # For screen display
    PRINT_DPI = 200    # For print-quality PDF embedding
    
    def __init__(self, style: str = "dark", dpi: int = None, for_pdf: bool = False):
        """
        Initialize chart renderer.
        
        Args:
            style: Chart style - "dark" or "light"
            dpi: Custom DPI (overrides defaults)
            for_pdf: If True, use higher DPI for print quality
        """
        self.style = style
        self.for_pdf = for_pdf
        self.dpi = dpi or (self.PRINT_DPI if for_pdf else self.SCREEN_DPI)
        self._setup_style()
    
    def _setup_style(self):
        """Configure matplotlib style."""
        if not MATPLOTLIB_AVAILABLE:
            return
        
        if self.style == "dark":
            plt.style.use('dark_background')
            self.bg_color = NFLIP_COLORS["background"]
            self.text_color = NFLIP_COLORS["text"]
            self.grid_color = "#374151"
        else:
            plt.style.use('default')
            self.bg_color = "#ffffff"
            self.text_color = "#1f2937"
            self.grid_color = "#e5e7eb"
    
    def _create_figure(self, figsize: Tuple[int, int] = (10, 6)) -> Tuple[Any, Any]:
        """Create a matplotlib figure with consistent styling."""
        fig, ax = plt.subplots(figsize=figsize, facecolor=self.bg_color)
        ax.set_facecolor(self.bg_color)
        ax.tick_params(colors=self.text_color)
        ax.xaxis.label.set_color(self.text_color)
        ax.yaxis.label.set_color(self.text_color)
        ax.title.set_color(self.text_color)
        for spine in ax.spines.values():
            spine.set_color(self.grid_color)
        return fig, ax
    
    def _figure_to_image(self, fig, title: str, chart_type: str, metadata: Dict = None) -> ChartImage:
        """Convert matplotlib figure to ChartImage."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight', 
                    facecolor=self.bg_color, edgecolor='none')
        buf.seek(0)
        image_data = buf.read()
        buf.close()
        plt.close(fig)
        
        # Compute hash
        content_hash = hashlib.sha256(image_data).hexdigest()[:16]
        
        return ChartImage(
            chart_id=f"chart-{uuid.uuid4().hex[:8]}",
            chart_type=chart_type,
            title=title,
            image_data=image_data,
            image_base64=base64.b64encode(image_data).decode('utf-8'),
            width=int(fig.get_figwidth() * self.dpi),
            height=int(fig.get_figheight() * self.dpi),
            content_hash=content_hash,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
    
    def render_to_buffer(
        self,
        chart_type: str,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        width: int = 400,
        height: int = 300,
        title: str = "",
        **kwargs
    ) -> io.BytesIO:
        """
        Render a chart to BytesIO buffer for direct PDF embedding.
        
        This is the primary method for Phase 2 ReportLab integration.
        
        Args:
            chart_type: Type of chart (see CHART_TYPE_MAP for aliases)
            data: Chart data (format depends on chart type)
            width: Width in pixels (will be converted to figsize)
            height: Height in pixels (will be converted to figsize)
            title: Chart title
            **kwargs: Additional arguments for specific chart types
            
        Returns:
            BytesIO buffer containing PNG image data
        """
        # Normalize chart type
        normalized_type = CHART_TYPE_MAP.get(chart_type.lower(), chart_type.lower())
        
        # Convert pixels to inches (figsize)
        figsize = (width / 100, height / 100)
        
        # Route to specific renderer
        chart_image = self._render_by_type(normalized_type, data, title, figsize, **kwargs)
        
        return chart_image.get_buffer()
    
    def _render_by_type(
        self,
        chart_type: str,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        title: str,
        figsize: Tuple[float, float],
        **kwargs
    ) -> ChartImage:
        """Route rendering to specific chart type handler."""
        renderers = {
            'timeline_area': lambda: self.render_timeline_chart(data, title=title, figsize=figsize),
            'bar': lambda: self.render_bar_chart(data, title=title, figsize=figsize, **kwargs),
            'pie': lambda: self.render_pie_chart(data, title=title, figsize=figsize),
            'heatmap': lambda: self.render_heatmap(data, title=title, figsize=figsize, **kwargs),
            'gauge': lambda: self.render_risk_gauge(data.get('value', 0) if isinstance(data, dict) else 0, title=title, figsize=figsize),
            'scatter': lambda: self.render_scatter_plot(data, title=title, figsize=figsize, threshold=kwargs.get('threshold', 0.7)),
            'shap_waterfall': lambda: self.render_shap_waterfall(data, title=title, figsize=figsize),
            'network_flow': lambda: self.render_network_flow(data, title=title, figsize=figsize),
            'correlation': lambda: self.render_correlation_graph(data, title=title, figsize=figsize),
            'top_anomalies': lambda: self.render_top_anomalies(data, title=title, figsize=figsize, max_items=kwargs.get('max_items', 10)),
            'exfiltration': lambda: self.render_exfiltration_summary(data, title=title, figsize=figsize),
        }
        
        renderer = renderers.get(chart_type)
        if renderer:
            try:
                return renderer()
            except Exception as e:
                logger.error(f"Error rendering {chart_type} chart: {e}")
                return self._placeholder_image(title or f"{chart_type} chart", chart_type, str(e))
        else:
            return self._placeholder_image(title or f"Unknown chart", chart_type, f"Unknown chart type: {chart_type}")
    
    def render_scatter_plot(
        self,
        data: List[Dict[str, Any]],
        title: str = "Anomaly Scatter Plot",
        x_field: str = "normalised_ts",
        y_field: str = "anomaly_score",
        threshold_field: str = None,
        threshold: float = 0.7,
        figsize: Tuple[int, int] = (12, 6),
        **kwargs
    ) -> ChartImage:
        """
        Render a scatter plot for anomaly detection visualization.
        
        Points above threshold are highlighted as anomalies.
        
        Args:
            data: List of dicts with x, y values and optional is_anomaly flag
            title: Chart title
            x_field: Field name for x-axis (typically timestamp)
            y_field: Field name for y-axis (anomaly score)
            threshold: Score threshold for anomaly classification
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "scatter")
        
        if not data:
            return self._placeholder_image(title, "scatter", "No data available")
        
        fig, ax = self._create_figure(figsize)
        
        # Parse data
        x_values = []
        y_values = []
        colors = []
        
        for item in data:
            try:
                x_val = item.get(x_field)
                y_val = float(item.get(y_field, 0))
                is_anomaly = item.get('is_anomaly', y_val >= threshold)
                
                # Parse timestamp if string
                if isinstance(x_val, str):
                    try:
                        x_val = datetime.fromisoformat(x_val.replace('Z', '+00:00'))
                    except:
                        x_val = len(x_values)  # Fallback to index
                
                x_values.append(x_val)
                y_values.append(y_val)
                colors.append(NFLIP_COLORS["danger"] if is_anomaly else NFLIP_COLORS["primary"])
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid scatter data point: {e}")
        
        if not x_values:
            return self._placeholder_image(title, "scatter", "No valid data points")
        
        # Plot scatter
        ax.scatter(x_values, y_values, c=colors, alpha=0.6, s=30, edgecolors='none')
        
        # Draw threshold line
        ax.axhline(y=threshold, color=NFLIP_COLORS["warning"], linestyle='--', 
                   linewidth=2, label=f'Threshold ({threshold})')
        
        # Fill above threshold
        ax.fill_between(
            ax.get_xlim(), threshold, 1.1,
            alpha=0.1, color=NFLIP_COLORS["danger"]
        )
        
        ax.set_xlabel("Time" if isinstance(x_values[0], datetime) else "Event Index", fontsize=10)
        ax.set_ylabel("Anomaly Score", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.legend(loc='upper right', facecolor=self.bg_color, edgecolor=self.grid_color)
        ax.grid(True, alpha=0.3, color=self.grid_color)
        ax.set_ylim(0, 1.05)
        
        # Format x-axis if dates
        if x_values and isinstance(x_values[0], datetime):
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Count anomalies
        anomaly_count = sum(1 for c in colors if c == NFLIP_COLORS["danger"])
        
        return self._figure_to_image(fig, title, "scatter", {
            "data_points": len(data),
            "anomalies": anomaly_count,
            "threshold": threshold
        })
    
    def render_shap_waterfall(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        title: str = "SHAP Feature Contributions",
        max_features: int = 10,
        figsize: Tuple[int, int] = (10, 6)
    ) -> ChartImage:
        """
        Render SHAP waterfall/bar chart showing feature contributions.
        
        Args:
            data: List of feature contributions with 'feature', 'shap_value' 
                  OR dict with 'feature_contributions' key
            title: Chart title
            max_features: Max features to display
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "shap_waterfall")
        
        # Handle nested structure
        if isinstance(data, dict):
            contributions = data.get('feature_contributions', data.get('contributions', []))
        else:
            contributions = data
        
        if not contributions:
            return self._placeholder_image(title, "shap_waterfall", "No SHAP data available")
        
        # Sort by absolute value and take top N
        sorted_contrib = sorted(
            contributions,
            key=lambda x: abs(x.get('shap_value', x.get('contribution', 0))),
            reverse=True
        )[:max_features]
        
        # Reverse for bottom-to-top display
        sorted_contrib = list(reversed(sorted_contrib))
        
        fig, ax = self._create_figure(figsize)
        
        features = [c.get('feature', c.get('name', 'Unknown'))[:25] for c in sorted_contrib]
        values = [c.get('shap_value', c.get('contribution', 0)) for c in sorted_contrib]
        
        # Color by sign (red = increases anomaly, green = decreases)
        colors = [
            NFLIP_COLORS["danger"] if v > 0 else NFLIP_COLORS["success"]
            for v in values
        ]
        
        y_pos = range(len(features))
        bars = ax.barh(y_pos, values, color=colors, alpha=0.8, height=0.7)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(features, fontsize=9)
        ax.set_xlabel("SHAP Value (Impact on Anomaly Score)", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.axvline(x=0, color=self.text_color, linewidth=0.5)
        ax.grid(True, alpha=0.3, color=self.grid_color, axis='x')
        
        # Add value labels
        for bar, val in zip(bars, values):
            label_x = val + (0.01 if val >= 0 else -0.01)
            ha = 'left' if val >= 0 else 'right'
            ax.text(label_x, bar.get_y() + bar.get_height()/2,
                   f'{val:.3f}', va='center', ha=ha, 
                   color=self.text_color, fontsize=8)
        
        plt.tight_layout()
        
        return self._figure_to_image(fig, title, "shap_waterfall", {
            "features_shown": len(features),
            "total_features": len(contributions)
        })
    
    def render_network_flow(
        self,
        data: List[Dict[str, Any]],
        title: str = "Network Flow Analysis",
        max_flows: int = 15,
        figsize: Tuple[int, int] = (12, 8)
    ) -> ChartImage:
        """
        Render network flow visualization as horizontal bar chart.
        
        Shows source→destination flows with data volume.
        
        Args:
            data: List of flow dicts with source_ip, dest_ip, total_bytes
            title: Chart title
            max_flows: Maximum flows to show
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "network_flow")
        
        if not data:
            return self._placeholder_image(title, "network_flow", "No network flow data")
        
        # Sort by bytes and take top N
        sorted_flows = sorted(
            data, 
            key=lambda x: x.get('total_bytes', x.get('bytes', 0)),
            reverse=True
        )[:max_flows]
        
        fig, ax = self._create_figure(figsize)
        
        # Create labels
        labels = []
        values = []
        colors = []
        
        for flow in sorted_flows:
            src = flow.get('source_ip', flow.get('src', 'Unknown'))
            dst = flow.get('dest_ip', flow.get('dst', 'Unknown'))
            bytes_val = flow.get('total_bytes', flow.get('bytes', 0))
            risk = flow.get('risk_level', flow.get('risk', 'LOW'))
            
            # Truncate IPs for display
            src_short = src[:15] + '...' if len(src) > 15 else src
            dst_short = dst[:15] + '...' if len(dst) > 15 else dst
            
            labels.append(f"{src_short} → {dst_short}")
            values.append(bytes_val / (1024*1024))  # Convert to MB
            colors.append(RISK_COLORS.get(risk, NFLIP_COLORS["primary"]))
        
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color=colors, alpha=0.8)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("Data Volume (MB)", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.grid(True, alpha=0.3, color=self.grid_color, axis='x')
        
        # Add value labels
        for bar, val in zip(bars, values):
            ax.text(val + max(values)*0.02, bar.get_y() + bar.get_height()/2,
                   f'{val:.2f} MB', va='center', color=self.text_color, fontsize=8)
        
        plt.tight_layout()
        
        return self._figure_to_image(fig, title, "network_flow", {
            "flows_shown": len(sorted_flows),
            "total_flows": len(data)
        })
    
    def render_correlation_graph(
        self,
        data: Dict[str, Any],
        title: str = "Entity Correlation Graph",
        figsize: Tuple[int, int] = (10, 10)
    ) -> ChartImage:
        """
        Render entity correlation/network graph.
        
        Args:
            data: Dict with 'nodes' and 'edges' lists
            title: Chart title
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "correlation")
        
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
        
        if not nodes:
            return self._placeholder_image(title, "correlation", "No graph data available")
        
        fig, ax = self._create_figure(figsize)
        
        # Simple circular layout
        n_nodes = len(nodes)
        angles = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)
        radius = 0.4
        
        # Calculate node positions
        node_positions = {}
        for i, node in enumerate(nodes):
            node_id = node.get('id', node.get('name', str(i)))
            x = 0.5 + radius * np.cos(angles[i])
            y = 0.5 + radius * np.sin(angles[i])
            node_positions[node_id] = (x, y)
        
        # Draw edges first (so nodes appear on top)
        for edge in edges:
            src = edge.get('source', edge.get('from'))
            dst = edge.get('target', edge.get('to'))
            weight = edge.get('weight', 1)
            
            if src in node_positions and dst in node_positions:
                x1, y1 = node_positions[src]
                x2, y2 = node_positions[dst]
                ax.plot([x1, x2], [y1, y2], 
                       color=self.grid_color, 
                       linewidth=min(weight, 3),
                       alpha=0.5)
        
        # Draw nodes
        for node in nodes:
            node_id = node.get('id', node.get('name'))
            node_type = node.get('type', 'default')
            node_label = node.get('label', node_id)[:12]
            
            if node_id in node_positions:
                x, y = node_positions[node_id]
                
                # Node color by type
                type_colors = {
                    'user': NFLIP_COLORS["primary"],
                    'ip': NFLIP_COLORS["secondary"],
                    'file': NFLIP_COLORS["success"],
                    'process': NFLIP_COLORS["warning"],
                    'anomaly': NFLIP_COLORS["danger"],
                }
                color = type_colors.get(node_type, NFLIP_COLORS["neutral"])
                
                # Draw node
                circle = plt.Circle((x, y), 0.05, color=color, alpha=0.8)
                ax.add_patch(circle)
                
                # Draw label
                ax.text(x, y - 0.08, node_label, ha='center', va='top',
                       fontsize=8, color=self.text_color)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color, pad=20)
        
        return self._figure_to_image(fig, title, "correlation", {
            "nodes": len(nodes),
            "edges": len(edges)
        })
    
    def render_timeline_chart(
        self,
        data: List[Dict[str, Any]],
        title: str = "Event Timeline",
        x_field: str = "timestamp",
        y_field: str = "total_events",
        anomaly_field: str = "anomaly_count",
        figsize: Tuple[int, int] = (12, 5)
    ) -> ChartImage:
        """
        Render a timeline chart showing events over time.
        
        Args:
            data: List of dicts with timestamp, total_events, anomaly_count
            title: Chart title
            x_field: Field name for x-axis (timestamp)
            y_field: Field name for y-axis (event count)
            anomaly_field: Field name for anomaly overlay
            figsize: Figure size in inches
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "timeline")
        
        if not data:
            return self._placeholder_image(title, "timeline", "No data available")
        
        fig, ax = self._create_figure(figsize)
        
        # Parse timestamps
        timestamps = []
        events = []
        anomalies = []
        
        for item in data:
            try:
                ts = item.get(x_field)
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                timestamps.append(ts)
                events.append(item.get(y_field, 0))
                anomalies.append(item.get(anomaly_field, 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping invalid timeline data point: {e}")
        
        if not timestamps:
            return self._placeholder_image(title, "timeline", "Invalid timestamp data")
        
        # Plot events as area
        ax.fill_between(timestamps, events, alpha=0.3, color=NFLIP_COLORS["primary"], label="Total Events")
        ax.plot(timestamps, events, color=NFLIP_COLORS["primary"], linewidth=2)
        
        # Plot anomalies as red overlay
        if any(a > 0 for a in anomalies):
            ax.bar(timestamps, anomalies, color=NFLIP_COLORS["danger"], alpha=0.7, 
                   width=0.02, label="Anomalies")
        
        # Formatting
        ax.set_xlabel("Time", fontsize=10)
        ax.set_ylabel("Event Count", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.legend(loc='upper right', facecolor=self.bg_color, edgecolor=self.grid_color)
        ax.grid(True, alpha=0.3, color=self.grid_color)
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        plt.xticks(rotation=45)
        
        return self._figure_to_image(fig, title, "timeline", {"data_points": len(data)})
    
    def render_heatmap(
        self,
        data: List[Dict[str, Any]],
        title: str = "Activity Heatmap",
        x_field: str = "hour",
        y_field: str = "day_of_week",
        value_field: str = "event_count",
        figsize: Tuple[int, int] = (10, 6)
    ) -> ChartImage:
        """
        Render a heatmap (e.g., hour of day vs day of week).
        
        Args:
            data: List of dicts with hour, day_of_week, event_count
            title: Chart title
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "heatmap")
        
        if not data:
            return self._placeholder_image(title, "heatmap", "No data available")
        
        # Create matrix (7 days x 24 hours)
        matrix = np.zeros((7, 24))
        
        for item in data:
            try:
                hour = int(item.get(x_field, 0))
                day = int(item.get(y_field, 0))
                value = float(item.get(value_field, 0))
                if 0 <= day < 7 and 0 <= hour < 24:
                    matrix[day, hour] = value
            except (ValueError, TypeError):
                continue
        
        fig, ax = self._create_figure(figsize)
        
        # Create custom colormap (blue to red)
        colors = ['#1e3a5f', '#2563eb', '#7c3aed', '#ef4444', '#dc2626']
        cmap = LinearSegmentedColormap.from_list('nflip', colors)
        
        # Plot heatmap
        im = ax.imshow(matrix, cmap=cmap, aspect='auto')
        
        # Labels
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        hours = [f'{h:02d}' for h in range(24)]
        
        ax.set_xticks(range(24))
        ax.set_xticklabels(hours, fontsize=8)
        ax.set_yticks(range(7))
        ax.set_yticklabels(days, fontsize=10)
        
        ax.set_xlabel("Hour of Day", fontsize=10)
        ax.set_ylabel("Day of Week", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Event Count', color=self.text_color)
        cbar.ax.yaxis.set_tick_params(color=self.text_color)
        plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=self.text_color)
        
        return self._figure_to_image(fig, title, "heatmap", {"data_points": len(data)})
    
    def render_bar_chart(
        self,
        data: List[Dict[str, Any]],
        title: str = "Distribution",
        x_field: str = "label",
        y_field: str = "value",
        color_field: Optional[str] = None,
        horizontal: bool = False,
        figsize: Tuple[int, int] = (10, 6)
    ) -> ChartImage:
        """
        Render a bar chart.
        
        Args:
            data: List of dicts with label and value
            title: Chart title
            x_field: Field for labels
            y_field: Field for values
            color_field: Optional field for bar colors
            horizontal: If True, render horizontal bars
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "bar")
        
        if not data:
            return self._placeholder_image(title, "bar", "No data available")
        
        fig, ax = self._create_figure(figsize)
        
        labels = [str(item.get(x_field, '')) for item in data]
        values = [float(item.get(y_field, 0)) for item in data]
        
        # Determine colors
        if color_field:
            colors = [RISK_COLORS.get(item.get(color_field), NFLIP_COLORS["primary"]) for item in data]
        else:
            colors = [NFLIP_COLORS["primary"]] * len(data)
        
        if horizontal:
            bars = ax.barh(labels, values, color=colors, alpha=0.8)
            ax.set_xlabel("Value", fontsize=10)
        else:
            bars = ax.bar(labels, values, color=colors, alpha=0.8)
            ax.set_ylabel("Value", fontsize=10)
            plt.xticks(rotation=45, ha='right')
        
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.grid(True, alpha=0.3, color=self.grid_color, axis='y' if not horizontal else 'x')
        
        # Add value labels
        for bar, val in zip(bars, values):
            if horizontal:
                ax.text(val + max(values)*0.01, bar.get_y() + bar.get_height()/2,
                       f'{val:.0f}', va='center', color=self.text_color, fontsize=9)
            else:
                ax.text(bar.get_x() + bar.get_width()/2, val + max(values)*0.01,
                       f'{val:.0f}', ha='center', color=self.text_color, fontsize=9)
        
        plt.tight_layout()
        return self._figure_to_image(fig, title, "bar", {"data_points": len(data)})
    
    def render_pie_chart(
        self,
        data: Dict[str, Any],
        title: str = "Distribution",
        figsize: Tuple[int, int] = (8, 8)
    ) -> ChartImage:
        """
        Render a pie chart.
        
        Args:
            data: Dict with label -> value mapping
            title: Chart title
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "pie")
        
        if not data:
            return self._placeholder_image(title, "pie", "No data available")
        
        fig, ax = self._create_figure(figsize)
        
        labels = list(data.keys())
        values = [float(v) for v in data.values()]
        
        # Generate colors
        colors = [NFLIP_COLORS["primary"], NFLIP_COLORS["secondary"], 
                  NFLIP_COLORS["success"], NFLIP_COLORS["warning"],
                  NFLIP_COLORS["danger"], NFLIP_COLORS["info"]]
        while len(colors) < len(labels):
            colors.extend(colors)
        
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=colors[:len(labels)],
            autopct='%1.1f%%', startangle=90,
            textprops={'color': self.text_color}
        )
        
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        
        return self._figure_to_image(fig, title, "pie", {"categories": len(data)})
    
    def render_risk_gauge(
        self,
        score: float,
        title: str = "Risk Score",
        max_score: float = 1.0,
        figsize: Tuple[int, int] = (6, 4)
    ) -> ChartImage:
        """
        Render a risk gauge/meter.
        
        Args:
            score: Current score (0-max_score)
            title: Chart title
            max_score: Maximum possible score
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "gauge")
        
        fig, ax = self._create_figure(figsize)
        
        # Normalize score
        normalized = min(score / max_score, 1.0)
        
        # Create semicircle gauge
        theta = np.linspace(0, np.pi, 100)
        
        # Background arc
        ax.plot(np.cos(theta), np.sin(theta), color=self.grid_color, linewidth=20, solid_capstyle='round')
        
        # Colored arc based on score
        if normalized > 0:
            score_theta = np.linspace(0, np.pi * normalized, 100)
            
            # Color gradient based on risk
            if normalized <= 0.3:
                color = NFLIP_COLORS["success"]
            elif normalized <= 0.5:
                color = NFLIP_COLORS["warning"]
            elif normalized <= 0.7:
                color = NFLIP_COLORS["danger"]
            else:
                color = RISK_COLORS["CRITICAL"]
            
            ax.plot(np.cos(score_theta), np.sin(score_theta), color=color, 
                   linewidth=20, solid_capstyle='round')
        
        # Score text in center
        risk_level = "LOW" if normalized <= 0.3 else ("MEDIUM" if normalized <= 0.5 else ("HIGH" if normalized <= 0.7 else "CRITICAL"))
        ax.text(0, 0.2, f'{score:.2f}', ha='center', va='center', 
               fontsize=24, fontweight='bold', color=self.text_color)
        ax.text(0, -0.1, risk_level, ha='center', va='center',
               fontsize=14, color=RISK_COLORS.get(risk_level, self.text_color))
        
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.3, 1.3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color, pad=20)
        
        return self._figure_to_image(fig, title, "gauge", {"score": score, "max_score": max_score})
    
    def render_top_anomalies(
        self,
        data: List[Dict[str, Any]],
        title: str = "Top Anomalies",
        max_items: int = 10,
        figsize: Tuple[int, int] = (10, 6)
    ) -> ChartImage:
        """
        Render top anomalies as horizontal bar chart.
        
        Args:
            data: List of anomaly dicts with anomaly_score, event_id, timestamp
            title: Chart title
            max_items: Maximum items to show
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "bar")
        
        if not data:
            return self._placeholder_image(title, "bar", "No anomalies detected")
        
        # Sort by score and take top N
        sorted_data = sorted(data, key=lambda x: x.get('anomaly_score', 0), reverse=True)[:max_items]
        
        fig, ax = self._create_figure(figsize)
        
        labels = [f"{d.get('event_id', 'Unknown')[:20]}..." for d in sorted_data]
        scores = [d.get('anomaly_score', 0) for d in sorted_data]
        
        # Color by score
        colors = []
        for score in scores:
            if score >= 0.9:
                colors.append(RISK_COLORS["CRITICAL"])
            elif score >= 0.7:
                colors.append(RISK_COLORS["HIGH"])
            elif score >= 0.5:
                colors.append(RISK_COLORS["MEDIUM"])
            else:
                colors.append(RISK_COLORS["LOW"])
        
        y_pos = range(len(labels))
        bars = ax.barh(y_pos, scores, color=colors, alpha=0.8)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Anomaly Score", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        ax.set_xlim(0, 1.1)
        ax.grid(True, alpha=0.3, color=self.grid_color, axis='x')
        
        # Add score labels
        for bar, score in zip(bars, scores):
            ax.text(score + 0.02, bar.get_y() + bar.get_height()/2,
                   f'{score:.2f}', va='center', color=self.text_color, fontsize=9)
        
        plt.tight_layout()
        return self._figure_to_image(fig, title, "top_anomalies", {"count": len(sorted_data)})
    
    def render_exfiltration_summary(
        self,
        data: List[Dict[str, Any]],
        title: str = "Exfiltration Candidates",
        figsize: Tuple[int, int] = (12, 6)
    ) -> ChartImage:
        """
        Render exfiltration candidates summary.
        
        Args:
            data: List of exfil candidates with source_ip, total_bytes, risk_level
            title: Chart title
            figsize: Figure size
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._placeholder_image(title, "bar")
        
        if not data:
            return self._placeholder_image(title, "bar", "No exfiltration candidates")
        
        # Sort by bytes
        sorted_data = sorted(data, key=lambda x: x.get('total_bytes', 0), reverse=True)[:10]
        
        fig, ax = self._create_figure(figsize)
        
        labels = [d.get('source_ip', 'Unknown') for d in sorted_data]
        bytes_mb = [d.get('total_bytes', 0) / (1024*1024) for d in sorted_data]
        risk_levels = [d.get('risk_level', 'LOW') for d in sorted_data]
        
        colors = [RISK_COLORS.get(r, NFLIP_COLORS["neutral"]) for r in risk_levels]
        
        bars = ax.bar(labels, bytes_mb, color=colors, alpha=0.8)
        
        ax.set_xlabel("Source IP", fontsize=10)
        ax.set_ylabel("Data Transferred (MB)", fontsize=10)
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
        plt.xticks(rotation=45, ha='right')
        ax.grid(True, alpha=0.3, color=self.grid_color, axis='y')
        
        # Add value labels
        for bar, val, risk in zip(bars, bytes_mb, risk_levels):
            ax.text(bar.get_x() + bar.get_width()/2, val + max(bytes_mb)*0.02,
                   f'{val:.1f}MB\n({risk})', ha='center', color=self.text_color, fontsize=8)
        
        plt.tight_layout()
        return self._figure_to_image(fig, title, "exfiltration", {"candidates": len(sorted_data)})
    
    def _placeholder_image(self, title: str, chart_type: str, message: str = "Chart not available") -> ChartImage:
        """Create a placeholder image when rendering fails or matplotlib unavailable."""
        # Create simple text-based placeholder
        if MATPLOTLIB_AVAILABLE:
            fig, ax = self._create_figure((6, 4))
            ax.text(0.5, 0.5, message, ha='center', va='center', 
                   fontsize=14, color=self.text_color)
            ax.set_title(title, fontsize=12, fontweight='bold', color=self.text_color)
            ax.axis('off')
            return self._figure_to_image(fig, title, chart_type, {"placeholder": True})
        else:
            # Return minimal placeholder
            return ChartImage(
                chart_id=f"chart-{uuid.uuid4().hex[:8]}",
                chart_type=chart_type,
                title=title,
                image_data=b'',
                image_base64='',
                width=0,
                height=0,
                content_hash='placeholder',
                created_at=datetime.utcnow(),
                metadata={"placeholder": True, "message": message}
            )
    
    def render_module_charts(
        self,
        module_name: str,
        module_data: Dict[str, Any]
    ) -> List[ChartImage]:
        """
        Render all charts for a specific module's output.
        
        Args:
            module_name: Name of the module (anomaly, network, crud, depth)
            module_data: Module output data containing chart data
        """
        charts = []
        
        if module_name == "anomaly":
            chart_data = module_data.get("charts", {})
            
            if chart_data.get("timeline"):
                charts.append(self.render_timeline_chart(
                    chart_data["timeline"],
                    title="Anomaly Timeline"
                ))
            
            if chart_data.get("heatmap"):
                charts.append(self.render_heatmap(
                    chart_data["heatmap"],
                    title="Activity Heatmap"
                ))
            
            if chart_data.get("top_anomalies"):
                charts.append(self.render_top_anomalies(
                    chart_data["top_anomalies"],
                    title="Top Anomalies by Score"
                ))
            
            # Score distribution
            if module_data.get("score_distribution"):
                dist_data = [
                    {"label": d["bucket"], "value": d["count"]}
                    for d in module_data["score_distribution"]
                ]
                charts.append(self.render_bar_chart(
                    dist_data,
                    title="Anomaly Score Distribution",
                    x_field="label",
                    y_field="value"
                ))
        
        elif module_name == "network":
            exfil = module_data.get("exfiltration_candidates", [])
            if exfil:
                charts.append(self.render_exfiltration_summary(
                    exfil,
                    title="Exfiltration Candidates"
                ))
        
        elif module_name == "crud":
            by_op = module_data.get("by_operation", {})
            if by_op:
                charts.append(self.render_pie_chart(
                    by_op,
                    title="Operations by Type"
                ))
            
            by_sens = module_data.get("by_sensitivity", {})
            if by_sens:
                charts.append(self.render_bar_chart(
                    [{"label": k, "value": v, "risk": k} for k, v in by_sens.items()],
                    title="Events by Sensitivity",
                    color_field="risk"
                ))
        
        elif module_name == "depth":
            impact = module_data.get("impact_score", {})
            if impact.get("overall") is not None:
                charts.append(self.render_risk_gauge(
                    impact["overall"],
                    title="Impact Score"
                ))
            
            dims = module_data.get("dimensions", {})
            if dims:
                charts.append(self.render_bar_chart(
                    [{"label": k, "value": v} for k, v in dims.items()],
                    title="Impact Dimensions",
                    horizontal=True
                ))
        
        return charts


def get_chart_renderer(style: str = "dark", for_pdf: bool = False, dpi: int = None) -> ChartRenderer:
    """
    Factory function to get a chart renderer instance.
    
    Args:
        style: Chart style - "dark" or "light"
        for_pdf: If True, use higher DPI (200) for print quality
        dpi: Custom DPI (overrides defaults)
    
    Returns:
        ChartRenderer instance
    """
    return ChartRenderer(style=style, for_pdf=for_pdf, dpi=dpi)


def get_pdf_chart_renderer(style: str = "light") -> ChartRenderer:
    """
    Get a chart renderer optimized for PDF embedding.
    
    Uses light style (better for print) and 200 DPI for quality.
    """
    return ChartRenderer(style=style, for_pdf=True, dpi=200)
