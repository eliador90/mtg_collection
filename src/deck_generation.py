from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from mtg_collection_utils import ensure_columns, read_csv_file, split_color_identity, to_bool


COLOR_ORDER = ["W", "U", "B", "R", "G"]
BASIC_LANDS = {
    "W": "Plains",
    "U": "Island",
    "B": "Swamp",
    "R": "Mountain",
    "G": "Forest",
}
BASIC_LAND_METADATA = {
    "Plains": {"mana_cost": "", "type_line": "Basic Land - Plains", "oracle_text": "({T}: Add {W}.)", "color_identity": ""},
    "Island": {"mana_cost": "", "type_line": "Basic Land - Island", "oracle_text": "({T}: Add {U}.)", "color_identity": ""},
    "Swamp": {"mana_cost": "", "type_line": "Basic Land - Swamp", "oracle_text": "({T}: Add {B}.)", "color_identity": ""},
    "Mountain": {"mana_cost": "", "type_line": "Basic Land - Mountain", "oracle_text": "({T}: Add {R}.)", "color_identity": ""},
    "Forest": {"mana_cost": "", "type_line": "Basic Land - Forest", "oracle_text": "({T}: Add {G}.)", "color_identity": ""},
}
REQUIRED_ENRICHED_COLUMNS = ["Name", "Quantity", "type_line", "oracle_text", "mana_cost", "color_identity"]


@dataclass
class CardCandidate:
    name: str
    quantity: int
    mana_cost: str
    mana_value: float
    type_line: str
    oracle_text: str
    color_identity: list[str]
    produced_mana: list[str]
    legal_commander: bool
    edhrec_rank: float | None
    is_land: bool
    is_basic_land: bool
    primary_role: str = "Utility"
    all_roles: list[str] = field(default_factory=list)
    score: float = 0.0
    theme_hits: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def color_identity_text(self) -> str:
        return ", ".join(self.color_identity)


@dataclass
class DeckGenerationResult:
    deck: dict
    selected_cards: list[CardCandidate]
    maybeboard: list[CardCandidate]
    candidate_pool: list[CardCandidate]


@dataclass
class CommanderProfile:
    name: str
    theme_terms: list[str]
    role_ratios: dict[str, float]
    payoff_mana_value: int = 6


DEFAULT_ROLE_RATIOS = {
    "Ramp": 0.16,
    "Draw / Selection": 0.16,
    "Interaction": 0.19,
    "Synergy Pieces": 0.21,
    "Protection": 0.06,
    "Big Payoffs": 0.14,
}


def generate_local_deck_draft(
    collection_path: str,
    commander_name: str,
    target_size: int = 100,
    land_count: int | None = None,
    theme: str = "",
) -> DeckGenerationResult:
    collection_df = read_collection(collection_path)
    commander = find_commander(collection_df, commander_name)
    commander_colors = set(commander.color_identity)
    profile = build_commander_profile(commander, theme)
    candidate_pool = build_candidate_pool(collection_df, commander, profile)

    target_noncommander = max(target_size - 1, 1)
    chosen_land_count = land_count if land_count is not None else default_land_count(target_size)
    chosen_land_count = min(chosen_land_count, target_noncommander)
    nonland_slots = target_noncommander - chosen_land_count

    nonlands = select_nonlands(candidate_pool, nonland_slots, profile)
    lands = select_lands(candidate_pool, commander_colors, chosen_land_count)
    selected_cards = nonlands + lands
    fill_shortfall_with_basics(selected_cards, commander_colors, target_noncommander)
    selected_names = {card.name for card in selected_cards}
    maybeboard = [card for card in candidate_pool if card.name not in selected_names and not card.is_basic_land][:16]
    actual_land_count = sum(card_count_for_deck(card) for card in selected_cards if card.is_land)

    deck = build_deck_json(
        commander=commander,
        selected_cards=selected_cards,
        maybeboard=maybeboard,
        commander_name=commander_name,
        target_size=target_size,
        land_count=actual_land_count,
        theme=theme,
        profile=profile,
    )
    return DeckGenerationResult(deck=deck, selected_cards=selected_cards, maybeboard=maybeboard, candidate_pool=candidate_pool)


