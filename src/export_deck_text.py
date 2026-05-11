from __future__ import annotations

import argparse

from deck_text_export import export_deck_to_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a project deck JSON to a plain text decklist.")
    parser.add_argument("--deck", required=True, help="Path to a deck JSON file.")
    parser.add_argument("--output", required=True, help="Path for the text decklist.")
    parser.add_argument("--no-categories", action="store_true", help="Write a flat list instead of grouped sections.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    export_deck_to_text(args.deck, args.output, include_categories=not args.no_categories)
    print(f"Saved text decklist to: {args.output}")


if __name__ == "__main__":
    main()
