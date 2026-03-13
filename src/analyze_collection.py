from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from mtg_collection_utils import (
    build_commander_candidate_table,
    ensure_columns,
    read_csv_file,
    split_color_identity,
    to_bool,
)


TYPE_COLUMNS = [
    "is_creature",
    "is_land",
    "is_artifact",
    "is_enchantment",
    "is_instant",
    "is_sorcery",
    "is_planeswalker",
    "is_battle",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce simple Commander-focused summary outputs from an enriched collection CSV."
    )
    parser.add_argument("--input", required=True, help="Path to an enriched collection CSV.")
    parser.add_argument("--output-dir", required=True, help="Directory for analysis outputs.")
    return parser.parse_args()


def build_color_distribution(df: pd.DataFrame) -> pd.DataFrame:
    ensure_columns(df, ["Quantity", "color_identity"])

    quantity_series = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    counts: dict[str, int] = {}
    for index, row in df.iterrows():
        quantity = int(quantity_series.loc[index])
        colors = split_color_identity(row["color_identity"])
        label = "Colorless" if not colors else "".join(colors)
        counts[label] = counts.get(label, 0) + quantity

    return (
        pd.DataFrame(
            [{"color_identity": color_identity, "card_count": count} for color_identity, count in counts.items()]
        )
        .sort_values(["card_count", "color_identity"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_type_distribution(df: pd.DataFrame) -> pd.DataFrame:
    present_type_columns = [column for column in TYPE_COLUMNS if column in df.columns]
    if not present_type_columns:
        raise ValueError("No type indicator columns were found in the enriched CSV.")

    quantity_series = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    rows = []
    for column in present_type_columns:
        label = column.replace("is_", "")
        mask = df[column].apply(to_bool)
        count = int(quantity_series.loc[mask].sum())
        rows.append({"card_type": label, "card_count": count})

    return pd.DataFrame(rows).sort_values(["card_count", "card_type"], ascending=[False, True]).reset_index(drop=True)


def build_summary(df: pd.DataFrame, commander_df: pd.DataFrame) -> dict:
    quantity_series = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0).astype(int)
    return {
        "total_rows": int(len(df)),
        "total_cards": int(quantity_series.sum()),
        "unique_card_names": int(df["Name"].nunique()),
        "candidate_commander_count": int(len(commander_df)),
        "candidate_commander_copies": int(commander_df["quantity"].sum()) if not commander_df.empty else 0,
    }


def main() -> None:
    args = parse_args()

    print(f"Reading input file: {args.input}")
    enriched_df = read_csv_file(args.input)
    ensure_columns(enriched_df, ["Name", "Quantity", "color_identity"])

    commander_df = build_commander_candidate_table(enriched_df)
    color_df = build_color_distribution(enriched_df)
    type_df = build_type_distribution(enriched_df)
    summary = build_summary(enriched_df, commander_df)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "collection_summary.json"
    color_path = output_dir / "color_distribution.csv"
    type_path = output_dir / "type_distribution.csv"
    commanders_path = output_dir / "candidate_commanders.csv"

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    color_df.to_csv(color_path, index=False)
    type_df.to_csv(type_path, index=False)
    commander_df.to_csv(commanders_path, index=False)

    print(json.dumps(summary, indent=2))
    print(f"Saved analysis outputs to: {output_dir}")


if __name__ == "__main__":
    main()
