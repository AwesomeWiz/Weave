# Weave — Shared Project Context Pack

Current implementation: [repository setup](../README.md), [Phase 1 contract](PHASE1_IMPLEMENTATION.md), [Phase 1 verification](PHASE1_VERIFICATION.md), and [Phase 2 Impact Analysis handoff](PHASE2_IMPACT_HANDOFF.md). Both teammate graph and source packages are integrated; offline checks pass. Successful live FalkorDB verification remains required on this machine.

Latest orchestration: [Multi-tool routing and Context Builder V2](PHASE2_MULTITOOL_HANDOFF.md), including the unchanged query response contract and future graph-tool extension instructions.

This folder is the recommended context pack for the shared ChatGPT Project **Weave — FalkorDB Graph Hacks**.

> **Important:** These are pre-hackathon planning/reference notes. The official rules currently state that the main coding and design work must begin after the hackathon starts. Use these files to align on the idea and constraints; confirm/refine the implementation during the official build window.

## Upload order

1. `00_PROJECT_CONTEXT.md` — master summary and source-of-truth rules
2. `01_HACKATHON_BRIEF.md` — current official rules, schedule, and compliance notes
3. `02_WEAVE_PRD.md` — product scope and requirements
4. `03_ARCHITECTURE.md` — proposed hackathon architecture
5. `04_KNOWLEDGE_GRAPH.md` — ontology, relationships, and graph-native features
6. `05_AI_GRAPHRAG_PIPELINE.md` — retrieval, tools, prompting, and grounding
7. `06_TEAM_PLAN.md` — suggested four-person ownership and build gates
8. `07_DEMO_PLAN.md` — NovaPay demo narrative and golden questions
9. `08_API_DESIGN.md` — proposed frontend/backend contracts
10. `09_DATASET_INGESTION.md` — synthetic dataset and ingestion plan
11. `10_SUBMISSION_CHECKLIST.md` — final delivery and QA checklist

## Recommended ChatGPT Project instruction

Use the uploaded Weave documents as the shared source of truth. Prefer the hackathon brief for external constraints, the PRD for product scope, and the knowledge-graph document for ontology. Do not silently reintroduce the old EKOS Neo4j + ChromaDB architecture. Optimize decisions for a small, reliable Company Brain demo in which FalkorDB performs essential graph reasoning. When proposing implementation changes, call out which context document should be updated.

## Before the event

Use the pack for team alignment, research, questions, and planning. Re-check the official hackathon pages just before the event in case rules or schedule change.

## During the event

Create the actual implementation repository after the official start, then update these documents to reflect what the team really builds. The submitted README and Cypher documentation should describe the working implementation, not merely this pre-event proposal.
