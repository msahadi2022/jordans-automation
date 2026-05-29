"""
Email generation and delivery for Jordan Brand container reports via Microsoft Graph API.
"""

import logging
import os
import time
from datetime import datetime, timezone

import requests
from azure.identity import ClientSecretCredential, DeviceCodeCredential
from dotenv import load_dotenv

GRAPH_TOKEN_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_SEND_URL = "https://graph.microsoft.com/v1.0/users/{from_address}/sendMail"

SUBJECT_THRESHOLD = "Maxwood Furniture — Container Ready for Scheduling"
SUBJECT_SCHEDULED = "Maxwood Furniture — Jordan's Open Order Status Update"

CTA_THRESHOLD = (
    "This container has reached the scheduling threshold. "
    "Please reply to approve this shipment for pickup scheduling."
)
CTA_SCHEDULED = (
    "This is your scheduled status update. "
    "Let us know if you'd like to approve this batch or wait for more volume to accumulate."
)

# Column widths for the plain-text line-item table
_COL_WIDTHS = {
    "sales_doc_num": 16,
    "cust_po_num": 20,
    "line_volume_cf": 14,
    "qty": 7,
    "short_description": 20,
    "item_description": 0,  # last column — no padding
}


def _get_graph_token(config: dict) -> str:
    """
    Obtain a Microsoft Graph API access token using Azure AD credentials.

    Uses the same auth_mode config flag as fabric_client — device_code for dev,
    service_principal for prod.

    Args:
        config: Loaded config.json dict.

    Returns:
        Bearer token string.
    """
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


def build_report_body(
    order_lines: list[dict],
    totals: dict,
    mode: str,
) -> str:
    """
    Compose the plain-text email body matching Heather's manual report format.

    Args:
        order_lines: List of row dicts from fetch_jordan_orders(), already sorted.
        totals: Dict with total_volume_cf, total_weight_lbs, total_cartons.
        mode: "threshold" or "scheduled" — determines CTA paragraph.

    Returns:
        Plain-text email body string.
    """
    cta = CTA_THRESHOLD if mode == "threshold" else CTA_SCHEDULED

    header = (
        f"Weight:   {totals['total_weight_lbs']:,.0f} lbs.\n"
        f"Volume:   {totals['total_volume_cf']:,.2f} cubes\n"
        f"Cartons:  {totals['total_cartons']:,}\n"
    )

    col_header = (
        f"{'Sales Doc Num':<{_COL_WIDTHS['sales_doc_num']}}"
        f"{'Cust PO Num':<{_COL_WIDTHS['cust_po_num']}}"
        f"{'Volume - cf':<{_COL_WIDTHS['line_volume_cf']}}"
        f"{'Qty':<{_COL_WIDTHS['qty']}}"
        f"{'Short Description':<{_COL_WIDTHS['short_description']}}"
        f"Item Description"
    )
    separator = "-" * (sum(v for v in _COL_WIDTHS.values() if v) + 40)

    rows = []
    for row in order_lines:
        line = (
            f"{str(row.get('sales_doc_num') or ''):<{_COL_WIDTHS['sales_doc_num']}}"
            f"{str(row.get('cust_po_num') or ''):<{_COL_WIDTHS['cust_po_num']}}"
            f"{row.get('line_volume_cf') or 0:<{_COL_WIDTHS['line_volume_cf']}.2f}"
            f"{row.get('qty') or 0:<{_COL_WIDTHS['qty']}.2f}"
            f"{str(row.get('short_description') or ''):<{_COL_WIDTHS['short_description']}}"
            f"{str(row.get('item_description') or '')}"
        )
        rows.append(line)

    table = "\n".join([col_header, separator] + rows)

    return "\n".join([
        cta,
        "",
        header,
        table,
        "",
        "Maxwood Furniture",
    ])


def _build_graph_payload(
    subject: str,
    body_text: str,
    config: dict,
) -> dict:
    """
    Build the Microsoft Graph API sendMail JSON payload.

    Args:
        subject: Email subject line.
        body_text: Plain-text email body.
        config: Loaded config.json dict.

    Returns:
        Dict ready to serialize as JSON for the Graph API request.
    """
    email_cfg = config["email"]

    to_recipients = [
        {"emailAddress": {"address": email_cfg["to"]}}
    ]
    cc_recipients = [
        {"emailAddress": {"address": addr}} for addr in email_cfg.get("cc", [])
    ]

    return {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": f"<pre>{body_text}</pre>",
            },
            "toRecipients": to_recipients,
            "ccRecipients": cc_recipients,
        },
        "saveToSentItems": True,
    }


def send_report(
    order_lines: list[dict],
    totals: dict,
    mode: str,
    config: dict,
) -> bool:
    """
    Generate and send the container report email via Microsoft Graph API.

    Retries once after 30 seconds on failure. Returns True on success.

    Args:
        order_lines: List of row dicts from fetch_jordan_orders().
        totals: Dict from aggregate_totals() with total_volume_cf, total_weight_lbs, total_cartons.
        mode: "threshold" or "scheduled".
        config: Loaded config.json dict.

    Returns:
        True if email was sent successfully, False otherwise.

    Raises:
        ValueError: If order_lines is empty or total_volume_cf is 0.
    """
    if not order_lines or totals.get("total_volume_cf", 0) == 0:
        raise ValueError("send_report called with empty order set — aborting.")

    subject = SUBJECT_THRESHOLD if mode == "threshold" else SUBJECT_SCHEDULED
    body_text = build_report_body(order_lines, totals, mode)
    payload = _build_graph_payload(subject, body_text, config)

    from_address = config["email"]["from"]
    url = GRAPH_SEND_URL.format(from_address=from_address)
    token = _get_graph_token(config)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, 3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()

            logging.info(
                f"Email sent successfully — mode={mode}, to={config['email']['to']}, "
                f"attempt={attempt}, status={response.status_code}"
            )
            return True

        except Exception as e:
            logging.error(f"Email send failed (attempt {attempt}/2): {e}")
            if attempt < 2:
                logging.info("Retrying in 30s...")
                time.sleep(30)

    logging.error(f"Email send failed after 2 attempts — mode={mode}")
    return False


def send_admin_alert(message: str, config: dict) -> None:
    """
    Send a plain-text alert email to the admin on fatal error.

    Best-effort — logs failure but does not raise.

    Args:
        message: Error description to include in the alert body.
        config: Loaded config.json dict.
    """
    admin_email = os.environ.get("ADMIN_ALERT_EMAIL", "msahadi@maxwoodfurniture.com")
    from_address = config["email"]["from"]
    url = GRAPH_SEND_URL.format(from_address=from_address)

    payload = {
        "message": {
            "subject": "Jordan Automation — Error Alert",
            "body": {
                "contentType": "Text",
                "content": (
                    f"Jordan Brand container automation encountered a fatal error:\n\n"
                    f"{message}\n\n"
                    f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
                ),
            },
            "toRecipients": [{"emailAddress": {"address": admin_email}}],
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
        logging.info(f"Admin alert sent to {admin_email}.")
    except Exception as e:
        logging.error(f"Failed to send admin alert: {e}")