def read_collection(collection_path: str) -> pd.DataFrame:
    df = read_csv_file(collection_path)
    ensure_columns(df, REQUIRED_ENRICHED_COLUMNS)
    working = df.copy()
    working["Quantity"] = pd.to_numeric(working["Quantity"], errors="coerce").fillna(0).astype(int)
    working["cmc"] = pd.to_numeric(working.get("cmc", 0), errors="coerce").fillna(0)
    return working


def find_commander(df: pd.DataFrame, commander_name: str) -> CardCandidate:
    exact = df[df["Name"].astype(str).str.casefold() == commander_name.casefold()]
    if exact.empty:
        contains = df[df["Name"].astype(str).str.contains(re.escape(commander_name), case=False, na=False)]
        if contains.empty:
            raise ValueError(f"Commander not found in collection: {commander_name}")
        exact = contains

    candidates = []
    for _, row in exact.iterrows():
        card = row_to_candidate(row)
        type_text = card.type_line.lower()
        oracle_text = card.oracle_text.lower()
        if ("legendary" in type_text and "creature" in type_text) or "can be your commander" in oracle_text:
            candidates.append(card)

    if not candidates:
        raise ValueError(f"Found {commander_name}, but it does not look like a Commander candidate in the enriched data.")
    return sorted(candidates, key=lambda card: (-card.quantity, card.name))[0]


def build_candidate_pool(df: pd.DataFrame, commander: CardCandidate, profile: CommanderProfile) -> list[CardCandidate]:
    commander_colors = set(commander.color_identity)
    rows = dedupe_collection_rows(df)
    candidates: list[CardCandidate] = []

    for _, row in rows.iterrows():
        card = row_to_candidate(row)
        if card.name == commander.name:
            continue
        if not is_legal_for_commander(card, commander_colors):
            continue
        if not card.legal_commander and not card.is_land:
            continue

        roles = detect_roles(card)
        card.all_roles = roles
        card.primary_role = choose_primary_role(card, roles)
        card.theme_hits = find_theme_hits(card, profile.theme_terms)
        card.score = score_candidate(card, profile)
        card.reason = build_reason(card)
        candidates.append(card)

    return sorted(candidates, key=lambda card: (card.score, -card.mana_value, card.name), reverse=True)


def dedupe_collection_rows(df: pd.DataFrame) -> pd.DataFrame:
    preferred = df.sort_values(["Quantity", "Name"], ascending=[False, True])
    for optional_column in ["produced_mana", "edhrec_rank", "edhrec_rank_x", "edhrec_rank_y"]:
        if optional_column not in preferred.columns:
            preferred[optional_column] = ""
    if "legal_commander" not in preferred.columns:
        preferred["legal_commander"] = True
    grouped = (
        preferred.groupby("Name", as_index=False)
        .agg(
            {
                "Quantity": "sum",
                "mana_cost": "first",
                "cmc": "first",
                "type_line": "first",
                "oracle_text": "first",
                "color_identity": "first",
                "produced_mana": "first",
                "legal_commander": "first",
                "edhrec_rank": "first",
                "edhrec_rank_x": "first",
                "edhrec_rank_y": "first",
            }
        )
    )
    return grouped


def row_to_candidate(row: pd.Series) -> CardCandidate:
    name = clean_text(row.get("Name"))
    type_line = clean_text(row.get("type_line"))
    oracle_text = clean_text(row.get("oracle_text"))
    color_identity = split_color_identity(row.get("color_identity"))
    produced_mana = split_color_identity(row.get("produced_mana")) if "produced_mana" in row.index else []
    legal_commander = to_bool(row.get("legal_commander", True))
    mana_value = float(row.get("cmc", 0) or 0)
    quantity = int(row.get("Quantity", 0) or 0)
    is_land = "Land" in type_line
    is_basic_land = type_line.startswith("Basic Land") or name in BASIC_LAND_METADATA

    return CardCandidate(
        name=name,
        quantity=quantity,
        mana_cost=clean_text(row.get("mana_cost")),
        mana_value=mana_value,
        type_line=type_line,
        oracle_text=oracle_text,
        color_identity=color_identity,
        produced_mana=produced_mana,
        legal_commander=legal_commander,
        edhrec_rank=extract_rank(row),
        is_land=is_land,
        is_basic_land=is_basic_land,
    )


