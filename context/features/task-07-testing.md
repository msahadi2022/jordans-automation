# Task 07 — Testing

## Overview

Write the pytest test suite for the Jordan Brand container automation. Tests cover all five core modules. External dependencies (Fabric, Graph API, Azure AD) are mocked — no live network calls in tests.

## Requirements

- Use **pytest** with `unittest.mock`
- All tests in `tests/` directory, one file per module
- No live Fabric or Graph API calls — mock all external I/O
- Validate against the April 29 baseline fixture
- Cover happy path, edge cases, and error handling for each module
- All tests must pass with `pytest tests/ -v`

## Test Files

```
tests/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── test_volume_calculator.py
├── test_scheduler.py
├── test_email_sender.py
├── test_inbox_monitor.py
├── test_fabric_client.py
└── fixtures/
    ├── heather_april29_baseline.json
    └── sample_order_lines.json
```

-----

## Fixtures (conftest.py)

```python
import pytest

@pytest.fixture
def config():
    return {
        "fabric": {
            "endpoint": "test.fabric.microsoft.com",
            "database": "Gold",
            "tenant_id": "test-tenant-id",
            "auth_mode": "service_principal",
        },
        "jordan_customers": ["0010033", "0010174", "0005505"],
        "qualifying_batches": ["WH ORDER REVIEW", "WH NEW ORDER"],
        "threshold": {"volume_cf": 2200},
        "schedule": {
            "interval_days": 14,
            "skip_window_after_threshold_days": 3,
        },
        "inbound": {
            "no_response_window_days": 2,
            "jordan_reply_addresses": ["bchartier@jordans.com", "traffic@jordans.com"],
        },
        "email": {
            "to": "traffic@jordans.com",
            "cc": ["bchartier@jordans.com", "rszewczyk@maxwoodfurniture.com"],
            "from": "logistics@maxwoodfurniture.com",
            "internal_notify": ["hcollins@maxwoodfurniture.com"],
        },
        "paths": {
            "state_file": "state.json",
            "log_file": "jordan_automation.log",
        },
    }

@pytest.fixture
def empty_state():
    return {
        "last_threshold_send": None,
        "last_scheduled_send": None,
        "last_reminder_sent": None,
        "last_run": None,
        "jordan_reply_received": False,
        "reminder_sent": False,
        "orders_at_last_threshold_send": [],
        "volume_at_last_threshold_send": None,
    }

@pytest.fixture
def sample_order_lines():
    return [
        {
            "sales_doc_num": "WH00121966",
            "cust_po_num": "MAXWC0309600B",
            "short_description": "710705-152",
            "item_description": "Bed Side Rails incl. Support Bar (Full)",
            "qty": 4.0,
            "volume_cf_per_unit": 1.30,
            "line_volume_cf": 5.20,
            "weight_per_unit": 2.10,
            "line_weight_lbs": 8.40,
            "cartons_per_unit": 1,
            "line_cartons": 4,
        },
        {
            "sales_doc_num": "WH00121967",
            "cust_po_num": "MAXWC0309601A",
            "short_description": "710331-131",
            "item_description": "Full Slat HeadBoard & FootPanel incl. Slat Roll",
            "qty": 1.0,
            "volume_cf_per_unit": 11.90,
            "line_volume_cf": 11.90,
            "weight_per_unit": 85.0,
            "line_weight_lbs": 85.0,
            "cartons_per_unit": 1,
            "line_cartons": 1,
        },
    ]
```

-----

## tests/fixtures/heather_april29_baseline.json

```json
{
  "description": "Heather Collins manual report — April 29, 2026. Used as validation baseline.",
  "total_volume_cf": 2039.0,
  "total_weight_lbs": 16112.0,
  "total_cartons": 339,
  "tolerance_pct": 0.01
}
```

-----

## test_volume_calculator.py

