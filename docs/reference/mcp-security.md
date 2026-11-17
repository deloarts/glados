# mcp security

The exact rules of how an AI agent gets into Glados through the MCP surface and what keeps it inside the person it acts for: authentication, the gate permission, agent tokens and their lifetime, the call budgets, what a result may carry, the agent call log and the threat model. The concept is in [MCP_INTEGRATION.md](../MCP_INTEGRATION.md); the rules for writing a tool are in [mcp-tools.md](mcp-tools.md).

- [1 authentication](#1-authentication)
- [2 the gate permission and the token presets](#2-the-gate-permission-and-the-token-presets)
- [2.1 approval and consent](#21-approval-and-consent)
- [3 agent token lifetime](#3-agent-token-lifetime)
- [4 the call budgets](#4-the-call-budgets)
- [5 what a result may carry](#5-what-a-result-may-carry)
- [6 the agent call log](#6-the-agent-call-log)
- [7 the agent settings](#7-the-agent-settings)
- [8 threat model](#8-threat-model)

## 1 authentication

- The surface is one route, `API_MCP` (`/api/v1/mcp`), served by `AgentAuthMiddleware` and `AgentMcpApp` in `src/modules/platform/adapters/inbound/mcp/server.py` and mounted by `src/bootstrap/main.py`.
- It speaks the MCP streamable HTTP transport in its stateless form with JSON responses, so no MCP session lives between requests and every request authenticates on its own.
- A request authenticates with `Authorization: Bearer <token>` and nothing else. The session cookie and the `X-Api-Key` header are ignored, so the surface has no cross-site request risk and needs no CSRF header.
- `AuthenticateAgent` (`application/use_cases/agent/authenticate_agent.py`) checks, in this order: the agent settings switch the surface on with the company's approval recorded, the `Origin` header is absent or allowlisted, the token is a valid PAT or API key, the token carries `use:mcp`, a PAT's owner holds a current agent consent (section 2.1), and maintenance mode lets the caller through.
- A PAT is validated by `ValidatePat`, so its permissions are capped again at what its owner holds now. An API key is validated by `ValidateApiKey`, needs `enable_api_key_auth` in the security settings and is refused when it is a terminal key.
- A refused request answers like every Glados error, `{"detail", "code"}` with the status of the error's base. A missing or wrong token answers 401 with `WWW-Authenticate: Bearer realm="glados"`.
- The middleware sets `pat_id_var` or `api_key_id_var`, so the request also lands in the token's usage log like any other PAT or API key call.
- OAuth is not offered. The protected resource metadata of RFC 9728 is added together with Entra ID, when there is an authorization server to name.

## 2 the gate permission and the token presets

- Reading in Glados is open to every active user. `use:mcp` (`Permission.USE_MCP`) is the gate of the surface, so a token without it, such as the SolidWorks add-in's PAT, cannot reach every reader at once through an agent.
- A token carries `use:mcp` only when its creator holds it (`assert_requested_permissions_allowed`), so an admin decides per user or group who may connect an agent at all.
- The draft tools need the write permission of what they create on top, such as `write:orders` for a draft purchase order. A tool lists those in `requires` and the use case checks them again.
- `AGENT_READ_SCOPES` and `AGENT_DRAFT_SCOPES` in `domain/services/token_permission_rules.py` are the two presets the token dialog offers. `GET /api/v1/web/host/capabilities` returns them with `agent_access_enabled` and the agent lifetime cap.
- An API key acts as its own service account, so nobody stands behind it. The server never lists a draft tool to an API key and refuses one with `AgentToolNotAllowedError`.

### 2.1 approval and consent

Agent access needs three confirmations, each by the person who answers for it.

- The company approves sending Glados data to AI providers. An admin records it in the agent settings with `processing_approved`, naming the providers in `approved_providers` and, optionally, linking the company's AI policy in `ai_policy_url` (an http or https URL without a query or fragment). `UpdateAgentSettings` stamps `processing_approved_at`. `AdminAgentSettings.assert_valid` refuses switching agent access on without the approval, and an approval naming no provider, with `AgentAccessNotApprovedError` (422).
- An admin grants `use:mcp` per user or group (section 2).
- Every user confirms for themselves that their agent may process Glados data on their behalf, at `GET`, `PUT` and `DELETE /api/v1/web/users/me/agent-consent`. The consent is one row per user in `user_agent_consent`, deleted with the user.
- `GET` returns what the consent dialog shows: whether agent access is ready, whether the caller holds `use:mcp`, the approved providers, the AI policy link, whether names and prices leave in results, the consent text version and the caller's own confirmation.
- `PUT` takes the `consent_version` the user read. It needs an account that may hold a PAT, `use:mcp`, and agent access approved and switched on (`AgentAccessDisabledError`, 403); another version than `AGENT_CONSENT_VERSION` answers `AgentConsentOutdatedError` (422).
- `DELETE` withdraws the consent and revokes every unexpired PAT of the caller that carries `use:mcp`, each recorded in the security log with the reason `agent_consent_withdrawn`. It works while agent access is off, so withdrawing is always possible.
- A consent counts only when it confirms `AGENT_CONSENT_VERSION` and was given at or after `processing_approved_at` (`consent_is_current` in `domain/services/agent_policy.py`). Otherwise `AuthenticateAgent` refuses a PAT with `AgentConsentRequiredError` (403), and the agent works again once the user confirms.
- The approval is stamped anew whenever the settings change what users consented to: the approved providers, the AI policy link, `include_person_names` or `include_costs` (`consent_terms_changed`). Every user then confirms again. Withdrawing the approval clears the stamp.
- Raise `AGENT_CONSENT_VERSION` whenever the consent text in the frontend locales changes in a way users must confirm again.
- An API key acts for a service account, not a person, so the company's approval covers it and it needs no consent.
- The consent records a user's informed choice, but it does not replace a review by data protection or the works council, which the company clarifies before approving.

## 3 agent token lifetime

- A PAT or API key that carries `use:mcp` is an agent token (`is_agent_token`).
- A new agent token needs an expiry within the agent settings' `token_max_lifetime_days` (default 30). That cap holds even while the security settings' general cap is 0, and the stricter of the two wins otherwise (`agent_token_lifetime_cap`, applied by `read_token_lifetime_cap_for` in `CreatePat` and `CreateApiKey`).
- The `agent_token_sweep` job of `BackupScheduler` runs `SweepAgentTokens` hourly under `AdvisoryLockKey.AGENT_TOKEN_SWEEP`.
- An agent token counts as used by its latest agent call, or from its creation when it has none. One unused for `token_idle_revoke_days` (default 14) is revoked, recorded as `pat_revoked` or `api_key_revoked` with `reason: idle`, and its owner (the API key's creator) gets an `agent_token_revoked` notification. Revoking an API key deactivates its service account, as a manual revocation does.
- The owner of an agent token that expires within three days gets one `agent_token_expiring` notification, deduplicated by its source event id.
- The agent call log is purged with the audit retention. When that retention is shorter than the idle days, a token whose last call was purged counts as unused since its creation.

## 4 the call budgets

- Every call of a token counts against `calls_per_minute` (default 120), refused calls included, so an agent stuck in a loop stays refused until it slows down.
- The successful draft calls of a token count against `drafts_per_hour` (default 20). Zero switches drafting off for everyone.
- A spent budget answers an error result with `AgentBudgetExceededError` in the log, never a protocol error, so the agent reads why.
- The budgets are counted from the agent call log, so they hold across workers. Two calls in the same instant may both pass the last free slot.
- A draft call with an `idempotency_key` the same token already used successfully for the same tool returns the first call's references and runs nothing. The key is checked against the log, not claimed in a transaction, so two concurrent calls with one key may both run; agents send repeats one after the other.

## 5 what a result may carry

- Tool results go to the agent's model provider, outside the company.
- `redact` in `domain/services/agent_policy.py` runs on every result. A key that names a person (`full_name`, `username`, `email`, `phone` and their `*_` forms such as `operator_full_name`) reads `[hidden]`, null stays null. A key that carries money (a word such as `price`, `cost`, `amount`, `currency`, `discount`, `surcharge` or `budget`, unless it also says `quantity`, `qty`, `count`, `hours` or `minutes`) is dropped with its value.
- A free text history, such as the `changes` changelog of an item or project, names the person behind each entry and may quote old and new prices, which redaction by key cannot see. It is dropped unless both names and money may leave.
- `include_person_names` and `include_costs` in the agent settings let them in. Both are off by default.
- Redaction works on key names. A tool whose result names people or money under another key must leave that field out itself.
- Files, drawings and pictures are not offered to agents.
- A result longer than 200 000 characters is refused with a hint to narrow the query, and the log keeps at most 4 000 characters of a call's arguments.

## 6 the agent call log

- Every tool call, a refused or failed one included, is one row of `agent_call_table` (`domain/entities/agent_call.py`): time, owner, token kind, id and name, tool, the capped arguments, outcome (`ok`, `error`, `refused`), duration, error message, request id, the references of the records it created and the idempotency key.
- The row is written on a session of its own after the call, so a call that failed is logged too. A write the call made still records the owner as its changer through `bind_acting_user`.
- `GET /api/v1/web/agent-calls/` lists the log, newest first, filtered by user, PAT, API key, tool or created reference. Everyone sees the calls of their own tokens; holders of `read:settings` see every call and may filter by user. Each row names the token's owner.
- A created reference reads `<kind>:<public id>`, such as `order:3f2c...`. Each one is also a row of `agent_created_record`, written with its call and purged before it, so a lookup by reference needs no search through the calls.
- `POST /api/v1/web/agent-calls/created-records` takes up to 200 references and answers which of them an agent created, with the token's name and owner. Every signed in user may ask, since the answer says nothing about what the agent was asked, and the web app marks those records with an Agent tag in the order, quote request and lot lists.

## 7 the agent settings

- The settings live in the singleton `admin_agent_settings` (`domain/entities/admin_settings/agents.py`), read and written at `/api/v1/web/admin/settings/agents` with `read:settings` and `write:settings`, and audited under `agents`.
- They are seeded switched off and without an approval. Every field and its default is on the entity.
- `allowed_origins` takes bare http or https origins, normalised to lower case without a trailing slash; anything else answers 422.

## 8 threat model

| Threat | What stops it |
| ------ | ------------- |
| A leaked add-in PAT is used to read everything through an agent. | The token lacks `use:mcp`. |
| Glados data goes to an AI provider the company has not approved, or for a user who never agreed. | Agent access cannot be switched on without the recorded approval, and a PAT works only while its owner's consent covers the current terms. Glados cannot see which provider a client uses, so the approval names the providers and the consent dialog shows them. |
| A leaked agent token in a laptop's client config. | At most 30 days of life, revoked after 14 idle days, revocable at once, every call logged with its arguments. |
| Text written into Glados (a description, a supplier note, a PDM property) instructs the agent to do harm. | The agent can only create drafts, which a person commits in the web app; no tool sends mail, posts webhooks, prints, sends a quote request or schedules. The server instructions say that field contents are data. |
| An injected agent sends Glados data out through its other tools. | Outside Glados' control. The guide tells users not to pair a Glados token with web or mail tools in unattended agents, and names and prices stay out of results by default. |
| An injected agent writes misleading meeting notes or notifies people through them. | A meeting notes draft is seen only by its creator and changes no meeting until they apply it; its card texts lose every mention and image on the way in, and the todo owners are notified only by the apply. |
| An unattended agent creates work without a person behind it. | An API key never reaches a draft tool. |
| An agent loop floods Glados or creates drafts by the dozen. | The call and draft budgets and the idempotency key. |
| A web page drives a user's local agent token through DNS rebinding or a local proxy. | Browser origins outside the allowlist are refused, cookies are never accepted. |
| A tool checks less than the web route it mirrors. | Tools build their use cases through the route's own factory (`DependencyResolver`), the use cases check their own permissions, and `requires` mirrors any check a route makes outside its use case. |
