[![English](https://img.shields.io/badge/English-blue?style=flat-square)](README.md) [![简体中文](https://img.shields.io/badge/%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-lightgrey?style=flat-square)](README.zh-CN.md)

# Cubase · Logic 13-inspired Graphite 48

A complete dark color scheme for Cubase, with **offline tools to apply, verify, and restore it**. Primarily inspired by the new Logic Pro 13 design direction: near-black workspaces, graphite panels, and silver faders, with vivid blue / purple / magenta / teal reserved for track content.

**All 16 factory colors are replaced with 48 redesigned colors—not appended to the original palette.**

> Currently validated on **Windows + Cubase 14**. Requires Python **3.10+**, with only the standard library and no third-party dependencies. Other platforms and versions are experimental and are not guaranteed to be compatible.
>
> This is a custom theme, not an official Apple palette. It does not modify application skins or add Liquid Glass to Cubase.

![Synthetic theme and palette preview](docs/preview.svg)

*The preview above is generated from the theme parameters. It is not an actual project screenshot or a promise of a particular Cubase layout. This repository contains no private projects, audio, complete preference files, or actual project screenshots.*

## Moving to another computer? Give your agent this prompt

> Follow this repository's `AGENTS.md` and `README.md` to apply the complete Logic Pro 13-inspired Graphite 48 color scheme to Cubase on this computer. First detect the version and preferences directory, then run inspect and a dry run. Ask me to save and fully quit Cubase before backing up and directly editing the configuration files. Then run verify, reopen Cubase, and check the result. Do not overwrite my keyboard shortcuts, audio devices, routing, or plug-in settings. Replace all 16 factory colors with the new 48-color palette, and keep “previous track color +1” behavior. Existing projects need to load the default palette separately; do not modify project files without confirmation. Do not upload any local configuration or backups to GitHub.

## What's included

| Scope | Design |
|---|---|
| Main interface | 13 public color settings: panels, focus, arrangement/editor backgrounds and grids, ruler, and cycle area |
| Track palette | 48 colors: 16 primary colors + 16 soft variants + 16 dark variants |
| Track-type defaults | All 9 types configured; sequential coloring remains previous color +1 |
| Mixer faders | 11 types of silver faders with subtle hue differences |
| Channel Strip | 6 coordinated functional accent colors |
| Racks | 21 settings, including inserts, sends, EQ, routing, and modulators |
| Meters | Consistent colors across 15 scales; original threshold positions, flags, and measurement modes are preserved |
| MIDI editors | 6 palettes: pitch, channel, velocity, voice, chord/scale, and grid match |
| Auxiliary palettes | 4 palettes: Note Expression, Score, SoundSlot, and Symbol |
| Display details | 3 cursor types, waveform/note brightness, event opacity and selection borders, and track/channel tint strength |

Main interface colors:

| Purpose | HEX |
|---|---|
| Panel base | `#28282A` |
| Arrangement background | `#141416` |
| Editor background | `#19191C` |
| Focus blue | `#589DE8` |
| Active cycle purple | `#9470D8` |

All color values and field mappings are defined in [`themes/logic13-graphite48.json`](themes/logic13-graphite48.json). Nothing is tied to a particular computer's username or drive paths.

## Quick start

### 1. Get the repository

```sh
git clone https://github.com/TallMessiWu/cubase-logic13-theme.git
cd cubase-logic13-theme
python --version
```

For a fresh Cubase installation, launch it once and quit normally so that the complete configuration is generated.

### 2. Inspect and preview changes (no writes)

```sh
python cubase_theme.py inspect
python cubase_theme.py apply --dry-run
```

On Windows, discovery looks for directories under `%APPDATA%\Steinberg\Cubase*` containing both configuration files. If multiple versions or directories are found, it stops and asks for an explicit path rather than choosing one automatically.

To explicitly select Cubase 14 in PowerShell:

```powershell
python .\cubase_theme.py apply --dry-run --prefs-dir "$env:APPDATA\Steinberg\Cubase 14_64"
```

Read-only operations can run while Cubase is open, but they read files on disk—not the application's unsaved in-memory state.

### 3. Save your projects, fully quit Cubase, then apply

**Close the Hub too. Do not force-kill any processes.**

```sh
python cubase_theme.py apply
python cubase_theme.py verify
```

Applying the theme only touches:

- `UserPreferences.xml`: display settings for the interface, faders, racks, meters, editors, and related elements.
- `Defaults.xml`: global track and auxiliary default palettes.

It does not replace your entire preferences or modify audio devices, keyboard shortcuts, plug-in parameters, audio files, or `.cpr` projects. If the theme is already applied, running it again does not add duplicate colors or create unnecessary backups.

### 4. Reopen Cubase and check the actual appearance

The main interface should show graphite-black and gray surfaces, silver faders, and coordinated functional rack colors. Start with an empty project to inspect the 48-color palette.

**Existing projects and templates may store their own palettes.** To update a project's palette, open:

> Project → Project Colors Setup → Options → **Reset Color Set to Default** → Apply

Do not choose **Reset Color Set to Factory Settings**. Recoloring existing tracks sequentially as 1, 2, 3 requires a separate step; “previous track color +1” only controls newly created tracks. See [Existing projects](docs/existing-projects.md).

## Backups and restore

Before each actual write, the tool saves complete local original files, checksums, and a field-level change journal **outside the repository**. The default location on Windows is:

```text
%LOCALAPPDATA%\CubaseLogicTheme\backups\<timestamp-random-id>\
```

The command output shows the actual backup directory. **These backups contain personal configuration and must not be published.** Use `--backup-root` to choose another location, but it must not be inside the active preferences directory or this repository.

After saving and fully quitting Cubase:

```sh
python cubase_theme.py restore --backup "/path/to/the/printed/backup-directory" --dry-run
python cubase_theme.py restore --backup "/path/to/the/printed/backup-directory"
```

Restore uses the field-level journal to revert theme changes rather than overwriting entire files with old copies. This preserves unrelated preferences changed later and tolerates runtime object IDs rewritten by Cubase. If a targeted color, palette, or meter structure has been changed separately, restore reports a conflict and stops for manual review by the agent.

Restore only affects global configuration. **It does not revert palettes or track colors already saved inside projects.** Back up projects separately.

## Compatibility and limitations

- **Only Windows Cubase 14 has been validated.** New versions and macOS require a schema review first, plus explicit `--prefs-dir` and `--allow-untested` arguments. This flag does not bypass safety checks.
- Missing fields, duplicate fields, unexpected palette lengths, and unrecognized custom meter colors all cause the tool to stop. Do not ignore these errors just to make it run.
- Default names do not depend on whether the interface is in Chinese or English; existing editor palette names are preserved.
- Recording, warning, and clipping states must remain meaningful, not be confused for decoration. Changing meter colors does not change thresholds.
- Third-party plug-ins, fixed built-in skins, Windows/legacy native dialog backgrounds, and undocumented derived colors cannot be controlled uniformly. Some windows may remain light gray.
- The tool does not change the global Windows theme, patch Cubase executables, or attempt to edit binary `.cpr` files directly.

See [Compatibility and implementation boundaries](docs/compatibility.md).

## Development and testing

```sh
python -m unittest discover -s tests -v
python tools/render_preview.py
```

Tests use only synthetic configuration files. They cover idempotency, preservation of unrelated settings, entities and line endings, process checks, conflict detection, scoped restore, and rollback on write failure. Cross-platform Python tests in CI do not mean that Cubase itself has been validated on those systems.

## Repository contents

```text
README.md                       English documentation (default)
README.zh-CN.md                 Chinese documentation
cubase_theme.py                 Portable offline CLI
themes/logic13-graphite48.json   Complete color parameters and field mappings
AGENTS.md                       Operating rules for migration agents
docs/compatibility.md           Compatibility, safety, and limitations
docs/existing-projects.md       Existing-project palettes and sequential coloring
docs/preview.svg                Synthetic preview with no private data
tests/test_theme.py             Synthetic configuration tests
```

MIT License. Not affiliated with Apple or Steinberg; product names are used only to describe the design inspiration and target application.
