# Schedules
A *Schedule* creates new campaigns from a set of campaign manifest templates, either on a recurring cadence or on demand.

## Definitions

- `templates`. The campaign manifests a schedule renders into a new campaign. Template variables (`${{ ... }}`) are rendered when the schedule creates the campaign.
- `expressions`. A mapping of variable names to Python expressions, evaluated in a sandbox when the schedule creates a campaign. The result of each expression is available to the templates as a variable of the same name.
- `cron`. The cadence on which an enabled schedule creates campaigns.
- `uri`. The location of an optional external resource that provides the schedule's templates and, optionally, its configuration.

## Running a Schedule
An enabled schedule runs on its `cron` cadence. A schedule that is not enabled can be run once, immediately, with the *oneshot* API (`cm schedules oneshot <id>`).

A oneshot may override or add expressions for that run only, without changing the schedule:

```
cm schedules oneshot <id> -e day_obs=20261101
```

A oneshot override replaces the schedule's expression of the same name. A template that uses `${{ day_obs }}` therefore uses the schedule's own `day_obs` expression, unless a oneshot overrides it.

> [!NOTE]
> Each expression is evaluated on its own, so an expression cannot refer to another expression, and the template filters (e.g., `as_day_obs`) are not available to expressions.

A oneshot's override expressions are evaluated when the oneshot is requested, and the resulting values replace the values of the schedule's expressions of the same name. Each campaign created by a schedule records the values used to render its templates in its `metadata.values`. This record is for people reading a campaign's provenance: a value that is not a JSON type, e.g., a `datetime`, is recorded as a string, so the record cannot be used to render the templates again.

A oneshot may also be given an *idempotency key* (`--idempotency-key`); a second oneshot of the schedule with the same key does not create another campaign, and refers to the campaign the key already created.

## External Resources
A schedule with a `uri` in its configuration loads its templates from the external resource at that location, a YAML file of manifest documents. The resource may also include a `schedule` manifest:

| The resource... | The schedule's configuration and `cron` are owned by | The templates are owned by |
|---|---|---|
| (no `uri`) | CM | CM |
| includes a `schedule` manifest | the resource | the resource |
| does not include a `schedule` manifest | CM | the resource |

When the resource owns the schedule's configuration, the `spec` of its schedule manifest *replaces* the schedule's configuration and `cron` each time the schedule is refreshed from the resource: any field the manifest does not set is reset to its default. The schedule's `uri`, owner, and enabled status are never changed by the resource.

### Refreshing a Schedule
A schedule is refreshed from its external resource only:

- when the schedule is created with a `uri`, or updated with a new `uri`;
- whenever the schedule runs, on its `cron` cadence or as a oneshot, before the new campaign is created;
- on request, with the refresh API (`cm schedules refresh <id>`), which does not create a campaign.

There is no other, automatic, refresh. A change to an external resource does not affect the schedule until one of these happens; use the refresh API to apply the change sooner, e.g., to apply a new `cron` before the schedule next runs.

Each refresh that changes a schedule is recorded in the audit log, with the changed fields.

> [!WARNING]
> An update to a schedule's configuration through the API is applied as requested, even when the schedule's external resource owns its configuration. Such an update lasts only until the schedule is next refreshed, when the resource's schedule manifest replaces it. To change such a schedule's configuration durably, change its external resource.

If the external resource cannot be fetched or is not valid, creating or updating the schedule with that `uri` fails, a refresh fails, and a run creates no campaign; in each case, the schedule keeps its last known configuration.

## Triggering Schedules
A schedule is triggered by a ``cron`` schedule or manually using a "oneshot" API.
A schedule in an "enabled" state is evaluated according to its ``cron`` schedule and the schedule renders a new campaign for every such ``cron`` tick.
A schedule's template expressions are evaluated at the time the schedule is triggered, so expressions that have a temporal component, e.g., those that use ``datetime`` functions, will evaluate wall-clock times consistent with the ``cron`` timing.

### External Triggers
Features may be added to support external triggers for running scheduled campaigns.
Some external triggers, such as an external ``cron`` scheduler that runs a script that calls CM's oneshot API, are not part of the CM ecosystem.

Support for other external triggers, such as Kafka, Slack, Redis, etc., may be added to CM from time to time.
The architecture for supporting external triggers includes:

- A consumer, webhook, or other actor task in the CM deployment receives a *message* on a *channel* for some *source*.
  CM defines a *dispatcher* for this *source* and sends the *message* to it.
- The *dispatcher* matches the message with any available schedule resources present in the CM deployment.
  A schedule may have in its `configuration` field a `triggers` object which is a list of `ScheduleTriggerBinding` objects.
  Each `ScheduleTriggerBinding` object identifies the *source* and *channel* for which the binding is effective, and a *protocol* field, a JMESPath query that defines which messages for this *source*/*channel* trigger the schedule and how they are interpreted.
- If the *dispatcher* matches a message with a schedule, the *message* and the *schedule* are sent to a *handler* specific to the *source* of the message.
- The *handler* applies the binding's *protocol* to the message, to both filter and shape the message payload into a set of override values to merge over the values of the schedule's template expressions.

Because a *protocol* is a JMESPath query, every external trigger source must deliver a message that is, or can be coerced to, JSON.
A source's *handler* is responsible for any such coercion.
The override values a *protocol* produces must be scalars (strings, numbers, or booleans); they are used as they are, and are not evaluated as expressions.

### Kafka Triggers
A CM daemon may run a Kafka Consumer task that reads messages from one or more Kafka topics.
In the Kafka dispatcher, each consumed message is checked against the available schedules using a containment test.
If any schedules include a `ScheduleTriggerBinding` that matches `{"source": "kafka", "channel": topic}`, the message and the schedule are dispatched to a Kafka handler.

The Kafka Handler tests whether the message payload satisfies the schedule's requirements by applying the `protocol` defined in the schedule's `ScheduleTriggerBinding`.
The `protocol` is a JMESPath query string that both filters the message payload and builds a JSON object of override values for the schedule's templates.

For example, the Kafka consumer receives a message with the following payload and sends it to a handler.

```
{
    "type": "prompt_processing",
    "state": "complete",
    "detail": {
        "day_obs": 20260214,
        "rubin-env": "v30",
        "version": "abcdef+ghijkl"
    }
}
```

The handler uses the `ScheduleTriggerBinding.protocol` field to determine whether this message matches the protocol the schedule needs.

The JMESPath query for the message is

```
(type=='prompt_processing' && state=='complete') && {day_obs: detail.day_obs} || `null`
```

This query will produce the JSON object `{"day_obs": 20260214}` when the filter expressions are true, and `null` when they are not.
If the query result is not `null`, then the Handler knows the message matches the protocol needed by the schedule.

> [!NOTE]
> CM supports only plaintext JSON message payloads when consuming Kafka messages.

If the JMESPath query produces a not-`null` result and the resulting object has only scalar, not-`null` fields, then the object is used as the schedule's override values.

The handler passes the schedule and the override values to the CM Daemon's schedule renderer as a "one-shot" operation.
