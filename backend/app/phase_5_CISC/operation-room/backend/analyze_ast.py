import json
from operation_room.database import open_vault

conn = open_vault('DEMO-RANSOMWARE-001')
result = conn.execute("SELECT ast_json FROM studio_documents WHERE doc_id = 'report_56252386'").fetchone()
ast = json.loads(result[0])

print("Total pages:", len(ast.get("pages", [])))

# Count element types
element_types = {}
empty_text = 0
for page in ast.get("pages", []):
    for elem in page.get("elements", []):
        t = elem.get("type", "unknown")
        element_types[t] = element_types.get(t, 0) + 1
        if t == "text" and not elem.get("content"):
            empty_text += 1

print("Element types:", element_types)
print("Empty text elements:", empty_text)

# Check page 1 content detail
page1 = ast.get("pages", [])[0]
print("\nPage 1 elements:")
for e in page1.get("elements", []):
    etype = e.get("type")
    if etype == "text":
        content = e.get("content", "")
        print("  TEXT:", repr(content[:80]) if content else "(EMPTY)")
    elif etype == "chart":
        data = e.get("data", {})
        print("  CHART:", e.get("chartType"), "data keys:", list(data.keys()) if isinstance(data, dict) else "no data")
    elif etype == "metric":
        print("  METRIC:", e.get("label"), "=", e.get("value"))

conn.close()
