#!/usr/bin/env python3
"""OmaOBS — Omarchy palettes → OBS Yami variants + Style-carousel mockups.

Discovers every theme with a colors.toml (no extra theme assets). Mockups are
illustrative OBS chrome matched to the Style tile aspect — not live captures.
"""

from __future__ import annotations

import argparse
import configparser
import multiprocessing as mp
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

PLUGIN_ID = "io.github.alxwolfenstein97.omaobs"
THEME_ID = "io.github.alxwolfenstein97.omaobs"
THEME_FILE = "Omarchy.ovt"
THEME_DISPLAY_NAME = "Omarchy"

HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def home() -> Path:
    return Path(os.environ.get("OMAOBS_HOME", Path.home())).expanduser()


def omarchy_path() -> Path:
    return Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy"))


def plugin_dir() -> Path:
    override = os.environ.get("OMAOBS_PLUGIN_DIR")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent.parent


def paths() -> dict[str, Path]:
    h = home()
    return {
        "user_themes": h / ".config/omarchy/themes",
        "stock_themes": omarchy_path() / "themes",
        "obs_themes": Path(
            os.environ.get("OMAOBS_OBS_THEMES", h / ".config/obs-studio/themes")
        ),
        "user_ini": Path(
            os.environ.get("OMAOBS_USER_INI", h / ".config/obs-studio/user.ini")
        ),
        "state": Path(os.environ.get("OMAOBS_STATE_DIR", h / ".local/state/omarchy/omaobs")),
        "cache": Path(os.environ.get("OMAOBS_CACHE_DIR", h / ".cache/omarchy/omaobs")),
        "menu": h / ".config/omarchy/extensions/omarchy-menu.jsonc",
        "hooks": h / ".config/omarchy/hooks/theme-set.d",
        "current_theme_name": h / ".local/state/omarchy/current/theme.name",
    }


def note(msg: str) -> None:
    print(f"omaobs: {msg}", file=sys.stderr)


def slugify(name: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", name or "")
    return cleaned.strip().lower().replace(" ", "-")


def pretty_name(slug: str) -> str:
    return re.sub(
        r"(^|-)([a-z])",
        lambda m: (" " if m.group(1) == "-" else "") + m.group(2).upper(),
        slugify(slug),
    )


def parse_hex(value: str, fallback: str) -> str:
    raw = (value or fallback).strip().strip('"').strip("'")
    if not HEX_RE.match(raw):
        raw = fallback
    if not raw.startswith("#"):
        raw = "#" + raw
    return raw.lower()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = parse_hex(value, "#000000").lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(c))) for c in rgb))


def mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex(
        (
            round(ar + (br - ar) * t),
            round(ag + (bg - ag) * t),
            round(ab + (bb - ab) * t),
        )
    )


def lighten(color: str, amount: float) -> str:
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float) -> str:
    return mix(color, "#000000", amount)


