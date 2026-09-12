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

# ------------------------------------------------------------------- theme hook
install -m 755 "$here/omarchy/theme-set-hook" "$hooks/omaobs"
note "hook: $hooks/omaobs"

# ------------------------------------------------------------------------ menu
"$here/bin/omaobs" install-menu
omarchy-shell -q omarchy.menu refresh >/dev/null 2>&1 || true
omarchy-shell -q shell rescanPlugins >/dev/null 2>&1 || true

# ----------------------------------------------------------- initial apply/sync
if command -v omarchy >/dev/null 2>&1; then
  "$here/bin/omaobs-sync" --quiet >/dev/null 2>&1 \
    && note "synced OBS theme to current Omarchy palette" \
    || warn "initial sync skipped (no current theme yet?)"
else
  warn "omarchy not on PATH; run 'omaobs sync' after your next theme set"
fi

# Warm mockups in the background so Style > OBS Themes opens quickly.
(
  "$here/bin/omaobs" preview >/dev/null 2>&1 || true
) &

if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin enable "$plugin_id" >/dev/null 2>&1 || true
fi

note "done — Style > OBS Themes, or '$here/bin/omaobs switcher'"
exit 0
