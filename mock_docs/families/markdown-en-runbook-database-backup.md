# Database Backup and Restore Runbook

This runbook is for the on-call engineer who needs to take a manual backup of the production PostgreSQL database or restore one into a staging environment. It assumes basic familiarity with the command line.

## Overview

The production database is backed up automatically every night at 02:00 UTC. Backups are compressed and stored in an object storage bucket for 30 days. Manual backups are needed only before risky changes such as schema migrations, or when the nightly job has failed.

Two kinds of backups exist. A logical backup is a dump of tables and data, portable across versions and slower to restore. A physical backup is a copy of the data directory, fast to restore but tied to the same major version.

## Prerequisites

- Access to the bastion host with your personal SSH key.
- The `backup-operator` role in the cloud console.
- At least 2x the database size free on the target volume.
- The latest version of the `pg_tools` package installed on the bastion.

Check free space before starting. A restore that runs out of disk leaves the target in an unusable state and takes much longer to recover from than the original task.

## Taking a manual backup

Connect to the bastion and open a terminal session that survives disconnects:

```bash
ssh bastion.example.internal
tmux new -s backup
```

Start the dump. The `--format=custom` option gives a compressed archive that allows selective restore:

```bash
pg_dump --host db-primary.internal --username backup_operator \
  --format=custom --file /backups/manual/app-$(date +%Y%m%d-%H%M).dump app
```

The dump of a 40 GB database normally takes 15 to 20 minutes. Do not interrupt the process. Progress can be seen by watching the size of the output file grow.

When the command finishes, verify the archive is readable:

```bash
pg_restore --list /backups/manual/app-20260312-1430.dump | head -20
```

Upload the file to the bucket and keep the checksum in the incident or change ticket:

```bash
sha256sum /backups/manual/app-20260312-1430.dump
aws s3 cp /backups/manual/app-20260312-1430.dump s3://company-db-backups/manual/
```

## Restoring into staging

Never restore into the production host. Always create or reuse a staging instance and double-check the hostname in the command before pressing enter.

First, drop and recreate the staging database so that no old objects remain:

```bash
psql --host db-staging.internal --username admin --command "DROP DATABASE IF EXISTS app;"
psql --host db-staging.internal --username admin --command "CREATE DATABASE app;"
```

Restore with parallel jobs to shorten the time. Four jobs is a good default for the staging instance size:

```bash
pg_restore --host db-staging.internal --username admin \
  --dbname app --jobs 4 --no-owner /backups/manual/app-20260312-1430.dump
```

After the restore, run the smoke checks: row counts of the five largest tables should match production within the backup time, and the application health endpoint should return OK.

## Troubleshooting

**The dump fails with "permission denied for table".** The backup role lacks read access to a recently created table. Ask the database owner to grant select on the new schema and rerun the command.

**The restore reports "role does not exist".** Use the `--no-owner` option or create the missing role first. Roles are not part of a single-database dump.

**The restore is very slow.** Check that parallel jobs are enabled and that indexes are not being created on a volume with throttled IOPS. Temporarily raising the volume throughput usually helps.

**The disk fills up during the dump.** Remove old files from `/backups/manual/`, keeping only the latest two, and start again. Do not delete anything outside that folder.

## Escalation

If a backup cannot be taken or a restore fails twice, page the database team through the on-call tool and attach the command output. Do not retry in a loop, because repeated attempts put extra load on the primary.
