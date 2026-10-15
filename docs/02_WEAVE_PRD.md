# Weave — Product Requirements Document

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Version:** 1.0 Hackathon Scope  
**Primary Track:** Company Brain  
**Product category:** Company decision intelligence / GraphRAG agent

## 1. Executive summary

Weave is an AI-powered company brain that turns fragmented organizational knowledge into a connected, explainable graph.

Instead of treating GitHub commits, issue tickets, chat discussions, documentation, incidents, people, and systems as isolated records, Weave models the relationships between them in FalkorDB. An AI agent can then follow those relationships to answer difficult organizational questions such as:

- Why was this architectural decision made?
- Who has the strongest evidence-backed expertise in this service?
- What would be affected if a dependency changed or failed?
- Which document may no longer reflect the system's current state?

The product combines graph traversal, semantic retrieval, provenance, and an LLM. The LLM explains retrieved evidence; FalkorDB determines how the evidence is connected.

## 2. Problem statement

Important company knowledge is distributed across multiple tools:

- source-code repositories
- issue trackers
- chat systems
- documents and architecture notes
- incident records

Search works well when a user knows the exact document or keyword. It performs poorly when the answer depends on connections across systems.

Example:

> A developer sees Redis in the Payment Service and wants to remove it. A code search may show where Redis is used, a ticket search may reveal an old performance problem, and chat may contain the discussion that produced the decision. None of those tools alone explains the complete chain.

The result is slow onboarding, repeated decisions, lost context, dependency risk, and reliance on tribal knowledge.

## 3. Product vision

Weave should act as an **evidence-backed organizational reasoning layer**.

It should not merely return matching passages. It should reconstruct the connected story behind company knowledge and expose that reasoning to the user.

## 4. Target users

### Primary

- software engineers
- engineering leads
- technical program managers
- platform/DevOps engineers

### Secondary

- product managers
- new employees onboarding into an existing system
- incident responders

The hackathon demo focuses on engineering knowledge because code, tickets, chat, architecture decisions, services, and incidents naturally form a strong graph.

## 5. Primary jobs to be done

### JTBD-1: Understand a decision

“When I encounter a technical choice I do not understand, show me why it exists and the evidence chain behind it.”

### JTBD-2: Find the right expert

“When I need help with a system, tell me who has actually worked on or decided things related to it, and explain the ranking.”

### JTBD-3: Estimate impact

“When I propose a change or a service fails, show me what depends on it and who needs to know.”

### JTBD-4: Detect stale knowledge

“When implementation or architecture changes, show me documentation that may no longer be current.”

## 6. Differentiation

Weave is not positioned as generic enterprise search or “chat with your documents.”

Its differentiator is **decision intelligence through connected evidence**.

Vector-only RAG can retrieve relevant text. Weave adds explicit organizational structure:

`Person → Decision → Issue → Discussion → Commit → Repository → Service → Dependency`

That allows deterministic traversal, explainable provenance, expertise ranking, and impact analysis.

## 7. Functional requirements

### FR-1 — Data ingestion

The system shall ingest company-like data from at least three source categories.

Hackathon baseline:

- GitHub-style repository/commit data
- Jira-style issue data
- Slack-style chat data
- Markdown documentation/ADRs

The primary demo uses synthetic normalized data to guarantee reproducibility.

### FR-2 — Entity and relationship construction

The system shall create normalized nodes and relationships in FalkorDB for people, teams, projects, systems, code, tickets, messages, documents, decisions, technologies, incidents, and source chunks.

### FR-3 — Decision Trace

Given a technology, service, or decision topic, the system shall return:

- the relevant Decision node
- preceding incident/issue/problem
- supporting discussion and documentation
- decision participants
- implementing commits/repositories
- evidence sources

### FR-4 — Expert Finder

Given a service/project/technology, the system shall rank people using graph evidence.

The ranking must be explainable through relationships such as:

- recent commits
- resolved issues
- authored documentation
- participation in relevant decisions
- relevant discussions
- ownership

### FR-5 — Impact Analysis

Given a service or technology, the system shall traverse dependency and usage relationships and return:

- directly affected entities
- downstream affected services/projects
- owners/experts
- relevant open issues/incidents where available

Traversal depth should be bounded to keep results interpretable.

### FR-6 — Knowledge Freshness

