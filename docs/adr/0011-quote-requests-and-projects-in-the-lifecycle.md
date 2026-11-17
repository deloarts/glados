# 0011 quote requests join the reconciler and a project's status becomes a guarded intent

- Status: accepted
- Date: 2026-10-31

## context

[ADR 0008](0008-derived-lifecycle-statuses.md) derived the statuses of lots, positions, production orders, orders, order lines and demands, but left two aggregates beside it. A quote request derived its status inside its own use cases from its close and cancel intents and line states, so no order writer had to lock it. A project's status was a free edit. An audit of the transitions showed what that cost: an award stayed recorded when the order line it created was canceled, deleting a lot position left its quote requests with a stale status, dropping the last line closed a request for good, and a project could be archived or completed with open lots, lines and demands on it, while new work could still be moved onto it. Keeping the request out of the lock order would have meant every order writer either ignoring the award or locking the request out of order.

## decision

A quote request is a reconciled aggregate, the last one in the lock order, so an order or lot writer that reaches it through a line never locks it early. A request line counts as awarded only while an order line its award created is not canceled; cancelling that line or its order opens the request line again with a note that the award was voided. The award reads the request, locks the lifecycle rows with the request last and refuses when the request changed meanwhile. A project's status keeps nothing to derive it from and stays a user's decision, but it moves only through the rules of an intent table: it needs `manage:projects` and the project's edit version, completing or archiving needs every piece of live work on the project finished, and holding is allowed with open work. Only an active project takes new work; the use cases that add work share-lock the project, which the status move locks for update before it counts.

## consequences

An award can no longer outlive the order line it created, and a buyer can award a voided line again on the same request. A request someone closed stays closed when an award on it is voided, with the void in its changelog, and offers a reopen that clears the close and derives the status again, so the closing decision is undone only on purpose. The drift report, the repair and the architecture tests cover quote requests like the other aggregates. Order and lot writers that reach a request line touch the request, and a use case that deletes positions touches the requests naming them first. A project with open work cannot be completed or archived, and a client must send the project's version with a status change. Work already on a project that is not active can still be ordered, delivered, corrected and closed, so it can be cleaned up. The rules are in [CONTRIBUTING.md section 3.7](../CONTRIBUTING.md#37-lifecycle-facts-intents-and-the-reconciler) and the glossary entries for quote requests and projects in [section 10](../CONTRIBUTING.md#10-domain-glossary).
