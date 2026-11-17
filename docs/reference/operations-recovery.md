# operations: recovery

This file holds the exact rules behind the recovery commands and the security settings an operator may have to undo: the system account, 2FA and passkey resets, login lockout, session and token limits, the defaults of the certificate and webhook settings, dead-lettered and republished events, the RFID lookup, the database restore, and the webhook target check and signature. The commands and when to use them are in [OPERATIONS.md section 5](../OPERATIONS.md#5-recovery-commands).

- [operations: recovery](#operations-recovery)
  - [1 recovery command dispatch](#1-recovery-command-dispatch)
  - [2 the system account](#2-the-system-account)
  - [3 2FA and passkeys](#3-2fa-and-passkeys)
  - [4 login lockout](#4-login-lockout)
  - [4.1 sessions, tokens and password changes](#41-sessions-tokens-and-password-changes)
  - [5 security setting defaults](#5-security-setting-defaults)
  - [6 dead-lettered events](#6-dead-lettered-events)
  - [6.1 republishing outbox events](#61-republishing-outbox-events)
  - [7 RFID lookup](#7-rfid-lookup)
  - [8 database restore](#8-database-restore)
  - [9 webhook targets and signatures](#9-webhook-targets-and-signatures)

## 1 recovery command dispatch

- The `admin` subcommands run out of process through the same container entrypoint as `restore`. Access to the container is the authority, so there is no actor and no permission check.
- The entrypoint dispatches them before `alembic upgrade head`, so they work while the schema is mid-upgrade. They read the database settings from the env file of the compose project.
- Where the entrypoint is skipped (a Console session), the module is called directly as `python -m src.bootstrap.cli.admin <subcommand> …`.

## 2 the system account

- Exactly one system account exists, `system`, created on first start from `INIT__FULL_NAME`, `INIT__MAIL` and `INIT__PASSWORD`.
- It cannot be created, renamed, deleted or duplicated through the API. A partial unique index on `is_systemuser` keeps a second flagged row out of the database.
- It is exempt from *allow local login* and from directory routing, so it can always sign in with its password.
- 2FA is mandatory for it and is enrolled on first login. Its sessions hard-expire 15 minutes after login regardless of *session timeout*.
- It cannot create personal access tokens, any it already had are refused, and "trust this device" is unavailable to it. It cannot hold passkeys.
- The UI's **Reset 2FA** button is unavailable for it, so `admin reset-totp system` is the only reset. At its next login the login screen shows a fresh QR code instead of the usual sign-in flow.

## 3 2FA and passkeys

- A user who lost their authenticator cannot use the self-service removal under *Account → Security*, because that route confirms with the current code.
- A 2FA reset, from the UI or `admin reset-totp`, deliberately leaves the user's existing sessions intact. It revokes every "trust this device" grant of the user, because a browser trusted for the old secret must not be able to skip enrolment of the new one.
- Removing a user's passkeys also leaves the sessions intact. Deactivating the account blocks passkey sign-in at once.
- A passkey sign-in never reaches the directory. For an LDAP account a passkey therefore works only while the account's last password sign-in is at most 30 days old. After that the login page asks for the password once, which also catches an account disabled in the directory.
- Passkeys are bound to the host name in `DOMAIN` and need `https`.

## 4 login lockout

- A new install ships with *max login attempts* 5 and *lockout duration minutes* 15, matching the always-on throttle on the TOTP step.
- Failed password sign-ins are throttled on three scopes (`application/services/login_throttle.py`, policy in `domain/services/login_policy.py`):
  - The username on one client address is locked for *lockout duration minutes* after *max login attempts* failures. Only that address is shut out, so nobody can lock an account out everywhere by failing on purpose.
  - The username alone, counted over every address, earns a growing delay once it reaches *max login attempts*: one second, doubling with each further failure, at most one minute. Attempts during the delay answer `429` and are not counted.
  - One client address is locked for 15 minutes after 30 failed sign-ins within an hour, whatever usernames it tried. This limit is fixed and always on.
- `0` for *max login attempts* turns off the username lock and the delay. The address limit stays.
- A successful sign-in clears the username's counter, delay and lock on that address, but never the address's own count.
- The password confirmations on the user's own account (registering a passkey, changing the own password, creating a personal access token, setting up 2FA from a session) count toward the same throttle.
- The client address is the one the backend resolves for the request, so behind a reverse proxy it must come from trusted forwarded headers.
- `admin unlock-users --user <name>` releases the username's delay and its locks on every address. Address locks are released only by `admin unlock-users` without a name, or by waiting.
- Throttle state lives in Redis and is deliberately disposable. While Redis is unavailable each worker process keeps its own counters in memory instead, so the limits hold per worker rather than failing open, and a warning is logged. Those counters are forgotten once Redis is back.

## 4.1 sessions, tokens and password changes

- A web session ends when it is revoked, after *session idle timeout* minutes without activity, or *session maximum lifetime* days after sign-in, however active it is. The idle timeout must be at least one minute and the lifetime between 1 and 365 days, 30 on a new install.
- The session cookie lives as long as the session may, so the browser drops it with the session.
- The system account keeps its own fixed 15 minute lifetime, and terminal and infoscreen sessions follow their own rules ([terminal-auth.md](terminal-auth.md)).
- While *maximum token lifetime* is above 0 every new personal access token, API key and terminal key needs an expiry within it, and the dialogs show "never expires" disabled. `0` lifts the cap, so a token may then never expire. Tokens created before the cap was lowered keep their expiry.
- A user changing their own password, in their account or in the user list, must give the current one. An administrator setting someone else's password is not asked. A directory account has no local password to change; a user without a usable password, such as one who signs in only with a passkey and forgot it, gets a new one from an administrator.

## 5 security setting defaults

| Setting | New install |
| ------- | ----------- |
| *Admin Settings → Mail → verify certificate* | On |
| *Admin Settings → Auth → verify certificate* (LDAP) | On |
| *Admin Settings → Features → Allow Private Webhook Targets* | On. The always refused targets of [9](#9-webhook-targets-and-signatures) are refused either way. |

- *Mail → Test connection* (`POST /admin/settings/mail/test`) gives a synchronous pass or fail against the relay before the setting takes effect for real mail. Without it a misconfiguration surfaces hours later as silent delivery failures of the background notification digest.
- *Auth → Test connection* binds with the new settings before they are stored, so a certificate problem is caught by an admin rather than by every user's next sign-in.
- The webhook target check runs when a subscription is created or edited and again before every delivery, with the setting as it is at that moment ([9](#9-webhook-targets-and-signatures)).

## 6 dead-lettered events

- A consumer group that fails the same event five times in a row moves it to the Redis stream `glados:events:dead`, together with the group that gave up, the original stream id, the delivery count and the time.
- The dead-letter stream keeps roughly the newest 10,000 events.
- `admin replay-dead-letters` puts them back on the events stream oldest first. Every consumer group sees a replayed event again, and groups that already handled it skip it, because each checks the producer's event id before acting.
- A webhook endpoint that is down does not hold up the webhooks group for its full timeout on every event. Once a subscription's last five attempts have all failed, posts to it are skipped for 60 seconds after the newest attempt, with a warning in the log. The event then counts as failed for that subscription, so it is redelivered or dead-lettered like any other failure.
- After the 60 seconds the next event tries the endpoint again, and one success closes the circuit. Skips write no delivery row, so the delivery log shows only real attempts.

## 6.1 republishing outbox events

- The relay marks each outbox row with the time it put the row on the stream (`published_at`) and keeps relayed rows for 30 days, the only full record of an event once Redis lost it.
- `admin republish-outbox` reads the rows relayed from `--since` on and before `--until`, optionally of the `--type` event types (class names, checked against the registered events), in id order and in batches of 500, and appends each to `glados:events` with its original type, payload and event id. `--dry-run` reads the same rows and prints the count per event type. A time without a UTC offset, an empty range or an unknown type is refused with exit code 2.
- A Redis failure part way stops the command with exit code 1 after printing how many went out. The rows before it are on the stream, and running it again with the same bounds puts them there once more, which the consumers skip.
- When Redis loses the stream or a consumer group, the group's worker gets `NOGROUP`, logs an error and creates the group again at the end of the stream (`$`), the same place a new group starts. The relay's next `XADD` creates the stream itself. Events relayed between the loss and the new group are therefore not delivered to that group until they are republished.
- Delivery is at least once, and the relay's order is not total either: within a batch rows go out in id order, but a transaction that took a lower id can commit after a higher one was relayed, and a republished event lands behind newer ones. Consumers therefore never rely on the order of events.
- Every consumer group keys on the producer's event id, so republishing an event it already handled repeats nothing, with the exceptions below:

| Group | What a republished event does when the group already handled it |
| ----- | ---------------------------------------------------------------- |
| `notifications` | Skipped while any notification of that event still exists. When every recipient deleted theirs, the notifications come back, and so does any mail the event sends. Two deliveries at once write one set: the unique index on (`source_event_id`, `user_id`) makes the later insert wait and then insert nothing, and that delivery rolls back and sends no mail. |
| `webhooks` | Skipped for every subscription with a successful delivery of that event id; a subscription that failed gets the post again. Receivers can also deduplicate on the `webhook-id` header, which carries the event id. |
| `auto_print` | Skipped for every template with a print job of that event id. The job row is written in status `printing` under the unique index on (`classifier`, `source_event_id`) and committed before anything is sent, and only the delivery whose insert wrote the row prints. Two deliveries at once print once: the later insert waits for the earlier transaction and then inserts nothing. A delivery that fails or is stopped before the send deletes its row again, so the redelivery prints. A row left in `printing` means the delivery ended after its claim, by a crash or by a database failure after the send; the label may be out, so the event is not printed again automatically and a missing label is reprinted from the record. A `failed` print (printer offline or rejecting) is not repeated either. |
| `pdm_sync` | Refreshes the file again: one more PDM read and sync run, with the same result. |
| `schedule` | Skipped when a walk already covered the event's generation. |
| `edp_pictures` | Keeps a picture already fetched for the same part, so nothing is downloaded again. |

## 7 RFID lookup

- An RFID tag is stored only as an HMAC lookup value, which saving a user's RFID writes, and a tag is looked up through the unique index on that value, so a lookup costs one indexed query whatever the number of users.
- The security setting `allow_rfid_login` switches every RFID lookup off: operator identification on the web surface (`POST /api/v1/web/production-operators/identify`) and the key surface's `POST /api/v1/key/users/rfid` both answer 403 while it is off.
- The tag travels in the request body, never in the URL, so it does not reach access logs or the request log. The key surface answers with the id, username and full name only.

## 8 database restore

The operator steps are in [OPERATIONS.md section 4.2](../OPERATIONS.md#42-restoring-the-database-out-of-process); the container mechanics are in [operations-storage-and-backup.md section 4](operations-storage-and-backup.md#4-database-restore-internals). The command is `src/bootstrap/cli/restore.py`.

- The restore never writes into the database `DATABASE__URL` names, the target. It works from a maintenance connection to the `postgres` database (`template1` when the target is itself called `postgres`), because Postgres cannot rename the database a session is connected to.
- It creates `<target>_restore_<timestamp>` from `template0`, with the target's encoding and collation when the target exists and UTF-8 otherwise. A name already taken gets a counter, and a long target name is shortened so every name fits the 63 byte identifier limit.
- It feeds the archive into `psql -X -v ON_ERROR_STOP=1 --single-transaction` against that database, so the first failing statement aborts the whole load. A damaged, truncated or wrongly keyed archive is detected while it is read; psql is then killed rather than given an end of input, which would commit the part loaded so far.
- `pg_dump` 17, which the backend image ships, writes `SET transaction_timeout = 0;` into every dump, and a Postgres older than 17 refuses that setting. For such a server the restore drops that one line from the dump's preamble.
- It then checks that the loaded database has a non-empty `alembic_version` table, which no complete Glados dump lacks, and reports its revision.
- Only then does it swap. When the target exists, it stops new connections to it (`ALLOW_CONNECTIONS false`), terminates the open ones, renames it to `<target>_pre_restore_<timestamp>` and allows connections to it again. It retries the rename for a few seconds while a terminated connection is still exiting. Then it renames the restored database to the target's name and checks once more that the name opens the restored data.
- When the target does not exist, as after losing it, the restored database simply takes its name and nothing is kept.
- Every failure before the swap drops the fresh database and leaves the target untouched. A failure to move the target aside leaves it under its name with connections allowed again. A failure to rename the restored database renames the previous one back; should that fail too, the command names both databases so an operator can finish the rename by hand.
- The command prints `Database restore FAILED.` and exits `1` on any failure, and prints `Database restore complete.` only after the final check. Argument errors exit `2`.
- The database user needs the right to create databases and to rename and terminate connections to the target, which the bundled Postgres's `POSTGRES_USER`, a superuser, has. The kept database is never dropped by the restore.
- The restore is proven on Postgres by `tests/pg/test_backup_restore_drill.py`, which CI runs on every pull request ([development-testing.md section 5.5](development-testing.md#55-the-backup-and-restore-drill)).

## 9 webhook targets and signatures

### 9.1 which targets are refused

- A webhook URL must use `http` or `https` and must not carry a user name or password. Any port is allowed.
- The host is refused by name when it is `localhost`, ends in `.localhost`, or is one of the stack's service names (`backend`, `frontend`, `postgres`, `redis`, `seaweedfs`, `pgadmin`, `maintenance`, `cloudflared`, `time-tracking`).
- Otherwise the host is resolved, and every A and AAAA answer must pass, not just the first. A host that does not resolve within five seconds is refused.
- An address is always refused when it is loopback, link-local (which includes the 169.254.169.254 cloud metadata address and `fe80::/10`), unspecified or in `0.0.0.0/8`, multicast, reserved, IPv6 site-local, or inside a subnet of `NETWORK__INTERNAL_SUBNETS`, which the release compose file sets to the stack's two pinned networks. An IPv4-mapped IPv6 address is judged as the IPv4 address it carries.
- Any other address that is not globally routable, such as RFC 1918, unique local IPv6 or the carrier-grade NAT range, passes only while *Allow Private Webhook Targets* is on.
- The check runs when a subscription is created or edited, where a refusal answers `400`, and again before every delivery and manual retry, where a refusal fails that delivery without sending anything. A subscription saved under looser rules is therefore stopped at its next delivery.
- The delivery connects to the first address the check returned, so a second DNS answer between the check and the request cannot redirect it. The Host header and the TLS server name stay the hostname, and the certificate is verified against the hostname.
- Redirects are not followed. A receiver that answers `3xx` counts as a failed delivery.
- The delivery log records only a short category for a failure (refused, timed out, connection failed, TLS failed, invalid HTTP), never the raw error or anything the remote end sent. Refusals name the host but not the address it resolved to. The response body is never read.

### 9.2 how a receiver verifies a delivery

Every delivery is signed the [Standard Webhooks](https://www.standardwebhooks.com) way, so the libraries that project publishes can verify it directly. The headers are:

| Header | Content |
| ------ | ------- |
| `webhook-id` | The event's message id. It stays the same on every redelivery and manual retry, so a receiver deduplicates on it. |
| `webhook-timestamp` | The time of this attempt in Unix seconds. |
| `webhook-signature` | `v1,` followed by the base64 HMAC-SHA256 of `{webhook-id}.{webhook-timestamp}.{body}`. |
| `X-Glados-Event` | The event type, such as `ProjectCreated`. |

- The signing secret is shown once when the subscription is created and has the form `whsec_` followed by base64. The HMAC key is the base64-decoded part after the prefix. Secrets created before this format are 64 hex characters without a prefix, and the same rule applies to them, since hex is valid base64.
- A receiver recomputes the signature over the raw body exactly as received, compares it in constant time with the value after `v1,`, and accepts the delivery only when the timestamp is within five minutes of its own clock. The timestamp check stops a captured delivery from being replayed later.
- In Python, without a library:

```python
import base64, hashlib, hmac, time

def verify(secret: str, headers: dict[str, str], body: bytes, tolerance: int = 300) -> bool:
    timestamp = int(headers["webhook-timestamp"])
    if abs(time.time() - timestamp) > tolerance:
        return False
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{headers['webhook-id']}.{timestamp}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(
        hmac.compare_digest(expected, part.split(",", 1)[1])
        for part in headers["webhook-signature"].split(" ")
        if part.startswith("v1,")
    )
```
