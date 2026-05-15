# Coding Standards — Jordan Brand Container Automation

> Standards for the Python automation codebase (INT2-411). All contributors must follow these conventions. When in doubt, optimize for readability and maintainability over cleverness.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Python Standards](#python-standards)
3. [Configuration](#configuration)
4. [State Management](#state-management)
5. [Error Handling](#error-handling)
6. [Logging](#logging)
7. [SQL](#sql)
8. [Testing](#testing)
9. [Security](#security)

---

## Project Structure

```
jordan_automation/
├── main.py                  # Entry point — orchestrates all modules
├── fabric_client.py         # Fabric connection, auth, SQL execution
├── volume_calculator.py     # Order aggregation and threshold logic
├── email_sender.py          # Email generation and M365 send
├── scheduler.py             # Bi-weekly schedule logic
├── inbox_monitor.py         # Inbound reply detection and routing
├── config.json              # All configurable values — no secrets
├── state.json               # Runtime state (send history, timestamps)
├── jordan_automation.log    # Append-only structured log file
├── requirements.txt         # Pinned dependencies
├── .env                     # Secrets only (never committed to source control)
├── .env.example             # Template showing required env var keys (no values)
└── tests/
    ├── test_volume_calculator.py
    ├── test_email_sender.py
    ├── test_scheduler.py
    └── fixtures/
        ├── sample_orders.json
        └── heather_april29_baseline.json
```

---

## Python Standards

### Version
- **Python 3.11** — match the confirmed development environment
- Virtual environment: `~/fabric-env`
- All dependencies pinned in `requirements.txt` with exact versions (`==` not `>=`)

### Style
- Follow **PEP 8** strictly
- Max line length: **100 characters**
- Use **4 spaces** for indentation — never tabs
- Use **double quotes** for strings

### Type Hints
All function signatures must include type hints:

```python
# ✅ Correct
def calculate_totals(order_lines: list[dict]) -> dict:
    ...

# ❌ Wrong
def calculate_totals(order_lines):
    ...
```

### Docstrings
Every module, class, and public function must have a docstring:

```python
def fetch_jordan_orders(conn: pyodbc.Connection, config: dict) -> list[dict]:
    """
    Fetch all open Jordan Brand order lines from Fabric Gold.

    Filters by qualifying customer numbers, Document_Type = 2,
    and Batch values defined in config. Joins to WDS_Items_Current
    for volume, weight, and carton data.

    Args:
        conn: Active pyodbc connection to Fabric Gold.
        config: Loaded config.json dict.

    Returns:
        List of order line dicts. Empty list if no qualifying orders.

    Raises:
        pyodbc.Error: If the SQL query fails.
    """
```

### Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Variables | `snake_case` | `total_volume_cf` |
| Functions | `snake_case` | `fetch_jordan_orders()` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_THRESHOLD_CF` |
| Classes | `PascalCase` | `FabricClient` |
| Files/modules | `snake_case` | `fabric_client.py` |
| Config keys | `snake_case` | `"volume_cf"` |

### Imports
- Standard library imports first, then third-party, then local — separated by blank lines
- Never use wildcard imports (`from module import *`)
- Prefer explicit imports

```python
# ✅ Correct
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pyodbc
import requests
from azure.identity import DeviceCodeCredential

from fabric_client import get_fabric_connection
from volume_calculator import calculate_totals
```

### Constants
Define module-level constants at the top of the file, below imports:

```python
DEFAULT_THRESHOLD_CF = 2200
DEFAULT_SCHEDULE_INTERVAL_DAYS = 14
DEFAULT_SKIP_WINDOW_DAYS = 3
DEFAULT_NO_RESPONSE_WINDOW_DAYS = 2
CUBE_IN3_TO_CF = 1728.0
```

### Functions
- Keep functions small and single-purpose — one function does one thing
- If a function exceeds ~40 lines, consider breaking it up
- Prefer returning values over modifying in place
- Avoid side effects in calculation functions (pure functions where possible)

```python
# ✅ Correct — pure function, easy to test
def aggregate_totals(order_lines: list[dict]) -> dict:
    return {
        "total_volume_cf": round(sum(line["line_volume_cf"] for line in order_lines), 2),
        "total_weight_lbs": round(sum(line["line_weight_lbs"] for line in order_lines), 2),
        "total_cartons": sum(line["line_cartons"] for line in order_lines),
    }

# ❌ Wrong — mixing aggregation with side effects
def aggregate_and_log(order_lines):
    total = 0
    for line in order_lines:
        total += line["line_volume_cf"]
        logging.info(f"Processing {line['sales_doc_num']}")  # side effect
    return total
```

---

## Configuration

All configurable values live in `config.json`. Nothing is hardcoded in source files except module-level constants used as defaults.

### config.json Structure

```json
{
  "fabric": {
    "endpoint": "h6iki2vuvsmulo2pxnbmbd5xuq-qaya6ajhjclezlpx7lhfvnqrpq.datawarehouse.fabric.microsoft.com",
    "database": "Gold",
    "tenant_id": "6aa4903f-acb4-4599-bb4f-bb42c08fb7a4",
    "auth_mode": "device_code"
  },
  "jordan_customers": ["0010033", "0010174", "0005505"],
  "qualifying_batches": ["WH ORDER REVIEW", "WH NEW ORDER"],
  "threshold": {
    "volume_cf": 2200
  },
  "schedule": {
    "interval_days": 14,
    "skip_window_after_threshold_days": 3
  },
  "inbound": {
    "no_response_window_days": 2,
    "jordan_reply_addresses": ["bchartier@jordans.com", "traffic@jordans.com"]
  },
  "email": {
    "to": "traffic@jordans.com",
    "cc": ["bchartier@jordans.com", "rszewczyk@maxwoodfurniture.com"],
    "from": "TBD",
    "internal_notify": ["hcollins@maxwoodfurniture.com", "rszewczyk@maxwoodfurniture.com"]
  },
  "paths": {
    "state_file": "state.json",
    "log_file": "jordan_automation.log"
  }
}
```

### Loading Config

```python
def load_config(path: str = "config.json") -> dict:
    """Load and return configuration from JSON file."""
    with open(path, "r") as f:
        return json.load(f)
```

### Rules
- `config.json` may be committed to source control — it contains no secrets
- Secrets (passwords, client secrets, API keys) live in `.env` only
- `.env` is never committed — add to `.gitignore`
- Access env vars via `os.environ.get()` with a clear error if missing

```python
import os

client_secret = os.environ.get("FABRIC_CLIENT_SECRET")
if not client_secret:
    raise EnvironmentError(
        "FABRIC_CLIENT_SECRET environment variable is not set. "
        "See .env.example for required variables."
    )
```

---

## State Management

Runtime state (send history, timestamps) is stored in `state.json`. This file is read and written by the automation — never manually edited unless explicitly required for debugging.

### state.json Structure

```json
{
  "last_threshold_send": null,
  "last_scheduled_send": null,
  "last_reminder_sent": null,
  "last_run": null,
  "jordan_reply_received": false,
  "reminder_sent": false,
  "orders_at_last_threshold_send": [],
  "volume_at_last_threshold_send": null
}
```

### Rules
- All timestamps stored in **UTC ISO 8601** format: `"2026-05-07T05:00:00Z"`
- Parse timestamps with `datetime.fromisoformat()` and always use `timezone.utc`
- If `state.json` is missing or malformed, initialize with defaults — never crash
- Write state atomically (write to temp file, then rename) to prevent corruption

```python
import json
import os
from pathlib import Path

def write_state(state: dict, path: str) -> None:
    """Write state atomically to prevent corruption on failure."""
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp_path, path)

def load_state(path: str) -> dict:
    """Load state file, returning defaults if missing or corrupt."""
    defaults = {
        "last_threshold_send": None,
        "last_scheduled_send": None,
        "last_reminder_sent": None,
        "last_run": None,
        "jordan_reply_received": False,
        "reminder_sent": False,
        "orders_at_last_threshold_send": [],
        "volume_at_last_threshold_send": None,
    }
    try:
        with open(path, "r") as f:
            return {**defaults, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.warning(f"State file issue ({e}). Using defaults.")
        return defaults
```

---

## Error Handling

### Principles
- Never use bare `except:` — always catch specific exceptions
- Always log the exception before re-raising or handling
- Distinguish between recoverable errors (retry) and fatal errors (alert + exit)
- The script must never crash silently — every unhandled error must be logged

```python
# ✅ Correct
try:
    conn = get_fabric_connection(config)
except pyodbc.Error as e:
    logging.error(f"Fabric connection failed: {e}")
    send_admin_alert(f"Fabric connection failed: {e}", config)
    raise SystemExit(1)

# ❌ Wrong
try:
    conn = get_fabric_connection(config)
except:
    pass
```

### Retry Pattern

```python
import time

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
```

### Admin Alerts
When a fatal error occurs, send a plain-text alert email to the admin before exiting:

```python
ADMIN_EMAIL = os.environ.get("ADMIN_ALERT_EMAIL", "msahadi@maxwoodfurniture.com")

def send_admin_alert(message: str, config: dict) -> None:
    """Send a plain-text alert email to the admin on fatal error."""
    # Use same email send logic as email_sender.py
    # Subject: "Jordan Automation — Error Alert"
    ...
```

---

## Logging

### Setup

```python
import logging
import json
from datetime import datetime, timezone

def setup_logging(log_path: str) -> None:
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    # Also log to console during development
    logging.getLogger().addHandler(logging.StreamHandler())
```

### Rules
- Use `logging.info()` for normal operations
- Use `logging.warning()` for non-fatal issues (missing SKU, null volume, state file missing)
- Use `logging.error()` for failures that require action (failed send, connection error)
- Never use `print()` in production code — use logging
- Log at the start and end of each major operation
- Every run produces one structured JSON summary entry (see below)

### Structured Run Log Entry

At the end of each run, write a single structured JSON log line:

```python
def log_run_summary(summary: dict) -> None:
    logging.info("RUN_SUMMARY " + json.dumps({
        **summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))
```

**Example output:**
```
2026-05-12T05:01:23Z [INFO] RUN_SUMMARY {"timestamp": "2026-05-12T05:01:23+00:00",
  "total_orders": 42, "total_lines": 117, "total_volume_cf": 1847.3,
  "total_weight_lbs": 14230.5, "total_cartons": 287,
  "threshold_triggered": false, "scheduled_triggered": false,
  "missing_skus": [], "warnings": 0,
  "reason": "Below threshold. Scheduled send not due."}
```

---

## SQL

- All SQL is written in module-level constants or passed as strings — never inline in logic functions
- Use parameterized queries where user/external input is involved
- For config-driven IN clauses (customer numbers, batch values), build the clause in Python and pass the full string — these values come from config, not user input
- Column aliases must match the Python dict keys exactly (no case mismatches)
- Always `ORDER BY` results — never rely on implicit ordering

```python
# ✅ Correct — SQL as a constant, aliases match dict keys
JORDAN_ORDERS_SQL = """
    SELECT
        h.Document_Number                           AS sales_doc_num,
        h.Customer_PO_Number                        AS cust_po_num,
        ...
    FROM dbo.SALESDOC_HEADER h
    JOIN dbo.SALESDOC_DETAIL d ON h.Document_Number = d.Document_Number
    JOIN dbo.WDS_Items_Current w ON d.Item_Number_Reference = w.shortItemnumber
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    ORDER BY h.Document_Number, d.Line_Item_Sequence
"""

# Build IN clause from config — not user input, so string formatting is acceptable
customers = ", ".join(f"'{c}'" for c in config["jordan_customers"])
batches = ", ".join(f"'{b}'" for b in config["qualifying_batches"])
sql = JORDAN_ORDERS_SQL.format(customers=customers, batches=batches)
```

---

## Testing

### Framework
- Use **pytest**
- Tests live in `tests/` directory, mirroring module names
- Test file naming: `test_{module_name}.py`

### Rules
- Every calculation function must have unit tests
- Use fixtures in `tests/fixtures/` for sample data — never hit Fabric or M365 in unit tests
- Mock external calls (`pyodbc`, `requests`, `azure-identity`) using `unittest.mock`
- The April 29 Heather baseline (2,039 cf, 16,112 lbs, 339 cartons) must be a test fixture

### Example

```python
# tests/test_volume_calculator.py
import pytest
from volume_calculator import aggregate_totals

def test_aggregate_totals_matches_baseline(sample_order_lines):
    """Validate against Heather's April 29, 2026 manual report."""
    result = aggregate_totals(sample_order_lines)
    assert result["total_volume_cf"] == pytest.approx(2039.0, rel=0.01)
    assert result["total_weight_lbs"] == pytest.approx(16112.0, rel=0.01)
    assert result["total_cartons"] == 339

def test_aggregate_totals_empty_returns_zeros():
    result = aggregate_totals([])
    assert result["total_volume_cf"] == 0.0
    assert result["total_weight_lbs"] == 0.0
    assert result["total_cartons"] == 0
```

### Running Tests
```bash
source ~/fabric-env/bin/activate
pytest tests/ -v
```

---

## Security

- **Never commit secrets** — `.env` is in `.gitignore`
- **Never log secrets** — no passwords, tokens, or client secrets in log files
- **Never hardcode credentials** — all auth values from environment variables
- **`.env.example`** must be kept up to date with all required variable names (no values)
- Fabric client secret (when Service Principal is set up) goes in env var `FABRIC_CLIENT_SECRET`
- M365 credentials go in env var `M365_CLIENT_SECRET`
- Admin alert email goes in env var `ADMIN_ALERT_EMAIL`

### .env.example
```
# Azure / Fabric
FABRIC_CLIENT_SECRET=

# Microsoft 365
M365_CLIENT_SECRET=

# Admin alerts
ADMIN_ALERT_EMAIL=msahadi@maxwoodfurniture.com
```

---

*Last updated: May 12, 2026*
*Applies to: INT2-411 — Jordan Brand Container Automation*