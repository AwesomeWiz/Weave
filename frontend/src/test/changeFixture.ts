import type { ChangeResponse } from '../types';

// Explicit offline component/API test data from the Stage 1 integration double.
// Never imported by application retrieval or used as a real-mode fallback.
export const changeFixture: ChangeResponse = {
  "answer": "Change Brief: proposed removal of Redis from Payment Service. This analysis does not execute the change.\n\nHistorical context (supported): Introduce Redis caching: During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors [issue:PAY-42]\n\nDocumented in ADR-7: Redis Caching for Payment Service [doc:ADR-7]. Implemented in commit:8fae2 [commit:8fae2].\n\nPotential direct impact, depth 1: service:payment-service \u2014USES\u2192 tech:redis. Not guaranteed failure.\n\nPotential indirect impact, depth 2: service:payment-service \u2014USES\u2192 tech:redis; service:checkout-service \u2014DEPENDS_ON\u2192 service:payment-service. Not guaranteed failure.\n\nPotential indirect impact, depth 3: service:payment-service \u2014USES\u2192 tech:redis; service:checkout-service \u2014DEPENDS_ON\u2192 service:payment-service; service:order-service \u2014DEPENDS_ON\u2192 service:checkout-service. Not guaranteed failure.\n\nReviewer: Ravi Nair (person:ravi), evidence score 16. Historical expertise and team membership do not establish current personal ownership.\n\nReviewer: Alice Menon (person:alice), evidence score 14. Historical expertise and team membership do not establish current personal ownership.\n\nReviewer: Maya Joseph (person:maya), evidence score 5. Historical expertise and team membership do not establish current personal ownership.\n\nCurrent freshness: review recommended for doc:architecture-overview, updated 2026-05-01T12:00:00Z; later graph-linked changes warrant review, not a conclusion that the document is wrong.\n\nIf approved and implemented, review: doc:ADR-7, doc:architecture-overview, doc:runbook-payment-latency. This is separate from current freshness.\n\nKNOWN_FACT: Payment Service uses Redis. Stored structural relationship; it does not establish guaranteed failure.\n\nKNOWN_FACT: Checkout Service depends on Payment Service. Stored structural relationship; it does not establish guaranteed failure.\n\nKNOWN_FACT: Order Service depends on Checkout Service. Stored structural relationship; it does not establish guaranteed failure.\n\nINFERRED_RISK: Removing Redis may reintroduce the latency pressure described in the historical rationale under comparable traffic conditions. Inference from historical evidence, not a benchmark or prediction of the proposed implementation. [issue:PAY-42]\n\nRECOMMENDATION: Validate Payment Service's cache-removal behavior before rollout. Suggested engineering action; no test has been performed by this analysis.\n\nRecommended validation (not performed): Test the returned dependency path to Payment Service under the proposed cache removal; do not assume failure propagation. Test the returned dependency path to Checkout Service under the proposed cache removal; do not assume failure propagation. Test the returned dependency path to Order Service under the proposed cache removal; do not assume failure propagation. Request review from the evidence-ranked contributors and verify current ownership and approval responsibilities. Team membership is not personal ownership. If the change is approved and implemented, review the returned service-linked documents and record the new architecture decision. Load-test Payment Service under comparable burst traffic and compare latency before approving cache removal. Verify Payment Service's behavior without Redis before rollout; this analysis does not execute the change or run tests.\n\nPer-tool support: decision_trace: supported (validated); impact_analysis: partially_supported (validated); find_expert: supported (validated); find_stale_knowledge: supported (validated)\n\nOverall evidence status: partially_supported. Potential downstream impact is not guaranteed failure.\n\nLimitations: Current graph relationships and potential downstream impact: Impact is based on bounded graph structure; textual evidence of propagation is not established.",
  "support_status": "partially_supported",
  "tools_used": [
    "trace_decision",
    "impact_analysis",
    "find_expert",
    "find_stale_knowledge"
  ],
  "sources": [
    {
      "id": "commit:8fae2",
      "type": "Commit",
      "title": "feat: introduce Redis-backed caching for payment reads",
      "snippet": "feat: introduce Redis-backed caching for payment reads\n\nAdd RedisCache adapter to Payment Service. Frequently-read payment\nconfiguration and idempotency keys are now served from Redis, reducing\ndirect PostgreSQL queries during burst traffic by ~60%.\n\nCloses PAY-42\nImplements Decision D-007\nSee ADR-7 for architectural rationale.",
      "url": "https://github.novapay.example/novapay/payments-api/commit/8fae2d4",
      "timestamp": "2026-05-19T10:15:00Z",
      "entity_ids": [
        "commit:8fae2"
      ],
      "metadata": {
        "source_id": "commit:8fae2",
        "source_type": "Commit",
        "chunk_ids": [
          "chunk:commit:8fae2:0"
        ],
        "chunks": [
          {
            "id": "chunk:commit:8fae2:0",
            "source_id": "commit:8fae2",
            "source_type": "Commit",
            "chunk_index": 0,
            "title": "feat: introduce Redis-backed caching for payment reads",
            "timestamp": "2026-05-19T10:15:00Z",
            "url": "https://github.novapay.example/novapay/payments-api/commit/8fae2d4"
          }
        ],
        "dataset": "development_fixture"
      }
    },
    {
      "id": "doc:ADR-7",
      "type": "Document",
      "title": "ADR-7: Redis Caching for Payment Service",
      "snippet": "# ADR-7: Redis Caching for Payment Service\n\n**Status:** Accepted  \n**Date:** 2026-05-20  \n**Decision:** D-007  \n**Author:** Alice Menon  \n\n## Context\n\nDuring incident INC-17 on May 10, 2026, Payment Service experienced request timeouts under burst traffic. Investigation via issue PAY-42 revealed that 70% of database query volume during peak windows consisted of repeated reads of idempotency keys and payment configuration data from PostgreSQL. These values change infrequently and are strong candidates for caching.\n\nThe payments engineering team discussed the problem in the #payments-engineering Slack channel (thread: payment-perf-2026-05). Benchmarks showed that placing Redis in front of PostgreSQL for these read paths reduced p99 latency from 380ms to 45ms at 500 concurrent requests, with a cache-hit ratio of 87%.\n\n## Decision\n\nIntroduce Redis-backed caching in Payment Service for:\n\n1. **Idempotency key lookups** \u2014 cached with a 60-second TTL and explicit invalidation on key creation/expiry.\n2. **Payment configuration reads** \u2014 cached with a 60-second TTL and explicit invalidation on configuration writes.\n\nRedis was selected because:\n\n- It is already deployed in the NovaPay infrastructure stack for session management (confirmed by Platform Engineering).\n- No new provisioning or operational overhead is required.\n- Its sub-millisecond read latency meets the p99 < 200ms target for payment operations.\n- The team has operational experience with Redis in production.\n\n## Consequences\n\n- **Positive:** Estimated 60% reduction in direct PostgreSQL queries during burst traffic. p99 la",
      "url": "https://docs.novapay.example/adrs/ADR-7",
      "timestamp": "2026-05-20T10:00:00Z",
      "entity_ids": [
        "doc:ADR-7"
      ],
      "metadata": {
        "source_id": "doc:ADR-7",
        "source_type": "Document",
        "chunk_ids": [
          "chunk:doc:ADR-7:0"
        ],
        "chunks": [
          {
            "id": "chunk:doc:ADR-7:0",
            "source_id": "doc:ADR-7",
            "source_type": "Document",
            "chunk_index": 0,
            "title": "ADR-7: Redis Caching for Payment Service",
            "timestamp": "2026-05-20T10:00:00Z",
            "url": "https://docs.novapay.example/adrs/ADR-7"
          }
        ],
        "dataset": "development_fixture"
      }
    },
    {
      "id": "issue:PAY-42",
      "type": "Issue",
      "title": "Reduce payment latency under burst traffic",
      "snippet": "During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors",
      "url": "https://jira.novapay.example/browse/PAY-42",
      "timestamp": "2026-05-11T09:00:00Z",
      "entity_ids": [
        "issue:PAY-42"
      ],
      "metadata": {
        "source_id": "issue:PAY-42",
        "source_type": "Issue",
        "chunk_ids": [
          "chunk:issue:PAY-42:0"
        ],
        "chunks": [
          {
            "id": "chunk:issue:PAY-42:0",
            "source_id": "issue:PAY-42",
            "source_type": "Issue",
            "chunk_index": 0,
            "title": "Reduce payment latency under burst traffic",
            "timestamp": "2026-05-11T09:00:00Z",
            "url": "https://jira.novapay.example/browse/PAY-42"
          }
        ],
        "dataset": "development_fixture"
      }
    },
    {
      "id": "message:payment-perf-7",
      "type": "Message",
      "title": "Thread: payment-perf-2026-05",
      "snippet": "Thread: Payment Service latency improvements\n\n[2026-05-15 10:00 UTC] Alice Menon: After INC-17 I reviewed the slow-query logs. The majority of burst-window reads are idempotency key lookups and payment config fetches \u2014 both are read-heavy and change infrequently. We should cache them.\n\n[2026-05-15 10:12 UTC] Ravi Nair: Agreed. I ran a local benchmark with Redis sitting in front of Postgres for those paths. p99 dropped from 380ms to 45ms at 500 concurrent requests. Cache-hit ratio was 87% with a 60-second TTL.\n\n[2026-05-16 09:30 UTC] Maya Joseph: From a platform perspective Redis is already in our infrastructure stack for session management. We can reuse the existing cluster \u2014 no new provisioning needed.\n\n[2026-05-17 14:00 UTC] Alice Menon: Let's go ahead. I'll write up ADR-7 and Ravi can start the implementation against PAY-42. We'll target a 60-second TTL with explicit invalidation on config writes.",
      "url": "https://slack.novapay.example/archives/payments-engineering/payment-perf-2026-05",
      "timestamp": "2026-05-15T10:00:00Z",
      "entity_ids": [
        "message:payment-perf-7"
      ],
      "metadata": {
        "source_id": "message:payment-perf-7",
        "source_type": "Message",
        "chunk_ids": [
          "chunk:message:payment-perf-7:0"
        ],
        "chunks": [
          {
            "id": "chunk:message:payment-perf-7:0",
            "source_id": "message:payment-perf-7",
            "source_type": "Message",
            "chunk_index": 0,
            "title": "Thread: payment-perf-2026-05",
            "timestamp": "2026-05-15T10:00:00Z",
            "url": "https://slack.novapay.example/archives/payments-engineering/payment-perf-2026-05"
          }
        ],
        "dataset": "development_fixture"
      }
    },
    {
      "id": "doc:architecture-overview",
      "type": "Document",
      "title": "NovaPay Core Architecture Overview",
      "snippet": "# NovaPay Core Architecture Overview\n\n**Document ID:** doc:architecture-overview\n**Version:** 2.4\n**Last Updated:** 2026-05-01\n**Author:** Platform & Architecture Working Group\n**Target Service:** service:payment-service\n\n## 1. System Overview\n\nNovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.\n\n### Core Components\n\n- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.\n- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.\n- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.\n\n## 2. Transaction Flow & Data Access\n\n1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.\n2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.\n3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.\n4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.\n\n## 3. Storage and Scaling Constraints\n\nAll configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.",
      "url": "https://docs.novapay.example/architecture/overview",
      "timestamp": "2026-05-01T12:00:00Z",
      "entity_ids": [
        "doc:architecture-overview"
      ],
      "metadata": {
        "source_id": "doc:architecture-overview",
        "source_type": "Document",
        "chunk_ids": [
          "chunk:doc:architecture-overview:0"
        ],
        "chunks": [
          {
            "id": "chunk:doc:architecture-overview:0",
            "source_id": "doc:architecture-overview",
            "source_type": "Document",
            "chunk_index": 0,
            "title": "NovaPay Core Architecture Overview",
            "timestamp": "2026-05-01T12:00:00Z",
            "url": "https://docs.novapay.example/architecture/overview"
          }
        ],
        "dataset": "development_fixture"
      }
    }
  ],
  "graph": {
    "nodes": [
      {
        "id": "decision:D-007",
        "type": "Decision",
        "label": "Introduce Redis caching",
        "properties": {
          "id": "decision:D-007",
          "title": "Introduce Redis caching",
          "summary": "Adopt Redis caching to reduce repeated read latency during payment bursts. Redis will cache idempotency keys and frequently-read payment configuration, reducing direct database hits by an estimated 60% during peak traffic windows.",
          "status": "accepted",
          "decided_at": "2026-05-18T14:30:00Z",
          "category": "architecture",
          "affects": [
            "service:payment-service"
          ],
          "introduces": [
            "tech:redis"
          ],
          "participants": [
            "person:alice",
            "person:ravi",
            "person:maya"
          ],
          "approved_by": [
            "person:alice"
          ],
          "supported_by": [
            "issue:PAY-42",
            "message:payment-perf-7"
          ],
          "implemented_by": [
            "commit:8fae2"
          ],
          "documented_in": [
            "doc:ADR-7"
          ]
        }
      },
      {
        "id": "service:payment-service",
        "type": "Service",
        "label": "Payment Service",
        "properties": {
          "id": "service:payment-service",
          "name": "Payment Service",
          "description": "Core payment processing service handling transaction authorization, capture, and settlement.",
          "criticality": "high",
          "technologies": [
            "tech:redis",
            "tech:postgresql"
          ],
          "depends_on": []
        }
      },
      {
        "id": "tech:redis",
        "type": "Technology",
        "label": "Redis",
        "properties": {
          "id": "tech:redis",
          "name": "Redis",
          "category": "cache"
        }
      },
      {
        "id": "incident:INC-17",
        "type": "Incident",
        "label": "Payment requests timing out during peak traffic",
        "properties": {
          "id": "incident:INC-17",
          "title": "Payment requests timing out during peak traffic",
          "severity": "high",
          "summary": "Multiple payment API endpoints returned HTTP 504 Gateway Timeout errors during the 11:00\u201311:45 UTC burst window on May 10. Approximately 12% of transactions failed. Root cause traced to excessive database read latency under concurrent burst load in Payment Service. No data loss confirmed.",
          "started_at": "2026-05-10T11:00:00Z",
          "resolved_at": "2026-05-10T13:30:00Z",
          "affected_services": [
            "service:payment-service"
          ],
          "related_issues": [
            "issue:PAY-42"
          ],
          "url": "https://incidents.novapay.example/INC-17"
        }
      },
      {
        "id": "doc:ADR-7",
        "type": "Document",
        "label": "ADR-7: Redis Caching for Payment Service",
        "properties": {
          "id": "doc:ADR-7",
          "title": "ADR-7: Redis Caching for Payment Service",
          "doc_type": "ADR",
          "content": "# ADR-7: Redis Caching for Payment Service\n\n**Status:** Accepted  \n**Date:** 2026-05-20  \n**Decision:** D-007  \n**Author:** Alice Menon  \n\n## Context\n\nDuring incident INC-17 on May 10, 2026, Payment Service experienced request timeouts under burst traffic. Investigation via issue PAY-42 revealed that 70% of database query volume during peak windows consisted of repeated reads of idempotency keys and payment configuration data from PostgreSQL. These values change infrequently and are strong candidates for caching.\n\nThe payments engineering team discussed the problem in the #payments-engineering Slack channel (thread: payment-perf-2026-05). Benchmarks showed that placing Redis in front of PostgreSQL for these read paths reduced p99 latency from 380ms to 45ms at 500 concurrent requests, with a cache-hit ratio of 87%.\n\n## Decision\n\nIntroduce Redis-backed caching in Payment Service for:\n\n1. **Idempotency key lookups** \u2014 cached with a 60-second TTL and explicit invalidation on key creation/expiry.\n2. **Payment configuration reads** \u2014 cached with a 60-second TTL and explicit invalidation on configuration writes.\n\nRedis was selected because:\n\n- It is already deployed in the NovaPay infrastructure stack for session management (confirmed by Platform Engineering).\n- No new provisioning or operational overhead is required.\n- Its sub-millisecond read latency meets the p99 < 200ms target for payment operations.\n- The team has operational experience with Redis in production.\n\n## Consequences\n\n- **Positive:** Estimated 60% reduction in direct PostgreSQL queries during burst traffic. p99 latency target of < 200ms is achievable based on benchmarks.\n- **Positive:** Reuse of existing Redis infrastructure reduces deployment risk and cost.\n- **Risk:** Cache invalidation bugs could serve stale idempotency keys, potentially allowing duplicate payment processing. Mitigated by short TTLs and explicit invalidation on writes.\n- **Risk:** Redis availability becomes a dependency for optimal Payment Service performance. Mitigated by fallback to direct PostgreSQL reads if the Redis connection is unavailable.\n\n## Implementation\n\n- **Commit:** 8fae2 in `novapay/payments-api`\n- **Issue:** PAY-42\n- **Service affected:** Payment Service\n- **Technology introduced:** Redis\n\n## Participants\n\n- Alice Menon \u2014 Payments Tech Lead (approver)\n- Ravi Nair \u2014 Payments Engineer (implementer)\n- Maya Joseph \u2014 Platform Engineer (infrastructure review)\n",
          "updated_at": "2026-05-20T10:00:00Z",
          "url": "https://docs.novapay.example/adrs/ADR-7",
          "describes": [
            "service:payment-service"
          ]
        }
      },
      {
        "id": "commit:8fae2",
        "type": "Commit",
        "label": "commit:8fae2",
        "properties": {
          "id": "commit:8fae2",
          "sha": "8fae2d4a1b3c5e6f7890abcdef1234567890abcd",
          "message": "feat: introduce Redis-backed caching for payment reads\n\nAdd RedisCache adapter to Payment Service. Frequently-read payment\nconfiguration and idempotency keys are now served from Redis, reducing\ndirect PostgreSQL queries during burst traffic by ~60%.\n\nCloses PAY-42\nImplements Decision D-007\nSee ADR-7 for architectural rationale.",
          "timestamp": "2026-05-19T10:15:00Z",
          "author": "person:ravi",
          "repository": "repo:novapay/payments-api",
          "changes": [
            "service:payment-service"
          ],
          "implements_decision": [
            "decision:D-007"
          ],
          "addresses": [
            "issue:PAY-42"
          ],
          "architecture_change": true,
          "url": "https://github.novapay.example/novapay/payments-api/commit/8fae2d4"
        }
      },
      {
        "id": "issue:PAY-42",
        "type": "Issue",
        "label": "Reduce payment latency under burst traffic",
        "properties": {
          "id": "issue:PAY-42",
          "key": "PAY-42",
          "title": "Reduce payment latency under burst traffic",
          "description": "During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors",
          "status": "Done",
          "priority": "High",
          "created_at": "2026-05-11T09:00:00Z",
          "resolved_at": "2026-05-20T16:00:00Z",
          "assignee": "person:ravi",
          "affected_services": [
            "service:payment-service"
          ],
          "related_incidents": [
            "incident:INC-17"
          ],
          "url": "https://jira.novapay.example/browse/PAY-42"
        }
      },
      {
        "id": "message:payment-perf-7",
        "type": "Message",
        "label": "message:payment-perf-7",
        "properties": {
          "id": "message:payment-perf-7",
          "channel": "#payments-engineering",
          "thread_id": "payment-perf-2026-05",
          "text": "Thread: Payment Service latency improvements\n\n[2026-05-15 10:00 UTC] Alice Menon: After INC-17 I reviewed the slow-query logs. The majority of burst-window reads are idempotency key lookups and payment config fetches \u2014 both are read-heavy and change infrequently. We should cache them.\n\n[2026-05-15 10:12 UTC] Ravi Nair: Agreed. I ran a local benchmark with Redis sitting in front of Postgres for those paths. p99 dropped from 380ms to 45ms at 500 concurrent requests. Cache-hit ratio was 87% with a 60-second TTL.\n\n[2026-05-16 09:30 UTC] Maya Joseph: From a platform perspective Redis is already in our infrastructure stack for session management. We can reuse the existing cluster \u2014 no new provisioning needed.\n\n[2026-05-17 14:00 UTC] Alice Menon: Let's go ahead. I'll write up ADR-7 and Ravi can start the implementation against PAY-42. We'll target a 60-second TTL with explicit invalidation on config writes.",
          "timestamp": "2026-05-15T10:00:00Z",
          "participants": [
            "person:alice",
            "person:ravi",
            "person:maya"
          ],
          "url": "https://slack.novapay.example/archives/payments-engineering/payment-perf-2026-05"
        }
      },
      {
        "id": "chunk:commit:8fae2:0",
        "type": "Chunk",
        "label": "feat: introduce Redis-backed caching for payment reads",
        "properties": {
          "id": "chunk:commit:8fae2:0",
          "source_id": "commit:8fae2",
          "source_type": "Commit",
          "chunk_index": 0,
          "title": "feat: introduce Redis-backed caching for payment reads",
          "text": "feat: introduce Redis-backed caching for payment reads\n\nAdd RedisCache adapter to Payment Service. Frequently-read payment\nconfiguration and idempotency keys are now served from Redis, reducing\ndirect PostgreSQL queries during burst traffic by ~60%.\n\nCloses PAY-42\nImplements Decision D-007\nSee ADR-7 for architectural rationale.",
          "timestamp": "2026-05-19T10:15:00Z",
          "url": "https://github.novapay.example/novapay/payments-api/commit/8fae2d4"
        }
      },
      {
        "id": "chunk:doc:ADR-7:0",
        "type": "Chunk",
        "label": "ADR-7: Redis Caching for Payment Service",
        "properties": {
          "id": "chunk:doc:ADR-7:0",
          "source_id": "doc:ADR-7",
          "source_type": "Document",
          "chunk_index": 0,
          "title": "ADR-7: Redis Caching for Payment Service",
          "text": "# ADR-7: Redis Caching for Payment Service\n\n**Status:** Accepted  \n**Date:** 2026-05-20  \n**Decision:** D-007  \n**Author:** Alice Menon  \n\n## Context\n\nDuring incident INC-17 on May 10, 2026, Payment Service experienced request timeouts under burst traffic. Investigation via issue PAY-42 revealed that 70% of database query volume during peak windows consisted of repeated reads of idempotency keys and payment configuration data from PostgreSQL. These values change infrequently and are strong candidates for caching.\n\nThe payments engineering team discussed the problem in the #payments-engineering Slack channel (thread: payment-perf-2026-05). Benchmarks showed that placing Redis in front of PostgreSQL for these read paths reduced p99 latency from 380ms to 45ms at 500 concurrent requests, with a cache-hit ratio of 87%.\n\n## Decision\n\nIntroduce Redis-backed caching in Payment Service for:\n\n1. **Idempotency key lookups** \u2014 cached with a 60-second TTL and explicit invalidation on key creation/expiry.\n2. **Payment configuration reads** \u2014 cached with a 60-second TTL and explicit invalidation on configuration writes.\n\nRedis was selected because:\n\n- It is already deployed in the NovaPay infrastructure stack for session management (confirmed by Platform Engineering).\n- No new provisioning or operational overhead is required.\n- Its sub-millisecond read latency meets the p99 < 200ms target for payment operations.\n- The team has operational experience with Redis in production.\n\n## Consequences\n\n- **Positive:** Estimated 60% reduction in direct PostgreSQL queries during burst traffic. p99 latency target of < 200ms is achievable based on benchmarks.\n- **Positive:** Reuse of existing Redis infrastructure reduces deployment risk and cost.\n- **Risk:** Cache invalidation bugs could serve stale idempotency keys, potentially allowing duplicate payment processing. Mitigated by short TTLs and explicit invalidation on writes.\n- **Risk:** Redis availability becomes a dependency for optimal Payment Service performance. Mitigated by fallback to direct PostgreSQL reads if the Redis connection is unavailable.\n\n## Implementation\n\n- **Commit:** 8fae2 in `novapay/payments-api`\n- **Issue:** PAY-42\n- **Service affected:** Payment Service\n- **Technology introduced:** Redis\n\n## Participants\n\n- Alice Menon \u2014 Payments Tech Lead (approver)\n- Ravi Nair \u2014 Payments Engineer (implementer)\n- Maya Joseph \u2014 Platform Engineer (infrastructure review)\n",
          "timestamp": "2026-05-20T10:00:00Z",
          "url": "https://docs.novapay.example/adrs/ADR-7"
        }
      },
      {
        "id": "chunk:issue:PAY-42:0",
        "type": "Chunk",
        "label": "Reduce payment latency under burst traffic",
        "properties": {
          "id": "chunk:issue:PAY-42:0",
          "source_id": "issue:PAY-42",
          "source_type": "Issue",
          "chunk_index": 0,
          "title": "Reduce payment latency under burst traffic",
          "text": "During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors",
          "timestamp": "2026-05-11T09:00:00Z",
          "url": "https://jira.novapay.example/browse/PAY-42"
        }
      },
      {
        "id": "chunk:message:payment-perf-7:0",
        "type": "Chunk",
        "label": "Thread: payment-perf-2026-05",
        "properties": {
          "id": "chunk:message:payment-perf-7:0",
          "source_id": "message:payment-perf-7",
          "source_type": "Message",
          "chunk_index": 0,
          "title": "Thread: payment-perf-2026-05",
          "text": "Thread: Payment Service latency improvements\n\n[2026-05-15 10:00 UTC] Alice Menon: After INC-17 I reviewed the slow-query logs. The majority of burst-window reads are idempotency key lookups and payment config fetches \u2014 both are read-heavy and change infrequently. We should cache them.\n\n[2026-05-15 10:12 UTC] Ravi Nair: Agreed. I ran a local benchmark with Redis sitting in front of Postgres for those paths. p99 dropped from 380ms to 45ms at 500 concurrent requests. Cache-hit ratio was 87% with a 60-second TTL.\n\n[2026-05-16 09:30 UTC] Maya Joseph: From a platform perspective Redis is already in our infrastructure stack for session management. We can reuse the existing cluster \u2014 no new provisioning needed.\n\n[2026-05-17 14:00 UTC] Alice Menon: Let's go ahead. I'll write up ADR-7 and Ravi can start the implementation against PAY-42. We'll target a 60-second TTL with explicit invalidation on config writes.",
          "timestamp": "2026-05-15T10:00:00Z",
          "url": "https://slack.novapay.example/archives/payments-engineering/payment-perf-2026-05"
        }
      },
      {
        "id": "service:checkout-service",
        "type": "Service",
        "label": "Checkout Service",
        "properties": {
          "id": "service:checkout-service",
          "name": "Checkout Service",
          "description": "Customer-facing checkout flow that orchestrates cart, pricing, and payment submission.",
          "criticality": "high",
          "technologies": [],
          "depends_on": [
            "service:payment-service"
          ]
        }
      },
      {
        "id": "service:order-service",
        "type": "Service",
        "label": "Order Service",
        "properties": {
          "id": "service:order-service",
          "name": "Order Service",
          "description": "Order management service that orchestrates checkout submissions and order lifecycle states.",
          "criticality": "medium",
          "technologies": [
            "tech:postgresql"
          ],
          "depends_on": [
            "service:checkout-service"
          ]
        }
      },
      {
        "id": "team:payments",
        "type": "Team",
        "label": "Payments",
        "properties": {
          "id": "team:payments",
          "name": "Payments",
          "members": [
            "person:alice",
            "person:ravi"
          ],
          "owns_services": [
            "service:payment-service"
          ]
        }
      },
      {
        "id": "team:platform",
        "type": "Team",
        "label": "Platform",
        "properties": {
          "id": "team:platform",
          "name": "Platform",
          "members": [
            "person:maya",
            "person:neeraj"
          ],
          "owns_services": [
            "service:checkout-service",
            "service:order-service"
          ]
        }
      },
      {
        "id": "doc:architecture-overview",
        "type": "Document",
        "label": "NovaPay Core Architecture Overview",
        "properties": {
          "id": "doc:architecture-overview",
          "title": "NovaPay Core Architecture Overview",
          "doc_type": "architecture",
          "content": "# NovaPay Core Architecture Overview\n\n**Document ID:** doc:architecture-overview\n**Version:** 2.4\n**Last Updated:** 2026-05-01\n**Author:** Platform & Architecture Working Group\n**Target Service:** service:payment-service\n\n## 1. System Overview\n\nNovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.\n\n### Core Components\n\n- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.\n- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.\n- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.\n\n## 2. Transaction Flow & Data Access\n\n1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.\n2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.\n3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.\n4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.\n\n## 3. Storage and Scaling Constraints\n\nAll configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.\n",
          "updated_at": "2026-05-01T12:00:00Z",
          "url": "https://docs.novapay.example/architecture/overview",
          "describes": [
            "service:payment-service"
          ]
        }
      },
      {
        "id": "doc:runbook-payment-latency",
        "type": "Document",
        "label": "Runbook: Payment Service Latency & Degradation",
        "properties": {
          "id": "doc:runbook-payment-latency",
          "title": "Runbook: Payment Service Latency & Degradation",
          "doc_type": "runbook",
          "content": "# Runbook: Payment Service Latency & Degradation\n\n**Document ID:** doc:runbook-payment-latency\n**Version:** 1.2\n**Last Updated:** 2026-05-22\n**Target Service:** service:payment-service\n**Related Incident:** incident:INC-17\n**Architecture Reference:** doc:ADR-7\n\n## 1. Trigger Conditions\n\nAlert `PaymentServiceP99LatencyHigh` fires when p99 API response latency exceeds 250ms for 3 consecutive minutes, or when HTTP 504 Gateway Timeout responses surpass 1% of total transaction volume.\n\n## 2. Diagnostic Steps\n\n1. **Verify Redis Cache Cluster Health**:\n   - Check Redis cluster CPU utilization and memory fragmentation via Grafana dashboard `Redis / Payments Cache`.\n   - Verify cache-hit ratio is maintained above 80% (target nominal: 87%).\n   - If cache-hit ratio drops below 50%, inspect Payment Service logs for Redis connection pool exhaustion or network partition.\n\n2. **Check Database Query Queue**:\n   - Query pg_stat_activity on PostgreSQL primary to identify lock contention on transaction tables.\n   - If Redis is healthy, database read pressure should remain below 40% of peak capacity.\n\n3. **Cache Invalidation & Failover**:\n   - In the event of primary Redis instance failure, the sentinel automatically promotes the replica within 15 seconds.\n   - Payment Service falls back to direct PostgreSQL reads if Redis is completely unreachable, operating in degraded mode.\n",
          "updated_at": "2026-05-22T10:00:00Z",
          "url": "https://docs.novapay.example/runbooks/payment-latency",
          "describes": [
            "service:payment-service"
          ]
        }
      },
      {
        "id": "tech:postgresql",
        "type": "Technology",
        "label": "PostgreSQL",
        "properties": {
          "id": "tech:postgresql",
          "name": "PostgreSQL",
          "category": "database"
        }
      },
      {
        "id": "person:alice",
        "type": "Person",
        "label": "Alice Menon",
        "properties": {
          "id": "person:alice",
          "name": "Alice Menon",
          "email_alias": "alice.menon@novapay.example",
          "role": "Payments Tech Lead",
          "team": "team:payments",
          "active": true
        }
      },
      {
        "id": "person:maya",
        "type": "Person",
        "label": "Maya Joseph",
        "properties": {
          "id": "person:maya",
          "name": "Maya Joseph",
          "email_alias": "maya.joseph@novapay.example",
          "role": "Platform Engineer",
          "team": "team:platform",
          "active": true
        }
      },
      {
        "id": "person:ravi",
        "type": "Person",
        "label": "Ravi Nair",
        "properties": {
          "id": "person:ravi",
          "name": "Ravi Nair",
          "email_alias": "ravi.nair@novapay.example",
          "role": "Payments Engineer",
          "team": "team:payments",
          "active": true
        }
      },
      {
        "id": "chunk:doc:architecture-overview:0",
        "type": "Chunk",
        "label": "NovaPay Core Architecture Overview",
        "properties": {
          "id": "chunk:doc:architecture-overview:0",
          "source_id": "doc:architecture-overview",
          "source_type": "Document",
          "chunk_index": 0,
          "title": "NovaPay Core Architecture Overview",
          "text": "# NovaPay Core Architecture Overview\n\n**Document ID:** doc:architecture-overview\n**Version:** 2.4\n**Last Updated:** 2026-05-01\n**Author:** Platform & Architecture Working Group\n**Target Service:** service:payment-service\n\n## 1. System Overview\n\nNovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.\n\n### Core Components\n\n- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.\n- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.\n- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.\n\n## 2. Transaction Flow & Data Access\n\n1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.\n2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.\n3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.\n4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.\n\n## 3. Storage and Scaling Constraints\n\nAll configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.\n",
          "timestamp": "2026-05-01T12:00:00Z",
          "url": "https://docs.novapay.example/architecture/overview"
        }
      }
    ],
    "edges": [
      {
        "id": "decision:D-007|AFFECTS|service:payment-service",
        "source": "decision:D-007",
        "target": "service:payment-service",
        "type": "AFFECTS",
        "properties": {}
      },
      {
        "id": "decision:D-007|INTRODUCES|tech:redis",
        "source": "decision:D-007",
        "target": "tech:redis",
        "type": "INTRODUCES",
        "properties": {}
      },
      {
        "id": "service:payment-service|USES|tech:redis",
        "source": "service:payment-service",
        "target": "tech:redis",
        "type": "USES",
        "properties": {}
      },
      {
        "id": "incident:INC-17|LED_TO|issue:PAY-42",
        "source": "incident:INC-17",
        "target": "issue:PAY-42",
        "type": "LED_TO",
        "properties": {}
      },
      {
        "id": "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
        "source": "decision:D-007",
        "target": "doc:ADR-7",
        "type": "DOCUMENTED_IN",
        "properties": {}
      },
      {
        "id": "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
        "source": "decision:D-007",
        "target": "commit:8fae2",
        "type": "IMPLEMENTED_BY",
        "properties": {}
      },
      {
        "id": "decision:D-007|SUPPORTED_BY|issue:PAY-42",
        "source": "decision:D-007",
        "target": "issue:PAY-42",
        "type": "SUPPORTED_BY",
        "properties": {}
      },
      {
        "id": "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
        "source": "decision:D-007",
        "target": "message:payment-perf-7",
        "type": "SUPPORTED_BY",
        "properties": {}
      },
      {
        "id": "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
        "source": "chunk:commit:8fae2:0",
        "target": "commit:8fae2",
        "type": "FROM_COMMIT",
        "properties": {}
      },
      {
        "id": "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
        "source": "chunk:doc:ADR-7:0",
        "target": "doc:ADR-7",
        "type": "FROM_DOCUMENT",
        "properties": {}
      },
      {
        "id": "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
        "source": "chunk:issue:PAY-42:0",
        "target": "issue:PAY-42",
        "type": "FROM_ISSUE",
        "properties": {}
      },
      {
        "id": "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7",
        "source": "chunk:message:payment-perf-7:0",
        "target": "message:payment-perf-7",
        "type": "FROM_MESSAGE",
        "properties": {}
      },
      {
        "id": "service:checkout-service|DEPENDS_ON|service:payment-service",
        "source": "service:checkout-service",
        "target": "service:payment-service",
        "type": "DEPENDS_ON",
        "properties": {}
      },
      {
        "id": "service:order-service|DEPENDS_ON|service:checkout-service",
        "source": "service:order-service",
        "target": "service:checkout-service",
        "type": "DEPENDS_ON",
        "properties": {}
      },
      {
        "id": "team:payments|OWNS|service:payment-service",
        "source": "team:payments",
        "target": "service:payment-service",
        "type": "OWNS",
        "properties": {}
      },
      {
        "id": "issue:PAY-42|AFFECTS|service:payment-service",
        "source": "issue:PAY-42",
        "target": "service:payment-service",
        "type": "AFFECTS",
        "properties": {}
      },
      {
        "id": "incident:INC-17|AFFECTS|service:payment-service",
        "source": "incident:INC-17",
        "target": "service:payment-service",
        "type": "AFFECTS",
        "properties": {}
      },
      {
        "id": "team:platform|OWNS|service:checkout-service",
        "source": "team:platform",
        "target": "service:checkout-service",
        "type": "OWNS",
        "properties": {}
      },
      {
        "id": "team:platform|OWNS|service:order-service",
        "source": "team:platform",
        "target": "service:order-service",
        "type": "OWNS",
        "properties": {}
      },
      {
        "id": "commit:8fae2|CHANGES|service:payment-service",
        "source": "commit:8fae2",
        "target": "service:payment-service",
        "type": "CHANGES",
        "properties": {}
      },
      {
        "id": "doc:ADR-7|DESCRIBES|service:payment-service",
        "source": "doc:ADR-7",
        "target": "service:payment-service",
        "type": "DESCRIBES",
        "properties": {}
      },
      {
        "id": "doc:architecture-overview|DESCRIBES|service:payment-service",
        "source": "doc:architecture-overview",
        "target": "service:payment-service",
        "type": "DESCRIBES",
        "properties": {}
      },
      {
        "id": "doc:runbook-payment-latency|DESCRIBES|service:payment-service",
        "source": "doc:runbook-payment-latency",
        "target": "service:payment-service",
        "type": "DESCRIBES",
        "properties": {}
      },
      {
        "id": "service:payment-service|USES|tech:postgresql",
        "source": "service:payment-service",
        "target": "tech:postgresql",
        "type": "USES",
        "properties": {}
      },
      {
        "id": "commit:8fae2|ADDRESSES|issue:PAY-42",
        "source": "commit:8fae2",
        "target": "issue:PAY-42",
        "type": "ADDRESSES",
        "properties": {}
      },
      {
        "id": "commit:8fae2|IMPLEMENTS_DECISION|decision:D-007",
        "source": "commit:8fae2",
        "target": "decision:D-007",
        "type": "IMPLEMENTS_DECISION",
        "properties": {}
      },
      {
        "id": "service:order-service|USES|tech:postgresql",
        "source": "service:order-service",
        "target": "tech:postgresql",
        "type": "USES",
        "properties": {}
      },
      {
        "id": "person:alice|APPROVED|decision:D-007",
        "source": "person:alice",
        "target": "decision:D-007",
        "type": "APPROVED",
        "properties": {}
      },
      {
        "id": "person:alice|PARTICIPATED_IN|decision:D-007",
        "source": "person:alice",
        "target": "decision:D-007",
        "type": "PARTICIPATED_IN",
        "properties": {}
      },
      {
        "id": "person:alice|WROTE|message:payment-perf-7",
        "source": "person:alice",
        "target": "message:payment-perf-7",
        "type": "WROTE",
        "properties": {}
      },
      {
        "id": "person:maya|PARTICIPATED_IN|decision:D-007",
        "source": "person:maya",
        "target": "decision:D-007",
        "type": "PARTICIPATED_IN",
        "properties": {}
      },
      {
        "id": "person:maya|WROTE|message:payment-perf-7",
        "source": "person:maya",
        "target": "message:payment-perf-7",
        "type": "WROTE",
        "properties": {}
      },
      {
        "id": "person:ravi|AUTHORED|commit:8fae2",
        "source": "person:ravi",
        "target": "commit:8fae2",
        "type": "AUTHORED",
        "properties": {}
      },
      {
        "id": "person:ravi|PARTICIPATED_IN|decision:D-007",
        "source": "person:ravi",
        "target": "decision:D-007",
        "type": "PARTICIPATED_IN",
        "properties": {}
      },
      {
        "id": "person:ravi|WROTE|message:payment-perf-7",
        "source": "person:ravi",
        "target": "message:payment-perf-7",
        "type": "WROTE",
        "properties": {}
      },
      {
        "id": "issue:PAY-42|ASSIGNED_TO|person:ravi",
        "source": "issue:PAY-42",
        "target": "person:ravi",
        "type": "ASSIGNED_TO",
        "properties": {}
      },
      {
        "id": "person:alice|MEMBER_OF|team:payments",
        "source": "person:alice",
        "target": "team:payments",
        "type": "MEMBER_OF",
        "properties": {}
      },
      {
        "id": "person:ravi|MEMBER_OF|team:payments",
        "source": "person:ravi",
        "target": "team:payments",
        "type": "MEMBER_OF",
        "properties": {}
      },
      {
        "id": "chunk:doc:architecture-overview:0|FROM_DOCUMENT|doc:architecture-overview",
        "source": "chunk:doc:architecture-overview:0",
        "target": "doc:architecture-overview",
        "type": "FROM_DOCUMENT",
        "properties": {}
      }
    ]
  },
  "metadata": {
    "latency_ms": 24,
    "graph_mode": "fixture",
    "generation": "deterministic",
    "warnings": [
      "Development fixture ? synthetic evidence, not live FalkorDB data.",
      "Current graph relationships and potential downstream impact: Impact is based on bounded graph structure; textual evidence of propagation is not established."
    ]
  },
  "data": {
    "proposed_change": {
      "requested_target": "Payment Service",
      "requested_change": "Remove Redis from Payment Service",
      "intent": "remove_technology",
      "resolution": "resolved",
      "service": {
        "id": "service:payment-service",
        "type": "Service",
        "label": "Payment Service",
        "properties": {
          "id": "service:payment-service",
          "name": "Payment Service",
          "description": "Core payment processing service handling transaction authorization, capture, and settlement.",
          "criticality": "high",
          "technologies": [
            "tech:redis",
            "tech:postgresql"
          ],
          "depends_on": []
        }
      },
      "technology": {
        "id": "tech:redis",
        "type": "Technology",
        "label": "Redis",
        "properties": {
          "id": "tech:redis",
          "name": "Redis",
          "category": "cache"
        }
      },
      "limitation": null
    },
    "historical_context": {
      "support_status": "supported",
      "summary": "Introduce Redis caching: During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors [issue:PAY-42]\n\nDocumented in ADR-7: Redis Caching for Payment Service [doc:ADR-7]. Implemented in commit:8fae2 [commit:8fae2].",
      "decision_ids": [
        "decision:D-007"
      ],
      "evidence": {
        "tool": "decision_trace",
        "node_ids": [
          "decision:D-007",
          "service:payment-service",
          "tech:redis",
          "incident:INC-17",
          "doc:ADR-7",
          "commit:8fae2",
          "issue:PAY-42",
          "message:payment-perf-7",
          "chunk:commit:8fae2:0",
          "chunk:doc:ADR-7:0",
          "chunk:issue:PAY-42:0",
          "chunk:message:payment-perf-7:0"
        ],
        "edge_ids": [
          "decision:D-007|AFFECTS|service:payment-service",
          "decision:D-007|INTRODUCES|tech:redis",
          "service:payment-service|USES|tech:redis",
          "incident:INC-17|LED_TO|issue:PAY-42",
          "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
          "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
          "decision:D-007|SUPPORTED_BY|issue:PAY-42",
          "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
          "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
          "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
          "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
          "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
        ],
        "source_ids": [
          "commit:8fae2",
          "doc:ADR-7",
          "issue:PAY-42",
          "message:payment-perf-7"
        ],
        "relationship_paths": [
          [
            "decision:D-007|AFFECTS|service:payment-service"
          ],
          [
            "decision:D-007|INTRODUCES|tech:redis"
          ],
          [
            "service:payment-service|USES|tech:redis"
          ],
          [
            "incident:INC-17|LED_TO|issue:PAY-42"
          ],
          [
            "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
          ],
          [
            "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
          ],
          [
            "decision:D-007|SUPPORTED_BY|issue:PAY-42"
          ],
          [
            "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
          ],
          [
            "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2"
          ],
          [
            "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7"
          ],
          [
            "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42"
          ],
          [
            "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
          ]
        ]
      }
    },
    "impact": {
      "entity": {
        "id": "tech:redis",
        "type": "Technology",
        "label": "Redis",
        "properties": {
          "id": "tech:redis",
          "name": "Redis",
          "category": "cache"
        }
      },
      "direct_impact": [
        {
          "service_id": "service:payment-service",
          "service": {
            "id": "service:payment-service",
            "name": "Payment Service",
            "description": "Core payment processing service handling transaction authorization, capture, and settlement.",
            "criticality": "high",
            "technologies": [
              "tech:redis",
              "tech:postgresql"
            ],
            "depends_on": []
          },
          "impact_depth": 1,
          "impact_type": "direct",
          "path": [
            "tech:redis",
            "service:payment-service"
          ],
          "path_edges": [
            {
              "source": "service:payment-service",
              "type": "USES",
              "target": "tech:redis"
            }
          ],
          "owners": [
            {
              "id": "team:payments",
              "name": "Payments"
            }
          ],
          "related_issues": [
            {
              "id": "issue:PAY-42",
              "title": "Reduce payment latency under burst traffic",
              "properties": {
                "id": "issue:PAY-42",
                "key": "PAY-42",
                "title": "Reduce payment latency under burst traffic",
                "description": "During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors",
                "status": "Done",
                "priority": "High",
                "created_at": "2026-05-11T09:00:00Z",
                "resolved_at": "2026-05-20T16:00:00Z",
                "assignee": "person:ravi",
                "affected_services": [
                  "service:payment-service"
                ],
                "related_incidents": [
                  "incident:INC-17"
                ],
                "url": "https://jira.novapay.example/browse/PAY-42"
              },
              "service_id": "service:payment-service"
            }
          ],
          "related_incidents": [
            {
              "id": "incident:INC-17",
              "title": "Payment requests timing out during peak traffic",
              "properties": {
                "id": "incident:INC-17",
                "title": "Payment requests timing out during peak traffic",
                "severity": "high",
                "summary": "Multiple payment API endpoints returned HTTP 504 Gateway Timeout errors during the 11:00\u201311:45 UTC burst window on May 10. Approximately 12% of transactions failed. Root cause traced to excessive database read latency under concurrent burst load in Payment Service. No data loss confirmed.",
                "started_at": "2026-05-10T11:00:00Z",
                "resolved_at": "2026-05-10T13:30:00Z",
                "affected_services": [
                  "service:payment-service"
                ],
                "related_issues": [
                  "issue:PAY-42"
                ],
                "url": "https://incidents.novapay.example/INC-17"
              },
              "service_id": "service:payment-service"
            }
          ],
          "source_ids": [
            "issue:PAY-42"
          ]
        }
      ],
      "indirect_impact": [
        {
          "service_id": "service:checkout-service",
          "service": {
            "id": "service:checkout-service",
            "name": "Checkout Service",
            "description": "Customer-facing checkout flow that orchestrates cart, pricing, and payment submission.",
            "criticality": "high",
            "technologies": [],
            "depends_on": [
              "service:payment-service"
            ]
          },
          "impact_depth": 2,
          "impact_type": "indirect",
          "path": [
            "tech:redis",
            "service:payment-service",
            "service:checkout-service"
          ],
          "path_edges": [
            {
              "source": "service:payment-service",
              "type": "USES",
              "target": "tech:redis"
            },
            {
              "source": "service:checkout-service",
              "type": "DEPENDS_ON",
              "target": "service:payment-service"
            }
          ],
          "owners": [
            {
              "id": "team:platform",
              "name": "Platform"
            }
          ],
          "related_issues": [],
          "related_incidents": [],
          "source_ids": []
        },
        {
          "service_id": "service:order-service",
          "service": {
            "id": "service:order-service",
            "name": "Order Service",
            "description": "Order management service that orchestrates checkout submissions and order lifecycle states.",
            "criticality": "medium",
            "technologies": [
              "tech:postgresql"
            ],
            "depends_on": [
              "service:checkout-service"
            ]
          },
          "impact_depth": 3,
          "impact_type": "indirect",
          "path": [
            "tech:redis",
            "service:payment-service",
            "service:checkout-service",
            "service:order-service"
          ],
          "path_edges": [
            {
              "source": "service:payment-service",
              "type": "USES",
              "target": "tech:redis"
            },
            {
              "source": "service:checkout-service",
              "type": "DEPENDS_ON",
              "target": "service:payment-service"
            },
            {
              "source": "service:order-service",
              "type": "DEPENDS_ON",
              "target": "service:checkout-service"
            }
          ],
          "owners": [
            {
              "id": "team:platform",
              "name": "Platform"
            }
          ],
          "related_issues": [],
          "related_incidents": [],
          "source_ids": []
        }
      ],
      "related_issues": [
        {
          "id": "issue:PAY-42",
          "title": "Reduce payment latency under burst traffic",
          "properties": {
            "id": "issue:PAY-42",
            "key": "PAY-42",
            "title": "Reduce payment latency under burst traffic",
            "description": "During the INC-17 incident on May 10, Payment Service experienced request timeouts due to excessive database read latency under concurrent burst load. Approximately 12% of payment transactions failed during the 11:00\u201311:45 UTC peak window.\n\nInvestigation shows that repeated reads of idempotency keys and payment configuration data from PostgreSQL account for 70% of query volume during bursts. These values change infrequently and are strong candidates for caching.\n\nProposed approach:\n- Introduce an in-memory or Redis-backed cache for hot-read paths\n- Measure cache-hit ratio and p99 latency improvement\n- Validate that cache invalidation does not introduce stale-payment risks\n\nAcceptance criteria:\n- p99 payment latency < 200ms during simulated burst traffic\n- Cache-hit ratio > 80% for idempotency key lookups\n- No increase in payment inconsistency errors",
            "status": "Done",
            "priority": "High",
            "created_at": "2026-05-11T09:00:00Z",
            "resolved_at": "2026-05-20T16:00:00Z",
            "assignee": "person:ravi",
            "affected_services": [
              "service:payment-service"
            ],
            "related_incidents": [
              "incident:INC-17"
            ],
            "url": "https://jira.novapay.example/browse/PAY-42"
          },
          "service_id": "service:payment-service"
        }
      ],
      "related_incidents": [
        {
          "id": "incident:INC-17",
          "title": "Payment requests timing out during peak traffic",
          "properties": {
            "id": "incident:INC-17",
            "title": "Payment requests timing out during peak traffic",
            "severity": "high",
            "summary": "Multiple payment API endpoints returned HTTP 504 Gateway Timeout errors during the 11:00\u201311:45 UTC burst window on May 10. Approximately 12% of transactions failed. Root cause traced to excessive database read latency under concurrent burst load in Payment Service. No data loss confirmed.",
            "started_at": "2026-05-10T11:00:00Z",
            "resolved_at": "2026-05-10T13:30:00Z",
            "affected_services": [
              "service:payment-service"
            ],
            "related_issues": [
              "issue:PAY-42"
            ],
            "url": "https://incidents.novapay.example/INC-17"
          },
          "service_id": "service:payment-service"
        }
      ],
      "support_status": "partially_supported",
      "max_depth": 3
    },
    "reviewers": [
      {
        "person": {
          "id": "person:ravi",
          "name": "Ravi Nair",
          "role": "Payments Engineer"
        },
        "evidence": [
          {
            "category": "commit_authorship",
            "entity_id": "commit:8fae2",
            "entity_type": "Commit",
            "path": [
              {
                "source": "person:ravi",
                "type": "AUTHORED",
                "target": "commit:8fae2"
              }
            ],
            "source_ids": [
              "commit:8fae2"
            ]
          },
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:ravi",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:ravi",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          },
          {
            "category": "issue_assignment",
            "entity_id": "issue:PAY-42",
            "entity_type": "Issue",
            "path": [
              {
                "source": "issue:PAY-42",
                "type": "ASSIGNED_TO",
                "target": "person:ravi"
              }
            ],
            "source_ids": [
              "issue:PAY-42"
            ]
          },
          {
            "category": "team_ownership",
            "entity_id": "service:payment-service",
            "entity_type": "Service",
            "path": [
              {
                "source": "person:ravi",
                "type": "MEMBER_OF",
                "target": "team:payments"
              },
              {
                "source": "team:payments",
                "type": "OWNS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          }
        ],
        "ownership": [
          {
            "category": "team_ownership",
            "entity_id": "service:payment-service",
            "entity_type": "Service",
            "path": [
              {
                "source": "person:ravi",
                "type": "MEMBER_OF",
                "target": "team:payments"
              },
              {
                "source": "team:payments",
                "type": "OWNS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          }
        ],
        "historical_contributions": [
          {
            "category": "commit_authorship",
            "entity_id": "commit:8fae2",
            "entity_type": "Commit",
            "path": [
              {
                "source": "person:ravi",
                "type": "AUTHORED",
                "target": "commit:8fae2"
              }
            ],
            "source_ids": [
              "commit:8fae2"
            ]
          },
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:ravi",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:ravi",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          },
          {
            "category": "issue_assignment",
            "entity_id": "issue:PAY-42",
            "entity_type": "Issue",
            "path": [
              {
                "source": "issue:PAY-42",
                "type": "ASSIGNED_TO",
                "target": "person:ravi"
              }
            ],
            "source_ids": [
              "issue:PAY-42"
            ]
          }
        ],
        "score": 16,
        "ranking_reasons": [
          "commit authorship: commit:8fae2",
          "decision participation: decision:D-007",
          "discussion contribution: message:payment-perf-7",
          "issue assignment: issue:PAY-42",
          "team ownership: service:payment-service"
        ],
        "ownership_classification": "team_membership_with_team_owned_service"
      },
      {
        "person": {
          "id": "person:alice",
          "name": "Alice Menon",
          "role": "Payments Tech Lead"
        },
        "evidence": [
          {
            "category": "decision_approval",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:alice",
                "type": "APPROVED",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:alice",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:alice",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          },
          {
            "category": "team_ownership",
            "entity_id": "service:payment-service",
            "entity_type": "Service",
            "path": [
              {
                "source": "person:alice",
                "type": "MEMBER_OF",
                "target": "team:payments"
              },
              {
                "source": "team:payments",
                "type": "OWNS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          }
        ],
        "ownership": [
          {
            "category": "team_ownership",
            "entity_id": "service:payment-service",
            "entity_type": "Service",
            "path": [
              {
                "source": "person:alice",
                "type": "MEMBER_OF",
                "target": "team:payments"
              },
              {
                "source": "team:payments",
                "type": "OWNS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          }
        ],
        "historical_contributions": [
          {
            "category": "decision_approval",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:alice",
                "type": "APPROVED",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:alice",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:alice",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          }
        ],
        "score": 14,
        "ranking_reasons": [
          "decision approval: decision:D-007",
          "decision participation: decision:D-007",
          "discussion contribution: message:payment-perf-7",
          "team ownership: service:payment-service"
        ],
        "ownership_classification": "team_membership_with_team_owned_service"
      },
      {
        "person": {
          "id": "person:maya",
          "name": "Maya Joseph",
          "role": "Platform Engineer"
        },
        "evidence": [
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:maya",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:maya",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          }
        ],
        "ownership": [],
        "historical_contributions": [
          {
            "category": "decision_participation",
            "entity_id": "decision:D-007",
            "entity_type": "Decision",
            "path": [
              {
                "source": "person:maya",
                "type": "PARTICIPATED_IN",
                "target": "decision:D-007"
              }
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ]
          },
          {
            "category": "discussion_contribution",
            "entity_id": "message:payment-perf-7",
            "entity_type": "Message",
            "path": [
              {
                "source": "person:maya",
                "type": "WROTE",
                "target": "message:payment-perf-7"
              }
            ],
            "source_ids": [
              "message:payment-perf-7"
            ]
          }
        ],
        "score": 5,
        "ranking_reasons": [
          "decision participation: decision:D-007",
          "discussion contribution: message:payment-perf-7"
        ],
        "ownership_classification": "no_current_ownership_evidence"
      }
    ],
    "risks": [
      {
        "classification": "KNOWN_FACT",
        "description": "Payment Service uses Redis.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "uncertainty": "Stored structural relationship; it does not establish guaranteed failure.",
        "affected_entity_ids": [
          "service:payment-service"
        ]
      },
      {
        "classification": "KNOWN_FACT",
        "description": "Checkout Service depends on Payment Service.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis",
              "service:checkout-service"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis",
                "service:checkout-service|DEPENDS_ON|service:payment-service"
              ]
            ]
          }
        ],
        "uncertainty": "Stored structural relationship; it does not establish guaranteed failure.",
        "affected_entity_ids": [
          "service:checkout-service"
        ]
      },
      {
        "classification": "KNOWN_FACT",
        "description": "Order Service depends on Checkout Service.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis",
              "service:checkout-service",
              "service:order-service"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service",
              "service:order-service|DEPENDS_ON|service:checkout-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis",
                "service:checkout-service|DEPENDS_ON|service:payment-service",
                "service:order-service|DEPENDS_ON|service:checkout-service"
              ]
            ]
          }
        ],
        "uncertainty": "Stored structural relationship; it does not establish guaranteed failure.",
        "affected_entity_ids": [
          "service:order-service"
        ]
      },
      {
        "classification": "INFERRED_RISK",
        "description": "Removing Redis may reintroduce the latency pressure described in the historical rationale under comparable traffic conditions.",
        "evidence": [
          {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "service:payment-service",
              "tech:redis",
              "incident:INC-17",
              "doc:ADR-7",
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7",
              "chunk:commit:8fae2:0",
              "chunk:doc:ADR-7:0",
              "chunk:issue:PAY-42:0",
              "chunk:message:payment-perf-7:0"
            ],
            "edge_ids": [
              "decision:D-007|AFFECTS|service:payment-service",
              "decision:D-007|INTRODUCES|tech:redis",
              "service:payment-service|USES|tech:redis",
              "incident:INC-17|LED_TO|issue:PAY-42",
              "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
              "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
              "decision:D-007|SUPPORTED_BY|issue:PAY-42",
              "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
              "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
              "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
              "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
              "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
            ],
            "source_ids": [
              "issue:PAY-42"
            ],
            "relationship_paths": [
              [
                "decision:D-007|AFFECTS|service:payment-service"
              ],
              [
                "decision:D-007|INTRODUCES|tech:redis"
              ],
              [
                "service:payment-service|USES|tech:redis"
              ],
              [
                "incident:INC-17|LED_TO|issue:PAY-42"
              ],
              [
                "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
              ],
              [
                "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
              ],
              [
                "decision:D-007|SUPPORTED_BY|issue:PAY-42"
              ],
              [
                "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
              ],
              [
                "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2"
              ],
              [
                "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7"
              ],
              [
                "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42"
              ],
              [
                "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
              ]
            ]
          },
          {
            "tool": "decision_trace",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "uncertainty": "Inference from historical evidence, not a benchmark or prediction of the proposed implementation.",
        "affected_entity_ids": [
          "service:payment-service"
        ]
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Validate Payment Service's cache-removal behavior before rollout.",
        "evidence": [
          {
            "tool": "decision_trace",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "uncertainty": "Suggested engineering action; no test has been performed by this analysis.",
        "affected_entity_ids": [
          "service:payment-service"
        ]
      }
    ],
    "validation_steps": [
      {
        "classification": "RECOMMENDATION",
        "description": "Test the returned dependency path to Payment Service under the proposed cache removal; do not assume failure propagation.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Test the returned dependency path to Checkout Service under the proposed cache removal; do not assume failure propagation.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis",
              "service:checkout-service"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis",
                "service:checkout-service|DEPENDS_ON|service:payment-service"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Test the returned dependency path to Order Service under the proposed cache removal; do not assume failure propagation.",
        "evidence": [
          {
            "tool": "impact_analysis",
            "node_ids": [
              "service:payment-service",
              "tech:redis",
              "service:checkout-service",
              "service:order-service"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service",
              "service:order-service|DEPENDS_ON|service:checkout-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis",
                "service:checkout-service|DEPENDS_ON|service:payment-service",
                "service:order-service|DEPENDS_ON|service:checkout-service"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Request review from the evidence-ranked contributors and verify current ownership and approval responsibilities. Team membership is not personal ownership.",
        "evidence": [
          {
            "tool": "find_expert",
            "node_ids": [
              "service:payment-service",
              "commit:8fae2",
              "decision:D-007",
              "doc:ADR-7",
              "doc:architecture-overview",
              "doc:runbook-payment-latency",
              "incident:INC-17",
              "issue:PAY-42",
              "tech:postgresql",
              "tech:redis",
              "message:payment-perf-7",
              "service:order-service",
              "person:alice",
              "person:maya",
              "person:ravi",
              "team:payments",
              "chunk:commit:8fae2:0",
              "chunk:issue:PAY-42:0",
              "chunk:message:payment-perf-7:0"
            ],
            "edge_ids": [
              "commit:8fae2|CHANGES|service:payment-service",
              "decision:D-007|AFFECTS|service:payment-service",
              "doc:ADR-7|DESCRIBES|service:payment-service",
              "doc:architecture-overview|DESCRIBES|service:payment-service",
              "doc:runbook-payment-latency|DESCRIBES|service:payment-service",
              "incident:INC-17|AFFECTS|service:payment-service",
              "issue:PAY-42|AFFECTS|service:payment-service",
              "service:payment-service|USES|tech:postgresql",
              "service:payment-service|USES|tech:redis",
              "commit:8fae2|ADDRESSES|issue:PAY-42",
              "commit:8fae2|IMPLEMENTS_DECISION|decision:D-007",
              "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
              "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
              "decision:D-007|INTRODUCES|tech:redis",
              "decision:D-007|SUPPORTED_BY|issue:PAY-42",
              "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
              "service:order-service|USES|tech:postgresql",
              "person:alice|APPROVED|decision:D-007",
              "person:alice|PARTICIPATED_IN|decision:D-007",
              "person:alice|WROTE|message:payment-perf-7",
              "person:maya|PARTICIPATED_IN|decision:D-007",
              "person:maya|WROTE|message:payment-perf-7",
              "person:ravi|AUTHORED|commit:8fae2",
              "person:ravi|PARTICIPATED_IN|decision:D-007",
              "person:ravi|WROTE|message:payment-perf-7",
              "issue:PAY-42|ASSIGNED_TO|person:ravi",
              "person:alice|MEMBER_OF|team:payments",
              "team:payments|OWNS|service:payment-service",
              "person:ravi|MEMBER_OF|team:payments",
              "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
              "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
              "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
            ],
            "source_ids": [
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7"
            ],
            "relationship_paths": [
              [
                "person:ravi|AUTHORED|commit:8fae2"
              ],
              [
                "person:ravi|PARTICIPATED_IN|decision:D-007"
              ],
              [
                "person:ravi|WROTE|message:payment-perf-7"
              ],
              [
                "issue:PAY-42|ASSIGNED_TO|person:ravi"
              ],
              [
                "person:ravi|MEMBER_OF|team:payments",
                "team:payments|OWNS|service:payment-service"
              ],
              [
                "person:alice|APPROVED|decision:D-007"
              ],
              [
                "person:alice|PARTICIPATED_IN|decision:D-007"
              ],
              [
                "person:alice|WROTE|message:payment-perf-7"
              ],
              [
                "person:alice|MEMBER_OF|team:payments",
                "team:payments|OWNS|service:payment-service"
              ],
              [
                "person:maya|PARTICIPATED_IN|decision:D-007"
              ],
              [
                "person:maya|WROTE|message:payment-perf-7"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "If the change is approved and implemented, review the returned service-linked documents and record the new architecture decision.",
        "evidence": [
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:ADR-7",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:ADR-7|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:ADR-7|DESCRIBES|service:payment-service"
              ]
            ]
          },
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:architecture-overview",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:architecture-overview|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:architecture-overview|DESCRIBES|service:payment-service"
              ]
            ]
          },
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:runbook-payment-latency",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:runbook-payment-latency|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:runbook-payment-latency|DESCRIBES|service:payment-service"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Load-test Payment Service under comparable burst traffic and compare latency before approving cache removal.",
        "evidence": [
          {
            "tool": "decision_trace",
            "node_ids": [
              "decision:D-007",
              "service:payment-service",
              "tech:redis",
              "incident:INC-17",
              "doc:ADR-7",
              "commit:8fae2",
              "issue:PAY-42",
              "message:payment-perf-7",
              "chunk:commit:8fae2:0",
              "chunk:doc:ADR-7:0",
              "chunk:issue:PAY-42:0",
              "chunk:message:payment-perf-7:0"
            ],
            "edge_ids": [
              "decision:D-007|AFFECTS|service:payment-service",
              "decision:D-007|INTRODUCES|tech:redis",
              "service:payment-service|USES|tech:redis",
              "incident:INC-17|LED_TO|issue:PAY-42",
              "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
              "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
              "decision:D-007|SUPPORTED_BY|issue:PAY-42",
              "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
              "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
              "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
              "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
              "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
            ],
            "source_ids": [
              "issue:PAY-42"
            ],
            "relationship_paths": [
              [
                "decision:D-007|AFFECTS|service:payment-service"
              ],
              [
                "decision:D-007|INTRODUCES|tech:redis"
              ],
              [
                "service:payment-service|USES|tech:redis"
              ],
              [
                "incident:INC-17|LED_TO|issue:PAY-42"
              ],
              [
                "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
              ],
              [
                "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
              ],
              [
                "decision:D-007|SUPPORTED_BY|issue:PAY-42"
              ],
              [
                "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
              ],
              [
                "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2"
              ],
              [
                "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7"
              ],
              [
                "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42"
              ],
              [
                "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
              ]
            ]
          },
          {
            "tool": "decision_trace",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "performed": false
      },
      {
        "classification": "RECOMMENDATION",
        "description": "Verify Payment Service's behavior without Redis before rollout; this analysis does not execute the change or run tests.",
        "evidence": [
          {
            "tool": "decision_trace",
            "node_ids": [
              "service:payment-service",
              "tech:redis"
            ],
            "edge_ids": [
              "service:payment-service|USES|tech:redis"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "service:payment-service|USES|tech:redis"
              ]
            ]
          }
        ],
        "performed": false
      }
    ],
    "current_freshness_findings": [
      {
        "document": {
          "id": "doc:architecture-overview",
          "type": "Document",
          "label": "NovaPay Core Architecture Overview",
          "properties": {
            "id": "doc:architecture-overview",
            "title": "NovaPay Core Architecture Overview",
            "doc_type": "architecture",
            "content": "# NovaPay Core Architecture Overview\n\n**Document ID:** doc:architecture-overview\n**Version:** 2.4\n**Last Updated:** 2026-05-01\n**Author:** Platform & Architecture Working Group\n**Target Service:** service:payment-service\n\n## 1. System Overview\n\nNovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.\n\n### Core Components\n\n- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.\n- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.\n- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.\n\n## 2. Transaction Flow & Data Access\n\n1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.\n2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.\n3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.\n4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.\n\n## 3. Storage and Scaling Constraints\n\nAll configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.\n",
            "updated_at": "2026-05-01T12:00:00Z",
            "url": "https://docs.novapay.example/architecture/overview",
            "describes": [
              "service:payment-service"
            ]
          }
        },
        "document_id": "doc:architecture-overview",
        "updated_at": "2026-05-01T12:00:00Z",
        "affected_entity_id": "service:payment-service",
        "document_path": [
          {
            "source": "doc:architecture-overview",
            "type": "DESCRIBES",
            "target": "service:payment-service"
          }
        ],
        "triggers": [
          {
            "type": "incident",
            "id": "incident:INC-17",
            "timestamp": "2026-05-10T11:00:00Z",
            "affected_entity_id": "service:payment-service",
            "path": [
              {
                "source": "incident:INC-17",
                "type": "AFFECTS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          },
          {
            "type": "decision",
            "id": "decision:D-007",
            "timestamp": "2026-05-18T14:30:00Z",
            "affected_entity_id": "service:payment-service",
            "path": [
              {
                "source": "decision:D-007",
                "type": "AFFECTS",
                "target": "service:payment-service"
              }
            ],
            "source_ids": []
          },
          {
            "type": "commit",
            "id": "commit:8fae2",
            "timestamp": "2026-05-19T10:15:00Z",
            "affected_entity_id": "service:payment-service",
            "path": [
              {
                "source": "commit:8fae2",
                "type": "CHANGES",
                "target": "service:payment-service"
              }
            ],
            "source_ids": [
              "commit:8fae2"
            ]
          }
        ],
        "reason": "Later graph-linked changes affect the same service; review may be warranted.",
        "source_ids": [
          "doc:architecture-overview"
        ]
      }
    ],
    "documents_to_review_if_change_proceeds": [
      {
        "document": {
          "id": "doc:ADR-7",
          "type": "Document",
          "label": "ADR-7: Redis Caching for Payment Service",
          "properties": {
            "id": "doc:ADR-7",
            "title": "ADR-7: Redis Caching for Payment Service",
            "doc_type": "ADR",
            "content": "# ADR-7: Redis Caching for Payment Service\n\n**Status:** Accepted  \n**Date:** 2026-05-20  \n**Decision:** D-007  \n**Author:** Alice Menon  \n\n## Context\n\nDuring incident INC-17 on May 10, 2026, Payment Service experienced request timeouts under burst traffic. Investigation via issue PAY-42 revealed that 70% of database query volume during peak windows consisted of repeated reads of idempotency keys and payment configuration data from PostgreSQL. These values change infrequently and are strong candidates for caching.\n\nThe payments engineering team discussed the problem in the #payments-engineering Slack channel (thread: payment-perf-2026-05). Benchmarks showed that placing Redis in front of PostgreSQL for these read paths reduced p99 latency from 380ms to 45ms at 500 concurrent requests, with a cache-hit ratio of 87%.\n\n## Decision\n\nIntroduce Redis-backed caching in Payment Service for:\n\n1. **Idempotency key lookups** \u2014 cached with a 60-second TTL and explicit invalidation on key creation/expiry.\n2. **Payment configuration reads** \u2014 cached with a 60-second TTL and explicit invalidation on configuration writes.\n\nRedis was selected because:\n\n- It is already deployed in the NovaPay infrastructure stack for session management (confirmed by Platform Engineering).\n- No new provisioning or operational overhead is required.\n- Its sub-millisecond read latency meets the p99 < 200ms target for payment operations.\n- The team has operational experience with Redis in production.\n\n## Consequences\n\n- **Positive:** Estimated 60% reduction in direct PostgreSQL queries during burst traffic. p99 latency target of < 200ms is achievable based on benchmarks.\n- **Positive:** Reuse of existing Redis infrastructure reduces deployment risk and cost.\n- **Risk:** Cache invalidation bugs could serve stale idempotency keys, potentially allowing duplicate payment processing. Mitigated by short TTLs and explicit invalidation on writes.\n- **Risk:** Redis availability becomes a dependency for optimal Payment Service performance. Mitigated by fallback to direct PostgreSQL reads if the Redis connection is unavailable.\n\n## Implementation\n\n- **Commit:** 8fae2 in `novapay/payments-api`\n- **Issue:** PAY-42\n- **Service affected:** Payment Service\n- **Technology introduced:** Redis\n\n## Participants\n\n- Alice Menon \u2014 Payments Tech Lead (approver)\n- Ravi Nair \u2014 Payments Engineer (implementer)\n- Maya Joseph \u2014 Platform Engineer (infrastructure review)\n",
            "updated_at": "2026-05-20T10:00:00Z",
            "url": "https://docs.novapay.example/adrs/ADR-7",
            "describes": [
              "service:payment-service"
            ]
          }
        },
        "condition": "if_change_approved_and_implemented",
        "reason": "Review this service-linked document if Redis removal is approved and implemented; this recommendation does not establish current staleness.",
        "evidence": [
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:ADR-7",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:ADR-7|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:ADR-7|DESCRIBES|service:payment-service"
              ]
            ]
          }
        ]
      },
      {
        "document": {
          "id": "doc:architecture-overview",
          "type": "Document",
          "label": "NovaPay Core Architecture Overview",
          "properties": {
            "id": "doc:architecture-overview",
            "title": "NovaPay Core Architecture Overview",
            "doc_type": "architecture",
            "content": "# NovaPay Core Architecture Overview\n\n**Document ID:** doc:architecture-overview\n**Version:** 2.4\n**Last Updated:** 2026-05-01\n**Author:** Platform & Architecture Working Group\n**Target Service:** service:payment-service\n\n## 1. System Overview\n\nNovaPay provides a distributed transaction processing platform designed for high-availability payment routing, card authorization, and merchant settlement.\n\n### Core Components\n\n- **Checkout Service (`service:checkout-service`)**: Customer-facing web checkout orchestration layer.\n- **Payment Service (`service:payment-service`)**: Core transaction authorization and processing backend.\n- **Database Layer**: Primary PostgreSQL cluster serving relational transaction records and merchant account configurations.\n\n## 2. Transaction Flow & Data Access\n\n1. Checkout Service submits payment requests to Payment Service over internal gRPC/REST APIs.\n2. Payment Service validates transaction requests against merchant configuration tables in PostgreSQL.\n3. Idempotency keys are queried directly from the `payment_idempotency_records` table in PostgreSQL before gateway dispatch.\n4. Successful authorizations are committed to PostgreSQL, and status receipts are returned downstream to Checkout Service.\n\n## 3. Storage and Scaling Constraints\n\nAll configuration reads, merchant rules, and idempotency lookups are executed as synchronous queries against the PostgreSQL primary database. Under elevated traffic surges, database connection pools must be scaled vertically to avoid queue saturation.\n",
            "updated_at": "2026-05-01T12:00:00Z",
            "url": "https://docs.novapay.example/architecture/overview",
            "describes": [
              "service:payment-service"
            ]
          }
        },
        "condition": "if_change_approved_and_implemented",
        "reason": "Review this service-linked document if Redis removal is approved and implemented; this recommendation does not establish current staleness.",
        "evidence": [
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:architecture-overview",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:architecture-overview|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:architecture-overview|DESCRIBES|service:payment-service"
              ]
            ]
          }
        ]
      },
      {
        "document": {
          "id": "doc:runbook-payment-latency",
          "type": "Document",
          "label": "Runbook: Payment Service Latency & Degradation",
          "properties": {
            "id": "doc:runbook-payment-latency",
            "title": "Runbook: Payment Service Latency & Degradation",
            "doc_type": "runbook",
            "content": "# Runbook: Payment Service Latency & Degradation\n\n**Document ID:** doc:runbook-payment-latency\n**Version:** 1.2\n**Last Updated:** 2026-05-22\n**Target Service:** service:payment-service\n**Related Incident:** incident:INC-17\n**Architecture Reference:** doc:ADR-7\n\n## 1. Trigger Conditions\n\nAlert `PaymentServiceP99LatencyHigh` fires when p99 API response latency exceeds 250ms for 3 consecutive minutes, or when HTTP 504 Gateway Timeout responses surpass 1% of total transaction volume.\n\n## 2. Diagnostic Steps\n\n1. **Verify Redis Cache Cluster Health**:\n   - Check Redis cluster CPU utilization and memory fragmentation via Grafana dashboard `Redis / Payments Cache`.\n   - Verify cache-hit ratio is maintained above 80% (target nominal: 87%).\n   - If cache-hit ratio drops below 50%, inspect Payment Service logs for Redis connection pool exhaustion or network partition.\n\n2. **Check Database Query Queue**:\n   - Query pg_stat_activity on PostgreSQL primary to identify lock contention on transaction tables.\n   - If Redis is healthy, database read pressure should remain below 40% of peak capacity.\n\n3. **Cache Invalidation & Failover**:\n   - In the event of primary Redis instance failure, the sentinel automatically promotes the replica within 15 seconds.\n   - Payment Service falls back to direct PostgreSQL reads if Redis is completely unreachable, operating in degraded mode.\n",
            "updated_at": "2026-05-22T10:00:00Z",
            "url": "https://docs.novapay.example/runbooks/payment-latency",
            "describes": [
              "service:payment-service"
            ]
          }
        },
        "condition": "if_change_approved_and_implemented",
        "reason": "Review this service-linked document if Redis removal is approved and implemented; this recommendation does not establish current staleness.",
        "evidence": [
          {
            "tool": "find_stale_knowledge",
            "node_ids": [
              "doc:runbook-payment-latency",
              "service:payment-service"
            ],
            "edge_ids": [
              "doc:runbook-payment-latency|DESCRIBES|service:payment-service"
            ],
            "source_ids": [],
            "relationship_paths": [
              [
                "doc:runbook-payment-latency|DESCRIBES|service:payment-service"
              ]
            ]
          }
        ]
      }
    ],
    "tool_support": {
      "decision_trace": {
        "support_status": "supported",
        "state": "validated",
        "evidence": {
          "tool": "decision_trace",
          "node_ids": [
            "decision:D-007",
            "service:payment-service",
            "tech:redis",
            "incident:INC-17",
            "doc:ADR-7",
            "commit:8fae2",
            "issue:PAY-42",
            "message:payment-perf-7",
            "chunk:commit:8fae2:0",
            "chunk:doc:ADR-7:0",
            "chunk:issue:PAY-42:0",
            "chunk:message:payment-perf-7:0"
          ],
          "edge_ids": [
            "decision:D-007|AFFECTS|service:payment-service",
            "decision:D-007|INTRODUCES|tech:redis",
            "service:payment-service|USES|tech:redis",
            "incident:INC-17|LED_TO|issue:PAY-42",
            "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
            "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
            "decision:D-007|SUPPORTED_BY|issue:PAY-42",
            "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
            "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
            "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7",
            "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
            "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
          ],
          "source_ids": [
            "commit:8fae2",
            "doc:ADR-7",
            "issue:PAY-42",
            "message:payment-perf-7"
          ],
          "relationship_paths": [
            [
              "decision:D-007|AFFECTS|service:payment-service"
            ],
            [
              "decision:D-007|INTRODUCES|tech:redis"
            ],
            [
              "service:payment-service|USES|tech:redis"
            ],
            [
              "incident:INC-17|LED_TO|issue:PAY-42"
            ],
            [
              "decision:D-007|DOCUMENTED_IN|doc:ADR-7"
            ],
            [
              "decision:D-007|IMPLEMENTED_BY|commit:8fae2"
            ],
            [
              "decision:D-007|SUPPORTED_BY|issue:PAY-42"
            ],
            [
              "decision:D-007|SUPPORTED_BY|message:payment-perf-7"
            ],
            [
              "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2"
            ],
            [
              "chunk:doc:ADR-7:0|FROM_DOCUMENT|doc:ADR-7"
            ],
            [
              "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42"
            ],
            [
              "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
            ]
          ]
        }
      },
      "impact_analysis": {
        "support_status": "partially_supported",
        "state": "validated",
        "evidence": {
          "tool": "impact_analysis",
          "node_ids": [
            "tech:redis",
            "service:payment-service",
            "service:checkout-service",
            "service:order-service",
            "team:payments",
            "issue:PAY-42",
            "incident:INC-17",
            "team:platform",
            "chunk:issue:PAY-42:0"
          ],
          "edge_ids": [
            "service:payment-service|USES|tech:redis",
            "service:checkout-service|DEPENDS_ON|service:payment-service",
            "service:order-service|DEPENDS_ON|service:checkout-service",
            "team:payments|OWNS|service:payment-service",
            "issue:PAY-42|AFFECTS|service:payment-service",
            "incident:INC-17|AFFECTS|service:payment-service",
            "incident:INC-17|LED_TO|issue:PAY-42",
            "team:platform|OWNS|service:checkout-service",
            "team:platform|OWNS|service:order-service",
            "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42"
          ],
          "source_ids": [
            "issue:PAY-42"
          ],
          "relationship_paths": [
            [
              "service:payment-service|USES|tech:redis"
            ],
            [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service"
            ],
            [
              "service:payment-service|USES|tech:redis",
              "service:checkout-service|DEPENDS_ON|service:payment-service",
              "service:order-service|DEPENDS_ON|service:checkout-service"
            ]
          ]
        }
      },
      "find_expert": {
        "support_status": "supported",
        "state": "validated",
        "evidence": {
          "tool": "find_expert",
          "node_ids": [
            "service:payment-service",
            "commit:8fae2",
            "decision:D-007",
            "doc:ADR-7",
            "doc:architecture-overview",
            "doc:runbook-payment-latency",
            "incident:INC-17",
            "issue:PAY-42",
            "tech:postgresql",
            "tech:redis",
            "message:payment-perf-7",
            "service:order-service",
            "person:alice",
            "person:maya",
            "person:ravi",
            "team:payments",
            "chunk:commit:8fae2:0",
            "chunk:issue:PAY-42:0",
            "chunk:message:payment-perf-7:0"
          ],
          "edge_ids": [
            "commit:8fae2|CHANGES|service:payment-service",
            "decision:D-007|AFFECTS|service:payment-service",
            "doc:ADR-7|DESCRIBES|service:payment-service",
            "doc:architecture-overview|DESCRIBES|service:payment-service",
            "doc:runbook-payment-latency|DESCRIBES|service:payment-service",
            "incident:INC-17|AFFECTS|service:payment-service",
            "issue:PAY-42|AFFECTS|service:payment-service",
            "service:payment-service|USES|tech:postgresql",
            "service:payment-service|USES|tech:redis",
            "commit:8fae2|ADDRESSES|issue:PAY-42",
            "commit:8fae2|IMPLEMENTS_DECISION|decision:D-007",
            "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
            "decision:D-007|IMPLEMENTED_BY|commit:8fae2",
            "decision:D-007|INTRODUCES|tech:redis",
            "decision:D-007|SUPPORTED_BY|issue:PAY-42",
            "decision:D-007|SUPPORTED_BY|message:payment-perf-7",
            "service:order-service|USES|tech:postgresql",
            "person:alice|APPROVED|decision:D-007",
            "person:alice|PARTICIPATED_IN|decision:D-007",
            "person:alice|WROTE|message:payment-perf-7",
            "person:maya|PARTICIPATED_IN|decision:D-007",
            "person:maya|WROTE|message:payment-perf-7",
            "person:ravi|AUTHORED|commit:8fae2",
            "person:ravi|PARTICIPATED_IN|decision:D-007",
            "person:ravi|WROTE|message:payment-perf-7",
            "issue:PAY-42|ASSIGNED_TO|person:ravi",
            "person:alice|MEMBER_OF|team:payments",
            "team:payments|OWNS|service:payment-service",
            "person:ravi|MEMBER_OF|team:payments",
            "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
            "chunk:issue:PAY-42:0|FROM_ISSUE|issue:PAY-42",
            "chunk:message:payment-perf-7:0|FROM_MESSAGE|message:payment-perf-7"
          ],
          "source_ids": [
            "commit:8fae2",
            "issue:PAY-42",
            "message:payment-perf-7"
          ],
          "relationship_paths": [
            [
              "person:ravi|AUTHORED|commit:8fae2"
            ],
            [
              "person:ravi|PARTICIPATED_IN|decision:D-007"
            ],
            [
              "person:ravi|WROTE|message:payment-perf-7"
            ],
            [
              "issue:PAY-42|ASSIGNED_TO|person:ravi"
            ],
            [
              "person:ravi|MEMBER_OF|team:payments",
              "team:payments|OWNS|service:payment-service"
            ],
            [
              "person:alice|APPROVED|decision:D-007"
            ],
            [
              "person:alice|PARTICIPATED_IN|decision:D-007"
            ],
            [
              "person:alice|WROTE|message:payment-perf-7"
            ],
            [
              "person:alice|MEMBER_OF|team:payments",
              "team:payments|OWNS|service:payment-service"
            ],
            [
              "person:maya|PARTICIPATED_IN|decision:D-007"
            ],
            [
              "person:maya|WROTE|message:payment-perf-7"
            ]
          ]
        }
      },
      "find_stale_knowledge": {
        "support_status": "supported",
        "state": "validated",
        "evidence": {
          "tool": "find_stale_knowledge",
          "node_ids": [
            "service:payment-service",
            "doc:ADR-7",
            "doc:architecture-overview",
            "doc:runbook-payment-latency",
            "decision:D-007",
            "commit:8fae2",
            "incident:INC-17",
            "chunk:commit:8fae2:0",
            "chunk:doc:architecture-overview:0"
          ],
          "edge_ids": [
            "doc:ADR-7|DESCRIBES|service:payment-service",
            "doc:architecture-overview|DESCRIBES|service:payment-service",
            "doc:runbook-payment-latency|DESCRIBES|service:payment-service",
            "decision:D-007|DOCUMENTED_IN|doc:ADR-7",
            "decision:D-007|AFFECTS|service:payment-service",
            "commit:8fae2|CHANGES|service:payment-service",
            "incident:INC-17|AFFECTS|service:payment-service",
            "chunk:commit:8fae2:0|FROM_COMMIT|commit:8fae2",
            "chunk:doc:architecture-overview:0|FROM_DOCUMENT|doc:architecture-overview"
          ],
          "source_ids": [
            "commit:8fae2",
            "doc:architecture-overview"
          ],
          "relationship_paths": [
            [
              "doc:architecture-overview|DESCRIBES|service:payment-service"
            ],
            [
              "incident:INC-17|AFFECTS|service:payment-service"
            ],
            [
              "decision:D-007|AFFECTS|service:payment-service"
            ],
            [
              "commit:8fae2|CHANGES|service:payment-service"
            ]
          ]
        }
      }
    },
    "limitations": [
      "Current graph relationships and potential downstream impact: Impact is based on bounded graph structure; textual evidence of propagation is not established."
    ]
  }
};
