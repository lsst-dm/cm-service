##########################################
Campaign Management Web Interface Guide
##########################################

The Campaign Management (CM) web interface is for creating and operating
campaigns: you can build a new campaign, follow a campaign's progress, pause
and resume it, inspect its nodes, and recover nodes that fail.

.. contents:: Contents
   :local:
   :depth: 2


*************
Page layout
*************

Every page has the same frame:

Header
    The page title and breadcrumbs, then the **Campaigns**, **Schedules**, and
    **Notifications** navigation buttons, a menu with your user name (and a
    link to manage your security tokens), and a **menu** button that opens
    the side panel.

Side panel
    Opened with the header's **menu** button, at the right of the page. Its
    contents depend on the page: filters, view options, and tools.

Footer
    Page-specific details, such as the ID of the campaign or node you are
    viewing, and a **help** button that opens the built-in help pages in a new
    tab.

A typical session moves down three levels:

#. **Campaign overview**, the home page, with a card for each campaign.
#. **Campaign detail**, for one campaign: its graph, status, manifests, and
   nodes.
#. **Node detail**, for one node: its status, history, configuration, and
   recovery controls.

Pages do not always update themselves when a campaign changes in the
background. Reload the page to see the latest state.


*******************
Campaign overview
*******************

The home page (``/``) shows a card for each campaign.

Campaign cards
==============

Each card shows:

- the campaign's avatar, which links to its **campaign detail** page;
- the campaign's name, with an icon for its status (hover for the status
  name);
- a count of the campaign's nodes in each status, as colored chips (hover for
  the status name) and the time of the most recent node update;
- the campaign's owner;
- a **run switch**, labeled with the campaign's status. Switch it on to
  resume a paused campaign, or off to pause a running one. The switch is
  disabled once the campaign is finished (``accepted``, ``failed``, or
  ``rejected``);
- a **save as** button with **clone** (make a new campaign from this one's
  graph and configuration) and **export** (not yet available);
- the campaign ID, a **favorite** button (bookmark), and a **hide** button
  (trash can).

Pausing or resuming shows a notification while the change is in progress,
then reports the result, such as "nostromo is now paused".

The **+** button at the bottom right opens the **New Campaign** page (see
`Creating a campaign`_).

Filtering campaigns
===================

Open the side panel to filter the cards. Filters combine: a card is shown only
if it passes all of them.

Favorites
    Show only the campaigns you have marked as favorites.

Filter by Owner
    Show only campaigns with the selected owners. When you are signed in, this
    starts with your own user name, so you initially see your own campaigns;
    remove your name to see everyone's. You can type in an owner name that is
    not in the list. Your choice is remembered.

Filter by Status
    Show only campaigns with any of the selected statuses.

Filter by Name
    Not yet available.

Show Hidden
    Also show the campaigns you have hidden with their **hide** button. Click
    **hide** again on a hidden campaign to show it normally.

Favorites, hidden campaigns, and the owner filter are remembered between
visits (see `Known limitations`_).


*********************
Creating a campaign
*********************

The **+** button on the campaign overview opens the **New Campaign** page.
Nothing is saved until you click **Save** in the side panel.

A new campaign is made of:

- its name and notification labels;
- its **manifests**, configuration documents of different kinds (``lsst``,
  ``bps``, ``butler``, ``wms``, ``site``, ``artifact``) that its steps use;
- its **graph** of steps between ``START`` and ``END``, each with its own
  spec.

Name and notification labels
============================

Campaign Name
    The campaign's name. It is converted to "snake case": spaces become
    underscores, and capitals are kept (``Prometheus Mission`` becomes
    ``Prometheus_Mission``). It starts as ``new_campaign``.

    The footer shows the campaign's ID, which is derived from its name, and
    changes as you change the name.

Notification Labels
    The labels for the campaign's notifications. ``default`` is always
    available.

Manifests
=========

