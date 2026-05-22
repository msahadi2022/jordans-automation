"""
Inbound reply detection, internal notification, and follow-up reminder for Jordan Brand emails.
"""

import logging
import os
from datetime import datetime, timezone

import requests
from azure.identity import ClientSecretCredential, DeviceCodeCredential

GRAPH_TOKEN_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_MESSAGES_URL = "https://graph.microsoft.com/v1.0/users/{from_address}/messages"
GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{from_address}/sendMail"

DEFAULT_NO_RESPONSE_WINDOW_DAYS = 2


def _get_graph_token(config: dict) -> str:
    """Obtain a Microsoft Graph API bearer token using auth_mode from config."""
    fabric_cfg = config["fabric"]
    auth_mode = fabric_cfg.get("auth_mode", "device_code")

    if auth_mode == "service_principal":
        client_id = os.environ.get("FABRIC_CLIENT_ID")
        client_secret = os.environ.get("FABRIC_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "FABRIC_CLIENT_ID and FABRIC_CLIENT_SECRET must be set for service_principal auth."
            )
        credential = ClientSecretCredential(
            tenant_id=fabric_cfg["tenant_id"],
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        credential = DeviceCodeCredential(tenant_id=fabric_cfg["tenant_id"])

    return credential.get_token(GRAPH_TOKEN_SCOPE).token


def _last_send_timestamp(state: dict) -> str | None:
    """
    Return the most recent outbound send timestamp (threshold or scheduled).

    Used as the lower bound when querying for Jordan replies.
    """
    timestamps = [
        t for t in [
            state.get("last_threshold_send"),
            state.get("last_scheduled_send"),
        ]
        if t is not None
    ]
    return max(timestamps) if timestamps else None


def fetch_jordan_replies(config: dict, state: dict) -> list[dict]:
    """
    Query the From mailbox for messages received from Jordan addresses since the last send.

    Uses Graph API message filter on receivedDateTime. Filters results by sender address
    against configured Jordan reply addresses — does not rely on subject line.

    Args:
        config: Loaded config.json dict.
        state: Current state dict (used to determine since timestamp).

    Returns:
        List of reply dicts with keys: from_address, subject, received_at, body_preview.
        Empty list if no replies found or no outbound send has occurred yet.
    """
    since = _last_send_timestamp(state)
    if not since:
        logging.info("No outbound send on record — skipping inbox check.")
        return []

    jordan_addresses = set(config.get("inbound", {}).get("jordan_reply_addresses", []))
    from_address = config["email"]["from"]

    url = GRAPH_MESSAGES_URL.format(from_address=from_address)
    params = {
        "$filter": f"receivedDateTime ge {since}",
        "$select": "from,subject,receivedDateTime,bodyPreview",
        "$orderby": "receivedDateTime desc",
        "$top": "50",
    }
    token = _get_graph_token(config)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to fetch inbox messages: {e}")
        return []

    messages = response.json().get("value", [])
    logging.info(f"Inbox query returned {len(messages)} message(s) since {since}.")

    replies = []
    for msg in messages:
        sender = msg.get("from", {}).get("emailAddress", {}).get("address", "").lower()
        if sender in {a.lower() for a in jordan_addresses}:
            replies.append({
                "from_address": sender,
                "subject": msg.get("subject", "(no subject)"),
                "received_at": msg.get("receivedDateTime", ""),
                "body_preview": msg.get("bodyPreview", ""),
            })

    logging.info(f"Found {len(replies)} Jordan reply/replies.")
    return replies


def send_internal_notification(reply: dict, config: dict) -> None:
    """
    Send an internal email to Heather and Rona notifying them of a Jordan reply.

    Args:
        reply: Reply dict from fetch_jordan_replies().
        config: Loaded config.json dict.
    """
    internal_recipients = config["email"].get("internal_notify", [])
    from_address = config["email"]["from"]
    url = GRAPH_SEND_URL.format(from_address=from_address)

    body = (
        f"Jordan Brand has replied to the container report email.\n\n"
        f"From:     {reply['from_address']}\n"
        f"Received: {reply['received_at']}\n"
        f"Subject:  {reply['subject']}\n\n"
        f"Preview:\n{reply['body_preview']}\n\n"
        f"Please review the reply and take appropriate action."
    )

    payload = {
        "message": {
            "subject": "Jordan Brand — Reply Received",
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [
                {"emailAddress": {"address": addr}} for addr in internal_recipients
            ],
        },
        "saveToSentItems": False,
    }

    try:
        token = _get_graph_token(config)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info(f"Internal notification sent to {internal_recipients}.")
    except Exception as e:
        logging.error(f"Failed to send internal notification: {e}")


def should_send_reminder(state: dict, config: dict) -> bool:
    """
    Return True if a follow-up reminder should be sent to Jordan.

    Conditions: outbound email was sent, no reply received, 2+ days elapsed,
    and a reminder has not already been sent this cycle.

    Args:
        state: Current state dict.
        config: Loaded config.json dict.

    Returns:
        True if reminder should be sent.
    """
    if state.get("jordan_reply_received"):
        logging.info("Jordan has already replied — no reminder needed.")
        return False

    if state.get("reminder_sent"):
        logging.info("Reminder already sent this cycle — skipping.")
        return False

    since = _last_send_timestamp(state)
    if not since:
        return False

    try:
        last_send_dt = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        logging.warning(f"Could not parse last send timestamp: {since!r}")
        return False

    window_days = config.get("inbound", {}).get(
        "no_response_window_days", DEFAULT_NO_RESPONSE_WINDOW_DAYS
    )
    elapsed_days = (datetime.now(timezone.utc) - last_send_dt).total_seconds() / 86400

    if elapsed_days < window_days:
        logging.info(
            f"No reminder yet: {elapsed_days:.1f} days elapsed "
            f"(window: {window_days} days)."
        )
        return False

    logging.info(
        f"No reply after {elapsed_days:.1f} days — reminder eligible."
    )
    return True


def send_reminder(config: dict) -> bool:
    """
    Send a follow-up reminder to Jordan Brand (same recipients as the original report).

    Returns True on success.

    Args:
        config: Loaded config.json dict.
    """
    email_cfg = config["email"]
    from_address = email_cfg["from"]
    url = GRAPH_SEND_URL.format(from_address=from_address)

    body = (
        "Hi Beverly,\n\n"
        "Just following up on our recent container report. "
        "Please let us know if you have any questions or if you're ready to approve the shipment.\n\n"
        "Maxwood Furniture"
    )

    payload = {
        "message": {
            "subject": "Maxwood Furniture — Following Up on Container Report",
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": email_cfg["to"]}}],
            "ccRecipients": [
                {"emailAddress": {"address": addr}} for addr in email_cfg.get("cc", [])
            ],
        },
        "saveToSentItems": True,
    }

    try:
        token = _get_graph_token(config)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        logging.info("Follow-up reminder sent to Jordan Brand.")
        return True
    except Exception as e:
        logging.error(f"Failed to send follow-up reminder: {e}")
        return False


def record_reply_received(state: dict, reply: dict) -> dict:
    """
    Return updated state dict recording that a Jordan reply was received.

    Args:
        state: Current state dict.
        reply: Reply dict from fetch_jordan_replies().

    Returns:
        Updated state dict.
    """
    return {
        **state,
        "jordan_reply_received": True,
        "last_jordan_reply": reply["received_at"],
    }


def record_reminder_sent(state: dict) -> dict:
    """
    Return updated state dict recording that a reminder was sent.

    Args:
        state: Current state dict.

    Returns:
        Updated state dict with reminder_sent=True and last_reminder_sent timestamp.
    """
    return {
        **state,
        "reminder_sent": True,
        "last_reminder_sent": datetime.now(timezone.utc).isoformat(),
    }
