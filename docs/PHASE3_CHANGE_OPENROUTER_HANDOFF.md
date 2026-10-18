# Phase 3 Stage 3: grounded Change presentation

## State and scope — October 18, 2026

Starting branch: `integration/phase3`, clean at `768857d839097d68d4c03099530834b4623074db` (`feat: implement Phase 3 Change Intelligence and Change Brief`). Stage 1 and Stage 2 were already committed at that point. Local `main` and `origin/main` remain `75e7f7c4c29b169d2737dcc1436ec0ae4953c742`; no fetch or merge was needed. These Stage 3 changes are uncommitted for review. No commit, push, deployment, or main update was performed.

Both stashes remain intact and unapplied:

- `stash@{0}`: `d3dc707e572f15650f4cb97ec09766dba5216ffb`
- `stash@{1}`: `f44b3ec6dc8ff51a3a61956bc12eeec2cf19aed3`

**Verification is offline only.** No live OpenRouter requests or provider probes were made. No live graph was launched, seeded, mutated, or used for Phase 3 acceptance. Earlier Phase 2 acceptance does not establish acceptance of this composition.

## Changed files

| File | Change |
| --- | --- |
| `backend/app/change_synthesis.py` | Minimal bounded Change packet and server-authored overview variants |
| `backend/app/change_intelligence.py` | Optional finite-plan selection after the existing validated deterministic computation |
| `backend/app/openrouter.py` | Change-specific instruction and selection method using the existing transport |
| `backend/app/main.py` | One shared Change runner for both endpoints |
| `backend/tests/test_change_openrouter.py` | 61 mocked presentation/provenance/failure regressions |
| `backend/tests/test_change_intelligence.py` | Clarify and strengthen the existing legacy-provider isolation test |
| `frontend/src/components/ChangeBrief.tsx` | Show the successful hosted overview with existing citation interactions |
| `frontend/src/ChangeBrief.test.tsx` | Hosted overview and deterministic fallback regressions |
| `docs/PHASE3_CHANGE_OPENROUTER_HANDOFF.md` | This handoff and live QA plan |
| `docs/README.md` | Link the current Phase 3 handoffs |

Public models, routing grammar, Context Builder V2, orchestration, synthesis validators, graph adapters, teammate graph/Cypher, ingestion, and source retrieval are unchanged. The existing four-tool computation remains authoritative.

## Provider and exact presentation contract

`OpenRouterProvider.generate(question, context)` retains the Phase 2 interface and protocol. Its existing request construction and completion-envelope checks are shared through `_complete()`. The new `select_change(packet)` uses that same HTTP client, credentials, configuration, timeout, model enforcement, and response bounds; it returns a selection plan rather than prose. The Change service validates and renders the plan itself.

Configuration remains:

```dotenv
WEAVE_LLM_PROVIDER=openrouter
WEAVE_LLM_MODEL=openai/gpt-oss-120b
WEAVE_OPENROUTER_MAX_TOKENS=1200
WEAVE_LLM_TIMEOUT_SECONDS=30
```

Model configuration permits `openai/gpt-oss-120b`; the completion must identify that exact model. The endpoint remains `https://openrouter.ai/api/v1/chat/completions`. There are no retries, alternate models, redirects, tools, provider fallbacks, or health probes in Change generation. The normal existing `/api/health` behavior is unchanged; **do not call it with a live hosted provider during an unapproved hosted QA session**.

The only permitted completion content is:

```json
{
  "selections": [
    {"block_id": "history", "variant": "explanation"},
    {"block_id": "impact", "variant": "explanation"},
    {"block_id": "reviewers", "variant": "explanation"},
    {"block_id": "checks", "variant": "explanation"}
  ],
  "source_ids": ["issue:PAY-42"]
}
```