The **Configuration Manifests** section (collapsed at first) has a card for
each of the campaign's manifests, with its kind and name, a button to make it
the campaign's default manifest of its kind, and an **edit** button.

The campaign starts with a copy of the library's default manifest of each
kind, if there is one; a kind without a library default is left out. With no
library defaults, the section is empty.

The **+** button at the end of the section opens the manifest editor for a new
manifest.

The manifest editor
-------------------

#. Enter the manifest's **Name** and choose its **Kind**. These can only be
   set for a new manifest.
#. Click **Apply Template** to fill the editor with every setting of the
   manifest's kind, each with an example or default value. You can also type
   or paste YAML of your own.
#. Edit the YAML.
#. Click the chip under the editor to validate the manifest. Validation checks
   that the YAML is well formed and that it is a correct spec for the kind.
#. Click **Done** to add the manifest to the campaign, or **Cancel** to
   discard it.

The chip shows the manifest's state:

================= ==============================================================
Chip              Meaning
================= ==============================================================
Not validated     The manifest has changed since it was last validated. **Done**
                  is disabled.
Valid!            The manifest is valid. **Done** is enabled.
Invalid!          The manifest is not valid. **Done** is disabled, and an error
                  log beside the editor explains the problem, such as a YAML
                  syntax error, a missing setting, or a setting the kind does
                  not have.
================= ==============================================================

Any edit returns the manifest to "Not validated", so validate it again after
each change. Validation may reformat your YAML.

The **help** button opens a pane with the documentation of the manifest's kind.

Labels
------

**Edit Labels** opens the **Manifest Labels** dialog, for labels that let
steps choose this manifest (see `Selectors`_).

- Enter a **Label Name** and **Label Value**, and click **+** to add the label
  to the list. **+** is disabled until both are entered.
- Click the delete icon of a label to remove it.
- To change a label, click it to copy it back to the inputs, change it, add
  it, and delete the original.
- **Submit** applies the list to the manifest; **Cancel** discards your
  changes.

The graph
=========

The canvas below the manifests shows the campaign's graph. A new campaign
already has ``START`` and ``END``. Drag a step (or a breakpoint) onto the
canvas, and connect the nodes so that every path runs from ``START`` to
``END``.

Click a step to open its editor.

The step editor
---------------

The step editor works like the manifest editor, with these differences:

- The step's **Name** comes from the canvas, and its **Kind** is always
  ``step``; neither can be changed in the editor.
- A new step starts with a placeholder spec: a placeholder
  ``bps.pipeline_yaml`` and no groups. Replace the pipeline with the step's
  own.
- **Grouping** sets how the step is split into groups, by replacing the
  ``groups`` setting with a template (see `Grouping`_). The rest of the spec is
  kept.
- **Edit Selectors** chooses manifests for the step by their labels (see
  `Selectors`_).

**Done** keeps the step's spec for the campaign; **Cancel** discards your
changes, including any to its selectors. Clicking the step again shows the
spec you were last done with. It starts "Not validated", so validate it again
before you click **Done**.

Grouping
--------

========================= =====================================================
Grouping option           Template and what to fill in
========================= =====================================================
No Grouping               ``groups: null``: the step runs as a single group.
                          Nothing to fill in.
Fixed-Value Grouping      ``split_by: values``: one group per value of a data
                          ID dimension. Fill in the ``dimension`` and the
                          ``values``; a value can be a single value, a list of
                          values, or a range (``min``, ``max``, and whether the
                          range includes its ``endpoint``).
Query Grouping            ``split_by: query``: groups made by querying a
                          ``dataset`` for the values of a ``dimension``. Fill
                          in the dataset and dimension, the minimum number of
                          groups (``min_groups``), and the maximum group size
                          (``max_size``).
========================= =====================================================

For example, fixed-value grouping::

    groups:
      split_by: values
      dimension: xenomorph
      values:
      - 1234
      - [2345, 3456, 4567]
      - facehugger
      - {min: 5678, max: 6789, endpoint: true}

