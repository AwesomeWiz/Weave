# Weave — Knowledge Graph Design

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Database:** FalkorDB  
**Purpose:** Represent company knowledge as connected evidence for agent reasoning.

## 1. Graph design principle

Every node or relationship should help answer at least one of these questions:

- Why did this happen?
- Who knows or owns this?
- What depends on this?
- What evidence supports this?
- What changed after this information was written?

If an entity does not contribute to those questions, it is probably not needed during the hackathon.

## 2. Core ontology

### Person

Represents an employee/contributor.

Key properties:

- `id`
- `name`
- `email_alias` (synthetic/non-sensitive)
- `role`
- `active`

### Team

Properties:

- `id`
- `name`

### Project

Properties:

- `id`
- `name`
- `description`

### Service

Represents a deployable or logical system component.

Properties:

- `id`
- `name`
- `criticality`
- `description`

### Repository

Properties:

- `id`
- `name`
- `url`
- `default_branch`

### Commit

Properties:

- `id` / SHA
- `message`
- `timestamp`
- `url`
- `architecture_change` (boolean)

### Issue

Represents ticket/task/bug/story.

Properties:

- `id`
- `key`
- `title`
- `status`
- `priority`
- `created_at`
- `resolved_at`
- `url`

### Message

Represents an individual message or compacted thread item.

Properties:

- `id`
- `text`
- `timestamp`
- `channel`
- `thread_id`
- `url`

### Document

Properties:

- `id`
- `title`
- `doc_type` (`ADR`, `architecture`, `runbook`, `general`)
- `updated_at`
- `url`

### Decision

**Decision is a first-class entity and is central to Weave.**

Properties:

- `id`
- `title`
- `summary`
- `status` (`proposed`, `accepted`, `superseded`)
- `decided_at`
- `category`

### Technology

Examples: Redis, PostgreSQL, Kafka.

Properties:

- `id`
- `name`
- `category`

### Incident

Properties:

- `id`
- `title`
- `severity`
- `started_at`
- `resolved_at`
- `summary`

### Chunk

Represents retrievable text evidence.

Properties:

- `id`
- `text`
- `source_type`
- `source_id`
- `chunk_index`
- `embedding` (when enabled)

## 3. Core relationships

### Organizational

- `(Person)-[:MEMBER_OF]->(Team)`
- `(Team)-[:OWNS]->(Service)`
- `(Person)-[:OWNS]->(Service)` where individual ownership is meaningful
- `(Project)-[:HAS_SERVICE]->(Service)`

### Code

- `(Repository)-[:IMPLEMENTS]->(Service)`
- `(Person)-[:AUTHORED]->(Commit)`
- `(Commit)-[:BELONGS_TO]->(Repository)`
- `(Commit)-[:CHANGES]->(Service)`
- `(Commit)-[:IMPLEMENTS_DECISION]->(Decision)`
- `(Commit)-[:ADDRESSES]->(Issue)`

### Work tracking / incidents

- `(Issue)-[:AFFECTS]->(Service)`
- `(Incident)-[:AFFECTS]->(Service)`
- `(Incident)-[:LED_TO]->(Issue)`
- `(Issue)-[:LED_TO]->(Decision)`
- `(Person)-[:ASSIGNED_TO]->(Issue)` or `(Issue)-[:ASSIGNED_TO]->(Person)`; choose one convention and keep it consistent

Recommended convention for Weave:

`(Issue)-[:ASSIGNED_TO]->(Person)`

### Communication and documentation

- `(Decision)-[:DISCUSSED_IN]->(Message)`
- `(Person)-[:WROTE]->(Message)`
- `(Decision)-[:DOCUMENTED_IN]->(Document)`
- `(Person)-[:AUTHORED]->(Document)`
- `(Document)-[:DESCRIBES]->(Service)`
- `(Issue)-[:DISCUSSED_IN]->(Message)`

### Architecture / dependency

- `(Service)-[:USES]->(Technology)`
- `(Service)-[:DEPENDS_ON]->(Service)`
- `(Decision)-[:AFFECTS]->(Service)`
- `(Decision)-[:INTRODUCES]->(Technology)`
- `(Decision)-[:SUPERSEDES]->(Decision)`

### Provenance

- `(Chunk)-[:FROM_DOCUMENT]->(Document)`
- `(Chunk)-[:FROM_ISSUE]->(Issue)`
- `(Chunk)-[:FROM_MESSAGE]->(Message)`
- `(Chunk)-[:FROM_COMMIT]->(Commit)`
- `(Chunk)-[:MENTIONS]->(Person|Service|Decision|Technology|Issue)` where useful

If the GraphRAG SDK creates equivalent provenance relationships automatically, preserve the SDK's relationship naming rather than duplicating semantically identical edges.

## 4. Canonical demo chain

The NovaPay dataset should contain this path:

```text
INC-17 Payment timeouts
    |
    | LED_TO
    v
PAY-42 Reduce payment latency
    |
    | DISCUSSED_IN
    v
Slack thread payment-perf-2026-05
    |
    | supports
    v
D-007 Introduce Redis cache
    |          |             \
    |          |              \
DECIDED_BY  INTRODUCES      DOCUMENTED_IN
    |          |                 |
  Alice      Redis              ADR-7
    |
    | IMPLEMENTED_BY / via commit
    v
commit 8fae2
    |
    v
payments-api repository
    |
    v
Payment Service
    |
    | depended on by
    v
Checkout Service
```

Implement relationship direction consistently even if the diagram above uses explanatory wording.

