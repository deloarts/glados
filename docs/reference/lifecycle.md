# lifecycle

The reconciler protocol for derived lifecycle statuses: what a use case that changes facts or intents must do, in which order, which locks it takes, how a user action is added, how edit versions and lost races work, and how the derivation is tested. The concept is in [CONTRIBUTING.md section 3.7](../CONTRIBUTING.md#37-lifecycle-facts-intents-and-the-reconciler), the reasoning in [ADR 0008](../adr/0008-derived-lifecycle-statuses.md), and every decision table is drawn in [LIFECYCLES.md](../LIFECYCLES.md).

- [1 facts, intents and derived fields](#1-facts-intents-and-derived-fields)
- [2 the use case protocol](#2-the-use-case-protocol)
  - [2.1 take the reconciler](#21-take-the-reconciler)
  - [2.2 touch](#22-touch)
  - [2.3 lock](#23-lock)
  - [2.4 locks after the lifecycle locks](#24-locks-after-the-lifecycle-locks)
  - [2.5 project and line checks under the lock](#25-project-and-line-checks-under-the-lock)
  - [2.6 check the intent and write](#26-check-the-intent-and-write)
  - [2.7 run](#27-run)
- [3 adding a user action](#3-adding-a-user-action)
- [4 lot on hold](#4-lot-on-hold)
- [5 edit versions](#5-edit-versions)
- [6 concurrency and retries](#6-concurrency-and-retries)
- [7 drift and tests](#7-drift-and-tests)
- [8 bookings of a production order](#8-bookings-of-a-production-order)

## 1 facts, intents and derived fields

- The status of a lot, lot position, production order, order, order line, demand and quote request is derived, never set.
- A fact is what was recorded, such as quantities, delivery and completion rows, interruptions and allocations.
- An intent is a timestamp that only a user action sets and only its inverse clears, such as `held_at`, `canceled_at`, `force_completed_at`, `requested_at`, `ordered_date` or `fulfilled_manually_at`.
- The status is the first matching row of the aggregate's decision table in `src/modules/fulfillment/domain/services/lifecycle/`, one module per aggregate, built from `rules.py`.
- The same tables derive a position's kind and completed count, a production order's completed count (its accepted completion pieces, reversals netted out) and the stamps of a status (`completed_at`, `actual_end`, `delivery_date`).
- `lifecycle/stored.py` compares the stored fields with the derivation and writes the derived values.
- Nothing else assigns a field of `LifecycleField`, neither through an entity nor through a Core `update(...).values(...)`. `test_status_written_only_by_lifecycle_domain` in `tests/unit/test_architecture.py` enforces this with a short allowlist of hand writes that record a fact, each with its reason.
- Never add a status transition. A status changes only because facts or intents changed.

## 2 the use case protocol

A use case that changes facts or intents follows these steps in order.

### 2.1 take the reconciler

- The use case takes the request's `LifecycleReconciler` from `get_lifecycle_reconciler` in Planning and fulfillment's `adapters/inbound/api/deps/lifecycle.py`, which shares the request's `LockPlan`.

### 2.2 touch

- The use case touches every aggregate whose facts or intents it writes, with `touch_lots`, `touch_positions`, `touch_production_orders`, `touch_orders`, `touch_order_items`, `touch_quote_requests` or `touch_demands(family, ids)`.
- It passes `created=True` for rows it inserts.
- A delivery touches its line, a completion its production order, and an allocation writer its demand.
- A use case that deletes lot positions touches the quote requests whose lines name them before it deletes.
- The reconciler adds the dependent rows itself: a line's order, position, demands and the quote request its award came from, a position's lot, a lot's positions and made demands, and a touched demand's neighbours.
- A demand's neighbours are the other demands allocated on its lines and lots, whose pieces depend on the allocations ahead of them in the fill order.
- An allocation writer also names the line or lot it writes on (`touch_allocations_on`, done by `lock_for_allocation`), so the demands on it are targets even where the written allocation is the only link.
- What the lock took as a target is derived by the run even when the use case deleted the allocation that led to it.
- Because the fill hands arrived pieces out by family and demand age, an allocation that would take pieces already arrived for another demand is refused with `AllocationTakesArrivedPiecesError`, and auto-allocate passes over such a line.

### 2.3 lock

- The use case calls `await reconciler.lock_touched(also=...)` before it reads what it checks.
- This locks the touched rows, their dependents and anything in `also` in one acquisition.
- The one lock order is lots, production orders, orders, order lines, bought, made and source demands, and quote requests last, ascending id within each.
- With them it locks the neighbours of every demand among them and in `also`, so a demand the use case touches only after writing its facts, as a line cancel touches the demands it deallocates, widens to nothing unlocked.
- It then reads the dependents again under those locks and locks late what a concurrent change added meanwhile, such as a demand allocated to the line, so everything the use case reads next is locked.
- When the touched rows reach a lot's first position (the position, a line of it or a production order of it) and the lot has a live raw material demand, the lock step locks that demand, its lines and its neighbours in the same acquisition, for the run's material follow-up (section 2.7). Where that would break the lock order, it leaves them out, and the follow-up locks them late only when it settles or resizes the demand.
- Locking a row that sorts before one already held raises `LockOrderError`.
- The row locks are FOR NO KEY UPDATE, so they serialize the lifecycle writers without blocking the foreign key check of a row that references a locked one.
- A FOR UPDATE lock on a lot would make a writer that updates the lot's source demand twice wait for the lot's writer, which may be waiting for that demand.

### 2.4 locks after the lifecycle locks

- A number (order, lot, production order, part or document number) is drawn only after the lifecycle locks, because its counter row is a lock outside the lock order.
- The project's time budget lock (`recompute_project_time_budgets`) is taken after the lifecycle locks too, and after the reconciler's run, for the same reason.
- A structure edit writes step rows, which a recompute of another request writes too. It therefore takes the time budget lock before its first step write instead, once every row it writes is locked (`lock_structure_edit`), and commits its steps, the budgets and the duration snapshot of queued and paused orders together.
- Every writer that changes a lot's quantity or a position's kind recomputes the budgets of the lot's project there. This includes the cascades of a lot cancel, a force-complete, a scrap and a disposition of rejected or lost pieces.
- A recompute copies a changed budget onto the duration snapshot of the queued and paused orders of that step's position, in whichever lot of the project it is.
- Every writer that recomputes therefore locks the project's queued and paused orders (`budget_order_locks`) with its other lifecycle rows, before the time budget lock.
- An order the plan does not hold by then, one queued meanwhile, refuses the request with `ConcurrentModificationError` instead of being written unlocked.

### 2.5 project and line checks under the lock

- A use case that puts new work on a project share-locks the project row (`ProjectRepository.lock_for_share`) before the lifecycle locks and refuses a project that is not active (`assert_project_active`).
- New work is a demand, a lot, a line moved onto the project, an external assignment, a reopened line, an approved source and a quote request line.
- The share lock serializes the use case with a status move, which locks the project for update before it counts the live work.
- Work already on a project that is not active (ordering, delivering, correcting, closing short) is not new work and stays allowed.
- A use case that finds a line by its id alone checks under the lock that the line is still on the order it locked, and answers `ConcurrentModificationError` when a move came first.
- Deliver-all, which books every deliverable line of the order, skips such a line as `moved` instead.

### 2.6 check the intent and write

- The use case checks the action against the aggregate's intent table in `lifecycle/intents.py`.
- It writes the facts and intents through its repositories and never assigns a status.
- The decisions about what to write are pure functions in a domain service, and the use case only reads, writes and calls them. A delivery, for example, takes the pieces it accepts, the line's new totals, whether it refits the line's allocations or closes it short, and whether a MADE line's pieces fit its lot from `domain/services/delivery_booking_rules.py`.

### 2.7 run

- The use case calls `await reconciler.run(actor, now, reason=...)` after its last write and before it publishes its own events and commits.
- The reconciler writes only the fields that differ, one changelog line each ending in the reason, and publishes the status events.
- The run also notes on a quote request every award it finds voided that the lock step saw live, even when the request's status stays. A use case that cancels or removes an awarded order line therefore locks it through `lock_touched` first.
- The run of a request's reconciler ends with the material follow-up (`lot_material_followup.py`). When the run changed the kind of a lot's first position, or touched a line of a MIXED one, it moves the lot's source approval status and settles, resizes or creates its raw material demand ([domain-rules.md section 6](domain-rules.md#6-source-approval)). A second pass then derives the demands it wrote. The pass changes no position, so no further follow-up runs, and the repair job's reconciler has no follow-up at all.
- A run that changes no first position reads nothing more. Only on such a change does the follow-up read the production setting, which turns it off when the rule is off.
- A use case must not save an entity it read before `run` afterwards, because that would write the old status back.
- `test_lifecycle_use_cases_reconcile_before_commit` checks the order of the calls in every application module that uses a reconciled aggregate's repository. Each commit needs a run since the previous commit, and each run a touch before it, made in the use case or in a helper the reconciler is handed to.
- Commit once where the work allows it, because the server retries a lost race only for a request that committed nothing before it (section 6).

## 3 adding a user action

- Add a `LifecycleAction`.
- Add a rule to the aggregate's intent table with the statuses it starts from, its guard, its permission and its effect text.
- When the action needs one, add an intent column through a migration.
- A guard of several conditions is a tuple of named `Check`s, so a refusal names the condition that failed (`IntentRefusal.failed` and `message`) rather than the whole requirement.
- A rule with checks may still name a condition its use case checks on facts the context does not carry. The table lists that condition but never refuses on it.
- A rule names a permission only when it is required on top of the action's base permission. The base permission is checked by the use case and shown by the client, so a user without it is still offered the action and sees it disabled with the reason.
- A rule with such an actor guard (`permitted`) also names the permission code it refuses without in `needs`, such as `manage:lots`, next to the `permission` text the rule listings show. The table refuses to build a rule that has the guard but lacks either.
- The rule then appears in the response's `actions` (`application/services/lifecycle_actions.py`) and in the state machine catalogue the handbook shows, both read from the same table.
- `actions` lists what `IntentTable.allowed_actions` allows the reader now. Orders, order lines and lots also carry `blocked_actions` from `IntentTable.blocked_actions`: each action the state allows but the actor guard refuses, mapped to the permission in `needs`, so the client shows it disabled and names that permission. An action the state rules out is in neither. The use case still checks the intent, so a blocked action sent anyway answers 403.
- Extend the property suite's model when you add an intent, and see section 7 for the transition table.

## 4 lot on hold

- A lot on hold refuses the work on its production orders through the check "lot not held".
- The refused work is a start or resume, and a completion, a scrap or the reversal of a completion, which answer 409 `LotOnHoldError` (`assert_production_order_action`).

## 5 edit versions

- Orders, order lines, lots, production orders and projects carry an `edit_version` (`domain/services/edit_version.py`).
- It moves on a user edit of an editable field and on an irreversible action: cancel, force-complete, close short, reopen, scrap, delivery correction, the merge of production orders, a lot source's approval, rejection or switch, and a project's status move.
- It also moves on a split of a production order and a move of a line, which rewrite the row a client may hold without asking for its version.
- It never moves on a derived status or a planned date.
- Responses carry it, and the web edit routes and those actions require `expected_edit_version`, the version of the row as the client shows it. So do the removal of an order line and the deletion of a project, as query parameters.
- A request without it answers 422, and a row that moved since answers 409. The general rule for routes is in [backend-conventions.md section 4](backend-conventions.md#4-dtos-and-schemas).
- A merge sends the version of every order it merges (`expected_edit_versions`, by order id).
- A scrap on a production order also sends its lot's `expected_lot_edit_version`.
- A use case that acts on such a row checks it under the row's lock with `assert_edit_version` and moves it with `bump_edit_version`. There the version stays optional, because a cascade ends rows the user never saw.
- Integration tests read the version they send with `tests/integration/_edit_versions.py`.

## 6 concurrency and retries

- Lifecycle rows carry a version column, so a write that lost a race answers 409 with `ConcurrentModificationError`.
- A deadlock or serialization failure (40P01, 40001) answers 503 `DatabaseConflictError`.
- A row lock wait that hit `lock_timeout` (55P03) answers 503 `DatabaseLockTimeoutError`.
- A write request that committed nothing before either error is run once more on the server after a short random delay, with fresh dependencies (`LostRaceRetryMiddleware`, `commit_tracking.py`), so the client sees the 503 only when that run loses too.
- A route whose repetition would book a fact twice takes an `Idempotency-Key` ([backend-conventions.md section 3](backend-conventions.md#3-idempotent-writes)), so a client that lost the answer can send the request again.
- The server-side run after a lost race and that client resend are the only retries, and neither repeats a write that committed.

## 7 drift and tests

- Every integration test ends with a drift check (`tests/integration/conftest.py`): the stored lifecycle fields must equal their derivation, so a use case that forgot a touch fails there.
- A test that leaves inconsistent rows on purpose requests `allow_lifecycle_drift`.
- On a real database, `admin lifecycle-drift` lists drift and `admin lifecycle-repair` writes the derivation ([operations-lifecycle-repair.md sections 1 and 2](operations-lifecycle-repair.md#1-drift-report)).
- The lifecycle rules have a property suite: Hypothesis state machines over the in-memory fake world (`tests/unit/lifecycle/`) run random sequences of intents and check after each one that every stored status equals its derivation and every quantity invariant holds. Extend the model when you add an intent. Profiles and the CI settings are in [development-testing.md](development-testing.md).
- The same model also writes the status transitions the handbook's transition pages show (`domain/services/lifecycle/observed_transitions.py`).
- `tests/unit/lifecycle/test_state_transitions.py` explores the model with a few fixed seeds and fails when the code makes a transition the table does not list.
- After a lifecycle change, regenerate the table with `GLADOS_WRITE_TRANSITIONS=1 poetry run pytest tests/unit/lifecycle/test_state_transitions.py -q` and review its diff, where a transition the code no longer makes drops out. The run takes about twenty minutes, because it explores many more seeds so rare transitions stay listed.
- A new request of the model's world also needs its lifecycle actions in `TRIGGER_ACTIONS` (`state_machine_catalog.py`) and a trigger label in both `stateMachines` locale files.

## 8 bookings of a production order

The bookings of a production order are its start and resume, its pauses, its completions and their reversals, and its manufacturing assessment. They record enough to tell afterwards who worked on the order, when, and why it stood still.

- `actual_start` keeps the first start. `first_started_operator_id` is set together with it, once, and never overwritten, while `started_operator_id` follows every start and resume.
- A pause opens an interruption (`production_order_interruption.py`), and every closing writes `ended_by` (`InterruptionEndedBy`). Each caller of `IProductionOrderInterruptionRepository.close_open`, directly or through `close_open_interruptions`, passes its value:

  | Caller | `ended_by` | Operator |
  | ------ | ---------- | -------- |
  | the resume path of `StartProductionOrder` | `resume` | `resumed_operator_id`, the resolved operator |
  | `ResumeLot` | `resume` | none |
  | `CancelProductionOrder` | `cancel` | none |
  | `lot_cascades.cancel_production_order`, for a lot cancel, a forced lot completion and a disposition that cancels an order | `cancel` | none |
  | `lot_cascades.close_live_work_short`, for a forced lot completion that ends an order at what it processed | `cut` | none |
  | `piece_disposition._cut_order`, for a scrap, an inspection reject or a loss at goods receipt that cuts an order to what it processed | `cut` | none |

- A `cancel` and a `cut` stamp `resumed_at` like a resume, but no work follows them, so a reader of the booked work time treats only `resume` as work going on. A new caller of `close_open` passes the value that says why the pause ended.
- A normal completion never closes an interruption, since it is allowed only on a running order, and a merge takes only queued orders, which have none.
- After a lot resume the work continues under the operator of the order's last start or resume, since the lot resume names no operator.
- Rows written before these fields existed hold none of them, and there is no backfill.
- `pause_cause` (`PauseCause`) is the cause an operator picks for a manual pause, next to its free-text reason. It is optional, and a lot hold never sets it.
- A reversal of the completion that completed an order keeps `actual_start`, clears `actual_end` and opens no interruption, so the order runs again without a new start.
- An order has one active manufacturing assessment, which a partial unique index over the rows without `superseded_at` holds. A second one is refused with `ManufacturingAssessmentAlreadyExistsError` unless a reversal of one of the order's completions was booked after the active one was recorded (`manufacturing_assessment_rules.py`). The new one then replaces it: the earlier row gets `superseded_at` and stays as history.
- Every read of an order's assessment filters on `superseded_at IS NULL`, and the response never carries a superseded one.
- `actual_minutes_per_piece` is stored as a float with at most two decimal places, which the request and the command both validate.
- The booked work of an order is derived from its bookings alone (`domain/policies/booked_work.py`). Work begins at `actual_start` under `first_started_operator_id`. A pause ends the running span. A pause ended by a resume opens the next span under `resumed_operator_id`, or under the previous operator after a lot resume. A pause ended by a cancel or a cut opens nothing. A closed row without `ended_by` counts as a resume.
- A reversal of the completion that completed the order, the one whose accepted pieces net of earlier reversals reached the order's quantity, makes the span from that completion to the reversal not work, and work goes on at the reversal with an unknown operator. Reversing an earlier, partial completion changes no span. The last span ends at `actual_end`, at `canceled_at`, or now while the order runs.
- `clip_to_windows` cuts the spans to working windows and reports the minutes it cut off, so a forgotten pause at the end of a shift does not count a night as work.
- The booking quality view of the KPI tab (`quality/domain/services/booking_quality.py`, `GET /production-kpi/booking-quality`) lists, for the period, the orders whose booked work lies at least 30 minutes outside the working time of their machine, or of the admin default calendar without one, the final completions without an active assessment, and the manual pauses without a cause. Lot holds are never counted, and pauses booked before `booking_quality_since` of the planning settings are left out. That moment is set when the settings row is created and cannot be changed.