The sample citation is the actual offline example, **not a hardcoded required citation**. Each of the four block IDs must occur exactly once, in any order. Each variant must be `recorded` or `explanation`. Extra fields, free-form transitions, factual text, entity selections, support overrides, duplicate citations, and unknown/missing section selections are rejected. `source_ids` must exactly match the genuine inline citations in the assembled answer; graph-only packets can have none.

The model can select and order complete server-authored variants. It cannot rewrite statements, select different reviewers or paths, change scores, promote an inference, omit a section or mandatory qualification, or change any structured field. The server always appends overall/per-tool support and all structured evidence limitations. All 384 combinations of variant choices and section order are tested.

## Minimal packet and bounds

The prompt contains a canonical server-authored question, `validated_evidence`, and `allowed_sections`:

- `validated_evidence`: canonical proposal, overall support, citation handles, per-tool support/state, and limitations.
- `history`: historical support, accepted decision IDs from the validated history, and any existing validated `INFERRED_RISK` wording/uncertainty with its own rationale citation.
- `impact`: returned scoped dependency paths, stored USES/DEPENDS_ON direction, depth and impact type, plus the no-guaranteed-failure qualification.
- `reviewers`: existing names, canonical person IDs, ranking order and scores, with the team/personal ownership qualification.
- `checks`: an unperformed validation summary, current document IDs and update times, and separate future document IDs conditional on approval and implementation.

No raw source excerpts, chunk text/metadata, graph properties, profiles, contact details, source URLs, raw Cypher, raw requested change text, or arbitrary graph inventory are included. Necessary IDs and names remain evidence data. The complete validated source/chunk provenance remains in the API response and inspector.

Limits:

- Change user-message packet: **24,000 UTF-8 bytes**. The fixed system instruction, bounded schema, and transport settings are additional request fields.
- Exactly four complete sections; two allowed variants each; at most 30 citation IDs through the existing schema.
- Shared transport response: **65,536 bytes**, including streamed-byte enforcement.
- Shared rendered answer: **6,000 characters**; both complete variants are preflighted before HTTP. Mixed variants cannot be longer than the all-explanation variant.
- Existing structured Change Brief bound: **160,000 UTF-8 bytes**, unchanged.
- Default token budget 1,200 and timeout 30 seconds; existing settings bounds remain enforced.
- At most one hosted POST for an eligible Change analysis; zero when disabled, unsupported, unresolved, insufficient, or rejected during packet preflight.

Measured actual mocked canonical request: **7,188 request-body bytes**, **4,546 user-message bytes**, **2,386 answer characters**, citation handles `issue:PAY-42`. No request body or authorization header was logged. This measurement is not hosted-provider acceptance.

Strings are serialized as JSON data. Suspicious instruction-like strings, URLs, email addresses, markup, credential assignments, and unsafe presentation content cause local rejection rather than removal of evidence or transmission. This is an additional conservative screen, not a general data-classification/privacy guarantee. The central grounding protection is finite server-authored output, independent of whether a model follows instructions. A future live payload still requires human review and approval.

## Grounding, immutability, and fallback

The pipeline remains `execute_plan` → four independent capability validators → Context Builder V2 → `_build` → bounded `ChangeBriefData`/deterministic-answer validation → optional packet → finite selection validation → answer assembly. There is no second traversal or source lookup for presentation.

Change references are checked against their own Context Builder capability inventories. Rationale citations originate only from the existing validated inference reference; neighboring ADR/commit records do not become rationale citations. The original builder still requires the accepted decision's real retrieved rationale provenance. Missing `SUPPORTED_BY` retains partial historical support and supplies no inferred rationale citation. Missing actual USES prevents hosted synthesis entirely. Missing source retrieval retains qualified graph-only evidence without invented citations. Shared inline-citation, HTML/link/control-character and length validation runs again on the final assembled answer.

On success, only `answer`, `metadata.generation`, and total `metadata.latency_ms` change. Generation is `openrouter` only after the selected plan passes validation and is actually rendered. The graph, sources/chunks, `data`, support status, tool list, existing warnings, classifications, reviewers, dates, and conditions are unchanged.

