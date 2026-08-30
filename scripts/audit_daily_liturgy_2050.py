#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 1, 1)
END = date(2050, 12, 31)


def dates():
    day = START
    while day <= END:
        yield day
        day += timedelta(days=1)


def load_day(day):
    path = ROOT / "app/src/main/assets/data/calendar" / f"calendar_{day.year}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(item for item in data["days"] if item["date_iso"] == day.isoformat())


def main():
    counts = Counter()
    rules = Counter()
    missing = []
    anomalies = []
    samples = defaultdict(list)
    for day in dates():
        item = load_day(day)
        selection = item.get("liturgy_service_selection") or {}
        service_type = selection.get("service_type")
        rule = selection.get("rule_id")
        if not service_type or not rule:
            missing.append(day.isoformat())
            continue
        counts[service_type] += 1
        rules[rule] += 1
        if len(samples[service_type]) < 5:
            samples[service_type].append(day.isoformat())
        basil_rules = {
            "saint_basil_day",
            "great_lent_sunday",
            "great_holy_thursday",
            "great_holy_saturday",
            "nativity_theophany_vesperal_basil_on_eve",
            "nativity_theophany_basil_on_sunday_or_monday_feast",
        }
        presanctified_rules = {"great_lent_wednesday_or_friday", "first_three_days_of_holy_week"}
        if service_type == "basil" and rule not in basil_rules:
            anomalies.append((day.isoformat(), "basil_rule_mismatch:" + str(rule)))
        if service_type == "presanctified" and rule not in presanctified_rules:
            anomalies.append((day.isoformat(), "presanctified_rule_mismatch:" + str(rule)))
        if service_type == "no_divine_liturgy" and rule != "great_friday_no_divine_liturgy":
            anomalies.append((day.isoformat(), "no_liturgy_rule_mismatch:" + str(rule)))
        if service_type == "typikon_override_required" and rule != "annunciation_paschal_triduum_collision":
            anomalies.append((day.isoformat(), "override_rule_mismatch:" + str(rule)))
    report = {
        "schema_version": 1,
        "range": {"start": START.isoformat(), "end": END.isoformat(), "days": (END - START).days + 1},
        "counts_by_service_type": dict(sorted(counts.items())),
        "counts_by_rule": dict(sorted(rules.items())),
        "missing_selection_days": missing,
        "anomalies": anomalies,
        "samples": dict(samples),
        "policy": "Structural audit only; exact local Typikon exceptions require dated official overrides and are not inferred.",
    }
    out = ROOT / "canonical/daily_liturgy_2050_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"days": report["range"]["days"], "counts": report["counts_by_service_type"], "missing": len(missing), "anomalies": len(anomalies)}, ensure_ascii=False))
    if missing or anomalies:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
