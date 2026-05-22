# Current Feature: Main Orchestration (main.py)

## Status

In Progress

## Goals

- Load config and state once at startup — pass to all modules
- Run full pipeline: connect → fetch → missing SKUs → aggregate → threshold check → schedule check → inbox check
- Threshold send: volume >= 2,200 cf AND not already sent for this batch
- Schedule send: bi-weekly interval elapsed AND skip window not active AND orders exist
- Inbox check after every send: detect replies, send reminder if no reply after 2 days
- On fatal error: log, send admin alert, exit 1
- On zero orders: log and exit 0 — not an error
- On success: log run summary, exit 0
- Never crash silently — top-level try/except catches everything
- Safe to run multiple times per day without duplicate sends

## Notes

- `main.py` is thin — all business logic lives in the five modules; no calculation/formatting here
- Fabric connection wrapped with `with_retry()` (2 attempts, 60s delay)
- State written atomically after each send action via `write_state()`
- Inbox monitor failures are non-fatal — log warning and continue
- State write failures are non-fatal — log warning and continue
- Email send failures already handled in `email_sender.py` — just check return value
- Top-level exception handler: log traceback + admin alert + exit 1
- Config load failure: log error + exit 1 (no alert possible, no config = no From address)
- Output: `jordan_automation/main.py`
- Full spec: `context/features/task-06-main-orchestration.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
- Outbound Email — Container Report (task-03): Graph API send, threshold/scheduled modes, Heather-format report body, retry logic, admin alert, python-dotenv integration
- Bi-Weekly Scheduled Send (task-04): is_scheduled_send_due() interval + skip window checks, record_scheduled_send(), UTC timestamp helpers, all timing from config.json
- Inbound Response Handling (task-05): Graph API inbox poll, Jordan reply detection, internal notification, follow-up reminder, one-per-cycle guard, pure state updaters
