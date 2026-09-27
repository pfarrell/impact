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
