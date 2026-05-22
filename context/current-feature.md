# Current Feature: Inbound Response Handling

## Status

In Progress

## Goals

- Monitor From mailbox for replies from Jordan Brand addresses (`bchartier@jordans.com`, `traffic@jordans.com`)
- Check for replies since the last outbound send (`last_threshold_send` or `last_scheduled_send`)
- On reply detected: send internal notification to Heather + Rona with sender, timestamp, and reply preview
- On no reply after 2 days: send one follow-up reminder to Jordan (same recipients as original)
- Do not send a second reminder — one per send cycle
- Reset monitoring state when a new outbound email is sent
- Use Microsoft Graph API for inbox read (`Mail.Read` permission)
- Log all detections, notifications, and reminders

## Notes

- Do NOT parse reply for intent (approve vs. hold) — Beverly's replies are conversational; Heather reads and acts manually
- No-response window (2 days) and Jordan reply addresses come from `config.json`
- Graph endpoint: `GET /v1.0/users/{from_address}/messages?$filter=receivedDateTime ge {since}&$select=from,subject,receivedDateTime,bodyPreview`
- Filter by `from.emailAddress.address` against Jordan reply addresses — do not rely on subject line
- State fields: `jordan_reply_received`, `reminder_sent`, `last_jordan_reply`
- `Mail.Read` permission must be granted via Azure AD before testing (coordinate with IT)
- Output: `jordan_automation/inbox_monitor.py`
- Full spec: `context/features/task-05-inbound-response.md`

## History

<!-- Keep this updated. Earliest to latest -->

- Project setup and boilerplate cleanup
- Fabric Connection & Data Pipeline Setup (task-01): ODBC + Azure AD auth, Jordan orders SQL query, result validation, missing SKU detection, structured JSON run logging
- Volume Calculation & Threshold Logic (task-02): aggregate_totals(), threshold check, deduplication via Document_Number set diff, atomic state load/write, evaluate() orchestrator
- Outbound Email — Container Report (task-03): Graph API send, threshold/scheduled modes, Heather-format report body, retry logic, admin alert, python-dotenv integration
- Bi-Weekly Scheduled Send (task-04): is_scheduled_send_due() interval + skip window checks, record_scheduled_send(), UTC timestamp helpers, all timing from config.json
