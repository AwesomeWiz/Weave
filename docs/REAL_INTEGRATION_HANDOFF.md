# Real FalkorDB integration handoff

Status: prepared, not verified against a real dataset. Antony's graph/tool and Alen's source/ingestion implementations are not present in the local checkout. Only `main` and `origin/main` refs were available during this review; remote branch availability was not checked. No teammate code, retrieval Cypher, or ingestion logic was implemented here.

## Contract review

Reviewed `04_KNOWLEDGE_GRAPH.md` (ontology and direction), `05_AI_GRAPHRAG_PIPELINE.md` (tool/context/provenance), `08_API_DESIGN.md` (generic response), `09_DATASET_INGESTION.md` (canonical records and chunks), and the implemented `PHASE1_IMPLEMENTATION.md` and `PHASE1_VERIFICATION.md`. Earlier planning examples are not necessarily the actual teammate interfaces.

The public `/api/query` object stays unchanged: `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`. No production component was refactored in this preparation pass. Existing citation validation, accepted-decision grounding, independent health probes, sanitized errors, and explicit mode selection remain in place.

The trusted `WEAVE_GRAPH_FACTORY=module:factory` returns the existing async `GraphGateway`. It may compose Antony's graph tool and Alen's source store independently; neither needs to import the development fixture. `test_adapter_contract.py` exercises that composition through the actual factory loader and HTTP endpoint with independent offline test doubles. Those tests do not establish database connectivity.

| Upstream evidence | Existing adapter field | Required mapping |
| --- | --- | --- |
| Antony's nodes/edges, whether nested or in a proposed `ToolResult` | `TraceResult.graph.nodes/edges` | Preserve canonical IDs, labels, properties, relationship direction and parallel-edge IDs. Map explicitly; do not pass a different outer envelope through unchanged. |
| Selected decisions | `TraceResult.decision_ids` | Include canonical Decision IDs. D-007 must carry `properties.status = "accepted"` for the primary accepted rationale. |
| Retrieval identifiers | `TraceResult.source_ids` | Exact returned citation IDs, including chunk IDs when returning individual chunks. |
| Alen's full canonical record | `Source.id`, `type`, `title`, `snippet`, `timestamp`, `url` | Preserve record ID and source content; `type` is the display ontology type. Do not synthesize a source from a graph label. |
| Alen's individual chunk | `Source.id`, `snippet` | Preserve the canonical **chunk** ID and chunk text. Never collapse multiple chunks to one parent ID. |
| Chunk provenance | `Source.metadata` | Preserve `chunk_id`, `source_id`, `source_type`, `chunk_index`, plus available dataset revision/provider provenance. Keep native `source_type` unchanged even if it differs from the display ontology type. |
| Source-to-entity linkage | `Source.entity_ids` | Include the canonical parent evidence node and any actually established links. A rationale chunk must be explicitly linked to D-007; do not infer that link from its prose. |

The planning pipeline describes `find_sources(entity_ids)`, while the implemented boundary accepts exact `source_ids`. This is an explicit translation point, not an interchangeable parameter name. If Alen resolves parent IDs to several chunks, the small composition adapter must resolve those IDs and place the actual chunk IDs into `TraceResult.source_ids` before context building (or use an agreed authoritative full-record representation). Unrequested chunks are intentionally excluded. Do not loosen that guard or relabel chunks to make them pass.

`Source.metadata` survives the HTTP response; citations use `Source.id`. Source metadata is intentionally omitted from LLM context, which retains IDs, excerpts, entity links, timestamps and paths. Context trims excerpts to 1,600 characters and sanitizes URLs; the smoke test accounts for those existing transformations. Two ADR chunks with distinct IDs remain distinct sources. Sources must link to returned graph entities, but rendering chunk nodes is not mandatory.

The ontology permits either `Decision IMPLEMENTED_BY Commit` or `Commit IMPLEMENTS_DECISION Decision`, and either `Decision SUPPORTED_BY Issue` or `Issue LED_TO Decision`. The smoke test accepts those documented alternatives without reversing them. The current deterministic summary explicitly narrates `IMPLEMENTED_BY`; a trace containing only its inverse still preserves the graph and source, but does not add that implementation sentence. Inspect Antony's actual output before deciding whether that small narration addition is needed.

