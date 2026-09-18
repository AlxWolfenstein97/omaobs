#!/usr/bin/env bash
#
# Full clean-slate: menu, theme-set hook, Omarchy.ovt, Appearance.Theme if we
# set it, cache/state. Leaves OBS itself and your scenes alone. Optional
# floating terminal for shared package drop.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_id="io.github.alxwolfenstein97.omaobs"
hooks="$HOME/.config/omarchy/hooks/theme-set.d"
ovt="$HOME/.config/obs-studio/themes/Omarchy.ovt"
state="$HOME/.local/state/omarchy/omaobs"
cache="$HOME/.cache/omarchy/omaobs"
menu_lock="$HOME/.local/state/omarchy/style-extenders/menu.lock"

note() { printf 'omaobs: %s\n' "$1"; }

offer_pkg_drop() {
  local -a have=()
  local pkg
  for pkg in "$@"; do
    pacman -Q "$pkg" &>/dev/null && have+=("$pkg")
  done
  ((${#have[@]})) || return 0
  local list="${have[*]}"
  local script="$state/uninstall-floater.sh"
  mkdir -p "$state"
  {
    printf '%s\n' '#!/usr/bin/env bash' 'set -uo pipefail'
    printf '%s\n' "printf '%s\n' 'OmaOBS — uninstall'"
    printf '%s\n' "printf '%s\n' '────────────────────────────────'"
    printf '%s\n' "printf '%s\n' 'Optional — drop shared packages only if nothing else needs them:'"
    for pkg in "${have[@]}"; do
      case $pkg in
        python-pillow) printf '%s\n' "printf '  • %s — %s\n' 'python-pillow' 'Style carousel mockups'" ;;
        python-numpy) printf '%s\n' "printf '  • %s — %s\n' 'python-numpy' 'Adwaita cursor remaps'" ;;
        adw-gtk-theme) printf '%s\n' "printf '  • %s — %s\n' 'adw-gtk-theme' 'GTK theme Chroma paints'" ;;
        *) printf '%s\n' "printf '  • %s\n' $(printf %q "$pkg")" ;;
      esac
    done
    printf '%s\n' "printf '%s\n' '────────────────────────────────'"
    printf '%s\n' "printf '%s\n' ''"
    printf '%s\n' "read -r -p 'Drop ${list}? [y/N] ' a"
    printf '%s\n' 'case $a in'
    printf '%s\n' "  [yY]|[yY][eE][sS]) omarchy pkg drop ${list} ;;"
    printf '%s\n' "  *) printf 'skipped package drop\n' ;;"
    printf '%s\n' 'esac'
  } >"$script"
  chmod 755 "$script"
  if command -v omarchy-launch-floating-terminal-with-presentation >/dev/null 2>&1; then
    note "optional package drop — opening floating terminal"
    omarchy-launch-floating-terminal-with-presentation "bash $(printf %q "$script")" >/dev/null 2>&1 &
  else
    note "optional: omarchy pkg drop $list"
  fi
}


export OMAOBS_PLUGIN_DIR="$here"

# Tombstone + disable first so Service --quiet cannot resurrect the Style row.
mkdir -p "$state"
touch "$state/uninstalled"
if command -v omarchy >/dev/null 2>&1; then
  omarchy plugin disable "$plugin_id" >/dev/null 2>&1 || true
fi

mkdir -p "$(dirname "$menu_lock")"
(
  flock 9
  "$here/bin/omaobs" uninstall-menu || true
) 9>"$menu_lock"
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
if changed:
    with path.open("w", encoding="utf-8") as fh:
        p.write(fh, space_around_delimiters=False)
    print("cleared Appearance.Theme")
PY
fi

rm -rf "$cache"
find "$state" -mindepth 1 ! -name uninstalled -delete 2>/dev/null || true
touch "$state/uninstalled"
note "cleared state/cache (tombstone left so quiet install cannot resurrect)"

omarchy-shell -q omarchy.menu refresh >/dev/null 2>&1 || true
omarchy-shell -q shell rescanPlugins >/dev/null 2>&1 || true

offer_pkg_drop python-pillow

note "done — no omaobs menu/hook/Omarchy.ovt left; pick a stock OBS theme if needed"
note "plugin files remain at $here until you omit/remove the plugin"
exit 0
