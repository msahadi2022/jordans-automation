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

    @patch("inbox_monitor._get_graph_token", return_value="mock-token")
    @patch("inbox_monitor.requests.get")
    def test_returns_empty_when_no_jordan_messages(self, mock_get, mock_token, config, empty_state):
        state = {**empty_state, "last_threshold_send": _ts(1)}
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "value": [
                {
                    "from": {"emailAddress": {"address": "noreply@other.com"}},
                    "subject": "Something else",
                    "receivedDateTime": _ts(0),
                    "bodyPreview": "...",
                }
            ]
        }
        mock_get.return_value = mock_response

        replies = fetch_jordan_replies(config, state)
        assert replies == []

    @patch("inbox_monitor._get_graph_token", return_value="mock-token")
    @patch("inbox_monitor.requests.get")
    def test_reply_dict_has_required_keys(self, mock_get, mock_token, config, empty_state):
        state = {**empty_state, "last_scheduled_send": _ts(1)}
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "value": [
                {
                    "from": {"emailAddress": {"address": "traffic@jordans.com"}},
                    "subject": "Approved",
                    "receivedDateTime": _ts(0),
                    "bodyPreview": "Go ahead.",
                }
            ]
        }
        mock_get.return_value = mock_response

        replies = fetch_jordan_replies(config, state)
        assert len(replies) == 1
        assert "from_address" in replies[0]
        assert "subject" in replies[0]
        assert "received_at" in replies[0]
        assert "body_preview" in replies[0]


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

    def test_uses_scheduled_send_if_no_threshold(self, config, empty_state):
        state = {**empty_state, "last_scheduled_send": _ts(3)}
        assert should_send_reminder(state, config) is True

    def test_uses_most_recent_send(self, config, empty_state):
        """If both sends are recorded, uses the more recent one as the window start."""
        state = {
            **empty_state,
            "last_threshold_send": _ts(5),
            "last_scheduled_send": _ts(1),  # more recent — still in window
        }
        assert should_send_reminder(state, config) is False


class TestStateUpdates:
    def test_record_reply_received(self, empty_state):
        reply = {
            "received_at": _ts(0),
            "from_address": "bchartier@jordans.com",
            "subject": "Re: Container",
            "body_preview": "Approved",
        }
        updated = record_reply_received(empty_state, reply)
        assert updated["jordan_reply_received"] is True
        assert updated["last_jordan_reply"] == reply["received_at"]

    def test_record_reply_preserves_other_state(self, empty_state):
        reply = {"received_at": _ts(0), "from_address": "x", "subject": "s", "body_preview": "p"}
        updated = record_reply_received(empty_state, reply)
        assert updated["reminder_sent"] is False

    def test_record_reminder_sent(self, empty_state):
        updated = record_reminder_sent(empty_state)
        assert updated["reminder_sent"] is True
        assert updated["last_reminder_sent"] is not None

    def test_record_reminder_timestamp_is_recent(self, empty_state):
        before = datetime.now(timezone.utc)
        updated = record_reminder_sent(empty_state)
        after = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(updated["last_reminder_sent"]).replace(tzinfo=timezone.utc)
        assert before <= ts <= after
