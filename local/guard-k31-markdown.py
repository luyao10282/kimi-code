#!/usr/bin/env python3
"""PreToolUse guard for Kimi Code: block K3.1 from authoring large Markdown directly.

Enforces the user-level rule in ~/.kimi-code/AGENTS.md:
- When the active model is Kimi K3.1 (e.g. kimi-code/k3.1-pro, kimi-code/k3.1-pro-highspeed),
  direct Write/Edit/Bash authoring of large Markdown content (>= 600 chars or >= 25 lines)
  is blocked with exit code 2.
- Small edits (< 600 chars and < 25 lines, such as adding a single index line) are allowed.
- When a delegated subagent running kimi-code/k3 (or any non-k3.1 model) executes Write/Edit,
  payload["model"] is "kimi-code/k3", so it passes through unobstructed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

MIN_CHARS = int(os.environ.get("KIMI_MD_GUARD_MIN_CHARS", "600"))
MIN_LINES = int(os.environ.get("KIMI_MD_GUARD_MIN_LINES", "25"))
TAIL_BYTES = 256 * 1024

MD_EXTS = (".md", ".mdx", ".markdown")

BASH_MD_WRITE_RE = re.compile(
    r"""(?ix)
    (?:
        (?:>{1,2}|\btee\b(?:\s+-a)?)\s*['"]?([^\s'"|;&]+\.(?:md|mdx|markdown))\b
        |
        \bopen\(\s*['"]([^'"]+\.(?:md|mdx|markdown))['"]\s*,\s*['"][wa]
        |
        \bPath\(\s*['"]([^'"]+\.(?:md|mdx|markdown))['"]\s*\)\.write_text\b
    )
    """
)


def resolve_model(payload: dict) -> str:
    model = payload.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()

    tp_raw = payload.get("transcript_path")
    tp = Path(tp_raw) if isinstance(tp_raw, str) and tp_raw else None
    if tp is None or not tp.is_file():
        sid = payload.get("session_id")
        agent_id = payload.get("agent_id") or "main"
        if isinstance(sid, str) and sid:
            matches = list(
                (Path.home() / ".kimi-code" / "sessions").glob(
                    f"*/{sid}/agents/{agent_id}/wire.jsonl"
                )
            )
            if matches:
                tp = matches[0]

    if tp is not None and tp.is_file():
        try:
            size = tp.stat().st_size
            with tp.open("rb") as fh:
                fh.seek(max(0, size - TAIL_BYTES))
                lines = fh.read().split(b"\n")
            for raw in reversed(lines):
                if not raw.strip():
                    continue
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                rtype = rec.get("type")
                if rtype == "usage.record" and isinstance(rec.get("model"), str):
                    return rec["model"].strip()
                if rtype == "profile.bind" and isinstance(rec.get("modelAlias"), str):
                    return rec["modelAlias"].strip()
        except OSError:
            pass
    return ""


def is_k31_model(model: str) -> bool:
    lowered = model.lower()
    return "k3.1" in lowered or "k3_1" in lowered or "k3-1" in lowered


def is_markdown_path(path_str: str) -> bool:
    return path_str.strip().lower().endswith(MD_EXTS)


def is_large_text(text: str) -> tuple[bool, int, int]:
    chars = len(text)
    lines = text.count("\n") + (1 if chars > 0 else 0)
    return (chars >= MIN_CHARS or lines >= MIN_LINES), chars, lines


def block(model: str, target: str, chars: int, lines: int) -> None:
    reason = (
        f"[PreToolUse Markdown Guard] Blocked: current model '{model}' is not allowed to directly "
        f"author or edit large Markdown content (target: {target}, size: {chars} chars / {lines} lines; "
        f"threshold: {MIN_CHARS} chars or {MIN_LINES} lines). "
        f"Per user-level rules, delegate large documentation writing to a subagent using the Agent tool "
        f"with `model: \"kimi-code/k3\"` and `fork: true`."
    )
    sys.stderr.write(reason + "\n")
    sys.exit(2)


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        return
    try:
        payload = json.loads(raw)
    except ValueError:
        return
    if not isinstance(payload, dict):
        return

    if payload.get("hook_event_name") not in (None, "PreToolUse"):
        return

    model = resolve_model(payload)
    if not is_k31_model(model):
        return

    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    if tool_name == "Write":
        path_str = str(tool_input.get("path") or tool_input.get("file_path") or "")
        if not is_markdown_path(path_str):
            return
        content = str(tool_input.get("content") or "")
        large, chars, lines = is_large_text(content)
        if large:
            block(model, path_str, chars, lines)

    elif tool_name == "Edit":
        path_str = str(tool_input.get("path") or tool_input.get("file_path") or "")
        if not is_markdown_path(path_str):
            return
        new_string = str(tool_input.get("new_string") or "")
        large, chars, lines = is_large_text(new_string)
        if large:
            block(model, path_str, chars, lines)

    elif tool_name == "Bash":
        command = str(tool_input.get("command") or "")
        m = BASH_MD_WRITE_RE.search(command)
        if not m:
            return
        target = next((g for g in m.groups() if g), ".md file")
        large, chars, lines = is_large_text(command)
        if large:
            block(model, f"Bash -> {target}", chars, lines)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        pass
    sys.exit(0)
