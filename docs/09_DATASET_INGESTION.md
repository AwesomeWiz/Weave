# Weave — Dataset and Ingestion Design

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

## 1. Goal

Create a small synthetic company dataset that demonstrates connected organizational knowledge reliably and legally.

The dataset is not meant to simulate a whole corporation. It is designed to create believable evidence chains for the four core Weave capabilities.

## 2. Synthetic company

**Company:** NovaPay  
**Domain:** payment software

### Teams

- Payments
- Platform
- Identity

### Services

- Payment Service
- Checkout Service
- Auth Service
- Notification Service

### Technologies

- Redis
- PostgreSQL
- Kafka
- OAuth/OIDC

### Repositories

- `novapay/payments-api`
- `novapay/checkout-web`
- `novapay/auth-service`

## 3. Minimum dataset size

Target:

- 8 people
- 3 teams
- 4 services
- 3 repositories
- 15 commits
- 12 issues
- 24 chat messages / thread records
- 8 documents
- 6 decisions
- 3 incidents
- 4 technologies

Do not inflate counts unless extra records improve a demo query.

## 4. Canonical records

### Primary incident

`INC-17` — Payment requests timing out during peak traffic.

### Primary issue

`PAY-42` — Reduce payment latency under burst traffic.

### Primary decision

`D-007` — Introduce Redis caching for selected payment reads/idempotency data.

### Primary document

`ADR-7` — Redis caching decision.

### Primary implementation commit

`8fae2...` — Introduce Redis-backed cache in Payment Service.

### Primary people

- Alice Menon — Payments tech lead
- Ravi Nair — Payments engineer
- Maya Joseph — Platform engineer
- Neeraj Shah — SRE

Use entirely fictional identities or obviously synthetic names/handles.

## 5. Recommended file layout

```text
data/novapay/
├── people.json
├── teams.json
├── services.json
├── technologies.json
├── github/
│   ├── repositories.json
│   └── commits.json
├── jira/
│   └── issues.json
├── slack/
│   └── messages.json
├── incidents.json
├── decisions.json
└── docs/
    ├── ADR-7.md
    ├── architecture-overview.md
    ├── payment-service.md
    └── runbook-payment-latency.md
```

## 6. Normalized record model

Each input record should have:

- `id`
- `source`
- `entity_type`
- source-specific fields
- timestamp when applicable
- URLs that are either synthetic placeholders or safe public links

Example normalized issue:

```json
{
  "id": "issue:PAY-42",
  "source": "jira",
  "entity_type": "Issue",
  "key": "PAY-42",
  "title": "Reduce payment latency under burst traffic",
  "status": "Done",
  "priority": "High",
  "created_at": "2026-05-11T09:00:00Z",
  "resolved_at": "2026-05-20T16:00:00Z",
  "affected_services": ["service:payment-service"],
  "related_incidents": ["incident:INC-17"]
}
```

## 7. Decision record

Because Decision is central to Weave, make it explicit in the dataset.

```json
{
  "id": "decision:D-007",
  "title": "Introduce Redis caching",
  "summary": "Adopt Redis caching to reduce repeated read latency during payment bursts.",
  "status": "accepted",
  "decided_at": "2026-05-18T14:30:00Z",
  "category": "architecture",
  "affects": ["service:payment-service"],
  "introduces": ["tech:redis"],
  "participants": ["person:alice", "person:ravi", "person:maya"],
  "approved_by": ["person:alice"],
  "supported_by": ["issue:PAY-42", "message:payment-perf-7"],
  "implemented_by": ["commit:8fae2"],
  "documented_in": ["doc:ADR-7"]
}
```

## 8. Dates for freshness demo

Create deliberate chronology:

- Architecture Overview updated: May 1
- Incident INC-17: May 10
- PAY-42 opened: May 11
- Redis discussion: May 15–17
- D-007 accepted: May 18
- Redis commit: May 19
- ADR-7 updated: May 20

Result:

- `Architecture Overview` is a stale candidate
- `ADR-7` is current for the Redis decision

This makes the freshness feature easy to explain.

## 9. Chunking

Chunk only text-bearing entities that benefit from semantic retrieval:

- documents
- longer issue descriptions/comments
- chat threads
- commit message/body where useful

Suggested chunk size:

- roughly 300–600 tokens
- small overlap only for longer documents

The synthetic corpus is small; do not over-engineer chunking.

Each Chunk must retain:

- `source_id`
- `source_type`
- `chunk_index`
- original title/identifier
- text
- timestamp if relevant

## 10. Entity resolution

Synthetic data should use canonical IDs directly, making exact resolution possible.

Also maintain alias maps for query resolution:

```json
{
  "payment service": "service:payment-service",
  "payments api": "service:payment-service",
  "redis cache": "tech:redis"
}
```

Use semantic resolution only as a fallback.

## 11. Ingestion algorithm

For each record:

1. validate schema
2. normalize ID
3. `MERGE` entity node by canonical ID
4. update mutable properties
5. create relationships using canonical IDs
6. create Chunk nodes for retrievable text
7. generate/store embeddings
8. record ingestion stats/errors

Re-running ingestion should not create duplicates.

## 12. Provenance

Every source-bearing fact should preserve where it came from.

Examples:

- decision supported by PAY-42
- decision discussed in a Slack message/thread
- decision documented by ADR-7
- decision implemented by commit `8fae2`

The UI should show human-readable source titles plus synthetic URLs/IDs.

## 13. Incremental update demo (optional)

If core features are stable, demonstrate one update:

1. seed graph
2. show old document flagged stale
3. ingest an updated architecture document with a later timestamp
4. rerun freshness
5. document is no longer flagged for that reason

This directly demonstrates “keeping knowledge current as things change.”

## 14. Data quality checks

Before demo:

- no orphan Decision nodes
- every core Service has an owner/team
- every core source has a stable ID
- no duplicate Person entities
- every primary decision has at least two evidence sources
- timestamps form the intended chronology
- all graph references resolve
- no private or real employee data is included

## 15. What not to ingest

Do not use:

- private Slack exports
- private GitHub organization data
- login-protected Jira/Confluence exports
- personal email/chat data
- customer PII

The synthetic dataset is sufficient to prove the product.

---

## Before/after demo fixtures

- **Causality:** seed `Checkout Service -[:DEPENDS_ON]-> Payment Service`. Save the expected impact result; remove the edge with a controlled demo mutation and confirm the result changes. Re-seed immediately.
- **Freshness:** `Architecture Overview` initially updated May 1; accepted D-007 May 18; architecture-changing commit May 19. Supply a revised Architecture Overview dated after May 19 with updated Redis description. Upsert by the same canonical ID, preserving source provenance; assert no duplicate Document nodes.
- **Negative test:** unsupported MongoDB/fraud-service question returns insufficient evidence.
- **Action payload (optional):** expected impacted service IDs, owner IDs, and source IDs for a review-task preview. Do not embed fabricated external issue URLs.
