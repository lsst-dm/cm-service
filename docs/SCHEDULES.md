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
