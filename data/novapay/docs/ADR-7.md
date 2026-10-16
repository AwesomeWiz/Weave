# ADR-7: Redis Caching for Payment Service

**Status:** Accepted  
**Date:** 2026-05-20  
**Decision:** D-007  
**Author:** Alice Menon  

## Context

During incident INC-17 on May 10, 2026, Payment Service experienced request timeouts under burst traffic. Investigation via issue PAY-42 revealed that 70% of database query volume during peak windows consisted of repeated reads of idempotency keys and payment configuration data from PostgreSQL. These values change infrequently and are strong candidates for caching.

The payments engineering team discussed the problem in the #payments-engineering Slack channel (thread: payment-perf-2026-05). Benchmarks showed that placing Redis in front of PostgreSQL for these read paths reduced p99 latency from 380ms to 45ms at 500 concurrent requests, with a cache-hit ratio of 87%.

## Decision

Introduce Redis-backed caching in Payment Service for:

1. **Idempotency key lookups** — cached with a 60-second TTL and explicit invalidation on key creation/expiry.
2. **Payment configuration reads** — cached with a 60-second TTL and explicit invalidation on configuration writes.

Redis was selected because:

- It is already deployed in the NovaPay infrastructure stack for session management (confirmed by Platform Engineering).
- No new provisioning or operational overhead is required.
- Its sub-millisecond read latency meets the p99 < 200ms target for payment operations.
- The team has operational experience with Redis in production.

## Consequences

- **Positive:** Estimated 60% reduction in direct PostgreSQL queries during burst traffic. p99 latency target of < 200ms is achievable based on benchmarks.
- **Positive:** Reuse of existing Redis infrastructure reduces deployment risk and cost.
- **Risk:** Cache invalidation bugs could serve stale idempotency keys, potentially allowing duplicate payment processing. Mitigated by short TTLs and explicit invalidation on writes.
- **Risk:** Redis availability becomes a dependency for optimal Payment Service performance. Mitigated by fallback to direct PostgreSQL reads if the Redis connection is unavailable.

## Implementation

- **Commit:** 8fae2 in `novapay/payments-api`
- **Issue:** PAY-42
- **Service affected:** Payment Service
- **Technology introduced:** Redis

## Participants

- Alice Menon — Payments Tech Lead (approver)
- Ravi Nair — Payments Engineer (implementer)
- Maya Joseph — Platform Engineer (infrastructure review)
