# Weave — System Architecture

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Version:** 1.0 Hackathon Architecture

## 1. Architecture goal

Build the smallest architecture that proves FalkorDB is the reasoning substrate of the product.

The architecture should support:

- ingestion of connected company knowledge
- source provenance
- graph traversal
- semantic retrieval
- agent tool selection
- LLM answer generation
- evidence-graph visualization

## 2. High-level architecture

```text
                       +--------------------+
                       |     React UI       |
                       | Chat + Evidence KG |
                       +---------+----------+
                                 |
                                 | REST / JSON
                                 v
                       +--------------------+
                       |      FastAPI       |
                       | Query Orchestrator |
                       +---------+----------+
                                 |
                   +-------------+-------------+
                   |                           |
                   v                           v
          +------------------+        +------------------+
          | Agent Tool Router|        | Ingestion Service|
          +--------+---------+        +---------+--------+
                   |                            |
          +--------+---------+         normalize/extract
          |        |         |                   |
          v        v         v                   v
       Cypher   Semantic   Provenance       +---------+
       tools    retrieval  retrieval        |FalkorDB |
          \        |         /              |         |
           +-------+--------+---------------+ Graph    |
                   |                       | Chunks   |
                   v                       | Vectors  |
             Context Builder               +---------+
                   |
                   v
              LLM Provider
          (Qwen/Ollama or hosted)
                   |
                   v
          Answer + sources + graph
```

## 3. Major components

### 3.1 Frontend

**Technology:** React, TypeScript, Vite, Tailwind CSS

Responsibilities:

- question input
- answer rendering
- source cards
- evidence-path visualization
- feature shortcuts: Decision Trace, Expert Finder, Impact Analysis, Freshness
- loading/error/empty states

Do not build a broad admin dashboard unless time remains.

### 3.2 FastAPI backend

Responsibilities:

- REST API
- input validation
- graph-tool dispatch
- GraphRAG orchestration
- LLM calls
- response shaping
- health/status endpoints
- ingestion trigger for local demo/setup

The backend is intentionally stateless for the primary demo except for data persisted in FalkorDB.

### 3.3 Ingestion layer

Inputs:

- normalized synthetic GitHub data
- normalized Jira-like tickets
- normalized Slack-like messages/threads
- Markdown docs and ADRs

Responsibilities:

1. validate records
2. normalize IDs and timestamps
3. create/merge entity nodes
4. create relationships
5. preserve source metadata
6. create source/chunk nodes
7. compute/store embeddings where needed
8. make re-ingestion idempotent

### 3.4 FalkorDB

FalkorDB is the primary company knowledge layer.

It stores:

- normalized business/engineering entities
- graph relationships
- decision provenance
- source/chunk nodes
- embedding vectors where semantic retrieval is enabled
- metadata required to reconstruct citations

Core features depend directly on graph traversal in FalkorDB.

### 3.5 Agent tool router

The agent receives a user question and selects one or more bounded tools.

Required tools:

- `trace_decision(topic_or_entity)`
- `find_expert(entity)`
- `impact_analysis(entity)`
- `find_stale_knowledge(entity)`
- `semantic_search(query)`
- `find_sources(entity_ids)`

The agent should not generate arbitrary unconstrained Cypher in the primary demo. Prefer tested tool functions with parameters.

### 3.6 Context builder

Combines:

- graph query output
- source snippets
- provenance paths
- entity metadata

It should deduplicate records and keep the final prompt compact.

### 3.7 LLM layer

The LLM's job is to summarize and explain evidence, not invent company facts.

Baseline rules:

- answer only from supplied context
- preserve source names/IDs
- state when evidence is insufficient
- do not imply certainty beyond the graph evidence

Use an LLM provider abstraction so the team can swap between Qwen/Ollama and a hosted model without changing graph logic.

## 4. Request flow

Example question:

> “Why does Payment Service use Redis?”

Flow:

