---
name: mcp-ops
description: "Use for VS Code MCP operations in operation-room: mcp.json setup, backend MCP endpoint checks, tool discovery validation, and troubleshooting."
argument-hint: "MCP setup or troubleshooting task"
user-invocable: true
---
# MCP Operations

## When to Use
- Configuring workspace MCP server entries.
- Troubleshooting MCP tool discovery in VS Code.
- Validating backend MCP endpoint readiness.

## Procedure
1. Confirm mcp.json server entries are valid.
2. Start backend API and verify MCP endpoints.
3. Confirm tools are discoverable via MCP tools list endpoint.
4. Use VS Code MCP commands to restart and inspect server logs.
5. Apply checks from [MCP checks](./references/mcp-checks.md).

## Output Checklist
- Active MCP server config
- Endpoint test outcomes
- Tool discovery status
- Next corrective action if discovery fails
