# Weave — Demo Plan

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Target length:** 2–3 minutes for the core demo  
**Goal:** Make the graph's value obvious before discussing implementation details.

## 1. Demo company

Use the fictional company **NovaPay**.

NovaPay operates a payment platform with:

- Checkout Service
- Payment Service
- Auth Service
- Notification Service

Teams:

- Payments
- Platform
- Identity

The dataset should contain enough cross-linked records to create realistic evidence paths without overwhelming the UI.

## 2. Demo story

A developer joins NovaPay and is assigned a Payment Service change.

They see Redis in the architecture but do not know:

- why it exists
- who chose it
- what problem led to it
- where the decision was discussed
- which commit implemented it
- what would break if it were removed
- whether the current docs still reflect reality

Normally they would search code, Jira, Slack, and docs separately.

With Weave, they ask one question.

## 3. Opening line

> “Company knowledge is usually stored as documents, tickets, chat messages, and code. But the questions employees actually ask are about the connections between them. Weave turns those connections into a graph an AI agent can reason over.”

## 4. Demo query 1 — Decision Trace

Ask:

> **Why does Payment Service use Redis?**

Expected answer structure:

1. Payment timeout incident occurred.
2. PAY-42 was created to address latency.
3. The team discussed caching in a Slack thread.
4. Decision D-007 approved Redis.
5. ADR-7 documented the choice.
6. Commit `8fae2` implemented it in the payments repository.

UI behavior:

- concise answer on left
- source cards below/alongside
- evidence graph on right
- highlight path from incident to decision to commit/service

Judging message:

> “This is not six independent search results. FalkorDB gives us the path connecting the problem, discussion, decision, implementation, and system.”

## 5. Demo query 2 — Expert Finder

Ask:

> **Who should I talk to before changing Payment Service?**

Expected result:

- Alice ranked first because she approved/participated in the Redis decision, authored relevant work, and has recent Payment Service activity
- Ravi ranked second because of recent commits/issues
- show score reasons, not only names

Judging message:

> “The LLM is not guessing who sounds senior. The ranking comes from graph relationships.”

## 6. Demo query 3 — Impact Analysis

Ask:

> **What would be affected if we removed Redis from Payment Service?**

Expected graph:

- Redis used by Payment Service
- Checkout Service depends on Payment Service
- Payments team owns Payment Service
- related issue/incident may indicate performance risk

If the synthetic data includes additional downstream services, show only the first 2–3 hops.

Judging message:

> “Impact is a traversal problem. The graph can follow dependencies and ownership directly.”

## 7. Demo query 4 — Knowledge Freshness

Ask:

> **Are the Payment Service architecture docs current?**

Expected result:

- `Architecture Overview` last updated before D-007 / architecture-changing commit
- `ADR-7` reflects the Redis decision
- older overview flagged as a **candidate for review**

Judging message:

> “Weave connects documents to the systems they describe and changes that happened later, so it can identify knowledge that may be stale.”

## 8. Combined killer query

If the system reliably handles multi-tool routing, finish with:

> **Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?**

This demonstrates Decision Trace + expertise + impact in one interaction.

Do not use the combined query first unless latency and reliability are excellent.

## 9. Evidence graph UX

The graph shown to judges should be a **focused subgraph**, not the full database.

Node labels should be visually distinguishable by type.

Important interactions:

- hover/click shows metadata
- clicking a source-bearing node opens snippet/details
- current reasoning path is emphasized
- unrelated nodes are excluded

The graph must be readable on a laptop screen during screen recording.

## 10. Golden dataset requirements

Minimum useful dataset:

- 6–10 people
- 3 teams
- 4 services
- 3 repositories
- 12–20 commits
- 10–15 issues
- 20–30 chat messages or compacted thread messages
- 6–10 documents/ADRs
- 5–7 decisions
- 3 incidents
- 4–6 technologies

Quality matters more than count. Each core feature needs at least one excellent evidence chain.

## 11. Golden questions

Prepare and test at least these:

1. Why does Payment Service use Redis?
2. What incident led to the Redis decision?
3. Who approved the Redis decision?
4. Which commit implemented D-007?
5. Who knows Payment Service best?
6. Why is Alice ranked above Ravi?
7. What depends on Payment Service?
8. What could be affected if Payment Service fails?
9. Which documents describe Payment Service?
10. Which of those documents may be stale?
11. What is the source for the claim that Redis was introduced for latency?
12. What evidence is missing for an intentionally unsupported question?

## 12. Negative demo case

Include one question the data cannot answer, for example:

> “Why did NovaPay choose MongoDB for the fraud service?”

If no such service/decision exists, Weave should say it does not have sufficient evidence.

This demonstrates grounding better than confidently answering everything.

## 13. Technical explanation after the demo

Keep it short:

> “We normalize tickets, chat, docs, code, incidents, and decisions into FalkorDB. The agent calls bounded Cypher tools for decision tracing, expertise, impact, and freshness, then combines those paths with semantically retrieved source chunks. The LLM only explains the evidence. The frontend shows the exact subgraph behind the answer.”

## 14. What not to show

Avoid spending demo time on:

- login screens
- CRUD admin pages
- setup terminal logs
- giant graph overview
- every API endpoint
- generic chat questions
- long architecture lectures before proving the product

## 15. Recording checklist

Before recording:

- reset and reseed graph
- run every golden query once
- clear accidental test data
- hide secrets/tokens
- close unrelated tabs/windows
- ensure font size is readable
- use deterministic query wording
- have local fallback running even if cloud deployment exists
- keep a prepared backup recording if allowed by submission workflow

## 16. Closing line

> **“Search tells you where information is. Weave tells you how the company got here.”**

---

## Revised 2–3 minute judging sequence

1. **0:00–0:20 — Problem:** fragmented code, issues, chat, and documentation; show Weave immediately.
2. **0:20–1:05 — Decision Trace:** ask why Payment Service uses Redis; reveal incident → issue → discussion → decision → commit, with source IDs and a readable subgraph.
3. **1:05–1:35 — Impact / graph causality:** show Checkout depending on Payment Service, then change the *actual FalkorDB* `DEPENDS_ON` edge in a protected demo control and re-run the same query. The answer and graph must change. Restore the seed.
4. **1:35–2:10 — Live freshness:** show Architecture Overview flagged as review candidate because it predates D-007; ingest the updated overview; re-query and show that specific warning disappear.
5. **2:10–2:35 — Expert Finder + sources:** show an evidence-backed person ranking. If the demo is running long, keep this as a brief pre-recorded segment.
6. **2:35–3:00 — Optional confirmed action / close:** preview a graph-derived review task and require user confirmation; include only if implemented and stable. Close: “Search tells you where information is. Weave tells you how the company got here.”

**Fallback:** prioritize working Decision Trace, Impact Analysis, source provenance, and visible FalkorDB dependence. Never simulate database updates with hardcoded UI output. Rehearse reset/seed and ensure no mutation affects later queries.