1. Frontend sends query to `POST /api/query`.
2. Backend classifies the intent as decision/provenance oriented.
3. `trace_decision` resolves `Payment Service` and `Redis`.
4. FalkorDB traverses relevant `USES`, `DECIDED`, `LED_TO`, `DISCUSSED_IN`, `IMPLEMENTED_BY`, and source relations.
5. Backend fetches supporting chunks/source records.
6. Context Builder creates a concise evidence packet.
7. LLM explains the result.
8. Backend returns:
   - answer
   - source list
   - evidence path
   - subgraph nodes/edges
9. Frontend renders answer and graph side-by-side.

## 5. Ingestion flow

```text
Raw synthetic record
      |
      v
Schema validation
      |
      v
Canonical IDs
      |
      +-------> entity node MERGE
      |
      +-------> relationship MERGE
      |
      +-------> source/chunk node
      |
      +-------> embedding generation
      |
      v
FalkorDB graph ready for query
```

## 6. Repository structure

Create this structure only after the hackathon starts:

```text
weave/
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── query.py
│   │   │   ├── graph.py
│   │   │   ├── ingestion.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── graph/
│   │   │   ├── client.py
│   │   │   ├── schema.py
│   │   │   ├── queries.py
│   │   │   └── algorithms.py
│   │   ├── ingestion/
│   │   │   ├── models.py
│   │   │   ├── normalizers.py
│   │   │   ├── loader.py
│   │   │   └── embeddings.py
│   │   ├── agent/
│   │   │   ├── router.py
│   │   │   ├── tools.py
│   │   │   ├── context_builder.py
│   │   │   └── prompts.py
│   │   └── services/
│   │       └── llm.py
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── lib/
│       └── types/
├── data/
│   └── novapay/
├── docs/
│   ├── graph-model.md
│   ├── cypher.md
│   └── demo.md
└── scripts/
    ├── seed.py
    └── reset_graph.py
```

## 7. Why no Neo4j + ChromaDB split

The prior EKOS architecture separated graph and vector concerns across Neo4j and ChromaDB. For Weave, that adds unnecessary moving parts and weakens the sponsor story.

Hackathon decision:

- no Neo4j
- no ChromaDB
- no PostgreSQL unless a concrete requirement appears

FalkorDB owns the company knowledge graph and associated retrieval data for the demo.

## 8. Reliability strategy

- seed a deterministic synthetic dataset
- use fixed canonical IDs
- use idempotent MERGE/upsert logic
- bound graph traversals by relationship type and depth
- maintain 10–15 golden questions
- cache nothing that could hide whether FalkorDB is actually used
- keep one tested fallback LLM provider
- record the demo against the same seeded dataset used in tests

## 9. Security scope

The hackathon demo does not implement enterprise RBAC.

Minimum safeguards:

- `.env` excluded from Git
- no real company secrets
- synthetic/public data only
- secrets never shown in demo video
- parameterized graph queries where supported
- basic API input validation

## 10. Deployment

Preferred local path:

- FalkorDB in Docker
- FastAPI locally or containerized
- React development/build server

Preferred hosted path if time allows:

- frontend on a static/React hosting platform
- backend on a Python-compatible host
- FalkorDB Cloud or a reachable FalkorDB deployment

A stable local setup plus demo video is better than a fragile live deployment.

---

## Demonstrable graph dependence and update path

- Add a demo-only controlled mutation/reset operation, disabled or protected on public deployments. It changes one known FalkorDB edge and returns the affected IDs. Re-run the same tested graph query; no UI-only substitution.
- Make document upsert idempotent: canonical document ID, updated timestamp, and provenance remain stable. Recompute freshness from FalkorDB after upsert, not cached responses.
- For optional follow-through, generate a review-task preview from `impact_analysis` results. Explicit user confirmation triggers a single creation request. Never create tasks automatically from a question.
- Keep the primary request path unchanged: FalkorDB Cypher tools → evidence/context → grounded answer + subgraph.
