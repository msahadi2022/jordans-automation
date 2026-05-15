"""
Fabric Gold connection, authentication, and data retrieval for Jordan Brand orders.
"""

import json
import logging
import os
import struct
import time
from datetime import datetime, timezone
import pyodbc
from azure.identity import ClientSecretCredential, DeviceCodeCredential

FABRIC_TOKEN_SCOPE = "https://database.windows.net/.default"
ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
ODBC_PORT = 1433

JORDAN_ORDERS_SQL = """
    SELECT
        h.Document_Number                               AS sales_doc_num,
        h.Customer_PO_Number                            AS cust_po_num,
        w.shortItemnumber                               AS short_description,
        d.Item_Description                              AS item_description,
        d.Quantity                                      AS qty,
        ROUND(w.cube / 1728.0, 2)                       AS volume_cf_per_unit,
        ROUND(d.Quantity * (w.cube / 1728.0), 2)        AS line_volume_cf,
        w.weight                                        AS weight_per_unit,
        ROUND(d.Quantity * w.weight, 2)                 AS line_weight_lbs,
        w.totalBox                                      AS cartons_per_unit,
        CAST(d.Quantity * w.totalBox AS INT)            AS line_cartons
    FROM dbo.SALESDOC_HEADER h
    JOIN dbo.SALESDOC_DETAIL d
        ON h.Document_Number = d.Document_Number
    JOIN dbo.WDS_Items_Current w
        ON d.Item_Number_Reference = w.itemNumber
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    ORDER BY h.Document_Number, d.Line_Item_Sequence
"""

MISSING_SKUS_SQL = """
    SELECT DISTINCT d.Item_Number_Reference AS sku
    FROM dbo.SALESDOC_DETAIL d
    JOIN dbo.SALESDOC_HEADER h ON d.Document_Number = h.Document_Number
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    AND   d.Item_Number_Reference NOT IN (
        SELECT itemNumber FROM dbo.WDS_Items_Current
    )
"""


def load_config(path: str = "config.json") -> dict:
    """Load and return configuration from JSON file."""
    with open(path, "r") as f:
        return json.load(f)


def setup_logging(log_path: str) -> None:
    """Configure file and console logging. Safe to call multiple times."""
    root = logging.getLogger()
    if root.handlers:
        return
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    root.addHandler(logging.StreamHandler())


def _build_credential(config: dict) -> DeviceCodeCredential | ClientSecretCredential:
    """
    Build an Azure AD credential from config.

    Supports 'device_code' (development) and 'service_principal' (production)
    via the fabric.auth_mode config key. Swapping modes requires no changes
    to calling code.
    """
    fabric_cfg = config["fabric"]
    auth_mode = fabric_cfg.get("auth_mode", "device_code")

    if auth_mode == "service_principal":
        client_id = os.environ.get("FABRIC_CLIENT_ID")
        client_secret = os.environ.get("FABRIC_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise EnvironmentError(
                "FABRIC_CLIENT_ID and FABRIC_CLIENT_SECRET must be set for service_principal auth. "
                "See .env.example for required variables."
            )
        return ClientSecretCredential(
            tenant_id=fabric_cfg["tenant_id"],
            client_id=client_id,
            client_secret=client_secret,
        )

    return DeviceCodeCredential(tenant_id=fabric_cfg["tenant_id"])


def _get_token_struct(credential) -> bytes:
    """Convert an Azure AD token into the byte struct expected by ODBC attr 1256."""
    token = credential.get_token(FABRIC_TOKEN_SCOPE)
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


def get_fabric_connection(config: dict) -> pyodbc.Connection:
    """
    Open and return an authenticated ODBC connection to Fabric Gold.

    Uses Azure AD token injection via attrs_before={1256: token_struct}.

    Args:
        config: Loaded config.json dict.

    Returns:
        Active pyodbc connection.

    Raises:
        EnvironmentError: If required env vars are missing for service_principal auth.
        pyodbc.Error: If the ODBC connection fails.
    """
    fabric_cfg = config["fabric"]
    credential = _build_credential(config)
    token_struct = _get_token_struct(credential)

    conn_str = (
        f"Driver={{{ODBC_DRIVER}}};"
        f"Server={fabric_cfg['endpoint']},{ODBC_PORT};"
        f"Database={fabric_cfg['database']};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
    )

    logging.info(
        f"Connecting to Fabric Gold at {fabric_cfg['endpoint']} "
        f"(auth: {fabric_cfg.get('auth_mode', 'device_code')})"
    )
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
    logging.info("Fabric connection established.")
    return conn


