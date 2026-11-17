# terminal display

What a display receives in its device state and how the `/infoscreen` page behaves on it, the hardware details it reports and who may see them, the display power schedule and override, and messages to terminals. The guide [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) explains terminals and the page; sign-in is in [terminal-auth.md](terminal-auth.md) and the screens and their feed in [terminal-infoscreens.md](terminal-infoscreens.md).

- [terminal display](#terminal-display)
  - [1 device state](#1-device-state)
  - [2 the device page](#2-the-device-page)
    - [2.1 runtime and refresh](#21-runtime-and-refresh)
    - [2.2 the starting screen](#22-the-starting-screen)
    - [2.3 theme and language](#23-theme-and-language)
    - [2.4 messages and identify](#24-messages-and-identify)
  - [3 device details](#3-device-details)
    - [3.1 what the bridge reports](#31-what-the-bridge-reports)
    - [3.2 cleaning and storage](#32-cleaning-and-storage)
    - [3.3 who sees identifying details](#33-who-sees-identifying-details)
  - [4 display power](#4-display-power)
    - [4.1 schedule](#41-schedule)
    - [4.2 override](#42-override)
    - [4.3 how the rules compute changes](#43-how-the-rules-compute-changes)
    - [4.4 what the page does](#44-what-the-page-does)
  - [5 messages to terminals](#5-messages-to-terminals)
    - [5.1 content](#51-content)
    - [5.2 audience](#52-audience)
    - [5.3 endpoints and the author](#53-endpoints-and-the-author)

## 1 device state

- `GET /terminal-device/state`, and `state` in the session answer, carry the status, mode, name, location, the pairing code while pending, the assigned screen, the reload and identify request times, the display power with the moment it changes, and the message to terminals the display shows.
- The device state names no person, and a schema test fails on any person field in it.

## 2 the device page

### 2.1 runtime and refresh

- A display opens `/infoscreen` (`frontend/src/features/infoscreens/runtime/`, with the sign-in and the bridge client in `frontend/src/core/terminal/`).
- The page renders no app shell, not even for its first frame.
- It runs one runtime per page load that signs in, follows the device state and loads the feed.
- On the live stream a `terminals` or `terminal-broadcasts` signal refetches the state and any other signal refetches the feed, debounced.
- A 60 second poll of both state and feed is the fallback.

### 2.2 the starting screen

- From boot until the screen is drawn the display shows one view, a sign-in report, and booting and loading the infoscreen are the same view.
- The report shows a status code, a plain title and sentence, the six sign-in steps (terminal service, device key, Glados server, registration, approval, infoscreen) with the step that stopped and why, a box with what to check, and a footer with the retry attempt, the time of the last try, the device name, the web version and the Glados origin.
- A pending display shows its pairing code in the same frame on `/infoscreen/register`, and an approved display without a screen shows its name.
- A sign-in failure before the first device state is held back for five seconds, or until a second attempt failed too, because on a booting Pi the bridge or the network often comes up a moment after the browser.
- Failed sign-ins retry forever with a growing delay.
- Once a screen is shown, a failure that usually passes by itself (no answer, a rate limit, a rejected signature, a missing bridge) keeps the screen with its stale badge instead of the report.

### 2.3 theme and language

- The display remembers the theme and the language of the last screen it showed in `localStorage` under `glados.terminal.screen`, and blocked or full storage counts as nothing remembered.
- It applies both before the first render, so a boot does not flash the tenant default.
- Without a remembered language it starts in the tenant default that the public branding names.
- The feed's theme and language replace them as soon as the feed arrives and are remembered in turn.
- The builder preview wears the screen's theme and language as well, gives the viewer's own back on leave and remembers nothing.

### 2.4 messages and identify

- The message to terminals in the device state is shown on every view, the screen and the waiting screens alike.
- The `banner` style shows it as a banner above, `fullscreen` over the whole display, in the colour of its severity.
- Its text goes through the message widget's Markdown renderer, which allows no raw HTML and no images, shows links as their text and sanitises.
- A timer on the device clock hides it at `show_until` without another request.
- Showing a message never switches a display on.
- The identify overlay shows the terminal's name and, below it, its location.

## 3 device details

### 3.1 what the bridge reports

- Every session request, renewals included, carries the bridge's `GET /device` answer as `device`.
- It holds the computer model, serial and kernel, the installed memory in megabytes (else what the kernel can use), temperature, uptime and under-voltage, and the host's OS and hostname.
- It holds the display on the connector that drives a picture (else the first one with a display connected), with the make, model, serial, native resolution and physical size from its EDID, its connector, connection and power state, and whether the device has a CEC adapter.
- `throttled` is always null, since the bridge cannot read the firmware's throttling flags.
- When the bridge cannot answer `/device` the request carries `device: null`, which keeps the previous details, and the sign-in goes ahead.
- A session without `device` keeps the details of the previous one.

### 3.2 cleaning and storage

- All of it is optional and untrusted, and nothing in it is interpreted.
- The wire refuses only text over a kilobyte or a number that is not finite.
- `parse_device_details` cuts every text to its cap (64 characters for serials, make, connector and power state, 200 for models, kernel and OS, 253 for the hostname), turns line breaks into spaces, drops control characters and drops a number outside its plausible range, instead of refusing the session.
- The details the terminals table shows (computer model, RAM, OS, display make, model and resolution) are typed columns, the rest is the JSON column `device_details`, and `device_reported_at` records when they arrived.

### 3.3 who sees identifying details

- `GET /terminals/` is open to every signed-in user.
- Only holders of `manage:terminals` get what identifies one device: the key fingerprint, the client addresses (`last_ip` and `last_session_ip`) and, inside `device`, the computer serial, the display serial and the hostname.
- For anyone else the backend answers these fields as `null` and sets `identifying_details_visible` to false; the frontend does not merely hide them.
- The answers of the admin actions always carry them, since those need the permission anyway.

## 4 display power

Glados decides and the display executes: the device state carries `display_power` (`on` or `off`) and `display_power_changes_at`, and the page asks for its state again at that moment, so the server runs no scheduler.

### 4.1 schedule

- The schedule belongs to the infoscreen, and every terminal showing the screen follows it.
- `display_schedule_mode` says which schedule that is: `default` follows the default schedule, `own` the screen's own `display_schedule` and `off_on_holidays`, and `always_on` keeps the displays on whatever either says. A new screen follows the default.
- The default schedule is one singleton row with the same two fields (`GET` and `PUT /infoscreens/display-schedule-default`). Reading it is open to every signed-in user, and setting it needs `write:infoscreens`. Until one is saved it is always on.
- A terminal without a screen follows no schedule and stays on.
- Saving the default signals the live topic `infoscreen-defaults`, which reaches every approved display showing a screen, so it reads its state again at once. A display reads its state again on a change of its screen's row too.
- `display_schedule` lists, per weekday, the windows in which the display is on, as `HH:MM` wall clock times of the tenant timezone (`default_timezone` of the general settings).
- A window ends on its own day, and `24:00` ends it at midnight.
- Windows of one day may touch but not overlap, and there are at most six per day.
- A weekday without windows is off all day.
- `off_on_holidays` keeps the display off on the tenant holidays, the same holidays the machine calendars and the clock widget use.
- No schedule and no holiday rule means always on.
- The editor works in half-hour slots: it shows each day as 48 slots, saves every run of slots that are on as one window, and widens a stored window that does not start and end on a half hour to the half hours around it, with a note, before it is saved again.

### 4.2 override

- `POST /terminals/{terminal_id}/display-override {power, until}` forces the display on or off until `until`.
- Without `until` the override lasts until the next change of the schedule, and when the schedule foresees no change the override needs an end.
- The end must lie in the future and within 31 days.
- The override needs `manage:terminals` and an approved terminal, else 409.
- `DELETE /terminals/{terminal_id}/display-override` hands the display back to the schedule.
- The override travels to the display through the live sync of its own row, like a reload request.
- A pending or revoked display stays on, since it shows a waiting screen.

### 4.3 how the rules compute changes

- `display_power_rules` turns the windows into instants day by day, so a day with a daylight saving change has its real length and a window keeps its wall clock times.
- A time the change skips is read with the offset before it.
- Windows that touch across midnight merge, so a display running through the night reports one change in the morning.
- The rules look two weeks ahead, and a display whose power does not change within that horizon gets no change time and picks up a later change through its regular state polling.
- The terminals list shows the same power and change time for each terminal.

### 4.4 what the page does

- The page has the bridge switch the display (`POST /display` on `localhost:8600`) on the first device state and whenever the wanted power changes.
- With every later state it reads `GET /display` and switches again when the bridge disagrees, because a restarted bridge has forgotten the request and a restarted kiosk has turned the display back on.
- A switch the bridge could not make is tried again with the next state.
- The page refetches its state one second after `display_power_changes_at`, once per change, so a device clock running ahead of the server does not refetch in a loop.
- While the display is off the feed of the screen shown is not refreshed, but the state polling and the live stream go on.
- A newly assigned screen still loads its first feed while off, and the feed is refreshed when the display comes back on.
- Nothing is switched before the first device state, so a booting display stays on as the kiosk starts it.
- While Glados cannot be reached the display keeps its last state.

## 5 messages to terminals

A message to terminals is a one-time text shown on many displays at once, separate from the global banner, which reaches web users too.

### 5.1 content

- The text has up to 2000 characters, is written in Markdown, stored as typed and rendered on the display.
- The severity is `info`, `warning` or `danger`.
- The style is `banner` above the screen or `fullscreen` over it.
- `show_until` must lie in the future and at most 30 days ahead, and the display hides the message at `show_until` on its own clock.

### 5.2 audience

- The audience is every terminal (`all_terminals`, the default) or a pick of terminals and infoscreens.
- A terminal is reached when it is picked itself or shows a picked infoscreen.
- The screen pick resolves live, so a terminal moved to another screen starts or stops showing the message.
- Only approved terminals are reached, and both every terminal and terminal picks include those without a screen.
- A pick must name at least one terminal or screen, at most 500 of each, and every id must exist.
- Several messages can be active at once, and a terminal shows the newest active one that reaches it.
- Whether a message reaches a display is decided when the display reads its state again, so every approved display gets the live signal of a message sent or ended.

### 5.3 endpoints and the author

- `POST /terminal-broadcasts/` sends a message and `POST /terminal-broadcasts/{broadcast_id}/end` ends it now; ending an ended one changes nothing.
- Both need `manage:terminals` and are written to the audit trail.
- `GET /terminal-broadcasts/` lists the active messages, newest first, and every listed message carries its own `reach_count`.
- `POST /terminal-broadcasts/reach` counts the approved terminals a draft audience reaches now.
- Listing and counting are open to every signed-in user.
- The author is stored for the audit trail and listed on the terminals page, but never sent to a display.
- The device state and the feed carry `TerminalBroadcastMessage` (id, text, severity, style, `show_until`), and a schema test fails on any person field in the device state.
- The builder preview of a screen shows the newest active message that goes to every terminal or picks that screen.