The system shall identify documents that are candidates for review when a later architecture-changing decision or implementation change affects the same system.

This feature should be described as a **staleness signal**, not a guarantee that a document is incorrect.

### FR-7 — Semantic retrieval

The system shall support semantic retrieval of source chunks so natural-language questions can locate relevant evidence before/alongside graph traversal.

### FR-8 — Sourced response generation

Every generated answer shall include clear source references and, for graph-native features, the evidence path used to produce the answer.

### FR-9 — Graph visualization

The frontend shall display the relevant evidence subgraph rather than the entire company graph.

Users should be able to inspect nodes and understand how the answer was derived.

### FR-10 — Query history within a session

The frontend should preserve the current session's questions and answers. Persistent long-term agent memory is optional and not required for Track 3.

## 8. Non-functional requirements

### NFR-1 — Explainability

Core conclusions must be traceable to graph paths and source records.

### NFR-2 — Reliability

The primary demo questions must produce deterministic or highly stable results.

### NFR-3 — Performance

Target interactive response time for graph-tool calls: under 2 seconds on the hackathon dataset where practical. End-to-end LLM response time may be longer depending on the selected model.

### NFR-4 — Reproducibility

A judge should be able to run the application locally using documented setup steps and the included synthetic dataset.

### NFR-5 — Privacy

No restricted company data should be required for the demo.

### NFR-6 — Simplicity

Avoid infrastructure that does not materially improve the demonstration.

## 9. Success criteria

Weave is demo-ready when all of the following are true:

1. A fresh install can load the synthetic company dataset into FalkorDB.
2. The primary demo question produces a coherent sourced answer.
3. Decision Trace displays a multi-hop evidence path.
4. Expert Finder returns a ranked list with reasons.
5. Impact Analysis returns downstream entities and owners.
6. The UI displays a readable evidence graph.
7. At least 10 golden questions are tested before recording the demo.
8. The team can explain the major Cypher queries without relying on generated notes.

## 10. Golden user story

A new engineer joins NovaPay and is assigned work on the Payment Service.

They ask:

> “Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?”

Weave should return a concise narrative such as:

- a timeout incident caused repeated payment latency
- issue PAY-42 tracked the problem
- a Slack discussion proposed Redis caching
- ADR/Decision D-007 approved the change
- Alice and Ravi were key participants
- commit `8fae2` implemented the cache
- Checkout depends on Payment Service
- the current architecture overview predates the decision and may need review

The UI then shows the evidence chain as a focused graph.

## 11. Out of scope

The hackathon version does not attempt to deliver:

- enterprise-grade authentication and RBAC
- complete SaaS multi-tenancy
- a production connector marketplace
- automated write-back to all enterprise tools
- enterprise governance/compliance workflows
- full analytics dashboards
- multimodal image/video knowledge ingestion
- large-scale benchmarking

These are valid future directions but should not compete with the core graph story during the event.

## 12. Relationship to prior EKOS work

The team previously explored enterprise connectors, semantic search, knowledge graphs, and GraphRAG in AEKOS/EKOS. Weave uses those lessons as background knowledge but intentionally changes the product focus and architecture:

- Weave centers the product around decisions and evidence paths.
- FalkorDB replaces the previous Neo4j + ChromaDB split for the hackathon knowledge layer.
- The product scope is narrowed from a broad enterprise knowledge platform to a small number of graph-native workflows.
- Implementation for the hackathon must be new work created during the official event window.

---

## Winning-demo acceptance criteria (2026-10-15 revision)

- **P0 — Graph causality:** an explicit change to a dependency/decision relationship in FalkorDB changes the corresponding impact/decision result and displayed evidence graph. Re-seeding restores the original result. Do not fake the change in frontend state.
- **P1 — Knowledge freshness:** seed an older Architecture Overview and newer decision/commit; mark it `review_recommended` with timestamps and supporting IDs. Re-ingest a revised overview dated after the change, re-query FalkorDB, and remove that specific warning. This is a *candidate for review* signal, not proof of document accuracy.
- **P2 — Confirmed follow-through (stretch):** from impact analysis, propose a review task with affected services, owners, evidence IDs, and a human-readable rationale. Show a confirmation step before creating it; record success/failure truthfully. Prefer a small local task record if GitHub integration threatens reliability.

**Non-goal remains:** general-purpose workflow automation. A single narrow confirmed action does not change Track 3 priority.
