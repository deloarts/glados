# terminal infoscreens

The settings, bars and widgets of an infoscreen, everything its feed carries and where each widget's data comes from, the thumbnail and drawing links, the weather service, the rule that no person appears on a wall, and the live stream of a display. The guide [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) explains screens and terminals; the display schedule of a screen is in [terminal-display.md section 4](terminal-display.md#4-display-power).

- [terminal infoscreens](#terminal-infoscreens)
  - [1 screen settings](#1-screen-settings)
  - [2 header and footer bars](#2-header-and-footer-bars)
  - [3 widgets and permissions](#3-widgets-and-permissions)
  - [4 the feed](#4-the-feed)
    - [4.1 contents](#41-contents)
    - [4.2 language](#42-language)
    - [4.3 widget sources](#43-widget-sources)
    - [4.4 thumbnails and drawings](#44-thumbnails-and-drawings)
    - [4.5 no persons](#45-no-persons)
    - [4.6 weather](#46-weather)
  - [5 live updates](#5-live-updates)

## 1 screen settings

- The name is unique among live screens, enforced by a partial unique index.
- `color_mode` is `dark` or `light`.
- `theme_preset` is `Aura`, `Lara`, `Material`, `Nora`, or null for the tenant default.
- `primary_color` is a palette name like the user theme setting, or null for the tenant default.
- `language` is `enGB`, `deAT`, or null for the tenant's `default_language`, and a language that is not one of the app locales answers 422.
- `rotation_seconds` lies between 10 and 600.
- A screen also has a description, `show_banner`, a header and a footer bar, and the display schedule with `off_on_holidays`.
- A page has a layout with one slot per position: `full` 1, `two_columns` 2, `main_side` 2, `grid_2x2` 4, `two_rows` 2, `three_rows` 3, `grid_2x3` 6 (two columns by three rows, for portrait screens) and `grid_3x2` 6 (three columns by two rows).
- A slot holds one widget config or nothing.
- The pages are one JSON column, validated by `parse_pages` on every write.

## 2 header and footer bars

- The header (`show_header`) is on by default and the footer (`show_footer`) is off by default; they sit above and below the pages.
- Each bar has a `left`, a `center` and a `right` area, each listing its items left to right, and the center area stays centred on the screen whatever the widths of the other two.
- The items are `logo`, `app_name`, `company_name`, `title`, `clock`, `date`, `next_holiday`, `last_updated` and `text`, each at most once across the whole bar, plus an optional text for the `text` item.
- The header defaults to logo and title on the left and the clock on the right, and the footer to the last update time on the right.
- `parse_bar` validates a bar and still reads a bar stored as the earlier single `items` list.
- The logo, the app name and the company name come from the public branding endpoint, clock and date are rendered on the display, and `last_updated` is the feed's `generated_at`.

## 3 widgets and permissions

- The widgets are `machine_board`, `machine_detail`, `lots_due`, `late_lots`, `qa_queue`, `deliveries_expected`, `external_work`, `products`, `projects`, `weather`, `message` and `clock`.
- An order card shows the lot number, the part number and the article name, one per line, and no times; the feed's order cards carry no planned start or end.
- Reading screens and the preview needs no permission beyond being signed in.
- Creating, editing, archiving and restoring need `write:infoscreens`.
- Screens are archived, not deleted, and a terminal keeps showing an archived screen until it is reassigned.

## 4 the feed

### 4.1 contents

- The feed is one aggregate per screen, built by `BuildInfoscreenFeed` for both the device (`GET /terminal-device/feed`, 409 until approved with a screen) and the builder preview (`GET /infoscreens/{infoscreen_id}/feed`), so both answer the same.
- It carries the screen settings and ready-made data for each slot, where `widgets[p][s]` belongs to `pages[p].slots[s]`.
- It carries the global banner when the screen shows it and it is active now.
- It carries the next tenant holiday when a shown bar has the `next_holiday` item.
- It carries the generation time, the backend version and the tenant's default timezone, in which the display draws every clock, date and time.
- It carries the resolved `language` and the message to terminals the display shows.

### 4.2 language

- `language` is the screen's language, or the tenant's `default_language` when the screen has none.
- A display has no user session, and the terminal key's service account only serves the first sign-in of many displays, so neither is ever the source.
- The display shows its built-in copy (status words, default widget titles, bar and stale labels, waiting screens) in it and formats dates, weekdays and numbers in it.
- Text people typed stays as entered.

### 4.3 widget sources

| Widget | Source |
| ------ | ------ |
| `machine_board` | The live orders of the chosen machines and pool members with their stored planned window, open downtimes (state `down`), the machine calendars with tenant holidays (state `closed`) and a running order (state `running`); plus, per chosen pool (every pool when nothing is chosen, none when only machines are), the orders waiting on the pool without a machine, in queue order. |
| `lots_due` | Open lots whose target date (as the lots table resolves it) is on or before today plus the horizon, overdue ones first with their days late, optionally only those with orders on the chosen pools or floating on them. |
| `late_lots` | The late lots KPI's candidates projected to finish after their target date. |
| `qa_queue` | Open inspection orders, as on the QA worklist. |
| `machine_detail` | One machine (`machine_id`, required): its state, the order on it now (running or paused), or the next in queue when none is, with the made item, its full-size picture, its drawing when `show_drawing` is on, its revision, material, mass, base size, quantities and routing step, the item's source or bought item with the lot's input demand status and expected delivery, and the order's own lot; then the next `next_count` (0 to 5) orders as cards. No lot times. An archived or missing machine answers with `machine_name` null. |
| `deliveries_expected` | Open ordered supplier lines expected from today to the horizon, oldest first, and with `show_overdue` also the open lines expected before today, each with its days late; the display groups them by day and highlights today. |
| `external_work` | The parts that still have to leave for a supplier for an outside process, as the procurement list of external work dates them (`GetExternalWork`, through Planning & fulfillment's `application/facade/external_work.py`): latest pickup from today to `horizon_days` (0 to 30, default 7) ahead, and with `show_overdue` (default on) also the ones whose latest pickup has passed, each with its days late. Parts already handed to the supplier have left and are not shown. Optionally only the methods in `fabrication_method_ids` and, with `only_with_supplier`, only parts on an order. Each row carries the lot, the item, the quantity, the methods in the screen's language, the supplier or the methods' default supplier as a suggestion, the ready date, the latest pickup, the day it is due back and the alert. `layout` is `days` (default), grouped by the latest pickup, or `suppliers`, one lane per supplier with its next send-out day and how many parts are ready; the display groups the rows itself. |
| `products` | Live products marked active, by product number, and with `show_projects` the projects in status `active` on each. |
| `projects` | Projects in status `active`, by project number, with their product. |
| `weather` | The forecast for the widget's town from the weather service (section 4.6), with `status` `ok`, `unavailable` or `off`. |
| `message` | The widget's own text, Markdown of up to 2000 characters rendered on the display, with its severity (`none` for no colour, `info`, `success`, `warning`, `danger`), its horizontal alignment (`text_align`: `left` by default, `center`, `right`) and its vertical alignment (`vertical_align`: `top`, `middle` by default, `bottom`); a stored config without the alignment reads as the defaults. |
| `clock` | The next tenant holiday when asked for; the time is drawn on the display, digital (default), analogue or binary, with seconds when `show_seconds` is on. |

### 4.4 thumbnails and drawings

- Rows that name an item (order cards, lot, QA and delivery rows) carry `thumbnail_url`, the picture the app shows for that item (`pick_picture`) in its thumbnail variant.
- Lots and production orders use their made item, and deliveries their bought, source or made item.
- The pictures of one widget are looked up in one query per item kind (`infoscreen_thumbnails.py`).
- The link points at `GET /terminal-device/thumbnails/{token}`, which needs no header.
- The token is an HMAC, under a key derived for this purpose, over the item kind, id, variant and an expiry rounded to the end of the hour plus 30 minutes.
- A link is therefore valid for 30 to 90 minutes, and every feed built within the same hour carries the same link, so the browser cache keeps working.
- The answer has `Cache-Control: private, max-age` up to the expiry.
- An expired or forged token, an archived item or an item without a picture answers 404.
- The preview returns the same links.
- The machine detail widget links to the full-size picture (variant `image`, the thumbnail when only that exists) through the same endpoint.
- Its drawing link points at `GET /terminal-device/drawings/{token}`, which needs no header and answers the item's drawing PDF inline.
- The drawing token is an HMAC under its own derived key over the made item id, the drawing file id and the same expiry as a thumbnail link, so neither kind of token passes for the other.
- An expired or forged token, an archived item or a drawing replaced since answers 404 (`InfoscreenDrawingNotFoundError`).
- The display fetches the PDF and embeds it as an object URL opened to fit the page, as the file preview does.

### 4.5 no persons

- The feed models (`infoscreen_feed_dto.py`) are written for the feed and carry no names, usernames, emails, user ids, creators, operators or orderers.
- `tests/integration/test_infoscreen_feed_gdpr.py` walks the published schema of `InfoscreenFeedResponse` and fails on any such field or on a reference to a user schema.
- Customer names, which are companies and not persons but possibly confidential, appear only when the widget's `show_customer` is on.
- Products and projects carry no designated user and no creator.
- Announcements are per user, so a screen shows its own `message` widgets plus the global banner.

### 4.6 weather

- The weather widget stores a town, never an address: `location_name`, `region`, `country_code` and the town centre's `latitude` and `longitude`, which the domain rounds to two decimals (about a kilometre).
- The editor picks a country and searches its towns through `GET /infoscreens/weather-places?q=&country=&language=`, which needs `write:infoscreens` and asks OpenStreetMap's Nominatim for settlements only.
- Nominatim's usage policy allows one request per second and no search as you type, so the editor searches on its button or Enter, the backend spaces its searches at least 1.1 seconds apart per process, and keeps each answer for a day. The editor credits OpenStreetMap (ODbL).
- The feed asks MET Norway's Locationforecast 2.0 (`IWeatherService`, no key, CC BY 4.0) for now and the `days` (0 to 7) after today, counted in the tenant timezone; only the rounded coordinates reach it, and the widget credits the source (`attribution`).
- Both services ask every client to name itself: the User-Agent is `Glados/<version>` with the organisation's support or imprint URL and contact email from the general settings, never a user's address.
- A day is the entries on that calendar day: the highest and lowest temperature, the precipitation in millimetres with each period counted once, and as its symbol the twelve hour summary starting nearest 06:00, else the period nearest noon. The weather now is the first entry, with the wind converted to km/h.
- Forecasts are cached in each process per coordinate, day count and timezone for 15 minutes; when a fetch fails, a forecast fetched within the last 12 hours stands in with its own `fetched_at`, and the display shows its time once it is older than an hour.
- Without any forecast the widget answers `unavailable`.
- The security setting `enable_infoscreen_weather` (default true) switches the weather off: the feed answers `off` without calling either service, and the place search answers 503 (`WeatherUnavailableError`).
- Temperatures are in degrees Celsius, the wind in km/h and precipitation in millimetres; `symbol` is MET Norway's symbol code, such as `partlycloudy_day`, which the display draws as an icon.

## 5 live updates

- A display opens `GET /terminal-device/live`, an SSE stream with the same frames as the web live stream.
- The hub keeps terminal connections apart from user connections, keyed by terminal id, with a cap of two per terminal and process.
- A terminal connection fails closed: it receives its own terminal row and, once approved, its screen's row plus `production-orders`, `production-lots`, `production-machines`, `production-machine-pools`, `orders` and `terminal-broadcasts`.
- A pending or revoked terminal receives only its own row.
- When its own row changes, the stream re-reads the terminal before passing the next signal on, so a new screen or a revoke changes the filter at once.
- Web users receive the `terminals`, `infoscreens` and `terminal-broadcasts` topics like any other row.
- A display override, a location change and the actions on all terminals reach the displays through the signal of their own rows.
