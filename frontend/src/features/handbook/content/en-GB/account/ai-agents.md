---
title: AI Agents
summary: How you connect an AI agent such as Claude to Glados, what you agree to first, and how you keep track of what it does.
sourceRefs:
  - backend/src/modules/platform/application/use_cases/agent/agent_consent.py
  - backend/src/modules/platform/application/use_cases/agent/authenticate_agent.py
  - backend/src/modules/platform/application/use_cases/agent/sweep_agent_tokens.py
  - backend/src/modules/platform/domain/services/agent_policy.py
  - backend/src/modules/platform/domain/entities/admin_settings/agents.py
  - backend/src/modules/fulfillment/adapters/inbound/mcp/draft_tools.py
lastVerified: 2026-11-12
---

An AI agent such as Claude Code can answer questions about Glados for you and prepare routine work as drafts. It works with an agent token you create on the **AI Agents** tab of your account, and it acts as you, with your permissions or fewer. The tab also shows your consent and every call your agents made.

## Before you start {#before}

Three things must be in place. Your company records its approval of the AI providers it allows, your administrator gives you the **Use AI Agents** permission, and you give your own consent. Without the permission the buttons on the tab stay disabled, and their tooltip names what is missing. An agent token is an [access token](/handbook/account/access-tokens), so creating one also needs **Write Access Token**.

## Giving and withdrawing consent {#consent}

**Give Consent** opens a dialog that names the approved providers and says whether names of people and prices leave Glados. Tick the box and confirm. The **Consent** card then shows **Given** with the date.

When your administrator changes the approved providers, the AI policy or what leaves Glados, the card shows **Terms changed**. Your agent is refused until you read the new terms and consent again.

**Withdraw Consent** revokes all your agent tokens at once. It works even when agent access is switched off.

## Creating an agent token {#token}

**New Agent Token** asks for your consent first if it is missing. Choose the **Access**: **Read** lets the agent read and answer questions, **Read and Draft** also lets it prepare draft orders, quote requests and lots. Set **Expires In (Days)**; an agent token lives at most as long as your administrator allows, usually 30 days. Enter your **Current Password**, as for every access token.

Glados shows the token once, together with a command you paste into a terminal to connect Claude Code. Copy both before you close the dialog. **Access Tokens** lists the token too, and **Revoke** there stops just that one.

## What the agent can and cannot do {#scope}

The agent reads what you may read. A draft it prepares waits for you: you open it, check it and then order, send, plan or delete it as usual. The agent never orders, sends, schedules or deletes anything. In the order, quote request and lot lists an **Agent** tag marks a draft an agent created, and its tooltip names the token.

## Reviewing agent calls {#calls}

The **Agent Calls** table lists every call, newest first, with the tool, the **Outcome** and the **Details**. The **Created** column links to the drafts a call made. By default each token may make 120 calls a minute and 20 drafts an hour, and a call above that shows as **Refused**.

## When a token stops working {#stops}

A token stops when it expires, when it goes unused for the number of days your administrator set, usually 14, or when your consent no longer covers the current terms. You get a notification three days before a token expires, and another one after an unused token has been revoked.

## Examples {#examples}

1. You create a **Read** token, connect Claude Code and ask why lot L-1042 is late. The agent reads the lot and its steps and answers.
2. With a **Read and Draft** token you ask for a purchase order for the open demands of a project. The draft appears with an **Agent** tag. You open it from **Created**, check the quantities and order it.
3. Your administrator lets prices leave Glados. Your card shows **Terms changed**, and your agent is refused until you consent again.
4. You stop using a token. After 14 days without a call it is revoked, and a notification tells you so.
