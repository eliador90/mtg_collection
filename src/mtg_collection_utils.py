from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests


SCRYFALL_COLLECTION_URL = "https://api.scryfall.com/cards/collection"
REQUIRED_MANABOX_COLUMNS = ["Name", "Quantity", "Scryfall ID"]


def read_csv_file(path_text: str) -> pd.DataFrame:
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    return pd.read_csv(path)


def ensure_columns(df: pd.DataFrame, required_columns: Iterable[str]) -> None:
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        joined = ", ".join(missing_columns)
        raise ValueError(f"Missing required columns: {joined}")


def normalize_scryfall_ids(series: pd.Series) -> list[str]:
    cleaned = series.astype(str).str.strip()
    return [value for value in cleaned.dropna().unique().tolist() if value and value.lower() != "nan"]


def flatten_scryfall_card(card: dict) -> dict:
    type_line = card.get("type_line", "") or ""
    legalities = card.get("legalities", {}) or {}
    color_identity = card.get("color_identity", []) or []
    colors = card.get("colors", []) or []
    keywords = card.get("keywords", []) or []
    produced_mana = card.get("produced_mana", []) or []
    prices = card.get("prices", {}) or {}

    return {
        "scryfall_name": card.get("name"),
        "released_at": card.get("released_at"),
        "mana_cost": card.get("mana_cost"),
        "cmc": card.get("cmc"),
        "type_line": type_line,
        "oracle_text": card.get("oracle_text"),
        "power": card.get("power"),
        "toughness": card.get("toughness"),
        "keywords": ", ".join(keywords),
        "colors": ", ".join(colors),
        "color_identity": ", ".join(color_identity),
        "produced_mana": ", ".join(produced_mana),
        "edhrec_rank": card.get("edhrec_rank"),
        "usd_price": prices.get("usd"),
        "usd_foil_price": prices.get("usd_foil"),
        "eur_price": prices.get("eur"),
        "is_legendary": "Legendary" in type_line,
        "is_creature": "Creature" in type_line,
        "is_land": "Land" in type_line,
        "is_artifact": "Artifact" in type_line,
        "is_enchantment": "Enchantment" in type_line,
        "is_instant": "Instant" in type_line,
        "is_sorcery": "Sorcery" in type_line,
        "is_planeswalker": "Planeswalker" in type_line,
        "is_battle": "Battle" in type_line,
        "legal_commander": legalities.get("commander") == "legal",
        "legal_brawl": legalities.get("brawl") == "legal",
        "legal_oathbreaker": legalities.get("oathbreaker") == "legal",
    }


def fetch_scryfall_cards_by_ids(scryfall_ids: list[str], sleep_seconds: float = 0.12) -> dict[str, dict]:
    if not scryfall_ids:
        return {}

    collected_cards: dict[str, dict] = {}
    session = requests.Session()

    for start in range(0, len(scryfall_ids), 75):
        chunk = scryfall_ids[start:start + 75]
        identifiers = [{"id": card_id} for card_id in chunk]
        response = session.post(
            SCRYFALL_COLLECTION_URL,
            json={"identifiers": identifiers},
            timeout=30,
        )
        response.raise_for_status()

        payload = response.json()
        for card in payload.get("data", []):
            collected_cards[card["id"]] = flatten_scryfall_card(card)

        not_found = payload.get("not_found", [])
        if not_found:
            print(f"Warning: {len(not_found)} cards were not found in this Scryfall batch.")

        print(f"Fetched {min(start + 75, len(scryfall_ids))} of {len(scryfall_ids)} unique Scryfall IDs")
        time.sleep(sleep_seconds)

    return collected_cards


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def can_be_commander(type_line: object, oracle_text: object, legal_commander: object) -> bool:
    type_text = "" if pd.isna(type_line) else str(type_line)
    oracle = "" if pd.isna(oracle_text) else str(oracle_text)
    legal = to_bool(legal_commander)

    is_legendary_creature = "Legendary" in type_text and "Creature" in type_text
    text_allows_commander = "can be your commander" in oracle.lower()
    return legal and (is_legendary_creature or text_allows_commander)


def build_commander_candidate_table(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = ["Name", "Quantity", "type_line", "oracle_text", "color_identity", "legal_commander"]
    ensure_columns(df, required_columns)

    working = df.copy()
    working["Quantity"] = pd.to_numeric(working["Quantity"], errors="coerce").fillna(0).astype(int)
    working["candidate_reason"] = working.apply(
        lambda row: _candidate_reason(row.get("type_line"), row.get("oracle_text"), row.get("legal_commander")),
        axis=1,
    )
    candidates = working[working["candidate_reason"] != ""].copy()

    if candidates.empty:
        return pd.DataFrame(
            columns=[
                "card_name",
                "quantity",
                "color_identity",
                "type_line",
                "oracle_text",
                "legal_commander",
                "candidate_reason",
            ]
        )

    grouped = (
        candidates.groupby("Name", as_index=False)
        .agg(
            quantity=("Quantity", "sum"),
            color_identity=("color_identity", "first"),
            type_line=("type_line", "first"),
            oracle_text=("oracle_text", "first"),
            legal_commander=("legal_commander", "first"),
            candidate_reason=("candidate_reason", "first"),
        )
        .rename(columns={"Name": "card_name"})
        .sort_values(["quantity", "card_name"], ascending=[False, True])
    )

    return grouped


def _candidate_reason(type_line: object, oracle_text: object, legal_commander: object) -> str:
    if not to_bool(legal_commander):
        return ""

    type_text = "" if pd.isna(type_line) else str(type_line)
    oracle = "" if pd.isna(oracle_text) else str(oracle_text).lower()

    if "Legendary" in type_text and "Creature" in type_text:
        return "legendary_creature"
    if "can be your commander" in oracle:
        return "rules_text_allows_commander"
    return ""


def split_color_identity(value: object) -> list[str]:
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    parts = [part.strip() for part in text.split(",")]
    return [part for part in parts if part]