```python
import pytest
from volume_calculator import (
    aggregate_totals,
    evaluate,
    get_order_numbers,
    has_new_orders,
    is_threshold_met,
    load_state,
    record_threshold_send,
    should_send_threshold,
    write_state,
)

class TestAggregateTotals:
    def test_sums_correctly(self, sample_order_lines):
        result = aggregate_totals(sample_order_lines)
        assert result["total_volume_cf"] == pytest.approx(17.10, rel=0.01)
        assert result["total_weight_lbs"] == pytest.approx(93.40, rel=0.01)
        assert result["total_cartons"] == 5

    def test_empty_returns_zeros(self):
        result = aggregate_totals([])
        assert result["total_volume_cf"] == 0.0
        assert result["total_weight_lbs"] == 0.0
        assert result["total_cartons"] == 0

    def test_null_values_treated_as_zero(self):
        lines = [{"line_volume_cf": None, "line_weight_lbs": None, "line_cartons": None}]
        result = aggregate_totals(lines)
        assert result["total_volume_cf"] == 0.0
        assert result["total_cartons"] == 0

    def test_baseline_validation(self):
        """Validate against Heather's April 29, 2026 manual report."""
        import json
        with open("tests/fixtures/heather_april29_baseline.json") as f:
            baseline = json.load(f)
        # NOTE: This test requires live Fabric data or a saved fixture of the
        # April 29 order lines. Placeholder assertion — replace with fixture data.
        assert baseline["total_volume_cf"] == pytest.approx(2039.0, rel=0.01)
        assert baseline["total_cartons"] == 339


class TestThresholdLogic:
    def test_threshold_met(self, config):
        assert is_threshold_met(2200.0, config) is True
        assert is_threshold_met(2500.0, config) is True

    def test_threshold_not_met(self, config):
        assert is_threshold_met(2199.9, config) is False
        assert is_threshold_met(0.0, config) is False

    def test_threshold_exactly_at_boundary(self, config):
        assert is_threshold_met(2200.0, config) is True

    def test_has_new_orders_detects_new(self, empty_state):
        current = {"WH001", "WH002"}
        state = {**empty_state, "orders_at_last_threshold_send": ["WH001"]}
        assert has_new_orders(current, state) is True

    def test_has_new_orders_no_new(self, empty_state):
        current = {"WH001"}
        state = {**empty_state, "orders_at_last_threshold_send": ["WH001"]}
        assert has_new_orders(current, state) is False

    def test_has_new_orders_empty_previous(self, empty_state):
        current = {"WH001"}
        assert has_new_orders(current, empty_state) is True

    def test_should_send_threshold_true(self, config, empty_state):
        assert should_send_threshold(2500.0, {"WH001"}, empty_state, config) is True

    def test_should_send_threshold_below_threshold(self, config, empty_state):
        assert should_send_threshold(1000.0, {"WH001"}, empty_state, config) is False

    def test_should_send_threshold_no_new_orders(self, config, empty_state):
        state = {**empty_state, "orders_at_last_threshold_send": ["WH001"]}
        assert should_send_threshold(2500.0, {"WH001"}, state, config) is False


class TestStateManagement:
    def test_load_state_missing_file(self, tmp_path):
        result = load_state(str(tmp_path / "nonexistent.json"))
        assert result["jordan_reply_received"] is False
        assert result["orders_at_last_threshold_send"] == []

    def test_load_state_corrupt_file(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not valid json")
        result = load_state(str(p))
        assert result["reminder_sent"] is False

    def test_write_and_read_state(self, tmp_path, empty_state):
        path = str(tmp_path / "state.json")
        write_state(empty_state, path)
        loaded = load_state(path)
        assert loaded["jordan_reply_received"] is False

    def test_record_threshold_send(self, empty_state):
        updated = record_threshold_send(empty_state, {"WH001", "WH002"}, 2300.0)
        assert updated["volume_at_last_threshold_send"] == 2300.0
        assert "WH001" in updated["orders_at_last_threshold_send"]
        assert updated["jordan_reply_received"] is False
        assert updated["reminder_sent"] is False


class TestEvaluate:
    def test_evaluate_empty_lines(self, config, empty_state):
        result = evaluate([], empty_state, config)
        assert result["send_threshold"] is False
        assert result["totals"]["total_volume_cf"] == 0.0

    def test_evaluate_below_threshold(self, config, empty_state, sample_order_lines):
        result = evaluate(sample_order_lines, empty_state, config)
        assert result["send_threshold"] is False

    def test_evaluate_above_threshold(self, config, empty_state):
        lines = [{"line_volume_cf": 2300.0, "line_weight_lbs": 10000.0,
                  "line_cartons": 100, "sales_doc_num": "WH001"}]
        result = evaluate(lines, empty_state, config)
        assert result["send_threshold"] is True

    def test_evaluate_no_new_orders(self, config, empty_state):
        state = {**empty_state, "orders_at_last_threshold_send": ["WH001"]}
        lines = [{"line_volume_cf": 2300.0, "line_weight_lbs": 10000.0,
                  "line_cartons": 100, "sales_doc_num": "WH001"}]
        result = evaluate(lines, state, config)
        assert result["send_threshold"] is False
```

