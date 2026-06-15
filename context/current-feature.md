# Current Feature — Migrate state.json to Azure Blob Storage

## Status

In Progress

## Goals

- `azure-storage-blob` confirmed in `requirements.txt`
- `_STATE_DEFAULTS` extracted to module-level constant (if not already)
- `load_state_from_blob()` and `write_state_to_blob()` added alongside existing local-file functions
- Both new functions fall back to local `load_state()` / `write_state()` when `AZURE_STORAGE_CONNECTION_STRING` is unset
- `main.py` `run()` updated to call the new blob-backed functions
- All 70 existing pytest tests still pass
- Local run with no `AZURE_STORAGE_CONNECTION_STRING` behaves identically to before

## Notes

- Azure Functions filesystem is ephemeral — `state.json` must live in Blob Storage in production
- `AZURE_STORAGE_CONNECTION_STRING` already configured in Function App settings (Step 3, done)
- Blob container name: `jordan-automation-state`, blob name: `state.json`
- Container must be created manually by Michael via Azure CLI (out of scope for this code task)
- Do NOT delete existing `load_state()` / `write_state()` — they remain as the local-file fallback
- Design: if env var is unset → local file path; if set → blob path

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
