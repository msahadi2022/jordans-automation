import json

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

    def test_baseline_fixture_values(self):
        """Validate the April 29, 2026 baseline fixture reflects the correct expected totals."""
        with open("tests/fixtures/heather_april29_baseline.json") as f:
            baseline = json.load(f)
        expected = baseline["expected_totals"]
        assert expected["total_volume_cf"] == pytest.approx(2039.0, rel=0.01)
        assert expected["total_cartons"] == 339


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


class TestGetOrderNumbers:
    def test_extracts_unique_doc_numbers(self, sample_order_lines):
        result = get_order_numbers(sample_order_lines)
        assert result == {"WH00121966", "WH00121967"}

    def test_deduplicates_same_doc(self):
        lines = [
            {"sales_doc_num": "WH001"},
            {"sales_doc_num": "WH001"},
            {"sales_doc_num": "WH002"},
        ]
        assert get_order_numbers(lines) == {"WH001", "WH002"}


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

    def test_evaluate_returns_reason(self, config, empty_state):
        lines = [{"line_volume_cf": 500.0, "line_weight_lbs": 1000.0,
                  "line_cartons": 10, "sales_doc_num": "WH001"}]
        result = evaluate(lines, empty_state, config)
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0
