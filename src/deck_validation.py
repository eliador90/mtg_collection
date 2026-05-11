from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from deck_generation import BASIC_LAND_METADATA, clean_text, dedupe_collection_rows, read_collection, row_to_candidate
from mtg_collection_utils import split_color_identity


BASIC_LAND_NAMES = set(BASIC_LAND_METADATA)
DEFAULT_TARGET_SIZE = 100
DEFAULT_MIN_LANDS = 33
DEFAULT_MAX_LANDS = 42


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    card_name: str = ""


@dataclass
class DeckValidationReport:
    deck_name: str
    total_cards: int
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    role_counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, code: str, message: str, card_name: str = "") -> None:
        self.errors.append(ValidationIssue("error", code, message, card_name))

    def add_warning(self, code: str, message: str, card_name: str = "") -> None:
        self.warnings.append(ValidationIssue("warning", code, message, card_name))


def load_deck(deck_path: str) -> dict:
    path = Path(deck_path)
    if not path.exists():
        raise FileNotFoundError(f"Deck JSON not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_deck(
    deck_path: str,
    collection_path: str,
    target_size: int = DEFAULT_TARGET_SIZE,
    min_lands: int = DEFAULT_MIN_LANDS,
    max_lands: int = DEFAULT_MAX_LANDS,
) -> DeckValidationReport:
    deck = load_deck(deck_path)
    collection_df = read_collection(collection_path)
    collection_lookup = build_collection_lookup(collection_df)

    deck_name = clean_text(deck.get("name")) or Path(deck_path).stem
    report = DeckValidationReport(deck_name=deck_name, total_cards=0)

    validate_required_shape(deck, report)
    if report.errors:
        return report

    commander = deck["commander"]
    commander_name = clean_text(commander.get("name"))
    commander_colors = set(split_color_identity(commander.get("color_identity")))
    validate_commander(commander, collection_lookup, report)

    main_cards = deck.get("cards", [])
    total_cards = 1
    seen_nonbasics: set[str] = set()
    land_count = 0
    ramp_count = 0
    draw_count = 0
    interaction_count = 0
    high_mana_count = 0

    for index, card in enumerate(main_cards, start=1):
        name = clean_text(card.get("name"))
        category = clean_text(card.get("category")) or "Uncategorized"
        count = parse_count(card.get("count"), report, name)
        total_cards += count
        report.role_counts[category] = report.role_counts.get(category, 0) + count

        if not name:
            report.add_error("missing_card_name", f"Card entry #{index} is missing a name.")
            continue
        if name == commander_name:
            report.add_error("commander_in_main_deck", "Commander also appears in the main deck.", name)

        metadata = collection_lookup.get(name) or fallback_metadata(card)
        if not metadata:
            report.add_error("card_not_in_collection", "Main-deck card is not in the collection CSV.", name)
            continue

        type_line = metadata["type_line"]
        oracle_text = metadata["oracle_text"]
        card_colors = set(metadata["color_identity"])
        mana_value = metadata["mana_value"]
        is_land = "Land" in type_line
        is_basic = name in BASIC_LAND_NAMES or type_line.startswith("Basic Land")

        if not card_colors.issubset(commander_colors):
            colors = ", ".join(sorted(card_colors)) or "Colorless"
            allowed = ", ".join(sorted(commander_colors)) or "Colorless"
            report.add_error("illegal_color_identity", f"Color identity {colors} is outside commander's identity {allowed}.", name)

        if not is_basic:
            if count > 1:
                report.add_error("singleton_violation", "Commander singleton rule allows only one copy of this non-basic card.", name)
            if name in seen_nonbasics:
                report.add_error("duplicate_nonbasic", "Card appears more than once in the deck list.", name)
            seen_nonbasics.add(name)

        if is_land:
            land_count += count
        if is_ramp(metadata):
            ramp_count += count
        if is_draw(metadata):
            draw_count += count
        if is_interaction(metadata):
            interaction_count += count
        if mana_value >= 6 and not is_land:
            high_mana_count += count

    report.total_cards = total_cards

    if total_cards != target_size:
        report.add_error("wrong_deck_size", f"Deck has {total_cards} cards including commander; expected {target_size}.")
    if land_count < min_lands:
        report.add_warning("low_land_count", f"Deck has {land_count} lands; most Commander decks want at least {min_lands}.")
    if land_count > max_lands:
        report.add_warning("high_land_count", f"Deck has {land_count} lands; review whether that many are needed.")
    if ramp_count < 8 and target_size >= 90:
        report.add_warning("low_ramp_count", f"Detected about {ramp_count} ramp/fixing cards; many Commander decks want 8-12.")
    if draw_count < 8 and target_size >= 90:
        report.add_warning("low_draw_count", f"Detected about {draw_count} draw/selection cards; many Commander decks want 8-12.")
    if interaction_count < 8 and target_size >= 90:
        report.add_warning("low_interaction_count", f"Detected about {interaction_count} interaction cards; many Commander decks want 8-12.")
    if high_mana_count > 16 and target_size >= 90:
        report.add_warning("heavy_top_end", f"Detected {high_mana_count} nonland cards with mana value 6 or higher.")

    return report


