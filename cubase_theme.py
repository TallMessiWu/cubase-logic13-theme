#!/usr/bin/env python3
"""Offline, scoped Cubase color migration. Python 3.10+, standard library only.

Never serializes an entire settings XML tree. Known fields are replaced by span;
unknown settings and XML entities are preserved. No .cpr or audio is modified.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import html.entities
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

FILES = ("UserPreferences.xml", "Defaults.xml")
ROOT = Path(__file__).resolve().parent
THEME_PATH = ROOT / "themes" / "logic13-graphite48.json"
TAG = re.compile(r'''<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<(?:[^>"']|"[^"]*"|'[^']*')*>''')
ATTR = re.compile(r'''([\w:.-]+)\s*=\s*(["'])(.*?)\2''', re.S)


class ThemeError(Exception):
    """An unsupported schema, conflict, or unsafe operation; no guessing."""


def require(condition, message):
    if not condition:
        raise ThemeError(message)


def u32(value):
    return int(value) & 0xFFFFFFFF


def signed(value):
    value = u32(value)
    return str(value if value < 0x80000000 else value - 0x100000000)


def argb(color):
    require(bool(re.fullmatch(r"[0-9A-Fa-f]{6}", color)), f"Invalid RGB: {color}")
    return int("FF" + color, 16)


def validate_xml(text):
    # Cubase writes some HTML named entities without a DTD. Expand in memory
    # only for validation; never rewrite those strings in the original file.
    require(not re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I), "DTD/entity declarations are not supported")

    def entity(match):
        name = match.group(1)
        if name in {"amp", "lt", "gt", "quot", "apos"}:
            return match.group()
        require(name in html.entities.name2codepoint, f"Unknown entity: &{name};")
        return f"&#{html.entities.name2codepoint[name]};"

    try:
        return ET.fromstring(re.sub(r"&([A-Za-z][A-Za-z0-9]+);", entity, text))
    except ET.ParseError as exc:
        raise ThemeError(f"Invalid settings XML: {exc}") from exc


@dataclass
class Node:
    tag: str
    attrs: dict
    start: int
    open_end: int
    end_start: int = 0
    end: int = 0
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()


def only(items, description):
    items = list(items)
    require(len(items) == 1, f"Expected one {description}; found {len(items)}")
    return items[0]


class Document:
    def __init__(self, text):
        self.text = text
        validate_xml(text)

    def nodes(self):
        stack, roots = [], []
        for match in TAG.finditer(self.text):
            raw = match.group()
            if raw.startswith(("<?", "<!")):
                continue
            if raw.startswith("</"):
                tag = raw[2:-1].strip()
                require(stack and stack[-1].tag == tag, "Unsupported XML nesting")
                node = stack.pop()
                node.end_start, node.end = match.start(), match.end()
                continue
            start = re.match(r"<([\w:.-]+)", raw)
            require(start is not None, "Unsupported XML tag")
            attrs = {m.group(1): html.unescape(m.group(3)) for m in ATTR.finditer(raw)}
            node = Node(start.group(1), attrs, match.start(), match.end())
            (stack[-1].children if stack else roots).append(node)
            if raw.rstrip().endswith("/>"):
                node.end_start, node.end = match.start(), match.end()
            else:
                stack.append(node)
        require(not stack, "Unclosed XML tag")
        return [node for root in roots for node in root.walk()]

    def select(self, selector):
        nodes = self.nodes()
        if selector["kind"] == "group":
            name = selector["name"]
            return only((n for n in nodes if n.tag == "item" and any(
                c.tag == "string" and c.attrs.get("name") == "Group" and c.attrs.get("value") == name
                for c in n.children)), f"preference group {name}")
        tag = selector["kind"]
        return only((n for n in nodes if n.tag == tag and n.attrs.get("name") == selector["name"]
                     and (tag != "obj" or n.attrs.get("class") == "UColorSet")), str(selector))

    def raw(self, node):
        return self.text[node.start:node.end]

    def replace(self, replacements):
        ordered = sorted(replacements, key=lambda item: item[0])
        for left, right in zip(ordered, ordered[1:]):
            require(left[1] <= right[0], "Overlapping edits")
        for start, end, text in reversed(ordered):
            self.text = self.text[:start] + text + self.text[end:]

    def value_replacement(self, node, value):
        raw = self.raw(node)
        match = only((m for m in ATTR.finditer(raw) if m.group(1) == "value"), "value attribute")
        return node.start + match.start(3), node.start + match.end(3), str(value)

    def integer(self, group, key):
        node = self.select({"kind": "group", "name": group})
        return only((n for n in node.walk() if n.tag == "int" and n.attrs.get("name") == key), f"{group}/{key}")


def canonical(text):
    def encode(node):
        attrs = dict(node.attrib)
        attrs.pop("ID", None)  # Cubase assigns new runtime object IDs on exit.
        if node.tag == "int" and attrs.get("name") in {"Color", "Color2"}:
            attrs["value"] = str(u32(attrs["value"]))
        return [node.tag, sorted([list(x) for x in attrs.items()]), [encode(c) for c in node]]
    return encode(validate_xml(text))


def color_nodes(node):
    return [n for n in node.walk() if n.tag == "int" and n.attrs.get("name") in {"Color", "Color2"}]


def meter_structure(node):
    result = []
    for curve in node.walk():
        if curve.attrs.get("class") != "CBreakPointSet":
            continue
        mode = only((n for n in curve.children if n.attrs.get("name") == "PpmMode"), "meter mode")
        points = []
        for point in curve.walk():
            if point.attrs.get("class") == "CDualColorBreakPoint":
                pos = only((n for n in point.children if n.attrs.get("name") == "Position"), "meter position")
                flags = only((n for n in point.children if n.attrs.get("name") == "Flags"), "meter flags")
                points.append([float(pos.attrs["value"]), int(flags.attrs["value"])])
        result.append([int(mode.attrs["value"]), points])
    return result


class Editor:
    def __init__(self, texts):
        self.docs = {name: Document(texts[name]) for name in FILES}
        self.operations = []

    def values(self, group, desired, allow_add=()):
        file = FILES[0]
        doc = self.docs[file]
        root = doc.select({"kind": "group", "name": group})
        values = only((n for n in root.children if n.tag == "member" and n.attrs.get("name") == "Values"), f"{group} values")
        edits, changes, additions = [], [], []
        for key, target in desired.items():
            matches = [n for n in root.walk() if n.tag == "int" and n.attrs.get("name") == key]
            require(len(matches) <= 1, f"Duplicate setting: {group}/{key}")
            node = matches[0] if matches else None
            before = node.attrs["value"] if node else None
            target = None if target is None else str(target)
            if before is None and target is None:
                continue
            if before is not None and target is not None and u32(before) == u32(target):
                continue
            if node is None:
                require(key in allow_add, f"Missing setting: {group}/{key}; version not supported")
                additions.append(f'<int name="{key}" value="{target}"/>')
            elif target is None:
                edits.append((node.start, node.end, ""))
            else:
                edits.append(doc.value_replacement(node, target))
            changes.append({"key": key, "before": before, "after": target})
        if additions:
            newline = "\r\n" if "\r\n" in doc.text else "\n"
            line_start = doc.text.rfind("\n", 0, values.end_start) + 1
            indent = doc.text[line_start:values.end_start]
            require(not indent.strip(), "Unsupported Values indentation")
            text = "".join(indent + "   " + tag + newline for tag in additions)
            edits.append((line_start, line_start, text))
        if edits:
            doc.replace(edits)
            self.operations.append({"kind": "values", "file": file, "group": group, "fields": changes})

    def set_list(self, file, selector, list_name, replacement):
        doc = self.docs[file]
        scope = doc.select(selector)
        node = only((n for n in scope.children if n.tag == "list" and n.attrs.get("name") == list_name), f"{selector}/{list_name}")
        before = doc.raw(node)
        if canonical(before) == canonical(replacement):
            return
        doc.replace([(node.start, node.end, replacement)])
        self.operations.append({"kind": "list", "file": file, "selector": selector, "name": list_name,
                                "before": before, "after": canonical(replacement)})

    def palette(self, file, selector, colors, names=None):
        for list_name in ("Set", "DefSet"):
            doc = self.docs[file]
            scope = doc.select(selector)
            node = only((n for n in scope.children if n.tag == "list" and n.attrs.get("name") == list_name), f"{selector}/{list_name}")
            current = color_nodes(node)
            require(current, f"Empty palette: {selector}/{list_name}")
            if names is None:
                require(len(current) == len(colors), f"Unexpected palette length: {selector}/{list_name}")
                text = doc.raw(node)
                for field_node, color in reversed(list(zip(current, colors))):
                    a, b, value = doc.value_replacement(field_node, argb(color))
                    text = text[:a-node.start] + value + text[b-node.start:]
            else:
                require(len(names) == len(colors), "Palette name/color mismatch")
                # Avoid deleting unknown per-item data in a custom project palette.
                for item in node.children:
                    require(item.tag == "item" and len(item.children) == 2 and
                            sorted((c.tag, c.attrs.get("name")) for c in item.children) ==
                            [("int", "Color"), ("string", "Name")], "Unsupported event palette item layout")
                newline = "\r\n" if "\r\n" in doc.text else "\n"
                indent = doc.text[doc.text.rfind("\n", 0, node.start)+1:node.start]
                require(not indent.strip(), "Unsupported palette indentation")
                lines = [f'<list name="{list_name}" type="list">']
                for name, color in zip(names, colors):
                    lines += [indent + '   <item>',
                              indent + f'      <string name="Name" value="{html.escape(name, quote=True)}" wide="true"/>',
                              indent + f'      <int name="Color" value="{argb(color)}"/>',
                              indent + '   </item>']
                lines.append(indent + '</list>')
                text = newline.join(lines)
            self.set_list(file, selector, list_name, text)

    def meter(self, desired):
        doc = self.docs[FILES[0]]
        node = doc.select({"kind": "group", "name": "MeterAppearance"})
        fields = color_nodes(node)
        before = [u32(n.attrs["value"]) for n in fields]
        require(len(before) == len(desired), "Meter color count changed")
        if before == desired:
            return
        structure = meter_structure(node)
        doc.replace([doc.value_replacement(n, value) for n, value in zip(fields, desired)])
        self.operations.append({"kind": "meter", "file": FILES[0], "before": before,
                                "after": desired, "structure": structure})

    def result(self):
        texts = {name: doc.text for name, doc in self.docs.items()}
        for text in texts.values():
            validate_xml(text)
        return texts, self.operations


def plan_apply(texts, theme):
    require(theme.get("schema_version") == 1, "Unsupported theme schema")
    colors = theme["track_colors"]
    require(len(colors) == 48 and len({c["color"] for c in colors}) == 48, "Expected 48 unique track colors")
    edit = Editor(texts)
    edit.values("SurfaceSchemeColorSetPreferences", {k: signed(argb(v["color"])) for k, v in theme["surface"].items()}, allow_add=theme["surface"])
    for group, values in theme["group_colors"].items():
        edit.values(group, {k: signed(argb(color)) for k, color in values.items()})
    edit.values("TrackDefaultColorPreferences", {k: signed(argb(v["color"])) for k, v in theme["track_type_colors"].items()})
    for group, values in theme["scalar_groups"].items():
        edit.values(group, values)
    for group, color in theme["cursor_colors"].items():
        current = edit.docs[FILES[0]].integer(group, "Line Color")
        value = (u32(current.attrs["value"]) & 0xFF000000) | int(color, 16)
        edit.values(group, {"Line Color": signed(value)})
    meter = edit.docs[FILES[0]].select({"kind": "group", "name": "MeterAppearance"})
    modes = [curve[0] for curve in meter_structure(meter)]
    require(sorted(modes) == sorted(theme["meter"]["ppm_modes"]), "Unrecognized meter scales; manual review required")
    mapping = {int(a, 16): int(b, 16) for a, b in theme["meter"]["factory_to_theme"].items()}
    allowed = set(mapping.values())
    new_colors = []
    for node in color_nodes(meter):
        old = u32(node.attrs["value"])
        require(old in mapping or old in allowed, f"Custom meter color {old:08X} cannot be mapped safely; manual review required")
        new_colors.append(mapping.get(old, old))
    edit.meter(new_colors)
    for name, values in theme["editor_palettes"].items():
        edit.palette(FILES[0], {"kind": "member", "name": name}, values)
    edit.palette(FILES[1], {"kind": "obj", "name": "Event Colors"}, [c["color"] for c in colors], [c["name"] for c in colors])
    for name, values in theme["auxiliary_palettes"].items():
        edit.palette(FILES[1], {"kind": "obj", "name": name}, values)
    return edit.result()


def plan_restore(texts, operations):
    edit = Editor(texts)
    for op in reversed(operations):
        require(op["file"] in FILES, "Invalid journal file")
        doc = edit.docs[op["file"]]
        if op["kind"] == "values":
            require(op["file"] == FILES[0], "Invalid values journal")
            scope = doc.select({"kind": "group", "name": op["group"]})
            desired, additions = {}, []
            for field_data in op["fields"]:
                key = field_data["key"]
                found = [n for n in scope.walk() if n.tag == "int" and n.attrs.get("name") == key]
                require(len(found) <= 1, "Duplicate setting during restore")
                current = found[0].attrs["value"] if found else None
                equal = lambda a, b: a is b if a is None or b is None else u32(a) == u32(b)
                if equal(current, field_data["before"]):
                    continue
                require(equal(current, field_data["after"]), f'Restore conflict: {op["group"]}/{key} was changed after application')
                desired[key] = field_data["before"]
                if not found:
                    additions.append(key)
            edit.values(op["group"], desired, additions)
        elif op["kind"] == "list":
            scope = doc.select(op["selector"])
            node = only((n for n in scope.children if n.tag == "list" and n.attrs.get("name") == op["name"]), "restore palette list")
            current = canonical(doc.raw(node))
            if current == canonical(op["before"]):
                continue
            require(current == op["after"], f'Restore conflict: palette {op["selector"]["name"]} changed after application')
            edit.set_list(op["file"], op["selector"], op["name"], op["before"])
        elif op["kind"] == "meter":
            require(op["file"] == FILES[0], "Invalid meter journal")
            scope = doc.select({"kind": "group", "name": "MeterAppearance"})
            require(meter_structure(scope) == op["structure"], "Meter thresholds changed; restore refused")
            current = [u32(n.attrs["value"]) for n in color_nodes(scope)]
            if current == op["before"]:
                continue
            require(current == op["after"], "Meter colors changed after application; restore refused")
            edit.meter(op["before"])
        else:
            raise ThemeError(f'Unknown journal operation: {op["kind"]}')
    return edit.result()


def cubase_running():
    if sys.platform == "win32":
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, check=True)
        text = result.stdout.decode(errors="replace")
        return any(row and re.fullmatch(r"Cubase.*\.exe", row[0], re.I) for row in csv.reader(io.StringIO(text)))
    result = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, check=True)
    return any(re.fullmatch(r"Cubase(?:\s*\d+(?:\.\d+)*)?", Path(line.strip()).name, re.I) for line in result.stdout.splitlines())


def ensure_closed():
    require(not cubase_running(), "Save your projects and completely quit Cubase (including the Hub) before writing settings")


def read_settings(directory):
    texts = {}
    for name in FILES:
        path = directory / name
        require(path.is_file() and not path.is_symlink(), f"Missing or symlinked settings file: {path}")
        require(path.stat().st_size <= 50_000_000, f"Unexpected settings size: {path}")
        texts[name] = path.read_bytes().decode("utf-8")
        validate_xml(texts[name])
    return texts


def discover():
    roots = []
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "Steinberg")
    elif sys.platform == "darwin":
        roots.append(Path.home() / "Library" / "Preferences")
    candidates = sorted({p for root in roots if root.is_dir() for p in root.glob("Cubase*")
                         if p.is_dir() and all((p / name).is_file() for name in FILES)})
    require(len(candidates) == 1, "Specify --prefs-dir explicitly; found " + str(len(candidates)) + " candidates: " + ", ".join(map(str, candidates)))
    return candidates[0].resolve()


def check_compatibility(directory, allow_untested):
    tested = sys.platform == "win32" and directory.name == "Cubase 14_64"
    require(tested or allow_untested, "Only Windows Cubase 14_64 is tested. Inspect first; other platforms/versions require explicit --prefs-dir and --allow-untested")
    return tested


def default_backup_root():
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "CubaseLogicTheme" / "backups"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CubaseLogicTheme" / "backups"
    return Path.home() / ".local" / "state" / "cubase-logic13-theme" / "backups"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_replace(path, text):
    fd, temporary = tempfile.mkstemp(prefix=".cubase-theme-", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(text.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        shutil.copymode(path, temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def commit(directory, before, after, operations, backup_root, theme_id, action):
    ensure_closed()
    if not operations:
        return None
    require(read_settings(directory) == before, "Settings changed during preflight; no files were written")
    backup_root = backup_root.expanduser().resolve()
    require(not backup_root.is_relative_to(directory.resolve()), "Backups must be outside the active preferences directory")
    require(not backup_root.is_relative_to(ROOT.resolve()), "Backups must stay outside this public source checkout")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(mode=0o700)
    for name in FILES:
        (backup / name).write_bytes(before[name].encode("utf-8"))
    manifest = {"schema_version": 1, "theme": theme_id, "action": action, "prefs_dir": str(directory.resolve()),
                "before_sha256": {n: digest(before[n]) for n in FILES},
                "after_sha256": {n: digest(after[n]) for n in FILES}, "operations": operations}
    (backup / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ensure_closed()
    require(read_settings(directory) == before, "Settings changed before commit; backup kept, no files written")
    committed = []
    try:
        for name in FILES:
            if before[name] != after[name]:
                atomic_replace(directory / name, after[name])
                committed.append(name)
        require(read_settings(directory) == after, "Post-write verification failed")
    except Exception:
        for name in reversed(committed):
            atomic_replace(directory / name, before[name])
        raise
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "apply", "verify", "restore"))
    parser.add_argument("--prefs-dir", type=Path)
    parser.add_argument("--theme", type=Path, default=THEME_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-untested", action="store_true")
    parser.add_argument("--backup-root", type=Path)
    parser.add_argument("--backup", type=Path, help="A backup directory created by this tool (restore only)")
    args = parser.parse_args(argv)
    require(not args.allow_untested or args.prefs_dir is not None, "--allow-untested requires an explicit --prefs-dir")
    manifest = None
    if args.command == "restore":
        require(args.backup is not None, "restore requires --backup")
        backup = args.backup.expanduser().resolve()
        manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
        require(manifest.get("schema_version") == 1, "Unsupported backup format")
        for name in FILES:
            original = (backup / name).read_bytes().decode("utf-8")
            require(digest(original) == manifest["before_sha256"][name], "Backup integrity check failed: " + name)
        directory = (args.prefs_dir or Path(manifest["prefs_dir"])).expanduser().resolve()
    else:
        directory = args.prefs_dir.expanduser().resolve() if args.prefs_dir else discover()
    before = read_settings(directory)
    print("Preferences:", directory)
    if args.command == "inspect":
        for name, text in before.items():
            print(f"  {name}: valid XML, {len(text.encode('utf-8'))} bytes")
        print("Tested target:", sys.platform == "win32" and directory.name == "Cubase 14_64")
        print("This command made no changes. Next: apply --dry-run")
        return 0
    tested = check_compatibility(directory, args.allow_untested)
    if not tested:
        print("WARNING: experimental platform/version; schema checks are not a compatibility guarantee.")
    if args.command == "restore":
        after, operations = plan_restore(before, manifest["operations"])
        theme_id = manifest["theme"]
    else:
        theme = json.loads(args.theme.read_text(encoding="utf-8"))
        after, operations = plan_apply(before, theme)
        theme_id = theme["id"]
    print("Changed setting blocks:", len(operations))
    if args.command == "verify":
        print("PASS: all configured values match." if not operations else "MISMATCH: some values differ from the theme.")
        print("Verification reads files, not Cubase's live in-memory state.")
        return 0 if not operations else 1
    if args.dry_run:
        print("DRY RUN: no settings, backups, projects, or audio were written.")
        return 0
    backup = commit(directory, before, after, operations, args.backup_root or default_backup_root(), theme_id, args.command)
    if backup:
        print("Saved backup:", backup)
        print("Done. Reopen Cubase. Existing projects may need Project Colors Setup > Reset Color Set to Default.")
    else:
        print("Already in the requested state; nothing written.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ThemeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(2)
