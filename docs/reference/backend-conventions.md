# backend conventions

The rules for backend application code: enums, use cases and permissions, idempotent writes, DTOs and schemas, quantities, delivery tolerances, logging, stored files, and composed mail with the export journal. The concept is in [CONTRIBUTING.md section 3](../CONTRIBUTING.md#3-backend-conventions). Persistence, soft delete and events are in [persistence.md](persistence.md), and lifecycle statuses in [lifecycle.md](lifecycle.md).

- [1 general rules](#1-general-rules)
- [2 use cases, auth and permissions](#2-use-cases-auth-and-permissions)
- [3 idempotent writes](#3-idempotent-writes)
- [4 DTOs and schemas](#4-dtos-and-schemas)
- [5 quantities](#5-quantities)
- [6 delivery tolerance](#6-delivery-tolerance)
- [7 logging](#7-logging)
- [8 stored files and browser headers](#8-stored-files-and-browser-headers)
- [9 composed mail and the export journal](#9-composed-mail-and-the-export-journal)

## 1 general rules

- The async rules (offloading blocking work, no `asyncio.gather` on one session, async tests) are in [development-async.md](development-async.md).
- The datetime rule (UTC, timezone-aware, always) is in [development-datetime.md](development-datetime.md).
- A new string enum subclasses `StrValueEnum` (`domain/value_objects/value_enum.py`), or `(str, Enum)` when it needs no `values()` listing, and never `StrEnum`.
- The reason is that `str()` and f-strings render a `(str, Enum)` member as `Class.MEMBER` but a `StrEnum` member as its bare value, so mixing the forms would make the same interpolation read differently from one enum to the next.
- An entity or domain dataclass field with a closed vocabulary is typed with its enum and holds a member, never a plain string. Nothing converts on assignment: the persistence mapper parses the stored string at the boundary ([persistence.md section 1.4](persistence.md#14-repositories-and-mappers)), a use case parses a command's string with the enum before it reaches the domain, and tests pass members.
- A domain rule compares an enum-typed field with enum members (`item.status == OrderItemStatus.DELIVERED`, `lot.status in TERMINAL_LOT_STATUSES`), never with `.value` strings, so strict mypy catches a misspelt or foreign status.
- A message, log line or changelog text interpolates such a field as `.value` (`f"Lot is {lot.status.value}"`), since the member itself renders as `Class.MEMBER`. `diff_changes` and `shown_value` in `changelog_service.py` already show an enum member as its value.

## 2 use cases, auth and permissions

- A use case is one class per action with the method `execute(actor: User, cmd_or_filters)`.
- A use case is a fresh instance per request and never keeps mutable state on the instance.
- The use case calls the domain permission rules (`src/modules/platform/domain/services/crud_permission_rules.py` and siblings) before any other logic or repository call.
- Permissions are flat strings, and there are no denials.
- A user holds the permissions granted to them directly (`User.permissions`) plus those of every group they belong to (`User.group_permissions`). `User.has_permission` and `User.effective_permissions` read both.
- Only the user repository loads the groups, so a user resolved as the relation of another row carries none and must not be permission checked.
- `write:settings` is the de facto admin gate.
- Other users' details belong to user administration. The full user view (`UserResponse`: e-mail, permissions, groups, `totp_enabled`, `last_logged_in`) needs `read:settings` or `write:settings`, except for one's own account (`UserRules.assert_can_read_details`). Every signed-in user reads the reduced directory, `GET /api/v1/web/users/directory` (`UserSummaryResponse`: id, username, full name, active state, account kind and the avatar flag), whose search and sort never touch the e-mail column. A user embedded in another resource (`PublicUserResponse`) carries no e-mail address.
- The Swagger UI pages (`/docs`, `/docs/web`, `/docs/pat`, `/docs/key`) and their OpenAPI schemas (`/openapi.json`, `/api/v1/<surface>/openapi.json`) need a signed-in web session outside debug mode; the pat ones also accept a PAT in `X-Api-Key` (`src/modules/platform/adapters/inbound/api/docs.py`). FastAPI's own docs routes are off and there is no ReDoc page.
- `src/modules/platform/adapters/inbound/api/auth_deps.py` resolves the three auth schemes (session, PAT, API key) and enforces maintenance mode on every authenticated route.
- Maintenance mode is a global 503 with the code `MaintenanceModeError`. The system user, holders of `write:settings` and allowlisted IPs are exempt.
- PAT scopes must be a subset of the issuing user's own permissions and may never include settings-adjacent scopes.
- On every use a PAT is capped again at what its owner holds then, so it loses a permission its owner lost, directly or by leaving a group.
- A new PAT, API key or terminal key needs an expiry within the security setting `token_max_lifetime_days` while that is above 0 (`domain/services/token_lifetime.py`); 0 lifts the cap. A new install sets it to 365 days.
- The self-service route creates a PAT only after the caller's current password is confirmed (`CreatePatWithPassword`), and a changed password revokes every PAT of the account, since a token outlives the session that made it.
- Every password check outside the login form that proves the caller's own password (passkey registration, changing the own password) goes through `PasswordConfirmation`, so it counts toward the login throttle ([operations-recovery.md section 4](operations-recovery.md#4-login-lockout)).
- A use case that signs someone in or out, or changes who may do what (accounts, permissions, groups, tokens and keys, passwords, 2FA, passkeys), records a security event through `SecurityAudit` (`application/services/security_audit.py`) before it commits, so the event commits with the change. Other modules take it through Platform's application services, as the terminal keys do.
- A refused login writes nothing else, so the login use cases commit its event themselves before raising. An attempt the throttle refuses is not recorded, so a flood of them cannot grow the log ([operations-monitoring.md section 1.5](operations-monitoring.md#15-the-security-log)).
- The client address and user agent come from the request through `RequestContextMiddleware`, so a use case passes them only when it knows better.

## 3 idempotent writes

- A web route whose repetition would book something twice takes an `Idempotency-Key` header. These are a delivery, deliver-all, a delivery correction, a completion, a scrap, a fulfilment from stock, a demand import, an allocation and a new order line.
- So do the `pat` creates of bought and source items, which the SolidWorks add-in sends a key with per user action, so a retry after a lost answer creates no second item and draws no second part number.
- A web route takes the key through `get_idempotency` and a `pat` route through `get_pat_idempotency` (`adapters/inbound/api/idempotency.py`), and runs its write through `Idempotency.run`, naming the resources the write produced and how a replay reads the answer back from them (`idempotent_replays.py`, `application/services/replay_reads.py`).
- A key is the user's, whichever surface sent it.
- The key is claimed on the request's session before the use case runs.
- The use case's commits are held back while it runs (`hold_commits` in `persistence/unit_of_work.py`, which turns them into flushes), so the work, the key and its record of what the work wrote commit in one transaction, and a failed request leaves none of them.
- A retry with the same key and the same request is answered from the first request's resources.
- The same key with another request answers 422, and one whose first request has not finished answers 409 (`application/services/idempotency.py`).
- Keys expire after 24 hours.
- A request without the header runs as before.
- A part number collision while the commits are held cannot be retried in the request, so it answers an error and the client sends the request again with its key.
- How these client resends relate to the server-side retry after a lost race is in [lifecycle.md section 6](lifecycle.md#6-concurrency-and-retries).

## 4 DTOs and schemas

- DTOs (`application/dto/`) are the application contract, and schemas (`adapters/inbound/api/schemas/`) are the wire contract. Keep them separate even when they look alike.
- Their identity bases are different classes in different layers: `ResultBase` for DTOs and `EntityResponse` for schemas. Both carry `id: int` and `public_id: UUID` with `from_attributes=True`.
- Do not import a DTO into a schema module or a schema into a DTO module.
- Every response schema subclasses `ResponseModel` (`EntityResponse` extends it), and a DTO that a route returns as its response model subclasses `ResultModel` (`ResultBase` extends it).
- Both set `json_schema_serialization_defaults_required`, so a response lists every field as required, defaulted ones included. Request schemas keep `BaseModel` and their defaulted fields optional.
- `tests/integration/test_api_response_schemas.py` fails on a response schema that leaves a field optional.
- A field with a closed vocabulary is typed with its domain enum, or a `Literal` where none exists, so the generated frontend type is a union rather than a string.
- Why request, command and response are written as three classes is in [recipes.md section 2.1](recipes.md#21-why-request-command-and-response-stay-separate).
- A row with an `edit_version` returns it in its response. A web route that writes the fields a user entered for such a row, or deletes the row, requires the version the client read as `expected_edit_version`: in the body of a PUT or PATCH, as a query parameter of a DELETE or a body-less action. A request without it answers 422 and a row that moved since answers 409.
- The same route on the `pat` surface keeps `expected_edit_version` optional, so an older client keeps working, and checks it when given. The command DTO carries it as `int | None`.
- Archive and restore, a merge, status intents, planning moves and writes of child rows that carry no version of their own (lot steps and positions, made item processes, files, pictures, device images and checks) take no version. They still move the version of the row when they change it, so a form that is open meanwhile is refused.
- How master data rows move their version is in [persistence.md section 1.10](persistence.md#110-edit-versions-of-master-data), and how lifecycle rows and projects do in [lifecycle.md section 5](lifecycle.md#5-edit-versions).

## 5 quantities

- A quantity in a request is one of the types of `adapters/inbound/api/schemas/quantity_fields.py`: a finite float (`allow_inf_nan=False`) that the NUMERIC(18, 6) columns can store and that the lifecycle tells from nothing.
- A quantity of 0.000001 or less, which rounds or compares to zero, or one that reaches 10^12 answers 422 (`quantities.storage_refusal`, which the spreadsheet imports apply per row).
- The `items_per_unit` factor of a demand or order line is a `PositiveQuantity` too, since it is stored the same way.
- Quantities are compared within `QUANTITY_EPSILON` (0.000001) through the helpers in `domain/services/quantities.py` (`quantity_eq`, `quantity_gt`, `quantity_ge`, `is_zero_quantity`), never with an epsilon of their own.
- Whether a quantity must be a whole number is a domain rule, checked in the use case or domain rule that books it through `assert_whole_pieces` in `domain/services/quantities.py`.
- Lots, production orders, completions, scrap and splits always count pieces.
- A demand, order line, allocation or delivery counts whole pieces when its unit counts whole things (`COUNTED_UNITS`: pieces, units, sets, pairs, rolls). A unit that measures, such as metres or kilograms, takes fractions.
- The refusal is `FractionalPiecesError` (422).
- An edit that leaves the quantity and unit as they are is not checked again.
- The frontend's `quantityFractionDigits` in `shared/utils/units.ts` mirrors the unit list for its inputs.
- The storage side of quantities is in [persistence.md section 1.3](persistence.md#13-column-types).

## 6 delivery tolerance

- A delivery on a supplier line may differ from the ordered quantity by the line's delivery tolerance (`domain/services/delivery_tolerance.py`).
- The order settings hold a global over- and under-delivery tolerance in percent, 0 by default. A bought or source item may hold its own pair, which replaces it, and `application/services/delivery_tolerances.py` reads the one that applies.
- A tolerance lies between 0 and 100 percent and is stored with three decimals. The web requests round it to those decimals (`TolerancePercent` in `delivery_tolerance_schema.py`).
- A MADE line has no tolerance, since it carries its lot's pieces.
- A delivery within the over tolerance is booked beyond the quantity, rounded down to whole pieces in a counted unit, and its surplus is free capacity for further allocations (`OrderItem.allocatable_quantity`).
- A delivery beyond the over tolerance is refused.
- The booking that settles a line within the under tolerance closes it short, as an explicit close short does, unless it sends pieces back for redelivery.
- An item's tolerance fields live on the web requests only (`DeliveryToleranceFields`), so a pat update that leaves them out keeps the item's values (`keep_unsent_tolerances`).

## 7 logging

- Use the single global logger: `from src.modules.platform.infrastructure.logging.logger import log`.
- Request id and user are stamped onto every record through contextvars, so never put them into the message yourself.
- The logger itself always runs at DEBUG. `cfg.log_level` only limits what reaches stdout, and `cfg.log_format` picks text or JSON.

## 8 stored files and browser headers

- A stored file's content type comes from its extension through `content_type_for` in `src/modules/platform/domain/services/content_types.py`, never from the type the client sent. An extension the mapping does not know is stored as `application/octet-stream`.
- The upload paths already follow this rule: the file attachment base (`application/services/file_attachments/base.py`) for every attachment family and PDM document, and `replace_stored_asset` for branding images, the login video, the company logo and avatars. A new upload path stores the type the same way, and a new extension is added to that mapping.
- The authenticated download use cases also report the type of the stored extension, so the type a browser gets never depends on the metadata the storage backend holds.
- A route that serves stored bytes builds its headers with `download_headers.py`. It sends `nosniff` and offers the file as an attachment unless the caller asks for `inline` and the type is in `INLINE_SAFE_CONTENT_TYPES` (raster images and PDF).
- `IStoragePort.get_url` takes the file name the download should carry. The S3 and Azure adapters sign response overrides into the URL: the content type of the key's extension, and a Content-Disposition that is `inline` only for an inline-safe type and `attachment` otherwise, with the name in both the plain and the RFC 5987 form.
- `SecurityHeadersMiddleware` gives every API response `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`. A PDF gets only `frame-ancestors 'none'`, because `default-src 'none'` can stop the browser's PDF viewer, and the Swagger UI pages under `/docs` get none, because they load their script from a CDN. A policy a route sets itself is kept.

## 9 composed mail and the export journal

- A mail a user composes goes through the `CustomMail` service (`platform/application/services/custom_mail.py`), whether it is sent by `SendMail` (`POST /mail/send`) or by a module that sends composed mails of its own, such as the meeting notes. It checks `send:mail`, holds the attachments to the size limit, applies the per-user rate limit and sanitises the HTML before `IMailService.send_custom`. A module never calls the mail service for a composed mail directly, since an unchecked path is an open relay.
- An attachment is a `MailAttachment` (file name, content type, bytes). The attachments of one mail have a total size limit, the admin mail setting `attachment_limit_mb` (10 MB by default). `assert_attachments_fit` (`domain/services/mail_attachment_policy.py`) refuses a larger set with `MailAttachmentsTooLargeError` (413), naming the files that no longer fit once the ones before them are attached, so a caller lists the most important file first. A caller that knows the sizes from its rows checks them before it reads any file.
- The web host capabilities carry the limit as `mail_attachment_limit_mb`, so a compose dialog shows what fits before it sends.
- A mail server that refuses the mail raises `SmtpDeliveryError` (502), and a caller that records the send records it only after the mail was accepted.
- A report sent as a mail attachment is journaled with the action `ReportJournalAction.MAIL`, and the entry keeps its recipients, To first and then CC. Anonymising a contact blanks its address in these recipients.
- The revision of a meeting notes journal entry is the issue label the PDF carried: `2` for issue 2, `2-draft` for a draft after issue 2 and `draft` before the first send.
- Mail templates are not seeded. A system mail uses the stored template of the first language in the fallback chain that has one (`domain/services/mail_template_resolution.py`), and without any it renders the packaged `<kind>.<language>.html` file in `adapters/outbound/external/mail/templates/` of the first language in the same chain that ships one, with the file's `<title>` as the subject (the kind's default subject from `mail_template_specs.py` when the title is empty). The enGB file always ships. Recommended templates in every language are imported by the admin from the root `templates/mail/` folder.