def extract_rank(row: pd.Series) -> float | None:
    for column in ["edhrec_rank", "edhrec_rank_x", "edhrec_rank_y"]:
        if column not in row.index:
            continue
        value = pd.to_numeric(row.get(column), errors="coerce")
        if not pd.isna(value) and float(value) > 0:
            return float(value)
    return None


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def is_legal_for_commander(card: CardCandidate, commander_colors: set[str]) -> bool:
    return set(card.color_identity).issubset(commander_colors)


def build_commander_profile(commander: CardCandidate, theme: str = "") -> CommanderProfile:
    terms = derive_theme_terms(commander, theme)
    text = f"{commander.name} {commander.oracle_text} {theme}".lower()
    ratios = dict(DEFAULT_ROLE_RATIOS)
    payoff_mana_value = 6

    if "suspend" in text or "without paying" in text or "time counter" in text:
        ratios.update(
            {
                "Ramp": 0.15,
                "Draw / Selection": 0.15,
                "Interaction": 0.16,
                "Synergy Pieces": 0.22,
                "Protection": 0.05,
                "Big Payoffs": 0.18,
            }
        )
        payoff_mana_value = 7
    elif "opponent's turn" in text or "flash" in terms:
        ratios.update(
            {
                "Ramp": 0.14,
                "Draw / Selection": 0.18,
                "Interaction": 0.24,
                "Synergy Pieces": 0.22,
                "Protection": 0.06,
                "Big Payoffs": 0.08,
            }
        )
    elif "token" in terms or "creatures you control" in text:
        ratios.update(
            {
                "Ramp": 0.15,
                "Draw / Selection": 0.15,
                "Interaction": 0.16,
                "Synergy Pieces": 0.27,
                "Protection": 0.07,
                "Big Payoffs": 0.10,
            }
        )

    return CommanderProfile(
        name=commander.name,
        theme_terms=terms,
        role_ratios=ratios,
        payoff_mana_value=payoff_mana_value,
    )


def derive_theme_terms(commander: CardCandidate, theme: str) -> list[str]:
    text = f"{commander.name} {commander.type_line} {commander.oracle_text} {theme}".lower()
    terms = []
    for raw_term in [
        "artifact",
        "enchantment",
        "equipment",
        "instant",
        "sorcery",
        "graveyard",
        "token",
        "draw",
        "discard",
        "sacrifice",
        "time counter",
        "suspend",
        "flash",
        "faerie",
        "rogue",
        "wizard",
        "dragon",
        "zombie",
        "elf",
        "angel",
        "vampire",
        "spirit",
    ]:
        if raw_term in text and raw_term not in terms:
            terms.append(raw_term)

    if "without paying" in text:
        terms.extend(["expensive", "big spell", "suspend"])
    if "counter target" in text:
        terms.append("counter target")
    if "each opponent" in text or "opponent's turn" in text:
        terms.extend(["instant", "flash", "counter"])

    return list(dict.fromkeys(terms))


def detect_roles(card: CardCandidate) -> list[str]:
    text = f"{card.name} {card.type_line} {card.oracle_text}".lower()
    roles = []
    if card.is_land:
        roles.append("Lands")
    if is_ramp_text(text, card):
        roles.append("Ramp")
    if is_draw_text(text):
        roles.append("Draw / Selection")
    if is_interaction_text(text):
        roles.append("Interaction")
    if is_protection_text(text):
        roles.append("Protection")
    if is_payoff(card, text):
        roles.append("Big Payoffs")
    if is_synergy_text(text):
        roles.append("Synergy Pieces")
    if not roles:
        roles.append("Utility")
    return roles


def is_ramp_text(text: str, card: CardCandidate) -> bool:
    if card.is_land:
        return False
    name = card.name.lower()
    is_mana_artifact = (
        "artifact" in card.type_line.lower()
        and any(fragment in name for fragment in ["signet", "talisman", "sol ring", "mind stone", "diamond", "keyrune", "locket"])
    )
    if is_mana_artifact:
        return True
    return any(
        phrase in text
        for phrase in [
            "add {",
            "add one mana",
            "add two mana",
            "search your library for a basic land",
            "spells you cast cost",
            "treasure token",
        ]
    )


def is_draw_text(text: str) -> bool:
    return any(phrase in text for phrase in ["draw a card", "draw two", "draw three", "scry", "surveil", "look at the top", "discard a card"])


