# operations: lifecycle drift and repair

This file holds the exact output, semantics and exit codes of the `lifecycle-drift` and `lifecycle-repair` admin commands, and the fact anomalies neither of them settles. What the commands are for and how to run them is in [OPERATIONS.md sections 5.9 and 5.10](../OPERATIONS.md#59-lifecycle-drift-report); why statuses are derived is in [ADR 0008](../adr/0008-derived-lifecycle-statuses.md).

- [operations: lifecycle drift and repair](#operations-lifecycle-drift-and-repair)
  - [1 drift report](#1-drift-report)
    - [1.1 options](#11-options)
    - [1.2 compared fields](#12-compared-fields)
    - [1.3 fact anomalies in the report](#13-fact-anomalies-in-the-report)
    - [1.4 how the report reads](#14-how-the-report-reads)
    - [1.5 exit codes](#15-exit-codes)
  - [2 repair](#2-repair)
    - [2.1 what it writes](#21-what-it-writes)
    - [2.2 options and output](#22-options-and-output)
    - [2.3 concurrency and retries](#23-concurrency-and-retries)
    - [2.4 exit codes](#24-exit-codes)
  - [3 settling fact anomalies](#3-settling-fact-anomalies)

## 1 drift report

The stored lifecycle status of a lot, lot position, production order, order, order line or demand is derived from quantities, deliveries, completions, interruptions, allocations and the timestamps an action records, such as when a lot was put on hold or an order was canceled. `lifecycle-drift` lists every stored lifecycle field that disagrees with that derivation and changes nothing.

### 1.1 options

- `--json` prints one JSON document with the rows and a summary per table instead of the table.
- `--only lots,orders` limits the report to some of the tables `order_items`, `orders`, `production_orders`, `lot_positions`, `lots`, `bought_demands`, `made_demands` and `source_demands`.
- `docker compose run -T` keeps the terminal's line endings out of a saved report.

### 1.2 compared fields

Each row shows the `table`, the `id` and `public_id`, the `field` that differs, the `stored` and the `derived` value, the `rule` that decided the derived value and the `facts` it read.

| Field | Compared |
| ----- | -------- |
| `status` | On every table, against the first applicable row of the table's decision table; the rule column names the table and the row, for example `lot_status row 3`. |
| `kind` | On lot positions: mixed, external, internal or unassigned, from the order line and the production orders of the position. |
| `quantity_completed` | On lot positions: the delivered pieces of the order line plus the pieces the position's production orders completed, never above the position quantity. |
| `completed_at`, `actual_end`, `delivery_date` | The stamp of a completed lot, a completed production order and a delivered order. A stamp is set exactly while its status holds, so a derived `-` means the stamp should be cleared and `set` means it is missing. |
| `ordered_date` | On orders: recorded the first time the order derives ORDERED without one and never cleared, so the derived value is always `set` and means the date is missing. |
| `cancelled` | On source demands: set exactly while the demand's cancel is recorded. |

### 1.3 fact anomalies in the report

A fact anomaly is a contradiction in the facts themselves, which only a person can settle. The `rule` column says so and the JSON row carries `"anomaly": true`.

- A lot position whose facts give it more completed pieces than its quantity is a fact anomaly. Its stored count stays at the quantity.
- An order line whose stored `quantity_delivered`, `quantity_rejected` or `quantity_rejected_lost` differs from the sum over its delivery rows is a fact anomaly, with the column as the `field`, the stored total as `stored` and the sum over the rows as `derived`. It means a booking without its row, or a row without its booking.
- Without `--only`, the report also lists, in the table `part_number_registry`, every part number a made or bought item carries whose registry entry is missing or names the other catalogue. The row names the item with the lowest id among those carrying the number, `stored` is the catalogue the registry names (`-` without an entry) and `derived` the item's catalogue. Such a number is not protected against the other catalogue claiming it.

### 1.4 how the report reads

- Every row is derived from facts, never from another row's stored status, so a stale order line does not carry over into its order or its demand.
- The report reads and compares through the lifecycle reconciler's own code, so a listed field is what the reconciler writes for that row once it recomputes the row's table.
- On Postgres it reads one consistent, read-only snapshot and writes nothing, so it is safe against the live backend.
- SQL echo, which the debug setting turns on, is off for the run, so stdout carries only the report and `--json` writes a clean file.

### 1.5 exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | No row differs. |
| `1` | Some row differs. |
| `2` | The arguments are invalid, for example an unknown table in `--only`. |
| `3` | The run failed, for example because the database cannot be read. Nothing is printed on stdout and a one-line message goes to stderr. |

## 2 repair

`lifecycle-repair` writes what `lifecycle-drift` lists. It is a dry run unless `--apply` is given.

### 2.1 what it writes

- It writes the derived fields through the same code the application uses for every status change. Each changed field gets a changelog line in the system user's name, such as `Status: ordered → allocated (lifecycle repair).`, and a lot gets its timeline entry.
- A stamp missing on a row that already holds its status (a delivered order without its delivery date, a completed lot without its completion time, a completed production order without its actual end, an ordered order without its ordered date) is dated at the row's last change, because the row reached the status then at the latest. A production order's actual end is never set before its actual start. A stamp of a status the repair itself sets gets the time of the run. The application dates such a stamp the same way when a request touches the row first.
- It publishes no events, so no notification, mail, webhook or automatic print follows, because it only brings stored fields back in line with facts that are already recorded and is no news to anyone. Open pages do not refresh by themselves and show the repaired rows after a reload.

### 2.2 options and output

- `--apply` writes the repair; without it nothing is written.
- `--json` prints one JSON document instead of the table.
- `--only lots,orders` starts from some of the tables, as in [1.1](#11-options). The rows that depend on a repaired row (an order on its lines, a lot on its positions, a demand on its lines or lots) are recomputed with it, as after any change.
- `--batch 200` sets how many rows of a table make one page, and each page is one transaction.
- Each output row shows the `action`, the `table`, `id` and `public_id`, the `field`, the `stored` and the `repaired` value, and the `rule` behind it. The action is `derived` for a field set to its derivation, or `manual` for a fact anomaly the repair leaves alone.
- After `--apply` the output also lists every row that still differs, which are the manual ones.

### 2.3 concurrency and retries

- Every page is read, locked, read again under its locks, written and committed in a transaction of its own.
- Only the rows that differ and the rows that depend on them are locked, in the same order every request locks them.
- A page that loses a race with a request (a lock or statement timeout, a deadlock, a row changed in between) is rolled back and tried again, at most three times. If it still fails, the run stops with exit code `3`.
- The pages committed before a failure stay written, and running the command again carries on, because a repaired row no longer differs. A second run over a repaired database writes nothing.

### 2.4 exit codes

| Code | Meaning |
| ---- | ------- |
| `0` | Nothing is left to do: a dry run found nothing, or nothing differs after `--apply`. |
| `1` | A dry run found rows, or rows still differ after `--apply`. Fact anomalies stay listed until they are settled ([3](#3-settling-fact-anomalies)). |
| `2` | The arguments are invalid, for example `--batch 0`. |
| `3` | The run failed, for example because the database cannot be read or the system user does not exist. Nothing is printed on stdout and a one-line message goes to stderr. |

## 3 settling fact anomalies

The repair writes derived fields only, so facts that contradict each other stay as they are and stay listed. Each one points at a code path that wrote a fact without its counterpart, which is a bug to report.

- **An order line whose booked totals differ from its delivery rows** (`field` `quantity_delivered`, `quantity_rejected` or `quantity_rejected_lost`). A booking lacks its row, or a row lacks its booking. Decide from the line's changelog and delivery history which side is right, and correct the other through the database console ([OPERATIONS.md section 5.7](../OPERATIONS.md#57-database-console-pgadmin)), or accept the row when the totals are the ones the demands should count.
- **A lot position with more completed pieces than its quantity.** The stored count stays at the quantity, so nothing reads the excess; accept the row.
- **A part number whose registry entry is missing or names the other catalogue.** The number is not protected against the other catalogue claiming it until the entry is right; report the row.

Keep a list of the accepted rows next to the saved drift reports, so a later report can be read against it.
