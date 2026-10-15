# Weave — AI and GraphRAG Pipeline

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

## 1. Objective

Use an LLM as an explanation layer on top of graph-derived context, not as the source of organizational facts.

The pipeline combines:

- entity resolution
- graph traversal
- semantic retrieval
- source provenance
- bounded agent tools
- grounded generation

## 2. Ingestion pipeline

```text
GitHub-like data   Jira-like data   Slack-like data   Docs/ADRs
       \                |                 |              /
        +---------------+-----------------+-------------+
                                |
                                v
                         Record Normalizer
                                |
                                v
                    Canonical Entity Extraction
                                |
                 +--------------+---------------+
                 |                              |
                 v                              v
         Graph nodes/edges                 Source chunks
                 |                              |
                 +---------------+--------------+
                                 |
                                 v
                         Embedding generation
                                 |
                                 v
                             FalkorDB
```

## 3. Query pipeline

```text
User question
     |
     v
Intent / tool routing
     |
     +--> Decision Trace
     +--> Expert Finder
     +--> Impact Analysis
     +--> Freshness Check
     +--> Semantic Search
     |
     v
FalkorDB retrieval
     |
     v
Evidence + paths + source chunks
     |
     v
Context Builder
     |
     v
Grounded LLM prompt
     |
     v
Answer + citations + graph payload
```

## 4. Tool-routing strategy

Use simple intent rules first. Upgrade to LLM tool selection only after deterministic paths work.

Example routing hints:

- “why”, “decision”, “chose”, “introduced” → `trace_decision`
- “who knows”, “expert”, “who should I contact”, “owner” → `find_expert`
- “what breaks”, “affected”, “depends on”, “remove” → `impact_analysis`
- “outdated”, “stale”, “current”, “up to date” → `find_stale_knowledge`
- broad factual question → `semantic_search` plus related graph expansion

A question may invoke multiple tools.

Example:

> “Why does Payment Service use Redis, who made the decision, and what would be affected if we removed it?”

Plan:

1. `trace_decision(Payment Service, Redis)`
2. `find_expert(Payment Service)` or read participants/owners from step 1
3. `impact_analysis(Redis or Payment Service)`
4. merge evidence
5. generate one answer

## 5. Required agent tools

### `trace_decision(topic_or_entity)`

Returns:

- Decision entities
- cause/problem entities
- participants/approvers
- supporting source records
- implementing commits
- affected services/technologies
- evidence subgraph

### `find_expert(entity)`

Returns:

- ranked people
- graph-derived score components
- evidence for each candidate

### `impact_analysis(entity)`

Returns:

- direct dependencies/dependents
- downstream affected services
- teams/owners
- relevant issues/incidents
- graph payload

### `find_stale_knowledge(entity)`

Returns:

- documents describing the entity
- later decisions/architecture-changing commits
- staleness reason

### `semantic_search(query)`

Returns:

- top source chunks
- source metadata
- linked entities

### `find_sources(entity_ids)`

Returns authoritative evidence records used for citations.

## 6. Semantic retrieval

Semantic retrieval helps map natural-language questions to relevant parts of the graph and source corpus.

Preferred approach:

- chunk text-bearing sources
- generate embeddings
- store embeddings with Chunk nodes or SDK-managed retrieval structures in FalkorDB
- retrieve semantically similar chunks
- expand from chunks to connected entities/relationships

The semantic result is a starting point, not the final answer.

## 7. Embedding model decision

The team already has experience with BAAI BGE embeddings from EKOS.

Preferred default:

- local BGE model if integration is working early on Day 1

Fallback:

- a provider supported cleanly by the chosen FalkorDB GraphRAG SDK path

Do not spend hours preserving a specific embedding model if it blocks the graph-native features.

## 8. LLM decision

Preferred local option:

- Qwen via Ollama

Advantages:

- team familiarity
- no external API dependency
- private/local demo capability

Risk:

- latency and tool-calling behavior may vary by local hardware/model size

Therefore implement an LLM interface such as:

```python
class LLMProvider:
    async def generate(self, messages: list[dict]) -> str:
        ...
```

This allows a hosted fallback without rewriting the pipeline.

## 9. Prompt contract

System behavior:

- use only supplied evidence
- do not invent company facts
- distinguish direct evidence from inference
- include source IDs/titles
- when evidence is insufficient, say so
- answer the user's actual question before adding explanation

Suggested prompt structure:

```text
ROLE
You are Weave, an organizational decision-intelligence assistant.

RULES
- Use only EVIDENCE below for company-specific claims.
- Preserve IDs and names exactly.
- Explain important relationships when they matter.
- If the evidence does not support a claim, say that the evidence is insufficient.

QUESTION
{question}

GRAPH FINDINGS
{graph_findings}

SOURCES
{source_chunks}

OUTPUT
1. Direct answer
2. Why / evidence chain
3. Impact or expert information if requested
4. Source references
```

## 10. Context builder

The Context Builder should:

- prioritize entities returned by explicit graph tools
- include only useful text snippets
- remove duplicate messages/chunks
- keep timestamps and source identifiers
- limit evidence to a manageable size
- attach relationship paths separately from prose snippets

Suggested internal object:

```json
{
  "entities": [],
  "paths": [],
  "snippets": [],
  "sources": []
}
```

## 11. Provenance model

Every claim shown in the demo should be traceable to one or more of:

- Issue
- Message/thread
- Document/ADR
- Commit
- Incident

The response object should preserve source IDs and graph paths even if the natural-language answer is concise.

## 12. Answer confidence

Do not invent a numeric probability unless it is calibrated.

Use simple statuses instead:

- `supported` — direct graph/source evidence
- `partially_supported` — incomplete evidence chain
- `insufficient_evidence` — retrieval did not support a reliable answer

## 13. Evaluation

Create 10–15 golden questions with expected key entities and paths.

Example metrics:

- expected Decision ID retrieved?
- correct key Person returned?
- expected dependency present?
- source evidence attached?
- hallucinated entity present?
- response understandable within 20–30 seconds?

A lightweight JSON test set is enough.

## 14. GraphRAG SDK usage

The FalkorDB GraphRAG SDK may be used for:

- document ingestion
- graph extraction
- semantic retrieval
- provenance helpers
- grounded-answer flows

However, the project's distinctive features should remain explicit:

- Decision Trace
- Expert Finder scoring
- Impact Analysis
- Knowledge Freshness

Those should be backed by documented graph queries/algorithms that the team understands.

## 15. Failure handling

If entity resolution fails:

- return closest known entities or ask the user to rephrase

If graph traversal finds no support:

- fall back to semantic search
- do not fabricate a graph path

If LLM generation fails:

- return structured graph findings and sources so the core product still demonstrates value

This is especially important in a live hackathon demo.

---

## Before/after correctness checks

- Run the same question before and after the demo graph mutation; verify graph paths, cited IDs, and natural-language claims agree.
- After a document update, run the same freshness tool again and verify the prior warning disappears only when its timestamp-based reason no longer applies.
- Include one unsupported question and require `insufficient_evidence`; do not invent missing paths.
- A review-task preview must be derived from graph-tool output; user confirmation is required for any write action.
