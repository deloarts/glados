# architecture decision records

An ADR records one decision that shapes the code: the situation that forced it, what was decided, and what follows from it. ADRs explain why the code looks the way it does; the rules themselves live in [CONTRIBUTING.md](../CONTRIBUTING.md), [DEVELOPMENT.md](../DEVELOPMENT.md) and the other docs, which the ADRs link to.

## index

| ADR | Title | Status |
| --- | ----- | ------ |
| [0001](0001-hexagonal-architecture-async-io.md) | Hexagonal backend with async I/O and a sync domain | accepted |
| [0002](0002-transactional-outbox-redis-streams.md) | Domain events through a transactional outbox and Redis Streams | accepted |
| [0003](0003-pdm-field-ownership.md) | PDM owns CAD data, enforced per field | accepted |
| [0004](0004-trunk-based-release-flow.md) | Trunk-based flow with release PRs that tag on merge | accepted |
| [0005](0005-secret-encryption-at-rest.md) | Encrypt readable secrets at rest with a dedicated key | accepted |
| [0006](0006-openvue-ui-library.md) | OpenVue as the UI component library | accepted |
| [0007](0007-pdf-reports-in-the-browser.md) | PDF reports are rendered in the browser and printed as uploaded PDFs | accepted |
| [0008](0008-derived-lifecycle-statuses.md) | Lifecycle statuses are derived from facts and intents by one reconciler | accepted |
| [0009](0009-controlled-documents-and-export-journal.md) | Controlled documents with revisions, an edit lock and an export journal | accepted |
| [0010](0010-terminal-device-authentication.md) | Displays sign in with a device key pair, not a shared secret | accepted |
| [0011](0011-quote-requests-and-projects-in-the-lifecycle.md) | Quote requests join the reconciler and a project's status becomes a guarded intent | accepted |
| [0012](0012-modular-monolith-bounded-contexts.md) | The backend is a modular monolith of seven bounded contexts | accepted |
| [0013](0013-mcp-surface-as-an-inbound-adapter.md) | Agents reach Glados through an in-process MCP adapter that only creates drafts | accepted |

## writing a new ADR

Write one when a change sets a rule others must follow, picks between real alternatives, or would surprise a reader of the code without its reason. Copy the template below into `NNNN-short-title.md` with the next free number, keep each section to one short paragraph, and add a row to the index. An accepted ADR is not rewritten; a later decision that replaces it gets its own ADR, and the old one's status becomes `superseded by NNNN`.

```markdown
# NNNN title as a short statement of the decision

- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD

## context

The forces at play: what problem exists, what constraints apply, which
alternatives were on the table.

## decision

What we do, stated plainly.

## consequences

What becomes easier, what becomes harder, what must now be maintained,
and where the resulting rules are documented.
```
