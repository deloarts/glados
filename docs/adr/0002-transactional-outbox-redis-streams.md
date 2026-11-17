# 0002 domain events through a transactional outbox and Redis Streams

- Status: accepted
- Date: 2026-10-05

## context

Notifications, webhooks, automatic label printing, PDM sync and live refresh all react to things that happen in a request. Running them inline would slow the request and let a printer or webhook failure fail the write. Publishing straight to Redis after the commit loses events when Redis is down or the process dies between commit and publish, and publishing before the commit announces writes that may still roll back.

## decision

Use cases publish domain events through an `IEventBus` that writes a row into `event_outbox_table` in the same transaction as the business write. A relay (`src/modules/platform/infrastructure/events/outbox_relay.py`), limited to one running instance across workers by a Postgres advisory lock, drains committed rows onto the `glados:events` Redis stream, each batch in id order. Consumer groups in each worker process handle notifications, webhooks, auto print and PDM sync. Delivery is at least once; consumers deduplicate on the producer-assigned event id and do not rely on the order of events, since rows commit in a different order than they take their ids.

## consequences

An event exists if and only if its write committed, and Redis being down only delays delivery. Events must be published before the commit; one published after it is lost, which a static test and a runtime log tripwire guard against. Repositories never commit, so the bus has one mode: the use case publishes through `get_transactional_event_bus` and then commits its unit of work, see [CONTRIBUTING.md section 3.6](../CONTRIBUTING.md#36-events-and-the-outbox). Events a consumer keeps failing on are dead-lettered and can be replayed, and relayed rows stay in the outbox for 30 days, so events lost with Redis can be republished, see [OPERATIONS.md](../OPERATIONS.md).
