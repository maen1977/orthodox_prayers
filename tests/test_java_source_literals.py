from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JAVA_ROOT = ROOT / "app/src"


def scan_unclosed_line_literals(path: Path) -> list[tuple[int, str]]:
    """Return physical Java lines ending inside a normal string/char literal.

    Java string and char literals cannot continue across a physical newline.
    Text blocks are tracked separately so valid triple-quoted blocks are allowed.
    """
    failures: list[tuple[int, str]] = []
    in_block_comment = False
    in_text_block = False

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        in_string = False
        in_char = False
        escaped = False
        index = 0

        while index < len(line):
            if in_text_block:
                closing = line.find('"""', index)
                if closing < 0:
                    index = len(line)
                    continue
                in_text_block = False
                index = closing + 3
                continue

            if in_block_comment:
                closing = line.find("*/", index)
                if closing < 0:
                    index = len(line)
                    continue
                in_block_comment = False
                index = closing + 2
                continue

            ch = line[index]
            nxt = line[index + 1] if index + 1 < len(line) else ""

            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                index += 1
                continue

            if in_char:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == "'":
                    in_char = False
                index += 1
                continue

            if ch == "/" and nxt == "/":
                break
            if ch == "/" and nxt == "*":
                in_block_comment = True
                index += 2
                continue
            if line.startswith('"""', index):
                in_text_block = True
                index += 3
                continue
            if ch == '"':
                in_string = True
            elif ch == "'":
                in_char = True
            index += 1

        if in_string or in_char:
            failures.append((line_number, line.strip()))

    return failures


class JavaSourceLiteralTests(unittest.TestCase):
    def test_no_java_string_or_char_literal_crosses_a_physical_line(self):
        failures: list[str] = []
        for path in sorted(JAVA_ROOT.rglob("*.java")):
            for line_number, line in scan_unclosed_line_literals(path):
                failures.append(f"{path.relative_to(ROOT)}:{line_number}: {line}")
        self.assertEqual([], failures, "Unclosed Java line literal(s):\n" + "\n".join(failures))

    def test_reader_share_newlines_are_escaped_java_literals(self):
        adapter = (JAVA_ROOT / "main/java/com/orthodoxprayers/privateapp/ui/ReaderAdapter.java").read_text(encoding="utf-8")
        reader = (JAVA_ROOT / "main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java").read_text(encoding="utf-8")
        self.assertIn('speaker + "\\n" + text', adapter)
        self.assertIn('String footer = "\\n\\n— " + title + "\\n"', reader)
        self.assertIn('footer += "\\n" + local(', reader)


if __name__ == "__main__":
    unittest.main()
