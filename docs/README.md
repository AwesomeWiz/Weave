# Weave documentation

Start with the [project README](../README.md) for the product, actual graph model, canonical walkthrough and local quick start. The current application includes four graph capabilities, Change Intelligence, cinematic Trace Mode, evidence inspection and browser-local conversations.

## Run and evaluate

- [Detailed run guide](RUNNING.md): PowerShell and POSIX commands, graph/source configuration, authenticated ingestion, offline checks and opt-in live gates.
- [Deployment runbook](DEPLOYMENT_RUNBOOK.md): Railway, Vercel and FalkorDB Cloud settings, approved hosted seeding, acceptance and rollback; no local Docker required.
- [Render Free proof of concept](RENDER_FREE_POC.md): separate experimental single-container API + genuine FalkorDB option; runtime/memory feasibility requires a live trial.
- [Screenshot assets and provenance](assets/README.md): repository-visible sample UI captures; no live database/provider acceptance is implied.
- [Submission checklist](10_SUBMISSION_CHECKLIST.md): requirements to verify before submitting. Checkboxes are a checklist, not a claim that submission or deployment is complete.

## Implementation and verification

Read handoffs as revision-specific records. Their statements about unfinished future stages may have been superseded by later phases. The current source code and root run guide define the release setup.

| Area | Documentation |
| --- | --- |
| Phase 4 product workspace | [Product redesign](PHASE4C_PRODUCT_REDESIGN_HANDOFF.md) |
| Trace playback and motion | [Trace Mode contracts](PHASE4B_TRACE_MODE_HANDOFF.md), [cinematic presentation](PHASE4B1_CINEMATIC_TRACE_HANDOFF.md) |
| Saved conversations | [IndexedDB workspace](PHASE4A_CHAT_WORKSPACE_HANDOFF.md) |
| Change Intelligence | [Backend and structured contract](PHASE3_CHANGE_BACKEND_HANDOFF.md), [React integration](PHASE3_CHANGE_FRONTEND_HANDOFF.md) |
| Ordered historical paths | [Decision Trace integration and provenance](PHASE3_ORDERED_PATH_INTEGRATION_HANDOFF.md) |
| Constrained hosted presentation | [Phase 3 Change synthesis](PHASE3_CHANGE_OPENROUTER_HANDOFF.md), [Phase 2 OpenRouter](PHASE2_OPENROUTER_HANDOFF.md) |
| Four-tool routing | [Context Builder V2 and multi-tool orchestration](PHASE2_MULTITOOL_HANDOFF.md) |
| Capabilities | [Impact Analysis](PHASE2_IMPACT_HANDOFF.md), [Expert Finder](PHASE2_EXPERT_FINDER_HANDOFF.md), [Knowledge Freshness](PHASE2_FRESHNESS_HANDOFF.md) |
| Earlier live acceptance | [Phase 2 QA report](PHASE2_QA_REPORT.md), scoped to its recorded code and dataset revisions |
| Initial integration | [Real graph/source boundary](REAL_INTEGRATION_HANDOFF.md), [Phase 1 implementation](PHASE1_IMPLEMENTATION.md), [Phase 1 verification](PHASE1_VERIFICATION.md) |
| Earlier UI work | [UI refinement verification](UI_REFINEMENT_VERIFICATION.md), [design reference](design.md) |

Phase 4C records 370 passing frontend tests. Phase 4B records 686 passing Python tests with 11 opt-in live tests skipped. Earlier Phase 2 live acceptance is documented separately. These records do not establish final combined Phase 3/4 live FalkorDB or hosted-provider acceptance; repeat the appropriate gates on the release environment.

Some historical handoffs link ignored `.local` QA artifacts that are available only on the original workstation. The root README uses the public-review assets under [`docs/assets`](assets/README.md) instead.

## Data and graph source of truth

| Resource | Purpose |
| --- | --- |
| [NovaPay corpus](../data/novapay) | Approved synthetic source records and documents |
| [Record models](../weave_data/models.py) | Canonical entity and chunk schemas |
| [Relationship mapping](../weave_data/relationships.py) | Actual stored relationship directions |
| [Chunk generation](../weave_data/chunks.py) | Source IDs, text and provenance metadata |
| [Ingestion](../weave_data/ingest.py) | Validation/preparation and explicit persistence |
| [Graph adapter](../weave_data/graph_adapter.py) | Idempotent FalkorDB writes and persisted chunk retrieval |
| [Source interface](../weave_data/retrieval.py) | Exact-source retrieval seam; the backend supplies the real graph adapter |
| [Graph queries](../app/graph) | Decision Trace, Impact, Expert and Freshness queries |
| [Compatibility namespace](../weave_graph/__init__.py) | Keeps graph imports separate from the backend `app` package |
| [API models](../backend/app/models.py) | Actual endpoint schemas and evidence bounds |

Earlier workstream contracts remain useful background: [ingestion contract](ingestion-contract.md), [graph handoff](handoff-antony.md), [AI integration handoff](handoff-abhishikth.md) and [frontend/demo handoff](handoff-arnold.md). Where their illustrative diagrams or planned interfaces differ from implemented code, use the actual mapping and current root README.

## Planning and organizer context

These documents retain the original project context and plans; they are not claims that every proposed feature shipped:

- [Master context](00_PROJECT_CONTEXT.md)
- [Hackathon brief and official references](01_HACKATHON_BRIEF.md)
- [Product requirements](02_WEAVE_PRD.md)
- [Architecture proposal](03_ARCHITECTURE.md)
- [Graph ontology proposal](04_KNOWLEDGE_GRAPH.md)
- [GraphRAG pipeline proposal](05_AI_GRAPHRAG_PIPELINE.md)
- [Team/workstream plan](06_TEAM_PLAN.md)
- [Demo plan](07_DEMO_PLAN.md)
- [API proposal](08_API_DESIGN.md)
- [Dataset plan](09_DATASET_INGESTION.md)

Reconfirm external organizer rules and submission requirements before final submission. No public deployment, demo-video URL or submission confirmation is asserted by this index.
