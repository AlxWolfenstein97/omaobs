#!/usr/bin/env bash
#
# Remove OmaOBS wiring. Leaves OBS itself and your scene collections alone.
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

# Drop Theme=omaobs from user.ini if we set it (best-effort; leave AutoReload).
ini="$HOME/.config/obs-studio/user.ini"
if [[ -f $ini ]] && grep -q 'io.github.alxwolfenstein97.omaobs' "$ini"; then
  python3 - <<'PY'
from configparser import ConfigParser
from pathlib import Path
path = Path.home() / ".config/obs-studio/user.ini"
p = ConfigParser(interpolation=None)
p.optionxform = str
p.read(path)
if p.has_section("Appearance") and p.get("Appearance", "Theme", fallback="") == "io.github.alxwolfenstein97.omaobs":
    p.remove_option("Appearance", "Theme")
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

note "done — plugin files left at $here; remove the folder yourself if you want it gone"
note "pick a stock theme under OBS Settings > Appearance if needed"
exit 0
