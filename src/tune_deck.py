from __future__ import annotations

import argparse

from deck_tuning import format_tuning_report, tune_deck


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest reviewable tuning swaps for an existing deck JSON.")
    parser.add_argument("--deck", required=True, help="Path to a deck JSON file.")
    parser.add_argument("--collection", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output", default="", help="Optional path for a JSON tuning report.")
    parser.add_argument("--max-suggestions", type=int, default=10, help="Maximum number of swaps to suggest.")
    parser.add_argument("--theme", default="", help="Optional theme hint to guide scoring.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = tune_deck(
        deck_path=args.deck,
        collection_path=args.collection,
        output_path=args.output,
        max_suggestions=args.max_suggestions,
        theme=args.theme,
    )
    print(format_tuning_report(report))
    if args.output:
        print(f"Saved tuning report to: {args.output}")


if __name__ == "__main__":
    main()
