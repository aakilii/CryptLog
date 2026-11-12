"""
Export report to PDF.
"""
import sys
sys.path.insert(0, '.')
import json
import os
from datetime import datetime
from operation_room.database import open_vault

case_id = 'DEMO-RANSOMWARE-001'
db = open_vault(case_id)

# Get the report
report = db.execute(
    "SELECT id, title, ast FROM report_documents WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1", 
    ['report_%']
).fetchone()

if report:
    doc_id = report[0]
    title = report[1]
    ast = json.loads(report[2])
    print(f'Found report: {doc_id}')
    print(f'Title: {title}')
    print(f'Pages: {len(ast.get("pages", []))}')
else:
    print('No report found')
    sys.exit(1)

db.close()

# Export to PDF
print()
print('Exporting to PDF...')
from operation_room.services.reportlab_pdf_service import ReportLabPDFService

# Initialize service
service = ReportLabPDFService(case_id, doc_id, focus_mode=False)

# Convert AST to PDF
pdf_bytes = service.convert_canvas_to_pdf(ast)

# Save PDF
export_dir = f'data/cases/{case_id}/exports'
os.makedirs(export_dir, exist_ok=True)
pdf_path = f'{export_dir}/report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'

with open(pdf_path, 'wb') as f:
    f.write(pdf_bytes)

print(f'PDF exported: {pdf_path}')
print(f'Size: {len(pdf_bytes):,} bytes ({len(pdf_bytes)/1024:.1f} KB)')
