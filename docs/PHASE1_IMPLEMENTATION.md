# Phase 1 integration contract

This document records the implemented scope. The user's Phase 1 task and follow-up explicitly authorize development fixtures and reserve graph/Cypher/data implementation for the teammate. Existing ontology remains authoritative. Broader features in older planning documents remain out of scope.

## HTTP contract

`POST /api/query` accepts `question` (trimmed, 1–2,000 characters) and optional `session_id` (maximum 128). Unknown fields are rejected. Sessions are not persisted or used as model memory.

Success returns the direct object specified in `08_API_DESIGN.md`: `answer`, `support_status`, `tools_used`, `sources`, `graph: {nodes, edges}`, and `metadata`. Additive metadata fields are `graph_mode`, `generation`, and `warnings`, alongside `latency_ms`. The matching Pydantic and TypeScript types live in `backend/app/models.py` and `frontend/src/types.ts`.

Errors use `{ "ok": false, "error": { "code": "...", "message": "..." } }`:

| HTTP | Code | Meaning |
| --- | --- | --- |
| 422 | INVALID_REQUEST | Invalid question/session/request shape |
| 503 | GRAPH_UNAVAILABLE | Missing factory, unavailable tool, or failed real graph retrieval |
| 502 | GRAPH_CONTRACT_ERROR | Malformed trace/source payloads, conflicting IDs, dangling edges, or oversized subgraph |
| 500 | INTERNAL_ERROR | Sanitized unexpected failure |

Unsupported questions return HTTP 200 with `insufficient_evidence`, empty graph/sources, and no tool invocation. The Phase 1 route supports decision/rationale/evidence questions naming Payment Service and Redis, plus the explicit screenshot alias “Why was Redis introduced?”. It does not infer conversational context or silently answer an impact request with a decision trace.

`GET /api/health` returns `status`, `backend`, `falkordb`, `graph_tool`, `llm`, `graph`, and `graph_mode`. Real-mode critical graph failures return 503. Fixture mode returns 200 with `status: degraded`, `graph_tool: fixture`, and `falkordb: not_checked`. LLM disabled is distinct from unavailable; neither removes the deterministic answer path.

## Teammate adapter

See [REAL_INTEGRATION_HANDOFF.md](REAL_INTEGRATION_HANDOFF.md) for the reviewed source/chunk ID mapping, current blockers, and the focused real-database acceptance test. Actual teammate signatures still require inspection when their branches arrive.

Configure a trusted local `module:factory` in `WEAVE_GRAPH_FACTORY`. Install the teammate package into the backend environment or make it importable. The factory receives `Settings` and returns three async methods:

```python
from app.config import Settings
from app.models import Source, TraceInput, TraceResult

class TeamAdapter:
    async def health(self) -> bool:
        # Execute a bounded readiness check through the actual graph tool/client.
        ...

    async def trace_decision(self, query: TraceInput) -> TraceResult:
        # Call the teammate's resolver/tool with query.service and query.technology.
        # Normalize the result into TraceResult, preserving IDs and edge directions.
        ...

    async def find_sources(self, source_ids: list[str]) -> list[Source]:
        # Retrieve actual graph-linked source records, not entities relabeled as sources.
        ...

def create_gateway(settings: Settings):
    # Configure the teammate's client here using settings.falkordb_* and graph_name.
    return TeamAdapter()
```

This is an interface example, not an implemented graph tool. To wrap synchronous teammate functions, use `await asyncio.to_thread(...)` and configure socket/query timeouts in that client. Do not perform blocking network work directly in an async method. The wrapper bounds trace retrieval to 15 seconds, sources to 10 seconds, and tool health to 4 seconds. Settings are operator-owned, never request-controlled. No credentials enter responses.

`TraceResult` contains:

```json
{
  "graph": {"nodes": [], "edges": []},
  "source_ids": [],
  "decision_ids": [],
  "warnings": []
}
```

Nodes require `id`, `type` (canonical ontology label, e.g. `Service`), `label` (display name), and `properties`. Edges require `id`, `source`, `target`, `type`, and `properties`. Prefer `source|TYPE|target` stable IDs where the graph contract uses one edge per typed endpoint pair. Preserve existing stable IDs for parallel relationships. Do not invert directions to match screenshot art.

