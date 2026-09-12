#!/usr/bin/env bash
# Lightweight self-check for OmaOBS.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0
pass() { printf 'ok  %s\n' "$1"; }
bad()  { printf 'FAIL %s\n' "$1"; fail=1; }

[[ -x $here/bin/omaobs ]] || bad "omaobs not executable"
[[ -x $here/bin/omaobs-switcher ]] || bad "omaobs-switcher not executable"
[[ -f $here/manifest.json ]] || bad "manifest.json missing"
[[ -f $here/lib/omaobs.py ]] || bad "lib/omaobs.py missing"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/themes/fixture" "$tmp/obs-themes" "$tmp/state" "$tmp/cache" "$tmp/config/omarchy/extensions"
cat >"$tmp/themes/fixture/colors.toml" <<'EOF'
mode = "dark"
accent = "#FF3D9A"
background = "#0B0618"
foreground = "#F2E8FF"
dark_background = "#070412"
darker_background = "#04020C"
lighter_background = "#1A1030"
muted = "#5A4A78"
selection = "#2A1848"
red = "#FF3355"
green = "#3DFF9A"
yellow = "#FFD400"
blue = "#5B7CFF"
magenta = "#FF3D9A"
cyan = "#00E8FF"
EOF

export OMAOBS_HOME="$tmp"
export OMAOBS_PLUGIN_DIR="$here"
export OMARCHY_PATH="$tmp"
export OMAOBS_OBS_THEMES="$tmp/obs-themes"
export OMAOBS_USER_INI="$tmp/user.ini"
export OMAOBS_STATE_DIR="$tmp/state"
export OMAOBS_CACHE_DIR="$tmp/cache"
mkdir -p "$tmp/.config/omarchy/themes" "$tmp/.local/state/omarchy/current"
# Point list discovery at the fixture via OMARCHY_PATH/themes
mkdir -p "$tmp/themes"
# stock path is $OMARCHY_PATH/themes — already have fixture there

# Also need ~/.config path under OMAOBS_HOME — lib uses home()/...
mkdir -p "$tmp/.config/omarchy/themes" "$tmp/.config/omarchy/extensions" "$tmp/.config/obs-studio"
ln -s "$tmp/themes/fixture" "$tmp/.config/omarchy/themes/fixture" 2>/dev/null || true

printf 'fixture\n' >"$tmp/.local/state/omarchy/current/theme.name"
cat >"$tmp/user.ini" <<'EOF'
[General]
FirstRun=true

[Appearance]
FontScale=10
Density=1
EOF

if "$here/bin/omaobs" set fixture --quiet; then
  pass "set fixture"
else
  bad "set fixture"
fi

[[ -f $tmp/obs-themes/Omarchy.ovt ]] && pass "wrote Omarchy.ovt" || bad "wrote Omarchy.ovt"
grep -q "io.github.alxwolfenstein97.omaobs" "$tmp/obs-themes/Omarchy.ovt" && pass "ovt id" || bad "ovt id"
grep -q "rgb(255,61,154)" "$tmp/obs-themes/Omarchy.ovt" && pass "accent in ovt" || bad "accent in ovt"
grep -q "text_on_selected\|text_on_accent" "$tmp/obs-themes/Omarchy.ovt" && pass "on-accent text vars" || bad "on-accent text vars"
# Fixture accent is loud pink → on_accent should be the dark background (#0b0618)
grep -q "rgb(11,6,24)" "$tmp/obs-themes/Omarchy.ovt" && pass "dark ink on accent" || bad "dark ink on accent"
grep -q "Theme=io.github.alxwolfenstein97.omaobs" "$tmp/user.ini" && pass "user.ini Theme" || bad "user.ini Theme"
grep -q "AutoReload=true" "$tmp/user.ini" && pass "AutoReload" || bad "AutoReload"
[[ "$(cat "$tmp/state/current")" == "fixture" ]] && pass "state current" || bad "state current"

if "$here/bin/omaobs" preview fixture >/dev/null; then
  [[ -f $tmp/cache/previews/fixture.png ]] && pass "preview png" || bad "preview png"
else
  bad "preview fixture"
fi

if command -v omarchy >/dev/null 2>&1; then
  if omarchy plugin validate "$here" >/dev/null 2>&1; then
    pass "omarchy plugin validate"
  else
    bad "omarchy plugin validate"
  fi
fi

if (( fail )); then
  echo "omaobs check: FAILED"
  exit 1
fi
echo "omaobs check: all good"
exit 0
