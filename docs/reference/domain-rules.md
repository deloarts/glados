# domain rules

The rule-like detail behind the terms of the domain glossary: how demands, lots, orders, quote requests, projects, user groups, controlled documents, product devices, PLC tags, flow sequences, calculations, contacts and meetings behave at their edges. The terms themselves are explained in [CONTRIBUTING.md section 10](../CONTRIBUTING.md#10-domain-glossary). Lifecycle mechanics are in [lifecycle.md](lifecycle.md), and scheduling in [scheduling.md](scheduling.md).

- [1 items and part numbers](#1-items-and-part-numbers)
- [2 demands and allocations](#2-demands-and-allocations)
  - [2.1 cancel and manual fulfil](#21-cancel-and-manual-fulfil)
  - [2.2 substitutions](#22-substitutions)
  - [2.3 demand families in code](#23-demand-families-in-code)
- [3 lots and positions](#3-lots-and-positions)
- [4 supplier orders](#4-supplier-orders)
- [5 quote requests](#5-quote-requests)
- [6 source approval](#6-source-approval)
- [7 projects and machines](#7-projects-and-machines)
- [8 user groups](#8-user-groups)
- [9 controlled documents](#9-controlled-documents)
- [10 product devices](#10-product-devices)
  - [10.1 device names](#101-device-names)
  - [10.2 kinds, positions and signals](#102-kinds-positions-and-signals)
  - [10.3 driven and operator devices](#103-driven-and-operator-devices)
- [11 PLC tags](#11-plc-tags)
- [12 flow sequences](#12-flow-sequences)
- [13 estimated cycle time](#13-estimated-cycle-time)
- [14 calculations and devices](#14-calculations-and-devices)
- [15 terminals](#15-terminals)
- [16 contacts](#16-contacts)
- [17 meetings](#17-meetings)
  - [17.1 cards, revisions and mentions](#171-cards-revisions-and-mentions)
  - [17.2 todos, follow-ups and notifications](#172-todos-follow-ups-and-notifications)
  - [17.3 files and retention](#173-files-and-retention)
  - [17.4 printing, sending and snapshots](#174-printing-sending-and-snapshots)

## 1 items and part numbers

- A made item's identity is `(part_number, revision)`. It is never edited in place, and a new revision is a copy.
- An ASCII hyphen `-` is the placeholder for an empty part number.
- `part_number_registry` keeps part numbers unique across the app. A number stays registered while any row, archived included, carries it, and is freed only once none does, such as after a merge, a renumber or a claim.
- `data_source` moves from web to CAD only.

- Article groups, source item types, fabrication methods and inspection methods keep their name and description in every UI language at once (`LocalizedText`, the same as product device kinds and options). A name needs a text in the tenant's default language, and no two live rows of one kind may show the same name in the same language, ignoring case (`label_name_rules.py`, `LabelTranslationConflictError`, 409). Names in different languages never clash. Product families keep one plain name.
- The web surface returns these names as language maps, also where an item, lot step or QA task carries one, and the frontend shows them in the user's language, falling back to the tenant's default language and then to any language. Search matches a name in any language, and a sort by name uses the user's language.
- The pat surface returns each of these names as one string in the add-in language of the PDM settings ([pdm-settings.md section 8](pdm-settings.md#8-other-switches)), so the SolidWorks add-in writes that language into the datacards. MCP tools and texts the server composes from a name, such as an order line's "material | type", use the acting user's language.

## 2 demands and allocations

### 2.1 cancel and manual fulfil

- A demand's status is a stored column the lifecycle reconciler derives from its allocations and its two intents, canceled and fulfilled, which are the only statuses a user sets.
- A cancel releases the demand's allocations.
- A manual fulfil of a bought or source demand keeps on each order line only the pieces that arrived for it and releases the rest, so the line can be shrunk or allocated again.
- A source demand that feeds a lot is cancelled only while the lot has not started.
- The cancel request says whether the lot is cancelled with the source demand or only loses its demand (`cancel_lot`). A lot that only loses its demand waits on raw material until its source is switched.
- An order line may cover a demand of any project: neither manual nor automatic allocation compares the demand's project with the line's, on purpose, so purchasing can pool one order line across projects and cover a demand from a line ordered for another one.

### 2.2 substitutions

- A demand can be covered by a different item of its family when the allocation declares the substitution: a source item by another source item, and a bought item by the bought item the order line carries.
- An order line allocation records a substitution only when the line's item differs from the item the demand asks for (`recorded_substitution` in `allocation_coverage.py`, used by every writer of a new or repointed order line allocation).
- A line for the demand's own item is stored as a plain match even when the caller sent a substitute, and a reason sent without a real substitution is dropped.

### 2.3 demand families in code

- A family binds its noun, terminal statuses and errors in a `DemandTerms` (`domain/services/demand_terms.py`), its allocation guards in a subclass of `DemandAllocationRules` (`allocation_coverage.py`), and what its use cases need on top in a `DemandFamilySpec` (`application/use_cases/_demand_family/`).
- The use cases in `_demand_family/` are written once for every family: the manual status change, delete, fulfilment from stock, the manual allocation writers and auto-allocation.
- For bought and made demands, which also bind their demand rules class, the shared use cases also cover creation, edit and batch import.
- A family's use case is a subclass that binds its spec and supplies only what differs.
- The status route hands a cancel to the family's cancel use case through `execute_permitted`, since it has already applied the shared status rule.

## 3 lots and positions

- A position's kind is derived from its order lines and its live production orders.
- A position's completed count is the delivered pieces of its lines that are not canceled plus the pieces its production orders completed.
- A position holds at most one open line. Once that line is closed short, a second line or an internal assignment can take the rest the position still lacks, so the lot can reach its quantity.
- A lot is `COMPLETED` once every position is completed or the lot was force-completed, which closes it short.
- A lot is `SCRAPPED` once its quantity is zero.
- `ON_HOLD` is an overlay over the active statuses, and a held lot still completes.
- A production order's `machine_id` may be empty, and `waiting_on_raw_material` flags missing material.
- A lot hold pauses its production orders, and its resume continues only those.

## 4 supplier orders

- Only ordered and partially delivered lines take deliveries.
- A line can be closed short at what arrived.
- A booking is corrected by a compensating row.
- A correction that carries a rejection takes accepted pieces back as rejected ones, for damage found after receipt: the row holds the negative accepted quantity and the rejected pieces with their reason and outcome, and names no correction reason. It is the `correct_delivery` intent with its guards, lost pieces refit the line's allocations, and it publishes `DeliveryPiecesRejected` like a rejection at receipt.
- A delivery row records whether damage was noted on the carrier's delivery note (`damage_noted_on_delivery_note`), and its pictures are order files of the `picture` category that name it (`delivery_id`). A receiver uploads and deletes them with `receive:deliveries`; every other order file needs `write:orders`.
- The order's status follows its live lines, so canceled lines do not hold it back.
- In a `PARTIALLY_ORDERED` order, the ordered lines need `manage:orders`, while its pending and requested lines stay open to `write:orders`.
- An order's extra costs (`OrderExtraCost`, kinds in `ExtraCostKind`, such as shipping, packaging, surcharges and a discount) are positive net amounts in cents beside its lines, and a discount is subtracted.
- Extra costs have no status, are never received and are saved as a whole list.
- The order's totals (`lines_total`, `extra_costs_total`, `net_total`) are computed when it is read (`domain/services/extra_cost_rules.py`).

## 5 quote requests

- A quote request's lines name what an order line would, with the bought or source item demands they are for. A demand share is no allocation and covers nothing.
- Each supplier row records when the request went out and the supplier's offer: a unit price or no offer per line, and the offer's extra costs.
- The request's status is derived (`lifecycle/quote_request.py`) from its close and cancel intents and its line states. The reconciler stores it, the request being the last aggregate in the lock order.
- A line is awarded only while an order line its award created is not canceled.
- Cancelling that order line or its order, or removing the line, opens the request line again with the note that the award was voided, and it can be awarded anew.
- A line closed short or delivered keeps its award.
- A request closed only because every line was dropped, or awarded only because every line is decided, takes a dropped line back and derives sent or draft again.
- A request someone closed stays closed when an award on it is voided, and the void is noted in its changelog.
- Such a request then offers a reopen (`ReopenQuoteRequest`, the `reopen` intent), which clears the close and derives the status again from the lines, so the voided line can be awarded anew and the lines the close dropped can be taken back.
- The award (`use_cases/quote_request/award_quote_request.py`) reads the request, locks the lifecycle rows with the request last, and refuses with 409 when the request or a line changed meanwhile, or when a target order was submitted or canceled since it was read.
- The award cuts each demand share to what the demand still needs and creates the lines through the cores of `CreateOrderItem` and `AssignExternalPosition` on a new or existing draft or partly ordered order per winning supplier, all in one transaction.
- The order line points back at the request line (`order_item.quote_request_line_id`).
- A bought or source line can take another item of its kind, with an optional reason. For every supplier this replaces the line, which drops it and moves its demand shares to the new line. For one supplier it is an alternative in that supplier's quote.
- The award puts the winner's item on the order line, so the order path records the substitution against each demand.

## 6 source approval

- Source approval is gated by `manage:lots`, and approving creates the material assignment demand.
- Approve, reject and switch are lot intents (`approve_source`, `reject_source`, `switch_source`) refused on a finished lot.
- Approve, reject and switch send the lot's `expected_edit_version`, and every one of the three moves it.
- Approve, and a switch that creates a demand, refuse a project that is not active or a source item no longer usable for new work.
- A switch replaces the lot's raw material demand once the caller confirmed it. An open demand is canceled (`LotHasOpenDemandError` asks first). An allocated or ordered one keeps the pieces that reached it, is marked fulfilled and releases the rest of its line allocations, as a manual fulfil does, and the new source is demanded for what is still missing (`LotHasPlacedDemandError` asks first). One nothing reached yet is canceled and replaced whole. The released order lines stay with purchasing to cancel or close short. A fulfilled demand leaves nothing to switch and is refused.
- A lot needs our raw material only for what its first position makes in house (`lot_material_rules.py`). A supplier who does the first position brings the material, so such a lot has no demand and nothing to approve. A MIXED first position demands only the pieces made in house.
- Two statuses say why a lot has no demand: `awaiting_first_step`, while the first position is unassigned and every one of its steps is a fabrication step whose method is required external, and `supplier_sourced`, once the first position is EXTERNAL. Neither allows approve or reject; a switch stays allowed and gives the new source the status its first position calls for.
- The routing predicts the supplier only at lot creation and when the first position becomes unassigned again. An assignment always wins over the prediction, and a structure edit of the first position does not run it again.
- When the lifecycle run changes who does a lot's first position, its material follow-up moves the status and settles, resizes or creates the demand ([lifecycle.md section 2.7](lifecycle.md#27-run)). A settle works like a switch's: canceled when nothing reached the demand, else fulfilled with what arrived. A recorded approval or rejection moves to `supplier_sourced` as well and stays in the lot's fields and changelog.
- A lot whose first position comes back to us is treated like a new lot: pending while its source item needs approval, otherwise with a demand for what it still lacks, never for what a settled demand already brought. The follow-up acts only when the first position's kind changes, or a line of a MIXED one does, so a demand a user ended or resized stays as it is.
- A lot in either supplier status has no input demand. A settled demand, and an ended one the lot still links, is unlinked and stays with the lot as its history. A demand can still be created by hand, for material sent along to the supplier; that is not automated.
- The production setting `external_first_step_needs_no_material`, on by default, turns the rule on. Off, every lot demands its material as before. Turning it on changes no existing lot. Turning it off gives every live lot in a supplier status its material need back, the way a new lot starts, in the same transaction as the settings save. The approval setting's backfill leaves both statuses alone.

## 7 projects and machines

- A project's status has nothing to derive it from. A user with `manage:projects` moves it through the intents of `PROJECT_INTENTS` (`lifecycle/project.py`), sending its `expected_edit_version`.
- Holding a project with open work is allowed, since a held project only refuses new work.
- Completing or archiving a project needs every lot, production order, order line, demand and open quote request on it finished, as deleting it does.
- A machine with queued, running or paused production orders cannot be archived.

## 8 user groups

- Groups are managed under Admin settings, Groups with `write:settings`.
- Every member holds the group's permissions on top of their direct grants.
- Groups carry permissions only, and none are predefined.
- Membership is kept in Glados and never synced from the directory.
- Personal and shared accounts can be members, while service accounts and the system user cannot.
- A group never holds the terminal connect permission.
- Nobody changes their own memberships or the permissions of a group they belong to.
- Deleting a group is never blocked. Its members lose what only that group gave them, and every user whose effective permissions changed is notified (`UserPermissionsChanged`).
- The user dialog shows an inherited permission checked and disabled.

## 9 controlled documents

- A draft is changed in place while its editor holds the edit lock.
- A release never changes again.
- A wrong released revision is marked invalid with a reason, and a correction is a new revision.
- A kind binds its permissions, errors and noun in a `DocumentAccess` (`domain/services/controlled_document_rules.py`), and its lock, release, revision, delete and read use cases in a `ControlledDocumentKind` (`application/use_cases/_controlled_documents/`).
- A kind's repository subclasses `ControlledDocumentRepositoryBase`, which also serves a kind without a project column (`_has_project`) and with another title column (`_title_column`).
- Every download and print of a saved record's report is written to the export journal and shown as the record's distribution.

## 10 product devices

### 10.1 device names

- A device's name is built from a free location, a free name, the letter of its driving medium and a number that counts per location, name and letter, for example `B01-W4-L Hubzylinder Einförderung P1`.
- The name is stored in UTF-8 and in ASCII. The ASCII form transliterates umlauts and turns every other character but letters and digits into one underscore, so PLC tags can be built from it.
- Both forms are unique per product over archived devices too, so a number never comes back for a different device.
- The variants with the product number in front are composed on read.
- A calculation may reference a device of its product, and the name is frozen into the revision on release.

### 10.2 kinds, positions and signals

- A device has a kind whose positions (retracted, extended and the like) give its initial position and the end position a sensor confirms, and PLC data such as its behaviour on energy loss and restoration.
- A kind also lists the signals its devices typically have besides the positions, such as the fault and ready signals of a servo axis, each with a signal type and a PLC name.
- A device's parts are components with an optional EPLAN tag, signals and ISO 13849-1 reliability data.
- A signal names a position, or else one of its kind's signals, which sets its type. Its meaning is free text, needed only when it names neither.
- Driving media, kinds, component roles and energy behaviours are hand-maintained lists with labels per language (`LocalizedText`).

### 10.3 driven and operator devices

- The driver owns the valve and its outputs, and the driven device only its sensors.
- There are no chains of driven devices.
- A driver of another kind maps its positions to the driven device's.
- Sequences never move a driven device. They move its driver, and the displacement-step diagram draws the driven device following it.
- Operator devices (buttons, key switches, indicator lamps, E-stops) are devices of kinds without driving medium. Their names carry no letter, and a number only from the second device of a name on.

## 11 PLC tags

- A PLC environment is a device resource an admin creates or imports, such as Siemens TIA Portal from the root `templates/` folder. A fresh install has none, and the first one created becomes the default.
- It holds a prefix per signal type with safety variants, the longest tag, a character conversion table, the tag tables and the export columns.
- A product uses its chosen environment or the default.
- A signal's tag is the prefix, the device's UTF-8 name through the conversion, and a suffix.
- The suffix is the signal's own suffix, or else the state name (input) or command name (output) of its position, which the kind's positions carry, or else the PLC name of the kind signal it picks, or else its meaning.
- A signal may also bring a whole tag name.
- Renaming a position's or a kind signal's PLC name renames the tags built from it.
- Tags that are too long or used twice are flagged, not refused, and the device dialog warns while the name is typed.
- The product's tag list adds manual tags that belong to no device, renames a built tag by storing the name on its signal, and exports an Excel sheet in the environment's columns, by default TIA's tag table import.
- Addresses are typed per signal.

## 12 flow sequences

- A sequence is an ordered list of steps numbered by their order and referenced by stable keys.
- A step holds actions that start together, each a device moved to a position of its kind or a text, with the qualifier stored (S), continuous (N) or pulse (P) and an optional condition, plus an optional timeout.
- A step leaves through transitions to the next step, any step or the end.
- Several transitions with conditions are an alternative branch, and parallel (AND) branches are not modelled.
- Condition terms are a device in a position, a device value compared with a threshold, another step complete, the time in the step (t/Xn) and a named external signal.
- A value is common to all variants or given per variant, falling back to the common one.
- The start state is the devices' initial positions.
- A draft may keep a reference to a device, position or variant archived since. A release needs every reference live and freezes the names it shows into the revision.
- Names are proposed from the hand-maintained sequence name list, and the number comes from `sequence_number_format`.

## 13 estimated cycle time

- A device carries a nominal travel time per position of its kind, and a sequence action may override it per variant.
- A step may have an expected duration per variant, which covers waiting for something outside the devices.
- A step takes as long as the longest of its actions (after the delay of a time condition), the time conditions of the transition it leaves through, and its expected duration.
- Without an expected duration a step is unestimated when an action has no time or it waits for an external signal, and a total then reads "at least".
- A pass runs from step 1 until it returns there or ends.
- A transition back to a step already passed is not taken again, so other loops count once.
- The cycle time is shown along the branches the engineer picks (the first by default) and as the worst case over all branches, for the variant picked in the controls bar. The picks are not stored.
- A release freezes the travel times with the names.

## 14 calculations and devices

- A calculation of a product, or of a project with a product, may refer to one device of it.
- The device dialog lists those calculations, links and unlinks drafts, and starts a new calculation with the device picked.
- A released calculation keeps its device until a new revision.

## 15 terminals

- Terminal registration, modes and terminal keys are covered in [TERMINAL_INTEGRATION.md](../TERMINAL_INTEGRATION.md) sections 1 and 5 and in [terminal-auth.md](terminal-auth.md).

## 16 contacts

- A contact belongs to a customer, to a supplier, or to neither, never to both (`ContactRules.assert_valid_organisation`).
- Only a supplier's contact carries the flags receives request mails and receives order mails. The supplier's request and order mails go to its flagged contacts, and to the supplier's own `request_email` and `order_email` when none is flagged.
- Reading contacts needs `read:contacts` and changing them `write:contacts`. Whoever holds `send:mail` also reads a supplier's flagged recipients, since a supplier mail goes to them.
- A contact is archived, never deleted. An archived contact stays on every link and record that names it but is offered for no new one.
- Products and projects link contacts with a receives meeting notes flag (`product_contact`, `project_contact`). A project shows its product's links first and its own after them; a project link for a contact the product already links overrides the product's flag, which is how a project mutes it. Linking follows the record's own edit rights, and reading the links needs `read:contacts`.
- Anonymising needs `write:contacts` together with `manage:meetings`, since it reaches the meetings. It blanks the name, e-mail address, phone and mobile numbers and note, takes the mail flags away and archives the contact, in the same commit as the copies on meeting attendees, todo owners and snapshots. The row stays, so every link keeps resolving, and it can be neither edited nor restored afterwards.
- Contacts never reach an infoscreen feed.

## 17 meetings

- A meeting belongs to exactly one project or one product, and its number comes from `NumberFamily.MEETING` in the `meeting_number_format` of the made-item settings, `MTG-{yy}-{seq:04d}` by default.
- Start and end are aware instants, and the end may not lie before the start.
- Attendees are users, contacts or guests, at most 100, each present, excused or distribution only. A contact attendee keeps a copy of the contact's name and e-mail address, so the meeting reads without `read:contacts`. Anonymising a guest needs `manage:meetings`.
- A meeting carries up to 10 free-text tags in the order given, such as Milestone or Acceptance. Each is trimmed with its inner whitespace collapsed, empty ones are dropped, a repeat that differs only in case is dropped in favour of the first spelling, and a tag over 40 characters or an 11th tag is refused (`MeetingInvalidInputError`). The meeting list filters by one tag in any case, the suggestions (`GET /meeting-tags`) rank the tags of all meetings not deleted by how many meetings carry them, and a follow-up copies its predecessor's tags. The PDF does not print them.
- Every signed-in user reads every meeting. Changing a meeting, its cards, decisions, todos and files needs `write:meetings`.
- Marking a meeting invalid needs `manage:meetings` and a reason. An invalid meeting refuses every change (`MeetingReadOnlyError`) and its open todos leave the todo pages. Restoring it needs `manage:meetings`, takes an optional note and makes it editable again. Both are history events.
- Deleting a meeting needs `manage:meetings` and its edit version, and soft deletes it ([persistence.md section 2](persistence.md#2-soft-delete)).
- The history (`meeting_event`) records creating and editing the meeting, adding, changing and deleting cards, adding, ticking off and reopening todos, adding and deleting files, every print, download and send, marking invalid and restoring.

### 17.1 cards, revisions and mentions

- A card saves on its own and sends its `expected_edit_version`. A clashing save answers 409, and the page offers the newer text next to the user's draft to merge.
- Every save writes a card revision. A save by the author of the card's last revision within 10 minutes of that revision's start updates it instead of adding one (`REVISION_MERGE_WINDOW`). Restoring a version saves its content as a new revision.
- Card Markdown is a fixed subset: one heading level, paragraphs, bold, italic, bullet and numbered lists two levels deep, links, inline code, mentions and images that are meeting files. The backend normaliser (`domain/services/meeting_markdown.py`) turns anything else into plain text, and the frontend port of it is tested against the same fixtures (`backend/tests/fixtures/meeting_markdown_cases.json`).
- A mention is stored as `@[Name](user:<id>)` and shown with the user's current name. Saving a card records its mentions in `meeting_card_mention`, and the row stays when the mention is removed, so a user is notified of a card once.
- The scope is free text of at most 80 characters with an optional icon from a fixed set of twelve. Suggestions rank the scopes by how often the cards of the owner use them, on a product with its projects included, and a scope that differs from an existing one only in case, spacing or a small typo is offered the existing one. Rename Scope renames a scope on every card of the owner's valid meetings, on a product also on those of its projects.
- Presence is a fleeting live signal: an editing card sends a heartbeat every 20 seconds, and other viewers show it until it is 45 seconds old. It is never stored.

### 17.2 todos, follow-ups and notifications

- A todo has one or more owners, each a user or a contact. A writer of meetings ticks any todo off, and an owner ticks off their own. Ticking off marks it done for everyone.
- The todo sources (`GET /todo/sources`) carry the user's open todos of valid meetings that are not deleted, due within the todo horizon or undated. A todo owned only by contacts reaches no todo page and notifies nobody.
- Mentions and todo assignments wait five minutes per meeting and recipient (`meeting_notification_table`) and go out as one notification and one digest entry. Nobody is notified of their own actions, and the queue of an invalid or deleted meeting is dropped. The title and the sentence are written in the recipient's language, since the in-app panel and the digest show them as stored.
- A follow-up meeting has the same owner, copies the name, location, tags and attendees with their status, and sets `follow_up_of`. It takes place at the agreed next meeting's date, time and place, for as long as the meeting lasted; without a time it keeps the start time, and without a date it is one week later.
- The Open Points of a follow-up are the open todos of the meeting it follows and of that meeting's predecessors, at most 50 deep. Invalid and deleted meetings are skipped, their predecessors are not.

### 17.3 files and retention

- Meeting files use the shared file attachment base under their own storage prefix `meetings`: images up to 10 MB and PDFs up to 50 MB. A pasted image is a meeting file the card's Markdown links, and removing it from the text leaves the file.
- A nightly sweep removes the blobs under the prefix that are older than 24 hours and that no file row names, and logs how many it removed.
- The retention setting `meeting_retention_days` purges meetings that started longer ago, deleted or not, with every row and file. It is 0 by default, which keeps meetings forever.

### 17.4 printing, sending and snapshots

- Meeting notes print, download and send through the meeting's own routes. A request carries every included card's id and edit version, the options and the issue the PDF carries. The server answers 409 naming the card when one changed meanwhile, computes the PDF's SHA-256 itself and journals the export with a snapshot.
- Internal cards are left out unless the options include them. The todos and the list of documents are options too, on by default.
- A meeting's issue counts its sends. A send carries the next issue. A print or download carries the last issue while the notes are unchanged since that send, otherwise a draft after it, and a plain draft before the first send.
- The notes changed since a send when a card the send contained was removed or changed its text, scope, icon or internal flag, got a new todo or changed its decisions, or when a card was added that the send would have contained. Ticking a todo off is no change.
- Sending needs `write:meetings` and `send:mail` and a valid meeting. The PDF goes first, and the meeting's documents go along only while they fit under the mail attachment limit. A send is journaled only after the mail server accepted it, and a refusal journals nothing.
- Printing needs `print:documents`, and a print that the printer refused is not journaled.
- The send suggests the attendees that are contacts or guests with an address, pre-selected. With `read:contacts` it also suggests the owner's linked contacts that receive meeting notes, pre-selected, and the customer's other contacts and the customer's own address, not pre-selected.
- A snapshot keeps the meeting's facts, the included cards with their decisions and todos, the attendees, the documents listed and attached, the options, the issue, the language, the recipients of a send and the PDF's size and checksum. Users are kept by id, contacts and guests by id with a copy of name and address that anonymising blanks, while the checksum stays as proof that the PDF went out.
- Changes Since compares a snapshot with the notes today card by card, and leaves out the internal cards a snapshot left out.

