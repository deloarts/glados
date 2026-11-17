# operations: monitoring internals

This file holds how logging, the health and metrics endpoints, Prometheus multiprocess mode, worker shutdown and the database connection limits work inside the backend, plus the full list of metrics. How to read the logs, set up scraping and alerts, and size workers and pools is in [OPERATIONS.md section 7](../OPERATIONS.md#7-monitoring--logs).

- [operations: monitoring internals](#operations-monitoring-internals)
  - [1 logging](#1-logging)
    - [1.1 database log writer](#11-database-log-writer)
    - [1.2 json log fields](#12-json-log-fields)
    - [1.3 the access log](#13-the-access-log)
    - [1.4 log rotation](#14-log-rotation)
    - [1.5 the security log](#15-the-security-log)
  - [2 health and readiness](#2-health-and-readiness)
  - [3 metrics](#3-metrics)
    - [3.1 sources](#31-sources)
    - [3.2 metric list](#32-metric-list)
    - [3.3 background tasks](#33-background-tasks)
  - [4 prometheus multiprocess mode](#4-prometheus-multiprocess-mode)
  - [5 worker shutdown](#5-worker-shutdown)
  - [6 database connection limits](#6-database-connection-limits)

## 1 logging

### 1.1 database log writer

- A log call only queues the line for `log_table`. One writer thread per worker inserts the queued lines in batches over its own dedicated connection.
- While the database is unreachable the queue holds up to 10,000 lines and then drops the oldest, so a database outage never slows requests down or grows memory without bound.
- Lines that never reach `log_table` (queue full, or a failed batch write) are counted in `glados_log_records_dropped_total`.

### 1.2 json log fields

With `LOG_FORMAT=json` every stdout line is one JSON object with these fields, written by `src/modules/platform/infrastructure/logging/json_formatter.py`:

| Field      | Meaning |
| ---------- | ------- |
| `ts`       | ISO-8601 UTC timestamp, millisecond precision |
| `level`    | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` |
| `logger`   | Logger name, always `glados` |
| `msg`      | The formatted message |
| `rid`      | Request id; `"-"` outside a request |
| `user_id`  | Acting user's id; `null` when unauthenticated or outside a request |
| `username` | Acting user's username; `null` likewise |
| `exc`      | Formatted traceback; present only on `log.exception(...)` or an error with `exc_info` |
| `http`     | Present only on the per-request access line: `{method, path, status, elapsed_ms}` |

A formatter failure never takes logging down: `JsonFormatter` falls back to a minimal `{ts, level, logger, msg}` object rather than raising.

### 1.3 the access log

- Gunicorn's own `--access-logfile` is deliberately not set (the backend `command:` in `docker-compose.yml` passes only `--error-logfile -`), so there is one access log, not two.
- The single access line comes from `RequestContextMiddleware` as `"HTTP <method> <path> → <status> [<ms>ms]"`, and carries the `http` fields under `LOG_FORMAT=json`.
- `/health`, `/ready`, `/metrics` and the live-sync SSE stream are left out of the access log, because probes and a connection that lasts as long as the tab stays open are no useful request telemetry (`_SKIP_LOG_PATHS` in `src/modules/platform/adapters/inbound/api/middleware/request_context_middleware.py`).
- The `X-Request-ID` is propagated from the caller's header when present, minted otherwise, echoed in the response header and attached to every log line of the request.

### 1.4 log rotation

`docker-compose.yml` sets `logging: {driver: json-file, options: {max-size: "20m", max-file: "5"}}` on `backend`, `frontend`, `postgres`, `redis`, `pgadmin` and `seaweedfs`. It is harmless where the host's Docker daemon already sets `json-file` size defaults in `/etc/docker/daemon.json`, and necessary on a default installation, where `json-file` has no size cap and a long-running deployment's container log grows without limit.

### 1.5 the security log

- The `security_event` table is the durable record of security events, read in **Admin Settings → Security Log** with `read:settings`, newest first, filtered by event type, outcome, user (acting or concerned) and day range. Nothing updates or deletes an entry.
- It records logins with their method (password, directory, 2FA code, passkey, 2FA setup) and every refused login after the throttle with its reason; each throttle scope a failure locks; logouts and ended sessions; created, deactivated and reactivated users; changed direct permissions and group memberships; created, changed (permissions or members) and deleted groups; created and revoked personal access tokens, API keys and terminal keys; changed passwords, by the user or by an administrator, and wrong current passwords; 2FA enabled, disabled and reset; and passkeys added and removed.
- An entry keeps the acting user and the user it concerns by id and by a copy of the username, the id of the token, key, group or session it concerns, the client address, the user agent cut to 255 characters and a small JSON detail.
- The log retention never purges the table, so it grows for as long as the installation runs. There is no retention setting for it.
- A login attempt the throttle refuses is not recorded; the throttle event marks when the lock began. So refused logins are bounded by the throttle: one address records at most 30 refused logins before each 15-minute address lock, about 120 an hour, plus the lock entries.
- A passkey login has no throttle, so its refusals are recorded only once the passkey is known, and at most one per account a minute. A refusal before that, such as an unknown credential or an expired challenge, is only logged.
- Bulk actions record one entry: signing out every user, revoking all own tokens or passkeys. Revoking all API keys records one entry per key.

## 2 health and readiness

- `/health` always answers `{"status": "ok", "version": ...}` and touches nothing. Docker's own `HEALTHCHECK` (`docker/backend.Dockerfile`) watches it.
- `/ready` pings the database (`SELECT 1`) and Redis (`PING`) with 1 second timeouts and answers `200` when both are `ok`, `503` otherwise.
- Its body is `{"status", "checks", "warnings"}`. `warnings` lists the backup warnings of [operations-storage-and-backup.md section 3.4](operations-storage-and-backup.md#34-the-backup-list) (`disabled`, `stored_on_host`, `encryption_key_missing`), read from the storage settings within the same 1 second budget. They never change the status, since a deployment without backups still serves requests, so an alert on them has to read the body. When the settings cannot be read the list is empty; the failing database check reports that case.
- `warnings` also holds one `background_task_stopped:<task>` entry for each background task that ended in any worker ([section 3.3](#33-background-tasks)), such as `background_task_stopped:outbox-relay`. It does not change the status either, and when the metric files cannot be read no such entry appears.
- `/ready` is deliberately not Docker's `HEALTHCHECK`: restarting the backend does not fix a dead Redis and would drop every SSE client without fixing anything.
- `/metrics` is deliberately not proxied by the frontend's nginx, because an unbounded-cardinality, denial-of-service surface has no business being public.
- The compose project name (`name: glados` at the top of `docker-compose.yml`) prefixes the network key, which is why the `internal` network is `glados_internal` on the host.

## 3 metrics

### 3.1 sources

- `GET /metrics` combines two sources into one Prometheus exposition-format response (`src/read/adapters/inbound/api/metrics.py`): the HTTP middleware metrics of `prometheus-fastapi-instrumentator`, and `GladosStateCollector`, a custom collector computed fresh on every scrape.
- `/health`, `/ready`, `/metrics` and the live stream are excluded from the HTTP metrics, the same exclusion list the access log uses (compare `_EXCLUDED_HANDLERS` with `_SKIP_LOG_PATHS`), because probes and scrapes do not belong in a latency dashboard.
- Every `GladosStateCollector` gauge is computed independently in its own try/except. A failing source, such as Redis being down, logs at `DEBUG` and is omitted from that scrape instead of failing the endpoint or taking the other gauges down.

### 3.2 metric list

| Metric | Type | Meaning |
| ------ | ---- | ------- |
| `http_requests_total{method,handler,status}` | Counter | Requests by route template (not raw path, so cardinality stays bounded), method and status |
| `http_request_duration_seconds{method,handler}` | Histogram | Request latency, low-resolution buckets sized for SLIs |
| `http_request_duration_highr_seconds` | Histogram | The same, high-resolution buckets, no labels |
| `http_request_size_bytes{handler}`, `http_response_size_bytes{handler}` | Histogram | Request and response body sizes |
| `http_requests_inprogress` | Gauge | Requests currently being handled |
| `glados_db_pool_checked_out` | Gauge | Database connections all workers hold out of their pools right now; compare with workers x (`DATABASE__POOL_SIZE` + `DATABASE__MAX_OVERFLOW`) |
| `glados_db_slow_queries_total` | Counter | Statements slower than `DATABASE__SLOW_QUERY_THRESHOLD_MS` (default 500); each is also logged as a warning with its request id and user |
| `glados_log_records_dropped_total` | Counter | Log records that never reached `log_table` (queue full during a database outage, or a failed batch write) |
| `glados_events_dead_lettered_total{group}` | Counter | Events a consumer group failed five times and moved to the `glados:events:dead` stream |
| `glados_outbox_unpublished_messages` | Gauge | Rows in the transactional outbox not yet relayed to the events stream (`event_outbox_table.published_at IS NULL`) |
| `glados_event_stream_length` | Gauge | `XLEN` of the `glados:events` Redis stream; trimmed each minute to what every consumer group has processed, hard cap 500,000 |
| `glados_event_stream_pending_messages{group}` | Gauge | `XPENDING` count per consumer group (`notifications`, `webhooks`, `auto_print`, `pdm_sync`, `edp_pictures`, `schedule`) |
| `glados_backup_last_success_timestamp_seconds` | Gauge | Unix timestamp of the newest successful backup run (`backup_runs` table) |
| `glados_backup_last_failure_timestamp_seconds` | Gauge | Unix timestamp of the newest failed backup run |
| `glados_pdm_last_poll_success_timestamp_seconds` | Gauge | Unix timestamp of the newest scheduled PDM poll that finished without an error |
| `glados_pdm_last_poll_failure_timestamp_seconds` | Gauge | Unix timestamp of the newest scheduled PDM poll that finished with an error |
| `glados_pdm_last_trigger_timestamp_seconds` | Gauge | Unix timestamp of the newest add-in change-notification sync, the signal that the add-in is alive |
| `glados_pdm_last_run{counter}` | Gauge | Per-counter tallies of the newest finished PDM sync run, any trigger (`files_seen`, `changed`, `ingested`, `skipped`, `conflicts`, `errors`, `missing`, `folders_walked`, `folders_skipped_cold`) |
| `glados_pdm_files{sync_state}` | Gauge | `pdm_file_snapshot_table` rows grouped by `sync_state`, zero-filled across every `PdmFileSyncState` value |
| `glados_pdm_reconciliation_findings{category}` | Gauge | Finding counts per category of the newest PDM reconciliation run, zero-filled across every `PdmReconciliationCategory` value; the whole family is omitted until the first reconciliation run |
| `glados_pdm_folders_cold` | Gauge | `pdm_folder_poll_state_table` rows whose `next_due_at` is still in the future |
| `glados_live_connections` | Gauge | Live-sync SSE connections currently held open, summed across worker processes |
| `glados_background_task_up{task}` | Gauge | 1 while the background task runs in every worker, 0 once it ended in any of them ([section 3.3](#33-background-tasks)) |
| `glados_info{version}` | Info | Static build info, the running app's version |

### 3.3 background tasks

- Each worker runs its own copy of the long-running background tasks: the event consumers (`event-worker:<group>`), the interval jobs, the PDM poll, the notification digest, the schedule tick, the live subscriber, the outbox relay and the events stream trim. Each one catches its own errors and carries on, so a task that still ends is a defect.
- When a task ends with anything but the cancellation of a shutdown, the worker logs `Background task '<task>' died` (or `ended although it should run forever`) at `CRITICAL` and sets `glados_background_task_up{task="<task>"}` to 0. Nothing restarts the task, because a supervisor loop that ended would most likely end again; restarting the backend starts every task afresh.
- The gauge uses the `livemin` multiprocess mode, so a scrape reads the lowest value across the live workers, and a task that ended in one worker reads 0 although the others still run it. A worker that exits takes its values along.
- `/ready` reads the same files on every probe, so its warning names the task whichever worker answers.
- Suggested alert rule:

```yaml
groups:
  - name: glados-background-tasks
    rules:
      - alert: GladosBackgroundTaskStopped
        expr: glados_background_task_up == 0
        annotations:
          summary: "Background task {{ $labels.task }} stopped in a backend worker; restart the backend."
```

## 4 prometheus multiprocess mode

- `prometheus_client` picks single-process or multiprocess value storage at import time from `PROMETHEUS_MULTIPROC_DIR`. That is why the variable is a container `environment:` value in `docker-compose.yml` rather than computed by the app: it has to exist before Python starts.
- Each worker writes its own per-pid `*.db` files under that directory, and a scrape aggregates all of them (`MultiProcessCollector`).
- The `child_exit` hook in `src/modules/platform/infrastructure/gunicorn_conf.py` removes a worker's files the moment it exits, on a restart or a crash. Without it a `livesum`-mode gauge such as `glados_live_connections` would keep summing a dead worker's last value forever.
- No `max_requests` recycle is configured, since a worker also runs the in-process background jobs.
- `docker/entrypoint.sh` creates the directory before `alembic upgrade head` runs, because `prometheus_client` does not create it and anything the migration step imports may touch it with the variable already set.
- The entrypoint wipes the directory again immediately before it `exec`s the real command, so files left by a previous container run (a different set of pids) are never summed into the new run's gauges.
- Development's single-process `uvicorn` never sets the variable and always uses the ordinary in-process registry.

## 5 worker shutdown

- On a restart the open live-update streams are closed immediately and browsers reconnect by themselves.
- Other in-flight requests get up to 25 seconds to finish before they are cancelled. Gunicorn allows 30 seconds and the container's `stop_grace_period` is 35 seconds, so Docker never kills a worker that is still finishing a request.
- The frontend container's request rate limit is set in `frontend/docker/nginx.conf`. It is a safety net against a runaway client and keys on `$binary_remote_addr`, the address the `real_ip` settings resolve ([installation-deployment.md section 4](installation-deployment.md#4-forwarded-client-addresses)).

## 6 database connection limits

- The three server-side limits (`statement_timeout`, `lock_timeout`, `idle_in_transaction_session_timeout`) are set on every backend connection and are visible per connection in `pg_settings`.
- When `lock_timeout` cancels a write that committed nothing, the write is run once more on the server before the request gets its 503.
- Connections that hold an advisory lock on purpose (the scheduler, relay and recompute locks) lift the idle limit for themselves. Waits on the blocking advisory locks are exempt from `lock_timeout`, while `statement_timeout` still caps them.
- A transaction holding a production queue lock (auto-plan's write, reordering, reassigning) raises its own idle limit to 10 minutes.
- Every other code path ends its transaction before slow non-database work (password hashing, LDAP, SMTP, printers, storage, webhooks, the PDM Web API, backups), so the 60 second idle limit only ever closes a leaked transaction.
- Postgres logs every statement slower than 500 ms through `log_min_duration_statement`, set in `docker-compose.yml`.