def is_interaction_text(text: str) -> bool:
    return any(
        phrase in text
        for phrase in [
            "counter target",
            "destroy target",
            "exile target",
            "return target",
            "deals ",
            "damage to target",
            "tap target",
            "can't attack",
            "can't block",
            "sacrifice a creature",
            "destroy all",
            "each creature",
            "each player",
            "all creatures",
            "all lands",
        ]
    )


def is_protection_text(text: str) -> bool:
    return any(phrase in text for phrase in ["hexproof", "indestructible", "protection from", "prevent", "phase out", "can't be countered"])


def is_payoff(card: CardCandidate, text: str) -> bool:
    return card.mana_value >= 6 or any(phrase in text for phrase in ["you win the game", "extra turn", "take an extra turn", "double"])


def is_synergy_text(text: str) -> bool:
    return any(
        phrase in text
        for phrase in [
            "whenever you cast",
            "whenever a creature",
            "whenever one or more",
            "time counter",
            "suspend",
            "proliferate",
            "token",
            "copy target",
            "artifact you control",
            "enchantment you control",
            "creatures you control",
            "graveyard",
        ]
    )


def choose_primary_role(card: CardCandidate, roles: list[str]) -> str:
    if card.is_land:
        return "Lands"
    if "Big Payoffs" in roles and card.mana_value >= 8:
        return "Big Payoffs"
    for role in ["Ramp", "Draw / Selection", "Interaction", "Synergy Pieces", "Protection", "Big Payoffs", "Utility"]:
        if role in roles:
            return role
    return roles[0]


def find_theme_hits(card: CardCandidate, theme_terms: list[str]) -> list[str]:
    text = f"{card.name} {card.type_line} {card.oracle_text}".lower()
    hits = []
    for term in theme_terms:
        if term in {"expensive", "big spell"}:
            if card.mana_value >= 6:
                hits.append(term)
        elif term in text:
            hits.append(term)
    return hits[:5]


def score_candidate(card: CardCandidate, profile: CommanderProfile) -> float:
    score = 10.0
    score += min(card.quantity, 4) * 0.5
    score += len(card.theme_hits) * 5
    score += role_score(card)

    if card.edhrec_rank:
        score += max(0.0, 12.0 - math.log10(card.edhrec_rank + 1) * 3)

    if card.primary_role in {"Ramp", "Draw / Selection", "Interaction"}:
        score += max(0.0, 5.0 - card.mana_value)
    if card.primary_role == "Big Payoffs":
        score += min(card.mana_value, 10.0) * 0.9
        if card.mana_value >= profile.payoff_mana_value:
            score += 4.0
    if card.is_land:
        score += 2.0
        if set(card.produced_mana) & set(COLOR_ORDER):
            score += 2.0
    score += curve_bonus(card)

    return round(score, 3)


def curve_bonus(card: CardCandidate) -> float:
    if card.is_land:
        return 0.0
    if card.primary_role == "Ramp":
        return max(0.0, 4.0 - card.mana_value)
    if card.primary_role in {"Draw / Selection", "Interaction", "Protection"}:
        return max(0.0, 5.0 - card.mana_value) * 0.7
    if card.primary_role == "Synergy Pieces":
        return max(0.0, 6.0 - abs(card.mana_value - 3.0))
    return 0.0


def role_score(card: CardCandidate) -> float:
    role_weights = {
        "Ramp": 7.0,
        "Draw / Selection": 6.5,
        "Interaction": 6.0,
        "Synergy Pieces": 7.5,
        "Protection": 5.0,
        "Big Payoffs": 5.0,
        "Lands": 4.0,
        "Utility": 2.0,
    }
    return sum(role_weights.get(role, 0.0) for role in card.all_roles[:3])


def build_reason(card: CardCandidate) -> str:
    role_reasons = {
        "Ramp": "helps the deck start faster or cast follow-up spells sooner",
        "Draw / Selection": "keeps cards flowing and smooths awkward hands",
        "Interaction": "answers opposing threats while the deck sets up",
        "Synergy Pieces": "matches the commander's main themes",
        "Protection": "helps protect key cards or stabilize the board",
        "Big Payoffs": "gives the deck a high-impact card to build toward",
        "Lands": "supports the mana base",
        "Utility": "adds flexible support to the shell",
    }
    reason = role_reasons.get(card.primary_role, "supports the deck plan")
    if card.theme_hits:
        reason += f"; theme matches: {', '.join(card.theme_hits)}"
    return reason + "."


