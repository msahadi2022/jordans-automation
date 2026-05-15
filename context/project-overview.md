# 📦 Jordan Brand Container Load Automation — Project Overview

> **A rule-based automation that monitors open Jordan Brand orders in Microsoft Fabric, calculates container volume daily, and automatically generates and sends shipment report emails — eliminating manual tracking and reducing response time.**

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Background & Current Process](#background--current-process)
3. [Stakeholders](#stakeholders)
4. [Feature Spec](#feature-spec)
5. [Email Specifications](#email-specifications)
6. [Data Architecture](#data-architecture)
7. [Tech Stack](#tech-stack)
8. [Architecture Diagram](#architecture-diagram)
9. [Order Processing Reference](#order-processing-reference)
10. [Open Questions](#open-questions)
11. [Jira Tickets](#jira-tickets)

---

## Problem Statement

Maxwood Furniture ships furniture to Jordan's Furniture via full container loads. The entire coordination process is currently manual:

| Step | Current State | Problem |
|---|---|---|
| Monitor open orders | Heather manually checks SalesPad | Time-consuming, easy to miss new orders |
| Calculate volume | Export to Excel, copy/paste into W&D sheet | Error-prone, slow |
| Decide when to ship | Judgment call, bi-weekly cadence | Inconsistent — Jordan sometimes has to ask |
| Send report to Jordan | Heather manually composes and sends | Delayed communication, human bottleneck |
| Track new orders | Manual re-pull and recalculate | Beverly had to ask on 4/28 — "It's been a few weeks" |

**Result:** Jordan Brand is left waiting for updates. Heather spends hours on manual data work. The relationship depends on one person's availability.

**This automation** replaces the manual monitoring, calculation, and notification steps — running daily and sending status reports to Jordan Brand automatically on a bi-weekly schedule and when the container threshold is reached.

---

## Background & Current Process

Jordan Brand orders arrive via EDI (SPS/TrueCommerce → EDI 850) and are manually entered into SalesPad in the `WH NEW ORDER` queue. Orders accumulate until there is enough volume to fill a container (~2,800 cubic feet).

### Real Example (April–May 2026)
- **April 28:** Beverly emailed Heather asking "Do you have any freight ready?" — illustrating the current reactive communication gap
- **April 29:** Heather sent a manual report showing 2,039 cubes across ~70 orders
- **May 6:** Beverly asked if new orders from 4/30–5/5 were included
- **May 7:** Heather sent an updated report at 2,283 cubes — Jordan approved
- **May 7:** Beverly coordinated pickup with Cargo Transporters for 5/14
- **May 8:** Pickup confirmed by carrier (Cargo #2618015)

This full cycle — from Beverly asking to pickup confirmed — took **10 days** and required **8+ manual emails**. The automation compresses this by proactively sending reports before Jordan has to ask.

### Current Report Format
Heather's emails to Beverly follow a consistent format that the automation must replicate exactly:

```
Weight:   18,015 lbs.
Volume:   2,283 cubes
Cartons:  372

Sales Doc Num   Cust PO Num       Volume - cf   Qty   Short Description   ItemDesc
WH00121966      MAXWC0309600B     5.20          4.00  710705-152          Bed Side Rails...
WH00121967      MAXWC0309601A     11.90         1.00  710331-131          Full Slat...
...
```

---

## Stakeholders

| Person | Role | Involvement |
|---|---|---|
| 🏗️ **Michael Sahadi** | Developer | Project owner — building INT2-410 / INT2-411 |
| 👩‍💼 **Heather Collins** | Sr. Wholesale Coordinator, Maxwood | Current manual process owner. CC'd on all outbound emails. From: address on outbound emails. |
| 👩‍💼 **Rona Szewczyk** | Maxwood internal | CC'd on outbound emails for internal visibility |
| 📦 **Beverly Chartier** | Logistics Manager, Jordan's Furniture | Primary Jordan contact. Approves shipments. CC'd on all emails. |
| 📫 **traffic@jordans.com** | Jordan's logistics inbox | Primary To: address for all outbound emails |
| 🔧 **Matthew Franke** | EDI/Integration Engineer, Maxwood | Owns EDI flows (850/856/810) and downstream SalesPad status updates |
| 📋 **Scott Eide** | Project Lead | Epic owner, escalation decisions |
| 📊 **JJ Lipo** | Data Engineer, Maxwood | Owns Fabric/Hydra workspace and GP pipelines |

---

## Feature Spec

### A. Send Modes

The automation operates in two modes, not one. The real email thread confirmed that Jordan expects regular updates regardless of threshold:

| Mode | Trigger | Description |
|---|---|---|
| 🗓️ **Scheduled Send** | Bi-weekly (e.g. every other Wednesday at 6 AM) | Status update sent to Jordan regardless of volume — keeps them informed so they don't have to ask |
| ⚡ **Threshold Send** | Volume ≥ 2,200 cf (daily check at 5 AM) | Full container report auto-sent when approaching capacity |

> Both modes generate the same report format. The threshold send includes a call-to-action for approval. The scheduled send is informational with an invitation to approve if ready.

---

### B. Daily Volume Calculation

Runs every morning at **5:00 AM**, one hour after the Fabric GP sync (~4:00 AM).

**Logic:**
```
1. Query Fabric Gold for all open Jordan orders
   Filter: Customer_Number IN ('0010033','0010174','0005505')
           Document_Type = 2
           Batch IN ('WH ORDER REVIEW', 'WH NEW ORDER')

2. Join to WDS_Items_Current on shortItemnumber
   → cube / 1728        = Volume per unit (cf)
   → weight             = Weight per unit (lbs)
   → totalBox × Qty     = Carton count per line

3. SUM all line volumes → Total Volume (cf)
   SUM all line weights → Total Weight (lbs)
   SUM all carton counts → Total Cartons

4. Compare to threshold:
   ≥ 2,200 cf → trigger Threshold Send (if not already sent for this batch)
   < 2,200 cf → log result, no action
```

**No persistent counter** — the query always pulls fresh live data. Once orders are moved to `WH PACK LIST` after approval, they automatically drop out of the `Batch` filter.

---

### C. Outbound Email — Container Report

Sent in both Threshold and Scheduled modes. Content is identical; subject line and CTA differ.

**Threshold Send subject:** `Maxwood Furniture — Container Ready for Scheduling`

**Scheduled Send subject:** `Maxwood Furniture — Jordan's Open Order Status Update`

**Recipients:**

| Field | Value |
|---|---|
| To | traffic@jordans.com |
| CC | bchartier@jordans.com (Beverly Chartier) |
| CC | rszewczyk@maxwoodfurniture.com (Rona Szewczyk) |
| From | TBD — licensed M365 mailbox, pending IT provisioning |

---

### D. Inbound Response Handling

Jordan responds via **email reply**. Beverly typically replies within 1–2 days. Jordan has historically always responded — no formal escalation needed.

**Response routing:**

| Signal | Action |
|---|---|
| Jordan approves (email reply) | Operations replies with ready-by date (5 business days from approval). Orders manually moved: `WH ORDER REVIEW → WH PACK LIST → WH SHIP` |
| Jordan requests hold | Container stays open. Orders keep accumulating. Next daily check continues. |
| No response after 2 days | System sends a follow-up reminder email |
| Ambiguous reply | Route to order management inbox for human review |

> **Note:** The ready-by date response ("Next Friday would be the soonest") is currently sent manually by Heather. For INT2-411, determine if this should be auto-calculated (approval date + 5 business days) or prompt Heather to confirm.

---

### E. Bi-Weekly Schedule Logic

The scheduled send ensures Jordan is never in the dark — even when volume hasn't hit threshold.

- **Cadence:** Every other Wednesday (configurable)
- **Condition:** Send regardless of volume — even if only 500 cubes
- **Content:** Same report format with note: *"Let us know if you'd like to approve this batch or wait for more volume to accumulate."*
- **Skip condition:** Don't send a scheduled email within 3 days of a threshold send

---

## Email Specifications

### Report Body Format

```
Weight:   {total_weight} lbs.
Volume:   {total_volume} cubes
Cartons:  {total_cartons}

Sales Doc Num    Cust PO Num         Volume - cf   Qty    Short Description   Item Description
{doc_number}     {po_number}         {line_vol}    {qty}  {short_descr}       {item_desc}
...
```

### Data Sources Per Field

| Email Field | Fabric Table | Field |
|---|---|---|
| Sales Doc Num | `SALESDOC_HEADER` | `Document_Number` |
| Cust PO Num | `SALESDOC_HEADER` | `Customer_PO_Number` |
| Volume - cf (line) | `WDS_Items_Current` | `(cube / 1728) × Quantity` |
| Qty | `SALESDOC_DETAIL` | `Quantity` |
| Short Description | `WDS_Items_Current` | `shortItemnumber` |
| Item Description | `SALESDOC_DETAIL` | `Item_Description` |
| Total Weight | `WDS_Items_Current` | `SUM(weight × Quantity)` |
| Total Volume | `WDS_Items_Current` | `SUM((cube / 1728) × Quantity)` |
| Total Cartons | `WDS_Items_Current` | `SUM(totalBox × Quantity)` |

---

## Data Architecture

**Single data source: Microsoft Fabric Gold data warehouse.**
No SalesPad API, no SharePoint file access required.

### Fabric Connection

| Parameter | Value |
|---|---|
| Endpoint | `h6iki2vuvsmulo2pxnbmbd5xuq-qaya6ajhjclezlpx7lhfvnqrpq.datawarehouse.fabric.microsoft.com` |
| Database | `Gold` |
| Authentication | Azure Active Directory (Device Code flow) |
| Tenant ID | `6aa4903f-acb4-4599-bb4f-bb42c08fb7a4` |
| Daily sync time | ~4:00 AM (from GP) |
| Automation run time | 5:00 AM daily |

### Key Tables

| Table | Purpose | Key Fields |
|---|---|---|
| `dbo.SALESDOC_HEADER` | Order headers | `Document_Number`, `Customer_Number`, `Customer_PO_Number`, `Document_Type`, `Batch` |
| `dbo.SALESDOC_DETAIL` | Line items | `Item_Number`, `Quantity`, `Item_Description`, `Item_Number_Reference` |
| `dbo.WDS_Items_Current` | Physical attributes | `shortItemnumber` (join key), `cube` (in³ ÷ 1728 = cf), `weight` (lbs), `totalBox` (cartons/unit) |
| `dbo.CUSTOMER_DICTIONARY` | Customer lookup | `Customer_Number`, `Customer_Name`, `Customer_Class` |

### Jordan Customer Numbers

| Customer Number | Name | Class |
|---|---|---|
| `0010033` | Jordan's Furniture, Inc. - FD | CONTAINER |
| `0010174` | Jordan's Furniture, Inc | WHOLESALE |
| `0005505` | Jordan's Home Furnishings | CONTAINER |

### SalesPad Batch Values (Queue Stages)

| Batch Value | Meaning | Include in Volume? |
|---|---|---|
| `WH NEW ORDER` | Just arrived, not yet reviewed | ✅ Yes |
| `WH ORDER REVIEW` | Active, awaiting container | ✅ Yes |
| `WH PACK LIST` | Approved, being picked | ❌ No |
| `WH SHIP` | Shipped | ❌ No |
| `COMPLETED` | Done | ❌ No |
| `READY TO INV` | Invoicing | ❌ No |
| All others | Other channels / stages | ❌ No |

### Core SQL Query

```sql
SELECT
    h.Document_Number                       AS Sales_Doc_Num,
    h.Customer_PO_Number                    AS Cust_PO_Num,
    w.shortItemnumber                       AS Short_Description,
    d.Item_Description                      AS Item_Desc,
    d.Quantity                              AS Qty,
    ROUND(w.cube / 1728, 2)                 AS Volume_CF_Per_Unit,
    ROUND(d.Quantity * (w.cube / 1728), 2)  AS Line_Volume_CF,
    w.weight                                AS Weight_Per_Unit,
    d.Quantity * w.weight                   AS Line_Weight_LBS,
    w.totalBox                              AS Cartons_Per_Unit,
    d.Quantity * w.totalBox                 AS Line_Cartons
FROM dbo.SALESDOC_HEADER h
JOIN dbo.SALESDOC_DETAIL d
    ON h.Document_Number = d.Document_Number
JOIN dbo.WDS_Items_Current w
    ON d.Item_Number_Reference = w.shortItemnumber
WHERE h.Customer_Number IN ('0010033', '0010174', '0005505')
AND   h.Document_Type = 2
AND   h.Batch IN ('WH ORDER REVIEW', 'WH NEW ORDER')
ORDER BY h.Document_Number, d.Item_Number
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Language** | Python 3.x | Scheduled script |
| **Data source** | Microsoft Fabric Gold | T-SQL via ODBC |
| **DB driver** | `pyodbc` + `msodbcsql18` | ODBC Driver 18 for SQL Server |
| **Auth** | `azure-identity` — Device Code flow | Azure AD, Tenant ID: `6aa4903f-...` |
| **Email sending** | Microsoft 365 (SMTP or Graph API) | Licensed mailbox, address TBD |
| **Scheduling** | Windows Task Scheduler or Azure Function | Runs daily at 5:00 AM |
| **Hosting** | On-premise office server or Azure | Must have access to Fabric endpoint |

> ⚠️ **This is a rule-based automation, not AI.** Logic is: query → calculate → threshold/schedule check → send. No ML or NLP involved. AI would only be relevant if inbound email reply parsing were required — currently not needed since Jordan's replies are handled manually.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SCHEDULER                                    │
│              Runs daily at 5:00 AM (after ~4 AM GP sync)           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Python Automation Script                        │
│                                                                     │
│  1. Connect to Fabric Gold via ODBC + Azure AD                      │
│  2. Run SQL → JOIN SALESDOC_HEADER + SALESDOC_DETAIL                │
│              + WDS_Items_Current                                    │
│     Filter: Jordan customers, Doc_Type=2,                          │
│             Batch IN ('WH ORDER REVIEW','WH NEW ORDER')            │
│  3. Calculate totals: Volume (cf), Weight (lbs), Cartons            │
│  4. Check: Volume ≥ 2,200 cf? → Threshold Send                     │
│            Bi-weekly schedule? → Scheduled Send                     │
│            Neither? → Log and exit                                  │
│  5. Generate email body from report data                            │
│  6. Send via M365                                                   │
└───────────┬─────────────────────────────────┬───────────────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────┐       ┌─────────────────────────────────────┐
│  Microsoft Fabric     │       │  Microsoft 365 (Email)              │
│  Gold Data Warehouse  │       │                                     │
│                       │       │  To:  traffic@jordans.com           │
│  SALESDOC_HEADER      │       │  CC:  bchartier@jordans.com         │
│  SALESDOC_DETAIL      │       │  CC:  rszewczyk@maxwoodfurniture.com│
│  WDS_Items_Current    │       │  From: TBD (licensed M365 mailbox)  │
│                       │       └─────────────────────────────────────┘
│  Synced from GP       │                        │
│  daily at ~4:00 AM    │                        ▼
└───────────────────────┘       ┌─────────────────────────────────────┐
                                │  Jordan Brand Reviews & Replies     │
                                │                                     │
                                │  APPROVE → Heather sends ready-by   │
                                │           date (5 business days)    │
                                │           Orders: WH ORDER REVIEW   │
                                │           → WH PACK LIST → WH SHIP  │
                                │                                     │
                                │  HOLD    → Container stays open     │
                                │           Accumulation continues    │
                                └─────────────────────────────────────┘
```

---

## Order Processing Reference

Full end-to-end process as documented by Matthew Franke (May 2026):

| Step | Description | Manual/Auto |
|---|---|---|
| 1 | EDI 850 received via TrueCommerce | Auto |
| 2 | Order manually entered into SalesPad → `WH NEW ORDER` | Manual |
| 3 | Order moved `WH NEW ORDER → WH ORDER REVIEW` | Manual |
| 4 | EDI 855 (PO Acknowledgment) sent via TrueCommerce | Manual |
| **5** | **🤖 Automation: Daily volume calc + bi-weekly/threshold email to Jordan** | **Auto** |
| 6 | Jordan approves via email reply | Manual (Jordan) |
| 7 | Operations replies with ready-by date (approval + 5 business days) | Manual |
| 8 | Jordan coordinates carrier pickup | Manual (Jordan) |
| 9 | Orders moved `WH ORDER REVIEW → WH PACK LIST → WH SHIP` | Manual |
| 10 | Warehouse picks orders, generates BOL | Manual |
| 11 | EDI 856 (ASN) created in TrueCommerce | Manual |
| 12 | Carrier picks up load | Manual |
| 13 | WDS closes orders, triggers SalesPad → `COMPLETED` | Auto |
| 14 | Orders auto-move `COMPLETED → READY TO INV` | Auto |
| 15 | BOL number added, orders transferred to invoice | Manual |
| 16 | GP invoices created (`NEW INVOICE` batch) | Auto |
| 17 | Invoices posted (`POST INVOICE`) | Manual (Finance) |
| 18 | EDI 810 (Invoice) sent via TrueCommerce | Manual |

> The automation slots in at **Step 5**, replacing the manual weekly/bi-weekly report that Heather currently prepares.

---

## Open Questions

| # | Question | Owner | Status |
|---|---|---|---|
| 1 | ~~Fabric sync time~~ **Confirmed: ~4:00 AM** | JJ Lipo | ✅ Closed |
| 2 | ~~Jordan approval mechanism~~ **Confirmed: email reply** | Heather Collins | ✅ Closed |
| 3 | ~~Escalation SLA~~ **Confirmed: 1-2 days, send reminder, no formal escalation** | Heather Collins | ✅ Closed |
| 4 | ~~SalesPad status on approval~~ **Confirmed: WH ORDER REVIEW → WH PACK LIST → WH SHIP** | Matthew Franke | ✅ Closed |
| 5 | ~~Email service~~ **Confirmed: Microsoft 365** | Michael Sahadi | ✅ Closed |
| 6 | ~~Carton count field~~ **Confirmed: `WDS_Items_Current.totalBox`** | Michael Sahadi | ✅ Closed |
| 7 | ~~Volume counter reset~~ **Confirmed: implicit via Batch filter — approved orders drop out automatically** | Matthew Franke | ✅ Closed |
| 8 | **From address** — licensed M365 mailbox, address TBD pending IT provisioning | Heather / IT | ⚠️ Pending |
| 9 | **Ready-by date** — should automation auto-calculate (approval + 5 business days) or prompt Heather to confirm before sending? | Scott Eide / Heather | ⚠️ Open |
| 10 | **Bi-weekly cadence** — confirm exact schedule day/time (e.g. every other Wednesday 6 AM) | Heather Collins | ⚠️ Open |
| 11 | **Threshold configurable?** — should 2,200 cf be adjustable without a code change? | Scott Eide | ⚠️ Open |

---

## Jira Tickets

| Ticket | Title | Owner | Status |
|---|---|---|---|
| INT2-50 | Jordan Brand End-to-End EDI & AI Logistics Automation | Scott Eide | In Progress |
| INT2-136 | SalesPad - Logistics Logic (The "Holding" Phase) | Scott Eide | Ready to Develop |
| INT2-347 | Build inbound EDI 850 → SalesPad order creation flow | Matthew Franke | Done |
| INT2-348 | Build outbound EDI 856 (ASN) flow | Matthew Franke | In Progress |
| INT2-349 | Build outbound EDI 810 (Invoice) flow | Matthew Franke | In Progress |
| INT2-394 | Define requirements for container size / threshold logic | Michael Sahadi | In Progress |
| INT2-410 | Research and define automation approach for order email triggers | Michael Sahadi | In Progress |
| INT2-411 | Build order email automation | Michael Sahadi | In Spec |

---

*Last updated: May 12, 2026*
*This automation is rule-based — no AI or ML involved. See INT2-410 for full research findings and INT2-394 for container size requirements.*
