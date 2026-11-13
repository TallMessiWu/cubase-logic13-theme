# Compatibility and implementation boundaries

## Tested

- Windows, Cubase 14, preference directory `Cubase 14_64`.
- The design was loaded in Cubase and the main project window visually inspected.
- The portable CLI was checked against an already-themed real Cubase 14 profile: dry run produced zero changes and verification passed.
- Automated tests use synthetic settings, never a user's real profile. They cover apply, idempotency, scoped restore, runtime object-ID changes, unrelated settings, process guards, conflict detection, CRLF/entities/comments, backup integrity assumptions and write-failure rollback. CI runs Python 3.10/3.12 on Windows and Linux; Linux CI is not a claim that Cubase itself runs there.

Python 3.10 or newer; standard library only. No pip packages, GUI automation, administrator rights or network access are needed to apply the theme.

## Other devices and versions

The CLI can discover macOS preference directories, but macOS and other major Cubase versions have **not** been validated. First launch and normally quit Cubase so the preference files exist. Inspect the actual schema and preserve a backup.

For an explicitly reviewed experimental target:

```sh
python cubase_theme.py inspect --prefs-dir "/path/to/the/actual/Cubase/preferences"
python cubase_theme.py apply --dry-run --prefs-dir "/path/to/the/actual/Cubase/preferences" --allow-untested
```

`--allow-untested` requires an explicit path and does not bypass missing-key, palette-size, unknown-meter-color or process checks. If multiple Cubase profiles exist, automatic discovery refuses to choose one. Do not copy opaque field IDs into another version without checking.

## Fields and safety

- Main UI: 13 public surface color fields; implicit fields may be added. Unknown derived/internal IDs and `AppColorSeed` are preserved.
- All 9 track-type defaults, 11 fader fields, 6 strip fields and 21 rack fields.
- 15 known meter scales: only `Color`/`Color2` are transformed. Positions, flags and modes are unchanged. Unknown custom colors fail preflight rather than being silently remapped.
- 6 MIDI editor palettes and 4 auxiliary palettes: names, lengths and other fields are preserved. Only the global Event Colors palette is deliberately replaced with 48 named colors.
- 3 cursor overlays preserve their existing alpha.
- Audio/MIDI display brightness, event opacity/selection borders, track/channel tint and automatic color mode are also configured.
- Numeric colors use packed `AARRGGBB`; signed and unsigned 32-bit representations compare equivalently.

Cubase's XML may contain HTML named entities and runtime object IDs. Validation expands entities only in memory. Edits use text spans instead of serializing the whole document. Restore uses a field-level journal, tolerates changed object IDs and preserves unrelated settings. If a targeted color, palette or meter structure has since been edited, restore stops with a conflict rather than overwriting those choices.

The two files cannot be committed as one filesystem transaction. Each replacement is atomic; a caught failure rolls back already-written files, with complete originals retained in a separate local backup. A power loss between replacements still requires restoring/reviewing the backup. Keep Cubase closed throughout a write; the process and concurrency checks are safeguards, not an OS-level application lock.

## Not controlled

Liquid Glass, custom widget shapes, third-party plug-in skins, fixed built-in skins, native/legacy dialog backgrounds, operating-system themes, and undocumented internal/derived colors. Some dialogs can remain light gray. Score/drawing paper and ink are not inverted; score/symbol palettes use darker color variants for readability on white paper.

This is a community-designed theme, not an Apple/Steinberg preset or an exact reproduction of official color tokens. Product names identify the inspiration and target application only.