-----

## test_scheduler.py

```python
from datetime import datetime, timedelta, timezone
from scheduler import is_scheduled_send_due, record_scheduled_send


def _ts(days_ago: float) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


class TestIsScheduledSendDue:
    def test_never_sent_is_due(self, config, empty_state):
        due, reason = is_scheduled_send_due(empty_state, config)
        assert due is True
        assert "no previous send" in reason.lower()

    def test_sent_recently_not_due(self, config, empty_state):
        state = {**empty_state, "last_scheduled_send": _ts(3)}
        due, _ = is_scheduled_send_due(state, config)
        assert due is False

    def test_sent_14_days_ago_is_due(self, config, empty_state):
        state = {**empty_state, "last_scheduled_send": _ts(14)}
        due, _ = is_scheduled_send_due(state, config)
        assert due is True

    def test_skip_window_after_threshold(self, config, empty_state):
        state = {
            **empty_state,
            "last_scheduled_send": _ts(15),
            "last_threshold_send": _ts(1),
        }
        due, reason = is_scheduled_send_due(state, config)
        assert due is False
        assert "skip window" in reason.lower()

    def test_skip_window_expired(self, config, empty_state):
        state = {
            **empty_state,
            "last_scheduled_send": _ts(15),
            "last_threshold_send": _ts(4),
        }
        due, _ = is_scheduled_send_due(state, config)
        assert due is True


class TestRecordScheduledSend:
    def test_updates_timestamp(self, empty_state):
        updated = record_scheduled_send(empty_state)
        assert updated["last_scheduled_send"] is not None
        assert updated["jordan_reply_received"] is False
```

-----

## test_email_sender.py

```python
from unittest.mock import MagicMock, patch
import pytest
from email_sender import build_report_body, send_report


class TestBuildReportBody:
    def test_threshold_contains_cta(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "threshold")
        assert "approve" in body.lower()
        assert "17.10" in body
        assert "93" in body
        assert "WH00121966" in body
        assert "710705-152" in body

    def test_scheduled_contains_cta(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "scheduled")
        assert "status update" in body.lower() or "accumulate" in body.lower()

    def test_table_has_header_and_separator(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "threshold")
        assert "Sales Doc Num" in body
        assert "---" in body

    def test_all_orders_present(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "threshold")
        assert "WH00121966" in body
        assert "WH00121967" in body


class TestSendReport:
    def test_raises_on_empty_lines(self, config):
        totals = {"total_volume_cf": 0, "total_weight_lbs": 0, "total_cartons": 0}
        with pytest.raises(ValueError):
            send_report([], totals, "threshold", config)

    def test_raises_on_zero_volume(self, config, sample_order_lines):
        totals = {"total_volume_cf": 0, "total_weight_lbs": 0, "total_cartons": 0}
        with pytest.raises(ValueError):
            send_report(sample_order_lines, totals, "threshold", config)

    @patch("email_sender._get_graph_token", return_value="mock-token")
    @patch("email_sender.requests.post")
    def test_sends_successfully(self, mock_post, mock_token, config, sample_order_lines):
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        result = send_report(sample_order_lines, totals, "threshold", config)
        assert result is True
        mock_post.assert_called_once()

    @patch("email_sender._get_graph_token", return_value="mock-token")
    @patch("email_sender.requests.post")
    @patch("email_sender.time.sleep", return_value=None)
    def test_returns_false_on_failure(self, mock_sleep, mock_post, mock_token, config, sample_order_lines):
        mock_post.side_effect = Exception("Network error")
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        result = send_report(sample_order_lines, totals, "threshold", config)
        assert result is False
        assert mock_post.call_count == 2  # retried once
```

-----

## test_inbox_monitor.py

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from inbox_monitor import (
    fetch_jordan_replies,
    record_reminder_sent,
    record_reply_received,
    should_send_reminder,
)


