# persistence

The rules for models, repositories, sessions and commits, for soft delete, and for domain events and the outbox. The concept is in [CONTRIBUTING.md sections 3.4 to 3.6](../CONTRIBUTING.md#34-persistence). Writing migrations is in [development-migrations.md](development-migrations.md).

- [1 models and repositories](#1-models-and-repositories)
  - [1.1 models and ids](#11-models-and-ids)
  - [1.2 sessions and engines](#12-sessions-and-engines)
  - [1.3 column types](#13-column-types)
  - [1.4 repositories and mappers](#14-repositories-and-mappers)
  - [1.5 relationships and load options](#15-relationships-and-load-options)
  - [1.6 shared statements and paging](#16-shared-statements-and-paging)
  - [1.7 commits and the unit of work](#17-commits-and-the-unit-of-work)
  - [1.8 constraint violations](#18-constraint-violations)
  - [1.9 listeners, locks and startup](#19-listeners-locks-and-startup)
  - [1.10 edit versions of master data](#110-edit-versions-of-master-data)
- [2 soft delete](#2-soft-delete)
- [3 events and the outbox](#3-events-and-the-outbox)

## 1 models and repositories

### 1.1 models and ids

- Models use SQLAlchemy 2.0 declarative style (`Mapped[...]`, `mapped_column()`), one model file per aggregate in `adapters/outbound/persistence/models/`.
- Every model inherits the base model, which carries an int `id` and a `public_id` UUID.
- The web API and the app's own URLs use the int `id`, which is short and readable.
- A link that leaves the app and has to keep working, such as a QR code on a label or report, a link in a mail or one a user shares, uses `public_id` through `/resolve/{public_id}`, because an int `id` points at another record after a restore or a move to another instance.
- Constraint names are explicit (`name="fk_supplier_creator_id"`). There is no global naming convention.
- Boolean defaults are server defaults: `server_default=sa.text("false")`.

### 1.2 sessions and engines

- The app uses `AsyncSession` on psycopg 3 with `expire_on_commit=False` (`persistence/session.py`).
- The only sync engine left is `log_engine` and `LogSessionLocal`, used by the database log writer thread.
- On the session, `add`, `add_all` and `expunge` are sync, while `flush`, `commit`, `execute`, `scalar(s)`, `get` and friends are awaited.
- Count rows with `count_rows(self._db, stmt)`.
- To get a parent's id before adding children, `await flush()` instead of committing early.
- SQLite returns naive datetimes, so repositories re-attach UTC when reading datetime columns through `utc_aware()` in `persistence/mapping_common.py`.

### 1.3 column types

- A date that records an action (`created`, `changed`, `released_at`, `finished_at` and the like) is a `DateTime(timezone=True)` column, even where the frontend shows only the day.
- Calendar dates a user picks (planned, required, desired or expected dates, a completion or provision date, holidays) stay `Date`.
- The whole app reads calendar days in one timezone, the tenant's default timezone from the general settings. There is no per-user timezone.
- A calendar-date filter over an action column compares through `day_start_utc` and `day_after_utc` from `persistence/date_range.py` and always passes the tenant zone.
- A repository resolves the tenant zone once per query method with `date_filter_zone` (`persistence/tenant_zone.py`), which reads the general settings only when a day bound is set, and hands it down to its filter builders.
- A created or changed window that an API schema expands itself (`expand_change_window`) gets the zone from the `get_tenant_zone` dependency.
- The application sets change timestamps itself. Only the allocation tables stamp `created_at` and `changed_at` on the Python side (`models/_allocation_audit.py`), since many write paths touch them.
- A model with a `changed` timestamp records its changer by mixing in `ChangedByColumns` (`models/changed_by_columns.py`).
- Nobody sets `changed_by_id` by hand. The before_flush listener in `persistence/changer_tracking.py` sets it to the session's acting user whenever a flush moves `changed`.
- The auth dependencies bind the acting user to the request session once they have verified the credential, so a write outside a request, by a worker or a scheduled job, clears the changer.
- The repository loads `changed_by` with `load_user(...)` and maps it with `changed_by_kwargs`.
- Made items and the controlled documents do not use the mixin and set their changer explicitly in the use case.
- Every piece quantity, and every factor that converts one such as `items_per_unit`, is a `QuantityType` column (`models/quantity_type.py`): NUMERIC(18, 6) in the database, a float in Python, rounded to six decimals on its way in, so SQLite and Postgres store the same number. A new quantity column uses it, never `Float`.
- Every stored percentage, such as a delivery tolerance, is a `PercentType` column (`models/percent_type.py`): NUMERIC(7, 3) in the database, a float in Python, rounded to three decimals on its way in.
- `Float` is left for continuous measurements that are never summed into a quantity or compared for equality: durations such as minutes per piece or a printer timeout, label dimensions in millimetres, marker coordinates, a device's initial position value and its MTTFd in years.
- Every entity changelog is a `changes` column of `ChangelogType` (`models/changelog_type.py`): a JSON list of change records in the database and a list of `ChangeEntry` lines in Python (`domain/value_objects/change_entry.py`).
- A changelog entry is the line "timestamp, actor, text" and carries those parts, and for an edit of one field also the field with its old and new value. Append with `append_changelog`, never by building the line yourself.

### 1.4 repositories and mappers

- Repositories implement their `I*Repository` port and return entities, never ORM rows.
- The common pattern is an `_orm_to_entity()` function or method for reads and an `_entity_to_dict()` that builds the write payload and leaves out `public_id`.
- That pattern is not a fixed interface. Many repositories have no `_entity_to_dict()`, some name their mappers per row type (`_run_to_entity`, `_run_to_dict`), and catalogue lookups share the mappers in `persistence/catalogue_mappers.py` (product families in `persistence/product_family_mappers.py`). Follow whatever the repository you touch already does.
- A mapper another repository reuses is public and named after its entity (`customer_orm_to_entity`), never imported under its private name.
- An entity field with a closed vocabulary, such as a status, kind, line type or priority, is typed with its domain enum while its column stays a string. The mapper converts at the boundary: `LotStatus(orm.status)` into the entity and `lot.status.value` into the write payload.
- The mapper is the only place a stored string becomes a member. Entities and other domain dataclasses do no conversion of their own, so a value read off a row that mypy cannot see, such as a joined or raw SQL row, is parsed explicitly in the mapper, and a stored value no member names fails there. Where a stored value from another writer must still be read, the mapper maps it to a member on purpose and says so, as the interruption mapper reads an unknown reason as a manual pause.
- Tests build entities with enum members, never with plain strings.

### 1.5 relationships and load options

- Every relationship is `lazy="raise_on_sql"`.
- Each repository has an `@lru_cache` load-options function, such as `made_item_load_options()`, that every query feeding a mapper applies with `.options(...)`.
- A write re-reads its row through `_reload` with those options and `populate_existing=True`.
- A forgotten option is a runtime error, so cover new read paths with a test.
- A user relationship is eager-loaded with `load_user(...)` from the user repository, which adds the memberships `user_orm_to_entity` reads.

### 1.6 shared statements and paging

- `persistence/statements.py` holds the statements most repositories share.
- `fetch_page` counts a list query and reads one clamped page of it.
- `order_term` turns a filter's `order_dir` into a sort term with the repository's own default direction.
- `by_id` selects one row by primary key, optionally `for_update` or `refresh` for `populate_existing`.
- `load_by_ids` loads the rows a relationship collection is assigned from.
- List endpoints answer with `PageResponse.from_result(result, params)`, and list filters inherit `skip` and `limit` from `PageParams`.

### 1.7 commits and the unit of work

- Repositories never commit, and their writes flush.
- The use case that writes owns an `IUnitOfWork` (`get_unit_of_work` in Platform's `adapters/inbound/api/deps/database.py`) and commits it once its writes are done and its events are published (section 3).
- Before a slow external call (storage upload, printer, webhook, mail, backup job) a use case commits its read transaction so no pooled connection idles, then records the outcome and commits again.
- Anything external that a failed commit would orphan, such as a new storage object, is cleaned up, and anything the commit replaces is removed only after it.
- A file family whose blobs can still be orphaned, by a crash between the upload and the commit or by a failed delete after it, keeps them under a storage prefix of its own and runs a sweep over `IStoragePort.list_objects(prefix)`, which lists every key under the prefix with its last write. The sweep removes only blobs older than a day that no row names, so an upload about to commit is never taken for an orphan. Meeting files are swept this way nightly.
- `test_no_repository_commits` in `tests/unit/test_architecture.py` fails on any commit inside a repository.
- Cover a new write with a test that reads it back through a separate request or session, so a forgotten commit fails there.

### 1.8 constraint violations

- The app engine turns every `IntegrityError`, whether raised at a flush or at the commit, into `SqlConstraintViolationError` (`persistence/constraint_violation.py`).
- That error is both an `IntegrityError` and the port-level `ConstraintViolationError` from `ports/outbound/unit_of_work_port.py`. Application code catches the port type, as the numbering retry in `application/services/retry_on_conflict.py` does.
- A violation that reaches the API answers 409 with the code `ConflictError`. The constraint is logged, never returned.
- A use case checks that every row its input names exists before it writes and answers 422 otherwise, so a violation means a concurrent change.
- An engine built outside `session.py` needs `register_constraint_violation_translation` to behave the same.

### 1.9 listeners, locks and startup

- Session event listeners, such as change tracking and the outbox tripwire, register on `SessionLocal.sync_session_class`.
- Advisory locks are async context managers: `async with advisory_lock(engine, KEY) as locked:`.
- Lifecycle statuses are stored columns that only the lifecycle reconciler writes ([lifecycle.md](lifecycle.md)). Other statuses (source approval, catalogue item, project) are set by the use case of the action. No status is computed on read.
- `persistence/init_db.py` runs at startup and is idempotent. It migrates, seeds the system user from `INIT__*`, seeds the admin settings singletons (`id=1`, including the PDM variable maps and the made-item revision policy) with their complete defaults on first run, and ensures one unconfigured slot per print classifier, so a new singleton or classifier needs no data migration. Mail templates and spreadsheet column names are not seeded: sending falls back to the packaged mail file of the recipient's language, and recommended content is imported by the admin from the root `templates/` folder.
- A Postgres advisory lock stops parallel workers from seeding twice. On SQLite that lock is a no-op.

### 1.10 edit versions of master data

- Made items, bought items, source items, suppliers, customers, products and product devices mix in `EditVersionColumn` (`models/edit_version_column.py`), an `edit_version` column that starts at 0.
- Nobody moves it by hand. The before_flush listener in `persistence/edit_version_tracking.py` moves it by one whenever a flush changes one of the row's columns or many-to-many collections, whoever writes: a web form, the `pat` API, a PDM or EDP ingest, an archive or a restore.
- The change timestamp, the changelog and the changer do not count, so a save that changes nothing leaves the version alone. Neither do the columns a model lists in `__edit_version_ignored__`: the PDM and EDP sync stamps of items and the two images of a device, which its edit dialog uploads on its own while it is open.
- A datetime counts as changed only when it names another instant, since SQLite hands back naive datetimes.
- A Core `UPDATE` passes the listener by, so one that changes a field an edit form sends sets `edit_version = edit_version + 1` itself, as the successor relinks of a catalogue merge do.
- A repository that saves rows of a child table as part of the row's edit, such as the components of a device, calls `bump_edit_version_by_hand` when only those rows changed.
- An update use case locks the row with `lock_for_update` (`statements.lock_row`, FOR NO KEY UPDATE) before it reads it, then checks the client's version with `assert_edit_version`, so the version it checks is the one it overwrites.
- Lifecycle rows and projects keep their own rule, where only user edits and irreversible actions move the version ([lifecycle.md section 5](lifecycle.md#5-edit-versions)). Which routes require the version is in [backend-conventions.md section 4](backend-conventions.md#4-dtos-and-schemas).

## 2 soft delete

- User-managed master data is archived, not deleted: supplier, contact, article_group, source_item_type, source_item, bought_item, made_item, customer, printer, production_machine, machine_pool, product, product_family, product_device, product_device_kind (with its positions and parameters), product_device_option, product_variant, fabrication_method and inspection_method.
- The model has `archived: Mapped[bool]` with a server default of false.
- Repositories filter `archived = false` explicitly in list queries unless the caller passes `include_archived`.
- `GET /{id}` resolves archived rows too.
- There is no `DELETE` route, only `POST /{id}/archive` and `POST /{id}/restore`, both idempotent.
- Product variants have neither route. Their list is saved as a whole, and a variant left out of a save is archived.
- Uniqueness covers live rows only, through a partial unique index that carries both dialect clauses (see the example in [development-migrations.md section 3](development-migrations.md#3-writing-a-migration)). Restoring a row can therefore answer 409 when a live row now holds the same key.
- Product device names are the one exception: `uq_product_device_name_utf8` and `uq_product_device_name_ascii_key` cover archived devices too, because a device's name goes into its PLC tags and released calculation revisions and its number never comes back for a different device ([domain-rules.md section 10.1](domain-rules.md#101-device-names)).
- Project keeps a `deleted` column, and its `status` value `archived` is unrelated.
- Meetings soft delete with a `deleted` column and `deleted_at`, like projects, since a meeting is a record rather than master data. A deleted meeting leaves every list, search and todo page, and its rows and files stay until it is purged.
- A meeting is purged, by the retention setting `meeting_retention_days`, by deleting every child row explicitly, children first, in one commit, so the purge does not rely on the database enforcing its cascades: the snapshots with their contact rows, the todos with their owners, the decisions, the mentions and revisions, the files, the cards, the history, the waiting notifications and the attendees. A follow-up keeps its row and loses its link. The blobs are removed after the commit, best effort.
- The snapshots of printed, downloaded and sent meeting notes live in `meeting_snapshot_table`, their content as JSON in the shapes the repository writes. The export journal entry is named by id without a foreign key, since it belongs to Quality and documents and outlives the meeting. `meeting_snapshot_contact_table` lists the contacts each snapshot keeps a copy of, so anonymising a contact finds them without reading every snapshot.
- Contacts are archived like other master data and can also be anonymised, which keeps the row and archives it for good ([domain-rules.md section 16](domain-rules.md#16-contacts)).

## 3 events and the outbox

- Publish a domain event when another component must react (notification, webhook, auto print, PDM sync, live refresh) and that reaction must not block or fail the request.
- Call the code directly when it belongs to the same unit of work and must succeed or fail with it.
- Events go through the transactional outbox ([ADR 0002](../adr/0002-transactional-outbox-redis-streams.md)). The bus stages a row in `event_outbox_table`, the relay (`src/modules/platform/infrastructure/events/outbox_relay.py`) drains committed rows onto the `glados:events` Redis stream, and consumer groups in each worker process handle them.
- If Redis is down, rows accumulate and nothing is lost.
- Delivery is at least once. Every consumer keys its idempotency on the producer's event id (the stream's `event_id` field), never on the stream message id, because a relay retry and `admin republish-outbox` put the same event on the stream as a new message.
- A consumer whose reaction cannot be taken back, such as a print, claims the work before it acts: it inserts its record under a unique key on the event id with `ON CONFLICT DO NOTHING` (`on_conflict_do_nothing` of the Postgres and SQLite dialect inserts), commits the claim, and acts only when its own insert wrote the row. Checking for a record and writing it after acting lets two concurrent deliveries both act. The `auto_print` group does this with its print job row ([operations-recovery.md section 6.1](operations-recovery.md#61-republishing-outbox-events)).
- A field added to an existing domain event gets a default for at least one release, so a payload written before the deploy and still waiting in the outbox or on the stream decodes. The default can go once a release has shipped with every publisher passing the field.
- Consumers must not rely on the order of events. The relay publishes a batch in id order, but ids are assigned at insert and rows become visible at commit, so a transaction that took a lower id can commit after a higher one was relayed, and a republished event lands behind newer ones.
- If Redis loses its data, relayed rows stay in the outbox for 30 days, and `admin republish-outbox` puts them back ([operations-recovery.md section 6.1](operations-recovery.md#61-republishing-outbox-events)).
- The SSE live path runs beside it. Committed changes are published on the Redis Pub/Sub channel `glados:live`, picked up by `LiveEventSubscriber` and pushed by the SSE hub (`adapters/inbound/api/live/hub.py`, at most five connections per user and process) to the frontend's `useLiveRefresh` and `useLiveRows`. An open stream checks its session again every minute without counting that as activity: it ends once the session is revoked, expired or its user deactivated, and takes over the user's current permissions otherwise.
- There is one commit model and one bus factory.
- A use case that writes owns an `IUnitOfWork`, takes `get_transactional_event_bus` from Platform's `deps/database.py`, and publishes its events before `uow.commit()`. The bus stages the event row in the open transaction, so the write and its event commit or roll back together.
- The bus never commits on its own.
- Publishing after `uow.commit()` loses the event, because `get_db()` never commits and the pending row is discarded at request end.
- `test_no_use_case_publishes_after_committing_its_unit_of_work` in `tests/unit/test_architecture.py` catches that statically, and the `EVENT_OUTBOX_ABANDONED` log tripwire in `event_outbox.py` catches it at runtime.
