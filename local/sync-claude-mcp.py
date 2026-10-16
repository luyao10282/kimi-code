#!/usr/bin/env python3
"""Sync global MCP servers from ~/.claude.json into ~/.kimi-code/mcp.json."""
import json
from pathlib import Path

CLAUDE_JSON = Path.home() / ".claude.json"
KIMI_MCP_JSON = Path.home() / ".kimi-code" / "mcp.json"


def main() -> None:
    if not CLAUDE_JSON.is_file():
        return
    try:
        claude_data = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return
    claude_servers = claude_data.get("mcpServers")
    if not isinstance(claude_servers, dict) or not claude_servers:
        return

    try:
        kimi_data = json.loads(KIMI_MCP_JSON.read_text(encoding="utf-8"))
    except Exception:
        kimi_data = {}
    if not isinstance(kimi_data, dict):
        kimi_data = {}
    kimi_servers = kimi_data.get("mcpServers")
    if not isinstance(kimi_servers, dict):
        kimi_servers = {}

    changed = False
    for name, cfg in claude_servers.items():
        if not isinstance(cfg, dict):
            continue
        if kimi_servers.get(name) != cfg:
            kimi_servers[name] = cfg
            changed = True

    if changed or not KIMI_MCP_JSON.is_file():
        kimi_data["mcpServers"] = kimi_servers
        KIMI_MCP_JSON.parent.mkdir(parents=True, exist_ok=True)
        tmp = KIMI_MCP_JSON.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(kimi_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(KIMI_MCP_JSON)


if __name__ == "__main__":
    main()
