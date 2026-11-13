# Agent instructions — Cubase Logic 13-inspired theme

## Goal
Apply the **complete** `themes/logic13-graphite48.json` theme, primarily inspired by the dark Logic Pro 13 design direction. This is not an older gray Logic theme, not a purple wash over every control, and not a claim to reproduce Liquid Glass. Replace the original 16 track colors with all 48; do not merely append colors.

## Non-negotiable safety rules

1. Read `README.md` and `docs/compatibility.md` before touching the user's settings.
2. Prefer the offline Python CLI. Do not reuse screen-coordinate GUI automation from another computer.
3. Detect the installed Cubase version and exact preferences directory. Do not assume a username, drive, language, resolution, or device configuration.
4. Run `inspect`, then `apply --dry-run`. Never interpret a successful XML parse as proof that a new Cubase version is compatible.
5. Before real writes, ask the user to save and fully quit Cubase, including its Hub. Never force-kill it. The CLI refuses writes while Cubase runs.
6. Use `apply` to create a local backup and change only the documented fields. Do not replace the user's entire preferences with someone else's XML. Never edit audio/MIDI devices, routing, shortcuts, plug-in parameters, musical content, meter thresholds, or the original alpha of cursors.
7. Missing/duplicate keys, unexpected palettes, or unknown custom meter colors are stop conditions. Investigate and obtain a decision instead of guessing IDs or bypassing validation. `--allow-untested` is an explicit compatibility acknowledgement, NOT permission to ignore schema failures.
8. Run `verify`, reopen Cubase, and visually check the main window. Distinguish file validation from runtime visual validation; report untested pages honestly.
9. Existing `.cpr` projects carry their own palettes. Follow `docs/existing-projects.md`; never hex-edit a project. Back it up before any project-level changes. If the user asks for sequential colors, assign track 1 -> palette 1, track 2 -> palette 2, etc. Do not infer instrument grouping.
10. Do not toggle disabled tracks, change record/monitor states, or create musical material merely to make a theme screenshot look better.

## Public repository privacy

- Publish only source, theme parameters, synthetic fixtures and synthetic previews.
- NEVER commit complete `UserPreferences.xml`, `Defaults.xml`, backup manifests/journals, `.cpr` projects, audio/media, unredacted screenshots, personal filesystem paths, device inventories, tokens or private logs.
- Backups contain private configuration and must remain local. `.gitignore` is a guard, not a substitute for reviewing `git diff --cached`.
- Use public/noreply Git identity when the user has not chosen another identity.

## Useful commands

```sh
python cubase_theme.py inspect
python cubase_theme.py apply --dry-run
# User saves and quits Cubase here.
python cubase_theme.py apply
python cubase_theme.py verify
python -m unittest discover -s tests -v
```

Use explicit `--prefs-dir` if discovery is ambiguous. Tested support is Windows Cubase 14; macOS and other major versions require reviewed, experimental use. Keep the 48-color palette, meter semantics (green/yellow/red), silver faders, restrained rack accents, and previous-track-color +1 behavior.

## Boundaries

Native Windows/legacy dialogs, fixed stock plug-in skins, third-party plug-ins, undocumented derived colors, and Apple-style glass effects are not controlled by this theme. Do not modify Windows globally or patch Cubase executables to hide these limitations.
