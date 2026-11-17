# 0013 agents reach Glados through an in-process MCP adapter that only creates drafts

- Status: accepted
- Date: 2026-11-05

## context

Planners and engineers want to ask their AI agent questions that cut across several Glados pages, such as why a lot is late or which demands of a project are still open, and to let it prepare routine work. MCP is the protocol agent clients speak. The usual way to offer it is a thin server over a product's public REST API, but the Glados `pat` API covers only the catalogue and is frozen per released minor, and the web API is shaped around browser pages and session cookies. An agent acts with its user's permissions, and the text it reads in Glados may carry instructions that steer it, so whatever it may write is what an attacker who plants such text may write. Reading is open to every active user, and SSO through Entra ID, which would give Glados an OAuth authorization server, is still to come.

## decision

The MCP server is one more inbound adapter inside the backend process. Each module declares its tools in `adapters/inbound/mcp/`, and every tool builds its use case through the same dependency factory as the matching web route, so it runs the same permission checks. The composition root mounts the surface at `/api/v1/mcp` with the stateless streamable HTTP transport. It takes a bearer PAT or API key that carries the new permission `use:mcp`, and OAuth waits for Entra ID. Agents only read and create drafts that a person reviews and commits in the web app; no tool commits, sends, schedules or deletes, and API keys get the read tools only. Agent tokens live at most 30 days and are revoked when idle, results leave without names and prices by default, and every call is logged.

## consequences

There is no second HTTP hop and no new REST contract, and a tool cannot drift from its web route's permission checks. The tool list is a contract of its own, kept apart from the OpenAPI snapshots. Prompt injection cannot finish a write, at the price that agents cannot order, schedule or approve anything for their user. Remote clients such as claude.ai connectors need OAuth and a Glados reachable from the internet, so they wait. The rules are in [mcp-security.md](../reference/mcp-security.md) and [mcp-tools.md](../reference/mcp-tools.md), and the concept is in [MCP_INTEGRATION.md](../MCP_INTEGRATION.md).
