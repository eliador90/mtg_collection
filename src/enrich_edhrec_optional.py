from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from mtg_collection_utils import build_commander_candidate_table, read_csv_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optionally enrich commander candidates with EDHREC data."
    )
    parser.add_argument("--input", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output", required=True, help="Path for the EDHREC-enriched CSV.")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of commander candidates to query from EDHREC.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.5,
        help="Delay between EDHREC requests.",
    )
    return parser.parse_args()


def safe_edhrec_fields(commander_name: str) -> dict:
    try:
        from pyedhrec import EDHRec
    except Exception:
        return {
            "edhrec_commander_found": False,
            "edhrec_deck_count": None,
            "edhrec_rank": None,
            "edhrec_salt": None,
            "edhrec_high_synergy_top30": None,
            "edhrec_average_deck_top100": None,
            "edhrec_error": "pyedhrec not installed",
        }

    try:
        client = EDHRec()
        details = client.get_commander_data(commander_name)
        high_synergy = client.get_high_synergy_cards(commander_name)
        average_deck = client.get_commanders_average_deck(commander_name)

        return {
            "edhrec_commander_found": True,
            "edhrec_deck_count": _extract_detail_value(details, ["num_decks", "deck_count", "decks"]),
            "edhrec_rank": _extract_detail_value(details, ["rank"]),
            "edhrec_salt": _extract_detail_value(details, ["salt", "salt_score"]),
            "edhrec_high_synergy_top30": " | ".join(_extract_card_names(high_synergy, 30)),
            "edhrec_average_deck_top100": " | ".join(_extract_card_names(average_deck, 100)),
            "edhrec_error": None,
        }
    except Exception as exc:
        return {
            "edhrec_commander_found": False,
            "edhrec_deck_count": None,
            "edhrec_rank": None,
            "edhrec_salt": None,
            "edhrec_high_synergy_top30": None,
            "edhrec_average_deck_top100": None,
            "edhrec_error": str(exc),
        }


def _extract_detail_value(details: object, keys: list[str]) -> object:
    if not isinstance(details, dict):
        return None
    for key in keys:
        if key in details:
            return details[key]
    return None


def _extract_card_names(items: object, limit: int) -> list[str]:
    if not isinstance(items, list):
        return []

    names: list[str] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            name = item.get("name") or item.get("label")
        else:
            name = str(item)
        if name:
            names.append(str(name))
    return names


def main() -> None:
    args = parse_args()

    print(f"Reading input file: {args.input}")
    enriched_df = read_csv_file(args.input)
    candidate_df = build_commander_candidate_table(enriched_df).head(args.limit)

    if candidate_df.empty:
        print("No commander candidates were found. Saving a copy of the input file.")
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        enriched_df.to_csv(output_path, index=False)
        print(f"Saved CSV to: {output_path}")
        return

    print(f"Querying EDHREC for up to {len(candidate_df)} commander candidates")
    edhrec_rows = []
    for _, row in candidate_df.iterrows():
        name = row["card_name"]
        edhrec_rows.append({"Name": name, **safe_edhrec_fields(name)})
        print(f"Processed EDHREC data for: {name}")
        time.sleep(args.sleep_seconds)

    edhrec_df = pd.DataFrame(edhrec_rows)
    merged_df = enriched_df.merge(edhrec_df, on="Name", how="left")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(output_path, index=False)

    print("EDHREC enrichment is optional and best-effort.")
    print(f"Saved CSV to: {output_path}")


if __name__ == "__main__":
    main()

