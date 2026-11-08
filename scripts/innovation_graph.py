"""Builds the report's main series from GitHub's Innovation Graph.

The Innovation Graph (github.com/github/innovationgraph) is GitHub's own
quarterly count of public activity per economy, with bots and implausibly
high-volume accounts excluded. It is free CSV on GitHub, so this needs no
BigQuery.

Run `python -m scripts.innovation_graph` to download the pinned release (once)
and write into data/:

- ig_quarterly.csv    global pushes, developer accounts and repositories per
                      quarter, with the pre-ChatGPT trend and YoY
- ig_languages.csv    developers pushing to each top programming language
- ig_topics.csv       developers pushing to repos tagged with each AI topic
- gha_quarterly.csv   GH Archive pushes per quarter (from monthly_volume.csv,
                      if present), for the source comparison panel
- ig_meta.json        release and build date
- milestones.json, data_quality.json (see scripts/report_config.py)

"Global" is the sum over economies, leaving out the EU aggregate (its members
are listed separately). GitHub withholds an economy's figure for a quarter
when fewer than 100 developers did that activity, so the sums slightly
under-count; the effect is small next to the totals.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.request import urlopen

import yaml

from scripts.config_loader import load_data_quality
from scripts.csv_store import overwrite_rows
from scripts.report_config import write_report_config

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "innovation_graph"
DEFAULT_CONFIG_PATH = ROOT / "config" / "innovation_graph.yaml"

RAW_FILES = ("git_pushes", "developers", "repositories", "languages", "topics")
BASE_URL = "https://raw.githubusercontent.com/github/innovationgraph/{release}/data/{name}.csv"
# Rows that aggregate other rows; summing them too would double-count.
AGGREGATE_CODES = frozenset({"EU"})

QUARTERLY_FIELDS = ["year_quarter", "git_pushes", "developers", "repositories",
                    "trend_pushes", "vs_trend", "yoy", "pushes_per_developer"]
LANGUAGE_FIELDS = ["year_quarter", "language", "num_pushers", "share"]
TOPIC_FIELDS = ["year_quarter", "topic", "num_pushers"]
GHA_FIELDS = ["year_quarter", "push_count"]

_QUARTER = re.compile(r"^(\d{4})Q([1-4])$")


# ---------- config ----------

def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    release = data.get("release")
    if not isinstance(release, str) or not release.strip():
        raise ValueError(f"{path}: 'release' must be a release tag such as \"v1.0.12\"")
    baseline_end = data.get("baseline_end")
    if not isinstance(baseline_end, str) or not _QUARTER.match(baseline_end):
        raise ValueError(f"{path}: 'baseline_end' must be a \"YYYYQn\" string, got {baseline_end!r}")
    top = data.get("top_languages")
    if not isinstance(top, int) or isinstance(top, bool) or top < 1:
        raise ValueError(f"{path}: 'top_languages' must be a positive integer")
    topics = data.get("ai_topics")
    if not isinstance(topics, list) or not topics or not all(isinstance(t, str) and t for t in topics):
        raise ValueError(f"{path}: 'ai_topics' must be a non-empty list of topic names")
    return {"release": release, "baseline_end": baseline_end, "top_languages": top,
            "ai_topics": [t.lower() for t in topics]}


# ---------- quarter keys ----------

def quarter_key(year: int | str, quarter: int | str) -> str:
    return f"{int(year)}Q{int(quarter)}"


def quarter_index(key: str) -> int:
    m = _QUARTER.match(key)
    if not m:
        raise ValueError(f"not a YYYYQn quarter key: {key!r}")
    return int(m.group(1)) * 4 + int(m.group(2)) - 1


def month_to_quarter(year_month: str) -> str:
    """'202405' or '2024-05' -> '2024Q2'."""
    digits = year_month.replace("-", "")
    return quarter_key(digits[:4], (int(digits[4:6]) - 1) // 3 + 1)


# ---------- download ----------

def fetch(release: str, raw_dir: Path = RAW_DIR, opener: Callable = urlopen) -> Path:
    """Downloads the release's CSVs into raw_dir/<release>/, skipping files already there."""
    dest = raw_dir / release
    dest.mkdir(parents=True, exist_ok=True)
    for name in RAW_FILES:
        target = dest / f"{name}.csv"
        if target.exists():
            continue
        with opener(BASE_URL.format(release=release, name=name)) as resp:
            body = resp.read()
        partial = target.with_suffix(".csv.part")
        partial.write_bytes(body)
        partial.replace(target)
    return dest


# ---------- aggregation ----------

def _economy_rows(path: Path) -> Iterator[dict]:
    with path.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["iso2_code"] not in AGGREGATE_CODES:
                yield row


def sum_by_quarter(path: Path, value_col: str) -> dict[str, int]:
    totals: Counter[str] = Counter()
    for row in _economy_rows(path):
        totals[quarter_key(row["year"], row["quarter"])] += int(row[value_col])
    return dict(sorted(totals.items(), key=lambda kv: quarter_index(kv[0])))


def log_linear_trend(series: dict[str, float], baseline_end: str) -> dict[str, float]:
    """Fits log(value) = a + b * quarter over quarters <= baseline_end; returns the fit for every quarter."""
    end = quarter_index(baseline_end)
    base = [(quarter_index(k), math.log(v)) for k, v in series.items() if quarter_index(k) <= end and v > 0]
    if len(base) < 2:
        raise ValueError(f"need at least two baseline quarters up to {baseline_end}")
    n = len(base)
    mx = sum(x for x, _ in base) / n
    my = sum(y for _, y in base) / n
    slope = sum((x - mx) * (y - my) for x, y in base) / sum((x - mx) ** 2 for x, _ in base)
    intercept = my - slope * mx
    return {k: math.exp(intercept + slope * quarter_index(k)) for k in series}


