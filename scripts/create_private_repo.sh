#!/usr/bin/env bash
# Opt-in helper for the user's authenticated machine; never run automatically.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
TARGET="wangwenqingqq/GTSPP-TIDEpro"

if [[ "${1:-}" != "--execute" ]]; then
  cat <<EOF
Dry run only. No network calls, commits, or remote changes.
Target: ${TARGET} (private)
Source: ${ROOT}
Execution checks package hashes, authenticated account, git identity, and a clean
new repository with no history or origin; only RELEASE_FILES.txt is staged.
Run explicitly on your authenticated machine:
  bash scripts/create_private_repo.sh --execute
EOF
  exit 0
fi
[[ $# -eq 1 ]] || { echo "Only --execute is accepted." >&2; exit 2; }
for tool in git gh python3; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 2; }
done
cd "$ROOT"
python3 -B scripts/verify_package.py
LOGIN="$(gh api user --jq .login)"
[[ "$LOGIN" == "wangwenqingqq" ]] || { echo "Authenticated account is not wangwenqingqq; stopping." >&2; exit 2; }

if TOP="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  [[ "$(cd "$TOP" && pwd -P)" == "$ROOT" ]] || { echo "Refusing to initialize inside a different repository." >&2; exit 2; }
else
  git init -b main
fi
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Repository already has history. Review and publish manually; no history will be replaced." >&2
  exit 2
fi
if git remote get-url origin >/dev/null 2>&1; then
  echo "An origin already exists; stopping without changing it." >&2
  exit 2
fi
[[ -n "$(git config --get user.name || true)" ]] || { echo "Configure your own git user.name first." >&2; exit 2; }
[[ -n "$(git config --get user.email || true)" ]] || { echo "Configure your own git user.email first." >&2; exit 2; }
if gh repo view "$TARGET" --json nameWithOwner >/dev/null 2>&1; then
  echo "Target repository already exists; nothing will be overwritten." >&2
  exit 2
fi

python3 -B - <<'PY'
from pathlib import Path
import subprocess
wanted = set(Path('RELEASE_FILES.txt').read_text().splitlines())
tracked = set(subprocess.check_output(['git','ls-files','-z']).decode().split('\0')) - {''}
if tracked - wanted:
    raise SystemExit('Unexpected staged/tracked files; review them manually before publishing.')
subprocess.run(['git','add','--',*sorted(wanted)],check=True)
staged = set(subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode().split('\0')) - {''}
if staged != wanted:
    raise SystemExit('Staged file list differs from the package allowlist; stopping.')
PY

git commit -m "Add research restart notes and CPU correctness reference"
gh repo create "$TARGET" --private --source=. --remote=origin --push \
  --description "GTS++ / TIDE research restart; CPU semantic reference and evaluation plan"
