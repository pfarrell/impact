import csv
import io
import json
import math
from datetime import date

import pytest

from scripts import innovation_graph as ig


def _csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return path


def _read(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _raw(tmp_path):
    """A tiny release: two economies plus the EU aggregate, 2021Q1-2022Q2."""
    d = tmp_path / "raw" / "vTEST"
    quarters = [(2021, 1), (2021, 2), (2021, 3), (2021, 4), (2022, 1), (2022, 2)]
    pushes = []
    for i, (y, q) in enumerate(quarters):
        pushes += [[100 * 2 ** i, "US", y, q], [50 * 2 ** i, "IN", y, q], [999999, "EU", y, q]]
    _csv(d / "git_pushes.csv", ["git_pushes", "iso2_code", "year", "quarter"], pushes)
    _csv(d / "developers.csv", ["developers", "iso2_code", "year", "quarter"],
         [[10, c, y, q] for y, q in quarters for c in ("US", "IN")] + [[5000, "EU", 2021, 1]])
    _csv(d / "repositories.csv", ["repositories", "iso2_code", "year", "quarter"],
         [[7, c, y, q] for y, q in quarters for c in ("US", "IN")])
    _csv(d / "languages.csv", ["num_pushers", "language", "language_type", "iso2_code", "year", "quarter"], [
        [6, "Python", "programming", "US", 2021, 1], [2, "Go", "programming", "US", 2021, 1],
        [4, "Python", "programming", "US", 2022, 2], [3, "Rust", "programming", "IN", 2022, 2],
        [3, "Go", "programming", "US", 2022, 2], [100, "HTML", "markup", "US", 2022, 2],
        [900, "Python", "programming", "EU", 2022, 2],
    ])
    _csv(d / "topics.csv", ["num_pushers", "topic", "iso2_code", "year", "quarter"], [
        [5, "llm", "US", 2022, 1], [4, "llm", "IN", 2022, 1], [8, "LLM", "US", 2022, 2],
        [70, "llm", "EU", 2022, 2], [9, "react", "US", 2022, 2],
    ])
    return d


def test_quarter_helpers():
    assert ig.quarter_key("2024", "3") == "2024Q3"
    assert ig.quarter_index("2021Q1") + 4 == ig.quarter_index("2022Q1")
    assert ig.month_to_quarter("202405") == "2024Q2"
    assert ig.month_to_quarter("2024-12") == "2024Q4"
    with pytest.raises(ValueError):
        ig.quarter_index("2024-05")


def test_sum_by_quarter_leaves_out_the_eu_aggregate(tmp_path):
    totals = ig.sum_by_quarter(_raw(tmp_path) / "git_pushes.csv", "git_pushes")

    assert list(totals) == ["2021Q1", "2021Q2", "2021Q3", "2021Q4", "2022Q1", "2022Q2"]
    assert totals["2021Q1"] == 150
    assert totals["2022Q2"] == 150 * 32


def test_log_linear_trend_recovers_exact_exponential_growth():
    series = {ig.quarter_key(2020 + i // 4, i % 4 + 1): 100 * 1.1 ** i for i in range(8)}

    trend = ig.log_linear_trend(series, "2020Q4")

    for k, v in series.items():
        assert trend[k] == pytest.approx(v)


def test_log_linear_trend_uses_only_baseline_quarters():
    series = {"2020Q1": 100.0, "2020Q2": 200.0, "2020Q3": 99999.0}

    trend = ig.log_linear_trend(series, "2020Q2")

    assert trend["2020Q3"] == pytest.approx(400.0)


def test_log_linear_trend_needs_two_baseline_quarters():
    with pytest.raises(ValueError):
        ig.log_linear_trend({"2020Q1": 1.0, "2020Q2": 2.0}, "2020Q1")


def test_build_quarterly_rows(tmp_path):
    rows = ig.build_quarterly(_raw(tmp_path), "2021Q4")

    first, last = rows[0], rows[-1]
    assert list(first) == ig.QUARTERLY_FIELDS
    assert first["git_pushes"] == 150 and first["developers"] == 20 and first["repositories"] == 14
    assert first["yoy"] == ""
    # Pushes double every quarter, so YoY is 2**4 - 1 and the fit is exact.
    assert last["yoy"] == pytest.approx(15.0)
    assert last["trend_pushes"] == 4800 and last["vs_trend"] == pytest.approx(0.0)
    assert last["pushes_per_developer"] == pytest.approx(4800 / 20)


def test_build_languages_takes_top_programming_languages_from_latest_quarter(tmp_path):
    rows = ig.build_languages(_raw(tmp_path), top_n=2)

    latest = [r for r in rows if r["year_quarter"] == "2022Q2"]
    # Python 4, Go 3, Rust 3: ties break alphabetically; HTML is markup; EU is dropped.
    assert [r["language"] for r in latest] == ["Python", "Go"]
    assert latest[0]["share"] == pytest.approx(4 / 10)
    early = {r["language"]: r for r in rows if r["year_quarter"] == "2021Q1"}
    assert early["Python"]["num_pushers"] == 6 and early["Python"]["share"] == pytest.approx(6 / 8)


def test_build_topics_fills_zero_quarters_and_matches_case_insensitively(tmp_path):
    rows = ig.build_topics(_raw(tmp_path), ["llm", "mcp"], ["2022Q2", "2021Q1", "2022Q1"])

    got = {(r["year_quarter"], r["topic"]): r["num_pushers"] for r in rows}
    assert [r["year_quarter"] for r in rows][::2] == ["2021Q1", "2022Q1", "2022Q2"]
    assert got[("2021Q1", "llm")] == 0
    assert got[("2022Q1", "llm")] == 9
    assert got[("2022Q2", "llm")] == 8
    assert got[("2022Q2", "mcp")] == 0


def test_build_gha_quarterly_blanks_incomplete_gap_and_late_quarters(tmp_path):
    months = [f"2021{m:02d}" for m in range(1, 13)] + ["202201", "202202", "202203", "202204"]
    volume = _csv(tmp_path / "monthly_volume.csv", ["year_month", "push_count"], [[m, 10] for m in months if m != "202105"])
    dq = {"last_reliable_month": "2022-02", "gap_months": [{"month": "2021-10", "note": "x"}], "source_breaks": []}

    rows = {r["year_quarter"]: r["push_count"] for r in ig.build_gha_quarterly(volume, dq)}

    assert rows == {"2021Q1": 30, "2021Q2": "", "2021Q3": 30, "2021Q4": "", "2022Q1": "", "2022Q2": ""}


def _config(tmp_path, text):
    p = tmp_path / "ig.yaml"
    p.write_text(text)
    return p


VALID = 'release: "v1.0.12"\nbaseline_end: "2022Q4"\ntop_languages: 8\nai_topics: [LLM, mcp]\n'


def test_load_config_validates_and_lowercases_topics(tmp_path):
    cfg = ig.load_config(_config(tmp_path, VALID))

    assert cfg == {"release": "v1.0.12", "baseline_end": "2022Q4", "top_languages": 8, "ai_topics": ["llm", "mcp"]}


@pytest.mark.parametrize("bad", [
    VALID.replace('release: "v1.0.12"\n', ""),
    VALID.replace('"2022Q4"', '"2022-12"'),
    VALID.replace("top_languages: 8", "top_languages: 0"),
    VALID.replace("ai_topics: [LLM, mcp]", "ai_topics: []"),
])
def test_load_config_rejects_malformed(tmp_path, bad):
    with pytest.raises(ValueError):
        ig.load_config(_config(tmp_path, bad))


def test_real_config_loads():
    assert ig.load_config()["release"].startswith("v")


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_fetch_downloads_each_file_once(tmp_path):
    calls = []

    def opener(url):
        calls.append(url)
        return _FakeResponse(b"a,b\n1,2\n")

    ig.fetch("vX", tmp_path, opener)
    ig.fetch("vX", tmp_path, opener)

    assert len(calls) == len(ig.RAW_FILES)
    assert all("/innovationgraph/vX/data/" in u for u in calls)
    assert (tmp_path / "vX" / "topics.csv").read_text() == "a,b\n1,2\n"
    assert not list((tmp_path / "vX").glob("*.part"))


def test_run_writes_every_report_file(tmp_path):
    raw = _raw(tmp_path)
    data_dir = tmp_path / "data"
    _csv(data_dir / "monthly_volume.csv", ["year_month", "push_count"], [["202101", 1], ["202102", 2], ["202103", 3]])
    cfg = {"release": "vTEST", "baseline_end": "2021Q4", "top_languages": 2, "ai_topics": ["llm"]}

    def no_network(url):
        raise AssertionError("files already present; should not download")

    rows = ig.run(cfg, raw_dir=raw.parent, data_dir=data_dir, opener=no_network, today=date(2026, 11, 7))

    assert rows[-1]["year_quarter"] == "2022Q2"
    for name in ("ig_quarterly.csv", "ig_languages.csv", "ig_topics.csv", "gha_quarterly.csv",
                 "milestones.json", "data_quality.json"):
        assert (data_dir / name).exists(), name
    assert _read(data_dir / "gha_quarterly.csv") == [{"year_quarter": "2021Q1", "push_count": "6"}]
    meta = json.loads((data_dir / "ig_meta.json").read_text())
    assert meta == {"release": "vTEST", "baseline_end": "2021Q4", "built": "2026-11-07"}
    assert math.isclose(float(_read(data_dir / "ig_quarterly.csv")[0]["vs_trend"]), 0.0, abs_tol=1e-6)
