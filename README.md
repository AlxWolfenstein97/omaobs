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

> Illustrative mockup of the same pipeline (Hackerman): see
> [preview-mockup.png](preview-mockup.png).

## Goals (and honest limits)

These Style plugins extend Omarchy’s theme system **without requiring theme
authors — or you — to ship anything extra**. Official themes, your forks, and
third-party installs all work as long as they have a `colors.toml`.

| Goal | What that means here |
|------|----------------------|
| Zero extra assets | No per-theme OBS screenshots. Colours come from `colors.toml` alone. |
| Extreme compatibility | Stock + user + foreign themes all appear in the picker automatically. |
| Illustrative mockups | Centered OBS-ish chrome. **Not** a live OBS window capture and **not** WYSIWYG. |
| Carousel-safe | Mockups are 1536×864 (menu-images thumbnail size) with ~8% side inset so the 768×475 tile crop does not shave the subject. |
| Slow pickers are OK | Warming every theme PNG takes a moment; that is the cost of generating previews instead of bundling assets. |

True WYSIWYG would mean launching OBS and grim’ing it per theme — slow,
fragile, and out of scope. The applied `Omarchy.ovt` *is* real; only the
picker art is drawn.

## What you get

- **Style → OBS Themes** in the Omarchy menu — same carousel picker as Unlock /
  Theme / Background.
- **Live theme discovery** — every Omarchy theme with a `colors.toml` under
  `~/.config/omarchy/themes` or `$OMARCHY_PATH/themes`.
- **Mockups** — a simplified OBS main window (scenes, sources, preview, mixer,
  stream/record) coloured from that theme’s background / accent / danger tones.
- **OBS format** — a Yami variant at
  `~/.config/obs-studio/themes/Omarchy.ovt`.
- **Apply** — sets `Appearance.Theme` + `AutoReload=true` in `user.ini`, so a
  running OBS that already uses Omarchy hot-reloads when the palette changes.
- **theme-set hook** — `omarchy theme set …` keeps OBS in step automatically.

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

- Live screenshot captured with
  [OMCP](https://github.com/btsouth/omarchy-omcp) (Omarchy MCP desktop bridge —
  themes, windows, screenshots, …) on the official **Hackerman** theme.
  `omarchy plugin add https://github.com/btsouth/omarchy-omcp --enable`
- Mockup strip: [preview-mockup.png](preview-mockup.png).
- Sibling Style plugins: [OmaBoot](https://github.com/AlxWolfenstein97/omaboot),
  [OmaVT](https://github.com/AlxWolfenstein97/omavt),
  [OmaTTY](https://github.com/AlxWolfenstein97/omatty).
- [Omarchy](https://omarchy.org/) — theme pipeline, Style menu image picker, and
  `theme-set` hooks this plugin hooks into.

## License

MIT — see [LICENSE](LICENSE).
