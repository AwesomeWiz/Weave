# Weave — Ingestion Contract

**Owner:** Alen Abraham Saji (Data / Ingestion)
**Last updated:** 2026-10-15

## 1. Canonical IDs

Every entity uses a prefixed canonical ID as its primary key.

| Entity Type | Prefix       | Example                    |
|-------------|-------------|----------------------------|
| Person      | `person:`    | `person:alice`             |
| Team        | `team:`      | `team:payments`            |
| Service     | `service:`   | `service:payment-service`  |
| Technology  | `tech:`      | `tech:redis`               |
| Repository  | `repo:`      | `repo:novapay/payments-api`|
| Commit      | `commit:`    | `commit:8fae2`             |
| Issue       | `issue:`     | `issue:PAY-42`             |
| Message     | `message:`   | `message:payment-perf-7`   |
| Document    | `doc:`       | `doc:ADR-7`                |
| Decision    | `decision:`  | `decision:D-007`           |
| Incident    | `incident:`  | `incident:INC-17`          |
| Chunk       | `chunk:`     | `chunk:issue:PAY-42:0`     |

IDs are globally unique. Never use display names as keys.

## 2. Source file layout

```
data/novapay/
├── people.json
├── teams.json
├── services.json
├── technologies.json
├── incidents.json
├── decisions.json
├── aliases.json
├── github/
│   ├── repositories.json
│   └── commits.json
├── jira/
│   └── issues.json
├── slack/
│   └── messages.json
└── docs/
    ├── ADR-7.md
    ├── architecture-overview.md
    └── runbook-payment-latency.md
```

## 3. Record schema

Every JSON record carries:

- `id` — canonical ID (non-empty, colon-prefixed)
- `source` — origin system (`hr`, `github`, `jira`, `slack`, `pagerduty`, `decision-log`, `service-catalog`, `docs`)
- `entity_type` — matches the graph label (`Person`, `Service`, `Decision`, …)
- Entity-specific fields (see `weave_data/models.py` for full Pydantic models)
- Relationship references use canonical IDs, not display names

## 4. Relationship mapping (source field → graph edge)

| Source Entity | Field                | Relationship            | Direction         |
|---------------|----------------------|------------------------|-------------------|
| Incident      | `related_issues`     | `LED_TO`               | Incident → Issue  |
| Incident      | `affected_services`  | `AFFECTS`              | Incident → Service|
| Issue         | `affected_services`  | `AFFECTS`              | Issue → Service   |
| Issue         | `related_incidents`  | `LED_TO`               | Incident → Issue  |
| Issue         | `assignee`           | `ASSIGNED_TO`          | Issue → Person    |
| Decision      | `affects`            | `AFFECTS`              | Decision → Service|
| Decision      | `introduces`         | `INTRODUCES`           | Decision → Tech   |
| Decision      | `participants`       | `PARTICIPATED_IN`      | Person → Decision |
| Decision      | `approved_by`        | `APPROVED`             | Person → Decision |
| Decision      | `supported_by`       | `SUPPORTED_BY`         | Decision → Issue/Message |
| Decision      | `implemented_by`     | `IMPLEMENTED_BY`       | Decision → Commit |
| Decision      | `documented_in`      | `DOCUMENTED_IN`        | Decision → Document|
| Commit        | `repository`         | `BELONGS_TO`           | Commit → Repository|
| Commit        | `changes`            | `CHANGES`              | Commit → Service  |
| Commit        | `author`             | `AUTHORED`             | Person → Commit   |
| Commit        | `implements_decision`| `IMPLEMENTS_DECISION`  | Commit → Decision |
| Commit        | `addresses`          | `ADDRESSES`            | Commit → Issue    |
| Repository    | `service`            | `IMPLEMENTS`           | Repository → Service|
| Service       | `technologies`       | `USES`                 | Service → Tech    |
| Service       | `depends_on`         | `DEPENDS_ON`           | Service → Service |
| Team          | `members`            | `MEMBER_OF`            | Person → Team     |
| Team          | `owns_services`      | `OWNS`                 | Team → Service    |
| Person        | `team`               | `MEMBER_OF`            | Person → Team     |
| Message       | `participants`       | `WROTE`                | Person → Message  |
| Document      | `describes`          | `DESCRIBES`            | Document → Service|

Directions follow `docs/04_KNOWLEDGE_GRAPH.md`.

## 5. Timeline

All timestamps are UTC ISO-8601.

