import json
import pandas as pd
from io import StringIO


def parse_json(content: bytes):
    data = json.loads(content.decode())
    if isinstance(data, list):
        return pd.DataFrame(data)
    return pd.DataFrame([data])


def parse_csv(content: bytes):
    return pd.read_csv(StringIO(content.decode()))


def parse_text(content: bytes):
    lines = content.decode().splitlines()
    data = []

    for line in lines:
        parts = line.split()
        entry = {}

        if len(parts) >= 2:
            entry["timestamp"] = f"{parts[0]} {parts[1]}"

        for part in parts[2:]:
            if "=" in part:
                key, value = part.split("=", 1)
                entry[key.lower()] = value

        data.append(entry)

    return pd.DataFrame(data)