def default_land_count(target_size: int) -> int:
    if target_size >= 90:
        return 37
    return max(1, round((target_size - 1) * 0.37))


def select_nonlands(candidates: list[CardCandidate], slots: int, profile: CommanderProfile) -> list[CardCandidate]:
    role_targets = build_role_targets(slots, profile)
    selected: list[CardCandidate] = []
    selected_names: set[str] = set()

    for role, target in role_targets.items():
        role_candidates = [
            card
            for card in candidates
            if not card.is_land and card.name not in selected_names and role in card.all_roles and fits_role_budget(card, role)
        ]
        role_candidates = sorted(role_candidates, key=lambda card: role_sort_key(card, role))
        for card in role_candidates[:target]:
            card.primary_role = role
            selected.append(card)
            selected_names.add(card.name)

    if len(selected) < slots:
        fill = [
            card
            for card in candidates
            if not card.is_land and card.name not in selected_names and not (card.mana_value >= 6 and "Big Payoffs" in card.all_roles)
        ]
        if len(fill) < slots - len(selected):
            fill.extend([card for card in candidates if not card.is_land and card.name not in selected_names and card not in fill])
        for card in fill[: slots - len(selected)]:
            selected.append(card)
            selected_names.add(card.name)

    return selected[:slots]


def fits_role_budget(card: CardCandidate, role: str) -> bool:
    if role == "Big Payoffs":
        return True
    return not (card.mana_value >= 6 and "Big Payoffs" in card.all_roles)


def role_sort_key(card: CardCandidate, role: str) -> tuple[float, float, str]:
    if role == "Big Payoffs":
        return (-card.score, -card.mana_value, card.name)
    if role in {"Ramp", "Draw / Selection", "Interaction"}:
        return (-card.score, card.mana_value, card.name)
    return (-card.score, abs(card.mana_value - 3), card.name)


def build_role_targets(slots: int, profile: CommanderProfile) -> dict[str, int]:
    targets = {role: max(1, round(slots * ratio)) for role, ratio in profile.role_ratios.items()}
    assigned = sum(targets.values())
    targets["Utility"] = max(0, slots - assigned)
    return targets


def select_lands(candidates: list[CardCandidate], commander_colors: set[str], land_slots: int) -> list[CardCandidate]:
    selected: list[CardCandidate] = []
    selected_names: set[str] = set()
    nonbasic_lands = sorted(
        [card for card in candidates if card.is_land and not card.is_basic_land],
        key=lambda card: land_sort_key(card, commander_colors),
    )
    for land in nonbasic_lands:
        if len(selected) >= land_slots:
            break
        selected.append(land)
        selected_names.add(land.name)

    basics_needed = land_slots - len(selected)
    if basics_needed <= 0:
        return selected

    basic_counts = distribute_basic_lands(commander_colors, basics_needed)
    existing_basics = {card.name: card for card in candidates if card.is_basic_land}
    for basic_name, count in basic_counts.items():
        if count <= 0:
            continue
        basic = existing_basics.get(basic_name) or synthetic_basic_land(basic_name)
        basic.quantity = max(basic.quantity, count)
        basic.primary_role = "Lands"
        basic.all_roles = ["Lands"]
        basic.score = 10
        selected.append(basic)
        selected_names.add(basic.name)

    return selected


def land_sort_key(card: CardCandidate, commander_colors: set[str]) -> tuple[int, float, str]:
    produced = set(card.produced_mana)
    fixing_score = len(produced & commander_colors)
    if "any color" in card.oracle_text.lower():
        fixing_score += len(commander_colors)
    tapped_penalty = 1 if "enters tapped" in card.oracle_text.lower() else 0
    return (-fixing_score, tapped_penalty, -card.score, card.name)


def fill_shortfall_with_basics(selected_cards: list[CardCandidate], commander_colors: set[str], target_count: int) -> None:
    current_count = sum(card_count_for_deck(card) for card in selected_cards)
    shortfall = target_count - current_count
    if shortfall <= 0:
        return

    basic_counts = distribute_basic_lands(commander_colors, shortfall)
    for basic_name, count in basic_counts.items():
        existing = next((card for card in selected_cards if card.name == basic_name), None)
        if existing:
            existing.quantity += count
        else:
            basic = synthetic_basic_land(basic_name)
            basic.quantity = count
            selected_cards.append(basic)


