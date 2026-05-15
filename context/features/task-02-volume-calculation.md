# Volume Calculation & Threshold Logic

## Overview

Build the core daily volume calculation module that aggregates open Jordan Brand order data from Fabric Gold and determines whether to trigger an outbound email.

## Requirements

- Run daily at 5:00 AM via scheduler
- Query Fabric Gold using `fabric_client.py` (Task 01)
- Aggregate `line_volume_cf`, `line_weight_lbs`, and `line_cartons` across all qualifying orders
- Compare total volume against the 2,200 cf threshold (from `config.json`)
- Implement deduplication — do not re-trigger threshold email if no net-new orders since last send
- Log every run with timestamp, totals, trigger decision, and any warnings
- Handle empty result set gracefully — log and exit without sending
- Missing SKUs (no WDS match) must be logged but must not crash the script

## References

- Full spec: `@feature-spec-01-volume-calculation.md`
- Fabric connection: `@feature-spec-05-fabric-connection.md` (Task 01 must be complete)
- SQL query: defined in Spec 01 and Spec 05
- State file structure: defined in Spec 03

## Notes

The threshold of 2,200 cf is ~80% of the 2,800 cf container max. This is configurable — read from `config.json`, never hardcode.

Deduplication uses a state file (`state.json`). Compare current order list (`Document_Number` set) against `orders_at_last_threshold_send`. If the sets are identical, skip. If new orders are present, the threshold is eligible to re-trigger.

The `cube` field in `WDS_Items_Current` is in cubic inches. Divide by 1728 to convert to cubic feet. This conversion happens in SQL — do not do it in Python after the fact.

Validate against Heather's April 29, 2026 manual report as a known-good baseline: 2,039 cf total, 16,112 lbs, 339 cartons.
