"""
Volume aggregation, threshold evaluation, and state management for Jordan Brand container automation.
"""

import json
import logging
import os
from datetime import datetime, timezone

DEFAULT_THRESHOLD_CF = 2200

_STATE_DEFAULTS = {
    "last_threshold_send": None,
    "last_scheduled_send": None,
    "last_reminder_sent": None,
    "last_run": None,
    "jordan_reply_received": False,
    "reminder_sent": False,
    "orders_at_last_threshold_send": [],
    "volume_at_last_threshold_send": None,
}


def load_state(path: str) -> dict:
    """
    Load state file, returning defaults if missing or corrupt.

    Args:
        path: Path to state.json.

    Returns:
        State dict with all expected keys populated.
    """
    try:
        with open(path, "r") as f:
            return {**_STATE_DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"State file issue ({e}). Using defaults.")
        return dict(_STATE_DEFAULTS)


def write_state(state: dict, path: str) -> None:
    """
    Write state atomically to prevent corruption on failure.

    Writes to a .tmp file then renames to the target path.

    Args:
        state: State dict to persist.
        path: Path to state.json.
    """
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp_path, path)


def aggregate_totals(order_lines: list[dict]) -> dict:
    """
    Sum volume, weight, and cartons across all order lines.

    Volume conversion (in³ → cf) is done in SQL — values here are already in cf.
    Null values are treated as zero and logged upstream by fabric_client.

    Args:
        order_lines: List of row dicts from fetch_jordan_orders().

    Returns:
        Dict with total_volume_cf, total_weight_lbs, total_cartons.
    """
    return {
        "total_volume_cf": round(
            sum(row.get("line_volume_cf") or 0 for row in order_lines), 2
        ),
        "total_weight_lbs": round(
            sum(row.get("line_weight_lbs") or 0 for row in order_lines), 2
        ),
        "total_cartons": int(
            sum(row.get("line_cartons") or 0 for row in order_lines)
        ),
    }


def get_order_numbers(order_lines: list[dict]) -> set[str]:
    """Extract the set of unique Document_Numbers from order lines."""
    return {row["sales_doc_num"] for row in order_lines}


def is_threshold_met(total_volume_cf: float, config: dict) -> bool:
    """
    Return True if total volume meets or exceeds the configured threshold.

    Args:
        total_volume_cf: Aggregated volume across all qualifying order lines.
        config: Loaded config.json dict.

    Returns:
        True if volume >= threshold.
    """
    threshold = config.get("threshold", {}).get("volume_cf", DEFAULT_THRESHOLD_CF)
    return total_volume_cf >= threshold


def has_new_orders(current_orders: set[str], state: dict) -> bool:
    """
    Return True if current order set contains any Document_Numbers not in the last threshold send.

    Used to prevent re-triggering the threshold email for the same batch.

    Args:
        current_orders: Set of Document_Number strings from today's query.
        state: Current state dict.

    Returns:
        True if at least one new order is present since the last threshold send.
    """
    previous_orders = set(state.get("orders_at_last_threshold_send") or [])
    return bool(current_orders - previous_orders)


def should_send_threshold(
    total_volume_cf: float, current_orders: set[str], state: dict, config: dict
) -> bool:
    """
    Determine whether to trigger a threshold send.

    Conditions: volume >= threshold AND at least one net-new order since last send.

    Args:
        total_volume_cf: Aggregated volume.
        current_orders: Set of current Document_Numbers.
        state: Current state dict.
        config: Loaded config.json dict.

    Returns:
        True if threshold send should be triggered.
    """
    if not is_threshold_met(total_volume_cf, config):
        return False
    if not has_new_orders(current_orders, state):
        logging.info("Threshold met but no new orders since last send — skipping.")
        return False
    return True


def record_threshold_send(state: dict, current_orders: set[str], total_volume_cf: float) -> dict:
    """
    Update state to record that a threshold send occurred.

    Returns the updated state dict (does not write to disk).

    Args:
        state: Current state dict.
        current_orders: Set of Document_Numbers included in this send.
        total_volume_cf: Volume at the time of send.

    Returns:
        Updated state dict.
    """
    return {
        **state,
        "last_threshold_send": datetime.now(timezone.utc).isoformat(),
        "orders_at_last_threshold_send": sorted(current_orders),
        "volume_at_last_threshold_send": total_volume_cf,
        "jordan_reply_received": False,
        "reminder_sent": False,
    }


def evaluate(order_lines: list[dict], state: dict, config: dict) -> dict:
    """
    Aggregate order data and determine send action for this run.

    Args:
        order_lines: List of row dicts from fetch_jordan_orders().
        state: Current state dict loaded from state.json.
        config: Loaded config.json dict.

    Returns:
        Dict with keys:
          totals          — dict from aggregate_totals()
          current_orders  — set of Document_Numbers
          send_threshold  — bool
          reason          — human-readable string explaining the decision
    """
    if not order_lines:
        logging.info("No qualifying order lines returned. Nothing to evaluate.")
        return {
            "totals": {"total_volume_cf": 0.0, "total_weight_lbs": 0.0, "total_cartons": 0},
            "current_orders": set(),
            "send_threshold": False,
            "reason": "No qualifying orders found.",
        }

    totals = aggregate_totals(order_lines)
    current_orders = get_order_numbers(order_lines)
    threshold = config.get("threshold", {}).get("volume_cf", DEFAULT_THRESHOLD_CF)

    logging.info(
        f"Totals — Volume: {totals['total_volume_cf']} cf, "
        f"Weight: {totals['total_weight_lbs']} lbs, "
        f"Cartons: {totals['total_cartons']} | "
        f"Orders: {len(current_orders)} | Threshold: {threshold} cf"
    )

    send_threshold = should_send_threshold(totals["total_volume_cf"], current_orders, state, config)

    if send_threshold:
        reason = (
            f"Threshold met: {totals['total_volume_cf']} cf >= {threshold} cf "
            f"with {len(current_orders - set(state.get('orders_at_last_threshold_send') or []))} new order(s)."
        )
    elif not is_threshold_met(totals["total_volume_cf"], config):
        reason = f"Below threshold: {totals['total_volume_cf']} cf < {threshold} cf."
    else:
        reason = "Threshold met but no new orders since last send."

    return {
        "totals": totals,
        "current_orders": current_orders,
        "send_threshold": send_threshold,
        "reason": reason,
    }
