#!/usr/bin/env bash
#
# Install OneSearch (trial build): the `onesearch` binary, an `os` shortcut,
# and the `onesearch` SKILL.md for coding agents.
#
# One line:
#   curl -fsSL https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh | bash
#
# Pinned to a release:
#   curl -fsSL https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh | ONESEARCH_VERSION=v0.1.0 bash
#
# Inspect before running (recommended for the security-conscious):
#   curl -fsSLO https://raw.githubusercontent.com/oneness/OneSearch-dist/main/install.sh && less install.sh
#
# Environment overrides:
#   ONESEARCH_VERSION    release tag, e.g. v0.1.0 (default: latest release)
#   ONESEARCH_BIN_DIR    install dir for `onesearch`/`os` (default: ~/.local/bin)
#   ONESEARCH_NO_SKILL=1 skip the SKILL.md install
#   ONESEARCH_SKILL_DIR  install the skill only here (default: auto-detect)
#
# The tarball's SHA-256 is verified against the release's SHA256SUMS before
# anything is installed. Works with `curl` or `wget`, `sha256sum` or `shasum`.
# macOS /bin/bash is 3.2, so this script stays to portable constructs.
set -euo pipefail

DIST_REPO="oneness/OneSearch-dist"
VERSION="${ONESEARCH_VERSION:-latest}"
BIN_DIR="${ONESEARCH_BIN_DIR:-$HOME/.local/bin}"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "need '$1' on PATH to install"
}

fetch() { # <url> <dest>
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --proto '=https' --tlsv1.2 "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$2" "$1"
  else
    fail "need 'curl' or 'wget' to download"
  fi
}

sha256_of() { # <file> -> prints hex digest
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    fail "need 'sha256sum' or 'shasum' to verify the download"
  fi
}

# --- platform ---------------------------------------------------------------
os_name="$(uname -s)"
arch="$(uname -m)"
case "$os_name/$arch" in
  Linux/x86_64|Linux/amd64)   target="x86_64-unknown-linux-gnu" ;;
  Darwin/arm64|Darwin/aarch64) target="aarch64-apple-darwin" ;;
  *) fail "unsupported platform '$os_name/$arch': trial builds ship for linux-x86_64 and macOS-arm64 (tell us what you need)" ;;
esac

asset="onesearch-$target.tar.gz"
if [ "$VERSION" = "latest" ]; then
  base="https://github.com/$DIST_REPO/releases/latest/download"
  raw_skill="https://raw.githubusercontent.com/$DIST_REPO/main/skills/onesearch/SKILL.md"
else
  case "$VERSION" in v*) tag="$VERSION" ;; *) tag="v$VERSION" ;; esac
  base="https://github.com/$DIST_REPO/releases/download/$tag"
  raw_skill="https://raw.githubusercontent.com/$DIST_REPO/$tag/skills/onesearch/SKILL.md"
fi

need_cmd tar
need_cmd awk

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# --- download ----------------------------------------------------------------
if [ -n "${ONESEARCH_TARBALL:-}" ]; then
  # Test hook: install from a local tarball instead of the network.
  cp "$ONESEARCH_TARBALL" "$tmp/$asset"
else
  say "downloading $asset ($VERSION) ..."
  fetch "$base/$asset" "$tmp/$asset"
  fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS"
  want="$(awk -v a="$asset" '$2 == a {print $1}' "$tmp/SHA256SUMS")"
  [ -n "$want" ] || fail "no checksum for $asset in SHA256SUMS"
  got="$(sha256_of "$tmp/$asset")"
  [ "$want" = "$got" ] || fail "checksum mismatch for $asset (want $want, got $got)"
  say "checksum ok."
fi

tar -xzf "$tmp/$asset" -C "$tmp"
[ -x "$tmp/onesearch" ] || [ -f "$tmp/onesearch" ] || fail "tarball has no 'onesearch' binary"

# --- binary ------------------------------------------------------------------
mkdir -p "$BIN_DIR"
cp "$tmp/onesearch" "$BIN_DIR/onesearch"
chmod +x "$BIN_DIR/onesearch"
ln -sf onesearch "$BIN_DIR/os"
say "installed onesearch + os -> $BIN_DIR"

# --- skill -------------------------------------------------------------------
install_skill_to() { # <dir>
  mkdir -p "$1"
  cp "$2" "$1/SKILL.md"
  say "installed skill -> $1/SKILL.md"
}

if [ "${ONESEARCH_NO_SKILL:-0}" = "1" ]; then
  say "skipping skill install (ONESEARCH_NO_SKILL=1)."
else
  skill_src=""
  if [ -n "${ONESEARCH_SKILL_FILE:-}" ]; then
    skill_src="$ONESEARCH_SKILL_FILE" # test hook
  elif [ -f "$tmp/SKILL.md" ]; then
    skill_src="$tmp/SKILL.md" # shipped inside the tarball
  else
    fetch "$raw_skill" "$tmp/SKILL.md" && skill_src="$tmp/SKILL.md"
  fi
  if [ -z "$skill_src" ]; then
    say "warning: SKILL.md not found; binary installed, skill skipped." >&2
  elif [ -n "${ONESEARCH_SKILL_DIR:-}" ]; then
    install_skill_to "$ONESEARCH_SKILL_DIR" "$skill_src"
  else
    installed=0
    for root in "$HOME/.claude/skills" "$HOME/.codex/skills" "$HOME/.agents/skills"; do
      case "$root" in
        "$HOME/.claude/skills") install_skill_to "$root/onesearch" "$skill_src"; installed=1 ;;
        *) [ -d "$root" ] && { install_skill_to "$root/onesearch" "$skill_src"; installed=1; } ;;
      esac
    done
    [ "$installed" = "1" ] || install_skill_to "$HOME/.claude/skills/onesearch" "$skill_src"
    say "using it project-locally? cp $skill_src .claude/skills/onesearch/SKILL.md"
  fi
fi

# --- verify + next steps ------------------------------------------------------
"$BIN_DIR/onesearch" --version
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "add to PATH: export PATH=\"$BIN_DIR:\$PATH\"  (then restart your shell/agent)" ;;
esac

cat <<EOF
next:
  cd <a git checkout> && os search "your question about the code"
  first run downloads the embedding model once (~33 MB, cached).

update: re-run this installer (or pin ONESEARCH_VERSION=vX.Y.Z).
uninstall: rm $BIN_DIR/onesearch $BIN_DIR/os
docs: https://github.com/$DIST_REPO
EOF