Accepted decision nodes should include `properties.status = "accepted"`. Service and technology display labels must match the resolved `TraceInput` names; keep original canonical IDs independently. A focused trace is capped at 30 nodes, 80 edges, and 20 deduplicated sources. Aim for 8–15 nodes. A contract violation fails explicitly instead of silently dropping evidence.

Sources require `id`, `type`, `title`, and a nonempty `snippet`; optional `url`, `timestamp`, `entity_ids`, and `metadata`. `entity_ids` links a source whose ID differs from its evidence node. A source is attached only when requested in `source_ids` and linked to a returned entity. Preserve canonical source IDs, source-native timestamps, provenance metadata, and real URLs. Unsafe, credential-bearing, or `.invalid` URLs are removed. Unavailable external URLs show an inspectable local excerpt without a broken link.

Narrative citations resolve through `entity_ids` when source IDs differ from graph node IDs. Citations preserve the source-native ID; an exact source/node ID match is preferred when present.

The `SourceRetriever` protocol is separate so the adapter can delegate source retrieval to a different implementation. Retrieval failure retains the graph, returns no fabricated sources, and downgrades support. Malformed source payloads instead return a sanitized `GRAPH_CONTRACT_ERROR`.

## Grounding

Context normalization removes duplicate identical nodes/edges and source records, preserves directed paths and IDs, rejects conflicting IDs/dangling edges, merges source metadata, and limits each excerpt to 1,600 characters. The prompt omits irrelevant node properties but keeps every returned relationship and canonical ID.

`supported` requires an accepted Decision with explicit `AFFECTS` to the requested Service, `INTRODUCES` to the requested Technology, and `Service USES Technology`, a retrieved rationale source, plus a graph-linked supporting/discussion/document source. A rationale source may link directly to the Decision under the existing contract, or via returned `Decision SUPPORTED_BY Issue/Message` and `Chunk FROM_ISSUE/FROM_MESSAGE Source` paths. The latter requires matching canonical parent IDs, source types, contributing chunk IDs/indexes and stored text; every contributing chunk must be present and linked in the graph. The ordered text must equal the retrieved excerpt after existing trimming/truncation. This derives an internal rationale lookup, not an additional graph edge or a changed `entity_ids` field. Citations retain actual parent source IDs. Missing requested sources downgrade to `partially_supported`. Other connected graph/source findings are partial; no usable sources or graph relationships are insufficient. Missing core rationale prevents LLM generation. Missing approval/implementation is never filled in; those claims appear only when corresponding edges exist.

The deterministic explanation copies the retrieved decision rationale and describes only actual approval, `LED_TO`, discussion, documentation, and implementation edges. It is not keyed to D-007, a person, a date, or a canned company answer. Removing the `INTRODUCES` edge changes support and removes the asserted rationale; this behavior has a focused test. Decisions not marked accepted cannot establish the current-use rationale. Decision status is included in model context.

Graph and LLM health probes are evaluated independently. A failed model probe reports degraded health and an unavailable LLM without marking a working graph unavailable.

Ollama receives graph/source evidence as data, strict grounding instructions and a JSON response schema. Unknown/mismatched source citations, uncited paragraphs, timeouts, and invalid responses trigger fallback. This does not guarantee model semantic fidelity; actual Qwen output still needs evaluation with the real dataset.

## Fixture boundary

`WEAVE_GRAPH_MODE=fixture` explicitly loads `backend/app/fixtures/novapay.development.json`. Its six synthetic source excerpts and 12 nodes are development application inputs. Unit test fixtures live in test files. Neither is a real ingestion result; no code seeds a database or labels fixture data as retrieved from FalkorDB.

`WEAVE_GRAPH_MODE=falkordb` never opens this JSON file. With no factory configured, queries return `GRAPH_UNAVAILABLE`. Database health uses the installed FalkorDB client to list graphs and execute only `MATCH (n) RETURN n.id LIMIT 1` read-only, with timeouts. This is readiness checking, not a second implementation of decision tracing.

## Implementation references

- [FalkorDB Python client API](https://falkordb-py.readthedocs.io/en/stable/falkordb.html): parameterized/read-only graph client methods.
- [Ollama chat API](https://docs.ollama.com/api/chat): non-streaming local generation and JSON response format.

The source-of-truth hierarchy in `00_PROJECT_CONTEXT.md` continues to apply to the teammate's ontology and graph implementation.
