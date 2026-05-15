# Bi-Weekly Scheduled Send

## Overview

Build the scheduling logic that triggers a proactive status email to Jordan Brand every two weeks, regardless of whether the volume threshold has been reached.

## Requirements

- Run as part of the daily 5:00 AM execution (not a separate process)
- Check if 14 days have passed since `last_scheduled_send` (from `state.json`)
- Skip if a threshold email was sent within the last 3 days
- Skip if no open Jordan orders exist
- Call email send module (Task 03) with `send_mode = "scheduled"` when conditions are met
- Update `state.json` after each scheduled send
- All timing values (interval, skip window) must be in `config.json`
- Log every schedule check with result and reason

## References

- Full spec: `@feature-spec-03-biweekly-schedule.md`
- State file structure: defined in Spec 03
- Config structure: defined in Spec 03
- Email send: Task 03 must be complete

## Notes

The preferred send day (Wednesday) is TBD — Heather needs to confirm. Build the cadence as interval-based (days since last send) not day-of-week based. This is simpler and more reliable. Day-of-week preference can be added later.

If `state.json` is missing or corrupted on startup, treat all timestamps as null and proceed. Do not crash. Log a warning.

All timestamps stored and compared in UTC to avoid timezone issues on the host machine.

The skip window (3 days after threshold send) prevents Beverly from receiving two emails in close succession. This is a UX decision — keep it configurable so it can be adjusted based on feedback.
