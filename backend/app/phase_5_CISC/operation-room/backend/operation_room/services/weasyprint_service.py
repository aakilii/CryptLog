"""
WeasyPrint PDF Service for NFLIP Report Generation.

Generates 1:1 Headless PDF Fidelity by natively compiling HTML/CSS models
that mirror the frontend React flexbox grid.
"""

import io
import logging
from typing import Any, Dict, Optional
from weasyprint import HTML, CSS

logger = logging.getLogger(__name__)

class WeasyPrintService:
    def __init__(
        self, 
        case_id: str, 
        doc_id: str, 
        focus_mode: str = 'review',
        page_size: str = 'A4'
    ):
        self.case_id = case_id
        self.doc_id = doc_id
        self.focus_mode = focus_mode
        self.page_size = page_size

    def convert_canvas_to_pdf(self, ast_data: Dict[str, Any], vault_keys: Optional[Dict[str, str]] = None) -> bytes:
        logger.info(f"Generating high-fidelity PDF via WeasyPrint for {self.case_id}/{self.doc_id}")
        
        # 1. Base Framework CSS matching standard Tailwind React layout
        base_css = """
            @page {
                size: A4 portrait;
                margin: 20mm;
                @bottom-center {
                    content: "Page " counter(page) " of " counter(pages);
                    font-family: Inter, Helvetica, sans-serif;
                    font-size: 8pt;
                    color: #64748b;
                }
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 10pt;
                color: #1e293b;
                line-height: 1.5;
            }
            .document-container {
                display: flex;
                flex-direction: column;
                gap: 16px;
            }
            .canvas-element {
                break-inside: auto;
                page-break-inside: auto;
                margin-bottom: 24px;
                position: relative;
            }
            .component-widget {
                break-inside: avoid;
                page-break-inside: avoid;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
                background-color: #f8fafc;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .widget-header {
                font-weight: 600;
                font-size: 12px;
                text-transform: uppercase;
                color: #64748b;
                margin-bottom: 12px;
                border-bottom: 1px solid #e2e8f0;
                padding-bottom: 8px;
            }
            .evidence-node {
                display: inline-block;
                background-color: #e0f2fe;
                color: #0369a1;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 0.8rem;
                font-weight: bold;
                border: 1px solid #bae6fd;
            }
            
            /* Text element styles */
            h1 { font-size: 24pt; font-weight: 800; color: #0f172a; margin-top: 24px; }
            h2 { font-size: 18pt; font-weight: 700; color: #1e293b; margin-top: 20px; }
            p { margin-bottom: 12px; }
            pre { background: #f1f5f9; padding: 12px; border-radius: 6px; overflow-x: auto; font-family: monospace; }
        """

        # 2. Map AST (JSON) to HTML
        html_content = [
            '<!DOCTYPE html>',
            '<html><head><meta charset="utf-8"></head><body>',
            '<div class="document-container">'
        ]
        
        pages = ast_data.get('pages', [])
        if not pages:
            pages = [{'elements': ast_data.get('elements', [])}]
            
        for idx, page in enumerate(pages):
            html_content.append(f'<div id="page-{idx}" class="canvas-page">')
            elements = sorted(page.get('elements', []), key=lambda e: e.get('zIndex', 0))
            for el in elements:
                el_type = el.get('type')
                
                if el_type == 'text':
                    # Parse Lexical / TinyMCE raw HTML content payload
                    data = el.get('data', {})
                    raw_html = data.get('content') or data.get('text', '')
                    html_content.append(f'<div class="canvas-element text-element">{raw_html}</div>')
                    
                elif el_type == 'component':
                    data = el.get('data', {})
                    comp_type = data.get('type') or data.get('componentType', 'Dynamic Component')
                    title = data.get('title') or data.get('source', comp_type.upper())
                    string_data = str(data.get('data', ''))
                    # WeasyPrint Native Fallback for components (Phase 3 mapping uses HTML tables instead of plots)
                    html_content.append(
                        f'''
                        <div class="canvas-element component-widget">
                            <div class="widget-header">{title}</div>
                            <pre>{string_data}</pre>
                        </div>
                        '''
                    )
            html_content.append('</div>')
            
            # Insert native CSS page break logic between array items
            if idx < len(pages) - 1:
                html_content.append('<div style="page-break-after: always;"></div>')
                
        html_content.append('</div></body></html>')
        layout_html = "".join(html_content)

        # 3. Convert via WeasyPrint directly to PDF stream bytes
        try:
            css = CSS(string=base_css)
            html = HTML(string=layout_html)
            return html.write_pdf(stylesheets=[css])
        except Exception as e:
            logger.error(f"WeasyPrint render failed: {e}")
            raise
