import json
import sys


SENSITIVE_DATA_PATH = "operation-room/backend/data"
WRITE_TOOL_HINTS = (
    "apply_patch",
    "edit",
    "create_file",
    "delete",
    "rename",
    "insert",
    "str_replace",
    "terminal",
    "shell",
    "run",
    "send_to_terminal",
)
TERMINAL_TOOL_HINTS = ("terminal", "shell", "run", "execute")
RISKY_SIGNATURES = (
    "git reset --hard",
    "git checkout --",
    "git clean -fd",
    "git clean -fdx",
    "rm -rf",
    "del /f /q",
    "rd /s /q",
    "rmdir /s /q",
    "remove-item",
    "format c:",
    "drop table ",
    "truncate table ",
    "drop database ",
)


def _emit(payload):
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def _safe_text(value):
    try:
        return json.dumps(value, ensure_ascii=False).lower()
    except Exception:
        return str(value).lower()


def _normalize_text(value):
    return str(value).lower().replace("\\\\", "/").replace("\\", "/")


def _extract_tool_name(data):
    tool = data.get("tool", {}) if isinstance(data.get("tool", {}), dict) else {}
    return str(
        data.get("tool_name")
        or data.get("toolName")
        or tool.get("name")
        or ""
    ).lower()


def _extract_tool_input(data):
    if "tool_input" in data:
        return data.get("tool_input")
    if "toolInput" in data:
        return data.get("toolInput")
    tool = data.get("tool", {})
    if isinstance(tool, dict):
        return tool.get("input", {})
    return {}


def _is_write_like_tool(tool_name):
    return any(token in tool_name for token in WRITE_TOOL_HINTS)


def _session_context_payload():
    context = (
        "Workspace focus is operation-room. Avoid editing generated artifacts in "
        "operation-room/backend/data unless explicitly requested. Keep FastAPI routes "
        "thin, preserve chain-of-custody integrity, and run targeted verification commands."
    )
    return {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
    }


def _pretool_payload(data):
    tool_name = _extract_tool_name(data)
    tool_input = _extract_tool_input(data)
    payload_text = _safe_text(tool_input)

    normalized_payload = _normalize_text(payload_text)
    terminal_like = any(token in tool_name for token in TERMINAL_TOOL_HINTS)
    risky = any(signature in normalized_payload for signature in RISKY_SIGNATURES)

    if _is_write_like_tool(tool_name) and SENSITIVE_DATA_PATH in normalized_payload:
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Potential write operation under operation-room/backend/data detected. "
                    "Require explicit user confirmation before proceeding."
                ),
            },
        }

    if terminal_like and risky:
        return {
            "continue": True,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    "Potentially destructive command detected. Require explicit user confirmation."
                ),
            },
        }

    return {"continue": True}


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        _emit({"continue": True})
        return

    try:
        data = json.loads(raw)
    except Exception:
        _emit({"continue": True})
        return

    event = data.get("hookEventName", "")

    if event == "SessionStart":
        _emit(_session_context_payload())
        return

    if event == "PreToolUse":
        _emit(_pretool_payload(data))
        return

    _emit({"continue": True})


if __name__ == "__main__":
    main()