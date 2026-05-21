# Current Feature: Bi-Weekly Scheduled Send

## Status

In Progress

## Goals

- Check if 14 days have passed since `last_scheduled_send` (from `state.json`)
- Skip if a threshold email was sent within the last 3 days
- Skip if no open Jordan orders exist
- Call `email_sender.send_report()` with `mode="scheduled"` when conditions are met
- Update `state.json` after each scheduled send
- All timing values (interval_days, skip_window_after_threshold_days) read from `config.json`
- Log every schedule check with result and reason

## Notes

- Runs as part of daily 5:00 AM execution — not a separate process
- Cadence is interval-based (days since last send), not day-of-week — simpler and easier to change
- Preferred send day (Wednesday) TBD pending Heather's confirmation
- Missing/corrupt `state.json` → treat all timestamps as null, log warning, continue
- All timestamps compared in UTC
- Skip window prevents Beverly receiving two emails in close succession — keep configurable
- Output: `jordan_automation/scheduler.py`
- Full spec: `context/features/task-04-biweekly-schedule.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
- Outbound Email — Container Report (task-03): Graph API send, threshold/scheduled modes, Heather-format report body, retry logic, admin alert, python-dotenv integration
