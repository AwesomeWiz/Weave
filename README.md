# Weave — Company Brain (Data & Ingestion)

> **Track 3: Company Brain** — FalkorDB Graph Hacks  
> **Workstream:** Data / Ingestion  
> **Owner:** Alen Abraham Saji

Weave is a company decision-intelligence agent that connects incidents, issues, discussions, decisions, people, commits, repositories, services, technologies, and documents in FalkorDB.

---

## 🎯 Primary Demo Query & Evidence Chain

**Question:** *"Why does Payment Service use Redis?"*

**Canonical Evidence Chain:**
```
incident:INC-17  ("Payment requests timing out during peak traffic")
       │ LED_TO
       ▼
issue:PAY-42     ("Reduce payment latency under burst traffic")
       │ SUPPORTED_BY (reverse)
       ▼
decision:D-007   ("Introduce Redis caching" — status: accepted)
       │
       ├── AFFECTS          ──► service:payment-service
       ├── INTRODUCES       ──► tech:redis
       ├── SUPPORTED_BY     ──► issue:PAY-42
       ├── SUPPORTED_BY     ──► message:payment-perf-7
       ├── IMPLEMENTED_BY   ──► commit:8fae2
       ├── DOCUMENTED_IN    ──► doc:ADR-7
       ├── PARTICIPATED_IN  ◄── person:alice, person:ravi, person:maya
       └── APPROVED         ◄── person:alice (approver)

commit:8fae2 ──► BELONGS_TO ──► repo:novapay/payments-api
                                       │ IMPLEMENTS
                                       ▼
                               service:payment-service ◄── USES ── tech:redis
                                       ▲
                                       │ DEPENDS_ON
                               service:checkout-service
```

---

## 🚀 Quickstart

### 1. Requirements

Install minimal dependencies (Python 3.10+):
```bash
pip install -r requirements.txt
```

### 2. Run Ingestion CLI

**Validate & prepare data without graph persistence:**
```bash
python -m weave_data.ingest --prepare-only
```

**Output prepared dataset as JSON:**
```bash
python -m weave_data.ingest --prepare-only --json
```

**Full ingestion run (in-memory adapter fallback or FalkorDB if configured):**
```bash
python -m weave_data.ingest
```

**Connect to FalkorDB:**
```bash
python -m weave_data.ingest --host localhost --port 6379 --graph novapay
```
*(Or set environment variables `FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_GRAPH`)*

### 3. Run Test Suite

```bash
python -m pytest -q
```
*(The suite covers schema validation, referential integrity, temporal ordering, relationship extraction, text chunking, local and graph-backed source retrieval, determinism, and idempotency.)*

---

## 📦 Package Architecture (`weave_data/`)

| Module | Purpose |
|---|---|
| [`models.py`](weave_data/models.py) | Pydantic v2 schemas for all canonical records (`Person`, `Team`, `Service`, `Technology`, `Repository`, `Commit`, `Issue`, `Message`, `Decision`, `Incident`, `Document`, `Chunk`). Enforces prefixed IDs, required fields, URLs, and ISO-8601 timestamps. |
| [`loader.py`](weave_data/loader.py) | Discovers and loads source files (`JSON`, `Markdown`) from `data/novapay/`. |
| [`validation.py`](weave_data/validation.py) | Validates unique IDs, entity type bounds, foreign reference resolution, and temporal consistency. |
| [`relationships.py`](weave_data/relationships.py) | Maps entity fields and chunks to 33 Cypher graph edge operations (`RelationshipOp`) adhering to the knowledge graph ontology. |
| [`chunks.py`](weave_data/chunks.py) | Generates normalized text chunks with source provenance (`url`, `timestamp`, `chunk_index`) and chunk-to-source relationships (`FROM_*`). |
| [`retrieval.py`](weave_data/retrieval.py) | Deterministic `find_sources(source_ids)` exact-source retrieval interface resolving canonical entity IDs to structured evidence. |
| [`graph_adapter.py`](weave_data/graph_adapter.py) | Abstraction over graph storage: `InMemoryGraphAdapter` (mock) and `FalkorDBGraphAdapter` (Cypher MERGE queries). |
| [`ingest.py`](weave_data/ingest.py) | Pipeline orchestrator & CLI entry point. Provides `prepare_ingestion()` and `run_ingestion()`. |

---

## 🤝 Team Handoff & Contracts

- [**Ingestion Contract**](docs/ingestion-contract.md) — Canonical IDs, schema fields, relationship mappings, and chunk specifications.
- [**Graph Handoff (Antony)**](docs/handoff-antony.md) — Node labels, Cypher MERGE patterns, and how to consume `prepare_ingestion()`.
- [**AI Integration Handoff (Abhishikth)**](docs/handoff-abhishikth.md) — Retrieval chunks, `find_sources` interface, entity aliases, and provenance metadata.
- [**Frontend & Demo Handoff (Arnold)**](docs/handoff-arnold.md) — Redis decision chain, evidence timeline, and causality demo edge.
