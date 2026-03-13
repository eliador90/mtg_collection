from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from mtg_collection_utils import (
    REQUIRED_MANABOX_COLUMNS,
    ensure_columns,
    fetch_scryfall_cards_by_ids,
    normalize_scryfall_ids,
    read_csv_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read a ManaBox CSV and enrich it with Scryfall metadata."
    )
    parser.add_argument("--input", required=True, help="Path to the ManaBox CSV file.")
    parser.add_argument("--output", required=True, help="Path for the enriched CSV file.")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.12,
        help="Delay between Scryfall API batches to stay polite.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Reading input file: {args.input}")
    collection_df = read_csv_file(args.input)
    ensure_columns(collection_df, REQUIRED_MANABOX_COLUMNS)

    unique_ids = normalize_scryfall_ids(collection_df["Scryfall ID"])
    print(f"Loaded {len(collection_df)} rows")
    print(f"Found {len(unique_ids)} unique Scryfall IDs")

    scryfall_lookup = fetch_scryfall_cards_by_ids(unique_ids, sleep_seconds=args.sleep_seconds)
    scryfall_df = pd.DataFrame(
        [{"Scryfall ID": scryfall_id, **metadata} for scryfall_id, metadata in scryfall_lookup.items()]
    )

    enriched_df = collection_df.merge(scryfall_df, on="Scryfall ID", how="left")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.to_csv(output_path, index=False)

    matched_rows = int(enriched_df["scryfall_name"].notna().sum()) if "scryfall_name" in enriched_df else 0
    print(f"Matched Scryfall metadata for {matched_rows} rows")
    print(f"Saved enriched CSV to: {output_path}")


if __name__ == "__main__":
    main()