def distribute_basic_lands(commander_colors: set[str], count: int) -> dict[str, int]:
    colors = [color for color in COLOR_ORDER if color in commander_colors]
    if not colors:
        return {}
    counts = {BASIC_LANDS[color]: 0 for color in colors}
    for index in range(count):
        basic_name = BASIC_LANDS[colors[index % len(colors)]]
        counts[basic_name] += 1
    return counts


def synthetic_basic_land(name: str) -> CardCandidate:
    metadata = BASIC_LAND_METADATA[name]
    return CardCandidate(
        name=name,
        quantity=0,
        mana_cost=metadata["mana_cost"],
        mana_value=0,
        type_line=metadata["type_line"],
        oracle_text=metadata["oracle_text"],
        color_identity=[],
        produced_mana=[],
        legal_commander=True,
        edhrec_rank=None,
        is_land=True,
        is_basic_land=True,
        primary_role="Lands",
        all_roles=["Lands"],
        reason="fills out the basic mana base.",
    )


def build_deck_json(
    commander: CardCandidate,
    selected_cards: list[CardCandidate],
    maybeboard: list[CardCandidate],
    commander_name: str,
    target_size: int,
    land_count: int,
    theme: str,
    profile: CommanderProfile,
) -> dict:
    cards_json = []
    for card in selected_cards:
        entry = {"name": card.name, "category": card.primary_role}
        count = card_count_for_deck(card)
        if count > 1:
            entry["count"] = count
        if card.name in BASIC_LAND_METADATA:
            entry.update(BASIC_LAND_METADATA[card.name])
        cards_json.append(entry)

    quality = build_quality_summary(selected_cards, target_size)

    return {
        "name": f"{commander.name} - Local Collection Draft",
        "commander": {
            "name": commander.name,
            "category": "Commander",
            "mana_cost": commander.mana_cost,
            "type_line": commander.type_line,
            "oracle_text": commander.oracle_text,
            "color_identity": commander.color_identity_text,
        },
        "generation": {
            "method": "local_heuristic",
            "commander_requested": commander_name,
            "target_size": target_size,
            "land_count": land_count,
            "theme": theme,
            "profile": {
                "theme_terms": profile.theme_terms,
                "role_ratios": profile.role_ratios,
                "payoff_mana_value": profile.payoff_mana_value,
            },
            "quality": quality,
            "notes": [
                "This is a free rules-based first draft, not a tuned final deck.",
                "Use the maybeboard and AI prompt export to refine the deck manually or with an assistant.",
            ],
        },
        "refinement": {
            "maybeboard": [{"name": card.name, "reason": card.reason} for card in maybeboard[:10]],
            "quality_notes": [
                {
                    "name": "Draft quality score",
                    "reason": f"{quality['score']}/100 - {quality['grade']}.",
                },
                *[{"name": note["name"], "reason": note["reason"]} for note in quality["notes"]],
            ],
            "cut_candidates": [
                {"name": card.name, "reason": "Lower local score than the rest of the selected shell; review after goldfishing."}
                for card in sorted(selected_cards, key=lambda entry: entry.score)[:8]
                if not card.is_basic_land
            ],
            "upgrade_suggestions": [],
        },
        "cards": cards_json,
    }


