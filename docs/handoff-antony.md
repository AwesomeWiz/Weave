# Handoff: Data → Graph (Antony)

**Owner:** Data / Ingestion (Phase 2 Update)
**Last updated:** 2026-10-17

---

## 1. Finalized Graph Specification & Counts

The expanded NovaPay dataset provides grounded evidence for all Phase 2 demos (Impact Analysis, Expert Finder, Knowledge Freshness, Exact Source Retrieval, Unsupported Question Grounding):

- **Domain Entity Nodes:** 20 canonical records
  - **4 People:** `person:alice`, `person:ravi`, `person:maya`, `person:neeraj`
  - **2 Teams:** `team:payments`, `team:platform`
  - **3 Services:** `service:payment-service`, `service:checkout-service`, `service:order-service`
  - **2 Technologies:** `tech:redis`, `tech:postgresql`
  - **1 Repository:** `repo:novapay/payments-api`
  - **1 Commit:** `commit:8fae2`
  - **1 Issue:** `issue:PAY-42`
  - **1 Message:** `message:payment-perf-7`
  - **1 Decision:** `decision:D-007`
  - **1 Incident:** `incident:INC-17`
  - **3 Documents:** `doc:ADR-7`, `doc:architecture-overview`, `doc:runbook-payment-latency`
- **Retrieval Chunk Nodes:** 6 chunk records
  - `chunk:issue:PAY-42:0`
  - `chunk:message:payment-perf-7:0`
  - `chunk:commit:8fae2:0`
  - `chunk:doc:ADR-7:0`
  - `chunk:doc:architecture-overview:0`
  - `chunk:doc:runbook-payment-latency:0`
- **Total Relationships:** 44 edges
  - 38 entity-to-entity edges
  - 6 chunk-to-source provenance edges (`FROM_ISSUE`, `FROM_MESSAGE`, `FROM_COMMIT`, `FROM_DOCUMENT`)
- **Alias Mappings:** 29 natural-language resolution keys in `aliases.json`

---

## 2. Key Relationship Traversal Paths

### Impact Analysis
- **Core direct dependency (1 hop):**
  `(service:checkout-service) -[:DEPENDS_ON]-> (service:payment-service)`
- **Indirect downstream dependency (2 hops):**
  `(service:order-service) -[:DEPENDS_ON]-> (service:checkout-service) -[:DEPENDS_ON]-> (service:payment-service)`
- **Technology usage:**
  - `(service:payment-service) -[:USES]-> (tech:redis)`
  - `(service:payment-service) -[:USES]-> (tech:postgresql)`
  - `(service:order-service) -[:USES]-> (tech:postgresql)`
- **Service ownership:**
  - `(team:payments) -[:OWNS]-> (service:payment-service)`
  - `(team:platform) -[:OWNS]-> (service:checkout-service)`
  - `(team:platform) -[:OWNS]-> (service:order-service)`

### Expert Finder Evidence
No artificial `expert_score` or `expert_rank` properties exist. The graph provides distinct, traversable evidence:
- **Alice Menon (`person:alice`):**
  - `(person:alice) -[:APPROVED]-> (decision:D-007)`
  - `(person:alice) -[:PARTICIPATED_IN]-> (decision:D-007)`
  - `(person:alice) -[:WROTE]-> (message:payment-perf-7)`
  - `(person:alice) -[:MEMBER_OF]-> (team:payments) -[:OWNS]-> (service:payment-service)`
  - Role: Payments Tech Lead
- **Ravi Nair (`person:ravi`):**
  - `(person:ravi) -[:PARTICIPATED_IN]-> (decision:D-007)`
  - `(person:ravi) -[:AUTHORED]-> (commit:8fae2) -[:IMPLEMENTS_DECISION]-> (decision:D-007)`
  - `(commit:8fae2) -[:ADDRESSES]-> (issue:PAY-42)`
  - `(issue:PAY-42) -[:ASSIGNED_TO]-> (person:ravi)`
  - `(person:ravi) -[:WROTE]-> (message:payment-perf-7)`
  - `(person:ravi) -[:MEMBER_OF]-> (team:payments)`
- **Maya Joseph (`person:maya`):**
  - `(person:maya) -[:PARTICIPATED_IN]-> (decision:D-007)`
  - `(person:maya) -[:WROTE]-> (message:payment-perf-7)` (Redis platform infrastructure availability)
  - `(person:maya) -[:MEMBER_OF]-> (team:platform)`
- **Neeraj Shah (`person:neeraj`) [Weaker Candidate]:**
  - `(person:neeraj) -[:MEMBER_OF]-> (team:platform)`
  - No decision approvals, no commits on Redis/payments, no assignment to PAY-42, no message participation. Easily distinguished by graph traversals.

### Knowledge Freshness
- `(doc:architecture-overview) -[:DESCRIBES]-> (service:payment-service)`
  - `updated_at`: `2026-05-01T12:00:00Z`
  - Pre-dates `decision:D-007` (`2026-05-18T14:30:00Z`) and `commit:8fae2` (`2026-05-19T10:15:00Z`).
  - **Status:** Review Candidate (stale candidate)
- `(doc:ADR-7)`:
  - `updated_at`: `2026-05-20T10:00:00Z`
  - Connected via `(decision:D-007) -[:DOCUMENTED_IN]-> (doc:ADR-7)` and `(doc:ADR-7) -[:DESCRIBES]-> (service:payment-service)`.
  - **Status:** Current
- `(doc:runbook-payment-latency) -[:DESCRIBES]-> (service:payment-service)`:
  - `updated_at`: `2026-05-22T10:00:00Z`
  - Post-dates all decisions and commits; details operational procedures for Redis cache hit rate monitoring.
  - **Status:** Negative freshness case (NOT stale)

---

## 3. How to Consume

```python
from weave_data.ingest import prepare_ingestion, run_ingestion
from weave_data.graph_adapter import FalkorDBGraphAdapter

# Option A: Consume prepared data directly
records, rel_ops, chunks, aliases, validation = prepare_ingestion()
# records: 20 validated BaseRecord models
# chunks: 6 validated ChunkRecord models
# rel_ops: 44 RelationshipOp instances
# aliases: 29 alias mappings

# Option B: Run full ingestion pipeline with FalkorDB
adapter = FalkorDBGraphAdapter(host="localhost", port=6379, graph_name="novapay")
result = run_ingestion(adapter=adapter)
```

---

## 4. Live Graph Verification Commands

When the FalkorDB container is running:

```cypher
// 1. Verify domain entity nodes (expected: 20)
MATCH (n) WHERE NOT n:Chunk RETURN count(n) AS domain_nodes;

// 2. Verify chunk nodes (expected: 6)
MATCH (n:Chunk) RETURN count(n) AS chunk_nodes;

// 3. Verify total relationships (expected: 44)
MATCH ()-[r]->() RETURN count(r) AS total_relationships;

// 4. Verify impact traversal from Payment Service
MATCH path = (s:Service)-[:DEPENDS_ON*1..2]->(p:Service {id: 'service:payment-service'})
RETURN [n in nodes(path) | n.id] AS impact_chain;
// Expected:
// ['service:checkout-service', 'service:payment-service'] (direct)
// ['service:order-service', 'service:checkout-service', 'service:payment-service'] (indirect)

// 5. Verify chunk provenance relationships (expected: 6)
MATCH (c:Chunk)-[r]->(s)
WHERE type(r) IN ['FROM_ISSUE', 'FROM_MESSAGE', 'FROM_COMMIT', 'FROM_DOCUMENT']
RETURN c.id, type(r), s.id
ORDER BY c.id;
```
