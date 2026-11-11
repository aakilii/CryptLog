import json

def detect_format(content: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    try:
        json.loads(content.decode())
        return "json"
    except:
        pass
    return "text"
