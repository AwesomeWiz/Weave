# Weave — Team Plan

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Team:** Abhishikth S. Mattom, Arnold Shibu, Alen Abraham Saji, Antony Jose  
**Build strategy:** parallel workstreams around one end-to-end demo, not four isolated features.

> The ownership below is a recommended starting split based on the team's prior EKOS work. Adjust it before the event if anyone prefers another area. Every member must still understand the graph model and major Cypher logic.

## 1. Ownership

### Antony Jose — Graph / FalkorDB owner

Primary responsibilities:

- FalkorDB setup
- graph schema/ontology implementation
- Cypher queries
- Decision Trace traversal
- Expert Finder graph evidence
- Impact Analysis traversal
- graph seed/reset tooling
- document the important queries for submission

Day-1 success condition:

> Seed data exists in FalkorDB and at least one multi-hop Decision Trace query returns the expected path.

### Alen Abraham Saji — Data / ingestion owner

Primary responsibilities:

- NovaPay synthetic dataset
- source schemas
- GitHub/Jira/Slack/doc normalizers
- idempotent ingestion
- canonical IDs
- source/chunk provenance
- timestamps needed for freshness
- optional incremental update demonstration

Day-1 success condition:

> The canonical Payment Service → Redis decision chain can be loaded repeatedly without duplicate entities.

### Abhishikth S. Mattom — AI integration / product integration owner

Primary responsibilities:

- FastAPI query flow
- agent/tool router
- Context Builder
- semantic retrieval integration
- LLM provider abstraction
- Qwen/Ollama path and fallback provider
- sourced response generation
- integrate frontend query flow with backend

Day-1 success condition:

> The primary question reaches a graph tool and returns an end-to-end textual answer from graph evidence.

### Arnold Shibu — Frontend / demo / quality owner

Primary responsibilities:

- React UI
- answer/source presentation
- evidence graph visualization
- feature entry points
- demo-state polish
- golden-query test execution
- README/demo assets coordination
- deployment/local-run validation

Day-1 success condition:

> Basic UI can send the primary query and render the backend response plus a placeholder/initial evidence graph.

## 2. Shared responsibilities

Every team member must be able to explain:

- why FalkorDB is essential
- the main node labels
- the main relationships
- the canonical decision chain
- at least one important Cypher query
- how the LLM is prevented from inventing company facts
- why the project is different from generic vector RAG

No subsystem should have only one person who understands it.

## 3. Build priority rule

Work in this order:

1. one end-to-end Decision Trace
2. evidence graph
3. Expert Finder
4. Impact Analysis
5. source-grounded generation
6. Knowledge Freshness
7. visual polish
8. optional extras

If Day 2 ends and items 1–5 are not stable, stop adding features.

## 4. Day 1 — Foundation and vertical slice

### Shared kickoff

- create new public/private-working repo according to submission strategy after official start
- confirm branch strategy
- add `.env.example`
- confirm exact graph schema
- agree canonical IDs
- define primary API response object

### Graph work

- run FalkorDB
- implement seed/reset
- create core labels/relationships
- implement first Decision Trace query

### Data work

- create small NovaPay seed dataset first, not full dataset
- minimum chain: incident → issue → discussion → decision → commit → service → Redis
- attach people and one downstream dependency

### Backend/AI work

- FastAPI skeleton
- `/api/health`
- `/api/query`
- direct routing of primary question to Decision Trace
- initial Context Builder
- LLM answer using returned graph evidence

### Frontend work

- chat screen
- answer pane
- source cards
- evidence graph component shell

### Day-1 gate

The following must work before ending Day 1:

> Ask “Why does Payment Service use Redis?” in the UI and receive a graph-grounded answer with at least one visible evidence path.

## 5. Day 2 — Intelligence

### Graph

- finish Decision Trace
- build Expert Finder evidence query
- build Impact Analysis
- implement freshness query/heuristic

### Data

- expand NovaPay dataset
- add ambiguity/negative cases
- add timestamps that make freshness meaningful
- verify all source URLs/IDs are synthetic or safe

### Backend/AI

- multi-tool routing
- semantic retrieval
- source deduplication
- confidence/support status
- structured graph payload

### Frontend

- interactive graph nodes/edges
- tool/feature labels
- source inspection
- loading/error states
- responsive demo layout

### Day-2 gate

All four core capabilities should work through the API. At least three should be polished in the UI.

## 6. Day 3 — Product and demo hardening

- run golden questions
- fix incorrect graph paths
- improve LLM prompts only after retrieval is correct
- reduce latency
- improve graph readability
- add empty/no-evidence behavior
- complete README architecture section
- document graph model
- document exact Cypher queries
- prepare setup instructions
- deploy if stable
- rehearse demo
- record fallback demo if appropriate

### Day-3 gate

A teammate who did not build a feature should be able to run and explain it.

## 7. Final submission buffer — October 18

Use primarily for:

- bug fixes
- final README
- screenshots
- architecture diagram
- demo video
- project description
- track declaration
- AI-assistant disclosure
- final repository cleanup
- submission

Do not plan a major feature for the final hours.

## 8. Git workflow

Recommended:

- `main` must always be demoable after Day 1
- short-lived feature branches
- merge small increments frequently
- require at least one teammate to review graph-schema changes
- avoid long branches that only merge at the end

Suggested branch names:

- `feat/graph-schema`
- `feat/ingestion`
- `feat/agent-tools`
- `feat/frontend`
- `feat/impact-analysis`

## 9. Daily synchronization

Run a 10-minute sync at the start and middle of each build day.

Each person answers:

- What is working?
- What is blocking the end-to-end demo?
- What contract changed?
- What can be cut?

The priority is integration, not equal amounts of code per member.

## 10. Scope-cut order

If behind schedule, cut in this order:

1. optional Track 1 action
2. incremental sync demo
3. persistent memory
4. extra connectors
5. sophisticated animation
6. advanced freshness scoring

Do **not** cut:

- FalkorDB centrality
- Decision Trace
- evidence/source display
- one convincing impact/expertise capability

---

## Updated delivery gates (October 15)

**Day 1 (Oct 15):** retain original end-to-end Decision Trace gate. Antony also selects a reversible dependency edge for the later causality demo; Alen defines document upsert version/timestamp fields; Abhishikth and Arnold retain their original integration/UI gates.

**Day 2 (Oct 16):** finish and stabilize Expert Finder, Impact Analysis, provenance, and graph view. Antony implements a protected demo edge mutation/reset; Alen implements idempotent revised-document ingestion; Abhishikth exposes re-query paths; Arnold designs a legible before/after presentation.

**Day 3 (Oct 17):** verify the graph mutation actually changes an answer and that updating Architecture Overview resolves the targeted freshness warning. Run golden queries, negative case, fresh-clone setup, and demo rehearsal. Only if all are stable: Abhishikth adds review-task preview/confirmed action, Arnold adds confirmation UI, Antony/Alen support evidence payloads.

**Oct 18:** submission/demo buffer; no new major feature. If P2 is unfinished, omit it. If live mutation is unstable, record deterministic before/after queries and keep core features reliable.

**Priority:** P0 graph-grounded core and causality proof; P1 freshness update; P2 confirmed action only as stretch.
