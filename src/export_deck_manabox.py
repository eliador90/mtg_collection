from __future__ import annotations

import argparse

from deck_io import export_deck_to_manabox_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a deck JSON to a ManaBox-style CSV.")
    parser.add_argument("--deck", required=True, help="Path to a deck JSON file.")
    parser.add_argument("--output", required=True, help="Path for the exported CSV.")
    parser.add_argument(
        "--collection",
        default="",
        help="Optional enriched collection CSV. Used to include Scryfall IDs when available.",
    )
    parser.add_argument(
        "--no-commander",
        action="store_true",
        help="Do not include the commander row in the exported CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_deck_to_manabox_csv(
        deck_path=args.deck,
        output_path=args.output,
        collection_path=args.collection,
        include_commander=not args.no_commander,
    )
    print(f"Saved ManaBox-style CSV to: {args.output}")


if __name__ == "__main__":
    main()
