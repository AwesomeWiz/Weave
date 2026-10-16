# Handoff: Data → Graph (Antony)

## 1. What's Ready

The ingestion pipeline in `weave_data/` produces:
- **15 validated domain entity records** (3 people, 2 teams, 2 services, 1 tech, 1 repo, 1 commit, 1 issue, 1 message, 1 decision, 1 incident, 1 document).
- **4 validated Chunk records** (`ChunkRecord` with `id`, `source_id`, `source_type`, `chunk_index`, `title`, `text`, `timestamp`, `url`).
- **33 relationship operations** (`RelationshipOp(source_id, rel_type, target_id)`):
  - 29 domain entity relationships (`LED_TO`, `AFFECTS`, `INTRODUCES`, `SUPPORTED_BY`, `IMPLEMENTED_BY`, `DOCUMENTED_IN`, `PARTICIPATED_IN`, `APPROVED`, `BELONGS_TO`, `IMPLEMENTS`, `USES`, `DEPENDS_ON`, `OWNS`, etc.).
  - 4 chunk-to-source relationships:
    - `(:Chunk {id: "chunk:issue:PAY-42:0"}) -[:FROM_ISSUE]-> (:Issue {id: "issue:PAY-42"})`
    - `(:Chunk {id: "chunk:message:payment-perf-7:0"}) -[:FROM_MESSAGE]-> (:Message {id: "message:payment-perf-7"})`
    - `(:Chunk {id: "chunk:commit:8fae2:0"}) -[:FROM_COMMIT]-> (:Commit {id: "commit:8fae2"})`
    - `(:Chunk {id: "chunk:doc:ADR-7:0"}) -[:FROM_DOCUMENT]-> (:Document {id: "doc:ADR-7"})`

---

## 2. How to Consume

```python
from weave_data.ingest import prepare_ingestion, run_ingestion
from weave_data.graph_adapter import FalkorDBGraphAdapter

# Option A: Consume the prepared data directly
records, rel_ops, chunks, aliases, validation = prepare_ingestion()
# records: 15 validated BaseRecord models
# chunks: 4 validated ChunkRecord models
# rel_ops: 33 RelationshipOp instances
# aliases: 17 alias mappings

# Option B: Run the full ingestion pipeline with FalkorDB
adapter = FalkorDBGraphAdapter(host="localhost", port=6379, graph_name="novapay")
result = run_ingestion(adapter=adapter)
print(result.to_dict())
# Expected:
# {
#   "status": "success",
#   "records_processed": 15,
#   "nodes_created_or_updated": 15,
#   "relationships_processed": 33,
#   "chunks_created_or_updated": 4,
#   "errors": []
# }
```

---

## 3. Persistence Order & Cypher Guarantees

In `run_ingestion()`, persistence executes in strict topological order:
1. `_persist_nodes`: writes the 15 domain entity nodes (`MERGE (n:{entity_type} {id: $id}) SET ...`).
2. `_persist_chunks`: writes the 4 Chunk nodes (`MERGE (n:Chunk {id: $id}) SET ...`).
3. `_persist_relationships`: writes the 33 graph edges (`MATCH (a {id: $src}), (b {id: $tgt}) MERGE (a)-[r:{rel_type}]->(b)`).

Both endpoints of every relationship (including `(Chunk)-[:FROM_*]->(Source)`) exist in the graph before relationship creation begins.

---

## 4. Commands to Seed & Verify against FalkorDB

```bash
# Ingestion command
python -m weave_data.ingest --host localhost --port 6379 --graph novapay

# Verify node counts in FalkorDB:
# Domain nodes:
MATCH (n) WHERE NOT n:Chunk RETURN count(n) AS domain_nodes
# Expected: 15

# Chunk nodes:
MATCH (n:Chunk) RETURN count(n) AS chunk_nodes
# Expected: 4

# Relationships:
MATCH ()-[r]->() RETURN count(r) AS total_relationships
# Expected: 33

# Verify chunk-to-source relationships:
MATCH (c:Chunk)-[r]->(s)
RETURN c.id, type(r), s.id, c.url
```

---

## 5. Verification Status

- **In-Memory Adapter:** Verified with 80 automated unit & integration tests (`pytest`).
- **Live FalkorDB:** Awaiting driver/server connectivity (requires `pip install falkordb` and a running instance on port 6379).
