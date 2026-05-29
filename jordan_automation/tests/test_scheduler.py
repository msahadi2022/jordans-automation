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

    def test_sent_just_under_interval_not_due(self, config, empty_state):
        state = {**empty_state, "last_scheduled_send": _ts(13)}
        due, _ = is_scheduled_send_due(state, config)
        assert due is False

    def test_threshold_only_no_scheduled(self, config, empty_state):
        """Only threshold send recorded, no scheduled send — should be due if past skip window."""
        state = {**empty_state, "last_threshold_send": _ts(10)}
        due, _ = is_scheduled_send_due(state, config)
        assert due is True


class TestRecordScheduledSend:
    def test_updates_timestamp(self, empty_state):
        updated = record_scheduled_send(empty_state)
        assert updated["last_scheduled_send"] is not None

    def test_does_not_modify_other_state(self, empty_state):
        updated = record_scheduled_send(empty_state)
        assert updated["jordan_reply_received"] is False
        assert updated["orders_at_last_threshold_send"] == []

    def test_timestamp_is_recent(self, empty_state):
        before = datetime.now(timezone.utc)
        updated = record_scheduled_send(empty_state)
        after = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(updated["last_scheduled_send"]).replace(tzinfo=timezone.utc)
        assert before <= ts <= after