and query grouping::

    groups:
      split_by: query
      dataset: species
      dimension: xenomorph
      min_groups: 4
      max_size: 1000000

The fixed-value and query templates do not validate until their placeholders
are filled in.

Selectors
---------

A step uses the campaign's (or the library's) manifests of each kind. A
**selector** chooses which manifest of a kind the step uses, by one of its
labels: a step with the selector ``butler : vessel : nostromo`` uses the
butler manifest labeled ``vessel : nostromo``.

**Edit Selectors** opens the **Manifest Selectors** dialog, which works like the
**Manifest Labels** dialog, but each selector has a **Manifest Kind** as well as
a **Selector Name** and **Selector Value**. The order of selectors does not
matter.

Saving
======

Open the side panel and click **Save**. The campaign, its manifests, its steps
and their specs and selectors, and its graph are saved, and the new campaign's
detail page opens. A new campaign is ``paused``; resume it to start it.

The side panel also has **Export** and **Import**, to download the campaign as
YAML or load one, and **scheduling** options for creating the campaign on a
schedule. These are not covered here.


*****************
Campaign detail
*****************

Open a campaign's detail page from the avatar on its card. The page title's
breadcrumb shows the campaign name.

Campaign graph
==============

The **Campaign Graph** section (collapsed at first; click to expand) draws the
campaign as a flowchart from ``START`` to ``END``. Each node is labeled with
its name and version and filled with the color of its status (see
`Node statuses`_). Click a node to open its **node detail** page.

The zoom button at the top left switches between fitting the graph to the page
and drawing it at full size with scroll bars.

Status gauges
=============

Below the graph are three gauges:

- **Run switch**: pause or resume the campaign, as on its overview card;
- **Nodes**: the share of the campaign's nodes that are ``accepted``;
- **Errors**: the number of failures during the campaign's execution, out of
  all its activity log entries. Every failure counts, including failures of
  nodes that have since been recovered.

Campaign manifests
==================

The **Campaign Manifests** section (collapsed at first) has a card for each of
the campaign's own manifests, with its kind, name, and version, and buttons to
view or edit it and to set it as the campaign's default manifest of its kind.
Library manifests, the global defaults used when a campaign has no manifest of
its own, are not listed here.

Nodes
=====

The rest of the page lists the campaign's nodes, as cards (the default) or as
a table. Choose with **Nodes As** in the side panel.

Each **node card** shows:

- the node's avatar and name, which both link to its **node detail** page;
- its status;
- its kind and version, with a **!** badge when a newer version of the node
  exists;
- when it was last updated;
- a button to view or edit its configuration (not available for ``start``,
  ``end``, and ``breakpoint`` nodes);
- **Other Versions**, when the node has more than one version, to swap in a
  different version.

The **table** lists each node once, at its latest version, with its name,
status, kind, update time, and version, and a view/edit button. It is simpler,
but offers fewer operations than the cards.

Side panel
==========

New Step
    Add a step to the campaign graph.

Nodes As
    Switch the node list between **Cards** and **Table**.

Notifications
    Choose the notification labels applied to the campaign, which control who
    is notified of its activity.

The **save as** button at the bottom right clones or exports the campaign, as
on the overview page.


*************
Node detail
*************

Open a node's detail page from its card (avatar or name), from its row in the
node table, or by clicking it in the campaign graph. The breadcrumbs show the
node's name and version.

The ribbon
==========

Under the header, a row of chips summarizes the node:

