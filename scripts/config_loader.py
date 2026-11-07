"""Loads and validates YAML config: AI/ML keyword list and milestone reference points."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

DEFAULT_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "config" / "ai_ml_keywords.yaml"
DEFAULT_MILESTONES_PATH = Path(__file__).resolve().parent.parent / "config" / "milestones.yaml"


def load_ai_ml_keywords(path: Path = DEFAULT_KEYWORDS_PATH) -> list[str]:
    data = yaml.safe_load(path.read_text())
    keywords = data.get("keywords") if data else None
    if not keywords or not isinstance(keywords, list):
        raise ValueError(f"{path}: expected a non-empty 'keywords' list")
    return [str(k).lower() for k in keywords]


def build_keyword_regex(keywords: list[str]) -> str:
    """Builds an RE2/Python regex matching any keyword as a standalone token.

    Intended to run against the lowercased repo-name segment (no owner). The
    keyword must not be preceded by a letter or digit, so "jax" doesn't match
    inside "ajax" and "gpt" doesn't match inside "chatgpt" (list compound names
    like that explicitly). It must not be followed by a letter, so "llamas" is
    rejected, but a trailing digit is allowed so versioned names like
    "gpt4all", "llama2", and "llm2vec" still match.
    """
    escaped = [re.escape(k) for k in keywords]
    return "(^|[^a-z0-9])(" + "|".join(escaped) + ")([^a-z]|$)"


def load_milestones(path: Path = DEFAULT_MILESTONES_PATH) -> dict:
    data = yaml.safe_load(path.read_text()) or {}
    for key in ("llm_milestones", "github_user_milestones"):
        if key not in data or not isinstance(data[key], list) or not data[key]:
            raise ValueError(f"{path}: expected a non-empty '{key}' list")
    return data


DEFAULT_DATA_QUALITY_PATH = Path(__file__).resolve().parent.parent / "config" / "data_quality.yaml"
_YEAR_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_month(path: Path, where: str, value: object) -> str:
    if not isinstance(value, str) or not _YEAR_MONTH.match(value):
        raise ValueError(f"{path}: {where} must be a \"YYYY-MM\" string, got {value!r}")
    return value


def load_data_quality(path: Path = DEFAULT_DATA_QUALITY_PATH) -> dict:
    """Loads known GH Archive collection problems: cutoff month, gap months, source breaks."""
    data = yaml.safe_load(path.read_text()) or {}
    result = {"last_reliable_month": _check_month(path, "last_reliable_month", data.get("last_reliable_month"))}
    for key in ("gap_months", "source_breaks"):
        entries = data.get(key)
        if not isinstance(entries, list):
            raise ValueError(f"{path}: expected a '{key}' list (it may be empty)")
        checked = []
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("note"), str) or not entry["note"].strip():
                raise ValueError(f"{path}: {key}[{i}] needs a 'month' and a non-empty 'note'")
            checked.append({"month": _check_month(path, f"{key}[{i}].month", entry.get("month")), "note": entry["note"]})
        result[key] = checked
    return result
