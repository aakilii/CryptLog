import json
from operation_room.database import open_vault
from operation_room.services.reportlab_pdf_service import generate_pdf_from_ast
import PyPDF2
import io

conn = open_vault('DEMO-RANSOMWARE-001')
row = conn.execute(
    'SELECT title, ast_json, content_hash FROM studio_documents WHERE doc_id=?',
    ['report_56252386']
).fetchone()
conn.close()

title, ast_str, content_hash = row[0], row[1], row[2]
ast = json.loads(ast_str)

print(f'Title: {title}')
print(f'AST pages: {len(ast.get("pages", []))}')

pdf_bytes, manifest = generate_pdf_from_ast(
    case_id='DEMO-RANSOMWARE-001',
    doc_id='report_56252386',
    ast_data=ast,
    focus_mode='review'
)

print(f'Generated {len(pdf_bytes)} bytes')

reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
print(f'Pages in PDF: {len(reader.pages)}')
for i, page in enumerate(reader.pages[:5]):
    text = page.extract_text() or ''
    print(f'Page {i+1}: {len(text)} chars - {text[:50]}...' if text else f'Page {i+1}: {len(text)} chars')
