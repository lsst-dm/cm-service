# Notifications
CM Service has the capability to send alerts or notifications at various phases of campaign processing.

## Definitions

- `label`. A string identifier for a set of rules defining a notification. A record identified by this label includes a set of filter rules, a secret, and a transport kind.
- `transport`. A Python class that defines a notification mechanism for delivering a notification as a message, e.g., to a Slack channel using an "app-based webhook".
- `secret`. An arbitrary component of a notification label that contains a secret (shared or otherwise) used by the label's transport. Example: a Slack webhook URL.
- `filter`. A three-tuple defined per **label** that specifies what activities should generate notifications. Each filter is a colon-delimited tuple of **node kind**, **from status**, and **to status**.

## Activity Log Records
Every CM node machine transition generates an activity log record, which is added to the database whether the transition is successful or not.
Each of these records includes a "from" and a "to" status (sometimes, in the case of milestone events or other special cases, these are the same state).
Additionally, an activity log record includes a list of **notification labels**, each of which is used to produce notifications.
New activity log records obtain their list of labels from the associated *Campaign*'s configuration. In the absense of this configuration, the new record will instead apply the **default** label.

> [!NOTE]
> If the activity log record's label list is empty, no notifications will be sent. This should not usually be the case, as new activity log entries should always have the **default** label applied when there is no specific *Campaign* configuration.

## Database Triggers
The CM Service database defines an **INSERT** trigger on the activity log table that produces Postgres **NOTIFY** events when new records are added.
One notification is generated for each **label** applied to the new activity log record, and is sent to a **channel** specific to to that label's **kind**, so all "Slack" notifications are sent to the same Postgres notification channel.
These notifications are received by channel listeners, which are set up by the CM Daemon.

> [!NOTE]
> If an activity log record includes a label that does not exist, this notification is sent to the **default** channel instead. This means only "undefined" labels and records that explicitly list labels with the `default` **kind** are sent to the **default** channel.

## Daemon Task
The CM Daemon runs a task for handling notifications. The task sets up listeners for each **kind** of label, which map to **channels** in the database notification system. Each **channel**/**kind** will contain notification events for a single transport, e.g., Slack.

For each message delivered to the **channel**, the Daemon dispatches the message to a handler dedicated to that channel's **transport**.

> [!NOTE]
> Events on the **default** channel are always dispatched using the `default` label, which uses a Slack transport. Without specific configuration, a default Slack transport uses the application's configured default webhook address (set by the `NOTIFICATIONS__SLACK_WEBHOOK_URL` environment variable) as its destination, i.e., its *secret*, and the set of default filters.

### Daemon Task Handler
The Daemon maintains an instance of a transport handler for each kind of message it knows how to send.
This handler receives message payloads that include the **label** and activity log record **id**.
The handler fetches both the **label** and full activity log entry from the database.
The activity log entry is compared to the **filters** defined on the label to determine whether a message needs to be sent using the transport.

> [!NOTE]
> For example, a label with the filter `*:*:failed` will notify on any activity that marks a transition to a `failed` state, so an activity log record for a `start` node that transitions from `waiting` to `ready` will not pass this filter and no notification will be sent.

The Daemon automatically builds a Slack transport handler for the label name "default".

## Default Filters
The default set of notification filters defined in the application are:
- `start:*:running`. This marks the beginning of a Campaign (its `start` node enters the running state).
- `end:running:*`. This marks the end of a Campaign (its `end` node exits the running state).
- `*:*:failed`. This marks any failure of any kind of node in a Campaign.
- `breakpoint:*:running`. This marks the engagement of any `breakpoint` node in a Campaign.

This is the set of filters that are included in new labels (subject to modification) and applied to the "default" label.

## Slack Notifications
CM supports a Slack transport for notification messages.
For **labels** of kind `slack`, the **secret** must be a Slack Webhook URL.
Because Slack Webhook URL are specific to a Slack Channel, different Slack channels require separate **notification labels**, and more than one Slack-based label can be applied to a Campaign's configuration.

> [!NOTE]
> CM Service requires that the Slack Webhook URL be an "app-based webhook" which includes embedded in the URL both the Slack App API key and the target Slack channel. This value should therefore be treated as a secret. CM Service does not support legacy custom integrations incoming webhooks.

## Web GUI
Labels can be reviewed, cloned, or created using the Web GUI's **notifications** page.

A new label is given a name, a secret, and a kind.
A default set of filters is provided for new labels, but these can be modified during creation.
The secret is based on the **kind**, e.g., Slack secrets must be the Webhook URL for the Slack App associated with the label.

A label can be "cloned" and given a new name and secret. The filters are inherited from the cloned label but can be customized for the new copy.

> [!NOTE]
> The Daemon always dispatches events from the `default` channel to the "default" label, so creating additional labels with the `default` kind will have no effect.

> [!NOTE]
> Label secrets can only be added to new (or cloned) notification labels. A secret for an existing label cannot be viewed, edited, or changed using the Web GUI.

## Extending Notifications
New transports may be added to CM to implement notifications to other platforms, such as PagerDuty, an SMS gateway, etc.
When a new transport is implemented, its **kind** must then be added as a channel listener to the Daemon Task and one or more **labels** created with the matching **kind**. The **label** must then be added to the *Campaign* configuration.

It is expected that additional transports may require in their implementation the handling of arbitrary secret components, such as a secure URL, API key, password, etc.
These secrets are always stored as encrypted ciphertext in the database, and the decryption secret is available only to the CM application at runtime.

The secret value is provided to the transport implementation as plaintext bytes at runtime.
If multiple secret values are needed to support a single transport, an engineer should design the secret as a JSON object string and assign this entire string to the `secret` field of a **label**.
The transport implementation can then decode the JSON values from the plaintext at runtime and use them as needed.

For example, if a transport required both a private URL and a bearer token to operate, a stringified JSON object like `'{"url": "https://transport.co/u/abcdefgh", "token": "secrettoken"}'` could be used as the **secret** for a label. The transport implementation could then use `secrets = json.loads(secret)` and subsequently access the `secret["url"]` and `secret["token"]` values as needed.

> [!NOTE]
> The plaintext secrets are usually referred to as strings for convenience, but CM always encodes a string value as bytes in order to apply encryption to the value. The resulting cipher bytes are stored in a database `BYTEA` column.

> [!NOTE]
> CM does not currently support automatic token rotation for existing secrets. Changing the symmetric encryption key will make existing stored secrets unrecoverable.
