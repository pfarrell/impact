from datetime import date

from scripts.month_range import latest_closed_month, month_range, month_suffix, next_month_suffix


def test_month_suffix_zero_pads_month():
    assert month_suffix(2015, 1) == "201501"
    assert month_suffix(2026, 11) == "202611"


def test_latest_closed_month_is_previous_month():
    assert latest_closed_month(date(2026, 9, 26)) == "202608"


def test_latest_closed_month_handles_january():
    assert latest_closed_month(date(2026, 1, 15)) == "202512"


def test_month_range_is_inclusive_and_spans_year_boundary():
    assert month_range("201511", "201602") == ["201511", "201512", "201601", "201602"]


def test_month_range_single_month():
    assert month_range("201501", "201501") == ["201501"]


def test_next_month_suffix_advances():
    assert next_month_suffix("201501") == "201502"


def test_next_month_suffix_wraps_year():
    assert next_month_suffix("201512") == "201601"
