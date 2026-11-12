import json
from operation_room.database import open_vault

conn = open_vault('DEMO-RANSOMWARE-001')
result = conn.execute("SELECT ast_json FROM studio_documents WHERE doc_id = 'report_56252386'").fetchone()
ast = json.loads(result[0])

# Find all charts and check their data
print("=== CHART ELEMENTS ===")
for i, page in enumerate(ast.get("pages", [])):
    for elem in page.get("elements", []):
        if elem.get("type") == "chart":
            chart_type = elem.get("chartType", "unknown")
            chart_title = elem.get("chartTitle", "no title")
            data = elem.get("data", {})
            print(f"Page {i+1}: {chart_type} - {chart_title}")
            if isinstance(data, dict):
                print(f"  Data keys: {list(data.keys())}")
                if "labels" in data:
                    print(f"  Labels: {data['labels'][:5]}")
                if "values" in data:
                    print(f"  Values: {data['values'][:5]}")
            else:
                print(f"  Data: {type(data)}")
            print()

conn.close()
