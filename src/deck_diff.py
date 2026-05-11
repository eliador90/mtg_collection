from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from deck_io import deck_entry_map, load_deck_json


@dataclass
class DeckDiffReport:
    old_deck_name: str
    new_deck_name: str
    added: list[dict] = field(default_factory=list)
    removed: list[dict] = field(default_factory=list)
    count_changed: list[dict] = field(default_factory=list)
    category_changed: list[dict] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.count_changed or self.category_changed)


def compare_decks(old_deck_path: str, new_deck_path: str, include_commander: bool = False) -> DeckDiffReport:
    old_deck = load_deck_json(old_deck_path)
    new_deck = load_deck_json(new_deck_path)
    old_map = deck_entry_map(old_deck, include_commander=include_commander)
    new_map = deck_entry_map(new_deck, include_commander=include_commander)

    report = DeckDiffReport(
        old_deck_name=str(old_deck.get("name", Path(old_deck_path).stem)),
        new_deck_name=str(new_deck.get("name", Path(new_deck_path).stem)),
    )

    for name in sorted(set(new_map) - set(old_map)):
        report.added.append(new_map[name])
    for name in sorted(set(old_map) - set(new_map)):
        report.removed.append(old_map[name])

    for name in sorted(set(old_map) & set(new_map)):
        old_entry = old_map[name]
        new_entry = new_map[name]
        if old_entry["count"] != new_entry["count"]:
            report.count_changed.append(
                {
                    "name": name,
                    "old_count": old_entry["count"],
                    "new_count": new_entry["count"],
                    "category": new_entry["category"],
                }
            )
        if old_entry["category"] != new_entry["category"]:
            report.category_changed.append(
                {
                    "name": name,
                    "old_category": old_entry["category"],
                    "new_category": new_entry["category"],
                    "count": new_entry["count"],
                }
            )

    return report


def report_to_dict(report: DeckDiffReport) -> dict:
    return {
        "old_deck_name": report.old_deck_name,
        "new_deck_name": report.new_deck_name,
        "has_changes": report.has_changes,
        "added": report.added,
        "removed": report.removed,
        "count_changed": report.count_changed,
        "category_changed": report.category_changed,
    }


def write_diff_json(report: DeckDiffReport, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")


def format_diff_report(report: DeckDiffReport) -> str:
    lines = [
        f"Old deck: {report.old_deck_name}",
        f"New deck: {report.new_deck_name}",
        f"Result: {'CHANGED' if report.has_changes else 'NO CHANGES'}",
    ]
    append_entry_section(lines, "Added", report.added, prefix="+")
    append_entry_section(lines, "Removed", report.removed, prefix="-")

    if report.count_changed:
        lines.append("Count Changes:")
        for item in report.count_changed:
            lines.append(f"* {item['name']}: {item['old_count']} -> {item['new_count']} ({item['category']})")

    if report.category_changed:
        lines.append("Category Changes:")
        for item in report.category_changed:
            lines.append(f"* {item['name']}: {item['old_category']} -> {item['new_category']}")

    return "\n".join(lines)


def append_entry_section(lines: list[str], title: str, entries: list[dict], prefix: str) -> None:
    if not entries:
        return
    lines.append(f"{title}:")
    for entry in entries:
        lines.append(f"{prefix} {entry['count']} {entry['name']} ({entry['category']})")
