# cm-web known issues

Bugs found by the cm-web test suite and not yet fixed. Each issue has a test
marked `@pytest.mark.xfail(strict=True)` that asserts the intended behavior.
Because the marker is strict, the test is reported as an unexpected pass
(`XPASS`), which fails the run, as soon as the bug is fixed. When you fix an
issue, remove its `xfail` marker and its entry in this log.

To run the known-issue tests as ordinary tests, for example to see how one fails:

```sh
uv run pytest packages/cm-web/web_tests --runxfail -k <test name>
```

## Campaign overview page

### Show Hidden is on for a new user's first visit

- **Test:** [`test_campaign_overview.py::test_show_hidden_is_off_on_first_visit`](test_campaign_overview.py)
- **Where:** [`pages/common.py:64`](../src/lsst/cmservice/web/pages/common.py#L64),
  [`pages/campaign_overview.py:69`](../src/lsst/cmservice/web/pages/campaign_overview.py#L69)
- **What happens:** `CMPage.__init__` builds the page layout, including the
  drawer, before `CampaignOverviewPage.setup()` adds the default `"ignored"`
  filter. On a browser's first visit, the drawer's "Show Hidden" switch is
  created from an empty filter set and starts on, so hiding a campaign
  appears to do nothing. Later visits behave as intended, because the default
  filter has been stored by then.
- **Related:** `toggle_ignored_filter` stores the switch state inverted
  (switching it on adds `"ignored"`), and `setup()` adds `"ignored"` again on
  every load, so the switch state never persists between visits.

### User preferences belong to the browser, not the user

- **Test:** [`test_campaign_overview.py::test_favorites_belong_to_the_user`](test_campaign_overview.py)
- **Where:** [`components/storage.py`](../src/lsst/cmservice/web/components/storage.py)
  (`UserStorageWrapper`)
- **What happens:** favorites, hidden campaigns, active filters, and the owner
  filter are kept in NiceGUI `app.storage.user`, which is keyed by the browser
  session cookie rather than by the `X-Auth-Request-User` identity. Everyone who
  uses the same browser shares the same preferences; for example, a campaign
  that weyland marks as a favorite is also a favorite for yutani.

## Node detail page

### Retry is offered for a node that was never ready

- **Test:** [`test_failure_recovery.py::test_no_retry_for_node_that_never_became_ready`](test_failure_recovery.py)
- **Where:** [`components/dialog.py:188`](../src/lsst/cmservice/web/components/dialog.py#L188)
  (`NodeRecoveryPopup.click`)
- **What happens:** the recovery dialog decides which actions to offer only
  from the node's kind, so "retry" is offered for any failed node that is not
  a breakpoint. A retry moves a node from `failed` to `ready`, which makes no
  sense for a node that failed to prepare (its `waiting → ready` transition)
  and so never entered the `ready` state. The node's activity log shows
  whether it ever reached `ready`.
- **Fixture:** covenant's walter step, which failed to prepare.

### The "became ready" timeline entry shows `None` without an artifact path

- **Test:** [`test_failure_recovery.py::test_ready_entry_without_artifact_path`](test_failure_recovery.py)
- **Where:** [`pages/node_detail.py:271`](../src/lsst/cmservice/web/pages/node_detail.py#L271)
  (`NodeDetailPage.node_activity_timeline`)
- **What happens:** the entry body is built with ``f"`{artifact_path}`" or ""``.
  The f-string is never empty, so the `or ""` fallback never applies, and a
  node without an `artifact_path` in its metadata shows a literal `` `None` ``.

### Recover is still offered after a node is recovered

- **Test:** [`test_failure_recovery.py::test_no_recovery_after_retry`](test_failure_recovery.py)
- **Where:** [`pages/node_detail.py:93`](../src/lsst/cmservice/web/pages/node_detail.py#L93),
  [`pages/node_detail.py:100`](../src/lsst/cmservice/web/pages/node_detail.py#L100)
  (`NodeDetailPage.node_detail_ribbon`)
- **What happens:** the ribbon reads `node = self.model["node"]` before
  `await self.node_status_chip()` fetches the current node and replaces
  `self.model["node"]`, so its `if node["status"] == "failed"` check uses the
  stale status. After a successful retry, the status chip correctly shows
  `ready`, but the "recover" chip is still offered.
- **Fixture:** sulaco's hudson step, retried after it failed while running.

### Step forward is visible for a node of a campaign that is not paused

- **Test:** [`test_failure_recovery.py::test_no_step_forward_for_running_campaign`](test_failure_recovery.py)
- **Where:** [`pages/node_detail.py`](../src/lsst/cmservice/web/pages/node_detail.py)
  (`NodeDetailPage.node_advance_chip`)
- **Intended behavior:** as the method's docstring says, the step forward chip
  is only visible when the node's campaign is paused, since the RPC "process"
  API is for evolving nodes the daemon is not considering, and it is disabled
  when the node is in a terminal state (`failed` or `accepted`).
- **What happens:** the chip binds its visibility to
  `app.storage.client["state"].campaigns[<campaign id>]["status"]`, but the
  node detail page only ever creates an empty entry for the campaign there,
  without a `status`, so the binding never applies and the chip is always
  visible. It is visible for hudson in the paused sulaco campaign as intended,
  but also for dallas, a running node in the running nostromo campaign.
- **Fixture:** nostromo's dallas step.

## Node recovery

### Rescue accepts the failed group when no rescue group was added

- **Test:** [`test_parallel_groups.py::test_rescue_does_not_accept_group_without_rescue`](test_parallel_groups.py)
- **Where:** [`api/nodes.py:80`](../src/lsst/cmservice/web/api/nodes.py#L80)
  (`insert_or_append_node`), [`api/rescue.py`](../src/lsst/cmservice/web/api/rescue.py)
  (`rescue_group`)
- **What happens:** when the graph insert of the rescue group fails with a
  `409 Conflict` (the campaign graph cannot be modified unless the campaign is
  paused), `insert_or_append_node` only notifies the user and returns, so
  `rescue_group` goes on to force-accept the failed group. The result is an
  accepted group with its rescue group created but not in the graph, so the
  failed group's remaining work is never done. The pause at the start of the
  rescue is not checked either, so a failed pause leads to the same result.
- **Fixture:** sulaco's hudson_group_002, after the parallel run of hudson's
  groups.

### The rescue's pause notification has no campaign name

- **Test:** [`test_parallel_groups.py::test_rescue_pause_notification`](test_parallel_groups.py)
- **Where:** [`api/rescue.py:78`](../src/lsst/cmservice/web/api/rescue.py#L78)
  (`rescue_group`)
- **What happens:** the rescue pauses the campaign with
  `toggle_campaign_state(e, {"id": campaign_id})`, a campaign without its name,
  so the notification reads "Pausing campaign " and then " is now paused".
- **Fixture:** sulaco's hudson_group_002.

### Waiting for a recovery action's result fails when it times out

- **Test:** [`test_failure_recovery.py::test_recovery_action_times_out`](test_failure_recovery.py)
- **Where:** [`api/activity.py:32`](../src/lsst/cmservice/web/api/activity.py#L32)
  (`wait_for_activity_to_complete`)
- **What happens:** when no activity log entry appears for a request within
  the time budget, the function reads `r.json()[0]` from the empty result
  before it checks whether it ran out of time, and raises `IndexError`. The
  notification keeps its spinner and "Retrying node..." (or similar) message
  instead of warning "Timed out waiting for result". This affects every
  recovery action and the rescue's force-accept.
- **Fixture:** sulaco's hudson step, retried without the daemon applying the
  status change.

## Manifest editor

### Validating non-canonical YAML needs a second click

- **Test:** [`test_new_campaign.py::test_validate_non_canonical_yaml`](test_new_campaign.py)
- **Where:** [`components/dialog.py`](../src/lsst/cmservice/web/components/dialog.py)
  (`EditorDialog.validate_editor`, `EditorDialog.changed_editor`)
- **What happens:** after it validates the editor's YAML, `validate_editor`
  replaces the editor's text with the same YAML in canonical form
  (`yaml.safe_dump`). When that changes the text, as it does for any valid
  YAML the user formatted differently, the editor's change handler runs after
  the validation and resets the chip to "Not validated", which disables
  "Done". A second click validates the now-canonical text.
- **Fixture:** a new butler manifest on the New Campaign page, with its
  template's `repo` field indented differently.

## Unfinished work

These are incomplete features rather than defects. They have no `xfail` tests
yet, because their intended behavior is not settled.

### Step forward gives no feedback on its progress or result

- **Where:** [`api/nodes.py`](../src/lsst/cmservice/web/api/nodes.py)
  (`fast_forward_node`), [`pages/node_detail.py`](../src/lsst/cmservice/web/pages/node_detail.py)
  (`NodeDetailPage.node_advance_chip`)
- **What happens:** after a click sends `POST /rpc/process`:
  - waiting for the result is commented out
    (`# . await wait_for_activity_to_complete(status_update_url)`), so nothing
    waits for the node's transition to complete;
  - the page is not refreshed, so the node's new status and timeline entry
    appear only when the user reloads the page (the tests reload it);
  - the notification's message is the raw `StatusUpdate` URL;
  - the "Advancing..." label and hourglass icon are written to
    `app.storage.client["state"].nodes`, but the chip is bound to the page's
    node model, so they never appear (and are reset straight away).
- **Exercised by:** [`test_failure_recovery.py::test_recovery_by_reset`](test_failure_recovery.py),
  which works around the missing refresh by reloading the page.

## Open questions

Behavior that may or may not be intended, to be settled before it is tested.

### Rescue design questions

- **Where:** [`api/rescue.py`](../src/lsst/cmservice/web/api/rescue.py)
  (`rescue_group` and the module docstring)
- **Rescuing a rescue:** the rescue name and collections are built from the
  group being rescued, so they nest: a rescue of `hudson_group_002_rescue_1` is
  `hudson_group_002_rescue_1_rescue_2`, with collections ending in
  `…/rescue_001/rescue_002`. A code comment says the run collection should be
  `*/rescue_NNN_version_Y`. Is the nesting intended?
- **Failed or accepted groups:** the module docstring's "Double Check" list
  asks whether rescue should act on a failed group, accepting it as part of
  the workflow as it does now, or only on accepted groups.
- **Resuming afterwards:** the rescue pauses the campaign and leaves it paused,
  so the user must resume it for the rescue group to be processed.

### Requests without a known user are sent as `anonymous`

- **Where:** [`pages/common.py:54`](../src/lsst/cmservice/web/pages/common.py#L54)
  (`CMPage.__init__`), [`lib/client_factory.py:31`](../src/lsst/cmservice/web/lib/client_factory.py#L31)
  (`set_actor_header`)
- **What happens:** when a page request has no `X-Auth-Request-User` header,
  the session's user is set to `settings.default_username` (`anonymous`), and
  every API request the app makes for that session sends
  `X-Auth-Request-User: anonymous`. API routes that require a known actor,
  such as the schedule oneshot API, which rejects a missing or empty actor
  with a `422`, accept these requests as made by a user named `anonymous`.
  A request made outside a client context sends no actor header at all, and
  is rejected.
- **Question:** the ingress always sets the header, so this only affects local
  and dev deployments without one, such as the integration smoketest. Should
  the app refuse to act without a known user there, as the API does, rather
  than act as `anonymous`?

### The graph insert notification says "Node replaced."

- **Where:** [`api/nodes.py:93`](../src/lsst/cmservice/web/api/nodes.py#L93)
  (`insert_or_append_node`)
- **What happens:** a successful insert or append shows "Node replaced.", the
  message of the replace operation (`replace_node`). The intended wording is
  not settled.
