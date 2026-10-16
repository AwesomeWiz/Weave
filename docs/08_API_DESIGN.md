# Weave — API Design

> **Implemented Phase 1:** `GET /api/health` and `POST /api/query` now use the direct response contract. See [PHASE1_IMPLEMENTATION.md](PHASE1_IMPLEMENTATION.md) for exact health codes, additive mode/generation metadata, source fields, the teammate graph adapter boundary, and explicit development fixture mode. Other endpoints below remain proposed, not implemented.

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

**Backend:** FastAPI  
**API style:** JSON REST for hackathon simplicity

## 1. Design principles

- Keep the frontend contract stable.
- Return graph evidence as structured data, not only prose.
- Make core graph tools independently testable.
- Preserve source IDs and URLs.
- Do not expose raw internal stack traces to the frontend.

## 2. Standard response envelope

Successful responses may use:

```json
{
  "ok": true,
  "data": {}
}
```

Errors:

```json
{
  "ok": false,
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Payment Service could not be resolved."
  }
}
```

For speed, endpoints may return the data object directly if the team prefers. Pick one convention early and keep it consistent.

## 3. `GET /api/health`

Purpose: verify backend and FalkorDB connectivity.

Response:

```json
{
  "status": "ok",
  "falkordb": "connected",
  "llm": "available",
  "graph": "novapay"
}
```

## 4. `POST /api/query`

Primary conversational endpoint.

Request:

```json
{
  "question": "Why does Payment Service use Redis?",
  "session_id": "demo-session"
}
```

Response:

```json
{
  "answer": "Redis was introduced after...",
  "support_status": "supported",
  "tools_used": ["trace_decision"],
  "sources": [
    {
      "id": "issue:PAY-42",
      "type": "Issue",
      "title": "Reduce payment latency",
      "snippet": "...",
      "url": "https://example.invalid/jira/PAY-42"
    }
  ],
  "graph": {
    "nodes": [],
    "edges": []
  },
  "metadata": {
    "latency_ms": 820
  }
}
```

`support_status` values:

- `supported`
- `partially_supported`
- `insufficient_evidence`

## 5. `POST /api/tools/decision-trace`

Useful for direct frontend shortcuts and testing.

Request:

```json
{
  "service": "Payment Service",
  "technology": "Redis"
}
```

Response:

```json
{
  "decision": {
    "id": "decision:D-007",
    "title": "Introduce Redis caching"
  },
  "causes": [],
  "people": [],
  "implementation": [],
  "sources": [],
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

## 6. `POST /api/tools/expert-finder`

Request:

```json
{
  "entity": "Payment Service",
  "limit": 5
}
```

Response:

```json
{
  "entity": "Payment Service",
  "experts": [
    {
      "person": {
        "id": "person:alice",
        "name": "Alice Menon"
      },
      "score": 17,
      "reasons": [
        "Approved Decision D-007",
        "3 recent commits affecting Payment Service",
        "Authored ADR-7"
      ]
    }
  ],
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

The score is an internal heuristic, not a universal expertise metric. Always expose reasons.

## 7. `POST /api/tools/impact-analysis`

Request:

```json
{
  "entity": "Payment Service",
  "max_depth": 3
}
```

Response:

```json
{
  "target": {
    "id": "service:payment-service",
    "type": "Service",
    "name": "Payment Service"
  },
  "affected": [],
  "owners": [],
  "risks": [],
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

Clamp `max_depth` server-side to a safe small range.

## 8. `POST /api/tools/freshness`

Request:

```json
{
  "entity": "Payment Service"
}
```

Response:

```json
{
  "documents": [
    {
      "document": {
        "id": "doc:architecture-overview",
        "title": "Architecture Overview"
      },
      "status": "review_recommended",
      "reason": "Decision D-007 was accepted after this document was last updated.",
      "evidence": ["decision:D-007"]
    }
  ]
}
```

## 9. `GET /api/graph/entity/{entity_id}`

Returns a single entity and a small neighborhood for UI expansion.

Query params:

- `depth=1`
- optional `relationship_types`

Do not allow unlimited graph expansion.

## 10. `POST /api/ingestion/seed`

Development/demo endpoint to load the included NovaPay dataset.

Response:

```json
{
  "status": "seeded",
  "nodes_created": 120,
  "relationships_created": 260
}
```

Protect or disable this endpoint in a public deployment if necessary.

## 11. `POST /api/ingestion/reset`

Development-only endpoint to reset the demo graph.

Avoid exposing this publicly unless protected by a secret/admin mechanism.

## 12. Graph payload contract

Node:

```json
{
  "id": "decision:D-007",
  "type": "Decision",
  "label": "Introduce Redis caching",
  "properties": {
    "status": "accepted"
  }
}
```

Edge:

```json
{
  "id": "decision:D-007|AFFECTS|service:payment-service",
  "source": "decision:D-007",
  "target": "service:payment-service",
  "type": "AFFECTS",
  "properties": {}
}
```

Frontend visualization should depend only on this generic graph contract.

## 13. Internal tool interface

Suggested backend abstraction:

```python
@dataclass
class ToolResult:
    data: dict
    sources: list[dict]
    nodes: list[dict]
    edges: list[dict]

async def trace_decision(...) -> ToolResult:
    ...
```

All tools should return structured evidence before LLM generation.

## 14. Error codes

Suggested codes:

- `ENTITY_NOT_FOUND`
- `INSUFFICIENT_EVIDENCE`
- `GRAPH_UNAVAILABLE`
- `LLM_UNAVAILABLE`
- `INGESTION_FAILED`
- `INVALID_REQUEST`

If the LLM is unavailable but graph retrieval succeeds, consider returning a structured non-LLM response rather than treating the whole request as failed.

---

## Demo update/action endpoints (proposed; finalize after implementation)

- `POST /api/demo/dependency-change` — protected, demo-only reversible change of a *predefined* FalkorDB dependency edge; return changed IDs. Avoid accepting arbitrary Cypher.
- `POST /api/demo/reset` — protected, restore deterministic seed. Disable both endpoints publicly unless authenticated.
- `POST /api/ingestion/document-update` — idempotently update a known synthetic document by canonical ID, content and timestamp; re-run freshness tool afterward.
- `POST /api/actions/review-task/preview` — return a proposed task title, affected services, owners, evidence IDs, and rationale from graph findings; no side effect.
- `POST /api/actions/review-task/confirm` — optional; explicitly confirmed creation of the previewed task. Use an idempotency key and return actual created status/ID; never claim success without persistence/provider acknowledgement.

These are proposed contracts, not claims of implemented endpoints. The original API remains authoritative until tested.
