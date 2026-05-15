# Current Feature: Volume Calculation & Threshold Logic

## Status

In Progress

## Goals

- Aggregate `line_volume_cf`, `line_weight_lbs`, and `line_cartons` across all qualifying order lines
- Compare total volume against the configurable 2,200 cf threshold from `config.json`
- Implement deduplication — skip threshold re-trigger if no net-new orders since last send (compare `Document_Number` sets against `state.json`)
- Load and write `state.json` atomically; initialize with defaults if missing or corrupt
- Handle empty result set gracefully — log and exit without sending
- Log every run with timestamp, totals, trigger decision, and warnings
- Missing SKUs must be logged but must not crash the script

## Notes

- Threshold (2,200 cf) is ~80% of 2,800 cf container max — always read from `config.json`, never hardcode
- Dedup: compare current `Document_Number` set against `orders_at_last_threshold_send` in state; re-trigger only if new orders are present
- Volume conversion (in³ → cf) happens in SQL (`cube / 1728`) — do not re-convert in Python
- Validate against Heather's April 29 baseline: 2,039 cf / 16,112 lbs / 339 cartons
- Depends on Task 01 (`fabric_client.py`) being complete — it is
- Output: `volume_calculator.py` + `state.json` initial structure
- Full spec: `context/features/task-02-volume-calculation.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
