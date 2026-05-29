# fabric_client.py — VOIDSTTS Filter Fix

**File:** `fabric_client.py`  
**From:** Heather Collins validation — May 29, 2026  
**Priority:** Fix before production deployment

-----

## Root Cause

The query is returning voided/cancelled orders that were cancelled while still in `WH ORDER REVIEW` or `WH NEW ORDER`. In SalesPad these orders show **Source = Void**, but their `Batch` value doesn’t change when voided — so our `Batch IN ('WH ORDER REVIEW', 'WH NEW ORDER')` filter doesn’t catch them.

The `SALESDOC_HEADER` table has a `VOIDSTTS` field:

- `0` = active/open
- `1` = voided/cancelled

Confirmed via live data:

- `WH00116983` (2022, voided) → `VOIDSTTS = 1` ❌ should be excluded
- `WH00117135` (voided) → `VOIDSTTS = 1` ❌ should be excluded
- `WH00122231` (first genuinely open order) → `VOIDSTTS = 0` ✅ correct

-----

## Fix 1 — Update JORDAN_ORDERS_SQL

Add `AND h.VOIDSTTS = 0` to the WHERE clause:

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
    AND   h.VOIDSTTS = 0
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    ORDER BY h.Document_Number, d.Line_Item_Sequence
"""
```

-----

## Fix 2 — Update MISSING_SKUS_SQL

Same filter:

```python
MISSING_SKUS_SQL = """
    SELECT DISTINCT d.Item_Number_Reference AS sku
    FROM dbo.SALESDOC_DETAIL d
    JOIN dbo.SALESDOC_HEADER h ON d.Document_Number = h.Document_Number
    WHERE h.Customer_Number IN ({customers})
    AND   h.Document_Type = 2
    AND   h.Batch IN ({batches})
    AND   h.VOIDSTTS = 0
    AND   d.Item_Number_Reference NOT IN ('NOTES', '1010', 'TARIFF', 'FREIGHT')
    AND   d.Item_Number_Reference NOT IN (
        SELECT itemNumber FROM dbo.WDS_Items_Current
    )
"""
```

-----

## Verification

After applying the fix, delete `state.json` and run:

```bash
source ~/fabric-env/bin/activate && python main.py
```

Expected result:

- First order in the report should be `WH00122231` or later
- No orders from 2022/2023 should appear
- Total volume should be significantly lower than 13,932 cf
- 0.00 cf lines (discontinued Craft items) should be gone

Send the updated report to Heather Collins for final validation.