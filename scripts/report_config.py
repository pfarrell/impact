"""Writes the config-derived JSON files the report reads next to the CSVs.

Backfill and refresh call this; run it directly (`python -m
scripts.report_config`) after editing config/milestones.yaml or
config/data_quality.yaml to update data/ without querying BigQuery.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.config_loader import load_data_quality, load_milestones

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def write_report_config(data_dir: Path = DATA_DIR) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "milestones.json").write_text(json.dumps(load_milestones(), indent=2))
    (data_dir / "data_quality.json").write_text(json.dumps(load_data_quality(), indent=2))


if __name__ == "__main__":
    write_report_config()
    print(f"Wrote milestones.json and data_quality.json to {DATA_DIR}")
