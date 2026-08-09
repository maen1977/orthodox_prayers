#!/usr/bin/env python3
"""Static Android resource-linkage checks that do not require an Android SDK."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app/src/main/res"
JAVA = ROOT / "app/src/main/java"
MANIFEST = ROOT / "app/src/main/AndroidManifest.xml"
BUILD = ROOT / "app/build.gradle.kts"
RESOURCE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
STYLE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.]*$")
JAVA_REF = re.compile(r"(?<!android\.)\bR\.(string|drawable|layout|raw|id)\.([A-Za-z0-9_]+)")
ID_DECL = re.compile(r"@\+id/([A-Za-z0-9_]+)")
BANNED_DECORATIVE_GLYPHS = set("⛪⚕☀★☆✎✅⛔")


def fail(message: str) -> None:
    raise SystemExit("ANDROID_RESOURCE_VALIDATION_FAILED\n" + message)


def direct_values_resources(directory: Path) -> dict[tuple[str, str], Path]:
    found: dict[tuple[str, str], Path] = {}
    for path in sorted(directory.glob("*.xml")):
        root = ET.parse(path).getroot()
        for child in root:
            resource_type = child.tag.split("}")[-1]
            name = str(child.attrib.get("name") or "").strip()
            if not name:
                continue
            valid_name = STYLE_NAME.fullmatch(name) if resource_type == "style" else RESOURCE_NAME.fullmatch(name)
            if not valid_name:
                fail(f"invalid {resource_type} resource name {name!r} in {path.relative_to(ROOT)}")
            key = (resource_type, name)
            if key in found:
                fail(
                    f"duplicate {resource_type}/{name} in {found[key].relative_to(ROOT)} "
                    f"and {path.relative_to(ROOT)}"
                )
            found[key] = path
    return found


def main() -> None:
    if not RES.is_dir() or not JAVA.is_dir() or not MANIFEST.is_file():
        fail("Android source tree is incomplete")

    xml_files = sorted(RES.rglob("*.xml")) + [MANIFEST]
    for path in xml_files:
        raw_xml = path.read_text(encoding="utf-8")
        # Android's resource compiler treats apostrophes inside <string> values
        # with its own escaping rules after XML entity decoding. An XML &apos;
        # can therefore become an unescaped ASCII apostrophe and fail AAPT2
        # with the misleading "Invalid unicode escape sequence" error.
        if path.parent.name.startswith("values") and "&apos;" in raw_xml:
            fail(
                "Android values resources must not use &apos; inside strings; "
                f"use a typographic apostrophe or Android \\' escaping: {path.relative_to(ROOT)}"
            )
        try:
            ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            fail(f"malformed XML in {path.relative_to(ROOT)}: {exc}")

    per_qualifier: dict[str, dict[tuple[str, str], Path]] = {}
    for directory in sorted(path for path in RES.iterdir() if path.is_dir() and path.name.startswith("values")):
        per_qualifier[directory.name] = direct_values_resources(directory)

    default_values = per_qualifier.get("values", {})
    strings = {name for (kind, name) in default_values if kind == "string"}
    if len(strings) < 340:
        fail(f"default string catalog is unexpectedly small: {len(strings)}")

    file_resources: dict[str, set[str]] = defaultdict(set)
    for directory in RES.iterdir():
        if not directory.is_dir():
            continue
        base_type = directory.name.split("-", 1)[0]
        if base_type not in {"drawable", "layout", "raw", "mipmap", "xml"}:
            continue
        for path in directory.iterdir():
            if path.is_file():
                file_resources[base_type].add(path.stem)

    declared_ids: set[str] = set()
    for path in RES.rglob("*.xml"):
        declared_ids.update(ID_DECL.findall(path.read_text(encoding="utf-8")))

    java_text = "\n".join(path.read_text(encoding="utf-8") for path in JAVA.rglob("*.java"))
    missing: list[str] = []
    for kind, name in JAVA_REF.findall(java_text):
        exists = (
            name in strings if kind == "string" else
            name in declared_ids if kind == "id" else
            name in file_resources.get(kind, set())
        )
        if not exists:
            missing.append(f"R.{kind}.{name}")
    if missing:
        fail("missing Java-linked resources: " + ", ".join(sorted(set(missing))[:20]))

    # The app starts at API 26, so a v26 adaptive icon is a valid base launcher.
    build_text = BUILD.read_text(encoding="utf-8")
    if not re.search(r"minSdk\s*=\s*26\b", build_text):
        fail("launcher validation assumes the declared minSdk is 26")
    adaptive = RES / "mipmap-anydpi-v26/ic_launcher.xml"
    monochrome = RES / "mipmap-anydpi-v33/ic_launcher.xml"
    if not adaptive.is_file() or not monochrome.is_file():
        fail("adaptive launcher icon or Android 13 monochrome icon is missing")
    mono_text = monochrome.read_text(encoding="utf-8")
    if "<monochrome" not in mono_text or "@drawable/ic_launcher_monochrome" not in mono_text:
        fail("Android 13 launcher icon does not provide a monochrome layer")

    manifest_text = MANIFEST.read_text(encoding="utf-8")
    for marker in ('android:icon="@mipmap/ic_launcher"', 'android:roundIcon="@mipmap/ic_launcher"'):
        if marker not in manifest_text:
            fail(f"manifest launcher marker missing: {marker}")

    android_ns = "{http://schemas.android.com/apk/res/android}"
    manifest_root = ET.parse(MANIFEST).getroot()
    application = manifest_root.find("application")
    if application is None:
        fail("manifest application element is missing")
    exported_components: set[str] = set()
    private_components: set[str] = set()
    for tag in ("activity", "receiver", "service", "provider"):
        for component in application.findall(tag):
            name = component.attrib.get(android_ns + "name", "")
            exported = component.attrib.get(android_ns + "exported")
            if exported == "true":
                exported_components.add(name)
            elif exported == "false":
                private_components.add(name)
    expected_exported = {".MainActivity", ".widget.DailyAgendaWidget"}
    if exported_components != expected_exported:
        fail(
            "unexpected exported Android components: "
            f"expected={sorted(expected_exported)} actual={sorted(exported_components)}"
        )
    required_private = {".update.MidnightUpdateReceiver", ".update.ScheduleRestoreReceiver"}
    if not required_private.issubset(private_components):
        fail("update receivers must remain non-exported")

    # Check only the UI Java and app-owned UI catalogs. Liturgical data may
    # legitimately contain traditional symbols, but control labels should not
    # regress to platform-dependent emoji artwork.
    ui_text = java_text + "\n" + "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            RES / "values/ui_strings.xml",
            RES / "values-en/ui_strings.xml",
            RES / "values-el/ui_strings.xml",
        )
    )
    found_banned = sorted(BANNED_DECORATIVE_GLYPHS.intersection(ui_text))
    if found_banned:
        fail("decorative emoji-style glyphs remain in UI controls: " + " ".join(found_banned))

    print(
        "ANDROID_RESOURCES_OK "
        f"xml={len(xml_files)} strings={len(strings)} "
        f"drawables={len(file_resources['drawable'])} ids={len(declared_ids)} "
        "adaptive_icon=true monochrome_icon=true exported_components=2 decorative_emoji=0"
    )


if __name__ == "__main__":
    main()