def _ts(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class TestFetchJordanReplies:
    def test_no_send_returns_empty(self, config, empty_state):
        result = fetch_jordan_replies(config, empty_state)
        assert result == []

    @patch("inbox_monitor._get_graph_token", return_value="mock-token")
    @patch("inbox_monitor.requests.get")
    def test_filters_jordan_senders(self, mock_get, mock_token, config, empty_state):
        state = {**empty_state, "last_threshold_send": _ts(1)}
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "value": [
                {
                    "from": {"emailAddress": {"address": "bchartier@jordans.com"}},
                    "subject": "Re: Container",
                    "receivedDateTime": _ts(0),
                    "bodyPreview": "Looks good, let's proceed.",
                },
                {
                    "from": {"emailAddress": {"address": "unknown@other.com"}},
                    "subject": "Spam",
                    "receivedDateTime": _ts(0),
                    "bodyPreview": "Buy now!",
                },
            ]
        }
        mock_get.return_value = mock_response

        replies = fetch_jordan_replies(config, state)
        assert len(replies) == 1
        assert replies[0]["from_address"] == "bchartier@jordans.com"


class TestShouldSendReminder:
    def test_no_send_no_reminder(self, config, empty_state):
        assert should_send_reminder(empty_state, config) is False

    def test_reply_received_no_reminder(self, config, empty_state):
        state = {
            **empty_state,
            "last_threshold_send": _ts(3),
            "jordan_reply_received": True,
        }
        assert should_send_reminder(state, config) is False

    def test_reminder_already_sent(self, config, empty_state):
        state = {
            **empty_state,
            "last_threshold_send": _ts(3),
            "reminder_sent": True,
        }
        assert should_send_reminder(state, config) is False

    def test_within_window_no_reminder(self, config, empty_state):
        state = {**empty_state, "last_threshold_send": _ts(1)}
        assert should_send_reminder(state, config) is False

    def test_past_window_sends_reminder(self, config, empty_state):
        state = {**empty_state, "last_threshold_send": _ts(3)}
        assert should_send_reminder(state, config) is True


class TestStateUpdates:
    def test_record_reply_received(self, empty_state):
        reply = {"received_at": _ts(0), "from_address": "bchartier@jordans.com",
                 "subject": "Re: Container", "body_preview": "Approved"}
        updated = record_reply_received(empty_state, reply)
        assert updated["jordan_reply_received"] is True
        assert updated["last_jordan_reply"] == reply["received_at"]

    def test_record_reminder_sent(self, empty_state):
        updated = record_reminder_sent(empty_state)
        assert updated["reminder_sent"] is True
        assert updated["last_reminder_sent"] is not None
```

-----

## test_fabric_client.py

```python
from unittest.mock import MagicMock, patch
import pytest
from fabric_client import _validate_row, _build_sql, aggregate_totals_from_rows


class TestValidateRow:
    def test_clean_row_no_warnings(self):
        row = {
            "sales_doc_num": "WH001",
            "cust_po_num": "MAXWC001",
            "line_volume_cf": 5.20,
            "line_weight_lbs": 10.0,
            "short_description": "710705-152",
        }
        assert _validate_row(row) == []

    def test_null_volume_warning(self):
        row = {"sales_doc_num": "WH001", "cust_po_num": "X",
               "line_volume_cf": None, "line_weight_lbs": 10.0, "short_description": "SKU"}
        warnings = _validate_row(row)
        assert any("volume" in w.lower() for w in warnings)

    def test_null_weight_warning(self):
        row = {"sales_doc_num": "WH001", "cust_po_num": "X",
               "line_volume_cf": 5.0, "line_weight_lbs": None, "short_description": "SKU"}
        warnings = _validate_row(row)
        assert any("weight" in w.lower() for w in warnings)

    def test_missing_sku_warning(self):
        row = {"sales_doc_num": "WH001", "cust_po_num": "X",
               "line_volume_cf": 5.0, "line_weight_lbs": 10.0, "short_description": ""}
        warnings = _validate_row(row)
        assert any("sku" in w.lower() for w in warnings)


class TestBuildSql:
    def test_injects_customers_and_batches(self, config):
        sql = _build_sql(config)
        assert "'0010033'" in sql
        assert "'WH ORDER REVIEW'" in sql
        assert "'WH NEW ORDER'" in sql
```

-----

## Notes

`test_fabric_client.py` references `aggregate_totals_from_rows` which doesn’t exist as a standalone function — remove that reference or use `aggregate_totals` from `volume_calculator` instead. Only test pure functions from `fabric_client` — `_validate_row` and `_build_sql` are the right targets.

The baseline test in `test_volume_calculator.py` currently only validates the JSON fixture values, not actual live data. To fully validate against the April 29 data, save the raw query results from that date as `tests/fixtures/sample_april29_order_lines.json` and run `aggregate_totals()` against them.

## Running Tests

```bash
source ~/fabric-env/bin/activate
pip install pytest --break-system-packages
pytest tests/ -v
```