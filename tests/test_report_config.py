import json

import pytest

from scripts.config_loader import load_data_quality
from scripts.report_config import write_report_config


def _write(tmp_path, text):
    path = tmp_path / "dq.yaml"
    path.write_text(text)
    return path


VALID = """
last_reliable_month: "2026-07"
gap_months:
  - month: "2021-10"
    note: "thin"
source_breaks:
  - month: "2025-06"
    note: "step down"
"""


def test_load_data_quality_returns_validated_config(tmp_path):
    result = load_data_quality(_write(tmp_path, VALID))

    assert result == {
        "last_reliable_month": "2026-07",
        "gap_months": [{"month": "2021-10", "note": "thin"}],
        "source_breaks": [{"month": "2025-06", "note": "step down"}],
    }


def test_load_data_quality_allows_empty_lists(tmp_path):
    result = load_data_quality(_write(tmp_path, 'last_reliable_month: "2026-07"\ngap_months: []\nsource_breaks: []\n'))

    assert result["gap_months"] == [] and result["source_breaks"] == []


@pytest.mark.parametrize("text", [
    'gap_months: []\nsource_breaks: []\n',
    'last_reliable_month: "202607"\ngap_months: []\nsource_breaks: []\n',
    'last_reliable_month: "2026-07"\ngap_months:\n  - month: "2021-10"\nsource_breaks: []\n',
    'last_reliable_month: "2026-07"\ngap_months:\n  - month: "21-10"\n    note: x\nsource_breaks: []\n',
    'last_reliable_month: "2026-07"\ngap_months: []\n',
])
def test_load_data_quality_rejects_malformed_config(tmp_path, text):
    with pytest.raises(ValueError):
        load_data_quality(_write(tmp_path, text))


def test_real_data_quality_config_loads():
    assert load_data_quality()["last_reliable_month"]


def test_write_report_config_writes_milestones_and_data_quality(tmp_path):
    data_dir = tmp_path / "data"

    write_report_config(data_dir)

    milestones = json.loads((data_dir / "milestones.json").read_text())
    data_quality = json.loads((data_dir / "data_quality.json").read_text())
    assert milestones["llm_milestones"]
    assert data_quality == load_data_quality()
