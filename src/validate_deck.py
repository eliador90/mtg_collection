from __future__ import annotations

import argparse
import sys

from deck_validation import format_report, validate_deck


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Commander deck JSON against an enriched collection CSV.")
    parser.add_argument("--deck", required=True, help="Path to a deck JSON file.")
    parser.add_argument("--collection", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument(
        "--target-size",
        type=int,
        default=100,
        help="Expected deck size including commander. Defaults to 100.",
    )
    parser.add_argument("--min-lands", type=int, default=33, help="Warn below this land count. Defaults to 33.")
    parser.add_argument("--max-lands", type=int, default=42, help="Warn above this land count. Defaults to 42.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_deck(
        deck_path=args.deck,
        collection_path=args.collection,
        target_size=args.target_size,
        min_lands=args.min_lands,
        max_lands=args.max_lands,
    )
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
