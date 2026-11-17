# operations

This guide is the runbook for a running Glados deployment: where the data lives, file storage, backup and restore, the recovery commands, Portainer specifics and monitoring. Installing and upgrading are in [INSTALLATION.md](INSTALLATION.md). Each section keeps the commands an operator types and links to a reference file for the internals. The commands use the production compose file; on a development stack, write `docker compose -f docker-compose.dev.yml` in place of `docker compose`.

- [operations](#operations)
  - [1 named volumes](#1-named-volumes)
  - [2 storage providers](#2-storage-providers)
    - [2.1 provider configuration](#21-provider-configuration)
    - [2.2 switching providers (migration)](#22-switching-providers-migration)
  - [3 backup](#3-backup)
    - [3.1 pre-migration dump](#31-pre-migration-dump)
    - [3.2 recovery strategy](#32-recovery-strategy)
  - [4 restore](#4-restore)
    - [4.1 restoring files (in-app)](#41-restoring-files-in-app)
    - [4.2 restoring the database (out-of-process)](#42-restoring-the-database-out-of-process)
      - [4.2.1 portainer, alternative: maintenance container](#421-portainer-alternative-maintenance-container)
  - [5 recovery commands](#5-recovery-commands)
    - [5.1 re-enabling password sign-in](#51-re-enabling-password-sign-in)
    - [5.2 resetting a user's 2FA](#52-resetting-a-users-2fa)
      - [5.2.1 resetting the system user's 2FA](#521-resetting-the-system-users-2fa)
      - [5.2.2 removing a user's passkeys](#522-removing-a-users-passkeys)
    - [5.3 releasing login lockouts](#53-releasing-login-lockouts)
    - [5.4 SMTP certificate verification](#54-smtp-certificate-verification)
    - [5.5 LDAP certificate verification](#55-ldap-certificate-verification)
    - [5.6 private webhook targets](#56-private-webhook-targets)
    - [5.7 database console (pgadmin)](#57-database-console-pgadmin)
    - [5.8 replaying dead-lettered events](#58-replaying-dead-lettered-events)
    - [5.9 lifecycle drift report](#59-lifecycle-drift-report)
    - [5.10 lifecycle repair](#510-lifecycle-repair)
    - [5.11 republishing events after a Redis loss](#511-republishing-events-after-a-redis-loss)
  - [6 portainer notes](#6-portainer-notes)
  - [7 monitoring & logs](#7-monitoring--logs)
    - [7.1 logs](#71-logs)
    - [7.2 endpoints](#72-endpoints)
    - [7.3 metrics](#73-metrics)
    - [7.4 prometheus multiprocess mode](#74-prometheus-multiprocess-mode)
    - [7.5 worker processes and restarts](#75-worker-processes-and-restarts)
    - [7.6 database connections and timeouts](#76-database-connections-and-timeouts)
  - [8 PDM synchronisation](#8-pdm-synchronisation)

## 1 named volumes

All persistent data lives in Docker named volumes under `/var/lib/docker/volumes/<name>/_data` on the host. Portainer lists them under Volumes like any other Docker volume.

| Volume             | Contents                                                                 |
| ------------------ | ------------------------------------------------------------------------ |
| `glados_postgres`  | PostgreSQL data                                                          |
| `glados_redis`     | Redis AOF persistence                                                    |
| `glados_seaweedfs` | SeaweedFS object data (with `--profile seaweedfs`)                       |
| `glados_pgadmin`   | pgAdmin settings and registered servers (with `--profile pgadmin`)       |
| `glados_media`     | Uploaded files (with local storage)                                      |
| `glados_logs`      | Application logs                                                         |
| `glados_pre_migration_dumps` | Database dumps taken before pending migrations ([3.1](#31-pre-migration-dump)) |

## 2 storage providers

File storage is configured at runtime in **Admin Settings → Storage** (or `PUT /api/v1/web/admin/settings/storage`), and no restart is needed. Five providers are supported:

| Provider    | Best for                                                          |
| ----------- | ----------------------------------------------------------------- |
| `local`     | Single-host self-hosted deployments                               |
| `seaweedfs` | Self-hosted deployments with the bundled SeaweedFS                |
| `s3`        | AWS S3 or another S3-compatible service, hosted or self-hosted    |
| `azure`     | Azure Blob Storage                                                |

Background: [reference/operations-storage-and-backup.md](reference/operations-storage-and-backup.md).

### 2.1 provider configuration

Every provider uses the same fields, and fields the chosen provider does not need are ignored. `provider` holds the provider's name from the table above.

**`seaweedfs`, bundled S3-compatible.** Set `SEAWEEDFS_ACCESS_KEY` and `SEAWEEDFS_SECRET_KEY` in the env file and start the stack with `--profile seaweedfs` (or add `seaweedfs` to `COMPOSE_PROFILES`). The secret needs at least 24 characters and must not be the sample value; the one-shot `seaweedfs-check` service and the backend refuse to start otherwise, since without a secret SeaweedFS serves its S3 API without authentication and nginx forwards `/objects/` to it. The container creates the bucket `objects` on first start and rejects every other bucket. Picking SeaweedFS in Admin Settings → Storage fills in the endpoint and the bucket.

| Field                 | Value                                                                  |
| --------------------- | ---------------------------------------------------------------------- |
| `endpoint_url`        | `"http://seaweedfs:8333"` (the compose-internal S3 gateway)            |
| `public_endpoint_url` | The public URL of the deployment, e.g. `"https://glados.example.com"`  |
| `bucket_name`         | `"objects"`, the only bucket the frontend routes to SeaweedFS          |
| `access_key`          | `SEAWEEDFS_ACCESS_KEY`                                                 |
| `secret_key`          | `SEAWEEDFS_SECRET_KEY`                                                 |
| `use_ssl`             | `false` (Docker-internal traffic)                                      |

Browsers load files through the deployment's own hostname under `/objects/`, which the frontend container forwards to SeaweedFS for reading only.

**The other providers.** `local` writes files to a directory on the host and serves them from whatever URL `endpoint_url` names, such as a static files mount or a reverse-proxy path. A dash means the provider ignores the field.

| Field                 | `local`                                   | `s3`                                         | `azure`                                    |
| --------------------- | ----------------------------------------- | -------------------------------------------- | ------------------------------------------ |
| `bucket_name`         | Storage root path; blank means `./media` relative to the working directory | S3 bucket name | Container name |
| `endpoint_url`        | Base URL serving the files, e.g. `"http://localhost:3000/media"` | Empty for AWS; the service URL for Backblaze B2, Cloudflare R2 and the like | Empty for standard Azure; set for custom endpoints (sovereign clouds, emulator) |
| `public_endpoint_url` | -                                         | Optional public URL presigned links are signed for | - |
| `access_key`          | -                                         | AWS access key ID                            | Storage account name                       |
| `secret_key`          | -                                         | AWS secret access key                        | Storage account key                        |
| `region`              | -                                         | AWS region, e.g. `"eu-central-1"`            | -                                          |
| `use_ssl`             | -                                         | `true` (always for AWS and public services) | - |

### 2.2 switching providers (migration)

> [!WARNING]
> Saving a different provider in Admin Settings → Storage does **not** move
> existing files. They stay on the old provider and are unreachable until
> migrated.

To switch with the files, fill in the new provider and use **Migrate to New Provider** in Admin Settings → Storage. It copies every object to the new provider and saves the new settings only if every file copied. If any file fails, the settings stay unchanged and the dialog lists the failed keys; fix the cause and run it again, since objects already copied are simply overwritten.

The copy runs on the backend, so closing the dialog or losing the connection does not stop it, and the Storage tab picks the running migration up again after a reload. Only one migration runs at a time. A backend restart during the copy ends it without switching the settings, so it can simply be started again.

Background: [reference/operations-storage-and-backup.md](reference/operations-storage-and-backup.md).

## 3 backup

The backend backs itself up on a schedule configured in **Admin Settings → Storage**:

| Setting                  | Description                                                              |
| ------------------------ | ------------------------------------------------------------------------ |
| `backup_enabled`         | Turns backups on or off                                                  |
| `backup_cron`            | Cron schedule, e.g. `0 2 * * *` (daily at 02:00 UTC)                     |
| `backup_path`            | Prefix within the active storage provider for the archives, e.g. `backups` |
| `backup_retention_count` | Number of archives to keep; older ones are deleted automatically        |

Each run writes a gzip-compressed `pg_dump`, encrypted with `SECURITY__BACKUP_ENCRYPTION_KEY`, to `{backup_path}/db/{timestamp}.sql.gz.enc` and a copy of every active storage object to `{backup_path}/files/{timestamp}/{original_key}`, both into the active storage provider. A cron change takes effect within a minute without a restart. A run missed while the app was down is caught up if the app comes back within an hour; older misses are skipped. A run left `running` by a dead worker is marked failed after two hours.

**The backup key.** Set `SECURITY__BACKUP_ENCRYPTION_KEY` to a long random value of its own, different from `SECURITY__ENCRYPTION_KEY` and both signing keys. Without it a production backend refuses to write a backup and records the run as failed, so no unencrypted archive ever reaches the backup storage; only a `DEBUG=true` development stack writes plain `.sql.gz` archives. A plain `.sql.gz` archive stays restorable.

**Warnings.** The Backups tab shows a warning, and `/ready` lists it under `warnings` ([7.2](#72-endpoints)), while backups are switched off, while the archives are stored on the database's own host (the `local` provider, or the bundled SeaweedFS reached by its service name) or while the backup key is missing. Fix each one: enable backups, point the storage at a provider off this host, and set the key.

> [!IMPORTANT]
> **Keep the backup key apart from the backups.** An archive cannot be
> restored without the `SECURITY__BACKUP_ENCRYPTION_KEY` it was written with.
> Store a copy of the key where losing the backup storage cannot take it, and
> never next to the archives. After changing the key, keep the old value for
> as long as archives written with it are kept; restoring one of them needs
> the old value set for that run ([4.2](#42-restoring-the-database-out-of-process)).

> [!IMPORTANT]
> **Back up the encryption key too.** Secrets in the database (SMTP, storage
> and PDM credentials, users' time-tracking credentials, webhook signing
> secrets, users' TOTP secrets) are encrypted with `SECURITY__ENCRYPTION_KEY`.
> A dump restored under a different key loads them as unset: an admin has to
> re-enter the credentials, recreate the webhook subscriptions and reset 2FA
> for every enrolled user, who are locked out until then, and every user has
> to enter their time-tracking credentials again. Keep a copy of the `.env`
> file with your backups, but store it apart from the database dumps, so one
> stolen backup does not hold both the ciphertext and the key. The design is
> in [ADR 0005](adr/0005-secret-encryption-at-rest.md).
>
> To rotate the key, move the current value to
> `SECURITY__ENCRYPTION_KEY_PREVIOUS`, set a new `SECURITY__ENCRYPTION_KEY`
> and restart. The backend re-encrypts every stored secret on start and
> recomputes the time-tracking user fingerprints derived from the key, after
> which the previous key can be removed.

> [!IMPORTANT]
> **The built-in backup is not enough on its own.** It writes into the same
> storage provider the app uses, so a failure of that provider (disk
> corruption, a deleted bucket, a crashed object store) takes the backups
> with the live data. Production deployments need an independent backup in
> addition:
>
> | Provider       | External backup approach                                                                 |
> | -------------- | ---------------------------------------------------------------------------------------- |
> | **Local**      | OS-level tools: `rsync` and cron to a remote host, `borgbackup` or `restic`, or an LVM/ZFS snapshot; a sidecar container mounting the volume works too. |
> | **Amazon S3**  | [Cross-Region Replication](https://docs.aws.amazon.com/AmazonS3/latest/userguide/replication.html) with S3 Versioning on both buckets. |
> | **Azure Blob** | [Geo-redundancy](https://learn.microsoft.com/en-us/azure/storage/common/storage-redundancy) (GRS or RA-GRS) or [object replication](https://learn.microsoft.com/en-us/azure/storage/blobs/object-replication-overview) between two accounts. |
>
> For PostgreSQL, the snapshots of the server's virtual machine are the
> point-in-time recovery ([3.2](#32-recovery-strategy)).

**Running and listing backups.** **Admin Settings → Backups → Run Backup Now** starts a backup (`POST /api/v1/web/admin/settings/storage/backups/run-now` answers `202` at once, or `409` while another backup runs). The Backups tab lists the archives with download and restore buttons, whether each archive is encrypted, and the last run with its status (`GET /api/v1/web/admin/settings/storage/backups`). An archive is downloaded only through the authenticated download route, never through a shareable link. Backup lives only in the app, so there is no compose command and no Portainer step for it.

Background: [reference/operations-storage-and-backup.md](reference/operations-storage-and-backup.md).

### 3.1 pre-migration dump

Before the backend applies pending migrations on start, it dumps the database into the `pre_migration_dumps` volume, as `/app/pre-migration-dumps/<timestamp>_<revision>.sql.gz.enc` (`.sql.gz` without the backup key). It keeps the newest three dumps. A start without pending migrations, and the first start on an empty database, take no dump.

When the dump fails, for example on a full disk, the backend refuses to migrate and does not start; its log names the cause. Fix the cause and start it again. To migrate without the dump, say after taking one by other means, set `GLADOS_SKIP_PRE_MIGRATION_DUMP=true` for that start and remove it again afterwards.

Two backends that start at the same time never migrate together: the second waits for the first and then finds nothing left to do.

To undo a migration that went wrong, roll the image back to the previous version and restore the newest dump with `--file` ([4.2](#42-restoring-the-database-out-of-process)):

```bash
docker compose run --rm backend restore \
    --file /app/pre-migration-dumps/2026-07-13T02-00-00_abc123def456.sql.gz.enc
```

`docker compose run --rm backend ls /app/pre-migration-dumps` lists the dumps. The directory and the number of dumps kept are set with `BACKUP__PRE_MIGRATION_DUMP_DIR` and `BACKUP__PRE_MIGRATION_DUMP_KEEP`.

Background: [reference/operations-storage-and-backup.md section 5](reference/operations-storage-and-backup.md#5-pre-migration-dump-and-migration-lock).

### 3.2 recovery strategy

The point-in-time recovery of a Glados server is the snapshot of its virtual machine, which the IT takes outside Glados. Restoring a snapshot puts the whole server back to the moment it was taken. Glados' own nightly dumps ([3](#3-backup)), encrypted and written to storage off the host, stay as the second, independent path: they restore the database on any machine, also when the snapshots are lost ([4.2](#42-restoring-the-database-out-of-process)).

The snapshots must guarantee:

- **One atomic snapshot of the whole disk Postgres writes to.** Such a snapshot is crash-consistent: a restored machine starts like after a power cut, and Postgres comes up with every transaction committed before the snapshot. When the machine has several disks, they are snapshotted together at the same instant.
- **Storage off the virtualisation host.** The snapshots are stored or replicated where a failure of the host or its storage cannot take them along with the machine.
- **A frequency that matches the acceptable data loss.** The snapshot interval is the recovery point: a restore loses everything written since the last snapshot.
- **A tested restore.** A snapshot has been restored at least once, for example onto the staging server, and Glados started and served from it.

After restoring a snapshot, run a PDM poll before users create items again, as after a dump restore ([4.2](#42-restoring-the-database-out-of-process)), since the number counters went back with the database.

Background: [reference/operations-storage-and-backup.md section 6](reference/operations-storage-and-backup.md#6-recovery-strategy).

## 4 restore

### 4.1 restoring files (in-app)

Restore a file snapshot from **Admin Settings → Backups**, or through the API:

```
POST /api/v1/web/admin/settings/storage/backups/files/restore
Content-Type: application/json

{ "snapshot_key": "backups/files/2026-07-13T02-00-00" }
```

Every object in the snapshot is copied back to its original key, overwriting the current object. The restore runs in place without downtime.

### 4.2 restoring the database (out-of-process)

The restore never writes into the current database. It loads the archive into a fresh database, checks that the result is a Glados database and only then swaps it in by renaming. The current database is kept as `<name>_pre_restore_<timestamp>` until you drop it, so a restore can itself be undone. When any step fails, the command prints the cause and `Database restore FAILED.`, exits non-zero and leaves the current database as it was.

Stop the app first: the swap closes every open connection to the database, and a running backend would keep writing until then.

1. **Stop the app** and keep postgres running:

   ```bash
   docker compose stop backend frontend
   ```

   **Portainer:** Containers → tick `glados-backend-1` and `glados-frontend-1` → Stop.

2. **Run the restore** with the storage key shown in the Backups tab:

   ```bash
   docker compose run --rm backend restore \
       --backup backups/db/2026-07-13T02-00-00.sql.gz.enc
   ```

   The command reads the storage settings from the current database, downloads the archive and restores it, using the database settings and the backup key of the compose project's env file. It ends with `Database restore complete.` and the name the previous database is kept under.

   **The database is lost or broken**, so the storage settings cannot be read: copy the archive from the backup storage onto the host and restore it from the file instead:

   ```bash
   docker compose run --rm -v /srv/restore:/restore backend restore \
       --file /restore/2026-07-13T02-00-00.sql.gz.enc
   ```

   **The archive was written with an older backup key:** pass that key for this one run, `docker compose run --rm -e SECURITY__BACKUP_ENCRYPTION_KEY=<old key> backend restore …`.

   **Portainer:** do not run this from the Console of `glados-backend-1`; that container holds the database connections the restore replaces the database under. Instead:

   1. Stop `glados-backend-1` and `glados-frontend-1` (step 1).
   2. Containers → `glados-backend-1` → Duplicate/Edit → name it `glados-restore`. Under Command & logging → Command, set `restore --backup backups/db/<file>.sql.gz.enc` and leave the entrypoint unchanged. Set Restart policy → Never. Keep the inherited environment, network and volumes, and deploy the container.
   3. Watch its Logs until it exits `0`.
   4. Remove the `glados-restore` container.
   5. Start `glados-backend-1` and `glados-frontend-1` again (step 3).

   > [!WARNING]
   > Never change the stack's backend `command:` to `restore` in the stack
   > editor. The service's `restart: unless-stopped` policy would re-run the
   > restore every time the container exits, in a loop.

3. **Restart the app:**

   ```bash
   docker compose up -d backend frontend
   ```

   **Portainer:** Containers → tick `glados-backend-1` and `glados-frontend-1` → Start.

4. **Drop the previous database** once the restored data is confirmed. The restore prints the command; with the bundled Postgres it is:

   ```bash
   docker compose exec postgres psql -U <POSTGRES_USER> -d postgres \
       -c 'DROP DATABASE "glados_pre_restore_20260713020000"'
   ```

   **Undoing the restore** instead: stop the app, rename the restored database out of the way and the previous one back, then start the app:

   ```bash
   docker compose exec postgres psql -U <POSTGRES_USER> -d postgres \
       -c 'ALTER DATABASE "glados" RENAME TO "glados_restored"' \
       -c 'ALTER DATABASE "glados_pre_restore_20260713020000" RENAME TO "glados"'
   ```

> [!NOTE]
> If migrations were added since the backup was taken, the entrypoint takes a
> pre-migration dump ([3.1](#31-pre-migration-dump)) and applies them on the
> next start.

> [!IMPORTANT]
> A restore also rolls back the number counters, while the PDM vault and the
> printed labels keep the numbers drawn after the backup. When the PDM
> integration is enabled, run a PDM poll from **Admin Settings → SolidWorks
> PDM** before users create items again, so the numbers PDM already holds are
> registered before the counters hand them out a second time.

#### 4.2.1 portainer, alternative: maintenance container

Instead of cloning `glados-backend-1`, the stack can run the `maintenance` service: an idle container with the backend's image, environment, volumes and network that runs neither migrations nor the app.

1. Add `maintenance` to the stack's `COMPOSE_PROFILES` (comma-joined with anything already there, e.g. `COMPOSE_PROFILES=seaweedfs,maintenance`) and **Update the stack** so `glados-maintenance-1` is created. It does nothing until you open a console in it.
2. Stop `glados-backend-1` and `glados-frontend-1` as in step 1 of [4.2](#42-restoring-the-database-out-of-process), since the restore still needs the live backend's connections gone.
3. Containers → `glados-maintenance-1` → Console → command `/bin/sh`, user `glados` → Connect, then:

   ```bash
   /entrypoint.sh restore --backup backups/db/2026-07-13T02-00-00.sql.gz.enc
   ```

   Calling the entrypoint script by its path runs the same dispatch as `docker compose run --rm backend restore …`, which a Console session would otherwise skip. `admin` subcommands work the same way here, see [5](#5-recovery-commands).
4. Wait for `Database restore complete.` in the Console output. There is no clone to remove afterwards.
5. Start `glados-backend-1` and `glados-frontend-1` again (step 3 in [4.2](#42-restoring-the-database-out-of-process)).
6. Remove `maintenance` from `COMPOSE_PROFILES` and **Update the stack**, so the idle container is not left running between uses.

Background: [reference/operations-storage-and-backup.md](reference/operations-storage-and-backup.md).

## 5 recovery commands

These commands cover the cases where the UI cannot help because signing in itself is broken. They run through the container entrypoint like `restore`, so **access to the container is the authority**: a host shell, `docker compose run` or a container console all count, and there is no login and no permission check. Unlike `restore`, they are safe to run while the live backend keeps serving. They are dispatched before `alembic upgrade head`, so they also work while the schema is mid-upgrade.

List the commands:

```bash
docker compose run --rm backend admin --help
```

**Portainer:** open Containers → `glados-backend-1` → Console → command `/bin/sh`, user `glados` → Connect, and run `python -m src.bootstrap.cli.admin <subcommand> …`. The `admin` shorthand is not available there ([6](#6-portainer-notes) explains why). This works for every subcommand: `enable-local-login`, `disable-ldap`, `reset-totp USERNAME`, `unlock-users [--user USERNAME]`, `replay-dead-letters`, `republish-outbox --since TIME`, `lifecycle-drift`, `lifecycle-repair`, `pre-migration-dump`. The last one is what the entrypoint runs before it migrates ([3.1](#31-pre-migration-dump)); run by hand, it dumps only while migrations are pending. If the backend is down, use the [maintenance container](#421-portainer-alternative-maintenance-container) and run `/entrypoint.sh admin <subcommand> …` there.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.1 re-enabling password sign-in

Password sign-in is the only interactive login method, so switching off *Admin Settings → Security → allow local login* stops every ordinary user signing in with `403`. The UI warns before saving, but it can still happen by accident. There are two ways back:

1. **Sign in as the system user.** It is exempt from the setting and can switch it back on. Its password is `INIT__PASSWORD` in the env file.
2. **Run the command**, which needs no login and changes nothing if password sign-in is already on:

   ```bash
   docker compose run --rm backend admin enable-local-login
   ```

   **Portainer:** Console → `python -m src.bootstrap.cli.admin enable-local-login`.

The system account `system` is created on first start from `INIT__FULL_NAME`, `INIT__MAIL` and `INIT__PASSWORD`. Its 2FA is mandatory and its sessions expire 15 minutes after login; [5.2.1](#521-resetting-the-system-users-2fa) resets its 2FA.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.2 resetting a user's 2FA

A user who lost their authenticator cannot pass the two-factor prompt and cannot remove it under *Account → Security* either, because that asks for a current code. An administrator with `write:settings` normally clears it in **Settings → Users → (select user) → Reset 2FA**. When nobody with that permission can sign in, run:

```bash
docker compose run --rm backend admin reset-totp i000
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin reset-totp i000`.

The user enrols again from *Account → Security* at their next sign-in.

> [!NOTE]
> A reset leaves the user's sessions intact. If the device may be
> compromised rather than lost, also terminate their sessions in **Settings →
> Users**. The reset does revoke every "trust this device" grant of the user.

#### 5.2.1 resetting the system user's 2FA

The UI's **Reset 2FA** button is unavailable for the system account, so this command is the only way:

```bash
docker compose run --rm backend admin reset-totp system
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin reset-totp system`.

At its next login the system account shows a fresh QR code and enrols again. Its existing sessions stay, but they expire 15 minutes after login anyway.

#### 5.2.2 removing a user's passkeys

A passkey (Windows Hello, Touch ID, a security key) signs in without password and TOTP code. Users manage their own under *Account → Passkeys*. When a device is lost or stolen, an administrator with `write:settings` removes all of a user's passkeys in **Settings → Users → (select user) → Remove Passkeys**. Like the 2FA reset this leaves the sessions intact, so terminate them too if the device may be in someone else's hands. Deactivating the account blocks passkey sign-in at once.

Passkeys are bound to the host name in `DOMAIN` and need `https`, see [INSTALLATION.md, section 5](INSTALLATION.md#5-configuration). The system account cannot hold passkeys.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.3 releasing login lockouts

With *Admin Settings → Security → max login attempts* above 0, repeated failed sign-ins for one user from one address lock that address out for that user, and further attempts from there answer `429` until the lock expires after *lockout duration minutes*. From any other address the user only waits a short, growing delay of at most a minute, so nobody can shut an account out everywhere by failing on purpose. An address that fails on many usernames is locked for 15 minutes regardless of the setting. A new install ships with 5 attempts and 15 minutes; `0` disables the per-user limits.

Release locks early with:

```bash
# Everyone, address locks included:
docker compose run --rm backend admin unlock-users

# A single account, on every address:
docker compose run --rm backend admin unlock-users --user i000
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin unlock-users` (everyone), or `unlock-users --user i000` for a single account.

Lockout state lives in Redis. While Redis is down, each backend worker enforces the limits from its own memory, and the log shows a warning.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.4 SMTP certificate verification

*Admin Settings → Mail → verify certificate* makes outbound SMTP validate the relay's TLS certificate, so an invalid certificate fails the send. New installs ship with it on; turning it off is the opt-out for an internal relay on a private CA. Before turning it on for a relay of uncertain configuration, run *Admin Settings → Mail → Test connection*, which reports pass or fail at once instead of letting the background notification digest fail silently hours later.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.5 LDAP certificate verification

*Admin Settings → Auth → verify certificate* makes an LDAPS or StartTLS bind validate the directory's certificate. New installs ship with it on. Run *Admin Settings → Auth → Test connection* before saving a change to it against a live directory, because it binds with the new settings before they are stored.

> [!WARNING]
> Enabling verification untested on an install bound against an internal CA
> risks `401` for every directory user at once. Recovery does not need the
> directory: sign in as `system`, which is exempt from directory routing, or
> run `admin disable-ldap` as in [5](#5-recovery-commands).

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.6 private webhook targets

Glados never sends a webhook to the local host, a link-local or cloud metadata address, or the stack's own network and services, whatever the settings say. *Admin Settings → Features → Allow Private Webhook Targets* decides whether a webhook may reach private ranges such as RFC 1918, where other servers of the company network live. New installs ship with it on; turn it off when every receiver is on the internet. The target is checked when a subscription is created or edited and again before every delivery, and a refused delivery shows *Refused* in the delivery log. How a receiver checks the signature is in [reference/operations-recovery.md section 9](reference/operations-recovery.md#9-webhook-targets-and-signatures).

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.7 database console (pgadmin)

For one-off inspection and data fixes no admin command covers, the stack ships an opt-in pgAdmin container. It is a second login in front of the production database: start it for the task and stop it afterwards.

1. Set `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` in the env file (see `.env.example`). They are pgAdmin's own login, not the database user.

2. Start it:

   ```bash
   docker compose --profile pgadmin up -d pgadmin
   ```

3. Reach it. It binds to `127.0.0.1:5050` on the host by default, so tunnel from your workstation:

   ```bash
   ssh -L 5050:127.0.0.1:5050 <host>
   ```

   Then open <http://localhost:5050>. `PGADMIN_PORT` changes the port. On a host without shell access, `PGADMIN_BIND=0.0.0.0` exposes it on every interface; do that only on a trusted network and stop the container as soon as you are done.

4. Register the database once (Add New Server): host `postgres`, port `5432`, maintenance database and username from `POSTGRES_DB` and `POSTGRES_USER`, password from `POSTGRES_PASSWORD`. The `glados_pgadmin` volume keeps the registration and the saved password.

5. Stop it when done:

   ```bash
   docker compose --profile pgadmin stop pgadmin
   ```

   In Portainer, removing `pgadmin` from `COMPOSE_PROFILES` does the same on the next redeploy. Nothing in the app depends on it.

> [!CAUTION]
> Prefer an admin command from [5.1](#51-re-enabling-password-sign-in) to
> [5.6](#56-private-webhook-targets) where one exists. pgAdmin bypasses every
> domain rule the application enforces, including part-number uniqueness and
> the PDM field-ownership rules in
> [FIELD_OWNERSHIP.md](FIELD_OWNERSHIP.md).

### 5.8 replaying dead-lettered events

When a consumer group (notifications, webhooks, auto_print, pdm_sync, edp_pictures, schedule) fails the same event five times in a row, the event moves to the Redis stream `glados:events:dead`, `glados_events_dead_lettered_total` goes up, and the backend log names the group, id and event type. Nothing is lost. The event design is in [ADR 0002](adr/0002-transactional-outbox-redis-streams.md).

Look at them:

```bash
docker compose exec redis redis-cli XRANGE glados:events:dead - + COUNT 20
```

Once the cause is fixed (a bug deployed, a printer back online, a webhook endpoint reachable again), put them back on the events stream, oldest first:

```bash
docker compose run --rm backend admin replay-dead-letters --limit 100
```

Every consumer group sees a replayed event again, but groups that already handled it skip it.

Background: [reference/operations-recovery.md](reference/operations-recovery.md).

### 5.9 lifecycle drift report

The status of a lot, lot position, production order, order, order line or demand is stored, and the lifecycle rules derive it from recorded facts and intents ([ADR 0008](adr/0008-derived-lifecycle-statuses.md)). `lifecycle-drift` lists every stored lifecycle field that disagrees with that derivation and changes nothing, so it is safe against the live backend.

```bash
docker compose run --rm backend admin lifecycle-drift
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin lifecycle-drift`.

Save a report with `-T`, which keeps the terminal's line endings out of the file:

```bash
docker compose run --rm -T backend admin lifecycle-drift --json > lifecycle-drift-$(date +%F).json
```

`--json` prints one JSON document instead of the table, and `--only lots,orders` limits the report to some tables. The command exits `0` when no row differs and `1` when any does. Rows marked as fact anomalies are contradictions in the facts themselves, which only a person can settle.

Background: [reference/operations-lifecycle-repair.md](reference/operations-lifecycle-repair.md).

### 5.10 lifecycle repair

`lifecycle-repair` writes what `lifecycle-drift` lists: every stored status, kind, completed count and stamp that differs gets its derived value. Without `--apply` it is a dry run that only shows what it would write.

```bash
# Dry run, then the repair:
docker compose run --rm backend admin lifecycle-repair
docker compose run --rm backend admin lifecycle-repair --apply
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin lifecycle-repair [--apply]`.

Every change gets a changelog line in the system user's name. The repair **publishes no events**, so no notification, mail, webhook or automatic print follows, and open pages show the repaired rows after a reload. It is safe to run against the live backend. If it stops with exit code `3`, run it again: committed pages stay written and it carries on where it stopped. Options are `--apply`, `--json`, `--only` and `--batch 200`.

Background: [reference/operations-lifecycle-repair.md](reference/operations-lifecycle-repair.md).

### 5.11 republishing events after a Redis loss

Redis holds the events stream that notifications, webhooks, automatic prints, the PDM sync, Data Portal pictures and schedule walks are driven by. The database keeps every event the relay put on the stream for 30 days, so when Redis loses its data (a restart without its volume, a flush, a restore of an older Redis), nothing is lost for good: the events it still owed are put back with `republish-outbox`.

1. Bring Redis back. The backend needs no restart: each consumer group notices that Redis lost it, logs an error naming the group and creates itself again at the end of the stream. Events relayed until then are not seen by that group.
2. Choose the last good point, a time when Redis still held its data and every group had caught up, such as shortly before the restart or flush. When unsure, go further back: consumers skip events they already handled.
3. Count, then republish. Times need a UTC offset:

```bash
docker compose run --rm backend admin republish-outbox --since 2026-11-04T06:00:00+01:00 --dry-run
docker compose run --rm backend admin republish-outbox --since 2026-11-04T06:00:00+01:00
```

**Portainer:** Console → `python -m src.bootstrap.cli.admin republish-outbox --since TIME [--until TIME] [--type EVENT_TYPE] [--dry-run]`.

`--until TIME` stops at a later point and `--type`, repeatable, limits it to some event types, such as `--type OrderCanceled`. The command appends the events behind newer ones, which is fine, since no consumer relies on the order of events. It exits `1` when Redis fails part way; run it again with the same bounds.

A republished event repeats nothing a consumer already did, with these exceptions: a notification whose every recipient has deleted it comes back, mails included, and a PDM file trigger refreshes its file once more. So the further back `--since` goes, the more deleted notifications can return.

Background: [reference/operations-recovery.md](reference/operations-recovery.md#61-republishing-outbox-events).

## 6 portainer notes

Points specific to running the stack from a Portainer stack rather than the CLI:

- **Console skips the entrypoint.** `docker/entrypoint.sh` dispatches the `admin` and `restore` shorthand, and a Console session (Containers → `glados-backend-1` → Console → command `/bin/sh`, user `glados` → Connect) bypasses it. Call the module directly instead: `python -m src.bootstrap.cli.admin <subcommand> …`, which is safe next to the live app.
- **Restoring the database.** Never restore from the Console of `glados-backend-1`, and never set the stack's backend `command:` to `restore`, because `restart: unless-stopped` would re-run it in a loop. Follow [4.2](#42-restoring-the-database-out-of-process) or [4.2.1](#421-portainer-alternative-maintenance-container).
- **Stack environment variables.** `ENV_FILE=stack.env` makes `docker-compose.yml` load the `stack.env` file Portainer writes from the stack's variables (the default is `.env`). `COMPOSE_PROFILES` enables profiles without a `--profile` flag, comma-joined, e.g. `COMPOSE_PROFILES=seaweedfs,pgadmin`. Verify the exact field name and behaviour on your Portainer version first.
- **Profiles for operations.** `maintenance` starts the idle `glados-maintenance-1`, whose Console may run `restore` because it holds no database connections ([4.2.1](#421-portainer-alternative-maintenance-container)). `pgadmin` with `PGADMIN_DEFAULT_EMAIL`/`PGADMIN_DEFAULT_PASSWORD` starts `glados-pgadmin-1`; a Portainer host usually has no SSH for the tunnel in [5.7](#57-database-console-pgadmin), so this is the case for `PGADMIN_BIND=0.0.0.0`. Remove `maintenance` and `pgadmin` again once done.
- **Common commands.** `docker compose logs -f backend` is Containers → `glados-backend-1` → Logs, and `docker compose ps` is Stacks → glados or Containers.
- **Registry credentials.** Pulling the images from a private GHCR registry needs credentials under Registries in Portainer, not in the stack file, see [INSTALLATION.md](INSTALLATION.md).

## 7 monitoring & logs

### 7.1 logs

The application writes every log line to **stdout**: `docker compose logs -f backend`, or Portainer → Containers → `glados-backend-1` → Logs. Two independent thresholds (`DEBUG`, `INFO`, `WARNING`, `ERROR`) decide where a line goes:

| Variable       | Destination                                      | Default                                       |
| -------------- | ------------------------------------------------ | --------------------------------------------- |
| `LOG_LEVEL`    | stdout                                           | `DEBUG` (the shipped `.env.example` sets `INFO`) |
| `LOG_DB_LEVEL` | `log_table`, shown in the in-app **Logs** tab    | `INFO`                                        |

Set either one to `DEBUG` to troubleshoot without touching the other, then restart the backend. Request audit rows (writes, PAT and API-key calls) are stored regardless of both settings. A database outage never slows requests down because of logging; lines that cannot be stored are dropped and counted.

**Retention.** Old rows are deleted hourly according to **Admin Settings → Retention**: `log_table` after the log retention period, and the PAT and API-key usage logs and the settings audit after the audit retention period (`0` keeps them forever). Lot history and the security log are never purged.

**Security log.** Logins and refused logins, login throttling, logouts and ended sessions, account, permission and group changes, tokens and keys created and revoked, and password, 2FA and passkey changes are recorded in **Admin Settings → Security Log**, which every holder of `read:settings` can read. Unlike the app log it survives the retention and log rotation. What it records and how its size stays bounded: [reference/operations-monitoring.md section 1.5](reference/operations-monitoring.md#15-the-security-log).

**Format.** `LOG_FORMAT=text` (the default) writes human-readable lines such as `2026-07-13 02:00:00,123 | INFO | rid=a1b2c3d4 | user=i000(id=7) | glados
| HTTP GET /api/v1/web/orders → 200 [12.3ms]`. `LOG_FORMAT=json` writes one
JSON object per line for a log aggregator such as Loki or Elastic.

**Correlation.** Every request carries an `X-Request-ID`, taken from the caller's header or minted, echoed in the response and attached to every log line of the request (`rid`). Use it to pull one request's lines out of an aggregator or to match a client-reported error.

**Rotation.** `docker-compose.yml` caps each container's log at five files of 20 MB, which matters on a default Docker install where `json-file` logs grow without limit.

Background: [reference/operations-monitoring.md](reference/operations-monitoring.md).

### 7.2 endpoints

| Endpoint   | Purpose                                                                                       | Reachable from |
| ---------- | --------------------------------------------------------------------------------------------- | -------------- |
| `/health`  | Liveness: always `{"status": "ok", "version": ...}`. Docker's `HEALTHCHECK` watches it.       | Public, through the frontend's nginx |
| `/ready`   | Readiness: `200` when the database and Redis answer, `503` otherwise. Meant for an external prober or alert. Its `warnings` list names what the backups lack ([3](#3-backup)) and each background task that stopped in a worker, without changing the status. | Public, through the frontend's nginx |
| `/metrics` | Prometheus exposition text ([7.3](#73-metrics)).                                              | **Docker network only**, at `http://backend:3000/metrics` |

None of them needs authentication. `/metrics` is deliberately not proxied. To scrape it from a Prometheus outside this compose project, use one of:

- **Join the network.** The Docker network is named after the compose project, so `internal` becomes `glados_internal`. Attach an existing Prometheus with `docker network connect glados_internal <prometheus-container>`, or add Prometheus as a service in an override file with `networks: [internal]`, and scrape `backend:3000/metrics`.
- **Static target.** If Prometheus runs on the same host outside the project, publish the backend port to loopback in a `docker-compose.override.yml` (`ports: ["127.0.0.1:<port>:3000"]` on the `backend` service, the same loopback binding [INSTALLATION.md, section 6.2](INSTALLATION.md#62-bind-the-container-port-to-localhost) describes for the frontend) and scrape `127.0.0.1:<port>`.

Background: [reference/operations-monitoring.md](reference/operations-monitoring.md).

### 7.3 metrics

`GET /metrics` combines the standard HTTP request metrics (`http_requests_total`, `http_request_duration_seconds` and others) with `glados_*` gauges and counters computed on every scrape: database pool use, slow queries, dropped log lines, outbox and event stream backlog, dead-lettered events, backup and PDM sync health, background tasks that stopped, live connections and the running version. A source that fails, such as Redis being down, is left out of that scrape rather than failing the endpoint.

**Suggested alert rules:**

| Alert                        | Condition                                                                 | Why |
| ---------------------------- | ------------------------------------------------------------------------- | --- |
| Outbox backlog stuck         | `glados_outbox_unpublished_messages > 0` for 10 minutes                    | The relay normally drains within seconds; a lasting backlog means it is stuck or the events stream is unreachable |
| Event stream pending growing | `glados_event_stream_pending_messages` rising over 15 minutes              | A consumer group is not keeping up or has stopped acking |
| Not ready                    | `/ready` not `200` for 2 minutes                                          | The database or Redis has been unreachable long enough to matter |
| Backup overdue               | `time() - glados_backup_last_success_timestamp_seconds > 36 * 3600`        | No successful backup in 36 hours, past a daily schedule's grace window ([3](#3-backup)) |
| Dead-lettered events         | `increase(glados_events_dead_lettered_total[1h]) > 0`                      | An event failed five deliveries; fix the cause, then replay it ([5.8](#58-replaying-dead-lettered-events)) |
| Background task stopped      | `glados_background_task_up == 0`                                           | An event consumer, scheduler or the outbox relay ended in a worker and nothing restarts it; read the CRITICAL log line, then restart the backend ([reference](reference/operations-monitoring.md#33-background-tasks)) |
| Elevated 5xx rate            | `rate(http_requests_total{status=~"5.."}[5m])` above the deployment's baseline | Standard error-rate alert; the threshold depends on normal volume |

**PDM alerting.** These rules watch the PDM integration on top of the ones above:

```yaml
groups:
  - name: pdm
    rules:
      - alert: PdmPollStale
        expr: time() - glados_pdm_last_poll_success_timestamp_seconds > 45 * 60
        for: 5m
        annotations:
          summary: No successful scheduled PDM poll in over 45 minutes (3x the poll interval).
      - alert: PdmAddInSilent
        expr: >
          time() - glados_pdm_last_trigger_timestamp_seconds > 4 * 3600
          and on() glados_pdm_last_run{counter="changed"} > 0
        for: 5m
        annotations:
          summary: No add-in change-notification sync in 4 hours despite the last run seeing changed files.
      - alert: PdmTriggerRejected
        expr: increase(http_requests_total{handler="/api/v1/key/pdm/files/changed",status=~"401|403|429"}[15m]) > 0
        annotations:
          summary: The add-in's change-notification calls are being rejected by auth or rate limiting.
      - alert: PdmBacklog
        expr: glados_pdm_files{sync_state="conflict"} > 0
        for: 24h
        annotations:
          summary: Parked PDM file conflicts have sat unresolved for a full day.
      - alert: PdmConsumerStuck
        expr: glados_event_stream_pending_messages{group="pdm_sync"} > 0
        for: 10m
        annotations:
          summary: The pdm_sync consumer group has unacked messages and is not keeping up.
```

Background: [reference/operations-monitoring.md](reference/operations-monitoring.md), which lists every metric.

### 7.4 prometheus multiprocess mode

The backend's worker processes share their metrics through the directory in `PROMETHEUS_MULTIPROC_DIR`, which `docker-compose.yml` sets and the entrypoint creates and empties on every start. Nothing needs configuring; a scrape always sums the live workers only.

Background: [reference/operations-monitoring.md](reference/operations-monitoring.md).

### 7.5 worker processes and restarts

`GUNICORN_WORKERS` (default 4) sets how many worker processes the backend container runs. Each worker has its own database pool, so the connection budget in [7.6](#76-database-connections-and-timeouts) scales with it.

On a restart (redeploy, `docker compose restart`) the live-update streams close at once and browsers reconnect by themselves. Other requests get up to 25 seconds to finish, inside gunicorn's 30 seconds and the container's 35-second `stop_grace_period`, so Docker never kills a worker mid-request.

**Request rate limit.** The frontend container's nginx allows each client 50 API requests per second with a burst of 200 and answers `429` beyond that. Normal use never reaches it. The client is the address nginx resolves from its trusted proxies ([INSTALLATION.md, section 6.7](INSTALLATION.md#67-client-addresses-behind-proxies)), so a client cannot pick another bucket; behind a proxy that is not trusted, every client shares that proxy's bucket.

### 7.6 database connections and timeouts

Each worker keeps its own pool of `DATABASE__POOL_SIZE` (default 5) connections plus up to `DATABASE__MAX_OVERFLOW` (default 5) under load. A request that finds the pool exhausted waits `DATABASE__POOL_TIMEOUT_SECONDS` (default 10) and then fails with a 503 `DatabaseBusyError`. With 4 workers that is at most 40 connections against Postgres' `max_connections=100` (set in `docker-compose.yml`), which leaves room for backups, migrations, the maintenance container and pgAdmin. When raising workers or pool sizes, keep `workers x (POOL_SIZE + MAX_OVERFLOW)` well below `max_connections`.

Every backend connection carries three server-side limits, set in seconds through these variables (`0` disables):

| Limit | Env var | Default | Effect when hit |
|---|---|---|---|
| `statement_timeout` | `DATABASE__STATEMENT_TIMEOUT_SECONDS` | 30 | The statement is cancelled and the request gets a 503 `DatabaseTimeoutError`. |
| `lock_timeout` | `DATABASE__LOCK_TIMEOUT_SECONDS` | 5 | The row-lock wait is cancelled and the request gets a 503 `DatabaseLockTimeoutError`. |
| `idle_in_transaction_session_timeout` | `DATABASE__IDLE_IN_TRANSACTION_TIMEOUT_SECONDS` | 60 | Postgres closes a connection left idle inside an open transaction. |

Statements slower than 500 ms are logged by Postgres in its own container log and by the backend with the request id and user that issued them (`glados_db_slow_queries_total`). Backend connections show up in `pg_stat_activity` as `glados-<host>-<pid>`, one name per worker:

```sql
SELECT application_name, state, count(*)
FROM pg_stat_activity
WHERE application_name LIKE 'glados-%'
GROUP BY 1, 2 ORDER BY 1, 2;
```

Background: [reference/operations-monitoring.md](reference/operations-monitoring.md).

## 8 PDM synchronisation

Glados keeps the catalogue in sync with a SOLIDWORKS PDM vault in two ways that end in the same ingest: a background poller that runs on one worker at a time, and a change notification the PDM vault add-in sends with each signed-in user's personal access token, which a `pdm_sync` consumer group processes. Every poll and every single-file refresh writes a row to the PDM sync run log, which keeps the runs of the last 30 days; every run drops the older ones when it ends. The PDM alerts are in [7.3](#73-metrics).

See [PDM_INTEGRATION.md](PDM_INTEGRATION.md) for the full mechanism: the settings, the folder walk, the trigger contract, the ingest rules, ownership enforcement and the admin surfaces that show what happened.
