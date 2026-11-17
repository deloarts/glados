# operations: storage and backup

This file holds the exact behaviour of file storage, provider migration, the built-in backup scheduler, the archive format, the database restore paths, the pre-migration dump and what the VM snapshots add to them: the API shapes, the scheduling rules and the entrypoint mechanics behind the operator steps. The steps themselves and the safety warnings are in [OPERATIONS.md sections 2 to 4](../OPERATIONS.md#2-storage-providers).

- [operations: storage and backup](#operations-storage-and-backup)
  - [1 storage providers](#1-storage-providers)
  - [2 provider migration](#2-provider-migration)
    - [2.1 the blocking endpoint](#21-the-blocking-endpoint)
    - [2.2 the streaming endpoint](#22-the-streaming-endpoint)
  - [3 backup scheduler](#3-backup-scheduler)
    - [3.1 claiming a slot](#31-claiming-a-slot)
    - [3.2 the run record](#32-the-run-record)
    - [3.3 manual runs](#33-manual-runs)
    - [3.4 the backup list](#34-the-backup-list)
    - [3.5 archive format and encryption](#35-archive-format-and-encryption)
  - [4 database restore internals](#4-database-restore-internals)
  - [5 pre-migration dump and migration lock](#5-pre-migration-dump-and-migration-lock)
  - [6 recovery strategy](#6-recovery-strategy)

## 1 storage providers

- The `seaweedfs` and `s3` providers need `boto3`, and `azure` needs `azure-storage-blob`. Both are default dependencies and are imported lazily, so the app starts cleanly whichever provider is active.
- The storage settings live in the admin settings (`PUT /api/v1/web/admin/settings/storage`); fields the chosen provider does not use are silently ignored.
- The bundled SeaweedFS rejects uploads to any bucket but `objects`, because the frontend container serves presigned file URLs only for that bucket, under `/objects/`.
- Presigned URLs for SeaweedFS are signed for `public_endpoint_url`, so the browser loads files through the deployment's own hostname. The frontend container forwards `/objects/` to SeaweedFS and accepts only `GET` and `HEAD` there; every write goes from the backend to SeaweedFS directly over the internal network.
- Every stored object carries the content type of its extension, and a presigned URL repeats that type and asks for a download, except for raster images and PDF, which open in the browser. The frontend container adds a sandboxing policy and `nosniff` to everything under `/objects/` ([installation-deployment.md section 1](installation-deployment.md#1-the-containers-nginx)).

## 2 provider migration

Saving a provider with `PUT /storage` changes the settings at once but moves no file, so the existing files stay on the old provider and are unreachable until migrated.

### 2.1 the blocking endpoint

`POST /api/v1/web/admin/settings/storage/migrate` takes the same body as `PUT /storage`, the full target provider configuration. It works in this order:

1. It reads the current (source) settings from the database.
2. It lists every object on the source provider.
3. It downloads each object and uploads it to the target provider.
4. It saves the new settings only if every file copied without error.
5. It returns a `StorageMigrationResult`.

```json
{
  "migrated_count": 42,
  "failed_count": 0,
  "errors": [],
  "committed": true
}
```

When any file fails, `committed` is `false`, the database is unchanged, and `errors` holds one entry per failed key with the cause. A retry overwrites the objects already copied without harm.

The request lasts as long as the copy, so a proxy in front of the stack (nginx's 60 second default, Cloudflare's 100 seconds) may give up on it while the copy carries on. That is why the UI uses the streaming endpoint.

### 2.2 the streaming endpoint

The **Migrate to New Provider** dialog uses these two endpoints, and the stream takes the same body as the blocking endpoint:

```
POST /api/v1/web/admin/settings/storage/migrate/stream
GET  /api/v1/web/admin/settings/storage/migrate/status
```

- The stream sends a `progress` event (`current`, `total`, `key`) before each object is copied, then one `result` event with the body from [2.1](#21-the-blocking-endpoint) or one `error` event.
- Keep-alive pings every 15 seconds hold the connection open through proxies.
- The copy runs as a background task on the backend. Closing the dialog or the page, or losing the connection, does not stop it, and the settings still switch once every object is copied.
- Only one migration runs at a time; a second one gets `409` (`StorageMigrationInProgressError`).
- The status endpoint reports the running migration with its progress, which is how the Storage tab picks it up again after a reload.
- A backend restart during the copy ends it without switching the settings.

## 3 backup scheduler

The backup scheduler is an in-process interval task on each backend worker's event loop. The backend runs four gunicorn workers in production by default (`GUNICORN_WORKERS`), and each one ticks its own copy of the scheduler every 60 seconds. The scheduler starts with the app and re-reads the settings on every tick.

### 3.1 claiming a slot

- Each tick computes the latest due time of `backup_cron` within the last hour that nobody has claimed yet, fresh from the schedule, and tries to insert a row for it into the `backup_runs` table.
- The `slot` column is unique, so of the workers that compute the same due time in the same minute exactly one insert succeeds. The others see the conflict, log a DEBUG line and do nothing.
- A changed `backup_cron` needs no restart: `PUT /storage` only saves it, and the next tick, within 60 seconds, uses it.
- A due time missed while the app was down is still run if it falls within one hour of the app starting again (a 60-minute grace window). Older misses count as missed and are not run late.
- The pg_dump and upload run under the claim and an advisory lock, so a scheduled and a manual run never run concurrently.

### 3.2 the run record

- Every attempt, scheduled or manual, leaves a row with `slot`, `trigger` (`scheduled` or `manual`), `started_at`, `finished_at`, `status` (`running`, `success` or `failed`), the resulting `db_key` and `files_key`, and `error` on failure.
- If a worker dies mid-backup (killed, out of memory, container restart), its row would stay `running` and every later run-now would answer `409`. So every tick first marks any `running` row older than 2 hours as `failed` with `error: "worker died or timed out"`. Two hours is well past any realistic dump and upload, so an older row is presumed dead, not slow.

### 3.3 manual runs

`POST /api/v1/web/admin/settings/storage/backups/run-now` starts the backup in a background task and returns `202 Accepted` at once, or `409 Conflict` when a `backup_runs` row is already `running` (a scheduled tick or another manual trigger). The work goes through the same claim and advisory lock as a scheduled tick.

### 3.4 the backup list

`GET /api/v1/web/admin/settings/storage/backups` returns:

```json
{
  "db":    [{ "key": "backups/db/2026-07-13T02-00-00.sql.gz.enc", "timestamp": "2026-07-13T02:00:00", "encrypted": true }],
  "files": [{ "key": "backups/files/2026-07-13T02-00-00",        "timestamp": "2026-07-13T02:00:00", "encrypted": false }],
  "warnings": ["stored_on_host"],
  "last_run": { "slot": "2026-07-13T02:00:00Z", "trigger": "scheduled", "status": "success", "started_at": "2026-07-13T02:00:00Z", "finished_at": "2026-07-13T02:00:41Z", "error": null },
  "runs": [ "... up to 20 of these, newest first ..." ]
}
```

- `last_run` is `null` and `runs` is `[]` until the first tick or manual run ever completes.
- `encrypted` tells an archive written with the backup key from a plain `.sql.gz` one. A file snapshot is never encrypted.
- The list carries no download URL. A presigned URL would hand the archive, with every password hash and TOTP secret in it, to whoever holds the link, so an archive is downloaded only through `GET /api/v1/web/admin/settings/storage/backups/download?key=…`, which checks the session and `write:settings` on every request.
- `warnings` lists, in this order, `disabled` (backups off or no `backup_path`), `stored_on_host` (the `local` provider, or `seaweedfs` with an endpoint host of `seaweedfs`, `localhost` or a loopback address) and `encryption_key_missing` (no `SECURITY__BACKUP_ENCRYPTION_KEY`). The rules live in `src/modules/platform/domain/services/backup_rules.py`, which `/ready` uses too.
- The Backups tab shows the same list with download and restore buttons, one warning banner per entry of `warnings`, plus "Last backup: `<time>` · `<status>`" from `last_run`.

### 3.5 archive format and encryption

- A database archive is a plain SQL `pg_dump` (`--no-owner --no-acl`), gzip-compressed. With `SECURITY__BACKUP_ENCRYPTION_KEY` set it is also encrypted and named `.sql.gz.enc`; without it, `.sql.gz`. The scheduled backup and the pre-migration dump share this code (`adapters/outbound/external/schedules/database_dump.py`).
- Outside `DEBUG=true` the scheduled backup refuses to run without the key and fails the run with a message naming the variable. The run history, the schedule-error mail and `glados_backup_last_failure_timestamp_seconds` report it like any other failure.
- The key is optional at boot, because a deployment may leave backups off. Once set, the boot guard refuses a placeholder value, a value shorter than 32 characters and a value equal to `SECURITY__ENCRYPTION_KEY` or either signing key, so an archive never carries the key that opens the secrets inside it.
- The encrypted format (`src/modules/platform/infrastructure/security/backup_cipher.py`) starts with an 8 byte magic, a 16 byte random salt and an 8 byte key id, followed by frames of at most 1 MiB of plaintext. HKDF-SHA256 derives a fresh AES-256-GCM key from the env key and the salt for every archive, the frame counter is the nonce, and every frame authenticates the header and whether it is the last one.
- A wrong key, a flipped byte, a missing or reordered frame and data after the last frame all fail to decrypt. The key id, derived from the env key alone, lets the restore say that the key differs rather than that the archive is damaged.
- The restore tells the formats apart by their first bytes, not by the file name.

## 4 database restore internals

- How the `restore` command loads, verifies and swaps the database, and what each failure leaves behind, is in [operations-recovery.md section 8](operations-recovery.md#8-database-restore). This section holds the container mechanics.
- `--backup KEY` reads the storage settings from the current database through the app's own repository, so it needs that database readable. `--file PATH` reads an archive inside the container and needs no database; mount the host directory that holds it, or use a pre-migration dump from its volume ([section 5](#5-pre-migration-dump-and-migration-lock)).
- The `maintenance` service in `docker-compose.yml` (`profiles: [maintenance]`) is a standing, idle container with the same image, environment, volumes and network as `backend`. It starts with `command: maintenance`, which the entrypoint resolves to `exec sleep infinity`, so it never runs migrations or the app (see `docker/entrypoint.sh`).
- A Console session execs a shell directly in the container, which bypasses the image's `ENTRYPOINT` line but not the script file at `/entrypoint.sh`. Calling that file by its explicit path still runs its allowlisted `case` dispatch, the same one `docker compose run --rm backend restore …` triggers, which is why the `restore` and `admin` shorthand work from the maintenance container's Console.

## 5 pre-migration dump and migration lock

- `docker/entrypoint.sh` runs `admin pre-migration-dump` after the out-of-process commands are dispatched and before `alembic upgrade head`. The command lives in `src/bootstrap/cli/pre_migration_dump.py`.
- It compares the revisions in `alembic_version` with the heads of the migration scripts in the image. It dumps only when they differ and the database already holds a table, so neither an up to date database nor the first start on an empty one gets a dump. It does nothing on SQLite.
- The dump is the archive of [3.5](#35-archive-format-and-encryption), encrypted when `SECURITY__BACKUP_ENCRYPTION_KEY` is set. Without the key it is written unencrypted rather than refused, because it stays on the host's own volume next to the database it copies, and a deployment that never configured backups must still be able to upgrade.
- It is written to `BACKUP__PRE_MIGRATION_DUMP_DIR` (default `./pre-migration-dumps`, which is `/app/pre-migration-dumps` in the image, the `pre_migration_dumps` volume) as `<timestamp>_<revision>.sql.gz[.enc]`. The file is written under a temporary name, synced and then renamed, so a dump under its final name is complete. The directory is created with mode `0700` and the file with `0600`.
- Afterwards only the newest `BACKUP__PRE_MIGRATION_DUMP_KEEP` dumps (default 3, at least 1) stay; other files in the directory are left alone.
- The command exits `0` when it wrote a dump or needed none and `1` when reading the revision, `pg_dump` or writing failed. On `1` the entrypoint prints why it stops and exits without migrating, and the container's restart policy retries the start.
- `GLADOS_SKIP_PRE_MIGRATION_DUMP=true` makes the entrypoint skip the command entirely and migrate with a warning on stderr. Any other value, or none, takes the dump.
- `alembic/env.py` takes the transaction-scoped advisory lock `AdvisoryLockKey.MIGRATION` before Alembic reads the current revision and holds it until the migration transaction commits. A second container that starts meanwhile waits on the lock, then reads the committed revision and has nothing left to do. Every migration runs in that one transaction, so the lock covers all of them. SQLite has no advisory locks and runs single-process, so the lock is skipped there.
- Two containers that start together may both take a dump, since the dump runs before the lock; the second waits on the first's migration locks while `pg_dump` reads, and its dump shows the state before or after that migration.

## 6 recovery strategy

The operator view and the requirements on the snapshots are in [OPERATIONS.md section 3.2](../OPERATIONS.md#32-recovery-strategy).

- Glados ships no WAL archiving and no point-in-time restore of its own. The snapshots of the server's virtual machine fill that role, and the nightly dumps of [section 3](#3-backup-scheduler) with the restore command ([operations-recovery.md section 8](operations-recovery.md#8-database-restore)) are the second path, which does not depend on the virtualisation platform.
- Postgres writes every commit to its write-ahead log in the data directory before it acknowledges it, and replays that log on start. A snapshot that captures the whole data directory at one instant therefore restores to exactly the commits made before that instant, with no hook or pause before the snapshot. A data directory spread over disks that are snapshotted at different moments gives no such guarantee.
- A snapshot holds every Docker volume on the machine: the database, Redis with the events stream, local file storage, the bundled SeaweedFS, the logs and the pre-migration dumps, all from the same moment.
- A storage provider off the machine, such as S3, Azure Blob or a self-hosted object store elsewhere, is not in the snapshot and does not go back with it. Files uploaded after the snapshot stay there unreferenced, and an object deleted after the snapshot is missing unless the provider keeps versions.
