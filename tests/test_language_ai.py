from scripts.language_ai import split_language_ai


def test_split_language_ai_keeps_language_rows_without_ai_column():
    rows = [
        {"year_month": "201501", "language": "Python", "push_count": 15, "ai_push_count": 4},
        {"year_month": "201501", "language": "Go", "push_count": 5, "ai_push_count": 0},
    ]

    language_rows, _ = split_language_ai(rows)

    assert language_rows == [
        {"year_month": "201501", "language": "Python", "push_count": 15},
        {"year_month": "201501", "language": "Go", "push_count": 5},
    ]


def test_split_language_ai_sums_ai_pushes_per_month_in_month_order():
    rows = [
        {"year_month": "201502", "language": "Python", "push_count": 9, "ai_push_count": 3},
        {"year_month": "201501", "language": "Python", "push_count": 15, "ai_push_count": 4},
        {"year_month": "201501", "language": "Unknown", "push_count": 7, "ai_push_count": 1},
        {"year_month": "201502", "language": "Go", "push_count": 2, "ai_push_count": 0},
    ]

    _, ai_rows = split_language_ai(rows)

    assert ai_rows == [
        {"year_month": "201501", "ai_push_count": 5},
        {"year_month": "201502", "ai_push_count": 3},
    ]


def test_split_language_ai_keeps_months_with_zero_ai_pushes():
    rows = [{"year_month": "201501", "language": "Go", "push_count": 2, "ai_push_count": 0}]

    _, ai_rows = split_language_ai(rows)

    assert ai_rows == [{"year_month": "201501", "ai_push_count": 0}]
