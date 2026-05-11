from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from deck_generation import (
    CardCandidate,
    build_candidate_pool,
    build_commander_profile,
    choose_primary_role,
    clean_text,
    dedupe_collection_rows,
    detect_roles,
    find_commander,
    find_theme_hits,
    read_collection,
    row_to_candidate,
    score_candidate,
)
from deck_io import deck_entry_map, load_deck_json
from deck_validation import validate_deck


ROLE_WARNING_MAP = {
    "low_ramp_count": "Ramp",
    "low_draw_count": "Draw / Selection",
    "low_interaction_count": "Interaction",
}


def tune_deck(
    deck_path: str,
    collection_path: str,
    output_path: str = "",
    max_suggestions: int = 10,
    theme: str = "",
) -> dict:
    deck = load_deck_json(deck_path)
    collection_df = read_collection(collection_path)
    commander_name = clean_text(deck.get("commander", {}).get("name"))
    commander = find_commander(collection_df, commander_name)
    profile = build_commander_profile(commander, theme or clean_text(deck.get("generation", {}).get("theme")))
    candidate_pool = build_candidate_pool(collection_df, commander, profile)
    deck_map = deck_entry_map(deck, include_commander=False)
    current_candidates = build_current_candidate_map(collection_df, deck_map, profile)
    target_size, min_lands, max_lands = infer_validation_settings(deck)
    validation = validate_deck(deck_path, collection_path, target_size=target_size, min_lands=min_lands, max_lands=max_lands)

    roles_needed = roles_from_validation(validation)
    suggestions = []
    used_adds: set[str] = set()
    used_cuts: set[str] = set()

    for role in roles_needed:
        add_candidates = [
            card for card in candidate_pool if role in card.all_roles and card.name not in deck_map and card.name not in used_adds
        ]
        cut_candidates = choose_cut_candidates(current_candidates, preferred_cut_role=None, used_cuts=used_cuts)
        suggestions.extend(pair_suggestions(role, add_candidates, cut_candidates, used_adds, used_cuts, max_suggestions - len(suggestions)))
        if len(suggestions) >= max_suggestions:
            break

    if len(suggestions) < max_suggestions:
        add_candidates = [card for card in candidate_pool if card.name not in deck_map and card.name not in used_adds]
        cut_candidates = choose_cut_candidates(current_candidates, preferred_cut_role="Big Payoffs", used_cuts=used_cuts)
        suggestions.extend(pair_suggestions("General upgrade", add_candidates, cut_candidates, used_adds, used_cuts, max_suggestions - len(suggestions)))

    report = {
        "deck_name": deck.get("name", Path(deck_path).stem),
        "commander": commander_name,
        "validation_ok": validation.ok,
        "validation_warnings": [{"code": issue.code, "message": issue.message} for issue in validation.warnings],
        "suggestions": suggestions[:max_suggestions],
    }

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def attach_tuning_report(deck_path: str, report: dict) -> dict:
    deck = load_deck_json(deck_path)
    updated = dict(deck)
    refinement = dict(updated.get("refinement", {}))
    suggestions = report.get("suggestions", [])
    refinement["upgrade_suggestions"] = suggestions
    refinement["tuning_report"] = {
        "validation_ok": report.get("validation_ok", False),
        "validation_warnings": report.get("validation_warnings", []),
        "suggestion_count": len(suggestions),
    }
    updated["refinement"] = refinement

    path = Path(deck_path)
    path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    return updated


def infer_validation_settings(deck: dict) -> tuple[int, int, int]:
    generation = deck.get("generation", {})
    target_size = parse_positive_int(generation.get("target_size"), default=100)
    if target_size >= 90:
        return target_size, 33, 42
    return target_size, 1, max(target_size - 1, 1)


def parse_positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def roles_from_validation(validation) -> list[str]:
    roles = []
    for warning in validation.warnings:
        role = ROLE_WARNING_MAP.get(warning.code)
        if role and role not in roles:
            roles.append(role)
    if not roles:
        roles.extend(["Ramp", "Draw / Selection", "Interaction", "Synergy Pieces"])
    return roles


def build_current_candidate_map(collection_df: pd.DataFrame, deck_map: dict[str, dict], profile) -> dict[str, CardCandidate]:
    current = {}
    for _, row in dedupe_collection_rows(collection_df).iterrows():
        card = row_to_candidate(row)
        if card.name not in deck_map:
            continue
        roles = detect_roles(card)
        card.all_roles = roles
        card.primary_role = deck_map[card.name].get("category") or choose_primary_role(card, roles)
        card.theme_hits = find_theme_hits(card, profile.theme_terms)
        card.score = score_candidate(card, profile)
        current[card.name] = card
    return current


def choose_cut_candidates(current_candidates: dict[str, CardCandidate], preferred_cut_role: str | None, used_cuts: set[str]) -> list[CardCandidate]:
    candidates = [card for card in current_candidates.values() if card.name not in used_cuts and not card.is_basic_land and not card.is_land]
    if preferred_cut_role:
        preferred = [card for card in candidates if card.primary_role == preferred_cut_role or preferred_cut_role in card.all_roles]
        if preferred:
            candidates = preferred
    return sorted(candidates, key=lambda card: (card.score, -card.mana_value, card.name))


def pair_suggestions(
    reason_role: str,
    add_candidates: list[CardCandidate],
    cut_candidates: list[CardCandidate],
    used_adds: set[str],
    used_cuts: set[str],
    limit: int,
) -> list[dict]:
    suggestions = []
    for add_card in add_candidates:
        if len(suggestions) >= limit:
            break
        cut_card = next((card for card in cut_candidates if card.name not in used_cuts), None)
        if not cut_card:
            break
        used_adds.add(add_card.name)
        used_cuts.add(cut_card.name)
        suggestions.append(
            {
                "cut": cut_card.name,
                "add": add_card.name,
                "reason": build_tuning_reason(reason_role, cut_card, add_card),
                "add_role": add_card.primary_role,
                "cut_role": cut_card.primary_role,
                "add_score": add_card.score,
                "cut_score": cut_card.score,
            }
        )
    return suggestions


def build_tuning_reason(reason_role: str, cut_card: CardCandidate, add_card: CardCandidate) -> str:
    if reason_role == "General upgrade":
        return (
            f"{add_card.name} has a stronger local fit score than {cut_card.name} "
            f"and appears to better support the deck's current plan."
        )
    return (
        f"The validator or deck-shape checks suggest the deck could use more {reason_role.lower()}. "
        f"{add_card.name} fills that role better than this lower-scoring {cut_card.primary_role.lower()} slot."
    )


def format_tuning_report(report: dict) -> str:
    lines = [
        f"Deck: {report['deck_name']}",
        f"Commander: {report['commander']}",
        f"Validation: {'PASS' if report['validation_ok'] else 'HAS ERRORS'}",
    ]
    if report["validation_warnings"]:
        lines.append("Validation warnings considered:")
        for warning in report["validation_warnings"]:
            lines.append(f"- {warning['code']}: {warning['message']}")

    suggestions = report.get("suggestions", [])
    if not suggestions:
        lines.append("No tuning suggestions found.")
        return "\n".join(lines)

    lines.append("Suggested swaps:")
    for item in suggestions:
        lines.append(f"- Cut {item['cut']} -> Add {item['add']}: {item['reason']}")
    return "\n".join(lines)
