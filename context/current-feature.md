# Current Feature

## Status

Not Started

## Goals

<!-- Add goals here -->

## Notes

<!-- Add notes here -->

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
- Outbound Email — Container Report (task-03): Graph API send, threshold/scheduled modes, Heather-format report body, retry logic, admin alert, python-dotenv integration
- Bi-Weekly Scheduled Send (task-04): is_scheduled_send_due() interval + skip window checks, record_scheduled_send(), UTC timestamp helpers, all timing from config.json
- Inbound Response Handling (task-05): Graph API inbox poll, Jordan reply detection, internal notification, follow-up reminder, one-per-cycle guard, pure state updaters
- Main Orchestration (task-06): main.py entry point wiring all five modules, full pipeline with retry, non-fatal inbox/state-write guards, top-level exception handler, structured run summary
- Testing (task-07): pytest suite covering all five modules — 71 tests, no live network calls, mocked Graph API and Fabric
- VOIDSTTS Filter Fix (task-08): added AND h.VOIDSTTS = 0 to JORDAN_ORDERS_SQL and MISSING_SKUS_SQL to exclude voided/cancelled orders that retain their Batch value in SalesPad
- Posted_Date Filter Fix (task-08 followup): added AND h.Posted_Date = '1900-01-01' to both SQL queries to exclude old partially-shipped orders that were already invoiced but never voided; GP uses 1900-01-01 as null sentinel for unposted orders
- Azure Functions Restructure (task-Restructure): added host.json, daily_trigger/__init__.py, daily_trigger/function.json (timer cron 0 0 10 * * *), and azure-functions + azure-storage-blob to requirements.txt; main.py required no changes
- Azure Blob State Migration (task-Migrate): added load_state_from_blob() and write_state_to_blob() to volume_calculator.py; main.py updated to use blob-backed functions; falls back to local state.json when AZURE_STORAGE_CONNECTION_STRING is unset
- Custom Docker Image with ODBC Driver (task-Custom-docker): Dockerfile based on mcr.microsoft.com/azure-functions/python:4-python3.11, installs msodbcsql18 via Microsoft apt repo, copies app code to /home/site/wwwroot, installs pip dependencies; .dockerignore excludes .env, state.json, tests, logs, and local venv
- Configurable ODBC Driver Name (task-Config): ODBC_DRIVER constant in fabric_client.py now reads from ODBC_DRIVER_NAME env var (defaults to ODBC Driver 18); .env.example created documenting the optional override for Azure Functions Python 3.10 deployment (ODBC Driver 17 pre-installed)
