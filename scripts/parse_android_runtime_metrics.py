#!/usr/bin/env python3
"""Parse Android startup, memory, and frame output and enforce lightweight budgets."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUDGETS = ROOT / "config/android-performance-budgets.json"


@dataclass(frozen=True)
class JankSample:
    total_frames: int | None
    janky_frames: int
    percent: float


def required_integer(patterns: list[str], text: str, label: str) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            return int(match.group(1))
    raise SystemExit(f"Unable to parse {label}")


def parse_total_pss(text: str) -> int:
    return required_integer(
        [r"^\s*TOTAL\s+PSS:\s*([0-9]+)", r"^\s*TOTAL\s+([0-9]+)\s+"],
        text,
        "TOTAL PSS",
    )


def parse_start(path: Path, label: str) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return (
        required_integer([r"^TotalTime:\s*([0-9]+)"], text, f"{label} TotalTime"),
        required_integer([r"^WaitTime:\s*([0-9]+)"], text, f"{label} WaitTime"),
    )


def parse_jank(path: Path | None) -> JankSample | None:
    if path is None or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"Janky frames:\s*([0-9]+)\s*\(([0-9]+(?:\.[0-9]+)?)%\)",
        text,
        re.I,
    )
    if not match:
        return None
    total_match = re.search(r"Total frames rendered:\s*([0-9]+)", text, re.I)
    return JankSample(
        total_frames=int(total_match.group(1)) if total_match else None,
        janky_frames=int(match.group(1)),
        percent=float(match.group(2)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-level", type=int, required=True)
    parser.add_argument("--enforcement-mode", choices=("strict", "compatibility"), default="strict")
    parser.add_argument("--start-output", type=Path, required=True)
    parser.add_argument("--warm-start-output", type=Path)
    parser.add_argument("--meminfo-output", type=Path, required=True)
    parser.add_argument("--reader-meminfo-output", type=Path)
    parser.add_argument("--search-meminfo-output", type=Path)
    parser.add_argument("--gfxinfo-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budgets", type=Path, default=DEFAULT_BUDGETS)
    args = parser.parse_args()

    total_time, wait_time = parse_start(args.start_output, "cold start")
    total_pss = parse_total_pss(args.meminfo_output.read_text(encoding="utf-8", errors="replace"))
    warm = parse_start(args.warm_start_output, "warm start") if args.warm_start_output else None
    reader_pss = parse_total_pss(args.reader_meminfo_output.read_text(encoding="utf-8", errors="replace")) if args.reader_meminfo_output else None
    search_pss = parse_total_pss(args.search_meminfo_output.read_text(encoding="utf-8", errors="replace")) if args.search_meminfo_output else None
    jank = parse_jank(args.gfxinfo_output)

    budgets_document = json.loads(args.budgets.read_text(encoding="utf-8"))
    budget = budgets_document.get("budgets", {}).get(str(args.api_level))
    if not isinstance(budget, dict):
        raise SystemExit(f"No performance budget configured for API {args.api_level}")

    metrics: dict[str, object] = {
        "schema_version": 3,
        "api_level": args.api_level,
        "enforcement_mode": args.enforcement_mode,
        "cold_start_total_time_ms": total_time,
        "cold_start_wait_time_ms": wait_time,
        "total_pss_kb": total_pss,
        "budgets": budget,
        "status": "PASS",
    }
    if warm:
        metrics["warm_start_total_time_ms"], metrics["warm_start_wait_time_ms"] = warm
    if reader_pss is not None:
        metrics["reader_total_pss_kb"] = reader_pss
    if search_pss is not None:
        metrics["search_total_pss_kb"] = search_pss
    if jank is not None:
        metrics["janky_frames_percent"] = jank.percent
        metrics["janky_frames_count"] = jank.janky_frames
        if jank.total_frames is not None:
            metrics["total_frames_rendered"] = jank.total_frames

    failures: list[str] = []
    warnings: list[str] = []
    checks = [
        (total_time, "cold_start_total_time_ms_max", "cold start", "ms"),
        (total_pss, "total_pss_kb_max", "home TOTAL PSS", "KB"),
        (warm[0] if warm else None, "warm_start_total_time_ms_max", "warm start", "ms"),
        (reader_pss, "reader_total_pss_kb_max", "reader TOTAL PSS", "KB"),
        (search_pss, "search_total_pss_kb_max", "search TOTAL PSS", "KB"),
    ]
    for actual, key, label, suffix in checks:
        if actual is not None and key in budget and actual > float(budget[key]):
            failures.append(f"{label} {actual}{suffix} exceeds {budget[key]}{suffix}")

    minimum_frames = int(budget.get("janky_frames_min_sample", 90))
    metrics["jank_minimum_sample_frames"] = minimum_frames
    metrics["jank_enforced"] = args.enforcement_mode == "strict"
    jank_requested = args.gfxinfo_output is not None
    if jank is None and jank_requested:
        message = "gfxinfo did not provide a janky-frame sample"
        (failures if args.enforcement_mode == "strict" else warnings).append(message)
    elif jank is not None and (jank.total_frames is None or jank.total_frames < minimum_frames):
        message = f"frame sample {jank.total_frames or 0} is below required {minimum_frames} frames"
        (failures if args.enforcement_mode == "strict" else warnings).append(message)
    elif jank is not None and "janky_frames_percent_max" in budget and jank.percent > float(budget["janky_frames_percent_max"]):
        message = f"janky frames {jank.percent}% exceeds {budget['janky_frames_percent_max']}%"
        (failures if args.enforcement_mode == "strict" else warnings).append(message)

    if warnings:
        metrics["warnings"] = warnings
    if failures:
        metrics["status"] = "FAIL"
        metrics["failures"] = failures

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(
        "ANDROID_RUNTIME_METRICS "
        f"api={args.api_level} mode={args.enforcement_mode} cold_ms={total_time} "
        f"warm_ms={warm[0] if warm else 'n/a'} home_pss_kb={total_pss} "
        f"reader_pss_kb={reader_pss or 'n/a'} search_pss_kb={search_pss or 'n/a'} "
        f"frames={jank.total_frames if jank and jank.total_frames is not None else 'n/a'} "
        f"jank_percent={jank.percent if jank is not None else 'n/a'} status={metrics['status']}"
    )
    if warnings:
        print("ANDROID_RUNTIME_WARNINGS " + "; ".join(warnings))
    if failures:
        raise SystemExit("; ".join(failures))


if __name__ == "__main__":
    main()