- **Campaign**, a link back to the node's campaign;
- the node's kind and version;
- the node's status;
- **recover**, if the node has failed (see `Recovering a failed node`_);
- **step forward**, if the node's campaign is paused (see `Stepping a node
  forward`_);
- **History (Grafana)**, once the node has a BPS run, a link to its history
  dashboard.

Tabs
====

Timeline
    The node's history, newest first: every status change, with its time,
    and the error that caused any failure (for example, "hudson failed to
    finish"), ending with the node's creation. Entries are never removed, so
    the timeline keeps every failure even after the node is recovered. For a
    group with a BPS run, the tab also shows a **BPS Report**: a gauge of the
    share of the workflow's jobs that succeeded, and a table of job counts by
    status for each pipeline task.

Configuration
    Each version of the node's configuration.

Metadata
    The node's metadata, such as its BPS and launcher details.


********************
Statuses and nodes
********************

Campaign statuses
=================

A new campaign starts ``paused``. Its status is one of:

``paused``
    The daemon does not process the campaign. You can change its graph and step
    its nodes forward by hand.

``running``
    The daemon processes the campaign, advancing each of its nodes that has
    work to do.

``accepted``
    The campaign is complete.

``rejected``
    The campaign has been rejected.

A campaign does **not** fail when one of its nodes fails: it stays
``running``, even if the failure leaves it with no work it can do. Watch the
failed-node count on its overview card or the **Errors** gauge.

Node statuses
=============

A node normally moves through ``waiting`` → ``ready`` → ``running`` →
``accepted``. Each step has a name, which appears in timeline entries:

- **prepare** (``waiting`` → ``ready``): the node gets ready to run, for
  example by building its configuration;
- **start** (``ready`` → ``running``): the node launches its work, such as a
  BPS submission;
- **finish** (``running`` → ``accepted``): the node's work is checked and, if
  it succeeded, accepted.

If any of these steps fails, the node becomes ``failed``, and the timeline
shows, for example, "walter failed to prepare".

=============== ============== ================================================
Status          Color          Meaning
=============== ============== ================================================
``waiting``     dark blue      Not yet prepared.
``ready``       light blue     Prepared, not yet started.
``running``     orange         Its work is in progress.
``accepted``    dark green     Done.
``failed``      dark red       A step failed; see `Recovering a failed node`_.
``paused``      yellow         Paused.
``blocked``     dark violet    Its work is held up and needs attention.
``reviewable``  light red      Its result is indeterminate and needs review.
``rejected``    dark red       Rejected.
=============== ============== ================================================

Node kinds
==========

``start``, ``end``
    The entry and exit points of every campaign graph.

``step``
    A unit of pipeline work, defined by a pipeline YAML. When a step prepares,
    it **expands** into a subgraph: one or more ``group`` nodes that follow
    it, and a ``collect_groups`` node after them, all ``waiting``. For
    example, a step ``hudson`` with two groups becomes::

        hudson ─┬─ hudson_group_001 ─┬─ hudson_collect_groups ─ (next step)
                └─ hudson_group_002 ─┘

    The groups only become processable once the step itself is ``accepted``.

``group``
    A part of a step's work, for a subset of its data. Groups run in parallel;
    each runs a BPS workflow.

``collect_groups``
    Gathers the outputs of a step's groups. It waits until all of its groups
    are ``accepted``.

``breakpoint``
    A deliberate stop in the graph, which you accept or reject on its node
    detail page to let the campaign continue.


**********************************
Pausing and stepping a campaign
**********************************

Pausing and resuming
====================

Use the run switch on the campaign's overview card or its detail page. Pause a
campaign before you recover a failed node, or to work through its nodes by
hand; resume it to hand it back to the daemon.

Stepping a node forward
=======================

While a campaign is paused, a node's detail page has a **step forward**
button, which advances the node by one step: ``waiting`` to ``ready``,
``ready`` to ``running``, or ``running`` to ``accepted`` (or ``failed``, if its
work failed). The button is disabled for ``failed`` and ``accepted`` nodes.

The page does not update by itself after a step: reload it to see the node's
new status and timeline entry.


**************************
Recovering a failed node
**************************

#. Pause the node's campaign.
#. Open the failed node's detail page.
#. Click **recover**, choose an action, and confirm it.

While the action is in progress, a notification shows a spinner (for example,
"Retrying node..."); it reports "Node Recovered" when the node has changed
status.

Recovery actions
================

The actions offered depend on the node's kind.

=========== ============ ======================================================
Action      Nodes        What it does
=========== ============ ======================================================
retry       all          Returns the node to ``ready`` without changing its
                         configuration or prepared artifacts, so its work can
                         be started again.
reset       all          Returns the node to ``waiting`` and removes its
                         generated configuration and artifacts. A step's
                         groups and collect node are removed from the graph,
                         and are created again when it next prepares. Data
                         products and collections already written are not
                         checked or removed.
restart     groups       Restarts the group's BPS workflow (a BPS restart)
                         with the same configuration. Needs the group's BPS
                         submit directory and quantum graph.
rescue      groups       Adds a copy of the group to the graph, after it, that
                         runs only the work the failed group did not finish,
                         and accepts the failed group as it is. See `Rescuing
                         a group`_.
accept      all          Marks the node ``accepted`` regardless of its
                         failure. For a group, any partial outputs are
                         included in the step's output.
cancel      all          Closes the dialog without doing anything.
=========== ============ ======================================================

Choosing an action
==================

- If the node failed while running and the cause was transient (for example,
  a lost batch job), **retry** it, then step it forward or resume the
  campaign.
- If the failure came from its configuration or preparation, fix the cause and
  **reset** it, so it prepares again from the start.
- If a group's workflow partly succeeded, **rescue** it to keep the finished
  work and rerun the rest.
- **Accept** a node only if its failure does not matter for the rest of the
  campaign.

Rescuing a group
================

A rescue creates a new group named after the failed one, such as
``hudson_group_002_rescue_1``, with its own output collections, configured to
skip any work already in the failed group's output. The rescue group is put
between the failed group and its collect node, and the failed group is
accepted.

A rescue pauses the campaign for you and leaves it paused: resume the campaign
for the rescue group to be processed. The collect node then waits for the
rescue group instead of the failed one.

After recovering
================

A recovered node continues from its new status: resume the campaign to let
the daemon take over, or keep it paused and **step forward** the node by hand.
If the node fails again, recover it again: its timeline keeps the whole
history.


*********
Example
*********

The ``hudson`` step of a campaign ran, then failed to finish because its batch
job ended abnormally.

#. On the campaign overview, the campaign's card shows a failed node; the
   campaign is still ``running``. Switch it off to pause it.
#. Open the campaign's detail page. ``hudson`` is red in the graph and on its
   card; click it.
#. The timeline shows "hudson failed to finish", with the error. Click
   **recover**, then **retry**, and confirm.
#. When the notification reports "Node Recovered", ``hudson`` is ``ready``.
   Click **step forward** to start it, and reload the page; repeat until it is
   ``accepted``.
#. Resume the campaign. The daemon processes ``hudson``'s groups in parallel.
#. If one group fails, open it and **rescue** it, then resume the campaign
   again. When the rescue group is ``accepted``, the step's collect node is
   next.


*******************
Known limitations
*******************

- **Reload to see changes.** Pages do not update when the daemon or a step
  forward changes a node; reload the page.
- **The recover button stays after recovery.** After a successful recovery
  action, the **recover** button is still shown until you reload the page.
- **Show Hidden starts on.** The first time you open the overview in a
  browser, **Show Hidden** is on, so hidden campaigns are shown. It is off
  from the next visit on.
- **Preferences belong to the browser.** Favorites, hidden campaigns, and the
  owner filter are stored per browser, not per user, so they are shared by
  anyone who uses the same browser.
- **Retry is offered for any failed node,** including a node that failed to
  prepare and so has never been ``ready``. Use **reset** for such a node.
- **Step forward is always shown,** even when the campaign is not paused.
  Only use it for nodes of a paused campaign.
- **Step forward gives little feedback.** Its notification shows a status URL
  rather than a message; reload the page to see the result.
- **Validating reformatted YAML may take two clicks.** When validation
  reformats your YAML, the chip can return to "Not validated" straight away;
  click it again.
- **Open every step before saving.** A step whose editor you never complete is
  saved without a spec.
