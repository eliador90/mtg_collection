from __future__ import annotations

import argparse

from deck_io import import_manabox_deck_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a ManaBox-style deck CSV into the project's deck JSON format.")
    parser.add_argument("--input", required=True, help="Path to a ManaBox-style deck CSV.")
    parser.add_argument("--commander", required=True, help="Commander name for the imported deck.")
    parser.add_argument("--output", required=True, help="Path for the generated deck JSON.")
    parser.add_argument(
        "--collection",
        default="",
        help="Optional enriched collection CSV. Used to fill commander metadata and infer categories.",
    )
    parser.add_argument("--name", default="", help="Optional deck name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import_manabox_deck_csv(
        input_path=args.input,
        output_path=args.output,
        commander_name=args.commander,
        collection_path=args.collection,
        deck_name=args.name,
    )
    print(f"Saved deck JSON to: {args.output}")


if __name__ == "__main__":
    main()
