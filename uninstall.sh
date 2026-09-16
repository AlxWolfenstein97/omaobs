#!/usr/bin/env bash
#
# Full clean-slate: menu, theme-set hook, Omarchy.ovt, Appearance.Theme if we
# set it, cache/state. Leaves OBS itself and your scenes alone.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_id="io.github.alxwolfenstein97.omaobs"
hooks="$HOME/.config/omarchy/hooks/theme-set.d"
ovt="$HOME/.config/obs-studio/themes/Omarchy.ovt"
state="$HOME/.local/state/omarchy/omaobs"
cache="$HOME/.cache/omarchy/omaobs"

note() { printf 'omaobs: %s\n' "$1"; }

export OMAOBS_PLUGIN_DIR="$here"
"$here/bin/omaobs" uninstall-menu || true
rm -f "$hooks/omaobs"
note "removed theme-set hook"

if [[ -f $ovt ]]; then
  rm -f "$ovt"
  note "removed $ovt"
fi

# Drop Theme= when it still points at OmaOBS (THEME_ID).
ini="$HOME/.config/obs-studio/user.ini"
if [[ -f $ini ]] && grep -q 'io.github.alxwolfenstein97.omaobs' "$ini"; then
  python3 - <<'PY'
from configparser import ConfigParser
from pathlib import Path
path = Path.home() / ".config/obs-studio/user.ini"
p = ConfigParser(interpolation=None)
p.optionxform = str
p.read(path)
changed = False
if p.has_section("Appearance"):
    if p.get("Appearance", "Theme", fallback="") == "io.github.alxwolfenstein97.omaobs":
        p.remove_option("Appearance", "Theme")
        changed = True
    # AutoReload was set by us; leave it — harmless OBS default-ish behaviour.
if changed:
    with path.open("w", encoding="utf-8") as fh:
        p.write(fh, space_around_delimiters=False)
    print("cleared Appearance.Theme")
PY
fi

rm -rf "$state" "$cache"
note "cleared state/cache"

omarchy-shell -q omarchy.menu refresh >/dev/null 2>&1 || true

if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin disable "$plugin_id" >/dev/null 2>&1 || true
fi

note "done — no omaobs menu/hook/Omarchy.ovt left; pick a stock OBS theme if needed"
note "plugin files remain at $here until you omit/remove the plugin"
note "optional: omarchy pkg drop python-pillow  # if nothing else needs Pillow"
exit 0
