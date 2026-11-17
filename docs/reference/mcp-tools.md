# mcp tools

The rules for offering a tool, a prompt or a resource to AI agents through the MCP surface, and for keeping the tool list a stable contract. The concept is in [MCP_INTEGRATION.md](../MCP_INTEGRATION.md); authentication, budgets, redaction and the call log are in [mcp-security.md](mcp-security.md).

- [1 where tools live](#1-where-tools-live)
- [2 writing a tool](#2-writing-a-tool)
- [3 read tools and draft tools](#3-read-tools-and-draft-tools)
- [4 prompts and resources](#4-prompts-and-resources)
- [5 the tool contract](#5-the-tool-contract)
- [6 testing a tool](#6-testing-a-tool)

## 1 where tools live

- The building blocks are in `src/modules/platform/adapters/inbound/mcp/tools.py`, which every module may import. The server (`server.py`) and Platform's own catalogue are private to Platform and the composition root.
- Each module offers its tools as one `AgentCatalog` in its `adapters/inbound/mcp/catalog.py`, named `<MODULE>_AGENT_CATALOG`. Planning and fulfillment splits its catalogue into `read_tools*.py` and `draft_tools.py`.
- The read tier's catalogue (`src/read/adapters/inbound/mcp/catalog.py`) holds the tools over read-tier use cases and the prompts, which may name the tools of every module.
- `src/bootstrap/agents.py` lists every catalogue. A tool or prompt name used twice fails at startup.
- A module's `adapters/inbound/mcp` package is in its privacy contract in `backend/.importlinter`, so no other module imports its tools, and the read tier may not import a module's catalogue.

## 2 writing a tool

- A tool is an `AgentTool` with a name in snake case, a title, a description written for a model, an input model and an async handler `(ctx, args) -> ToolOutput`.
- The input model subclasses `ToolInput`, which refuses unknown arguments, and gives every field a `Field(description=...)`. A list tool takes a `limit` with a small default and `le=100`.
- The handler builds its use case with `await ctx.use_case(<factory>)`, where the factory is the one the matching web or `pat` route takes through `Depends`, and calls `execute` with exactly the arguments that route passes, the caller (`ctx.actor`) first. `DependencyResolver` (`resolve.py`) resolves the factory's `Depends` tree on the call's session and applies the app's dependency overrides.
- A factory whose tree reads the request, such as a header, cannot be resolved and fails the first test that calls the tool. Such a tool needs a factory that takes the value as an argument.
- A permission a route checks outside its use case goes into the tool's `requires`, so a tool never checks less than its route. A tool whose use case needs a permission no token may carry, such as `read:settings` for the PDM admin views or the print jobs, is not offered.
- A field that names a person or carries money under a key the redaction does not know yet is added to the keys in `domain/services/agent_policy.py`, so every tool is covered, never renamed in one tool to slip into the redaction. A tool renames a field only where its own name would mislead an agent, such as a supplier's sum `total`, which reads `total_price` because every list result calls its row count `total`.
- A tool looks records up by the numbers people use (project, lot, part number) through the use cases the routes already have, never through a new repository query.
- The handler returns the use case's result DTO, or a small dict around it, in `ToolOutput`. A large DTO is cut to the fields an agent needs, so a result stays well below the size limit.
- The handler raises the domain errors the use cases raise; the server turns them into an error result the agent reads.

## 3 read tools and draft tools

- A read tool (`ToolKind.READ`, the default) never writes and never commits.
- A draft tool (`ToolKind.DRAFT`) creates only records that wait for a person in the web app: a DRAFT purchase order, a DRAFT quote request, a DRAFT production lot or a meeting notes draft. It never commits, sends, orders, approves, schedules or deletes anything beyond creating its draft.
- A record without a draft state of its own, such as meeting notes, gets a draft record apart from it that only its creator sees, and the web app applies the reviewed form through the record's own use case helpers. The draft keeps people as the text the agent read and the review matches them, so the agent needs no lookup of people.
- A draft tool's input subclasses `DraftToolInput`, which carries the optional `idempotency_key` the server answers repeats with.
- A draft tool returns the references of every record it created in `ToolOutput.created_refs`, built with `ref(kind, public_id)`, and says in its description and result that a person reviews and commits the draft in Glados.
- When a draft takes several use case calls with their own commits, a failure part way leaves a smaller draft behind, which is acceptable because a person reviews it.

## 4 prompts and resources

- An `AgentPrompt` is a ready-made instruction a client offers as a command. Its `render` returns the user message, names the tools to use and says that drafts wait for a person. Required arguments missing from a `prompts/get` answer a JSON-RPC error.
- Prompts are listed to every token, also when it cannot call every tool a prompt names.
- An `AgentResource` maps a URI template with one parameter, such as `glados://lot/{number}`, to a tool and one of its arguments. Reading it runs the tool through the same budgets, redaction and log, and a tool error answers a JSON-RPC error.

## 5 the tool contract

- The tool list, with each tool's input schema and annotations, is a contract agent clients and prompts rely on. `scripts/export_mcp_tools.py` writes it to `backend/mcp-contract/tools.json`, and `tests/unit/test_mcp_tool_contract.py` fails while the file is stale. It lives outside `openapi/`, which holds the OpenAPI snapshots only and is cleared of every other file on export.
- Renaming a tool or an argument, or making an optional argument required, breaks the agents that use it; add a new argument as optional instead.
- The server marks read tools `readOnlyHint` and every tool `destructiveHint: false`, so clients that ask before a write ask before a draft.

## 6 testing a tool

- Integration tests call a tool over HTTP with the helpers in `backend/tests/integration/_mcp_helpers.py`: `save_agent_settings`, `mint_agent_token`, `call_tool`, `list_tool_names`, `rpc` and `logged_calls`.
- A tool's test arranges real rows, calls the tool and checks the answer. A permission-gated tool also checks that a token without the permission does not list it, and a draft tool checks the draft's state, the created references in the log and that a repeated idempotency key creates nothing.
