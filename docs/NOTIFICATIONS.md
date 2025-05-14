# Notifications
CM Service has the capability to send alerts or notifications at various phases of campaign processing.

## Slack Notifications
If the environment variable `NOTIFICATIONS__SLACK_WEBHOOK_URL` is set, CM Service will use this address to send notifications to Slack.

> [!NOTE]
> CM Service requires that the Slack Webhook Url be an "app-based webhook" which includes embedded in the URL both the Slack App API key and the target Slack channel. This value should therefore be treated as a secret. CM Service does not support legacy custom integrations incoming webhooks.

## Notification Triggers
CM Service sends notifications when the following states are raised during normal daemon processing:

- A "script" enters a failed state.
- A "Campaign" transitions from a prepared to a running state.
- A "Campaign" node begins running a BPS submit action.
- A "Campaign" node changes state during a BPS report action.
- A "Campaign" enters a terminal state.

Additionally, CM Service may send notifications when a Campaign or element is manually moved into a particular state:

- When a Campaign is rejected.
- When a Campaign is accepted.
