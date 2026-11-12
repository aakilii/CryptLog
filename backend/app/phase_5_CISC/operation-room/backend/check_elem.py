import json
from operation_room.database import open_vault

conn = open_vault('DEMO-RANSOMWARE-001')
result = conn.execute("SELECT ast_json FROM studio_documents WHERE doc_id = 'report_56252386'").fetchone()
ast = json.loads(result[0])

# Check first text element structure
page1 = ast.get("pages", [])[0]
for elem in page1.get("elements", []):
    if elem.get("type") == "text":
        print("TEXT ELEMENT STRUCTURE:")
        print(json.dumps(elem, indent=2))
        break

conn.close()