def validate_required_shape(deck: dict, report: DeckValidationReport) -> None:
    if not isinstance(deck, dict):
        report.add_error("invalid_json_shape", "Deck file must contain a JSON object.")
        return
    if not isinstance(deck.get("commander"), dict):
        report.add_error("missing_commander", "Deck JSON must include a commander object.")
    if not isinstance(deck.get("cards"), list):
        report.add_error("missing_cards", "Deck JSON must include a cards list.")
    if "name" not in deck:
        report.add_warning("missing_deck_name", "Deck JSON does not include a deck name.")


def validate_commander(commander: dict, collection_lookup: dict[str, dict], report: DeckValidationReport) -> None:
    name = clean_text(commander.get("name"))
    if not name:
        report.add_error("missing_commander_name", "Commander is missing a name.")
        return
    if not clean_text(commander.get("color_identity")):
        report.add_warning("missing_commander_colors", "Commander color_identity is missing; legality checks may be incomplete.", name)

    metadata = collection_lookup.get(name)
    if not metadata:
        report.add_warning("commander_not_in_collection", "Commander was not found in the collection CSV.", name)
        return

    type_line = metadata["type_line"].lower()
    oracle_text = metadata["oracle_text"].lower()
    if not (("legendary" in type_line and "creature" in type_line) or "can be your commander" in oracle_text):
        report.add_error("commander_not_valid", "This card does not look like a valid Commander in the enriched data.", name)
    if not metadata["legal_commander"]:
        report.add_error("commander_not_legal", "Collection metadata says this commander is not legal in Commander.", name)


def build_collection_lookup(collection_df: pd.DataFrame) -> dict[str, dict]:
    lookup = {}
    for _, row in dedupe_collection_rows(collection_df).iterrows():
        candidate = row_to_candidate(row)
        lookup[candidate.name] = {
            "name": candidate.name,
            "type_line": candidate.type_line,
            "oracle_text": candidate.oracle_text,
            "color_identity": candidate.color_identity,
            "mana_value": candidate.mana_value,
            "legal_commander": candidate.legal_commander,
        }
    return lookup


def fallback_metadata(card: dict) -> dict | None:
    name = clean_text(card.get("name"))
    if name in BASIC_LAND_METADATA:
        metadata = BASIC_LAND_METADATA[name]
        return {
            "name": name,
            "type_line": metadata["type_line"],
            "oracle_text": metadata["oracle_text"],
            "color_identity": [],
            "mana_value": 0,
            "legal_commander": True,
        }
    if {"type_line", "color_identity"}.issubset(card):
        return {
            "name": name,
            "type_line": clean_text(card.get("type_line")),
            "oracle_text": clean_text(card.get("oracle_text")),
            "color_identity": split_color_identity(card.get("color_identity")),
            "mana_value": 0,
            "legal_commander": True,
        }
    return None


def parse_count(value: object, report: DeckValidationReport, card_name: str) -> int:
    try:
        count = int(value or 1)
    except (TypeError, ValueError):
        report.add_error("invalid_count", "Card count must be a positive integer.", card_name)
        return 1
    if count <= 0:
        report.add_error("invalid_count", "Card count must be a positive integer.", card_name)
        return 1
    return count


def is_ramp(metadata: dict) -> bool:
    text = f"{metadata['type_line']} {metadata['oracle_text']}".lower()
    return any(phrase in text for phrase in ["add {", "add one mana", "add two mana", "search your library for a basic land", "treasure token"])


def is_draw(metadata: dict) -> bool:
    text = metadata["oracle_text"].lower()
    return any(phrase in text for phrase in ["draw a card", "draw two", "draw three", "scry", "surveil", "look at the top"])


def is_interaction(metadata: dict) -> bool:
    text = metadata["oracle_text"].lower()
    return any(
        phrase in text
        for phrase in [
            "counter target",
            "destroy target",
            "exile target",
            "return target",
            "damage to target",
            "destroy all",
            "all creatures",
            "each creature",
        ]
    )


def format_report(report: DeckValidationReport) -> str:
    lines = [
        f"Deck: {report.deck_name}",
        f"Cards including commander: {report.total_cards}",
        f"Result: {'PASS' if report.ok else 'FAIL'}",
    ]

    if report.role_counts:
        lines.append("Role counts:")
        for role, count in sorted(report.role_counts.items()):
            lines.append(f"- {role}: {count}")

    if report.errors:
        lines.append("Errors:")
        lines.extend(format_issue(issue) for issue in report.errors)
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(format_issue(issue) for issue in report.warnings)
    return "\n".join(lines)


def format_issue(issue: ValidationIssue) -> str:
    card = f" [{issue.card_name}]" if issue.card_name else ""
    return f"- {issue.code}{card}: {issue.message}"


def report_to_dict(report: DeckValidationReport) -> dict:
    return {
        "deck_name": report.deck_name,
        "total_cards": report.total_cards,
        "ok": report.ok,
        "role_counts": report.role_counts,
        "errors": [issue_to_dict(issue) for issue in report.errors],
        "warnings": [issue_to_dict(issue) for issue in report.warnings],
    }


def issue_to_dict(issue: ValidationIssue) -> dict:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "card_name": issue.card_name,
    }


def attach_validation_report(deck: dict, report: DeckValidationReport) -> dict:
    updated = dict(deck)
    refinement = dict(updated.get("refinement", {}))
    refinement["validation_report"] = report_to_dict(report)
    updated["refinement"] = refinement
    return updated
