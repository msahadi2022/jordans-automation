# fabric_client.py — Join Key Fix

**File:** `fabric_client.py`  
**From:** Live data testing — May 15, 2026  
**Priority:** Fix before running Task 02

-----

## Root Cause

The JOIN between `SALESDOC_DETAIL` and `WDS_Items_Current` was using the wrong key.

|Field                                  |Format                    |Example         |
|---------------------------------------|--------------------------|----------------|
|`SALESDOC_DETAIL.Item_Number_Reference`|Zero-padded GP item number|`000710735152`  |
|`WDS_Items_Current.itemNumber`         |Same zero-padded format   |`000710735152` ✅|
|`WDS_Items_Current.shortItemnumber`    |Dash-formatted SKU        |`710735-152` ❌  |

The original query joined on `w.shortItemnumber` — wrong field. All rows were excluded by the INNER JOIN, returning 0 results.

Additionally, `SALESDOC_DETAIL` contains non-inventory lines (`NOTES`, `1010`, `TARIFF`) that must be excluded from volume calculation.

-----

## Fix 1 — Update JORDAN_ORDERS_SQL

Change the JOIN condition and add non-inventory filter:

```sql
-- BEFORE
JOIN dbo.WDS_Items_Current w
    ON d.Item_Number_Reference = w.shortItemnumber

-- AFTER
JOIN dbo.WDS_Items_Current w
    ON d.Item_Number_Reference = w.itemNumber
```

Also add to the WHERE clause:

```sql
AND d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
```

Full updated `JORDAN_ORDERS_SQL`:

```python
JORDAN_ORDERS_SQL = """
    SELECT
        h.Document_Number                               AS sales_doc_num,
        h.Customer_PO_Number                            AS cust_po_num,
        w.shortItemnumber                               AS short_description,
        d.Item_Description                              AS item_description,
        d.Quantity                                      AS qty,
        ROUND(w.cube / 1728.0, 2)                       AS volume_cf_per_unit,
        ROUND(d.Quantity * (w.cube / 1728.0), 2)        AS line_volume_cf,
        w.weight                                        AS weight_per_unit,
        ROUND(d.Quantity * w.weight, 2)                 AS line_weight_lbs,
        w.totalBox                                      AS cartons_per_unit,
        CAST(d.Quantity * w.totalBox AS INT)            AS line_cartons
    FROM dbo.SALESDOC_HEADER h
    JOIN dbo.SALESDOC_DETAIL d
        ON h.Document_Number = d.Document_Number
    JOIN dbo.WDS_Items_Current w
        ON d.Item_Number_Reference = w.itemNumber
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    ORDER BY h.Document_Number, d.Line_Item_Sequence
"""
```

-----

## Fix 2 — Update MISSING_SKUS_SQL

Same join key fix and non-inventory filter:

```python
MISSING_SKUS_SQL = """
    SELECT DISTINCT d.Item_Number_Reference AS sku
    FROM dbo.SALESDOC_DETAIL d
    JOIN dbo.SALESDOC_HEADER h ON d.Document_Number = h.Document_Number
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    AND   d.Item_Number_Reference NOT IN (
        SELECT itemNumber FROM dbo.WDS_Items_Current
    )
"""
```

-----

## Verification

After applying fixes, re-run the test command and validate against the baseline:

```bash
source ~/fabric-env/bin/activate && python3 -c "
from fabric_client import load_config, setup_logging, get_fabric_connection, fetch_jordan_orders, detect_missing_skus, log_run_summary

config = load_config('config.json')
setup_logging(config['paths']['log_file'])

conn = get_fabric_connection(config)
order_lines, warnings = fetch_jordan_orders(conn, config)
missing_skus = detect_missing_skus(conn, config)
log_run_summary(order_lines, warnings, missing_skus, reason='Manual test run')

print(f'Total orders: {len({r[\"sales_doc_num\"] for r in order_lines})}')
print(f'Total lines: {len(order_lines)}')
print(f'Total volume: {sum(r[\"line_volume_cf\"] or 0 for r in order_lines):.2f} cf')
print(f'Total weight: {sum(r[\"line_weight_lbs\"] or 0 for r in order_lines):.2f} lbs')
print(f'Total cartons: {int(sum(r[\"line_cartons\"] or 0 for r in order_lines))}')
print(f'Missing SKUs: {len(missing_skus)}')
print(f'Warnings: {len(warnings)}')
"
```

Expected output should show non-zero orders, lines, volume, weight, and cartons.

> ⚠️ Note: The April 29 baseline (2,039 cf / 16,112 lbs / 339 cartons) reflected orders at that point in time. Current totals will differ as new orders have been added since then. What matters is that totals are non-zero and plausible.