def build_quality_summary(selected_cards: list[CardCandidate], target_size: int) -> dict:
    role_counts: dict[str, int] = {}
    curve_counts = {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6+": 0}
    land_count = 0
    nonland_count = 0
    ramp_count = 0
    draw_count = 0
    interaction_count = 0
    high_mana_count = 0

    for card in selected_cards:
        count = card_count_for_deck(card)
        role_counts[card.primary_role] = role_counts.get(card.primary_role, 0) + count
        if card.is_land:
            land_count += count
            continue

        nonland_count += count
        if card.primary_role == "Ramp":
            ramp_count += count
        if card.primary_role == "Draw / Selection":
            draw_count += count
        if card.primary_role == "Interaction":
            interaction_count += count
        if card.mana_value >= 6:
            high_mana_count += count

        curve_key = "6+" if card.mana_value >= 6 else str(int(max(card.mana_value, 0)))
        curve_counts[curve_key] = curve_counts.get(curve_key, 0) + count

    notes = []
    quality_score = 100
    if target_size >= 90:
        if land_count < 35:
            notes.append({"name": "Land count", "reason": f"{land_count} lands is lean for Commander; review mana consistency."})
            quality_score -= (35 - land_count) * 4
        if land_count > 41:
            notes.append({"name": "Land count", "reason": f"{land_count} lands is high for many Commander decks; review whether the deck floods."})
            quality_score -= (land_count - 41) * 3
        if ramp_count < 8:
            notes.append({"name": "Ramp count", "reason": f"{ramp_count} ramp/fixing cards may be low for a 100-card deck."})
            quality_score -= (8 - ramp_count) * 4
        if draw_count < 8:
            notes.append({"name": "Card flow", "reason": f"{draw_count} draw/selection cards may leave the deck short on reloads."})
            quality_score -= (8 - draw_count) * 4
        if interaction_count < 8:
            notes.append({"name": "Interaction", "reason": f"{interaction_count} interaction cards may be light for multiplayer Commander."})
            quality_score -= (8 - interaction_count) * 3
        if high_mana_count > 14:
            notes.append({"name": "Mana curve", "reason": f"{high_mana_count} nonland cards cost 6 or more; hands may become clunky."})
            quality_score -= (high_mana_count - 14) * 3

    if not notes:
        notes.append({"name": "First-pass shape", "reason": "The draft cleared the basic local shape checks; tune by playtesting and table power level."})

    quality_score = max(0, min(100, quality_score))
    return {
        "score": quality_score,
        "grade": quality_grade(quality_score),
        "role_counts": role_counts,
        "mana_curve": curve_counts,
        "land_count": land_count,
        "nonland_count": nonland_count,
        "ramp_count": ramp_count,
        "draw_selection_count": draw_count,
        "interaction_count": interaction_count,
        "high_mana_value_count": high_mana_count,
        "notes": notes,
    }


def quality_grade(score: int) -> str:
    if score >= 85:
        return "strong first draft"
    if score >= 70:
        return "promising first draft"
    if score >= 50:
        return "needs review"
    return "rough draft"


def card_count_for_deck(card: CardCandidate) -> int:
    if card.is_basic_land:
        return max(1, card.quantity)
    return 1


def write_deck_json(deck: dict, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(deck, indent=2), encoding="utf-8")


def write_ai_prompt(result: DeckGenerationResult, output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_ai_prompt(result)
    path.write_text(prompt, encoding="utf-8")


def build_ai_prompt(result: DeckGenerationResult) -> str:
    deck = result.deck
    commander = deck["commander"]
    candidates_by_role = group_candidates_for_prompt(result.candidate_pool)
    selected_json = json.dumps(deck, indent=2)
    role_blocks = []
    for role, cards in candidates_by_role.items():
        lines = [f"- {card.name}: {card.reason}" for card in cards[:18]]
        role_blocks.append(f"## {role}\n" + "\n".join(lines))

    return f"""You are helping refine a Magic: The Gathering Commander deck from a local collection.

Commander:
- Name: {commander["name"]}
- Mana cost: {commander.get("mana_cost", "")}
- Type: {commander.get("type_line", "")}
- Color identity: {commander.get("color_identity", "")}
- Rules text: {commander.get("oracle_text", "")}

Task:
Refine the draft deck below using only cards from the candidate pool unless you explicitly put outside cards in upgrade_suggestions.
Return JSON in the same deck format. Keep the commander legal, keep Commander color identity legal, and explain important changes in refinement.

Current local draft JSON:
```json
{selected_json}
```

Candidate pool from the user's collection:
{chr(10).join(role_blocks)}
"""


def group_candidates_for_prompt(candidates: list[CardCandidate]) -> dict[str, list[CardCandidate]]:
    grouped: dict[str, list[CardCandidate]] = {}
    for card in candidates:
        grouped.setdefault(card.primary_role, []).append(card)
    return grouped


def summarize_result(result: DeckGenerationResult) -> str:
    deck = result.deck
    total_cards = 1
    role_counts: dict[str, int] = {}
    for card in deck["cards"]:
        count = int(card.get("count", 1))
        total_cards += count
        role_counts[card["category"]] = role_counts.get(card["category"], 0) + count

    lines = [
        f"Created {deck['name']}",
        f"Total cards including commander: {total_cards}",
        "Role counts:",
    ]
    for role, count in sorted(role_counts.items(), key=lambda item: item[0]):
        lines.append(f"- {role}: {count}")
    return "\n".join(lines)
