from __future__ import annotations

import argparse
from pathlib import Path

from mtg_collection_utils import build_commander_candidate_table, read_csv_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify likely commander candidates from an enriched collection CSV."
    )
    parser.add_argument("--input", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output", required=True, help="Path for the commander candidate CSV.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(f"Reading input file: {args.input}")
    enriched_df = read_csv_file(args.input)
    commander_df = build_commander_candidate_table(enriched_df)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    commander_df.to_csv(output_path, index=False)

    print(f"Found {len(commander_df)} commander candidates")
    print(f"Saved commander candidate CSV to: {output_path}")


if __name__ == "__main__":
    main()

