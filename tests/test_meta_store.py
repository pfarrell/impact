from scripts.meta_store import read_meta, write_meta


def test_read_meta_returns_defaults_when_missing(tmp_path):
    meta = read_meta(tmp_path / "_meta.json")

    assert meta == {"last_refreshed_month": None, "total_bytes_billed": 0}


def test_write_meta_then_read_round_trips(tmp_path):
    path = tmp_path / "_meta.json"
    write_meta(path, last_refreshed_month="201501", additional_bytes_billed=100)

    meta = read_meta(path)

    assert meta == {"last_refreshed_month": "201501", "total_bytes_billed": 100}


def test_write_meta_accumulates_bytes_billed_across_calls(tmp_path):
    path = tmp_path / "_meta.json"
    write_meta(path, last_refreshed_month="201501", additional_bytes_billed=100)
    write_meta(path, last_refreshed_month="201502", additional_bytes_billed=50)

    meta = read_meta(path)

    assert meta == {"last_refreshed_month": "201502", "total_bytes_billed": 150}