Disabled providers return the existing deterministic brief without an attempted hosted call. A missing key, a legacy injected provider without `select_change`, unsafe/oversized packet, timeout, HTTP/rate-limit/network failure, malformed/empty output, wrong schema/model/role, truncation, refusal, tool call, unknown citation/section, duplicated selection, unsupported factual text, or attempted support/entity/reviewer override returns the **exact original deterministic answer**. Generation stays `deterministic`; existing warnings are retained and one sanitized warning is appended:

> OpenRouter synthesis unavailable or rejected; showing the deterministic evidence summary.

No secret, raw provider body, debug detail, or rejection payload enters the response. This intentional generic reason avoids disclosing provider internals. An insufficient or unsupported proposal skips presentation instead of treating it as a provider failure.

## Endpoint and frontend compatibility

Both endpoints use the same `run_change()` and `analyze_change()` path, with a single four-tool computation and one deduplicated source lookup per request:

- `/api/change-intelligence`: unchanged seven-field structured response, including `data`.
- `/api/query`: unchanged exact six fields `answer`, `support_status`, `tools_used`, `sources`, `graph`, `metadata`; no `data`.

The React client still makes one dedicated Change request. A successful hosted answer appears as a compact **Grounded overview** before the nine unchanged structured sections, using the existing citation/inspector interaction. It summarizes rather than replaying the complete historical excerpts, detailed proofs, reviewer reasons, validation steps, or nine section bodies. Deterministic responses keep the original nine-section presentation; metadata-only fallback warnings remain visible. No browser provider client or extra API request was introduced.

Focused graph, path direction, reviewer evidence, risk labels, unperformed validation, current/future document separation, unsupported proposals, retry/history and Phase 2 cards remain unchanged.

## Verification

Final results:

- Python: **639 passed, 11 skipped**, full `backend/tests tests app/graph` suite.
- Ruff: passed for `backend/app backend/tests`.
- Frontend: **182 passed** across eight test files.
- ESLint, TypeScript, production build: passed.
- `git diff --check`: passed.

The 11 skips remain opt-in live integration tests. One existing Starlette/httpx TestClient deprecation warning remains. The new 61 Python cases cover both endpoints, exact structured/evidence immutability, selection variants, all finite orderings, local membership and missing provenance, source/tool outages, unsafe inputs, size bounds, provider failures, missing key, disabled/legacy providers, exact model and sanitized fallback. The two added UI cases cover hosted citations and deterministic fallback without duplicating structured sections.

Browser QA used the real React/graph workspace at 1440×1000 and 390×844 with explicitly labeled intercepted offline data and the answer rendered from a mocked provider. Non-local HTTP was blocked. Verified one Change POST, zero `/api/query` replay, working desktop/mobile citation inspection and Escape dismissal, one structured reviewer section, no horizontal overflow, and no page errors. Ignored screenshots: `.local/change-openrouter-desktop.png` and `.local/change-openrouter-mobile.png`. These are not live graph/provider evidence.

Reproduce offline:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_SOURCE_BACKEND = 'delegate'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests tests app/graph -q --basetemp=.local/pytest-phase3-stage3
.\.venv\Scripts\python.exe -m ruff check backend/app backend/tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

## Arnold: real FalkorDB acceptance plan

Stage 3 is ready for offline review and **Arnold's live QA**, not live sign-off. Coordinate the seed revision and any required data preparation with Alen and Antony. Do not launch, reseed, truncate, or mutate a shared graph automatically. Use an already available, approved seeded database and record the application commit, seed revision, graph name and non-secret environment settings.

