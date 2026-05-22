"""
Entry point for the Jordan Brand container automation.

Runs daily at 5:00 AM. Wires all five modules together in the correct execution order.
All business logic lives in the individual modules — this file is orchestration only.
"""

import logging
import sys
import traceback
from datetime import datetime, timezone

from dotenv import load_dotenv

from email_sender import send_admin_alert, send_report
from fabric_client import (
    detect_missing_skus,
    fetch_jordan_orders,
    get_fabric_connection,
    load_config,
    log_run_summary,
    setup_logging,
    with_retry,
)
from inbox_monitor import (
    fetch_jordan_replies,
    record_reminder_sent,
    record_reply_received,
    send_internal_notification,
    send_reminder,
    should_send_reminder,
)
from scheduler import is_scheduled_send_due, record_scheduled_send
from volume_calculator import evaluate, load_state, record_threshold_send, write_state

load_dotenv()


def _safe_write_state(state: dict, config: dict) -> None:
    """Write state to disk, logging a warning on failure rather than crashing."""
    try:
        write_state(state, config["paths"]["state_file"])
    except Exception as e:
        logging.warning(f"State file write failed: {e}")


def run() -> None:
    """
    Execute the full daily pipeline.

    Flow:
      1. Load config and state
      2. Connect to Fabric Gold (with retry)
      3. Fetch Jordan order lines + detect missing SKUs
      4. Evaluate threshold send
      5. Evaluate scheduled send
      6. Check inbox for Jordan replies and follow-up reminders
      7. Log run summary
    """
    # --- 1. Config and logging ---
    try:
        config = load_config("config.json")
    except Exception as e:
        print(f"FATAL: Could not load config.json: {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(config["paths"]["log_file"])
    logging.info("=== Jordan automation run started ===")

    state = load_state(config["paths"]["state_file"])

    # --- 2. Fabric connection ---
    try:
        conn = with_retry(
            lambda: get_fabric_connection(config),
            max_attempts=2,
            delay_seconds=60,
            label="Fabric connection",
        )
    except Exception as e:
        logging.error(f"Fabric connection failed after retry: {e}")
        send_admin_alert(f"Fabric connection failed after retry:\n{e}", config)
        sys.exit(1)

    # --- 3. Fetch orders and detect missing SKUs ---
    try:
        order_lines, validation_warnings = fetch_jordan_orders(conn, config)
    except Exception as e:
        logging.error(f"Jordan orders query failed: {e}")
        send_admin_alert(f"Jordan orders SQL query failed:\n{e}", config)
        conn.close()
        sys.exit(1)

    try:
        missing_skus = detect_missing_skus(conn, config)
    except Exception as e:
        logging.warning(f"Missing SKU detection failed (non-fatal): {e}")
        missing_skus = []

    conn.close()

    # --- 4. Zero orders — clean exit ---
    if not order_lines:
        logging.info("No open Jordan orders found. Nothing to do.")
        state = {**state, "last_run": datetime.now(timezone.utc).isoformat()}
        _safe_write_state(state, config)
        log_run_summary([], [], [], reason="No qualifying orders found.")
        logging.info("=== Run complete (no orders) ===")
        return

    # --- 5. Aggregate and evaluate threshold ---
    result = evaluate(order_lines, state, config)
    totals = result["totals"]
    current_orders = result["current_orders"]
    threshold_triggered = False
    scheduled_triggered = False

    if result["send_threshold"]:
        sent = send_report(order_lines, totals, "threshold", config)
        if sent:
            threshold_triggered = True
            state = record_threshold_send(state, current_orders, totals["total_volume_cf"])
            _safe_write_state(state, config)

    # --- 6. Evaluate scheduled send ---
    schedule_due, _ = is_scheduled_send_due(state, config)
    if schedule_due:
        sent = send_report(order_lines, totals, "scheduled", config)
        if sent:
            scheduled_triggered = True
            state = record_scheduled_send(state)
            _safe_write_state(state, config)

    # --- 7. Inbox check (non-fatal) ---
    try:
        replies = fetch_jordan_replies(config, state)
        if replies:
            for reply in replies:
                send_internal_notification(reply, config)
            state = record_reply_received(state, replies[0])
            _safe_write_state(state, config)

        if should_send_reminder(state, config):
            sent = send_reminder(config)
            if sent:
                state = record_reminder_sent(state)
                _safe_write_state(state, config)

    except Exception as e:
        logging.warning(f"Inbox check failed (non-fatal): {e}")

    # --- 8. Finalize ---
    state = {**state, "last_run": datetime.now(timezone.utc).isoformat()}
    _safe_write_state(state, config)

    log_run_summary(
        order_lines,
        validation_warnings,
        missing_skus,
        reason=result["reason"],
        threshold_triggered=threshold_triggered,
        scheduled_triggered=scheduled_triggered,
    )

    logging.info("=== Jordan automation run complete ===")


if __name__ == "__main__":
    config: dict = {}
    try:
        config = load_config("config.json")
    except Exception:
        pass

    try:
        run()
    except Exception as e:
        logging.error(f"Unhandled exception:\n{traceback.format_exc()}")
        try:
            send_admin_alert(f"Unhandled exception:\n{e}\n\n{traceback.format_exc()}", config)
        except Exception:
            pass
        sys.exit(1)
