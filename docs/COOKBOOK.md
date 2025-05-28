# My Campaign Is ...

## Running and I Want the Status
Campaigns are made up of multiple scripts that execute various steps and perform actions for a Campaign.
Once a Campaign is running, you can check the current set of scripts for that Campaign using the Campaign's "fullname" property.
A `jq` filter is provided to help assemble a useful display of Campaign script statuses using the CM Client CLI.
The `CM_CAMPAIGN` shell variable must be set to the Campaign's fullname.
The output of this command displays the script ID, status, and name.

```
export CM_CAMPAIGN=...
cm-client script list -o json | jq -rf ../script/step_status.jq
```

## Running and I Want to Change Something
CM Service won't allow changes to a Campaign once it is in a running state, so before any changes can be made, this status must be changed.

We recommend that you first delete an active queue for your campaign, then you can "reject" the campaign. These commands use the `row_id` of the elements in question, which you may discover by issuing `cm-client ... list` and noting the id in the response.

```
export CM_CAMPAIGN=...
cm-client queue delete --row_id XXX
cm-client campaign action reject --row_id 16
```

Now you can change the Campaign's `data` manifest, after which you can ...

# My Script Is ...

## Still Running After A Long Time
Scripts that are in a `running` state should eventually enter one terminal state or another.
Especially long-running scripts, like those that report on BPS Workflows, can run for several hours until the workflow completes.
Behind the scenes, CM Service periodically checks on these with the equivalent of a `bps report`.

If you would like to check on a long-running script yourself, CM Service can help locate the BPS submit directory you should inspect.

```
cm-client script get all -o json --row_id XXX -o json | jq '.stamp_url'
```

If the long-running script is understood by CM Service to be `running` when it is not, this is an error and should be raised with CM Ops.

## Blocked
Scripts enter the blocked state when the WMS jobs they depend upon are HELD.
CM Service considers these states terminal in that they are unlikely to progress without intervention.
After the jobs are unblocked, the blocked state persists in CM Service until the intervention has been acknowledged.
A pilot may either mark the script as accepted if the intervention has resulted in a successful outcome or ask CM Service to re-check the script and make its own determination.

*Marking a Blocked Script as Accepted*
```
cm-client script action accept --row_id XXX
```

*Requesting Re-Check of a Blocked Script*
```
cm-client script action run_check --row_id XXX
```

## Failed
Scripts become failed when CM Service determines that the WMS jobs they depend upon have entered an unsuccessful terminal state.
Usually, if a BPS workflow has failed jobs but otherwise has successfully run its `finalJob`, CM Service considers this script `accepted` and defers other qualitative analysis to a subsequent `pipetask report` output.
A script that is actually marked as failed can be inspected for its failure reason and/or reset (in order to try again).

*Checking the Diagnostic Message of a Failed Script*
CM Service tries to capture a diagnostic message for failed scripts.
This will produce any diagnostic messages found with that script; there may be more than one if the script was run multiple times with an error result.

```
cm-client script get script-errors -o json --row_id XXX
```

Or, use the failed script's ID as a variable with a provided `jq` filter.

```
cm-client script_error list -o json | jq -f ./script/script_error.jq --arg script_id XXX
```

*Resetting a Failed Script to Retry*
If a script is in a `failed` state, the script can be directly retried by resetting its status.
This will set the script status back to `waiting` which signals the CM Daemon to run it from that point.
Resetting a script in this way may not clean up all artifacts created by the script when it was previously run.

```
cm-client script action reset --row_id XXX
```

### ...and I fixed it!
If CM Service failed to run a script but you managed to correct the failure out-of-band, such as by performing the script's action manually, you can manually register this success with CM Service by marking the failed script as accepted. To do so, the script must first be marked as reviewable.

```
cm-client script update status --status reviewable --row_id XXX
cm-client script action accept --row_id XXX
```

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
