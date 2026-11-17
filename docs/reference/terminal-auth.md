# terminal auth

How a display proves its identity, how an unknown display registers and is approved, what an admin can do to a terminal afterwards, and the address and rate limits in front of all of it. The guide [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) explains terminals and the bridge; [ADR 0010](../adr/0010-terminal-device-authentication.md) explains why displays use a key pair instead of a shared secret.

- [terminal auth](#terminal-auth)
  - [1 challenge](#1-challenge)
  - [2 session](#2-session)
    - [2.1 checks in order](#21-checks-in-order)
    - [2.2 known and unknown keys](#22-known-and-unknown-keys)
    - [2.3 renewal and the answer](#23-renewal-and-the-answer)
  - [3 every later request](#3-every-later-request)
  - [4 terminal keys](#4-terminal-keys)
  - [5 pairing and approval](#5-pairing-and-approval)
  - [6 actions on a terminal](#6-actions-on-a-terminal)
    - [6.1 single terminal](#61-single-terminal)
    - [6.2 all terminals](#62-all-terminals)
    - [6.3 audit](#63-audit)
  - [7 clone detection](#7-clone-detection)
  - [8 address allowlist and rate limit](#8-address-allowlist-and-rate-limit)
  - [9 permissions per route](#9-permissions-per-route)

## 1 challenge

- `POST /terminal-device/challenge {public_key}` answers a nonce that is valid for 60 seconds.
- The public key is the raw 32 byte Ed25519 key in base64url without padding, and anything else is refused.
- The nonce is stateless and has the form `v1.<expiry unix seconds>.<18 random bytes, base64url>.<HMAC-SHA256>`.
- The HMAC covers the version, the public key, the expiry and the random part, under a key derived from `SECURITY__SECRET_KEY_NON_PERSISTENT` for this purpose alone.
- Any worker can therefore check a nonce without shared state, and a nonce issued for one key is useless for another.
- The bridge signs `glados-terminal-auth-v1:` followed by the nonce with Ed25519 (`POST /identity/sign`).

## 2 session

`POST /terminal-device/session` carries the public key, the nonce, the signature and the device telemetry: user agent, screen size, frontend and bridge versions, and the hardware details under `device` ([terminal-display.md section 3](terminal-display.md#3-device-details)).

### 2.1 checks in order

1. Terminals are switched on and the client address is allowed, else 403.
2. The per address rate limit holds, else 429.
3. The nonce was issued for this key and has not expired, else 401 `TerminalChallengeError`.
4. The signature verifies, else 401 `TerminalSignatureError`.
5. The nonce has not been used before: it is claimed in the replay guard (Redis `SET NX EX`, shared by every worker) for 90 seconds, else 401 `TerminalChallengeError`.

### 2.2 known and unknown keys

- A known public key needs nothing more than the checks above.
- An unknown key needs a terminal key in `X-Api-Key`.
- No key answers 401 `TerminalKeyRequiredError`, an unknown, revoked or expired terminal key answers 401 `InvalidTerminalKeyError`, and any other API key answers 403 `NotATerminalKeyError`.
- The new terminal is created as pending with a pairing code, unless 20 terminals with a valid code already wait, which answers 409 `PendingTerminalLimitError`.
- Pending terminals whose code expired more than a day ago are removed at that moment.
- The public key is unique across terminals, enforced by a unique index.
- The partial unique indexes on terminals and infoscreens carry both dialect predicates.
- A revoked terminal that signs in again goes back to pending with a new code.
- A pending terminal whose code expired gets a new one.

### 2.3 renewal and the answer

- The answer is a terminal access token valid for 15 minutes, plus the device state ([terminal-display.md section 1](terminal-display.md#1-device-state)).
- The page repeats challenge, sign and session before the token runs out.
- Each renewal sends the telemetry and the hardware details again, so temperature, uptime and display state stay current.

## 3 every later request

Every other device request sends `Authorization: Bearer <terminal token>`. `get_current_terminal` reads only that header, never the session cookie, and resolves it through `AuthenticateTerminal`, which does the following.

- It verifies the token with the terminal signing key, else 401 `TerminalTokenInvalidError`.
- It applies the terminal switch, the terminal allowlist and maintenance mode, and the maintenance allowlist exempts a display like anyone else.
- It reloads the terminal row, so a revoke or a deletion takes effect at once.
- It refreshes `last_seen_at` and `last_ip` when they are older than two minutes or the address changed.

A revoked terminal can still read its state, which then says `revoked`, but gets no feed and no live data.

## 4 terminal keys

- A terminal key is an ordinary `ApiKey` whose service account holds exactly `connect:terminals`.
- `POST /admin/api-keys/terminal {name, expires_at}` creates it, needs `manage:api_keys` and has no permission picker.
- The security settings' token lifetime cap applies to the expiry: while it is above 0 the key needs an expiry within it.
- The API key list marks a terminal key with `kind: "terminal"` and filters on it with `?kind=terminal` or `?kind=standard`; `?expiry=unexpired` keeps the keys that never expire or expire later. The terminals tab asks for `kind=terminal&expiry=unexpired&limit=1` to tell whether a usable terminal key exists.
- Creating a key is audited.
- `NEVER_GRANTABLE_TO_TOKENS` keeps `connect:terminals` off normal API keys and PATs.
- `UserRules.assert_permissions_assignable` refuses `connect:terminals` on user create and update, and refuses to change the permissions of a terminal key's account.
- `get_current_api_key_user` answers 403 to any key holding `connect:terminals`, because the key router has routes that accept any valid key without a permission check.
- The only place a terminal key is accepted is the first session of an unknown device.
- Revoking or rotating a terminal key stops new registrations only, because a known device signs in with its key pair alone.

## 5 pairing and approval

- `POST /terminals/{terminal_id}/approve` needs `manage:terminals` and the pairing code shown on the display.
- The code has six characters from an alphabet without 0, O, 1, I and L.
- The code is unique among pending terminals, enforced by a partial unique index, and lives one hour.
- The code is compared in constant time, ignoring case and spaces.
- A wrong code answers 422 `PairingCodeMismatchError`, an expired one 422 `PairingCodeExpiredError`, and a terminal that is not pending 409.
- Approval sets the name and may set the location and the screen.

## 6 actions on a terminal

### 6.1 single terminal

- `PATCH /terminals/{terminal_id}` changes the name, the mode, the location or the screen, and an explicit `null` unassigns the screen or clears the location.
- Only the mode `infoscreen` is accepted; `kiosk` is reserved and refused by the rules.
- The location is free text of up to 200 characters, set on approval or later; it is searchable on the terminals tab and reaches the display in its state.
- An archived screen cannot be assigned.
- Revoke, reload and identify are `POST` actions on the terminal.
- Reload and identify set `reload_requested_at` and `identify_requested_at`, which the display compares with the values it last saw.
- `DELETE /terminals/{terminal_id}` removes the terminal, and its next sign-in counts as unknown.
- The display override is described in [terminal-display.md section 4.2](terminal-display.md#42-override).

### 6.2 all terminals

- `POST /terminals/all/reload`, `/all/identify` and `/all/revoke` act on every approved terminal.
- `POST /terminals/all/delete` deletes every terminal, waiting and revoked ones included.
- Each runs in one unit of work, so a failure leaves every terminal as it was, and answers `{count}`, the number of terminals it touched.
- Every touched row is signalled on the live channel as a single action would be.

### 6.3 audit

- Approval, revocation, screen reassignment and deletion are written to the audit trail under the `terminals` domain and logged.
- Revoking all and deleting all are written to the audit trail once, naming the terminals.

## 7 clone detection

- When a session starts from an address other than the one the previous, still valid token was issued to, `duplicate_detected_at` is set.
- A warning is logged and an audit entry without an actor is written.
- The terminals tab shows a badge.
- Nothing is revoked automatically, since a display that changed its DHCP lease looks the same.

## 8 address allowlist and rate limit

| Setting (`/settings/security`) | Default | Meaning |
| ------------------------------ | ------- | ------- |
| `enable_terminals` | true | Terminals may sign in at all, independent of `enable_api_key_auth`. |
| `terminal_allowed_ips` | empty | Addresses or CIDR networks displays may connect from; empty allows any. |
| `enable_infoscreen_weather` | true | The weather widget may call MET Norway and the editor's place search OpenStreetMap ([terminal-infoscreens.md section 4.6](terminal-infoscreens.md#46-weather)). |

- The client address is `request.client.host`, which the server takes from `X-Forwarded-For` only for a trusted proxy ([installation-deployment.md section 4](installation-deployment.md#4-forwarded-client-addresses)); a display cannot set it with a header of its own.
- Behind a reverse proxy the stack does not trust, every display appears with the proxy's address; the allowlist then only tells the proxy apart, and the per address rate limit is shared by every display.
- The rate limit is 60 challenge and 60 session requests per address and minute, kept per worker process.

## 9 permissions per route

- The challenge needs nothing and is rate limited.
- The session needs a signature, plus `X-Api-Key` for an unknown device, and is rate limited.
- State, feed and live need the terminal token; the feed answers 409 until the terminal is approved with a screen.
- `GET /terminal-device/thumbnails/{token}` needs only its signed token.
- `GET /terminals/` is open to every signed-in user, with identifying details only for holders of `manage:terminals`.
- Every action on a terminal needs `manage:terminals`: approve, `PATCH`, revoke, reload, identify, the display override and its removal, `DELETE` and the actions on all terminals.
- `POST /admin/api-keys/terminal` needs `manage:api_keys`.
- The permissions of messages to terminals and of infoscreens are in [terminal-display.md section 5.3](terminal-display.md#53-endpoints-and-the-author) and [terminal-infoscreens.md section 3](terminal-infoscreens.md#3-widgets-and-permissions).