## 5. Recommended explicit decision relationships

To make provenance unambiguous, add:

- `(Person)-[:PARTICIPATED_IN]->(Decision)`
- `(Person)-[:APPROVED]->(Decision)`
- `(Decision)-[:SUPPORTED_BY]->(Issue)`
- `(Decision)-[:SUPPORTED_BY]->(Message)`
- `(Decision)-[:IMPLEMENTED_BY]->(Commit)`

This makes the decision itself the hub connecting rationale, people, and implementation.

## 6. Identity strategy

Every node must have a stable canonical `id`.

Examples:

- `person:alice`
- `team:payments`
- `service:payment-service`
- `repo:novapay/payments-api`
- `commit:8fae2...`
- `issue:PAY-42`
- `decision:D-007`
- `doc:ADR-7`
- `incident:INC-17`

Use source-native identifiers where possible. Never rely on display names as unique keys.

## 7. Decision Trace query shape

Goal: retrieve the reason, evidence, participants, and implementation for a decision related to a service/technology.

Illustrative Cypher:

```cypher
MATCH (s:Service {name: $service})-[:USES]->(t:Technology {name: $technology})
MATCH (d:Decision)-[:AFFECTS]->(s)
OPTIONAL MATCH (d)-[:INTRODUCES]->(t)
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(i:Issue)
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(m:Message)
OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN|APPROVED]->(d)
OPTIONAL MATCH (d)-[:IMPLEMENTED_BY]->(c:Commit)-[:BELONGS_TO]->(r:Repository)
OPTIONAL MATCH (d)-[:DOCUMENTED_IN]->(doc:Document)
RETURN d, t, collect(DISTINCT i) AS issues,
       collect(DISTINCT m) AS messages,
       collect(DISTINCT p) AS people,
       collect(DISTINCT c) AS commits,
       collect(DISTINCT r) AS repositories,
       collect(DISTINCT doc) AS documents
```

If FalkorDB's supported Cypher syntax differs for any construct, adapt the final query and document the exact working query in the repository.

## 8. Expert Finder

Expertise should be evidence-backed, not guessed by the LLM.

Suggested score for a person relative to a target service:

- +5 if owner of service/team owner
- +3 per relevant accepted decision participation, capped
- +2 per recent commit affecting service, capped
- +2 per resolved issue affecting service, capped
- +1 per authored document describing service, capped
- +1 for relevant discussion participation, capped

Use caps so a person with many trivial commits does not dominate every ranking.

Illustrative traversal:

```cypher
MATCH (s:Service {name: $service})
MATCH (p:Person)
OPTIONAL MATCH (p)-[:OWNS]->(s)
OPTIONAL MATCH (p)-[:AUTHORED]->(c:Commit)-[:CHANGES]->(s)
OPTIONAL MATCH (p)-[:PARTICIPATED_IN]->(d:Decision)-[:AFFECTS]->(s)
OPTIONAL MATCH (doc:Document)-[:DESCRIBES]->(s)
OPTIONAL MATCH (p)-[:AUTHORED]->(doc)
RETURN p,
       count(DISTINCT c) AS commits,
       count(DISTINCT d) AS decisions,
       count(DISTINCT doc) AS docs
```

The backend can compute the final weighted score from returned evidence if doing the full arithmetic in Cypher becomes brittle.

## 9. Impact Analysis

Impact analysis follows controlled dependency edges rather than arbitrary graph expansion.

Primary edges:

- `DEPENDS_ON`
- `USES`
- `IMPLEMENTS`
- `OWNS`

Suggested behavior:

1. resolve target Service or Technology
2. collect direct dependents
3. traverse downstream services up to 2–3 hops
4. attach owners/teams
5. attach relevant open issues/incidents
6. return a small subgraph

Avoid showing the entire graph.

## 10. Knowledge Freshness

A document is a **stale candidate** when it describes a service and a later material change affects that service.

Baseline heuristic:

```text
Document.updated_at < Decision.decided_at
AND Decision affects same Service
AND Decision.status = accepted
```

OR

```text
Document.updated_at < Commit.timestamp
AND Commit.changes same Service
AND Commit.architecture_change = true
```

Surface the reason:

> “Architecture Overview was last updated on May 1, but Decision D-007 changed Payment Service caching on May 19.”

Do not claim the document is definitely wrong.

## 11. Graph constraints for the hackathon

- Keep relationship semantics narrow and readable.
- Avoid more than ~15 core node labels unless a demo query requires them.
- Avoid generic `RELATED_TO` wherever a meaningful typed relationship exists.
- Preserve timestamps on event-like entities.
- Preserve URLs/source IDs on evidence-bearing entities.
- Prefer explicit Decision nodes over burying decisions in documents/messages.

## 12. What the graph must prove to judges

A graph screenshot is not enough.

The demo should visibly show that:

- a multi-hop graph path answers a question that a single record cannot
- changing/removing an edge changes the answer
- expertise is ranked from relationships
- impact is computed through dependencies
- sources are connected to claims through provenance

---

## Graph-causality demonstration

Use one bounded, reversible demo mutation: remove or redirect a known `DEPENDS_ON` edge between Checkout Service and Payment Service, then re-run the same impact query. The returned dependent services and evidence subgraph must reflect the new graph state. Re-seed to restore the original edge. Document the exact working Cypher and show before/after output. Never represent a synthetic demo change as a real company event.

Freshness re-ingestion updates the same `Document` node's `updated_at` and source content/provenance. Re-evaluate the accepted decision/architecture-change heuristic against that timestamp.
