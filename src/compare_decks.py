from __future__ import annotations

import argparse

from deck_diff import compare_decks, format_diff_report, write_diff_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two project deck JSON files.")
    parser.add_argument("--old", required=True, help="Path to the old/before deck JSON.")
    parser.add_argument("--new", required=True, help="Path to the new/after deck JSON.")
    parser.add_argument("--json-output", default="", help="Optional path for a machine-readable JSON diff report.")
    parser.add_argument("--include-commander", action="store_true", help="Include commander changes in the comparison.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = compare_decks(args.old, args.new, include_commander=args.include_commander)
    print(format_diff_report(report))
    if args.json_output:
        write_diff_json(report, args.json_output)
        print(f"Saved JSON diff report to: {args.json_output}")


if __name__ == "__main__":
    main()
