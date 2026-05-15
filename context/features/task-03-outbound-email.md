# Outbound Email — Container Report

## Overview

Build the email generation and send module that composes and delivers the Jordan Brand container report email via Microsoft 365.

## Requirements

- Support two send modes: `threshold` and `scheduled` — different subject lines and CTA language
- Generate email body matching Heather's exact manual report format (summary header + line-item table)
- Send via Microsoft Graph API (preferred over SMTP — consistent with Graph API auth used for Fabric)
- Recipients from `config.json` — To: `traffic@jordans.com`, CC: `bchartier@jordans.com`, `rszewczyk@maxwoodfurniture.com`
- Retry send once after 30 seconds on failure, then log error and alert admin
- Do not send if `order_lines` is empty or `total_volume_cf` is 0
- Log every send attempt with timestamp, mode, recipient, success/failure

## References

- Full spec: `@feature-spec-02-outbound-email.md`
- Email templates: defined in Spec 02
- Line-item table formatting: defined in Spec 02
- Project overview (email format reference): `@jordan-automation-project-overview.md`

## Notes

The M365 licensed mailbox From address is pending IT provisioning. Build the module with the From address as a config value — do not block development on this. Use a placeholder during testing.

Use Microsoft Graph API (`/v1.0/users/{from_address}/sendMail`) for sending. This avoids storing M365 passwords and uses the same Azure AD auth pattern already established in Task 01.

The line-item table must sort by `Document_Number` ASC, then `Line_Item_Sequence` ASC. Volume column shows `line_volume_cf` (line total, not per-unit). Match Heather's column order exactly:

```
Sales Doc Num | Cust PO Num | Volume - cf | Qty | Short Description | Item Description
```

Plain text format preferred. If plain text table alignment is unacceptable in testing, fall back to HTML with a simple `<table>`.
