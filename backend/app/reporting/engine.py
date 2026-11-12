"""
Report generation engine using ReportLab for PDF creation.
Adapted from the standalone report_engine project.
"""
import io
import base64
from datetime import datetime
from typing import Any, Dict, List

try:
    from reportlab.lib.utils import ImageReader
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, 
        PageBreak, Image, KeepTogether
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
except ImportError:
    raise ImportError("reportlab is required. Install with: pip install reportlab")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _num(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _fmt_dt(dt: Any) -> str:
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        try:
            x = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return x.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return dt
    if isinstance(dt, datetime):
        try:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(dt)
    return str(dt)


def _human_bytes(n: Any) -> str:
    try:
        b = int(n)
    except Exception:
        return "N/A"
    if b < 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    v = float(b)
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    if i == 0:
        return f"{int(v)} {units[i]}"
    return f"{v:.2f} {units[i]}"


def _short_hash(h: Any, n: int = 12) -> str:
    if not h or not isinstance(h, str):
        return "N/A"
    if len(h) <= n:
        return h
    return h[:n] + "…"


def _safe_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _safe_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


class GraphEngine:
    """Chart generation using matplotlib."""

    @staticmethod
    def _save_fig(dpi=150) -> io.BytesIO:
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", dpi=dpi)
        buf.seek(0)
        plt.close()
        return buf

    @staticmethod
    def pie_chart(data: Dict[str, int], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)
        if len(items) > 7:
            top = items[:6]
            other = sum(v for _, v in items[6:])
            items = top + [("other", other)]
        labels = [k for k, _ in items]
        values = [v for _, v in items]
        plt.figure(figsize=(6.4, 3.2))
        plt.pie(values, labels=labels, autopct="%1.1f%%" if sum(values) > 0 else None, 
                startangle=140, textprops={"fontsize": 8})
        plt.title(title, fontsize=10, fontweight="bold")
        return GraphEngine._save_fig()

    @staticmethod
    def bar_chart(data: Dict[str, float], title: str, xlabel: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        xs = [k for k, _ in items]
        ys = [v for _, v in items]
        plt.figure(figsize=(6.4, 3.2))
        plt.bar(xs, ys, width=0.6)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel(xlabel, fontsize=8)
        plt.xticks(rotation=35, ha="right", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def line_chart(values: List[float], title: str, ylabel: str = "Value") -> io.BytesIO:
        plt.figure(figsize=(6.4, 3.2))
        plt.plot(range(len(values)), values, linewidth=2, marker="o", markersize=4)
        if values:
            plt.fill_between(range(len(values)), values, alpha=0.12)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.ylabel(ylabel, fontsize=8)
        plt.grid(True, alpha=0.25)
        return GraphEngine._save_fig()

    @staticmethod
    def horizontal_bar(data: Dict[str, float], title: str) -> io.BytesIO:
        items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [k for k, _ in items][::-1]
        vals = [v for _, v in items][::-1]
        plt.figure(figsize=(6.4, 3.2))
        plt.barh(labels, vals)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel("Score", fontsize=8)
        plt.yticks(fontsize=8)
        plt.grid(axis="x", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()

    @staticmethod
    def hist_chart(values: List[float], title: str, xlabel: str = "Value") -> io.BytesIO:
        if not values:
            values = [0]
        plt.figure(figsize=(6.4, 3.2))
        plt.hist(values, bins=18)
        plt.title(title, fontsize=10, fontweight="bold")
        plt.xlabel(xlabel, fontsize=8)
        plt.ylabel("Count", fontsize=8)
        plt.grid(axis="y", linestyle="--", alpha=0.35)
        return GraphEngine._save_fig()


def b64_from_buf(buf: io.BytesIO) -> str:
    """Convert BytesIO buffer to base64 PNG string."""
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def generate_forensic_pdf(title: str, sections: List[Dict[str, Any]]) -> bytes:
    """
    Generate a forensic report PDF.
    
    Args:
        title: Report title
        sections: List of section dicts with 'heading', 'paragraphs', 'charts', 'tables'
    
    Returns:
        PDF bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#003366"),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold"
    )
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Generated: {_fmt_dt(datetime.now())}", styles["Normal"]))
    story.append(PageBreak())
    
    # Sections
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#003366"),
        spaceAfter=12,
        spaceBefore=12,
        fontName="Helvetica-Bold"
    )
    
    for section in sections:
        if section.get("heading"):
            story.append(Paragraph(section["heading"], section_style))
        
        # Paragraphs
        for para in _safe_list(section.get("paragraphs")):
            story.append(Paragraph(para, styles["BodyText"]))
            story.append(Spacer(1, 0.1*inch))
        
        # Tables
        for tbl in _safe_list(section.get("tables")):
            cols = tbl.get("columns", [])
            rows = tbl.get("rows", [])
            
            if cols and rows:
                data = [cols] + rows
                table = Table(data, colWidths=[1.5*inch] * len(cols))
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTSIZE", (0, 1), (-1, -1), 9),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.2*inch))
        
        # Charts
        for chart in _safe_list(section.get("charts")):
            b64 = chart.get("b64")
            if b64:
                try:
                    img_data = base64.b64decode(b64)
                    img_buf = io.BytesIO(img_data)
                    img_obj = Image(img_buf, width=4.5*inch, height=2.7*inch)
                    story.append(img_obj)
                    story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    story.append(Paragraph(f"[Chart error: {str(e)}]", styles["Normal"]))
        
        story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
