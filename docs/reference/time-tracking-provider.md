# time tracking provider contract

The HTTP contract between Glados and a time tracking service, which Glados defines and every service implements, and the rules behind the numbers of the Time Tracking view. The guide [TIME_TRACKING.md](../TIME_TRACKING.md) explains the integration; settings and credentials are in [time-tracking-credentials.md](time-tracking-credentials.md).

- [time tracking provider contract](#time-tracking-provider-contract)
  - [1 conventions](#1-conventions)
  - [2 routes](#2-routes)
  - [3 sealed credentials](#3-sealed-credentials)
  - [4 the binding](#4-the-binding)
  - [5 values and errors](#5-values-and-errors)
    - [5.1 values](#51-values)
    - [5.2 errors](#52-errors)
  - [6 the time tracking view](#6-the-time-tracking-view)
    - [6.1 routes](#61-routes)
    - [6.2 rules behind the numbers](#62-rules-behind-the-numbers)
    - [6.3 read rights](#63-read-rights)
    - [6.4 load limits](#64-load-limits)
  - [7 versions](#7-versions)

## 1 conventions

- Every route except `GET /health` takes the header `X-Api-Key`.
- Credentials only ever travel sealed and in a request body, so every route that carries them is a `POST`. Request bodies reject unknown fields.
- Durations are whole seconds, datetimes are UTC with an offset (Glados rejects a booking time without one), dates are ISO dates in the attendance system's calendar.
- The service stores nothing and answers with `Cache-Control: no-store`.
- Glados validates every answer against its own wire models in `adapters/outbound/external/time_tracking_service/models.py`, which ignore fields they do not name; a missing or mistyped required field is a `TimeTrackingProviderError`.
- The client never follows a redirect.

## 2 routes

| Route | Purpose |
| ----- | ------- |
| `GET /health` | `{status, version}`, for the Host tab's service panel. |
| `GET /api/v1/info` | `service`, `version`, `contract_version`, `provider_label` (the name Glados shows), `credential_fields`, `credential_public_key`, `credential_key_id` and the current `binding`. Contacts nothing behind the service. |
| `GET /api/v1/status` | `provider_label`, `server_version`, `default_project` of the attendance system, read without user credentials. The admin connection test. |
| `POST /api/v1/credentials/verify` | `{sealed_credentials}`. Signs in, checks the rights, signs out. Answers `binding`, `employee_name` and `rights` `{days, month, year}`. |
| `POST /api/v1/months` | `{sealed_credentials, binding, month: "YYYY-MM"}`. Answers `employee_name`, `month` and `fetched_at`. Future months are refused. |
| `POST /api/v1/years` | `{sealed_credentials, binding, year}`. Checks the year right, then answers the months of the year up to the current one as `months`, read in one session. A future year is refused. |

`credential_fields` lists `{name, kind, required, max_length}` with `kind` `text` or `secret`. Glados renders a user name (`user`, text) and a password (`password`, secret); a service asking for any other required field is reported as unsupported by the connection test, and optional fields Glados does not render are left out of the sealed value.

## 3 sealed credentials

- HPKE (RFC 9180) in base mode with DHKEM(X25519, HKDF-SHA256), HKDF-SHA256 and ChaCha20-Poly1305, `info` the bytes `glados time tracking credentials v1`.
- The plaintext is UTF-8 JSON with one entry per credential field, `{"user": "...", "password": "..."}`.
- The sealed value is the HPKE ciphertext in base64url without padding.
- The public key is the confirmed `credential_public_key`, 32 raw X25519 bytes in base64url.
- Glados seals in `infrastructure/security/time_tracking_sealer.py` at save time and never holds the plaintext beyond that request.

## 4 the binding

The binding is an opaque value the service derives from the server it talks to and its credential key. `verify` answers it, Glados stores it with the sealed value, and every month or year request sends it back. The service answers `binding_changed` for a binding that is not its current one, without contacting the attendance system, so credentials never reach a server they were not verified for.

## 5 values and errors

### 5.1 values

- A month has `first_day`, `last_day`, `days` in order and `accounts`.
- A day has `date`, `target_seconds`, `worked_seconds` (null while open), `first_in`, `last_out`, `status` and `bookings`, and optionally `shift_name`, `shift_short_name` and `running_balance_seconds`, which a system without shifts or a running balance omits.
- `status` is `normal`, `shift_free`, `holiday`, `absence` or `open`.
- A booking is `{at, direction}` with direction `in` or `out`; Glados sorts them by time.
- An account has `account_id`, `name`, `short_name`, `format` and its values `pre`, `sum` and `post` before, during and after the month. `format` is `duration_clock` (seconds as h:mm), `duration_hours` (seconds as decimal hours), `count`, `decimal` (two places), `money` (cents) or `raw`; a format Glados does not know reads as `raw`. Glados never interprets an account by its name or id.

### 5.2 errors

Every error answer is `{code, message}`. Glados maps the code onto its domain errors and never shows the message to users.

| Code | Glados error |
| ---- | ------------ |
| `credentials_rejected` | `TimeTrackingAuthenticationFailedError`, which marks stored credentials as rejected. |
| `permission_denied` | `TimeTrackingPermissionDeniedError`; the month or year view then shows the missing right. |
| `binding_changed`, `credentials_unreadable` | `TimeTrackingBindingChangedError`, which drops the stored sealed value. |
| `period_invalid` | `TimeTrackingPeriodInvalidError`. |
| `provider_unavailable` | `TimeTrackingUnavailableError`. |
| `api_key_invalid` (HTTP 401) and every other code | `TimeTrackingProviderError`. |

A transport failure towards the service is a `TimeTrackingUnavailableError`.

## 6 the time tracking view

### 6.1 routes

| Route | Purpose |
| ----- | ------- |
| `GET /time-tracking/me/month?month=YYYY-MM` | The user's month with totals. |
| `GET /time-tracking/me/year?year=YYYY` | The year overview, month by month. |

- Both serve only the signed-in user's own data and need no permission beyond being signed in.
- Both refuse future periods before the service is asked, and answer with `Cache-Control: no-store`.
- The month answer lists every day (with weekday, live worked time and day balance added), every account, the totals (today's live figures, and worked, target and balance of the days up to today), the rights and the fetch time.

### 6.2 rules behind the numbers

These live in `time_tracking_summary.py` and `time_tracking_time.py`, in Glados, so every service gets the same figures.

- Worked time of a closed day is the system's own figure.
- Today's open day is computed live from its bookings: closed in and out pairs plus the time since the last "in", every stamp truncated to the minute first.
- Only days up to today, in the instance's default time zone, count towards the month's worked and target time.
- Today's running balance is the system's figure once the day is closed, and otherwise the latest reported balance before today plus today's live day balance.
- While clocked in, "target reached at" is now plus the time still missing.
- A year line is a month's totals with the last running balance reported up to today as its end balance.

### 6.3 read rights

- `verify` reports whether the account may read single days, a month and a year; Glados shows them after Save and Check access and stores none of them.
- A month read without the right answers the rights and no data; the year section is hidden when the month already says the year may not be read.

### 6.4 load limits

- A user may fetch at most one month and one year every 5 seconds.
- The service limits its own concurrent sessions on the attendance system.

## 7 versions

- `contract_version` is the contract's own `major.minor`, independent of the service's version.
- Glados lists the minors it supports in `SUPPORTED_CONTRACT_MINORS` (`application/services/time_tracking_service.py`), today `0.1`. The connection test warns about any other; calls are not blocked by it.
- A contract change that a service must follow bumps the minor here and in the service, together.
