"""
Bi-weekly scheduled send logic for Jordan Brand container status emails.
"""

import logging
from datetime import datetime, timezone

DEFAULT_INTERVAL_DAYS = 14
DEFAULT_SKIP_WINDOW_DAYS = 3


def _parse_utc(timestamp: str | None) -> datetime | None:
    """Parse a UTC ISO 8601 timestamp string, returning None if null or unparseable."""
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        logging.warning(f"Could not parse timestamp: {timestamp!r}")
        return None


def _days_since(timestamp: str | None) -> float | None:
    """Return days elapsed since a UTC timestamp string. None if timestamp is null."""
    dt = _parse_utc(timestamp)
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def is_scheduled_send_due(state: dict, config: dict) -> tuple[bool, str]:
    """
    Determine whether a scheduled send should fire on this run.

    Checks two conditions in order:
      1. Enough time has passed since the last scheduled send (interval_days)
      2. A threshold email was not sent within the skip window

    Note: the "no open orders" guard belongs in main.py — skip calling this
    function entirely if order_lines is empty.

    Args:
        state: Current state dict from state.json.
        config: Loaded config.json dict.

    Returns:
        Tuple of (should_send: bool, reason: str).
    """
    schedule_cfg = config.get("schedule", {})
    interval_days = schedule_cfg.get("interval_days", DEFAULT_INTERVAL_DAYS)
    skip_window_days = schedule_cfg.get(
        "skip_window_after_threshold_days", DEFAULT_SKIP_WINDOW_DAYS
    )

    days_since_scheduled = _days_since(state.get("last_scheduled_send"))
    days_since_threshold = _days_since(state.get("last_threshold_send"))

    if days_since_scheduled is not None and days_since_scheduled < interval_days:
        reason = (
            f"Scheduled send not due: {days_since_scheduled:.1f} days since last send "
            f"(interval: {interval_days} days)."
        )
        logging.info(reason)
        return False, reason

    if days_since_threshold is not None and days_since_threshold < skip_window_days:
        reason = (
            f"Skipping scheduled send: threshold email sent {days_since_threshold:.1f} days ago "
            f"(skip window: {skip_window_days} days)."
        )
        logging.info(reason)
        return False, reason

    if days_since_scheduled is None:
        reason = f"Scheduled send due: no previous send on record (interval: {interval_days} days)."
    else:
        reason = (
            f"Scheduled send due: {days_since_scheduled:.1f} days since last send "
            f"(interval: {interval_days} days)."
        )

    logging.info(reason)
    return True, reason


def record_scheduled_send(state: dict) -> dict:
    """
    Return updated state dict recording that a scheduled send occurred now.

    Does not write to disk — caller is responsible for persisting via write_state().

    Args:
        state: Current state dict.

    Returns:
        Updated state dict with last_scheduled_send set to now (UTC).
    """
    return {
        **state,
        "last_scheduled_send": datetime.now(timezone.utc).isoformat(),
    }
