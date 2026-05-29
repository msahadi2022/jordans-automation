import pytest
from unittest.mock import MagicMock, patch

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

    def test_weight_volume_cartons_in_header(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "threshold")
        assert "Weight:" in body
        assert "Volume:" in body
        assert "Cartons:" in body

    def test_footer_present(self, sample_order_lines):
        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        body = build_report_body(sample_order_lines, totals, "threshold")
        assert "Maxwood Furniture" in body


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
        assert mock_post.call_count == 2

    @patch("email_sender._get_graph_token", return_value="mock-token")
    @patch("email_sender.requests.post")
    def test_uses_correct_subject_for_mode(self, mock_post, mock_token, config, sample_order_lines):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        send_report(sample_order_lines, totals, "threshold", config)
        payload = mock_post.call_args[1]["json"]
        assert "Container Ready" in payload["message"]["subject"]

    @patch("email_sender._get_graph_token", return_value="mock-token")
    @patch("email_sender.requests.post")
    def test_sends_to_correct_recipient(self, mock_post, mock_token, config, sample_order_lines):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        totals = {"total_volume_cf": 17.10, "total_weight_lbs": 93.40, "total_cartons": 5}
        send_report(sample_order_lines, totals, "scheduled", config)
        payload = mock_post.call_args[1]["json"]
        recipients = [r["emailAddress"]["address"] for r in payload["message"]["toRecipients"]]
        assert "traffic@jordans.com" in recipients
