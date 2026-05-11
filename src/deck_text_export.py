from __future__ import annotations

from pathlib import Path

from deck_io import iter_deck_entries, load_deck_json


DEFAULT_CATEGORY_ORDER = [
    "Commander",
    "Lands",
    "Ramp",
    "Draw / Selection",
    "Interaction",
    "Protection",
    "Synergy Pieces",
    "Big Payoffs",
    "Creatures",
    "Artifacts / Enchantments",
    "Instants / Sorceries",
    "Utility",
]


def export_deck_to_text(deck_path: str, output_path: str, include_categories: bool = True) -> None:
    deck = load_deck_json(deck_path)
    text = format_deck_text(deck, include_categories=include_categories)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def format_deck_text(deck: dict, include_categories: bool = True) -> str:
    deck_name = str(deck.get("name", "Untitled Deck"))
    entries = iter_deck_entries(deck, include_commander=True)
    if not include_categories:
        lines = [deck_name, ""]
        for entry in entries:
            lines.append(f"{entry['count']} {entry['name']}")
        return "\n".join(lines).rstrip() + "\n"

    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry["category"], []).append(entry)

    lines = [deck_name]
    for category in ordered_categories(grouped):
        category_entries = sorted(grouped[category], key=lambda item: item["name"])
        lines.extend(["", category])
        for entry in category_entries:
            lines.append(f"{entry['count']} {entry['name']}")
    return "\n".join(lines).rstrip() + "\n"


def ordered_categories(grouped: dict[str, list[dict]]) -> list[str]:
    known = [category for category in DEFAULT_CATEGORY_ORDER if category in grouped]
    unknown = sorted(category for category in grouped if category not in DEFAULT_CATEGORY_ORDER)
    return known + unknown
