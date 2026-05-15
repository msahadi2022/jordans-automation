# Inbound Response Handling

## Overview

Build the inbox monitoring module that detects Jordan Brand email replies, notifies the internal team, and sends a follow-up reminder if no response is received within 2 days.

## Requirements

- Monitor the From mailbox for replies from Jordan Brand (`bchartier@jordans.com`, `traffic@jordans.com`)
- Check for replies since the last outbound send (`last_threshold_send` or `last_scheduled_send`)
- On reply detected: send internal notification to Heather and Rona with sender, timestamp, and reply preview
- On no reply after 2 days: send one follow-up reminder to Jordan (same recipients as original)
- Do not send a second reminder — one per send cycle
- Reset monitoring state when a new outbound email is sent
- Use Microsoft Graph API for inbox read (`Mail.Read` permission required)
- Log all inbound detections, notifications, and reminders

## References

- Full spec: `@feature-spec-04-inbound-response.md`
- Internal notification template: defined in Spec 04
- Follow-up reminder template: defined in Spec 04
- State file fields: `jordan_reply_received`, `reminder_sent`, `last_jordan_reply`

## Notes

Do NOT attempt to parse Jordan's reply for intent (approve vs. hold). Beverly's replies are conversational and variable. This module only detects that a reply was received and routes it to Heather. Heather reads it and acts manually.

The no-response window (2 days) and Jordan reply addresses are in `config.json`. The real email thread shows Beverly sometimes takes 1-2 days — do not trigger a reminder sooner.

Graph API endpoint for reading mail:
`GET /v1.0/users/{from_address}/messages?$filter=receivedDateTime ge {since}&$select=from,subject,receivedDateTime,bodyPreview`

Filter replies by checking `from.emailAddress.address` against Jordan reply addresses. Do not rely on subject line matching — Beverly's subjects vary.

`Mail.Read` permission must be granted on the From mailbox via Azure AD before this feature can be tested. Coordinate with IT alongside mailbox provisioning.
