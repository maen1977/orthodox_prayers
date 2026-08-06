#!/usr/bin/env python3
"""Cross-platform source gate for Safe Windows Cleaner Lite.

This does not replace a Windows/.NET build. It catches malformed XML/JSON,
missing WPF handlers, duplicate names, bracket damage, version drift, unsafe
manifest settings, and missing v2 Lite components before the Windows gate.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "SafeWindowsCleaner"
LEGACY = ROOT / "src" / "SafeWindowsCleaner.Win7"
ERRORS: list[str] = []


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def check_xml_and_json() -> tuple[int, int]:
    xml_count = 0
    json_count = 0
    xml_files = list(ROOT.rglob("*.xaml")) + list(ROOT.rglob("*.csproj")) + list(ROOT.rglob("app.manifest"))
    for path in xml_files:
        if any(part in {"bin", "obj", ".git"} for part in path.parts):
            continue
        try:
            ET.parse(path)
            xml_count += 1
        except Exception as exc:  # noqa: BLE001
            ERRORS.append(f"Malformed XML {relative(path)}: {exc}")

    for path in ROOT.rglob("*.json"):
        if any(part in {"bin", "obj", ".git"} for part in path.parts):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
            json_count += 1
        except Exception as exc:  # noqa: BLE001
            ERRORS.append(f"Malformed JSON {relative(path)}: {exc}")
    return xml_count, json_count


def check_xaml() -> tuple[int, int]:
    total_names = 0
    total_handlers = 0
    for project in (APP, LEGACY):
        xaml_path = project / "MainWindow.xaml"
        if not xaml_path.exists():
            ERRORS.append(f"Missing WPF window: {relative(xaml_path)}")
            continue
        xaml = xaml_path.read_text(encoding="utf-8")
        names = re.findall(r'\bx:Name="([A-Za-z_][A-Za-z0-9_]*)"', xaml)
        for name in sorted(set(names)):
            if names.count(name) > 1:
                ERRORS.append(f"Duplicate x:Name in {relative(xaml_path)}: {name}")

        event_attributes = re.findall(
            r'\b(Click|Loaded|Closing|SelectionChanged|Checked|Unchecked|TextChanged|MouseDoubleClick|PreviewMouseDown|PreviewKeyDown|KeyDown|Drop|DragOver)="([A-Za-z_][A-Za-z0-9_]*)"',
            xaml,
        )
        code = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in project.glob("MainWindow*.cs")
        )
        for event_name, handler in sorted(set(event_attributes)):
            if not re.search(r"\b" + re.escape(handler) + r"\s*\(", code):
                ERRORS.append(f"Missing WPF handler {handler} ({event_name}) in {relative(xaml_path)}")
        total_names += len(names)
        total_handlers += len(set(event_attributes))
    return total_names, total_handlers


def check_csharp_brackets() -> int:
    checked = 0
    pairs = {"}": "{", ")": "(", "]": "["}
    opening = set(pairs.values())
    for path in ROOT.rglob("*.cs"):
        if any(part in {"bin", "obj", ".git"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        stack: list[tuple[str, int]] = []
        index = 0
        state = "code"
        while index < len(text):
            char = text[index]
            nxt = text[index + 1] if index + 1 < len(text) else ""
            if state == "code":
                if char == "/" and nxt == "/":
                    state = "line"; index += 2; continue
                if char == "/" and nxt == "*":
                    state = "block"; index += 2; continue
                if char in {"$", "@"} and nxt in {"$", "@"} and index + 2 < len(text) and text[index + 2] == '"':
                    state = "verbatim"; index += 3; continue
                if char == "@" and nxt == '"':
                    state = "verbatim"; index += 2; continue
                if char == '"':
                    state = "string"; index += 1; continue
                if char == "'":
                    state = "char"; index += 1; continue
                if char in opening:
                    stack.append((char, index))
                elif char in pairs:
                    if not stack or stack[-1][0] != pairs[char]:
                        ERRORS.append(f"Bracket mismatch in {relative(path)} at character {index}")
                        stack.clear()
                        break
                    stack.pop()
                index += 1
            elif state == "line":
                if char == "\n": state = "code"
                index += 1
            elif state == "block":
                if char == "*" and nxt == "/": state = "code"; index += 2
                else: index += 1
            elif state == "string":
                if char == "\\": index += 2
                elif char == '"': state = "code"; index += 1
                else: index += 1
            elif state == "char":
                if char == "\\": index += 2
                elif char == "'": state = "code"; index += 1
                else: index += 1
            else:  # verbatim string
                if char == '"' and nxt == '"': index += 2
                elif char == '"': state = "code"; index += 1
                else: index += 1
        if stack:
            ERRORS.append(f"Unclosed bracket in {relative(path)}")
        checked += 1
    return checked


def check_localization_catalog() -> int:
    catalog_path = APP / "Services" / "LocalizationCatalog.cs"
    text = catalog_path.read_text(encoding="utf-8")
    entries: list[list[str]] = []
    index = 0
    while True:
        index = text.find('new("', index)
        if index < 0:
            break
        cursor = index + 4
        arguments: list[str] = []
        valid = True
        while True:
            if cursor >= len(text) or text[cursor] != '"':
                valid = False
                break
            cursor += 1
            value: list[str] = []
            while cursor < len(text):
                char = text[cursor]
                if char == "\\" and cursor + 1 < len(text):
                    value.extend((char, text[cursor + 1]))
                    cursor += 2
                    continue
                if char == '"':
                    cursor += 1
                    break
                value.append(char)
                cursor += 1
            arguments.append("".join(value))
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor < len(text) and text[cursor] == ",":
                cursor += 1
                while cursor < len(text) and text[cursor].isspace():
                    cursor += 1
                if cursor < len(text) and text[cursor] == '"':
                    continue
                valid = False
                break
            if cursor < len(text) and text[cursor] == ")":
                cursor += 1
                break
            valid = False
            break
        if valid:
            entries.append(arguments)
        index = max(index + 4, cursor)

    keys: list[str] = []
    arabic = re.compile(r"[\u0600-\u06ff]")
    for arguments in entries:
        if len(arguments) != 3:
            ERRORS.append(f"Localization entry has {len(arguments)} fields instead of 3: {arguments[:2]}")
            continue
        keys.append(arguments[0])
        if not arguments[1].strip():
            ERRORS.append(f"Empty Arabic localization value for key: {arguments[0]}")
        if not arguments[2].strip():
            ERRORS.append(f"Empty English localization value for key: {arguments[0]}")
        if arabic.search(arguments[2]):
            ERRORS.append(f"Arabic text leaked into English localization for: {arguments[0]}")
        if re.search(r"(?<![A-Za-z])(?:TB|GB|MB|KB|B)(?![A-Za-z])", arguments[1]):
            ERRORS.append(f"English size unit leaked into Arabic localization for: {arguments[0]}")
        if re.search(r"(?:ت\.ب|ج\.ب|م\.ب|ك\.ب|بايت|كيلوبايت|ميغابايت|غيغابايت|تيرابايت)", arguments[2]):
            ERRORS.append(f"Arabic size unit leaked into English localization for: {arguments[0]}")
    for key in sorted(set(keys)):
        if keys.count(key) > 1:
            ERRORS.append(f"Duplicate localization key: {key}")
    return len(entries)


def check_production_localization() -> None:
    service = (APP / "Services" / "LocalizationService.cs").read_text(encoding="utf-8")
    supported_block_match = re.search(
        r"SupportedLanguages\s*\{[^=]*=\s*\[(?P<body>.*?)\];",
        service,
        re.DOTALL,
    )
    if not supported_block_match:
        ERRORS.append("Could not inspect the production language list.")
    else:
        codes = re.findall(r'new\("([a-z]{2})"', supported_block_match.group("body"))
        if codes != ["ar", "en"]:
            ERRORS.append(
                "Only fully audited Arabic and English packs may be exposed; "
                f"found: {codes}"
            )

    main_window_xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    language_window_xaml = (APP / "LanguageSelectionWindow.xaml").read_text(encoding="utf-8")
    if not re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="DisplayName"', main_window_xaml):
        ERRORS.append("Settings language list does not use interface-localized display names.")
    if re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="NativeName"', main_window_xaml):
        ERRORS.append("Settings language list still exposes native names and can mix scripts.")
    if "{Binding DisplayName}" not in language_window_xaml:
        ERRORS.append("First-run language list does not use interface-localized display names.")
    if "Binding NativeName" in language_window_xaml or "Binding EnglishName" in language_window_xaml:
        ERRORS.append("First-run language list still displays two languages side by side.")

    virtual_memory = (APP / "Services" / "VirtualMemoryService.cs").read_text(encoding="utf-8")
    command_runner = (APP / "Services" / "CommandLineRunner.cs").read_text(encoding="utf-8")
    installer = (ROOT / "installer" / "SafeWindowsCleaner.iss").read_text(encoding="utf-8")
    for pattern, label in (
        (r"FixedPageFileSizeMb\s*=\s*16\s*\*\s*1024", "16 GB"),
        (r"MediumPageFileSizeMb\s*=\s*8\s*\*\s*1024", "8 GB"),
        (r"MinimumPageFileSizeMb\s*=\s*4\s*\*\s*1024", "4 GB"),
    ):
        if not re.search(pattern, virtual_memory):
            ERRORS.append(f"The adaptive {label} page-file preset is missing.")
    if "GetRecommendedPageFileSizeMb" not in virtual_memory or "MinimumFreeBytesAfterApply" not in virtual_memory:
        ERRORS.append("Adaptive page-file sizing or protected Windows free-space reserve is missing.")
    if "virtual-memory-backup.json" not in virtual_memory:
        ERRORS.append("The virtual-memory backup file is missing.")
    if "ApplyVirtualMemory_Click" not in main_window_xaml or "RestoreVirtualMemory_Click" not in main_window_xaml:
        ERRORS.append("The reversible virtual-memory controls are missing from the UI.")
    if "--restore-virtual-memory" not in command_runner or "--restore-virtual-memory" not in installer:
        ERRORS.append("Complete uninstall does not restore the saved page-file setting.")
    catalog = (APP / "Services" / "LocalizationCatalog.cs").read_text(encoding="utf-8")
    if "Disk space cannot be converted into real VRAM." not in catalog:
        ERRORS.append("The graphics-memory explanation must state that disk space is not real VRAM.")

    catalog_values = set()
    for match in re.finditer(
        r'new\("((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)"',
        catalog,
    ):
        catalog_values.update(match.groups())

    arabic = re.compile(r"[\u0600-\u06ff]")
    xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    visible_literals = re.findall(
        r'(?:Text|Content|Header|ToolTip|Title|AutomationProperties\.Name)="([^"]+)"',
        xaml,
    )
    for value in sorted(set(visible_literals)):
        if arabic.search(value) and value not in catalog_values:
            ERRORS.append(f"Visible XAML text lacks an exact English translation: {value}")

    for installer_path in (
        ROOT / "installer" / "SafeWindowsCleaner.iss",
        ROOT / "installer" / "SafeWindowsCleaner.x86.iss",
        ROOT / "installer" / "SafeWindowsCleaner.Win7.iss",
    ):
        installer_text = installer_path.read_text(encoding="utf-8")
        language_section = installer_text.split("[Languages]", 1)[1].split("[CustomMessages]", 1)[0]
        installer_codes = re.findall(r'Name:\s*"([a-z]{2})"', language_section)
        if installer_codes != ["en", "ar"]:
            ERRORS.append(
                f"{relative(installer_path)} must expose only English and Arabic; found: {installer_codes}"
            )
        desktop_task = next(
            (line for line in installer_text.splitlines() if line.startswith('Name: "desktopicon";')),
            "",
        )
        if not desktop_task or "unchecked" in desktop_task.lower():
            ERRORS.append(f"The desktop shortcut must be a clear default task in {relative(installer_path)}.")
        postinstall_lines = [line for line in installer_text.splitlines() if "postinstall" in line.lower()]
        if not postinstall_lines or not all("runascurrentuser" in line.lower() for line in postinstall_lines):
            ERRORS.append(f"Post-install launch must explicitly inherit Setup elevation to avoid error 740 in {relative(installer_path)}.")

    required = [
        APP / "MainWindow.Shortcuts.cs",
        APP / "LanguageSelectionWindow.xaml",
        APP / "LanguageSelectionWindow.xaml.cs",
    ]
    for path in required:
        if not path.exists():
            ERRORS.append(f"Missing interface/localization component: {relative(path)}")



def _unescape_csharp_string(value: str) -> str:
    return (
        value.replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
        .replace(r'\"', '"')
        .replace(r"\\", "\\")
    )


def _normalize_interpolated_template(value: str) -> str:
    result: list[str] = []
    index = 0
    placeholder = 0
    while index < len(value):
        if value.startswith("{{", index):
            result.append("{{")
            index += 2
            continue
        if value.startswith("}}", index):
            result.append("}}")
            index += 2
            continue
        if value[index] != "{":
            result.append(value[index])
            index += 1
            continue

        depth = 1
        cursor = index + 1
        quote: str | None = None
        escaped = False
        while cursor < len(value) and depth:
            char = value[cursor]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            cursor += 1
        result.append("{" + str(placeholder) + "}")
        placeholder += 1
        index = cursor
    return "".join(result)


def _find_invocation_end(text: str, start: int) -> int:
    depth = 1
    index = start
    quote: str | None = None
    verbatim = False
    escaped = False
    while index < len(text):
        char = text[index]
        if quote is not None:
            if verbatim:
                if char == '"':
                    if index + 1 < len(text) and text[index + 1] == '"':
                        index += 2
                        continue
                    quote = None
                    verbatim = False
            elif escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char == '"':
            quote = '"'
            verbatim = index > 0 and text[index - 1] == "@"
        elif char == "'":
            quote = "'"
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def check_runtime_localization_coverage() -> int:
    catalog_path = APP / "Services" / "LocalizationCatalog.cs"
    catalog = catalog_path.read_text(encoding="utf-8")

    # Normal C# strings cannot contain literal line breaks. This caught a prior
    # localization-regression that a line-based parser could miss.
    in_string = False
    escaped = False
    literal_newlines = 0
    for char in catalog:
        if in_string:
            if char == "\n":
                literal_newlines += 1
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
    if literal_newlines:
        ERRORS.append(
            f"LocalizationCatalog.cs contains {literal_newlines} literal newline(s) inside regular C# strings."
        )

    localized_values: set[str] = set()
    for line in catalog.splitlines():
        if "new(" not in line:
            continue
        values = re.findall(r'"((?:\\.|[^"\\])*)"', line)
        localized_values.update(_unescape_csharp_string(value) for value in values[:2])

    method_names = [
        "L", "SetStatus", "SetBusy", "HandleError", "ShowLocalizedMessage",
        "RecordActivityAsync", "SetInstallMonitorStatus",
        "LocalizationService.Translate", "LocalizationService.T",
    ]
    invocation_pattern = re.compile(
        r"(?<![\w.])(" + "|".join(re.escape(name) for name in sorted(method_names, key=len, reverse=True)) + r")\s*\("
    )
    string_pattern = re.compile(r'(?P<prefix>\$?@?|@?\$?)"(?P<body>(?:\\.|[^"\\])*)"')
    arabic = re.compile(r"[\u0600-\u06ff]")
    checked = 0

    for path in APP.glob("MainWindow*.cs"):
        text = path.read_text(encoding="utf-8")
        for invocation in invocation_pattern.finditer(text):
            end = _find_invocation_end(text, invocation.end())
            if end < 0:
                ERRORS.append(f"Could not parse localized invocation in {relative(path)}")
                continue
            body = text[invocation.end():end]
            line_number = text.count("\n", 0, invocation.start()) + 1
            for match in string_pattern.finditer(body):
                value = _unescape_csharp_string(match.group("body"))
                if not arabic.search(value):
                    continue
                if "$" in match.group("prefix"):
                    value = _normalize_interpolated_template(value)
                checked += 1
                if value not in localized_values:
                    ERRORS.append(
                        f"Runtime UI text lacks an exact Arabic/English catalog entry at "
                        f"{relative(path)}:{line_number}: {value}"
                    )
    return checked


def _catalog_arabic_to_english() -> dict[str, str]:
    main_window_xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    language_window_xaml = (APP / "LanguageSelectionWindow.xaml").read_text(encoding="utf-8")
    if not re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="DisplayName"', main_window_xaml):
        ERRORS.append("Settings language list does not use interface-localized display names.")
    if re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="NativeName"', main_window_xaml):
        ERRORS.append("Settings language list still exposes native names and can mix scripts.")
    if "{Binding DisplayName}" not in language_window_xaml:
        ERRORS.append("First-run language list does not use interface-localized display names.")
    if "Binding NativeName" in language_window_xaml or "Binding EnglishName" in language_window_xaml:
        ERRORS.append("First-run language list still displays two languages side by side.")

    catalog = (APP / "Services" / "LocalizationCatalog.cs").read_text(encoding="utf-8")
    result: dict[str, str] = {}
    pattern = re.compile(
        r'new\("((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)"'
    )
    for match in pattern.finditer(catalog):
        key, arabic, english = (_unescape_csharp_string(value) for value in match.groups())
        result[key] = english
        result[arabic] = english
    return result


def check_cleaner_rule_localization() -> int:
    translations = _catalog_arabic_to_english()
    arabic = re.compile(r"[\u0600-\u06ff]")
    checked = 0
    cleaners_dir = APP / "Cleaners"
    for path in sorted(cleaners_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rules = data if isinstance(data, list) else data.get("rules", [])
        if not isinstance(rules, list):
            ERRORS.append(f"Cleaner rule file has no rules list: {relative(path)}")
            continue
        for rule_index, rule in enumerate(rules, start=1):
            if not isinstance(rule, dict):
                ERRORS.append(f"Cleaner rule #{rule_index} is not an object: {relative(path)}")
                continue
            for field in ("name", "description"):
                value = str(rule.get(field, "")).strip()
                if not value:
                    ERRORS.append(
                        f"Cleaner rule #{rule_index} has an empty {field}: {relative(path)}"
                    )
                    continue
                checked += 1
                if arabic.search(value):
                    english = translations.get(value, "")
                    if not english:
                        ERRORS.append(
                            f"Cleaner rule {field} lacks an exact English translation in "
                            f"{relative(path)} rule #{rule_index}: {value}"
                        )
                    elif arabic.search(english):
                        ERRORS.append(
                            f"Cleaner rule English translation contains Arabic in "
                            f"{relative(path)} rule #{rule_index}: {value}"
                        )
    return checked


def check_application_source_localization() -> int:
    """Reject untranslated Arabic literals in production C# outside intentional internals."""
    translations = _catalog_arabic_to_english()
    arabic = re.compile(r"[\u0600-\u06ff]")
    string_pattern = re.compile(r'(?P<prefix>\$?@?|@?\$?)"(?P<body>(?:\\.|[^"\\])*)"')

    # These strings are implementation tokens, not user-facing copy. Keep the
    # allowlist narrow so any new Arabic source literal requires an audit.
    intentional: dict[str, set[str]] = {
        "src/SafeWindowsCleaner/Services/LocalizationService.cs": {
            "العربية", "رام", "ذاكر", "تثبيت", "إزالة", "بقايا", "قرص",
            "إصدار", "حماية", "أمان", "بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت",
            "ك.ب", "م.ب", "ج.ب", "ت.ب",
        },
        "src/SafeWindowsCleaner/Helpers/SizeFormatter.cs": {
            "بايت", "كيلوبايت", "ميغابايت", "غيغابايت", "تيرابايت",
        },
        "src/SafeWindowsCleaner/Services/PublisherInfo.cs": {
            "معن حنونة للستلايت",
        },
    }
    checked = 0
    for path in sorted(APP.rglob("*.cs")):
        if path.name == "LocalizationCatalog.cs" or any(part in {"bin", "obj"} for part in path.parts):
            continue
        rel = relative(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in string_pattern.finditer(text):
            value = _unescape_csharp_string(match.group("body"))
            if not arabic.search(value):
                continue
            # The protected-token regex intentionally contains Arabic unit and
            # punctuation fragments and is not displayed as interface text.
            if rel.endswith("LocalizationService.cs") and ("PID" in value or "\\u0600" in value or "م\\.ب" in value):
                continue
            normalized = _normalize_interpolated_template(value) if "$" in match.group("prefix") else value
            if normalized in translations or value in translations:
                checked += 1
                continue
            if value in intentional.get(rel, set()):
                checked += 1
                continue
            line_number = text.count("\n", 0, match.start()) + 1
            ERRORS.append(
                f"Production Arabic source literal is not localized or allowlisted at "
                f"{rel}:{line_number}: {normalized}"
            )
    return checked



def check_strict_bilingual_sources() -> None:
    unsupported_branch = re.compile(r'"(?:es|fr|it|ru|de|pt)"\s*=>')
    for source_root in (APP, LEGACY):
        for path in source_root.rglob("*.cs"):
            if any(part in {"bin", "obj"} for part in path.parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if unsupported_branch.search(text):
                ERRORS.append(f"Unsupported production language switch remains: {relative(path)}")
            if "EmptyWorkingSet" in text or "TrimWorkingSetsAsync" in text:
                ERRORS.append(f"Temporary working-set trimming remains in Lite production source: {relative(path)}")



def check_resource_and_binding_contract() -> None:
    """Verify that every visible WPF resource and language-bearing table field is localized."""
    catalog_text = (APP / "Services" / "LocalizationCatalog.cs").read_text(encoding="utf-8")
    catalog_keys = set(re.findall(r'new\("((?:\\.|[^"\\])*)"\s*,', catalog_text))

    for xaml_path in (
        APP / "MainWindow.xaml",
        APP / "LanguageSelectionWindow.xaml",
        LEGACY / "MainWindow.xaml",
    ):
        tree = ET.parse(xaml_path)
        for element in tree.iter():
            if element.text and element.text.strip():
                ERRORS.append(
                    f"Visible XAML text node must be resource-backed in {relative(xaml_path)}: {element.text.strip()}"
                )

        if xaml_path.parent == APP:
            text = xaml_path.read_text(encoding="utf-8")
            for key in sorted(set(re.findall(r'\{DynamicResource\s+([^}\s]+)', text))):
                if key.startswith("UI.") and key not in catalog_keys:
                    ERRORS.append(f"Missing DynamicResource localization key in {relative(xaml_path)}: {key}")

    modern_xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    # These model properties can contain Arabic source values or localization keys.
    # Binding the raw value was the main source of mixed-language data grids.
    forbidden_raw_bindings = (
        "{Binding Category}",
        "{Binding Description}",
        "{Binding ProtectionReason}",
        "{Binding MatchReason}",
        "{Binding Confidence}",
        "{Binding SignatureStatus}",
        "{Binding RecommendationText}",
        "{Binding Summary}",
        "{Binding Status}",
    )
    for binding in forbidden_raw_bindings:
        if binding in modern_xaml:
            ERRORS.append(f"Modern data grid bypasses localization through raw binding: {binding}")

    modern_sources = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in APP.rglob("*.cs")
        if not any(part in {"bin", "obj"} for part in path.parts)
    )
    for pattern, label in (
        (r'MessageBox\.Show\(\s*ex\.Message', "raw exception message"),
        (r'\.(?:Text|Content|Header|Title|ToolTip)\s*=\s*ex\.Message', "raw exception UI assignment"),
    ):
        if re.search(pattern, modern_sources):
            ERRORS.append(f"Modern UI exposes a {label} instead of a localized message.")

    legacy_localization = (LEGACY / "Services" / "LocalizationService.cs").read_text(encoding="utf-8")
    legacy_entries = re.findall(
        r'\{"((?:\\.|[^"\\])*)",\s*new\[\]\{"((?:\\.|[^"\\])*)",\s*"((?:\\.|[^"\\])*)"\}\}',
        legacy_localization,
    )
    legacy_keys: list[str] = []
    arabic = re.compile(r"[\u0600-\u06ff]")
    for key, ar, en in legacy_entries:
        legacy_keys.append(key)
        if not ar.strip() or not en.strip():
            ERRORS.append(f"Legacy localization entry is incomplete: {key}")
        if arabic.search(en):
            ERRORS.append(f"Arabic text leaked into Legacy English localization: {key}")
        if re.search(r"(?<![A-Za-z])(?:TB|GB|MB|KB|B)(?![A-Za-z])", ar):
            ERRORS.append(f"English size unit leaked into Legacy Arabic localization: {key}")
        if re.search(r"(?:بايت|كيلوبايت|ميغابايت|غيغابايت|تيرابايت)", en):
            ERRORS.append(f"Arabic size unit leaked into Legacy English localization: {key}")
    for key in sorted(set(legacy_keys)):
        if legacy_keys.count(key) > 1:
            ERRORS.append(f"Duplicate Legacy localization key: {key}")


def check_release_contract() -> None:
    expected = "2.4.0"
    checks = {
        "modern project": ((APP / "SafeWindowsCleaner.csproj").read_text(encoding="utf-8"), f"<Version>{expected}</Version>"),
        "modern assembly": ((APP / "SafeWindowsCleaner.csproj").read_text(encoding="utf-8"), f"<AssemblyVersion>{expected}.0</AssemblyVersion>"),
        "legacy project": ((LEGACY / "SafeWindowsCleaner.Win7.csproj").read_text(encoding="utf-8"), f"<Version>{expected}</Version>"),
        "legacy target": ((LEGACY / "SafeWindowsCleaner.Win7.csproj").read_text(encoding="utf-8"), "<TargetFramework>net461</TargetFramework>"),
        "legacy architecture": ((LEGACY / "SafeWindowsCleaner.Win7.csproj").read_text(encoding="utf-8"), "<PlatformTarget>AnyCPU</PlatformTarget>"),
        "legacy executable identity": ((LEGACY / "SafeWindowsCleaner.Win7.csproj").read_text(encoding="utf-8"), "<AssemblyName>SafeWindowsCleaner</AssemblyName>"),
        "x64 installer": ((ROOT / "installer" / "SafeWindowsCleaner.iss").read_text(encoding="utf-8"), f'#define MyAppVersion "{expected}"'),
        "x86 installer": ((ROOT / "installer" / "SafeWindowsCleaner.x86.iss").read_text(encoding="utf-8"), f'#define MyAppVersion "{expected}"'),
        "legacy installer": ((ROOT / "installer" / "SafeWindowsCleaner.Win7.iss").read_text(encoding="utf-8"), f'#define MyAppVersion "{expected}"'),
        "workflow": ((ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8"), f"Version: {expected}"),
        "release script": ((ROOT / "scripts" / "validate-release.ps1").read_text(encoding="utf-8"), expected),
    }
    for name, (text, needle) in checks.items():
        if needle not in text:
            ERRORS.append(f"Version contract failed for {name}: missing {needle}")

    for manifest_path in (APP / "app.manifest", LEGACY / "app.manifest"):
        manifest = manifest_path.read_text(encoding="utf-8")
        if 'requestedExecutionLevel level="requireAdministrator"' not in manifest:
            ERRORS.append(f"Administrator execution level is missing: {relative(manifest_path)}")
        if f'assemblyIdentity version="{expected}.0"' not in manifest:
            ERRORS.append(f"Manifest version drift: {relative(manifest_path)}")

    required_files = [
        APP / "Services" / "ElevationService.cs",
        APP / "Services" / "CleanerRuleService.cs",
        APP / "Services" / "CleanupProfileService.cs",
        APP / "Services" / "ScheduledCleanupService.cs",
        APP / "Services" / "CommandLineRunner.cs",
        APP / "Services" / "AuthenticodeVerifier.cs",
        APP / "Services" / "OperationSessionService.cs",
        APP / "Services" / "VirtualMemoryService.cs",
        APP / "MainWindow.VirtualMemory.cs",
        APP / "MainWindow.V20.cs",
        APP / "Cleaners" / "windows-and-apps.json",
    ]
    for path in required_files:
        if not path.exists():
            ERRORS.append(f"Missing v2 Lite component: {relative(path)}")

    legacy_required = [
        LEGACY / "App.xaml",
        LEGACY / "MainWindow.xaml",
        LEGACY / "Services" / "CleanupService.cs",
        LEGACY / "Services" / "InstalledProgramService.cs",
        LEGACY / "Services" / "VirtualMemoryService.cs",
        ROOT / "installer" / "SafeWindowsCleaner.Win7.iss",
        ROOT / "installer" / "SafeWindowsCleaner.x86.iss",
        ROOT / "WINDOWS7-LEGACY-README-AR-EN.txt",
        ROOT / "PACKAGE-SELECTION-AR-EN.txt",
    ]
    for path in legacy_required:
        if not path.exists():
            ERRORS.append(f"Missing multi-OS component: {relative(path)}")

    installers = [
        (ROOT / "installer" / "SafeWindowsCleaner.iss").read_text(encoding="utf-8"),
        (ROOT / "installer" / "SafeWindowsCleaner.x86.iss").read_text(encoding="utf-8"),
        (ROOT / "installer" / "SafeWindowsCleaner.Win7.iss").read_text(encoding="utf-8"),
    ]
    common_app_id = "AppId={{CE435A11-66CC-4B7E-A669-F45DCE612BB4}"
    for installer_text in installers:
        if common_app_id not in installer_text:
            ERRORS.append("All Setup packages must share one AppId so upgrades replace old copies.")
        if 'DefaultDirName={autopf}\\Safe Windows Cleaner Lite' not in installer_text:
            ERRORS.append("All Setup packages must share the same installation directory.")
        if '#define MyAppExeName "SafeWindowsCleaner.exe"' not in installer_text:
            ERRORS.append("All Setup packages must install SafeWindowsCleaner.exe.")
        postinstall_lines = [line for line in installer_text.splitlines() if "postinstall" in line.lower()]
        if not postinstall_lines or not all("runascurrentuser" in line.lower() for line in postinstall_lines):
            ERRORS.append("Every post-install application launch must explicitly inherit Setup elevation.")

    profile_code = (APP / "Services" / "CleanupProfileService.cs").read_text(encoding="utf-8")
    if "normalized == ReviewProfile ? SafeProfile : normalized" not in profile_code:
        ERRORS.append("Scheduled cleanup does not guard against the manual-review profile.")

    main_window_xaml = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    language_window_xaml = (APP / "LanguageSelectionWindow.xaml").read_text(encoding="utf-8")
    if not re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="DisplayName"', main_window_xaml):
        ERRORS.append("Settings language list does not use interface-localized display names.")
    if re.search(r'LanguageComboBox[\s\S]*?DisplayMemberPath="NativeName"', main_window_xaml):
        ERRORS.append("Settings language list still exposes native names and can mix scripts.")
    if "{Binding DisplayName}" not in language_window_xaml:
        ERRORS.append("First-run language list does not use interface-localized display names.")
    if "Binding NativeName" in language_window_xaml or "Binding EnglishName" in language_window_xaml:
        ERRORS.append("First-run language list still displays two languages side by side.")
    localization_service = (APP / "Services" / "LocalizationService.cs").read_text(encoding="utf-8")
    if "TranslateElement(" in localization_service:
        ERRORS.append("Legacy visual-tree translation remains and can mix already-localized controls.")
    if "IsTechnicalIdentifier" not in localization_service:
        ERRORS.append("Strict Arabic fallback for unknown English prose is missing.")
    if 'Binding="{Binding LocationText}"' not in main_window_xaml:
        ERRORS.append("Install-monitor location text bypasses localization.")

    legacy_main = (LEGACY / "MainWindow.xaml.cs").read_text(encoding="utf-8")
    if re.search(r"MessageBox\.Show\(ex\.Message", legacy_main):
        ERRORS.append("Legacy UI exposes raw exception text in the active interface language.")
    if 'LocalizationService.Get("OperationFailed")' not in legacy_main:
        ERRORS.append("Legacy UI has no language-safe generic error message.")

    modern_vm = (APP / "Services" / "VirtualMemoryService.cs").read_text(encoding="utf-8")
    if "Environment.Is64BitOperatingSystem ? RegistryView.Registry64 : RegistryView.Registry32" not in modern_vm:
        ERRORS.append("Modern virtual-memory registry access does not support both x64 and x86 Windows.")

    legacy_vm = (LEGACY / "Services" / "VirtualMemoryService.cs").read_text(encoding="utf-8")
    for needle in ("MaximumSizeMb = 16384", "MediumSizeMb = 8192", "MinimumSizeMb = 4096", "MinimumFreeBytesAfterApply"):
        if needle not in legacy_vm:
            ERRORS.append(f"Legacy adaptive virtual-memory contract is missing: {needle}")

    updater = (APP / "Services" / "UpdateService.cs").read_text(encoding="utf-8")
    for needle in (
        "Environment.Is64BitProcess",
        "-Win10-11-{architecture}-Setup.exe",
        "SelectSetupAssetName",
        "SafeWindowsCleaner-Lite-Setup.exe",
    ):
        if needle not in updater:
            ERRORS.append(f"Architecture-aware update selection is missing: {needle}")

    legacy_installer_text = (ROOT / "installer" / "SafeWindowsCleaner.Win7.iss").read_text(encoding="utf-8")
    if "OnlyBelowVersion=10.0" not in legacy_installer_text:
        ERRORS.append("Legacy installer must reject Windows 10 and newer.")
    if "Net461MinimumRelease = 394254" not in legacy_installer_text:
        ERRORS.append("Legacy installer does not detect .NET Framework 4.6.1 or later.")
    modern_xaml_text = (APP / "MainWindow.xaml").read_text(encoding="utf-8")
    if "EnableTemporaryMemoryReleaseCheckBox" in modern_xaml_text:
        ERRORS.append("Obsolete temporary-memory setting is still exposed.")

    if "Windows7-8-8.1-Legacy-Setup.exe" in updater:
        ERRORS.append("The modern updater must not select the Windows Legacy package.")

    catalog = (APP / "Services" / "LocalizationCatalog.cs").read_text(encoding="utf-8")
    for key in (
        "@ProfileSafe", "@ProfileSafeDescription", "@ProfileBrowser", "@ProfileBrowserDescription",
        "@ProfileSpace", "@ProfileSpaceDescription", "@ProfileReview", "@ProfileReviewDescription",
    ):
        if f'new("{key}",' not in catalog:
            ERRORS.append(f"Missing localization entry: {key}")


def main() -> int:
    xml_count, json_count = check_xml_and_json()
    xaml_names, handlers = check_xaml()
    csharp_count = check_csharp_brackets()
    localization_count = check_localization_catalog()
    check_production_localization()
    runtime_localization_count = check_runtime_localization_coverage()
    cleaner_rule_text_count = check_cleaner_rule_localization()
    production_source_text_count = check_application_source_localization()
    check_strict_bilingual_sources()
    check_resource_and_binding_contract()
    check_release_contract()

    print("Safe Windows Cleaner Lite 2.4.0 - static source gate")
    print(f"XML/XAML files parsed: {xml_count}")
    print(f"JSON files parsed: {json_count}")
    print(f"C# files bracket-scanned: {csharp_count}")
    print(f"Localization entries checked: {localization_count}")
    print(f"Runtime UI strings checked: {runtime_localization_count}")
    print(f"Cleaner rule texts checked: {cleaner_rule_text_count}")
    print(f"Production Arabic source strings checked: {production_source_text_count}")
    print(f"Unique WPF handlers checked: {handlers}")
    print(f"Named WPF elements checked: {xaml_names}")
    if ERRORS:
        print(f"FAILED: {len(ERRORS)} error(s)")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print("PASSED: no static source-gate errors")
    print("NOTE: run the Windows/.NET build and safety tests before publishing binaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