def build_quarterly(raw_dir: Path, baseline_end: str) -> list[dict]:
    pushes = sum_by_quarter(raw_dir / "git_pushes.csv", "git_pushes")
    developers = sum_by_quarter(raw_dir / "developers.csv", "developers")
    repositories = sum_by_quarter(raw_dir / "repositories.csv", "repositories")
    trend = log_linear_trend(pushes, baseline_end)
    by_index = {quarter_index(k): v for k, v in pushes.items()}
    rows = []
    for k, p in pushes.items():
        prior = by_index.get(quarter_index(k) - 4)
        devs = developers.get(k)
        rows.append({
            "year_quarter": k,
            "git_pushes": p,
            "developers": devs if devs is not None else "",
            "repositories": repositories.get(k, ""),
            "trend_pushes": round(trend[k]),
            "vs_trend": round(p / trend[k] - 1, 6),
            "yoy": round(p / prior - 1, 6) if prior else "",
            "pushes_per_developer": round(p / devs, 6) if devs else "",
        })
    return rows


def build_languages(raw_dir: Path, top_n: int) -> list[dict]:
    """Developers pushing to each of the top_n programming languages (by the latest quarter).

    share is that language's count over the sum across all programming
    languages that quarter. A developer who pushes to repos in several
    languages counts once in each, so share is of developer-language pairs.
    """
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in _economy_rows(raw_dir / "languages.csv"):
        if row["language_type"] != "programming":
            continue
        counts[quarter_key(row["year"], row["quarter"])][row["language"]] += int(row["num_pushers"])
    quarters = sorted(counts, key=quarter_index)
    if not quarters:
        return []
    top = [lang for lang, _ in sorted(counts[quarters[-1]].items(), key=lambda kv: (-kv[1], kv[0]))[:top_n]]
    rows = []
    for q in quarters:
        total = sum(counts[q].values())
        for lang in top:
            n = counts[q].get(lang, 0)
            rows.append({"year_quarter": q, "language": lang, "num_pushers": n,
                         "share": round(n / total, 6) if total else ""})
    return rows


def build_topics(raw_dir: Path, topics: Iterable[str], quarters: Iterable[str]) -> list[dict]:
    """Developers pushing to repos tagged with each topic, with 0 for quarters where it never appears."""
    wanted = list(topics)
    counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for row in _economy_rows(raw_dir / "topics.csv"):
        topic = row["topic"].lower()
        if topic in wanted:
            counts[quarter_key(row["year"], row["quarter"])][topic] += int(row["num_pushers"])
    return [{"year_quarter": q, "topic": t, "num_pushers": counts[q].get(t, 0)}
            for q in sorted(quarters, key=quarter_index) for t in wanted]


def build_gha_quarterly(volume_csv: Path, data_quality: dict) -> list[dict]:
    """GH Archive pushes per quarter. push_count is blank unless all three months are present,
    none is a known collection gap, and all are on or before last_reliable_month."""
    last = data_quality["last_reliable_month"].replace("-", "")
    gaps = {g["month"].replace("-", "") for g in data_quality["gap_months"]}
    months: defaultdict[str, dict[str, int]] = defaultdict(dict)
    with volume_csv.open(newline="") as f:
        for row in csv.DictReader(f):
            ym = row["year_month"].replace("-", "")
            months[month_to_quarter(ym)][ym] = int(row["push_count"])
    if not months:
        return []
    keys = sorted(months, key=quarter_index)
    first, final = quarter_index(keys[0]), quarter_index(keys[-1])
    rows = []
    for i in range(first, final + 1):
        k = quarter_key(i // 4, i % 4 + 1)
        ms = months.get(k, {})
        ok = len(ms) == 3 and not gaps & ms.keys() and max(ms) <= last
        rows.append({"year_quarter": k, "push_count": sum(ms.values()) if ok else ""})
    return rows


# ---------- entry point ----------

def run(config: dict | None = None, raw_dir: Path = RAW_DIR, data_dir: Path = DATA_DIR,
        opener: Callable = urlopen, today: date | None = None) -> list[dict]:
    config = config or load_config()
    src = fetch(config["release"], raw_dir, opener)
    quarterly = build_quarterly(src, config["baseline_end"])
    overwrite_rows(data_dir / "ig_quarterly.csv", QUARTERLY_FIELDS, quarterly)
    overwrite_rows(data_dir / "ig_languages.csv", LANGUAGE_FIELDS, build_languages(src, config["top_languages"]))
    overwrite_rows(data_dir / "ig_topics.csv", TOPIC_FIELDS,
                   build_topics(src, config["ai_topics"], [r["year_quarter"] for r in quarterly]))
    volume = data_dir / "monthly_volume.csv"
    if volume.exists():
        overwrite_rows(data_dir / "gha_quarterly.csv", GHA_FIELDS, build_gha_quarterly(volume, load_data_quality()))
    (data_dir / "ig_meta.json").write_text(json.dumps({
        "release": config["release"],
        "baseline_end": config["baseline_end"],
        "built": (today or date.today()).isoformat(),
    }, indent=2))
    write_report_config(data_dir)
    return quarterly


if __name__ == "__main__":
    rows = run()
    print(f"Wrote Innovation Graph series ({rows[0]['year_quarter']} to {rows[-1]['year_quarter']}) to {DATA_DIR}")
