# OmaOBS

**Omarchy themes your desktop. OmaOBS carries the same palette into OBS Studio —
mockup previews in the Style menu, then a real Yami variant OBS can load.**

![OmaOBS on Hackerman — live OBS Studio wearing the Omarchy palette](preview.png)

Stock Omarchy paints Hyprland, the terminal, and your GTK apps. OBS keeps its
own skin. Your desktop wears Hackerman neon; the encoder wears default grey.

OmaOBS closes that gap the same way Style → Unlock works for Plymouth: a
labelled image picker, one mockup per installed theme, and an apply step that
writes what OBS understands. Pick once, or let `omarchy theme set` keep OBS in
lockstep forever after.

## Goals (and honest limits)

These Style plugins extend Omarchy’s theme system **without requiring theme
authors — or you — to ship anything extra**. Official themes, your forks, and
third-party installs all work as long as they have a `colors.toml`. That
“every theme” contract is intentional: once the desktop can follow farther,
making *another* theme is more worth it. Longer origin story, stop-line, and
marketplace notes live in [Chroma](https://github.com/AlxWolfenstein97/chroma).

| Goal | What that means here |
|------|----------------------|
| Zero extra assets | No per-theme OBS screenshots in themes. Colours come from `colors.toml` alone. |
| Extreme compatibility | Stock + user + foreign themes all appear in the picker automatically. |
| True Theme Vibe | Dock layout tracked from a live OmaOBS window; recoloured per theme. **Not** grim’ing OBS twenty times. |
| Carousel-safe | Mockups are 1536×864 with ~8% side inset so the 768×475 tile crop does not shave the chrome. |
| Slow pickers are OK | Warming every theme PNG takes a moment; that is the cost of generating previews instead of bundling assets. |

The applied `Omarchy.ovt` *is* real Yami. Only the picker art is drawn — same
True Theme Vibe idea as [OmaBoot](https://github.com/AlxWolfenstein97/omaboot) /
[OmaVT](https://github.com/AlxWolfenstein97/omavt).

### Why a picker if `theme-set` already syncs?

Chroma can stay silent — it rewrites toolkit CSS for the whole desktop. OBS is
one specific surface with a real theme format. The Style carousel is still
worth it: you can skim how OBS would look across **every** installed theme
faster than applying and eyeballing each one by hand. Pick once (or never —
the hook keeps pace after that). Same idea as OmaCursor / OmaBoot / OmaVT.

## What you get

- **Style → OBS Themes** in the Omarchy menu — same carousel picker as Unlock /
  Theme / Background.
- **Live theme discovery** — every Omarchy theme with a `colors.toml` under
  `~/.config/omarchy/themes` or `$OMARCHY_PATH/themes`.
- **Mockups** — current OBS dock chrome (Scenes + Sources, empty preview,
  mixer, Fade transitions, control stack) coloured from that theme’s palette.
- **OBS format** — a Yami variant at
  `~/.config/obs-studio/themes/Omarchy.ovt`.
- **Apply** — sets `Appearance.Theme` + `AutoReload=true` in `user.ini`, so a
  running OBS that already uses Omarchy hot-reloads when the palette changes.
- **theme-set hook** — `omarchy theme set …` keeps OBS in step automatically.

## Mockups: True Theme Vibe (live OBS as layout base)

OBS has a real theme format, so we do not need per-theme screenshots in theme
repos. One clean window capture locks the dock silhouette; Pillow recolours it
from every `colors.toml`.

**How it was done**

1. Apply OmaOBS on official **Hackerman**, open OBS (Display Capture parked so the
   preview stays empty and readable).
2. Capture the window (OMCP + grim) — Scenes/Sources left, black preview,
   Audio Mixer + Scene Transitions + Controls along the bottom.
3. Trace that chrome in `lib/omaobs.py`, carousel-safe (SAFE_X=120), then
   recolour from each theme’s Yami grey/primary roles.

**Compare — live OmaOBS window vs generated mockup (same theme):**

| Real OBS (Hackerman / OmaOBS) | OmaOBS mockup (Hackerman) |
| --- | --- |
| ![Live OBS on Hackerman — reference](reference-obs-hackerman.png) | ![Generated OmaOBS mockup — same docks, drawn from colors.toml](preview-mockup.png) |

Hero above is the live capture. Picker tiles are the drawn mockups.

## Install

```sh
omarchy plugin add https://github.com/AlxWolfenstein97/omaobs.git --enable
```

That clones into `~/.config/omarchy/plugins/io.github.alxwolfenstein97.omaobs`.
Or from a checkout:

```sh
~/.config/omarchy/plugins/io.github.alxwolfenstein97.omaobs/install.sh
omarchy plugin enable io.github.alxwolfenstein97.omaobs
```

**Needs:** OBS Studio 30.2+ (composable Yami themes), Omarchy’s image picker,
Python 3 with Pillow (`python-pillow` on Arch).

## How it works

1. `bin/omaobs-switcher` renders PNG mockups into
   `~/.cache/omarchy/omaobs/previews/`, then opens `omarchy-menu-images`.
2. On selection, `bin/omaobs-set` maps `colors.toml` → Yami `@OBSThemeVars`
   (greys, primary/accent, text, stream/record reds, meter colours) and writes
   `Omarchy.ovt` with a stable id `io.github.alxwolfenstein97.omaobs`.
3. `user.ini` gets `Appearance.Theme` + `AutoReload=true`.
4. `~/.config/omarchy/hooks/theme-set.d/omaobs` runs `omaobs sync` after every
   desktop theme change.

First time with OBS already open: restart OBS once so it discovers the Omarchy
theme. After that, palette switches hot-reload via `Appearance.AutoReload`.

CLI:

```sh
omaobs list
omaobs preview              # warm all mockups
omaobs switcher             # picker → prints slug
omaobs set tokyo-night      # generate + apply
omaobs sync                 # apply current desktop theme
omaobs current
```

## Remove

```sh
~/.config/omarchy/plugins/io.github.alxwolfenstein97.omaobs/uninstall.sh
omarchy plugin disable io.github.alxwolfenstein97.omaobs
omarchy plugin remove io.github.alxwolfenstein97.omaobs
```

Uninstall removes the menu row, theme-set hook, generated `Omarchy.ovt`, and
OmaOBS state/cache. Scene collections are untouched.

## Limits, honestly

- OBS only hot-reloads the *current* theme file. Switching *to* Omarchy for the
  first time needs one OBS restart (or pick Omarchy under Settings → Appearance).
- Individual stock OBS variants (Acri, Rachni, …) are left alone; OmaOBS owns
  only `Omarchy.ovt`.

## Check

```sh
bash ~/.config/omarchy/plugins/io.github.alxwolfenstein97.omaobs/check.sh
```

## Credits

- **Layout reference:** [`reference-obs-hackerman.png`](reference-obs-hackerman.png)
  — live OBS on official **Hackerman** via OmaOBS (Display Capture removed for a
  clean preview). Captured with [OMCP](https://github.com/btsouth/omarchy-omcp)
  + grim. Compare to [`preview-mockup.png`](preview-mockup.png).
- Sibling Style plugins: [OmaBoot](https://github.com/AlxWolfenstein97/omaboot),
  [OmaVT](https://github.com/AlxWolfenstein97/omavt),
  [OmaTTY](https://github.com/AlxWolfenstein97/omatty),
  [OmaCursor](https://github.com/AlxWolfenstein97/omacursor),
  [Chroma](https://github.com/AlxWolfenstein97/chroma).
- [Omarchy](https://omarchy.org/) — theme pipeline, Style menu image picker, and
  `theme-set` hooks this plugin hooks into.

## License

MIT — see [LICENSE](LICENSE).