1. Disable hosted generation. Configure the real existing `app.antony:create_gateway` factory, real source adapter and actual database connection locally; never print credentials. Run the existing opt-in acceptance test below and the original Phase 2 real gates against the same seed. Confirm actual DB health with provider disabled.
2. For the canonical proposal, verify resolution uses the actual `service:payment-service -USES→ tech:redis` edge. Inspect stored Checkout→Payment and Order→Checkout DEPENDS_ON directions and depths rather than inferring directions from traversal-list order.
3. Inspect accepted `decision:D-007`, actual SUPPORTED_BY Issue/Message relationships and Chunk FROM_* provenance. Verify genuine PAY-42, payment-perf-7, ADR-7, commit 8fae2 and Architecture Overview retrieval, canonical IDs and chunk metadata; citations must match the actual local claim provenance. Require no development fixture records or fallback adapters.
4. Compare reviewer order, scores, reasons, ownership classification and graph proof against the actual Expert Finder result. No inferred personal ownership or rescoring.
5. Verify current Architecture Overview review with actual earlier update and later trigger dates. Verify ADR-7 future review only through a returned document/service association and only if approved/implemented; do not mark it currently stale merely for future review. Inspect per-tool and overall support exactly; do not force the overall status to `supported`.
6. Exercise both dedicated and canonical query endpoints. Compare evidence and narrative; the dedicated response alone contains `data`. Confirm the browser makes one dedicated request, renders sources and focused graph with actual directions, and retains reviewer/risk/validation/current-versus-future qualifications at desktop/mobile sizes.
7. Check unsupported changes, partial tool/source failures, missing/reversed USES, missing rationale provenance, unrelated Redis users and identity conflicts using a controlled test double or a separately authorized isolated dataset. Never alter the shared seed for these cases. Verify no fabricated citations, no fixture fallback, preserved limitations, truthful partial/insufficient status and appropriate existing graph errors.
8. For hosted isolation over real graph data, first use a **local mocked selector** to compare every non-presentation field against deterministic output, including browser behavior and fallback. Do not configure a real hosted client merely to perform this check. This verifies presentation isolation but still is not live OpenRouter acceptance.
9. Record actual outputs, skips/failures, seed/app revisions and screenshots before QA sign-off. Resolve live schema/data/provenance differences through the existing adapters with the teammates; do not fill missing evidence in the renderer.

Existing read-only gate (requires available approved seeded FalkorDB):

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
$env:WEAVE_GRAPH_FACTORY = 'app.antony:create_gateway'
$env:WEAVE_RUN_REAL_CHANGE_INTEGRATION = '1'
$env:WEAVE_LLM_PROVIDER = 'none'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_change_intelligence.py -m integration -v
Remove-Item Env:WEAVE_RUN_REAL_CHANGE_INTEGRATION
```

## Hosted approval and remaining limitations

There is **no live hosted approval for these packets**. The earlier bounded Expert Finder approval is consumed and does not apply. Before any later hosted test, freeze the exact minimal request body locally, review its full field inventory and necessary evidence, redact unnecessary/sensitive data, verify fictional demo identities and citation handles, show the reviewable body plus model/endpoint/byte size/request bound/timeout, and obtain explicit approval. Transmit only that approved frozen body, with credentials solely in headers, no rebuilding from unredacted files, and no extra probes/retries. If its contents or transmission scope change, obtain renewed approval.

Live FalkorDB acceptance and live model/schema acceptance remain unverified. The limited canonical Redis-removal scenario is unchanged. This finite protocol deliberately permits selection/ordering rather than free-form paraphrasing. Long, unsafe or over-bound evidence falls back without truncating factual data; the original deterministic brief retains its own existing contract limits. The overview does not replace detailed proofs or expose every source excerpt. No runtime PostgreSQL fallback, change execution, benchmark, new agentic routing, or Trace Mode is implemented or claimed.

Antony's future ordered Decision Trace paths should enter through the existing validated history/ToolProvenance seam. Once an actual typed ordered-path contract is available, add normalized path validation and finite presentation variants using those supplied edges. Do not treat today's relationship inventories or branching document proof groups as a linear historical timeline, and do not infer new edges or chronology. No teammate branch was merged for this task.
