# Weave — Project Context

**Project:** Weave  
**Hackathon:** Graph Hacks: Context for AI Agents  
**Primary Track:** Track 3 — Company Brain  
**Team Size:** 4  
**Status:** Pre-hackathon planning only. Main coding and design implementation begins after the official hackathon start.

## 1. One-line idea

**Weave is a company decision-intelligence agent that connects people, code, tickets, conversations, documents, services, incidents, and decisions in FalkorDB so users can ask not only _what happened_, but _why it happened, who knows about it, what evidence supports it, and what will be affected next_.**

## 2. Problem

Company knowledge is fragmented across tools such as GitHub, Jira, Slack, and internal documentation. Conventional search can retrieve matching text, but the difficult questions are relational:

- Why was a technology or architecture choice made?
- Which incident or ticket led to that decision?
- Who made, discussed, or implemented it?
- Who is the best person to contact now?
- Which services and teams would be affected by a change?
- Which documents may have become outdated after later changes?

The answer usually does not live in one document. It exists across a chain of connected evidence.

## 3. Product thesis

Company knowledge is not merely a collection of documents. It is a network of **people, decisions, systems, events, and evidence**.

Weave models that network directly in FalkorDB and gives an AI agent explicit graph tools to traverse it. The graph is therefore not a visualization layer added after retrieval; it is the system that produces the answer.

## 4. Primary user

The primary demo persona is a software engineer or engineering lead joining or maintaining a complex product.

Typical situation:

> “I need to change the Payment Service. I can find code and docs, but I do not know why Redis was introduced, who owns the decision, whether the docs are current, or what depends on it.”

Weave should answer that in one workflow.

## 5. Core capabilities

### Decision Trace
Trace a technical or business decision back through the issue, incident, discussion, document, people, and implementation that produced it.

### Expert Finder
Rank people with evidence based on their relationship to a service, repository, issue, decision, document, and recent work.

### Impact Analysis
Traverse dependencies to show what services, projects, teams, repositories, and owners may be affected by a proposed change or failure.

### Knowledge Freshness
Detect documentation that may be stale because a later architecture-changing decision, commit, or incident affected the same system.

### Sourced GraphRAG Answers
Generate natural-language answers only after graph/vector retrieval and attach the supporting evidence path and sources.

## 6. Primary demo question

> **Why does the Payment Service use Redis, who made that decision, and what would be affected if we removed it?**

Expected reasoning path:

`Incident → Issue → Slack discussion → Decision → Person → Commit → Repository → Payment Service → Redis → dependent services → owners`

A judge should be able to see the path behind the answer.

## 7. Secondary demo questions

- Who knows the Payment Service best, and why?
- Which teams would be affected if the Auth Service went down?
- What evidence supports the decision to introduce Redis?
- Which architecture documents may now be outdated?
- Which unresolved issue is connected to the most critical service dependency?

## 8. Technical direction

```text
GitHub / Tickets / Chat / Docs / Synthetic Dataset
                    |
                    v
          Normalization + Extraction
                    |
                    v
                FalkorDB
     Graph + source chunks + embeddings
                    |
       +------------+-------------+
       |            |             |
       v            v             v
  Cypher tools   semantic      provenance
                retrieval       traversal
       \            |             /
        \           |            /
         +----- Agent / GraphRAG -----+
                       |
                       v
                       LLM
                       |
                       v
             FastAPI response layer
                       |
                       v
          React answer + evidence graph
```

Preferred stack:

- Frontend: React + TypeScript + Vite + Tailwind
- Backend: FastAPI + Python
- Primary knowledge store: FalkorDB
- Graph query language: Cypher
- GraphRAG: FalkorDB GraphRAG SDK where it saves time, plus custom Cypher tools for differentiating features
- LLM: provider abstraction; Qwen via Ollama is acceptable for local development
- Embeddings: local BGE is preferred if integration is reliable; otherwise use a compatible provider that minimizes hackathon risk

## 9. Design principles

1. **FalkorDB must be indispensable.** Removing it should break Decision Trace, Expert Finder, Impact Analysis, provenance, and GraphRAG retrieval.
2. **Every important answer must be explainable.** Surface sources and graph paths.
3. **Prefer one excellent workflow over a broad enterprise suite.**
4. **Use synthetic/public/owned data only.**
5. **Keep the demo deterministic.** Prepare a small but richly connected company dataset.
6. **Build one vertical slice first.** By the end of the first build day, one query must work end-to-end.
7. **Do not rebuild EKOS.** Reuse lessons, not the existing product implementation.

## 10. Scope for the hackathon

### Must have

- FalkorDB-based graph model
- Ingestion of at least three company knowledge types
- Decision Trace
- Expert Finder
- Impact Analysis
- Sourced answers with evidence
- Interactive evidence graph or graph-path view
- Public repository and reproducible setup
- Demo video

### Should have

- Knowledge Freshness
- Incremental re-ingestion of the synthetic dataset
- Golden-query evaluation set
- Simple graph statistics/status panel

### Could have

- Track 1 extension: create a GitHub issue after a user confirms an impact-analysis action
- Persistent agent/session memory
- Additional connector

### Explicit non-goals

- Full enterprise RBAC
- Production multi-tenancy
- Kubernetes
- Enterprise admin dashboard
- Six or more connectors
- Multimodal ingestion
- Large multi-agent system
- Full workflow automation
- Building both Neo4j and ChromaDB alongside FalkorDB

## 11. Winning narrative

**Weave — Trace the why behind every company decision.**

Pitch:

> Company knowledge is not a folder of documents; it is a chain of decisions. Weave builds that chain in FalkorDB, then lets an agent follow it to explain why something happened, who knows about it, what depends on it, and exactly which evidence supports the answer.

## 12. Source-of-truth rule

If project discussions conflict, use the documents in this folder in this order:

1. `01_HACKATHON_BRIEF.md` for rules and event constraints
2. `02_WEAVE_PRD.md` for product scope
3. `04_KNOWLEDGE_GRAPH.md` for ontology
4. `03_ARCHITECTURE.md` and `05_AI_GRAPHRAG_PIPELINE.md` for implementation direction
5. `06_TEAM_PLAN.md` for ownership
6. `07_DEMO_PLAN.md` for presentation behavior
7. `08_API_DESIGN.md` and `09_DATASET_INGESTION.md` for implementation contracts
8. `10_SUBMISSION_CHECKLIST.md` for final delivery

If a technical decision changes during the event, update the relevant document rather than letting the agreed architecture live only in chat.

---

## Winning-demo refinements (October 15 update)

1. **Graph causality proof (priority P0):** update one explicit FalkorDB relationship and re-run a golden query; answer, citations, and focused subgraph must change consistently. Restore seed afterward.
2. **Live freshness update (priority P1):** show an older architecture document flagged for review, ingest its revised version, and demonstrate the warning resolving. Never claim timestamps alone prove correctness.
3. **Confirmed action (priority P2, optional):** after impact analysis, offer a user-confirmed review task containing affected services, owners, and evidence IDs. A local review-task record is an acceptable fallback; an external GitHub issue is optional and must never be created without confirmation.

**Scope gate:** Do not implement P2 until Decision Trace, Expert Finder, Impact Analysis, source citations, graph UI, and golden queries are stable. Do not sacrifice submission quality or the October 18 buffer.
