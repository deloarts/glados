# mcp integration

- [mcp integration](#mcp-integration)
  - [1 purpose and scope](#1-purpose-and-scope)
  - [2 how it fits together](#2-how-it-fits-together)
  - [3 setting it up](#3-setting-it-up)
    - [3.1 the admin](#31-the-admin)
    - [3.2 the user](#32-the-user)
    - [3.3 the agent client](#33-the-agent-client)
  - [4 what an agent can do](#4-what-an-agent-can-do)
  - [5 drafts](#5-drafts)
  - [6 security](#6-security)
  - [7 limits and open points](#7-limits-and-open-points)

## 1 purpose and scope

An AI agent such as Claude Code or Claude Desktop can work with Glados on its user's behalf through MCP, the Model Context Protocol agent clients speak. It answers questions that cut across several Glados pages, such as why a lot is late, which demands of a project are still open or what is planned on a machine next week, and it prepares routine work as drafts. A person reviews every draft and commits it in the web app; the agent never orders, sends, schedules or deletes anything.

The agent acts as the person whose token it uses, with that person's permissions or fewer. An API key lets an unattended agent, such as a nightly report, read with the permissions of its own service account.

## 2 how it fits together

The MCP surface is one more inbound adapter of the backend, next to the web, `pat` and key APIs, at `/api/v1/mcp`. Each module offers its tools from its own `adapters/inbound/mcp/` package, and every tool runs the same use case, with the same permission checks, as the matching button in the web app. [ADR 0013](adr/0013-mcp-surface-as-an-inbound-adapter.md) explains why it is built this way rather than as a separate server over the REST API.

Every request authenticates on its own with a bearer token, so a revoked token or a permission the user lost stops working on the agent's next call. Every tool call lands in the agent call log, which tells an agent's actions apart from its user's own.

## 3 setting it up

### 3.1 the admin

1. Clarify with data protection, and the works council where one exists, that Glados data may go to the AI providers the company uses, then record that approval in the agent settings: name the approved providers and link the company's AI policy. Agent access cannot be switched on without it, and changing the providers, the policy link or whether names and prices leave asks every user to confirm again.
2. Grant `use:mcp` to the users or groups who may connect an agent. A user can only put the permission on a token they hold themselves.
3. Switch agent access on in the agent settings and check the defaults: agent tokens live at most 30 days and are revoked after 14 days without a call, names of people and prices stay out of results, and each token may make 120 calls a minute and 20 drafts an hour.
4. For an unattended agent, create an API key with `use:mcp` and keep API key authentication switched on in the security settings. It reaches the read tools only.

### 3.2 the user

Confirm the agent consent in My Account first: it shows which AI providers the company approved and what leaves Glados, and the user agrees that their agent may process Glados data on their behalf. Without it every agent token of the user is refused; withdrawing it revokes them. Then create a personal access token with the "Read" preset (`use:mcp`) or the "Read and draft" preset, which adds `write:orders`, `write:lots` and `write:meetings`, and an expiry of at most 30 days. Glados shows the token once.

### 3.3 the agent client

Claude Code connects with:

```sh
claude mcp add --transport http glados https://<glados host>/api/v1/mcp --header "Authorization: Bearer <token>"
```

Other clients take the same URL and header in their MCP configuration. The client then lists the Glados tools, the prompts as commands and the records an agent can attach as `glados://` resources.

## 4 what an agent can do

The tools, grouped by what they answer. The exact list with each tool's arguments is what the client shows; the rules for adding one are in [mcp-tools.md](reference/mcp-tools.md).

| Question | Tools |
| -------- | ----- |
| Find anything | `search` |
| What needs my attention | `my_briefing`, `my_notifications`, `list_planning_exceptions` |
| Where a project or product stands | `project_status`, `product_status`, `demand_coverage`, `controlled_documents` |
| Why a lot is late, unplanned or on hold | `explain_lot` (also the resource `glados://lot/{number}`), `explain_lifecycle` |
| What the shop floor does | `schedule`, `shop_floor_now`, `production_kpis` |
| Purchasing | `orders`, `compare_offers`, `suppliers` |
| Catalogue and parts | `item`, `source_items`, `edp_lookup`, `renumber_impact` |
| A product's devices and what is still missing on them | `product_devices` |
| Documents | `controlled_documents`, `sequence`, `calculation`, `report_journal` |
| Which meetings a project or product had | `meetings` |
| Drafts for a person to commit | `draft_purchase_order`, `draft_quote_request`, `draft_production_lot`, `draft_meeting_notes` |

The prompts are ready-made tasks: `morning-briefing`, `project-report`, `why-late`, `procurement-review` and `weekly-kpis`.

## 5 drafts

A draft tool creates a purchase order, a quote request or a production lot in its draft state, exactly as the web app would, with the user as its creator, and the agent call log names the token that created it. The order, quote request and lot lists mark such a draft with an Agent tag naming the token, and the user reviews it and orders, sends or plans it, or deletes it. Creating a lot does what creating it in the web app does: it also creates the lot's raw material demand, and a routing with inspection steps queues its inspection orders, so such a lot reads partially planned. Draft tools are open to personal access tokens only, need the write permission of what they create, and answer a repeated call with the same idempotency key with the draft the first call created.

Meeting notes have no draft state of their own, since a card saves and shows to everyone the moment it is written. A user who hands the agent a record of a meeting, such as handwritten notes or a photo of a notebook page, therefore gets a meeting notes draft: a record apart from the meetings that only its creator sees, which adds to an existing meeting of a project or product or proposes a new one. The agent names people exactly as the notes do and never looks them up. The user opens the draft from the notice on the meeting or the meeting list, matches each name once to a user, a contact, a guest or nobody, with Glados suggesting the one that fits, adjusts or leaves out cards and applies it. Applying adds the cards with their decisions and todos after the meeting's own cards, adds the attendees the meeting lacks and only then notifies the todo owners; a card's text never mentions anybody on its way in. A draft nobody applies or discards is deleted after 30 days, since it keeps names of people.

## 6 security

The agent is only as trustworthy as the text it reads, and much of that text was written by people, suppliers and CAD files. Glados therefore assumes that an agent may be talked into anything its tools allow and limits what they allow: reading, and drafts that wait for a person. No tool makes Glados send anything anywhere. Nothing reaches an agent before the company approved the AI providers and the user agreed for themselves. Results leave without the names of people and without prices unless the admin lets them in, because they go to the agent's model provider. Agent tokens are short-lived, revoked when idle and logged call by call.

Users should keep a Glados token out of unattended agents that can also browse the web or send mail, since such an agent could pass on what it read, and use the "Read" preset unless they want drafts. The full rules and the threat model are in [mcp-security.md](reference/mcp-security.md).

## 7 limits and open points

- Agents connect with tokens only; OAuth and remote connectors such as claude.ai wait for Entra ID and for a decision on reaching Glados from outside.
- Auto-Plan has no dry run, so an agent can read the schedule but not propose a plan.
- Agents cannot print, create demands or catalogue items, or read files and drawings.
