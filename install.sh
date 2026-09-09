#!/usr/bin/env bash
set -euo pipefail

if [[ $# -eq 2 && "${1:-}" == "--clean" && -n "${2:-}" ]]; then
  CLEAN_CONFIG=true
  VERSION_VALUE="$2"
elif [[ $# -eq 1 && -n "${1:-}" ]]; then
  CLEAN_CONFIG=false
  VERSION_VALUE="$1"
else
  echo "Usage: ./install.sh [--clean] <version>" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/src/anki_ai_workspace"
MANIFEST_PATH="$SRC_DIR/manifest.json"
ARCHIVE_PATH="$REPO_ROOT/dist/anki_ai_workspace.ankiaddon"
INSTALL_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$INSTALL_DIR"
}

trap cleanup EXIT

if command -v pgrep >/dev/null 2>&1 && pgrep -x "Anki" >/dev/null 2>&1; then
  echo "Close Anki before installing Anki AI Workspace." >&2
  exit 1
fi

PACKAGE_NAME="$(
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["package"])' \
    "$MANIFEST_PATH"
)"

if [[ -n "${ANKI_ADDONS_DIR:-}" ]]; then
  ADDONS_DIR="$ANKI_ADDONS_DIR"
elif [[ -d "$HOME/Library/Application Support/Anki2/addons21" ]]; then
  ADDONS_DIR="$HOME/Library/Application Support/Anki2/addons21"
elif [[ -d "$HOME/.local/share/Anki2/addons21" ]]; then
  ADDONS_DIR="$HOME/.local/share/Anki2/addons21"
else
  echo "Could not find an Anki add-ons directory." >&2
  echo "Set ANKI_ADDONS_DIR to your addons21 path and rerun." >&2
  exit 1
fi

TARGET_DIR="$ADDONS_DIR/$PACKAGE_NAME"

"$REPO_ROOT/build.sh" "$VERSION_VALUE"

if [[ "$CLEAN_CONFIG" == true && -f "$TARGET_DIR/meta.json" ]]; then
  echo "Resetting AI Workspace settings to their packaged defaults"
  python3 - "$TARGET_DIR/meta.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
metadata = json.loads(path.read_text(encoding="utf-8"))
metadata.pop("config", None)
path.write_text(
    json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
PY
fi

echo "Installing add-on into $TARGET_DIR"
mkdir -p "$TARGET_DIR"
unzip -oq "$ARCHIVE_PATH" -d "$INSTALL_DIR"

rsync -a --delete \
  --exclude "meta.json" \
  --exclude "user_files/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  "$INSTALL_DIR/" "$TARGET_DIR/"

echo "Install complete."
echo "Addon dir: $TARGET_DIR"