## Focused real smoke test

`backend/tests/test_real_integration.py` is opt-in. When enabled, missing prerequisites fail the test rather than quietly skipping or substituting fixture data. The test performs no writes, seeding, or ingestion and disables LLM generation to isolate graph/source integration.

It requires:

- Actual configured FalkorDB and graph-tool health, with real mode forced.
- Accepted `decision:D-007`, Payment Service `USES` Redis, and the decision's `AFFECTS` / `INTRODUCES` paths.
- INC-17 `LED_TO` PAY-42, issue support for D-007, the payment-perf-7 discussion/support link, ADR-7 documentation, and the 8fae2 implementation link. Both short and full canonical commit IDs are accepted, with no ambiguous prefix match.
- Retrieved source records or provenance-linked chunks for PAY-42, payment-perf-7, ADR-7 and commit 8fae2, with nonempty text matching an independent seeded-corpus export.
- Preserved IDs, title/type, timestamps, parent/chunk provenance and metadata, accounting for existing excerpt truncation and URL sanitation.
- No `development_fixture` provenance, and no instantiation of `FixtureGateway`.

The test also requires `WEAVE_REAL_EVIDENCE_MANIFEST`, a **test-only** JSON export reviewed against Alen's actual seeded source corpus. This is not an API input, ingestion format, or application data fallback. It supplies an independent expected-content check so expected-looking IDs alone cannot pass. Do not generate it from `/api/query`, copy the development fixture, or create invented evidence to make the test pass.

Export structure:

```json
{
  "graph_name": "novapay",
  "dataset_revision": "<actual seed revision or content hash>",
  "sources": []
}
```

The empty `sources` list above is a template: the real file must contain Source objects and an actual dataset revision. Include the authoritative originals for every source the focused trace returns. For each chunk, include its original text as `snippet`, exact ID, canonical parent in `entity_ids`, and the provenance metadata described above. Real seeded NovaPay is itself a synthetic demo corpus; that is valid. The prohibited substitute is the application development fixture.

PowerShell, after installing the teammate adapter and seeding using their instructions:

```powershell
$env:WEAVE_GRAPH_MODE = 'falkordb'
$env:WEAVE_GRAPH_FACTORY = '<actual.module>:<actual_factory>'
$env:WEAVE_REAL_EVIDENCE_MANIFEST = '<path-to-reviewed-seeded-source-export.json>'
$env:WEAVE_RUN_REAL_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_real_integration.py -v
Remove-Item Env:WEAVE_RUN_REAL_INTEGRATION
```

Set the real host, port, graph name and credentials in the ignored `.env` as documented in README. The test overrides fixture mode even if a development shell or `.env` selected it. No real test has passed yet. An export is a trusted test oracle, not a proof of database origin by itself; the actual adapter must also be inspected to confirm it queries the configured seeded graph/source store.

## Blockers and next integration steps

| Blocker | Needed to resolve |
| --- | --- |
| Antony's interface unavailable | Branch/commit, module and function signature, returned types, canonical IDs, direction conventions, timeout/readiness behavior. Inspect actual code before writing the thin mapping. |
| Alen's retrieval interface unavailable | Branch/commit, exact parent/chunk ID format, record schema, provenance fields, lookup semantics and seed/retrieval entry points. |
| Seeded runtime and independent expected evidence unavailable | Actual graph configuration, seed revision, authoritative source/chunk export for the primary trace. |

When branches are available: inspect their interfaces and AGENTS instructions; add only the composition/normalization needed at the existing factory boundary; reconcile actual IDs with these documented contracts rather than guessing; run the full offline backend suite and frontend checks; run the opt-in test against their seeded database; repeat the primary browser workflow in real mode. Record commit/seed revisions, results and any remaining failures in `PHASE1_VERIFICATION.md`. Do not mark real integration complete from offline doubles, health alone, or skipped acceptance checks.
