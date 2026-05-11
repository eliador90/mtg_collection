from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from deck_generation import BASIC_LAND_METADATA, clean_text, read_collection
from deck_validation import build_collection_lookup


MANABOX_EXPORT_COLUMNS = ["Name", "Quantity", "Scryfall ID", "Category", "Commander"]


def load_deck_json(deck_path: str) -> dict:
    path = Path(deck_path)
    if not path.exists():
        raise FileNotFoundError(f"Deck JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_deck_entries(deck: dict, include_commander: bool = False) -> list[dict]:
    entries = []
    commander = deck.get("commander", {})
    commander_name = clean_text(commander.get("name"))
    if include_commander and commander_name:
        entries.append(
            {
                "name": commander_name,
                "count": 1,
                "category": "Commander",
                "is_commander": True,
            }
        )

    for card in deck.get("cards", []):
        name = clean_text(card.get("name"))
        if not name:
            continue
        entries.append(
            {
                "name": name,
                "count": int(card.get("count", 1) or 1),
                "category": clean_text(card.get("category")) or "Uncategorized",
                "is_commander": False,
            }
        )
    return entries


def deck_entry_map(deck: dict, include_commander: bool = False) -> dict[str, dict]:
    mapped: dict[str, dict] = {}
    for entry in iter_deck_entries(deck, include_commander=include_commander):
        name = entry["name"]
        if name in mapped:
            mapped[name]["count"] += entry["count"]
            continue
        mapped[name] = dict(entry)
    return mapped


def export_deck_to_manabox_csv(deck_path: str, output_path: str, collection_path: str = "", include_commander: bool = True) -> None:
    deck = load_deck_json(deck_path)
    collection_lookup = build_export_lookup(collection_path) if collection_path else {}
    rows = []

    commander = deck.get("commander", {})
    commander_name = clean_text(commander.get("name"))
    if include_commander and commander_name:
        rows.append(build_export_row(commander_name, 1, "Commander", True, collection_lookup))

    for card in deck.get("cards", []):
        name = clean_text(card.get("name"))
        if not name:
            continue
        count = int(card.get("count", 1) or 1)
        category = clean_text(card.get("category")) or infer_export_category(name, collection_lookup)
        rows.append(build_export_row(name, count, category, False, collection_lookup))

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANABOX_EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def import_manabox_deck_csv(input_path: str, output_path: str, commander_name: str, collection_path: str = "", deck_name: str = "") -> None:
    csv_path = Path(input_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"ManaBox-style CSV not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Input CSV is empty.")
    if "Name" not in rows[0] or "Quantity" not in rows[0]:
        raise ValueError("ManaBox-style deck CSV must include Name and Quantity columns.")

    collection_lookup = build_import_lookup(collection_path) if collection_path else {}
    commander = build_commander_entry(commander_name, collection_lookup)
    cards = []

    for row in rows:
        name = clean_text(row.get("Name"))
        if not name or name.casefold() == commander_name.casefold():
            continue
        count = int(row.get("Quantity") or 1)
        category = clean_text(row.get("Category")) or infer_import_category(name, collection_lookup)
        entry = {"name": name, "category": category}
        if count > 1:
            entry["count"] = count
        if name in BASIC_LAND_METADATA:
            entry.update(BASIC_LAND_METADATA[name])
        cards.append(entry)

    deck = {
        "name": deck_name or f"{commander_name} - ManaBox Import",
        "commander": commander,
        "refinement": {
            "maybeboard": [],
            "cut_candidates": [],
            "upgrade_suggestions": [],
        },
        "cards": cards,
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(deck, indent=2), encoding="utf-8")


def build_export_lookup(collection_path: str) -> dict[str, dict]:
    df = read_collection(collection_path)
    lookup = {}
    for _, row in df.sort_values(["Quantity", "Name"], ascending=[False, True]).iterrows():
        name = clean_text(row.get("Name"))
        if not name or name in lookup:
            continue
        lookup[name] = {
            "scryfall_id": clean_text(row.get("Scryfall ID")),
            "type_line": clean_text(row.get("type_line")),
        }
    return lookup


def build_import_lookup(collection_path: str) -> dict[str, dict]:
    df = read_collection(collection_path)
    validation_lookup = build_collection_lookup(df)
    export_lookup = build_export_lookup(collection_path)
    for name, metadata in validation_lookup.items():
        metadata["scryfall_id"] = export_lookup.get(name, {}).get("scryfall_id", "")
    return validation_lookup


def build_export_row(name: str, count: int, category: str, is_commander: bool, collection_lookup: dict[str, dict]) -> dict:
    return {
        "Name": name,
        "Quantity": count,
        "Scryfall ID": collection_lookup.get(name, {}).get("scryfall_id", ""),
        "Category": category,
        "Commander": "yes" if is_commander else "",
    }


def build_commander_entry(commander_name: str, collection_lookup: dict[str, dict]) -> dict:
    metadata = collection_lookup.get(commander_name, {})
    return {
        "name": commander_name,
        "category": "Commander",
        "mana_cost": "",
        "type_line": metadata.get("type_line", "Legendary Creature"),
        "oracle_text": metadata.get("oracle_text", ""),
        "color_identity": ", ".join(metadata.get("color_identity", [])),
    }


def infer_export_category(name: str, collection_lookup: dict[str, dict]) -> str:
    type_line = collection_lookup.get(name, {}).get("type_line", "")
    return category_from_type_line(type_line)


def infer_import_category(name: str, collection_lookup: dict[str, dict]) -> str:
    type_line = collection_lookup.get(name, {}).get("type_line", "")
    if name in BASIC_LAND_METADATA:
        return "Lands"
    return category_from_type_line(type_line)


def category_from_type_line(type_line: str) -> str:
    if "Land" in type_line:
        return "Lands"
    if "Instant" in type_line or "Sorcery" in type_line:
        return "Instants / Sorceries"
    if "Artifact" in type_line or "Enchantment" in type_line:
        return "Artifacts / Enchantments"
    if "Creature" in type_line:
        return "Creatures"
    return "Utility"
