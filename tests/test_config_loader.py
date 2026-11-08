# tests/test_config_loader.py
import re

import pytest

from scripts.config_loader import build_keyword_regex, load_ai_ml_keywords, load_milestones


def test_load_ai_ml_keywords_lowercases_and_returns_list(tmp_path):
    path = tmp_path / "keywords.yaml"
    path.write_text("keywords:\n  - PyTorch\n  - LangChain\n")

    result = load_ai_ml_keywords(path)

    assert result == ["pytorch", "langchain"]


def test_load_ai_ml_keywords_rejects_empty_list(tmp_path):
    path = tmp_path / "keywords.yaml"
    path.write_text("keywords: []\n")

    with pytest.raises(ValueError):
        load_ai_ml_keywords(path)


def test_build_keyword_regex_escapes_special_characters_and_anchors_boundaries():
    result = build_keyword_regex(["pytorch", "c++"])

    assert result == r"(^|[^a-z0-9])(pytorch|c\+\+)([^a-z]|$)"


@pytest.mark.parametrize(
    "repo_segment",
    ["jax", "jax-md", "google-jax", "flax_jax_examples", "learning.jax", "gpt4all", "llm2vec", "llama.cpp"],
)
def test_build_keyword_regex_matches_keyword_as_a_token(repo_segment):
    pattern = re.compile(build_keyword_regex(["jax", "gpt", "llm", "llama"]))

    assert pattern.search(repo_segment)


@pytest.mark.parametrize(
    "repo_segment",
    ["ajax-something", "jquery-ajax", "ajax", "jaxb-tools", "gptables", "allmighty", "llamas"],
)
def test_build_keyword_regex_does_not_match_inside_longer_words(repo_segment):
    pattern = re.compile(build_keyword_regex(["jax", "gpt", "llm", "llama"]))

    assert not pattern.search(repo_segment)


def test_load_milestones_returns_both_sections(tmp_path):
    path = tmp_path / "milestones.yaml"
    path.write_text(
        "llm_milestones:\n"
        "  - date: '2022-11'\n"
        "    label: 'ChatGPT released'\n"
        "github_user_milestones:\n"
        "  - date: '2023-01'\n"
        "    users_millions: 100\n"
        "    source: 'GitHub blog'\n"
    )

    result = load_milestones(path)

    assert result["llm_milestones"][0]["label"] == "ChatGPT released"
    assert result["github_user_milestones"][0]["users_millions"] == 100


def test_load_milestones_rejects_missing_section(tmp_path):
    path = tmp_path / "milestones.yaml"
    path.write_text("llm_milestones:\n  - date: '2022-11'\n    label: 'x'\n")

    with pytest.raises(ValueError):
        load_milestones(path)
