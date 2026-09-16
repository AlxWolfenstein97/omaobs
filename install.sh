#!/usr/bin/env bash
#
# OmaOBS installer. Safe to re-run: rewrites what it owns, leaves the rest alone.
# Lives under ~/.config/omarchy/plugins/ like other third-party plugins.
#
# Flags:
#   --quiet   less chatter (used by the shell service on startup)
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
quiet=0
for arg in "$@"; do
  case $arg in
    --quiet) quiet=1 ;;
  esac
done

note() { (( quiet )) || printf 'omaobs: %s\n' "$1"; }
warn() { printf 'omaobs: %s\n' "$1" >&2; }

plugin_id="io.github.alxwolfenstein97.omaobs"
hooks="$HOME/.config/omarchy/hooks/theme-set.d"
state="$HOME/.local/state/omarchy/omaobs"

mkdir -p "$hooks" "$state" "$HOME/.config/obs-studio/themes"

chmod 755 "$here"/bin/* "$here/omarchy/theme-set-hook" "$here/check.sh" \
  "$here/install.sh" "$here/uninstall.sh" 2>/dev/null || true

export OMAOBS_PLUGIN_DIR="$here"

ensure_pkg() {
  local pkg=$1
  local why=$2
  if pacman -Q "$pkg" &>/dev/null; then
    return 0
  fi
  note "installing $pkg — $why"
  if command -v omarchy >/dev/null 2>&1; then
    omarchy pkg add "$pkg" || warn "could not install $pkg"
  else
    warn "install $pkg manually — $why"
  fi
}

# Pillow draws Style carousel mockups — install before warming previews.
ensure_pkg python-pillow "draws Style → OBS Themes mockups (Pillow)"

# ------------------------------------------------------------------- theme hook
install -m 755 "$here/omarchy/theme-set-hook" "$hooks/omaobs"
note "hook: $hooks/omaobs"

# ------------------------------------------------------------------------ menu
# Style extenders all rewrite the same extensions file. Shell-service --quiet
# starts them in parallel — flock so we don't clobber each other's rows, then
# refresh the live menu only when the file actually changed (avoids stacked
# Hypr "zoom strokes" on every boot).
menu_lock="$HOME/.local/state/omarchy/style-extenders/menu.lock"
menu_sha="$HOME/.local/state/omarchy/style-extenders/menu.sha"
menu_file="$HOME/.config/omarchy/extensions/omarchy-menu.jsonc"
mkdir -p "$(dirname "$menu_lock")"
(
  flock 9
  "$here/bin/omaobs" install-menu
  if command -v omarchy-shell >/dev/null 2>&1 && [[ -f $menu_file ]]; then
    new_sha=$(sha256sum "$menu_file" 2>/dev/null | awk '{print $1}')
    old_sha=$(cat "$menu_sha" 2>/dev/null || true)
    if [[ -n $new_sha && $new_sha != "$old_sha" ]]; then
      omarchy-shell -q omarchy.menu refresh >/dev/null 2>&1 || true
      printf '%s\n' "$new_sha" >"$menu_sha"
    fi
  fi
) 9>"$menu_lock"
if (( ! quiet )); then
  omarchy-shell -q shell rescanPlugins >/dev/null 2>&1 || true
fi

# ----------------------------------------------------------- initial apply/sync
# Interactive always syncs. Quiet: one-shot if we have never synced on this
# machine (fresh plugin add), then the theme-set hook keeps OBS in step.
if command -v omarchy >/dev/null 2>&1; then
  if (( ! quiet )) || [[ ! -f $state/synced ]]; then
    if "$here/bin/omaobs-sync" --quiet >/dev/null 2>&1; then
      touch "$state/synced"
      note "synced OBS theme to current Omarchy palette"
    else
      warn "initial sync skipped (no current theme yet?)"
    fi
  fi
else
  warn "omarchy not on PATH; run 'omaobs sync' after your next theme set"
fi

# Warm mockups once on interactive install — not on every shell-start --quiet.
if (( ! quiet )); then
  (
    "$here/bin/omaobs" preview >/dev/null 2>&1 || true
  ) &
fi

if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin enable "$plugin_id" >/dev/null 2>&1 || true
fi

note "done — Style > OBS Themes, or '$here/bin/omaobs switcher'"
exit 0
