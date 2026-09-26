"""Tracks pipeline refresh state: last refreshed month and cumulative bytes billed."""
from __future__ import annotations

import json
from pathlib import Path


def read_meta(path: Path) -> dict:
    if not path.exists():
        return {"last_refreshed_month": None, "total_bytes_billed": 0}
    return json.loads(path.read_text())


def write_meta(path: Path, last_refreshed_month: str, additional_bytes_billed: int) -> None:
    meta = read_meta(path)
    meta["last_refreshed_month"] = last_refreshed_month
    meta["total_bytes_billed"] = meta.get("total_bytes_billed", 0) + additional_bytes_billed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))