| Date            | Event                                                     | Freshness Significance |
|-----------------|-----------------------------------------------------------|------------------------|
| 2026-05-01      | Architecture Overview (`doc:architecture-overview`)       | Review candidate (stale) |
| 2026-05-10      | INC-17 (started)                                          | Precedes decision      |
| 2026-05-11      | PAY-42 opened                                             | Precedes decision      |
| 2026-05-15–17   | Redis / latency discussion (`message:payment-perf-7`)     | Precedes decision      |
| 2026-05-18      | D-007 accepted (`decision:D-007`)                         | Architecture decision  |
| 2026-05-19      | Commit `8fae2` (Redis implementation)                     | Architecture change    |
| 2026-05-20      | ADR-7 updated (`doc:ADR-7`)                               | Current for D-007      |
| 2026-05-22      | Runbook updated (`doc:runbook-payment-latency`)           | Current (negative case)|

## 6. Validation checks

Run `validate_dataset()` before any persistence. It checks:

1. Non-empty canonical IDs
2. Global uniqueness
3. Canonical ID format validity (valid prefix, no whitespace, valid characters)
4. Required fields (Pydantic schemas)
5. Valid entity/source types
6. Timestamp parsing and chronological consistency (supporting evidence before decision, implementing commit after decision, incident before issue)
7. Reference resolution
8. Reference type compatibility (including `Document.describes -> Service`)
9. D-007 completeness
10. Redis decision chain completeness
11. Structural relationships (ownership, dependencies, tech USES)
12. Orphan Decisions check (every Decision must connect to at least one entity)
13. Service ownership check (every Service must have an owning Team)
14. Decision evidence check (every accepted Decision must have at least 2 evidence sources)
15. Text integrity check (no empty text/description in issues, messages, commits, documents)
16. Chunk/source provenance integrity (chunk source_id resolves, type matches)
17. Alias integrity (targets exist, no empty/duplicate keys)
18. Credential/PII scanning

## 7. Chunk contract

Chunks carry:

| Field          | Description                              |
|----------------|------------------------------------------|
| `id`           | `chunk:{source_id}:{index}`              |
| `source_id`    | Canonical ID of source entity            |
| `source_type`  | `Issue`, `Message`, `Commit`, `Document` |
| `chunk_index`  | 0-based (one chunk per source)           |
| `title`        | Short title or subject                   |
| `text`         | Full verbatim text content               |
| `timestamp`    | ISO-8601 timestamp from source           |
| `url`          | Source web URL, if available             |

### Chunk Relationships
Every Chunk node is connected to its parent source entity:
- `(:Chunk {id: "chunk:issue:PAY-42:0"}) -[:FROM_ISSUE]-> (:Issue {id: "issue:PAY-42"})`
- `(:Chunk {id: "chunk:message:payment-perf-7:0"}) -[:FROM_MESSAGE]-> (:Message {id: "message:payment-perf-7"})`
- `(:Chunk {id: "chunk:commit:8fae2:0"}) -[:FROM_COMMIT]-> (:Commit {id: "commit:8fae2"})`
- `(:Chunk {id: "chunk:doc:ADR-7:0"}) -[:FROM_DOCUMENT]-> (:Document {id: "doc:ADR-7"})`
- `(:Chunk {id: "chunk:doc:architecture-overview:0"}) -[:FROM_DOCUMENT]-> (:Document {id: "doc:architecture-overview"})`
- `(:Chunk {id: "chunk:doc:runbook-payment-latency:0"}) -[:FROM_DOCUMENT]-> (:Document {id: "doc:runbook-payment-latency"})`

### Exact Retrieval Interface
`find_sources()` in `weave_data.retrieval` provides deterministic source-evidence lookup without text fabrication:

```python
def find_sources(
    source_ids: Iterable[str] | None,
    data_dir: Path | None = None,
    chunks: list[ChunkRecord] | None = None,
    records: list[BaseRecord] | None = None,
    adapter: GraphAdapter | None = None,
) -> list[SourceRecord]:
```

## 8. Alias contract

`aliases.json` maps 29 lowercase natural-language names to canonical IDs.
Used for deterministic entity resolution before semantic fallback.

## 9. Assumptions for Antony (Graph / FalkorDB)

1. Node labels match `EntityType` values: `Person`, `Service`, `Decision`, `Technology`, `Commit`, `Chunk`, etc.
2. Every node has an `id` property holding the canonical ID.
3. Relationships use the labels from the mapping table above plus the 6 `FROM_*` chunk relationships (total 44 relationships).
4. `MERGE` on `{id: $id}` provides idempotent upserts.
5. In `run_ingestion()`, source entity nodes and chunk nodes are persisted before relationships are created.
6. The `prepare_ingestion()` function returns `(records, rel_ops, chunks, aliases, validation)` — Antony can consume `rel_ops` directly as `(source_id, rel_type, target_id)` tuples.
