#!/usr/bin/env bash
set -euo pipefail

SCRIPT_REAL="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "${BASH_SOURCE[0]}")"
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$SCRIPT_REAL")/.." && pwd)}"
KIMI_BIN="${KIMI_BIN:-$HOME/.kimi-code/bin/kimi}"
export PATH="$HOME/.nvm/versions/node/v24.15.0/bin:/opt/homebrew/bin:$PATH"

cd "$REPO_ROOT"
node scripts/check-no-comments.mjs
pnpm --filter @moonshot-ai/agent-core-v2 exec vitest run test/features/externalHooks test/hooks.test.ts test/agent/toolExecutor
pnpm -C apps/kimi-code run build:native:sea

if [ -f "$KIMI_BIN" ] && [ ! -f "${KIMI_BIN}.official.bak" ]; then
  cp -f "$KIMI_BIN" "${KIMI_BIN}.official.bak"
fi

cp -f apps/kimi-code/dist-native/bin/darwin-arm64/kimi "${KIMI_BIN}.tmp"
mv -f "${KIMI_BIN}.tmp" "$KIMI_BIN"
rm -rf "$(dirname "$KIMI_BIN")/.staging"
python3 "$REPO_ROOT/local/sync-claude-mcp.py"
mkdir -p "$HOME/.kimi-code/hooks"
ln -sfn "$REPO_ROOT/local/guard-k31-markdown.py" "$HOME/.kimi-code/hooks/guard_k31_markdown.py"
ln -sfn "$HOME/.claude/skills" "$HOME/.kimi-code/skills"
echo "Installed local kimi binary: $($KIMI_BIN --version)"