def relative_luminance(color: str) -> float:
    r, g, b = [c / 255.0 for c in hex_to_rgb(color)]

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def luma(color: str) -> float:
    """Chroma-compatible perceived brightness (0–255)."""
    r, g, b = hex_to_rgb(color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def on_color(base: str, candidates: list[str]) -> str:
    """Pick the candidate with the largest luma gap from base (Chroma/GTK style)."""
    base_l = luma(base)
    return max(candidates, key=lambda c: abs(luma(c) - base_l))


def read_colors_toml(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def theme_dir(slug: str) -> Path | None:
    p = paths()
    slug = slugify(slug)
    for root in (p["user_themes"], p["stock_themes"]):
        candidate = root / slug
        if (candidate / "colors.toml").is_file():
            return candidate
    return None


def list_theme_slugs() -> list[str]:
    p = paths()
    found: set[str] = set()
    for root in (p["user_themes"], p["stock_themes"]):
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir() or entry.is_symlink():
                if (entry / "colors.toml").is_file():
                    found.add(entry.name)
    return sorted(found)


def current_omarchy_slug() -> str | None:
    name_path = paths()["current_theme_name"]
    if name_path.is_file():
        return slugify(name_path.read_text(encoding="utf-8").strip())
    return None


def current_omaobs_slug() -> str | None:
    current = paths()["state"] / "current"
    if current.is_file():
        return slugify(current.read_text(encoding="utf-8").strip())
    return None


def palette_from_theme(slug: str) -> dict[str, Any]:
    directory = theme_dir(slug)
    if directory is None:
        raise FileNotFoundError(f"theme not found or missing colors.toml: {slug}")

    raw = read_colors_toml(directory / "colors.toml")
    mode = (raw.get("mode") or "dark").strip().lower()
    dark = mode != "light"

    background = parse_hex(raw.get("background", ""), "#1e1e2e")
    dark_background = parse_hex(raw.get("dark_background", ""), darken(background, 0.15))
    darker_background = parse_hex(raw.get("darker_background", ""), darken(background, 0.35))
    lighter_background = parse_hex(raw.get("lighter_background", ""), lighten(background, 0.12))
    foreground = parse_hex(raw.get("foreground", ""), "#cdd6f4")
    dark_foreground = parse_hex(raw.get("dark_foreground", ""), "#6c7086")
    light_foreground = parse_hex(raw.get("light_foreground", ""), foreground)
    muted = parse_hex(raw.get("muted", ""), dark_foreground)
    selection = parse_hex(raw.get("selection", ""), lighter_background)
    accent = parse_hex(raw.get("accent", raw.get("blue", "")), "#89b4fa")
    red = parse_hex(raw.get("red", ""), "#f38ba8")
    green = parse_hex(raw.get("green", ""), "#a6e3a1")
    yellow = parse_hex(raw.get("yellow", ""), "#f9e2af")
    blue = parse_hex(raw.get("blue", ""), accent)
    cyan = parse_hex(raw.get("cyan", ""), "#94e2d5")
    magenta = parse_hex(raw.get("magenta", ""), "#f5c2e7")

    if dark:
        # Yami expects grey7 (bg_window / menubar) darker than grey6 (bg_base /
        # docks). Omarchy's dark_background is the deeper surface — put it on
        # the chrome so the top bar doesn't float as a lighter stripe.
        greys = {
            "grey1": lighten(muted, 0.15),
            "grey2": muted,
            "grey3": selection,
            "grey4": mix(lighter_background, selection, 0.35),
            "grey5": lighter_background,
            "grey6": background,
            "grey7": dark_background,
            "grey8": darker_background,
        }
        text = foreground
        text_muted = dark_foreground
    else:
        greys = {
            "grey1": muted,
            "grey2": lighten(background, 0.02),
            "grey3": lighten(background, 0.04),
            "grey4": lighten(background, 0.01),
            "grey5": mix(background, darker_background, 0.25),
            "grey6": background,
            "grey7": dark_background,
            "grey8": darker_background,
        }
        text = foreground
        text_muted = dark_foreground

    # Keep focus/border primary close to the real accent; selection fills are
    # pulled slightly toward the surface so neon themes stop blowing out.
    primary = accent
    primary_light = lighten(accent, 0.12)
    primary_lighter = lighten(accent, 0.24)
    primary_dark = darken(accent, 0.18)
    primary_darker = darken(accent, 0.32)

    selected_bg = mix(accent, background, 0.22)
    hover_bg = mix(accent, background, 0.40)
    # Same rule as Chroma GTK/Qt: text on accent picks background or foreground
    # by contrast — dark themes usually get dark text on loud accents (qBittorrent).
    # Keep that ink even when the selected fill is softened toward the surface,
    # otherwise mid-luma accents flip back to light-on-neon and wash out.
    on_accent = on_color(accent, [background, foreground])
    on_selected = on_accent
    on_hover = on_accent
    on_red = on_color(
        darken(red, 0.35) if dark else mix(red, background, 0.55),
        [background, foreground],
    )

    return {
        "slug": slugify(slug),
        "name": pretty_name(slug),
        "dark": dark,
        "background": background,
        "dark_background": dark_background,
        "darker_background": darker_background,
        "lighter_background": lighter_background,
        "foreground": foreground,
        "dark_foreground": dark_foreground,
        "light_foreground": light_foreground,
        "muted": muted,
        "selection": selection,
        "accent": accent,
        "red": red,
        "green": green,
        "yellow": yellow,
        "blue": blue,
        "cyan": cyan,
        "magenta": magenta,
        "text": text,
        "text_muted": text_muted,
        "on_accent": on_accent,
        "on_selected": on_selected,
        "on_hover": on_hover,
        "on_red": on_red,
        "selected_bg": selected_bg,
        "hover_bg": hover_bg,
        "primary": primary,
        "primary_light": primary_light,
        "primary_lighter": primary_lighter,
        "primary_dark": primary_dark,
        "primary_darker": primary_darker,
        **greys,
        "button_bg_red": darken(red, 0.35) if dark else mix(red, background, 0.55),
        "button_bg_red_hover": darken(red, 0.2) if dark else mix(red, background, 0.4),
        "button_bg_red_down": darken(red, 0.5) if dark else mix(red, background, 0.65),
    }


def css_rgb(color: str) -> str:
    r, g, b = hex_to_rgb(color)
    return f"rgb({r},{g},{b})"


def render_ovt(palette: dict[str, Any]) -> str:
    dark = "true" if palette["dark"] else "false"
    # Keep a stable OBS id so AutoReload can hot-swap the palette in place.
    display = f"Omarchy · {palette['name']}"
    return f"""@OBSThemeMeta {{
    name: '{display}';
    id: '{THEME_ID}';
    extends: 'com.obsproject.Yami';
    author: 'OmaOBS';
    dark: '{dark}';
}}

@OBSThemeVars {{
    --grey1: {css_rgb(palette['grey1'])};
    --grey2: {css_rgb(palette['grey2'])};
    --grey3: {css_rgb(palette['grey3'])};
    --grey4: {css_rgb(palette['grey4'])};
    --grey5: {css_rgb(palette['grey5'])};
    --grey6: {css_rgb(palette['grey6'])};
    --grey7: {css_rgb(palette['grey7'])};
    --grey8: {css_rgb(palette['grey8'])};

    --primary: {css_rgb(palette['primary'])};
    --primary_light: {css_rgb(palette['primary_light'])};
    --primary_lighter: {css_rgb(palette['primary_lighter'])};
    --primary_dark: {css_rgb(palette['primary_dark'])};
    --primary_darker: {css_rgb(palette['primary_darker'])};

    --bg_window: var(--grey7);
    --bg_base: var(--grey6);
    --bg_preview: var(--grey8);

    --text: {css_rgb(palette['text'])};
    --text_light: {css_rgb(palette['text'])};
    --text_muted: {css_rgb(palette['text_muted'])};
    --text_on_accent: {css_rgb(palette['on_accent'])};
    --text_on_selected: {css_rgb(palette['on_selected'])};
    --text_on_hover: {css_rgb(palette['on_hover'])};
    --text_on_red: {css_rgb(palette['on_red'])};

    --border_color: var(--grey5);

    --input_bg: var(--grey5);
    --input_bg_hover: var(--grey3);
    --input_bg_focus: var(--grey3);

    /* Softened vs raw accent — same idea as Chroma: keep accent readable */
    --list_item_bg_selected: {css_rgb(palette['selected_bg'])};
    --list_item_bg_hover: {css_rgb(palette['hover_bg'])};

    --input_border: var(--grey2);
    --input_border_hover: var(--primary_light);
    --input_border_focus: var(--primary);

    --button_bg: var(--grey5);
    --button_bg_hover: {css_rgb(palette['hover_bg'])};
    --button_bg_down: var(--primary_dark);
    --button_bg_disabled: var(--grey6);

    --button_bg_red: {css_rgb(palette['button_bg_red'])};
    --button_bg_red_hover: {css_rgb(palette['button_bg_red_hover'])};
    --button_bg_red_down: {css_rgb(palette['button_bg_red_down'])};

    --button_border: var(--grey5);
    --button_border_hover: var(--primary_light);
    --button_border_focus: var(--primary);

    --tab_bg: var(--input_bg);
    --tab_bg_hover: var(--grey3);
    --tab_bg_down: {css_rgb(palette['selected_bg'])};
    --tab_border: var(--grey3);
    --tab_border_hover: var(--primary_light);
    --tab_border_focus: var(--primary);
    --tab_border_selected: var(--primary);

    --scrollbar_handle: var(--grey5);
    --scrollbar_hover: var(--primary_light);
    --scrollbar_down: var(--grey3);
    --scrollbar_border: var(--grey5);

    --toolbutton_bg: var(--grey5);
    --toolbutton_bg_hover: {css_rgb(palette['hover_bg'])};
    --toolbutton_bg_down: var(--primary_dark);

    --palette_window: var(--bg_window);
    --palette_windowText: var(--text);
    --palette_base: var(--bg_base);
    --palette_highlight: {css_rgb(palette['selected_bg'])};
    --palette_highlightedText: var(--text_on_selected);
    --palette_text: var(--text);
    --palette_buttonText: var(--text);
}}

/* Yami hard-codes selection-color / selected item text to --text (light on
 * dark themes). Override like Chroma GTK: contrasting ink on accent fills. */
QWidget {{
    selection-background-color: {css_rgb(palette['selected_bg'])};
    selection-color: var(--text_on_selected);
}}

QDockWidget::title {{
    background-color: var(--bg_base);
}}

/* Menubar sits on bg_window; keep selected items on the softened accent +
 * contrasting ink (Yami defaults to raw --primary + --text). */
QMenuBar {{
    background-color: var(--bg_window);
    color: var(--text);
}}

QMenuBar::item {{
    background-color: transparent;
    color: var(--text);
}}

QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background-color: var(--list_item_bg_selected);
    color: var(--text_on_selected);
}}

QStatusBar {{
    background-color: var(--bg_window);
    color: var(--text);
}}

QMenu::item:selected,
QMenu > QWidget:selected,
QListView::item:selected,
QListWidget::item:selected,
QTreeView::item:selected,
QTreeWidget::item:selected,
QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:hover {{
    background-color: var(--list_item_bg_selected);
    color: var(--text_on_selected);
}}

QMenu::item:selected:hover,
QListView::item:selected:hover,
QListWidget::item:selected:hover,
QTreeView::item:selected:hover,
QTreeWidget::item:selected:hover {{
    background-color: var(--list_item_bg_hover);
    color: var(--text_on_hover);
}}

QMenu::item:hover,
QListView::item:hover,
QListWidget::item:hover,
QTreeView::item:hover,
QTreeWidget::item:hover {{
    background-color: var(--list_item_bg_hover);
    color: var(--text_on_hover);
}}

.button-primary,
.button-primary:hover,
.button-primary:focus {{
    color: var(--text_on_accent);
}}

#streamButton:!hover:!pressed.state-active,
#recordButton:!hover:!pressed.state-active,
#pauseRecordButton:!hover:!pressed.state-active,
#replayBufferButton:!hover:!pressed.state-active,
#virtualCamButton:!hover:!pressed.state-active,
#modeSwitch:!hover:!pressed.state-active,
#broadcastButton:!hover:!pressed.state-active {{
    background: var(--button_bg_red);
    border-color: var(--button_bg_red);
    color: var(--text_on_red);
}}

#streamButton:hover:!pressed.state-active,
#recordButton:hover:!pressed.state-active,
#pauseRecordButton:hover:!pressed.state-active,
#replayBufferButton:hover:!pressed.state-active,
#virtualCamButton:hover:!pressed.state-active,
#modeSwitch:hover:!pressed.state-active,
#broadcastButton:hover:!pressed.state-active {{
    background: var(--button_bg_red_hover);
    color: var(--text_on_red);
}}

.list-grid SceneTree::item:selected,
.list-grid SceneTree::item:checked,
.list-grid SceneTree::item:selected:hover {{
    background-color: var(--list_item_bg_selected);
    color: var(--text_on_selected);
}}

.list-grid SceneTree::item:hover {{
    background-color: var(--list_item_bg_hover);
    color: var(--text_on_hover);
}}

OBSQTDisplay {{
    qproperty-displayBackgroundColor: var(--bg_preview);
}}

VolumeMeter {{
    qproperty-backgroundNominalColor: {css_rgb(darken(palette['green'], 0.35))};
    qproperty-backgroundWarningColor: {css_rgb(darken(palette['yellow'], 0.35))};
    qproperty-backgroundErrorColor: {css_rgb(darken(palette['red'], 0.35))};
    qproperty-foregroundNominalColor: {css_rgb(palette['green'])};
    qproperty-foregroundWarningColor: {css_rgb(palette['yellow'])};
    qproperty-foregroundErrorColor: {css_rgb(palette['red'])};
}}
"""


def atomic_write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if isinstance(content, bytes):
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        with contextlib_suppress(FileNotFoundError):
            os.unlink(tmp)


def contextlib_suppress(*exceptions):
    class _Suppress:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return exc_type is not None and issubclass(exc_type, exceptions)

    return _Suppress()


def write_ovt(slug: str) -> Path:
    palette = palette_from_theme(slug)
    target = paths()["obs_themes"] / THEME_FILE
    atomic_write(target, render_ovt(palette))
    # Nudge mtime even when content is unchanged so OBS AutoReload fires.
    os.utime(target, None)
    return target


def load_user_ini(path: Path) -> configparser.ConfigParser:
    # OBS stores Qt binary blobs (geometry, docks) that contain '%'; disable
    # interpolation so ConfigParser does not treat them as format strings.
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # type: ignore[attr-defined]
    if path.is_file():
        parser.read(path, encoding="utf-8")
    return parser


def ensure_obs_theme_selected() -> bool:
    """Write Appearance Theme + AutoReload. Returns True if Theme key changed."""
    ini_path = paths()["user_ini"]
    parser = load_user_ini(ini_path)
    if "Appearance" not in parser:
        parser["Appearance"] = {}

    appearance = parser["Appearance"]
    previous = appearance.get("Theme", "")
    appearance["Theme"] = THEME_ID
    appearance["AutoReload"] = "true"

    # Preserve FontScale / Density defaults OBS expects.
    appearance.setdefault("FontScale", "10")
    appearance.setdefault("Density", "1")

    buf = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=ini_path.parent, prefix=".user.ini."
    )
    try:
        with buf:
            parser.write(buf, space_around_delimiters=False)
            buf.flush()
            os.fsync(buf.fileno())
        os.replace(buf.name, ini_path)
    finally:
        with contextlib_suppress(FileNotFoundError):
            os.unlink(buf.name)

    return previous != THEME_ID


def obs_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-x", "obs"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def notify(title: str, body: str) -> None:
    for cmd in (
        ["omarchy-shell", "notifications", "send", title, body],
        ["notify-send", title, body],
    ):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            return
        except FileNotFoundError:
            continue


def set_theme(slug: str, *, quiet: bool = False) -> int:
    slug = slugify(slug)
    if theme_dir(slug) is None:
        note(f"theme not found: {slug}")
        return 1

    ovt = write_ovt(slug)
    theme_changed = ensure_obs_theme_selected()

    state = paths()["state"]
    state.mkdir(parents=True, exist_ok=True)
    atomic_write(state / "current", slug + "\n")

    if not quiet:
        note(f"wrote {ovt}")
        note(f"OBS theme id {THEME_ID} ← {pretty_name(slug)}")

    if obs_running():
        if theme_changed:
            notify(
                "OmaOBS",
                f"Applied {pretty_name(slug)}. Restart OBS once to load the Omarchy theme.",
            )
            if not quiet:
                note("OBS is running — restart it once so it picks up the Omarchy theme")
        else:
            # AutoReload watches the ovt; rewrite + utime already happened.
            if not quiet:
                note("OBS should hot-reload via Appearance.AutoReload")
    return 0


def try_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_round_rect(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    radius: int = 8,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# omarchy-menu-images thumbnails every source to 1536×864 (16:9) with
# smartcrop BEFORE the Style carousel shows it in a 768×475 tile. Matching
# omarchy-menu-images serves 1536×864 then crops to a 768×475 tile
# (PreserveAspectCrop — shaves the sides). Keep the OBS chrome inside ~8%.
MOCKUP_SIZE = (1536, 864)
SAFE_X = 120
SAFE_Y = 48
# Bump when render_mockup chrome changes so cached tiles re-draw.
MOCKUP_LAYOUT_VERSION = "2"


def _input_token(path: Path | None) -> str:
    if path is None:
        return "none"
    try:
        st = path.stat()
    except OSError:
        return "missing"
    return f"{st.st_mtime_ns}:{st.st_size}"


def _preview_meta_path(dest: Path) -> Path:
    return Path(str(dest) + ".meta")


def _preview_fresh(dest: Path, fingerprint: str) -> bool:
    if not dest.is_file():
        return False
    try:
        return _preview_meta_path(dest).read_text(encoding="utf-8").strip() == fingerprint
    except OSError:
        return False


def _write_preview_meta(dest: Path, fingerprint: str) -> None:
    try:
        _preview_meta_path(dest).write_text(fingerprint + "\n", encoding="utf-8")
    except OSError:
        pass


def _preview_fingerprint(slug: str) -> str:
    directory = theme_dir(slug)
    colors = (directory / "colors.toml") if directory else None
    return f"layout:{MOCKUP_LAYOUT_VERSION}|colors:{_input_token(colors)}"


def render_mockup(palette: dict[str, Any], dest: Path, size: tuple[int, int] = MOCKUP_SIZE) -> Path:
    """OBS Studio chrome from a real Hackerman/OmaOBS window capture.

    Dock layout matches current OBS (Scenes+Sources left, preview center,
    mixer + transitions + controls along the bottom). Colours from
    colors.toml via the Yami grey/primary roles. Not a live grim per theme —
    Limine/TTY-style True Theme Vibe. Content stays inside SAFE_X.
    """
    w, h = size
    img = Image.new("RGB", size, hex_to_rgb(palette["grey8"]))
    draw = ImageDraw.Draw(img)

    font_sm = try_font(16)
    font_md = try_font(20)
    font_btn = try_font(18)

    # Outer window — flat, no fake rounded OS chrome (OBS is a normal client).
    win = (SAFE_X, SAFE_Y, w - SAFE_X, h - SAFE_Y)
    draw.rectangle(win, fill=hex_to_rgb(palette["grey7"]))

    x0, y0, x1, y1 = win
    # Menu bar
    menu_h = 28
    draw.rectangle((x0, y0, x1, y0 + menu_h), fill=hex_to_rgb(palette["grey7"]))
    menu = "File   Edit   View   Docks   Profile   Scene Collection   Tools   Help"
    draw.text((x0 + 12, y0 + 6), menu, font=font_sm, fill=hex_to_rgb(palette["text"]))

    body_top = y0 + menu_h
    status_h = 26
    bottom_h = 200  # mixer + transitions + controls row
    body_bottom = y1 - status_h - bottom_h

    left_w = 220
    # Left column: Scenes (top) + Sources (bottom)
    mid_y = body_top + int((body_bottom - body_top) * 0.42)
    scenes = (x0 + 4, body_top + 4, x0 + 4 + left_w, mid_y - 2)
    sources = (x0 + 4, mid_y + 2, x0 + 4 + left_w, body_bottom - 4)
    preview = (scenes[2] + 6, body_top + 4, x1 - 4, body_bottom - 4)

    draw.rectangle(scenes, fill=hex_to_rgb(palette["grey6"]))
    draw.rectangle(sources, fill=hex_to_rgb(palette["grey6"]))
    draw.rectangle(preview, fill=hex_to_rgb(palette["grey8"]))

    # Scenes header + selected row (accent fill like real OBS)
    draw.text((scenes[0] + 10, scenes[1] + 8), "Scenes", font=font_md, fill=hex_to_rgb(palette["text"]))
    sel = (scenes[0] + 6, scenes[1] + 36, scenes[2] - 6, scenes[1] + 64)
    draw.rectangle(sel, fill=hex_to_rgb(palette["selected_bg"]))
    draw.text((sel[0] + 10, sel[1] + 6), "Scene", font=font_sm, fill=hex_to_rgb(palette["on_selected"]))

    # Sources — Media / Game / Chat (no Display Capture, matching the capture)
    draw.text((sources[0] + 10, sources[1] + 8), "Sources", font=font_md, fill=hex_to_rgb(palette["text"]))
    src_rows = ["Media", "Game", "Chat"]
    sy = sources[1] + 36
    for index, label in enumerate(src_rows):
        row = (sources[0] + 6, sy, sources[2] - 6, sy + 28)
        if index == 1:
            draw.rectangle(row, fill=hex_to_rgb(palette["selected_bg"]))
            ink = palette["on_selected"]
        else:
            ink = palette["text"]
        draw.text((row[0] + 10, row[1] + 5), label, font=font_sm, fill=hex_to_rgb(ink))
        sy += 32

    # Preview canvas — empty black (no display capture)
    pad = 10
    canvas = (preview[0] + pad, preview[1] + pad, preview[2] - pad, preview[3] - 52)
    draw.rectangle(canvas, fill=hex_to_rgb(palette["darker_background"]))
    draw.text(
        (canvas[0] + 12, canvas[3] + 8),
        "33%    Scale to Window          No source selected",
        font=font_sm,
        fill=hex_to_rgb(palette["text_muted"]),
    )

    # Bottom docks: Audio Mixer | Transitions | Controls
    dock_top = body_bottom
    mixer_w = int((x1 - x0 - 12) * 0.50)
    trans_w = int((x1 - x0 - 12) * 0.18)
    mixer = (x0 + 4, dock_top + 4, x0 + 4 + mixer_w, y1 - status_h - 4)
    transitions = (mixer[2] + 4, dock_top + 4, mixer[2] + 4 + trans_w, y1 - status_h - 4)
    controls = (transitions[2] + 4, dock_top + 4, x1 - 4, y1 - status_h - 4)

    draw.rectangle(mixer, fill=hex_to_rgb(palette["grey6"]))
    draw.rectangle(transitions, fill=hex_to_rgb(palette["grey6"]))
    draw.rectangle(controls, fill=hex_to_rgb(palette["grey6"]))

    draw.text((mixer[0] + 10, mixer[1] + 8), "Audio Mixer", font=font_md, fill=hex_to_rgb(palette["text"]))
    meters = [
        ("Desktop", palette["green"], 0.15),
        ("Mic/Aux", palette["yellow"], 0.08),
        ("Chat", palette["green"], 0.22),
        ("Game", palette["primary"], 0.18),
    ]
    mw = max(36, (mixer[2] - mixer[0] - 24) // len(meters) - 10)
    mx = mixer[0] + 14
    bar_top = mixer[1] + 40
    bar_bot = mixer[3] - 28
    for label, color, level in meters:
        draw.text((mx, bar_top - 18), label[:7], font=font_sm, fill=hex_to_rgb(palette["text_muted"]))
        bar = (mx + 8, bar_top, mx + 8 + 18, bar_bot)
        draw.rectangle(bar, fill=hex_to_rgb(palette["grey8"]))
        fill_h = max(4, int((bar[3] - bar[1]) * level))
        draw.rectangle((bar[0], bar[3] - fill_h, bar[2], bar[3]), fill=hex_to_rgb(color))
        mx += mw

    draw.text((transitions[0] + 10, transitions[1] + 8), "Scene Transitions", font=font_sm, fill=hex_to_rgb(palette["text"]))
    draw_round_rect(
        draw,
        (transitions[0] + 10, transitions[1] + 36, transitions[2] - 10, transitions[1] + 64),
        palette["grey5"],
        radius=4,
    )
    draw.text((transitions[0] + 18, transitions[1] + 42), "Fade", font=font_sm, fill=hex_to_rgb(palette["text"]))
    draw.text((transitions[0] + 10, transitions[1] + 78), "300 ms", font=font_sm, fill=hex_to_rgb(palette["text_muted"]))

    # Controls — stacked like real OBS (Streaming often red-tinted in Yami)
    btns = [
        ("Start Streaming", palette["button_bg_red"], palette["on_red"]),
        ("Start Recording", palette["grey5"], palette["text"]),
        ("Studio Mode", palette["grey5"], palette["text"]),
        ("Settings", palette["grey5"], palette["text"]),
    ]
    by = controls[1] + 10
    for label, fill, ink in btns:
        box = (controls[0] + 10, by, controls[2] - 10, by + 34)
        draw_round_rect(draw, box, fill, radius=6)
        tw = draw.textlength(label, font=font_btn)
        draw.text(
            (int((box[0] + box[2] - tw) / 2), by + 8),
            label,
            font=font_btn,
            fill=hex_to_rgb(ink),
        )
        by += 42

    # Status bar
    draw.rectangle((x0, y1 - status_h, x1, y1), fill=hex_to_rgb(palette["grey7"]))
    draw.text(
        (x0 + 12, y1 - status_h + 5),
        "CPU 0.4%    60.00 fps",
        font=font_sm,
        fill=hex_to_rgb(palette["text_muted"]),
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="PNG", optimize=True)
    return dest


def preview_path(slug: str) -> Path:
    return paths()["cache"] / "previews" / f"{slugify(slug)}.png"


def generate_preview(slug: str, *, force: bool = False) -> Path:
    dest = preview_path(slug)
    fp = _preview_fingerprint(slug)
    if not force and _preview_fresh(dest, fp):
        return dest
    palette = palette_from_theme(slug)
    render_mockup(palette, dest)
    _write_preview_meta(dest, fp)
    return dest


def bust_image_picker_cache(preview_root: Path) -> None:
    """Invalidate omarchy-menu-images rows/thumbnails for our preview dir."""
    try:
        os.utime(preview_root, None)
    except OSError:
        pass

    cache_dir = Path(
        os.environ.get(
            "OMAOBS_IMAGE_SELECTOR_CACHE",
            home() / ".cache/omarchy/image-selector",
        )
    )
    if not cache_dir.is_dir():
        return

    needle = str(preview_root.resolve())
    for path in cache_dir.iterdir():
        name = path.name
        if not (
            name.endswith(".rows")
            or name.endswith(".signature")
            or name.endswith(".fast-signature")
            or name.endswith(".rows.lock")
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle in text or str(preview_root) in text:
            path.unlink(missing_ok=True)

    index = cache_dir / "index.tsv"
    if index.is_file():
        try:
            lines = index.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            lines = []
        kept: list[str] = []
        for line in lines:
            parts = line.split("\t")
            if parts and (needle in parts[0] or str(preview_root) in parts[0]):
                if len(parts) >= 3:
                    (cache_dir / f"{parts[2]}.jpg").unlink(missing_ok=True)
                    (cache_dir / f"{parts[2]}.jpg.lock").unlink(missing_ok=True)
                continue
            kept.append(line)
        try:
            atomic_write(index, ("\n".join(kept) + ("\n" if kept else "")))
        except OSError:
            pass


def _preview_pool(workers: int) -> ProcessPoolExecutor:
    # See omacursor: force fork so bin/* → python3 lib/*.py workers do not
    # re-import __main__ under Python 3.14's forkserver default.
    try:
        ctx = mp.get_context("fork")
    except ValueError:
        ctx = mp.get_context()
    return ProcessPoolExecutor(max_workers=workers, mp_context=ctx)


def generate_all_previews() -> list[Path]:
    out: list[Path] = []
    preview_root = paths()["cache"] / "previews"
    preview_root.mkdir(parents=True, exist_ok=True)
    wanted = sorted(set(list_theme_slugs()))
    wanted_set = set(wanted)
    for existing in preview_root.glob("*.png"):
        if existing.stem not in wanted_set:
            existing.unlink(missing_ok=True)
            _preview_meta_path(existing).unlink(missing_ok=True)
    dirty = [
        slug
        for slug in wanted
        if not _preview_fresh(preview_path(slug), _preview_fingerprint(slug))
    ]
    if not dirty:
        return out
    workers = max(1, min(len(dirty), os.cpu_count() or 2))
    with _preview_pool(workers) as pool:
        futures = {
            pool.submit(generate_preview, slug, force=True): slug for slug in dirty
        }
        for fut in as_completed(futures):
            slug = futures[fut]
            try:
                out.append(fut.result())
            except Exception as error:  # noqa: BLE001
                note(f"preview {slug}: {error}")
    bust_image_picker_cache(preview_root)
    return out


def cmd_list(_: argparse.Namespace) -> int:
    for slug in list_theme_slugs():
        print(slug)
    return 0


def cmd_current(_: argparse.Namespace) -> int:
    slug = current_omaobs_slug()
    if not slug:
        return 1
    print(slug)
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    targets = [slugify(args.theme)] if args.theme else list_theme_slugs()
    if args.theme and theme_dir(args.theme) is None:
        note(f"theme not found: {args.theme}")
        return 1
    if not targets:
        note("no themes with colors.toml found")
        return 1
    # Only the selected/current palette is written into the live Omarchy.ovt;
    # generating "all" still only prepares previews unless --theme is given,
    # or sync writes the active desktop theme.
    if args.theme:
        write_ovt(args.theme)
        print(paths()["obs_themes"] / THEME_FILE)
        return 0
    for slug in targets:
        generate_preview(slug)
    print(len(targets))
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    if args.theme:
        if theme_dir(args.theme) is None:
            note(f"theme not found: {args.theme}")
            return 1
        path = generate_preview(args.theme)
        print(path)
        return 0
    paths_written = generate_all_previews()
    print(len(paths_written))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    return set_theme(args.theme, quiet=args.quiet)


def cmd_sync(args: argparse.Namespace) -> int:
    slug = current_omarchy_slug()
    if not slug:
        note("no current Omarchy theme")
        return 1
    return set_theme(slug, quiet=args.quiet)


def cmd_switcher(_: argparse.Namespace) -> int:
    """Build mockups and open omarchy-menu-images, printing the chosen slug."""
    generate_all_previews()
    preview_dir = paths()["cache"] / "previews"
    current = current_omaobs_slug() or current_omarchy_slug()
    selected = ""
    if current and (preview_dir / f"{current}.png").is_file():
        selected = str(preview_dir / f"{current}.png")

    cmd = [
        "omarchy-menu-images",
        "--print-name",
        "--show-labels",
        "--filterable",
    ]
    if selected:
        cmd.extend(["--selected", selected])
    cmd.append(str(preview_dir))

    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        note("omarchy-menu-images not found")
        return 1

    choice = (result.stdout or "").strip()
    if result.returncode != 0 and not choice:
        return result.returncode or 1
    if choice:
        print(choice)
    return 0


MENU_START = "  // omaobs:start"
MENU_END = "  // omaobs:end"


def strip_jsonc(content: str) -> str:
    out: list[str] = []
    index = 0
    in_string = False
    escape = False
    while index < len(content):
        character = content[index]
        if in_string:
            out.append(character)
            if escape:
                escape = False
            elif character == "\\":
                escape = True
            elif character == '"':
                in_string = False
            index += 1
        elif character == '"':
            in_string = True
            out.append(character)
            index += 1
        elif content.startswith("//", index):
            index = content.find("\n", index)
            if index < 0:
                break
        elif content.startswith("/*", index):
            finish = content.find("*/", index + 2)
            index = len(content) if finish < 0 else finish + 2
        else:
            out.append(character)
            index += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def remove_marked(content: str, start: str, end: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    return pattern.sub("", content)


def menu_action() -> str:
    switcher = plugin_dir() / "bin" / "omaobs-switcher"
    setter = plugin_dir() / "bin" / "omaobs-set"
    return (
        f'theme="$({switcher})"; '
        f'[[ -n $theme ]] && {setter} "$theme"'
    )


def install_menu_entry() -> None:
    path = paths()["menu"]
    content = path.read_text(encoding="utf-8") if path.is_file() else "{\n}\n"
    content = remove_marked(content, MENU_START, MENU_END)
    entries = [
        (
            "style.obs",
            {
                "icon": "󰕧",
                "label": "OBS Themes",
                "description": "Preview Omarchy palettes on a mock OBS window and apply a Yami theme",
                "action": menu_action(),
            },
        )
    ]
    brace = content.find("{")
    if brace < 0:
        raise RuntimeError(f"menu config has no root object: {path}")
    body = [MENU_START]
    import json

    for key, value in entries:
        body.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    body.append(MENU_END)
    insertion = "\n".join(body) + "\n"
    atomic_write(path, content[: brace + 1] + "\n" + insertion + content[brace + 1 :])


def uninstall_menu_entry() -> None:
    path = paths()["menu"]
    if not path.is_file():
        return
    content = path.read_text(encoding="utf-8")
    if MENU_START in content:
        atomic_write(path, remove_marked(content, MENU_START, MENU_END))


def cmd_install_menu(_: argparse.Namespace) -> int:
    install_menu_entry()
    note(f"menu entry → {paths()['menu']}")
    return 0


def cmd_uninstall_menu(_: argparse.Namespace) -> int:
    uninstall_menu_entry()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omaobs", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List Omarchy theme slugs with colors.toml").set_defaults(func=cmd_list)
    sub.add_parser("current", help="Print the last applied OmaOBS theme slug").set_defaults(func=cmd_current)

    generate = sub.add_parser("generate", help="Write Omarchy.ovt for a theme, or warm all previews")
    generate.add_argument("theme", nargs="?", help="Theme slug or display name")
    generate.set_defaults(func=cmd_generate)

    preview = sub.add_parser("preview", help="Render mockup PNG(s)")
    preview.add_argument("theme", nargs="?", help="Theme slug; omit for all")
    preview.set_defaults(func=cmd_preview)

    set_cmd = sub.add_parser("set", help="Generate and apply a theme to OBS")
    set_cmd.add_argument("theme", help="Theme slug or display name")
    set_cmd.add_argument("--quiet", action="store_true")
    set_cmd.set_defaults(func=cmd_set)

    sync = sub.add_parser("sync", help="Apply the current Omarchy desktop theme to OBS")
    sync.add_argument("--quiet", action="store_true")
    sync.set_defaults(func=cmd_sync)

    sub.add_parser("switcher", help="Open the mockup picker and print the selected slug").set_defaults(
        func=cmd_switcher
    )
    sub.add_parser("install-menu", help="Add Style > OBS Themes to the Omarchy menu").set_defaults(
        func=cmd_install_menu
    )
    sub.add_parser("uninstall-menu", help="Remove the Style > OBS Themes menu entry").set_defaults(
        func=cmd_uninstall_menu
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0
    except Exception as error:  # noqa: BLE001 — CLI boundary
        note(str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
