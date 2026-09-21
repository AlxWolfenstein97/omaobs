#!/usr/bin/env bash
#
# Full clean-slate: menu, theme-set hook, Omarchy.ovt, Appearance.Theme if we
# set it, cache/state. Leaves OBS itself and your scenes alone. Optional
# package drop prompts in this TTY (no floater).
#
set -euo pipefail

assume_yes=0
for arg in "$@"; do
  case $arg in --yes|-y) assume_yes=1 ;; esac
done

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
plugin_id="io.github.alxwolfenstein97.omaobs"
hooks="$HOME/.config/omarchy/hooks/theme-set.d"
ovt="$HOME/.config/obs-studio/themes/Omarchy.ovt"
state="$HOME/.local/state/omarchy/omaobs"
cache="$HOME/.cache/omarchy/omaobs"
menu_lock="$HOME/.local/state/omarchy/style-extenders/menu.lock"

note() { printf 'omaobs: %s\n' "$1"; }

try_pkg_drop() {
  # Best-effort: drop packages we may have pulled. If something else still
  # needs them, pacman refuses and we leave them — that is fine.
  local pkg
  for pkg in "$@"; do
    pacman -Q "$pkg" &>/dev/null || continue
    if command -v omarchy >/dev/null 2>&1 && omarchy pkg drop "$pkg"; then
      note "dropped $pkg"
    else
      note "kept $pkg (still required elsewhere or drop failed — fine)"
    fi
  done
}

ask_pkg_drop() {
  # Interactive — prompts in this terminal (no floater).
  local -a have=()
  local pkg a req
  for pkg in "$@"; do
    pacman -Q "$pkg" &>/dev/null && have+=("$pkg")
  done
  ((${#have[@]})) || return 0
  note "optional package drops — n / Enter keeps; pacman may refuse if still required"
  for pkg in "${have[@]}"; do
    case $pkg in
      python-pillow)
        note "python-pillow — Style carousel mockups (shared); MangoHud/goverlay/Lutris may need it"
        req=$(pacman -Qi python-pillow 2>/dev/null | awk -F': ' '/^Required By/{print $2}')
        note "  pacman Required By: ${req:-none}"
        ;;
      python-numpy)
        note "python-numpy — OmaCursor Adwaita remaps"
        req=$(pacman -Qi python-numpy 2>/dev/null | awk -F': ' '/^Required By/{print $2}')
        note "  pacman Required By: ${req:-none}"
        ;;
      terminus-font)
        note "terminus-font — OmaTTY console faces"
        ;;
      adw-gtk-theme)
        note "adw-gtk-theme — GTK theme Chroma paints over"
        ;;
      *)
        note "package: $pkg"
        ;;
    esac
    read -r -p "Drop $pkg? [y/N] " a || a=
    case $a in
      [yY]|[yY][eE][sS]) try_pkg_drop "$pkg" ;;
      *) note "kept $pkg" ;;
    esac
  done
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
rm -f "$state/armed-theme-hook" "$state/armed-style-menu"
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

if (( ! assume_yes )); then
  ask_pkg_drop python-pillow
else
  note "full wipe (--yes): trying package drops (kept if still required elsewhere)"
  try_pkg_drop python-pillow
fi

note "done — no omaobs menu/hook/Omarchy.ovt left; pick a stock OBS theme if needed"
if (( assume_yes )); then
  note "full wipe (--yes): removing plugin $plugin_id"
  if command -v omarchy >/dev/null 2>&1; then
    # Leave the tree before Omarchy deletes it out from under us.
    cd "${HOME:-/}" || cd /
    omarchy plugin remove "$plugin_id" --yes \
      || note "plugin remove failed — try: omarchy plugin remove $plugin_id --yes"
  else
    note "omarchy CLI missing — delete by hand: $here"
  fi
else
  note "plugin files remain at $here until you omit/remove the plugin"
  note "  omarchy plugin remove $plugin_id"
fi

exit 0
