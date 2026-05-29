# Current Feature: VOIDSTTS Filter Fix (task-08)

## Status

In Progress

## Goals

- Add `AND h.VOIDSTTS = 0` to `JORDAN_ORDERS_SQL` WHERE clause to exclude voided/cancelled orders
- Add `AND h.VOIDSTTS = 0` to `MISSING_SKUS_SQL` WHERE clause
- Verify first qualifying order is `WH00122231` or later (no 2022/2023 orders)
- Verify total volume is significantly below 13,932 cf after fix

## Notes

- Root cause: voided orders in SalesPad retain their `Batch` value (`WH ORDER REVIEW` / `WH NEW ORDER`) when voided — they only change `VOIDSTTS` to `1`
- `VOIDSTTS = 0` means active/open; `VOIDSTTS = 1` means voided/cancelled
- Confirmed bad data: `WH00116983`, `WH00117135` — both `VOIDSTTS = 1`, appeared in report
- First valid order confirmed: `WH00122231` with `VOIDSTTS = 0`
- Fix is two SQL constants in `fabric_client.py` only — no logic changes
- After fix: delete `state.json` and run `python main.py` to validate with Heather
- Output: `jordan_automation/fabric_client.py`
- Full spec: `context/features/task-08-followup-fixes.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
- Outbound Email — Container Report (task-03): Graph API send, threshold/scheduled modes, Heather-format report body, retry logic, admin alert, python-dotenv integration
- Bi-Weekly Scheduled Send (task-04): is_scheduled_send_due() interval + skip window checks, record_scheduled_send(), UTC timestamp helpers, all timing from config.json
- Inbound Response Handling (task-05): Graph API inbox poll, Jordan reply detection, internal notification, follow-up reminder, one-per-cycle guard, pure state updaters
- Main Orchestration (task-06): main.py entry point wiring all five modules, full pipeline with retry, non-fatal inbox/state-write guards, top-level exception handler, structured run summary
- Testing (task-07): pytest suite covering all five modules — 70 tests, no live network calls, mocked Graph API and Fabric
