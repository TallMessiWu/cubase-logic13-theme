"""Synthetic fixtures only: no personal Cubase preferences or projects."""
import copy
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cubase_theme as c

THEME = json.loads(c.THEME_PATH.read_text(encoding="utf-8"))


def integer(parent, name, value):
    return ET.SubElement(parent, "int", name=name, value=str(value))


def string(parent, name, value):
    return ET.SubElement(parent, "string", name=name, value=value, wide="true")


def palette(parent, tag, name, count):
    attrs = {"name": name}
    if tag == "obj":
        attrs.update({"class": "UColorSet", "ID": "987"})
    root = ET.SubElement(parent, tag, attrs)
    string(root, "SetName", name)
    for list_name in ["Set", "DefSet"]:
        lst = ET.SubElement(root, "list", name=list_name, type="list")
        for i in range(count):
            item = ET.SubElement(lst, "item")
            string(item, "Name", f"Factory {i + 1}")
            integer(item, "Color", c.argb("E53636") + i)
    return root


def fixture():
    root = ET.Element("UserPreferences")
    entries = ET.SubElement(root, "list", name="Entries", type="list")

    def group(name, values):
        item = ET.SubElement(entries, "item")
        string(item, "Group", name)
        member = ET.SubElement(item, "member", name="Values")
        for key, value in values.items():
            integer(member, key, value)
        return member

    group("SurfaceSchemeColorSetPreferences", {"1000": c.signed(c.argb("25282B")), "11000": c.signed(c.argb("FFCC66")), "Type": 1400})
    for name, values in THEME["group_colors"].items():
        group(name, {**{key: c.signed(c.argb("424447")) for key in values}, "Type": 1400, "new-version-extra": 12345})
    group("TrackDefaultColorPreferences", {**{key: c.signed(c.argb("8EA0B2")) for key in THEME["track_type_colors"]}, "Type": 1400})
    for name, values in THEME["scalar_groups"].items():
        group(name, {key: 0 for key in values})
    for name in THEME["cursor_colors"]:
        group(name, {"Line Color": c.signed(0x80FFFFFF), "LineWidth": 1})
    group("NotThemePrefs", {"PrivateDeviceSetting": 17})
    meter = group("MeterAppearance", {})
    array = ET.SubElement(meter, "obj", {"class": "CmArray", "name": "MeterBreakPointsSets", "ID": "100"})
    curves = ET.SubElement(array, "list", name="obj", type="obj")
    original_colors = list(THEME["meter"]["factory_to_theme"])
    for i, mode in enumerate(THEME["meter"]["ppm_modes"]):
        curve = ET.SubElement(curves, "obj", {"class": "CBreakPointSet", "ID": str(200+i)})
        points = ET.SubElement(curve, "list", name="Points", type="obj")
        for j in range(2):
            point = ET.SubElement(points, "obj", {"class": "CDualColorBreakPoint", "ID": str(300+i*2+j)})
            ET.SubElement(point, "float", name="Position", value=str(j))
            integer(point, "Flags", 0)
            for color_name in ["Color", "Color2"]:
                integer(point, color_name, int(original_colors[(i+j) % len(original_colors)], 16))
        integer(curve, "PpmMode", mode)
    auto = ET.SubElement(root, "member", name="AutoSavers")
    for name, colors in THEME["editor_palettes"].items():
        p = palette(auto, "member", name, len(colors))
        integer(p, "FixedSize", 1)
    defaults = ET.Element("Defaults")
    container = ET.SubElement(defaults, "member", name="FixtureColors")
    palette(container, "obj", "Event Colors", 16)
    for name in THEME["auxiliary_palettes"]:
        palette(container, "obj", name, 16)
    result = {}
    for name, tree in zip(c.FILES, [root, defaults]):
        ET.indent(tree, space="   ")
        result[name] = '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(tree, encoding="unicode", short_empty_elements=True) + '\n'
    # Deliberately keep a named entity, comments containing XML-looking text,
    # literal '>' in an attribute and mixed newlines: the tool must not rewrite them.
    marker = '<!-- keep <nested>not a node</nested> -->\n<string name="Untouched" value="keep &auml; &amp; x > 5"/>\n'
    result[c.FILES[0]] = result[c.FILES[0]].replace('</UserPreferences>', marker + '</UserPreferences>')
    return result


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.before = fixture()
        self.after, self.ops = c.plan_apply(self.before, THEME)

    def test_apply_and_idempotency(self):
        self.assertGreater(len(self.ops), 20)
        again, ops = c.plan_apply(self.after, THEME)
        self.assertEqual(again, self.after)
        self.assertEqual(ops, [])
        root = c.validate_xml(self.after[c.FILES[1]])
        palette_node = root.find('.//obj[@name="Event Colors"]')
        self.assertEqual(len(palette_node.find('list[@name="Set"]')), 48)

    def test_unknown_settings_entities_and_comments_unchanged(self):
        self.assertIn('value="keep &auml; &amp; x > 5"', self.after[c.FILES[0]])
        self.assertIn('<!-- keep <nested>not a node</nested> -->', self.after[c.FILES[0]])
        self.assertIn('name="new-version-extra" value="12345"', self.after[c.FILES[0]])
        self.assertIn('name="PrivateDeviceSetting" value="17"', self.after[c.FILES[0]])
        self.assertIn('name="11000" value="-13210"', self.after[c.FILES[0]])

    def test_meter_structure_and_cursor_alpha_preserved(self):
        sel = {"kind": "group", "name": "MeterAppearance"}
        self.assertEqual(c.meter_structure(c.Document(self.before[c.FILES[0]]).select(sel)), c.meter_structure(c.Document(self.after[c.FILES[0]]).select(sel)))
        doc = c.Document(self.after[c.FILES[0]])
        for name in THEME["cursor_colors"]:
            self.assertEqual(c.u32(doc.integer(name, "Line Color").attrs["value"]) >> 24, 0x80)

    def test_restore_roundtrip_and_idempotency(self):
        restored, inverse = c.plan_restore(self.after, self.ops)
        for name in c.FILES:
            self.assertEqual(c.canonical(restored[name]), c.canonical(self.before[name]))
        _, no_ops = c.plan_restore(restored, self.ops)
        self.assertEqual(no_ops, [])
        redone, _ = c.plan_restore(restored, inverse)
        for name in c.FILES:
            self.assertEqual(c.canonical(redone[name]), c.canonical(self.after[name]))

    def test_restore_survives_runtime_ids_and_unrelated_edits(self):
        edited = {name: re.sub(r'ID="\d+"', 'ID="7777777"', text) for name, text in self.after.items()}
        edited[c.FILES[0]] = edited[c.FILES[0]].replace('name="PrivateDeviceSetting" value="17"', 'name="PrivateDeviceSetting" value="99"')
        restored, _ = c.plan_restore(edited, self.ops)
        self.assertIn('name="PrivateDeviceSetting" value="99"', restored[c.FILES[0]])
        self.assertIn('ID="7777777"', restored[c.FILES[1]])
        expected = self.before[c.FILES[0]].replace('name="PrivateDeviceSetting" value="17"', 'name="PrivateDeviceSetting" value="99"')
        self.assertEqual(c.canonical(restored[c.FILES[0]]), c.canonical(expected))

    def test_restore_rejects_user_color_conflict(self):
        changed = dict(self.after)
        changed[c.FILES[0]] = changed[c.FILES[0]].replace('name="Wave Brightness" value="65"', 'name="Wave Brightness" value="66"')
        with self.assertRaisesRegex(c.ThemeError, "Restore conflict"):
            c.plan_restore(changed, self.ops)

    def test_restore_rejects_meter_threshold_change(self):
        changed = dict(self.after)
        changed[c.FILES[0]] = changed[c.FILES[0]].replace('name="Position" value="0"', 'name="Position" value="0.1"', 1)
        with self.assertRaisesRegex(c.ThemeError, "thresholds changed"):
            c.plan_restore(changed, self.ops)

    def test_apply_rejects_unknown_meter_color(self):
        changed = dict(self.before)
        changed[c.FILES[0]] = changed[c.FILES[0]].replace('name="Color" value="4279883774"', 'name="Color" value="4278256131"', 1)
        with self.assertRaisesRegex(c.ThemeError, "Custom meter color"):
            c.plan_apply(changed, THEME)

    def test_apply_rejects_missing_required_key(self):
        changed = dict(self.before)
        changed[c.FILES[0]] = re.sub(r'<int name="Wave Brightness"[^>]*/>', '', changed[c.FILES[0]])
        with self.assertRaisesRegex(c.ThemeError, "Missing setting"):
            c.plan_apply(changed, THEME)

    def test_rejects_duplicate_keys(self):
        changed = dict(self.before)
        tag = re.search(r'<int name="1000"[^>]*/>', changed[c.FILES[0]]).group()
        changed[c.FILES[0]] = changed[c.FILES[0]].replace(tag, tag+tag)
        with self.assertRaisesRegex(c.ThemeError, "Duplicate setting"):
            c.plan_apply(changed, THEME)

    def test_unsigned_color_values_are_idempotent(self):
        changed = dict(self.after)
        changed[c.FILES[0]] = re.sub(r'value="(-\d+)"', lambda m: 'value="'+str(c.u32(m.group(1)))+'"', changed[c.FILES[0]])
        result, ops = c.plan_apply(changed, THEME)
        self.assertEqual(ops, [])
        self.assertEqual(result, changed)

    def test_crlf_input_is_supported(self):
        source = {name: text.replace('\n', '\r\n') for name, text in self.before.items()}
        result, _ = c.plan_apply(source, THEME)
        self.assertNotIn('\n', result[c.FILES[0]].replace('\r\n', ''))

    def test_rejects_dtd(self):
        with self.assertRaisesRegex(c.ThemeError, "DTD"):
            c.validate_xml('<!DOCTYPE x SYSTEM "file:///not-read"><x/>')

    def setup_directory(self, root):
        prefs = root / 'Cubase 14_64'
        prefs.mkdir()
        for name, text in self.before.items():
            (prefs/name).write_bytes(text.encode('utf-8'))
        return prefs

    @patch('cubase_theme.cubase_running', return_value=False)
    def test_transaction_and_journal_restore(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            backup = c.commit(prefs, self.before, self.after, self.ops, root/'backups', THEME['id'], 'apply')
            self.assertEqual(c.read_settings(prefs), self.after)
            manifest = json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
            restored, inverse = c.plan_restore(c.read_settings(prefs), manifest['operations'])
            c.commit(prefs, self.after, restored, inverse, root/'backups', THEME['id'], 'restore')
            for name in c.FILES:
                self.assertEqual(c.canonical(c.read_settings(prefs)[name]), c.canonical(self.before[name]))

    @patch('cubase_theme.cubase_running', return_value=True)
    def test_running_process_blocks_writes(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            with self.assertRaisesRegex(c.ThemeError, 'quit Cubase'):
                c.commit(prefs, self.before, self.after, self.ops, root/'backups', THEME['id'], 'apply')
            self.assertFalse((root/'backups').exists())
            self.assertEqual(c.read_settings(prefs), self.before)

    @patch('cubase_theme.cubase_running', return_value=False)
    def test_atomic_failure_rolls_back_first_file(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            real_replace = c.atomic_replace
            calls = []
            def failing_replace(path, text):
                calls.append(path.name)
                if len(calls) == 2:
                    raise OSError('simulated write failure')
                return real_replace(path, text)
            with patch('cubase_theme.atomic_replace', side_effect=failing_replace):
                with self.assertRaisesRegex(OSError, 'simulated'):
                    c.commit(prefs, self.before, self.after, self.ops, root/'backups', THEME['id'], 'apply')
            self.assertEqual(c.read_settings(prefs), self.before)
            self.assertEqual(len(list((root/'backups').glob('*/manifest.json'))), 1)

    @patch('cubase_theme.cubase_running', return_value=False)
    def test_concurrent_change_and_unsafe_backup_path_rejected(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            with self.assertRaisesRegex(c.ThemeError, 'outside'):
                c.commit(prefs, self.before, self.after, self.ops, prefs/'backups', THEME['id'], 'apply')
            with self.assertRaisesRegex(c.ThemeError, 'public source checkout'):
                c.commit(prefs, self.before, self.after, self.ops, c.ROOT/'private-backup', THEME['id'], 'apply')
            (prefs/c.FILES[0]).write_bytes(self.before[c.FILES[0]].replace('value="17"', 'value="19"').encode())
            with self.assertRaisesRegex(c.ThemeError, 'changed during preflight'):
                c.commit(prefs, self.before, self.after, self.ops, root/'backups', THEME['id'], 'apply')

    @patch('cubase_theme.cubase_running', return_value=False)
    def test_cli_restore_rejects_corrupt_backup(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            backup = c.commit(prefs, self.before, self.after, self.ops, root/'backups', THEME['id'], 'apply')
            (backup/c.FILES[0]).write_text('corrupted', encoding='utf-8')
            with self.assertRaisesRegex(c.ThemeError, 'Backup integrity'):
                c.main(['restore', '--backup', str(backup), '--prefs-dir', str(prefs), '--allow-untested', '--dry-run'])
            self.assertEqual(c.read_settings(prefs), self.after)

    def test_cli_dry_run_creates_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prefs = self.setup_directory(root)
            before_files = set(root.rglob('*'))
            with patch('sys.stdout', new_callable=io.StringIO):
                code = c.main(['apply', '--dry-run', '--prefs-dir', str(prefs), '--allow-untested', '--backup-root', str(root/'backups')])
            self.assertEqual(code, 0)
            self.assertEqual(set(root.rglob('*')), before_files)
            self.assertEqual(c.read_settings(prefs), self.before)


if __name__ == '__main__':
    unittest.main()
