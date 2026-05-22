# Task 06 — main.py Orchestration

## Overview

Wire all five modules together into the daily 5:00 AM entry point. `main.py` is the only file the scheduler calls — it owns the top-level execution flow, error handling, and exit codes.

## Requirements

- Import and call all five modules in the correct order
- Load config and state once at startup — pass to all modules
- Run the full pipeline: connect → fetch → calculate → threshold check → schedule check → inbox check
- On any fatal error: log, send admin alert, exit with code 1
- On success: log run summary, exit with code 0
- Never crash silently — every exception must be caught at the top level and logged
- The script must be safe to run daily — idempotent, no side effects beyond intended sends

## Execution Flow

```
1. Load config (config.json)
2. Setup logging
3. Load state (state.json)
4. Connect to Fabric Gold (with retry)
5. Fetch Jordan order lines
6. Detect missing SKUs
7. Aggregate totals (volume, weight, cartons)
8. CHECK THRESHOLD
   → If volume >= threshold AND not already sent for this batch:
     → send_report(mode="threshold")
     → update state
9. CHECK SCHEDULE
   → If bi-weekly send is due AND skip window not active:
     → send_report(mode="scheduled")
     → update state
10. CHECK INBOX
    → Detect Jordan replies since last send
    → Send reminder if no reply after 2 days
11. Log run summary
12. Exit 0
```

## Error Handling

|Failure Point                        |Action                                            |
|-------------------------------------|--------------------------------------------------|
|Config file missing                  |Log error, exit 1 — no alert possible             |
|Fabric connection fails (after retry)|Log error, send admin alert, exit 1               |
|SQL query fails                      |Log error, send admin alert, exit 1               |
|Zero order lines returned            |Log “No open Jordan orders”, exit 0 — not an error|
|Email send fails                     |Already handled in email_sender.py — log, continue|
|Inbox monitor fails                  |Log warning, continue — not fatal                 |
|State file write fails               |Log warning, continue — not fatal                 |

## References

- `@CLAUDE.md` — build order, key constants, architecture
- `@coding-standards.md` — logging, error handling patterns
- `@feature-spec-01-volume-calculation.md` — threshold and dedup logic
- `@feature-spec-03-biweekly-schedule.md` — schedule check logic
- `@feature-spec-04-inbound-response.md` — inbox monitor flow

## Notes

`main.py` should be thin — all business logic lives in the modules. If you find yourself writing calculation or formatting logic here, it belongs in a module instead.

Use a top-level `try/except` to catch any unhandled exception, log it with a full traceback, send admin alert, and exit 1:

```python
import traceback

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logging.error(f"Unhandled exception: {e}\n{traceback.format_exc()}")
        try:
            send_admin_alert(f"Unhandled exception: {e}", config)
        except Exception:
            pass  # Best effort — don't crash the crash handler
        sys.exit(1)
```

The scheduler (Windows Task Scheduler or Azure Function) should check the exit code — a non-zero exit means the run failed and should be flagged.

## Acceptance Criteria

- [ ] Single `python main.py` runs the full pipeline end to end
- [ ] Threshold email fires when volume >= 2,200 cf and not already sent
- [ ] Scheduled email fires on correct cadence
- [ ] Inbox check runs after every send
- [ ] Fatal errors exit with code 1 and trigger admin alert
- [ ] Zero order lines exits with code 0 and no email sent
- [ ] Every run produces a structured JSON log entry
- [ ] Script is safe to run multiple times in a day without duplicate sends