def _build_sql(config: dict) -> str:
    """Inject customer and batch values from config into the SQL template."""
    customers = ", ".join(f"'{c}'" for c in config["jordan_customers"])
    batches = ", ".join(f"'{b}'" for b in config["qualifying_batches"])
    return JORDAN_ORDERS_SQL.format(customers=customers, batches=batches)


def _validate_row(row: dict) -> list[str]:
    """
    Validate a single order line. Returns a list of warning strings (empty if clean).

    Checks for null volume, null weight, and null/empty short_description (missing SKU).
    """
    warnings = []
    if row.get("line_volume_cf") is None:
        warnings.append(f"Null volume on {row.get('sales_doc_num')} / {row.get('cust_po_num')}")
    if row.get("line_weight_lbs") is None:
        warnings.append(f"Null weight on {row.get('sales_doc_num')} / {row.get('cust_po_num')}")
    if not row.get("short_description"):
        warnings.append(f"Missing SKU on {row.get('sales_doc_num')} / {row.get('cust_po_num')}")
    return warnings


def fetch_jordan_orders(conn: pyodbc.Connection, config: dict) -> tuple[list[dict], list[str]]:
    """
    Fetch all open Jordan Brand order lines from Fabric Gold.

    Filters by qualifying customer numbers, Document_Type = 2, and Batch values
    defined in config. Joins to WDS_Items_Current for volume, weight, and carton data.

    Args:
        conn: Active pyodbc connection to Fabric Gold.
        config: Loaded config.json dict.

    Returns:
        Tuple of (order_lines, warnings) where order_lines is a list of row dicts
        and warnings is a list of validation warning strings.

    Raises:
        pyodbc.Error: If the SQL query fails.
    """
    sql = _build_sql(config)
    logging.info("Executing Jordan orders query...")

    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    logging.info(f"Query returned {len(rows)} order lines.")

    all_warnings = []
    for row in rows:
        row_warnings = _validate_row(row)
        for w in row_warnings:
            logging.warning(w)
        all_warnings.extend(row_warnings)

    return rows, all_warnings


def detect_missing_skus(conn: pyodbc.Connection, config: dict) -> list[str]:
    """
    Find Jordan order line items with no matching entry in WDS_Items_Current.

    The main query uses an INNER JOIN, so unmatched SKUs are silently excluded
    from volume totals. This secondary query surfaces those gaps explicitly.

    Args:
        conn: Active pyodbc connection to Fabric Gold.
        config: Loaded config.json dict.

    Returns:
        List of SKU strings missing from WDS_Items_Current.
    """
    customers = ", ".join(f"'{c}'" for c in config["jordan_customers"])
    batches = ", ".join(f"'{b}'" for b in config["qualifying_batches"])
    sql = MISSING_SKUS_SQL.format(customers=customers, batches=batches)

    cursor = conn.cursor()
    cursor.execute(sql)
    missing = [row[0] for row in cursor.fetchall()]

    for sku in missing:
        logging.warning(f"SKU missing from WDS_Items_Current (excluded from totals): {sku}")

    return missing


def with_retry(fn, max_attempts: int = 2, delay_seconds: int = 60, label: str = ""):
    """Execute fn with retry on failure."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            logging.warning(f"{label} attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                logging.info(f"Retrying in {delay_seconds}s...")
                time.sleep(delay_seconds)
            else:
                raise


def log_run_summary(
    order_lines: list[dict],
    validation_warnings: list[str],
    missing_skus: list[str],
    reason: str,
    threshold_triggered: bool = False,
    scheduled_triggered: bool = False,
) -> None:
    """Write a structured JSON summary line to the log at the end of each run."""
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_orders": len({r["sales_doc_num"] for r in order_lines}),
        "total_lines": len(order_lines),
        "total_volume_cf": round(sum(r.get("line_volume_cf") or 0 for r in order_lines), 2),
        "total_weight_lbs": round(sum(r.get("line_weight_lbs") or 0 for r in order_lines), 2),
        "total_cartons": int(sum(r.get("line_cartons") or 0 for r in order_lines)),
        "threshold_triggered": threshold_triggered,
        "scheduled_triggered": scheduled_triggered,
        "missing_skus": missing_skus,
        "validation_warnings": len(validation_warnings),
        "reason": reason,
    }
    logging.info("RUN_SUMMARY " + json.dumps(summary, default=str))
