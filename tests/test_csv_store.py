from scripts.csv_store import (
    append_rows,
    last_cumulative_value,
    overwrite_rows,
    with_running_cumulative,
)


def test_append_rows_writes_header_once(tmp_path):
    path = tmp_path / "data.csv"
    append_rows(path, ["year_month", "count"], [{"year_month": "201501", "count": 5}])
    append_rows(path, ["year_month", "count"], [{"year_month": "201502", "count": 7}])

    lines = path.read_text().strip().splitlines()
    assert lines == ["year_month,count", "201501,5", "201502,7"]


def test_overwrite_rows_replaces_file_contents(tmp_path):
    path = tmp_path / "data.csv"
    append_rows(path, ["year_month", "count"], [{"year_month": "201501", "count": 5}])
    overwrite_rows(path, ["year_month", "count"], [{"year_month": "202601", "count": 99}])

    lines = path.read_text().strip().splitlines()
    assert lines == ["year_month,count", "202601,99"]


def test_last_cumulative_value_returns_zero_when_missing(tmp_path):
    assert last_cumulative_value(tmp_path / "missing.csv", "cumulative_total") == 0


def test_last_cumulative_value_reads_last_row(tmp_path):
    path = tmp_path / "data.csv"
    overwrite_rows(
        path,
        ["year_month", "cumulative_total"],
        [
            {"year_month": "201501", "cumulative_total": 10},
            {"year_month": "201502", "cumulative_total": 25},
        ],
    )

    assert last_cumulative_value(path, "cumulative_total") == 25


def test_with_running_cumulative_accumulates_from_starting_total():
    rows = [{"year_month": "201501", "new_actor_count": 5}, {"year_month": "201502", "new_actor_count": 3}]

    result = with_running_cumulative(rows, "new_actor_count", "cumulative_total", starting_total=10)

    assert result == [
        {"year_month": "201501", "new_actor_count": 5, "cumulative_total": 15},
        {"year_month": "201502", "new_actor_count": 3, "cumulative_total": 18},
    ]
