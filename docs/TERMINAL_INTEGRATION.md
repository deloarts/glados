# terminal integration

- [terminal integration](#terminal-integration)
  - [1 purpose and scope](#1-purpose-and-scope)
  - [2 components and data flow](#2-components-and-data-flow)
  - [3 setting up a display](#3-setting-up-a-display)
  - [4 device sign-in](#4-device-sign-in)
    - [4.1 the handshake](#41-the-handshake)
    - [4.2 the device page](#42-the-device-page)
  - [5 terminal keys](#5-terminal-keys)
  - [6 approval and the terminal lifecycle](#6-approval-and-the-terminal-lifecycle)
    - [6.1 display power](#61-display-power)
    - [6.2 messages to terminals](#62-messages-to-terminals)
  - [7 infoscreens and the feed](#7-infoscreens-and-the-feed)
  - [8 live updates](#8-live-updates)
  - [9 configuration](#9-configuration)
  - [10 security](#10-security)
    - [10.1 assets](#101-assets)
    - [10.2 trust boundaries](#102-trust-boundaries)
    - [10.3 main threats](#103-main-threats)
    - [10.4 operator duties](#104-operator-duties)
  - [11 limits and open points](#11-limits-and-open-points)

## 1 purpose and scope

Wall displays in halls, production and offices show what is going on at their location, with nobody touching them. Each display is a TV driven by a Raspberry Pi that runs [glados-terminal](https://github.com/deloarts/glados-terminal): a kiosk browser plus a small local bridge that holds the device's key pair. The browser opens one fixed Glados URL, the display registers itself, shows a pairing code, and someone with the right permission approves it in Glados and picks what it shows.

Two concepts carry this. A **terminal** is one physical display and is managed on the Resources tab `/resources/terminals`. An **infoscreen** is a screen definition, built on `/resources/infoscreens`, and can be shown on many terminals; a terminal shows at most one. A terminal has a mode; only `infoscreen` exists today, and `kiosk` is reserved and refused.

Only displays with the glados-terminal bridge are supported. Without the bridge the page's sign-in report stops at its first step, the terminal service, and says what to check; there is no fallback that puts a secret into the URL. [ADR 0010](adr/0010-terminal-device-authentication.md) explains why.

## 2 components and data flow

```
TV + Pi (glados-terminal)                       Glados
┌───────────────────────────────┐               ┌────────────────────────────────────┐
│ kiosk browser: /infoscreen     │──HTTPS───────▶│ /api/v1/web/terminal-device/*       │
│   │ GET  /identity             │               │   challenge, session, state, feed,  │
│   │ POST /identity/sign        │               │   live (SSE)                        │
│   ▼                            │               │ /api/v1/web/terminals/*  (admins)   │
│ bridge on localhost:8600       │               │ /api/v1/web/infoscreens/* (builders)│
│   Ed25519 private key          │               │ /api/v1/web/admin/api-keys/terminal │
└───────────────────────────────┘               └────────────────────────────────────┘
```

The bridge generates the key pair on first start and never lets the private key leave the Pi. It answers `GET /identity` with the public key and the terminal key from its `.env`, and `POST /identity/sign` with a signature over the nonce it is given. It also switches the display when the page asks (`GET` and `POST /display`) and describes the device (`GET /device`); `docs/BRIDGE_API.md` in glados-terminal has the exact shapes. It decides nothing; every check happens in Glados.

On the Glados side the terminals, infoscreens, messages to terminals and the device endpoints live in the `operations` module (`backend/src/modules/operations/`), the feed use case in `backend/src/read/`, the live hub in the `platform` module, and the device page in `frontend/src/features/infoscreens/runtime/` with its sign-in and bridge client in `frontend/src/core/terminal/`.

## 3 setting up a display

1. On the API keys tab of the settings (`/settings/apiKeys`), choose "Create terminal key" (needs `manage:api_keys`). The raw key is shown once, as an `IDENTITY__API_KEY=…` line.
2. On the Pi, in glados-terminal's `.env`, set `KIOSK_URL` to the Glados `/infoscreen` page, `BRIDGE__ALLOWED_ORIGINS` to the Glados origin and `IDENTITY__API_KEY` to the key, then start the stack.
3. The Pi opens `/infoscreen`, registers and shows a six character pairing code.
4. On `/resources/terminals` (needs `manage:terminals`), approve the terminal: type the code shown on the TV, name it and pick the screen. The TV switches within seconds.
5. Screens are built on `/resources/infoscreens` (needs `write:infoscreens`), before or after.

One terminal key can register any number of displays. Revoking or rotating it stops new registrations only; enrolled displays keep working, because a known device signs in with its key pair alone.

## 4 device sign-in

### 4.1 the handshake

A display signs in with three steps: it asks Glados for a challenge, has the bridge sign it, and exchanges the signature for a session. The challenge is a short-lived nonce bound to the display's public key, so any worker can check it without shared state and it is useless for another key; a replay guard in Redis makes sure each nonce is used once. A known key needs nothing more. An unknown key must also present a terminal key, and the display is then created as pending with a pairing code. The session answer is a terminal access token that lives 15 minutes, plus the device state, and the page repeats the handshake before the token runs out.

Every later device request carries that token as a bearer header, never the session cookie. Each request reloads the terminal row, so a revoke or a deletion takes effect on the next request, and a revoked display can still read its state but gets no feed and no live data.

Full rules: [reference/terminal-auth.md](reference/terminal-auth.md).

### 4.2 the device page

A display opens `/infoscreen`, which renders no app shell and runs one runtime per page load: it signs in, follows the device state and loads the feed. Until the screen is drawn it shows a sign-in report that names the step that stopped (terminal service, device key, Glados server, registration, approval, infoscreen) and what to check, and it retries forever. A pending display shows its pairing code and an approved display without a screen shows its name. Once a screen is shown, a passing failure keeps the screen with a stale badge instead of the report.

The page remembers the theme and language of the last screen so a boot does not flash the tenant default, sends the bridge's hardware report with every session, switches the display on and off through the bridge as the device state asks, and shows messages to terminals and the identify overlay on every view.

Full rules: [reference/terminal-display.md](reference/terminal-display.md).

## 5 terminal keys

A terminal key is an ordinary API key whose service account holds exactly `connect:terminals`, created on the API keys tab with no permission picker. Its only use is the first session of an unknown device. Nothing else can grant `connect:terminals`, and the key router refuses any key holding it, because some key routes accept any valid key without a permission check.

Full rules: [reference/terminal-auth.md section 4](reference/terminal-auth.md#4-terminal-keys).

## 6 approval and the terminal lifecycle

```
            unknown key + terminal key
                      │
                      ▼
   ┌────────────── pending ◀───────────── revoked
   │  approve with      │      sign-in again   ▲
   │  matching code     ▼                      │ revoke
   └─────────────▶ approved ───────────────────┘
```

A person with `manage:terminals` approves a pending terminal by typing the pairing code shown on the TV, which proves they stand in front of that display. Afterwards an admin can rename the terminal, give it a free text location such as "Hall 2, north wall above gate 3", assign or unassign its screen, ask it to reload or identify itself, revoke it or delete it, one at a time or on all terminals at once. A deleted terminal counts as unknown on its next sign-in, and a revoked one goes back to pending.

When a session starts from another address than the previous, still valid token, Glados marks the terminal as a possible clone and audits it, but revokes nothing, since a display with a new DHCP lease looks the same.

The terminals list is open to every signed-in user, but the details that identify one device (key fingerprint, client addresses, serials, hostname) are only answered to holders of `manage:terminals`.

Full rules: [reference/terminal-auth.md](reference/terminal-auth.md) sections 5 to 7, and device details in [reference/terminal-display.md section 3](reference/terminal-display.md#3-device-details).

### 6.1 display power

Displays switch off on a schedule and on demand. Glados decides and the display executes: the device state says whether the display should be on and when that next changes, and the page asks again at that moment, so the server runs no scheduler. The schedule belongs to the infoscreen, as windows per weekday in the tenant timezone, optionally off on tenant holidays, and every terminal showing the screen follows it. An admin can override one terminal's power for a while, and the override hands back to the schedule when it ends.

Full rules: [reference/terminal-display.md section 4](reference/terminal-display.md#4-display-power).

### 6.2 messages to terminals

A message to terminals is a one-time Markdown text shown on many displays at once, as a banner or full screen, until a set time. It is separate from the global banner, which reaches web users too. It goes to every terminal or to a pick of terminals and infoscreens, and a display never learns who sent it.

Full rules: [reference/terminal-display.md section 5](reference/terminal-display.md#5-messages-to-terminals).

## 7 infoscreens and the feed

A screen has a look (colour mode, theme, primary colour, language), a rotation interval, optional header and footer bars, the display schedule, and pages. Each page has a layout with a fixed number of slots, and each slot holds one widget: machine board, lots due, late lots, QA queue, expected deliveries, a message or a clock. Reading screens needs only a sign-in; building them needs `write:infoscreens`. Screens are archived, not deleted, and a terminal keeps showing an archived screen until it is reassigned.

The feed is one aggregate per screen with ready-made data for every slot, built by the same use case for the display and the builder preview, so both show the same. It also carries the global banner, the next holiday, the tenant timezone in which the display draws every time, the language and the active message to terminals. The language is the screen's own or the tenant default, never a user's, because a display has no user. Item rows carry short-lived signed thumbnail links that need no header, and the machine view links to the item's drawing the same way. The weather widget is the one place where the backend calls public services: MET Norway for the forecast, with nothing but the rounded centre of a town, and OpenStreetMap's Nominatim for the editor's place search. Both are free for any use, both ask for a credit the screen and the editor show, and an admin can switch them off in the security settings.

No person appears on a wall: the feed models carry no names, users, creators or operators, a schema test enforces it, and customer names appear only where a widget asks for them.

Full rules: [reference/terminal-infoscreens.md](reference/terminal-infoscreens.md).

## 8 live updates

A display opens an SSE stream with the same frames as the web live stream. Its connection fails closed: it receives only its own terminal row until approved, and then its screen plus the topics its widgets read. A change to its own row re-reads the terminal at once, so a new screen or a revoke changes what it receives immediately. The page also polls every 60 seconds as a fallback.

Full rules: [reference/terminal-infoscreens.md section 5](reference/terminal-infoscreens.md#5-live-updates).

## 9 configuration

The security settings (`/settings/security`) switch terminals on or off, independently of API key auth, and can restrict them to address ranges. The client address is the one the stack resolves from trusted proxies only ([INSTALLATION.md, section 6.7](INSTALLATION.md#67-client-addresses-behind-proxies)), so a display cannot claim another address; behind a proxy Glados is not told to trust, every display shares that proxy's address for the allowlist and the rate limit. The devices live in `terminal_table` and `infoscreen_table`, with `infoscreen_display_default` for the display defaults and `terminal_broadcast_table` with its join tables `terminal_broadcast_terminal_table` and `terminal_broadcast_infoscreen_table` for broadcasts; the security settings add `enable_terminals`, `enable_infoscreen_weather` and `terminal_allowed_ips` to `admin_security_settings`.

Full rules: [reference/terminal-auth.md section 8](reference/terminal-auth.md#8-address-allowlist-and-rate-limit).

## 10 security

### 10.1 assets

- The Ed25519 private key of each display is its identity.
- Terminal keys let a device register itself.
- Terminal access tokens let a display read its state, its feed and live data.
- The production data a feed shows is an asset, and so is the promise that no person appears on a wall.

### 10.2 trust boundaries

- **Kiosk browser to bridge.** This is `localhost` on the Pi, and the bridge only answers the configured Glados origin.
- **Display to Glados.** This runs over HTTPS, and the network between hall and server is not trusted.
- **Admin browser to Glados.** This is the normal web session.
- **The room.** Anyone in front of a display can read it and may get physical access to the Pi.

### 10.3 main threats

The main threats are a stolen or replayed sign-in, a leaked terminal key, a token used on the wrong surface, a stolen or copied display, personal data on a wall and untrusted hardware reports. The key pair, the bound and single-use nonce, the pairing code typed by a person, separate token keys, the reload on every request and the person-free feed models answer them. What remains is mainly physical access to a Pi, a proxy Glados is not told to trust that hides client addresses, and a replay guard that fails open while Redis is down.

Full threat table and residual risks: [reference/terminal-security.md](reference/terminal-security.md).

### 10.4 operator duties

- Serve Glados over HTTPS and keep `SECURITY__SECRET_KEY_NON_PERSISTENT` secret; rotating it ends every terminal token, and displays sign in again on their own.
- Set `terminal_allowed_ips` to the display networks where they are known.
- Give terminal keys an expiry and revoke them once the displays are set up.
- Check terminals marked as possible clones.
- If a Pi goes missing, delete its terminal in Glados and rotate the terminal key it carried, which means revoking that key and creating a new one for the next displays. Revoking the terminal alone is not enough, because a revoked display that signs in again goes back to pending and shows a new pairing code that someone could approve, and it needs no terminal key for that. A deleted terminal counts as unknown, so it can only register again with a valid terminal key.

## 11 limits and open points

- The key router's routes that accept any valid key without a permission (products, projects, `users/rfid`) are unchanged; terminal keys are refused there instead.
- There is no generic `/terminal` entry point, no setup script and no scheduled colour mode.
- The `kiosk` mode is reserved and refused by the rules.
- Chromium's Local Network Access may block the page's calls to the bridge on `localhost`; the glados-terminal kiosk image writes a managed policy for the Glados origin, which still needs verifying on a Pi.
