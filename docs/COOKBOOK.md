# My Campaign Is ...

## Running and I Want the Status
...

## Running and I Want to Change Something
...

# My Node Is ...

## Still Running After A Long Time
Nodes that are in a `running` state should eventually enter one terminal state or another.
Especially long-running nodes, like those that execute large BPS Workflows, can run for several hours until the workflow completes.
Behind the scenes, CM Service periodically checks on these with the equivalent of a `bps report`.

If you would like to check on a long-running node yourself, CM Service can help locate the BPS submit directory you should inspect.

...

## Blocked
NOdes enter the blocked state when the WMS jobs they depend upon are HELD.
CM Service considers these states terminal in that they are unlikely to progress without intervention.
After the jobs are unblocked, the blocked state persists in CM Service until the intervention has been acknowledged.
A pilot may either mark the node as accepted if the intervention has resulted in a successful outcome or ask CM Service to re-check the node and make its own determination.

*Marking a Blocked Node as Accepted*
...

*Requesting Re-Check of a Blocked Node*
...

## Failed
Nodes become failed when CM Service determines that the WMS jobs they depend upon have entered an unsuccessful terminal state.
Usually, if a BPS workflow has failed jobs but otherwise has successfully run its `finalJob`, CM Service considers this node `accepted` and defers other qualitative analysis to a subsequent `pipetask report` output.
A node that is actually marked as failed can be inspected for its failure reason and/or reset (in order to try again).

*Checking the Diagnostic Message of a Failed Node*
CM Service tries to capture a diagnostic message for failed nodes.
This will produce any diagnostic messages found with that node; there may be more than one if the node was run multiple times with an error result.

```
...
```

Or, use the failed node's ID as a variable with a provided `jq` filter.

```
...
```

*Resetting a Failed Script to Retry*
If a script is in a `failed` state, the script can be directly retried by resetting its status.
This will set the script status back to `waiting` which signals the CM Daemon to run it from that point.
Resetting a script in this way may not clean up all artifacts created by the script when it was previously run.

```
cm-client script action reset --row_id XXX
```

### ...and I fixed it!
If CM Service failed to run a script but you managed to correct the failure out-of-band, such as by performing the script's action manually, you can manually register this success with CM Service by forcing the associated Job into an accepted state. This requires that you also provide the name of the Job's output run collection even if it is not different to the extant configuration.

```
cm-client job action accept --force --row_id XXX --run-collection XXX
```

## Not Needed (Skipping Part of a Graph)
Sometimes a campaign graph contains work that should not run.
For example, a step may create more groups than should actually run, or a whole step in the campaign graph should be skipped.
In CM Service, the way to skip a node is to **reject** it.

A `rejected` node is treated by the CM Daemon as a finished node that can be passed over: nodes downstream of it continue to be processed.
When a step's `collect_groups` node prepares, it only chains together the run collections of groups that are `accepted`, so the output of a rejected group is left out of the step's output collection.
This is different from a `failed` node, which blocks every path through it until a pilot intervenes.

> [!IMPORTANT]
> Only an `accepted` node can be rejected.
> A `waiting` or `failed` node cannot be rejected directly; the request is ignored and the node's status does not change.
> To skip such a node, force it into the `accepted` state first, then reject it.

*Rejecting a Node*
Pause the campaign first.
While the node is briefly `accepted`, the CM Daemon treats it as a success, so a running campaign could move downstream work forward before the rejection lands.
A `waiting` group has never run, so its run collection probably does not exist; if the step's collect node prepares during that window, it will try to chain a collection that is not there.

```
cm campaigns set <campaign> paused
cm nodes set <node-uuid> accepted --force
cm nodes set <node-uuid> rejected
cm campaigns start <campaign>
```

*Skipping Some of a Step's Groups*
After a step has prepared and created its groups, reject each group that should not run, using the commands above.
The step's collect node still runs once the remaining groups are `accepted`, and its output collection includes only those accepted groups.

*Skipping a Whole Step*
Reject the step node while it is still `waiting`, before it prepares.
A step creates its groups and its collect node when it prepares, so a step rejected before then never adds them to the graph, and later steps do not include any output from it in their input collections.

> [!WARNING]
> Rejecting a step *after* it has prepared does not skip its groups or its collect node; they are already in the graph and will still be processed.
> Later steps chain in the output collection of every earlier collect node, whatever its status, so rejecting a collect node does not remove its output from later steps either.

# My Database Is ...

## Working fine but I want to back it up
Outside of a managed database hosting environment, database maintenance tasks are not necessarily scheduled or handled by default.
In these cases, and especially for development and/or debugging purposes, an operator may want to manually back up a CM Service database for recovery or development snapshot purposes.

### Using pg_dump
The canonical tool for backing up a PosgreSQL database is the `pg_dump` tool. An example command line invocation follows. This backs up the "public" schema for a database named "cmservice". Variable arguments include the host, port, and output file path. Credentials or secret information is not given in this tool invocation and should be stashed in the environment in the usual way.

```
pg_dump --verbose --host=localhost --port=... --format=c --encoding=UTF-8 --inserts --no-privileges --clean --create --file /path/to/dump-cmservice-YYYYmmddHHMM.sql -n public cmservice
```

## Empty and I want to fill it up
For development and debugging purposes, having a copy of a CM Service database available is useful.
The most supported way of setting up a dev-test database is to use the Docker Compose tooling provided in the repo.
Together with the Alembic migration tool, a properly-structured but *empty* database can be created quite quickly using the `make migrate` command.

Following the creation of a Database container and the Alembic migration, a database backup can be restored into the target local database (see "Using pg_dump" above).

> [!WARNING]
> It is important to be sure which database one is manipulating in this way. Be sure no production or otherwise unintended databases are available to your client via port forwarding or configured via environment variables before proceeding.

> [!IMPORTANT]
> The Docker Compose in the project will make a PostgreSQL database available on `localhost` at port `65432`. The username, password, and database name are specified in the Compose file and can be referenced from there.

Using `pg_restore` is the opposite action to `pg_dump` and will load or restore a dump file.
If the target database has been set up with the Alembic migration, the `--data-only` argument will streamline the restore operation; the `--disable-triggers` argument will bypass database integrity checks (i.e., foreign key constraints).

```
export PGHOST=localhost
export PGPORT=65432
export PGUSER=cm-service
export PGPASSWORD=INSECURE-PASSWORD

pg_restore --dbname=cm-service --schema=public --no-owner --no-privileges --data-only --disable-triggers /path/to/dump.sql
```
