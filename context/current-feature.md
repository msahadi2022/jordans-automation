# Current Feature: Outbound Email — Container Report

## Status

In Progress

## Goals

- Support `threshold` and `scheduled` send modes — different subject lines and CTA language
- Generate email body matching Heather's exact format: summary header (Weight / Volume / Cartons) + line-item table
- Send via Microsoft Graph API (`/v1.0/users/{from}/sendMail`) using Azure AD auth from Task 01
- Recipients from `config.json` — To: traffic@jordans.com, CC: bchartier@jordans.com + rszewczyk@maxwoodfurniture.com
- Retry send once after 30 seconds on failure, then log error and alert admin
- Guard: do not send if `order_lines` is empty or `total_volume_cf` is 0
- Log every send attempt with timestamp, mode, recipients, and success/failure

## Notes

- From address is pending IT provisioning — read from config, use placeholder during dev
- Graph API endpoint: `https://graph.microsoft.com/v1.0/users/{from_address}/sendMail`
- Same Azure AD token pattern as Task 01 — scope: `https://graph.microsoft.com/.default`
- Line-item table column order: Sales Doc Num | Cust PO Num | Volume - cf | Qty | Short Description | Item Description
- Table sorted: Document_Number ASC, Line_Item_Sequence ASC (already ordered by SQL)
- Plain text preferred; fall back to HTML `<table>` if alignment is unacceptable in testing
- Threshold subject: `Maxwood Furniture — Container Ready for Scheduling`
- Scheduled subject: `Maxwood Furniture — Jordan's Open Order Status Update`
- Output: `jordan_automation/email_sender.py`
- Full spec: `context/features/task-03-outbound-email.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
