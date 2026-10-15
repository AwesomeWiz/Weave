# Weave — FalkorDB Graph Hacks Brief

**Hackathon:** Graph Hacks: Context for AI Agents  
**Organizer:** WeMakeDevs in collaboration with FalkorDB  
**Primary Track:** Track 3 — Company Brain  
**Verified:** 2026-10-05

> This file records externally imposed rules. Re-check the official pages immediately before the event because the organizers state that rules, schedule, and prize details may be updated.

## 1. Event window

The official schedule currently states:

- Hacking begins: **October 15, 2026 at 12:01 AM IST**
- Submissions close: **October 18, 2026 at 11:59 PM IST**
- Event format: online
- Team size: solo or up to 4 people

For planning, Weave treats October 15–17 as the main build period and October 18 as the submission/demo buffer, while still recognizing that the official build window remains open through October 18 at 11:59 PM IST.

## 2. Track 3 — Company Brain

The official Track 3 challenge is to build an agent that understands how a company works by connecting company knowledge in a graph.

The track specifically emphasizes:

- knowledge from documents, tickets, and chats in one graph
- who owns what and who knows what
- tracing decisions back to their source
- keeping knowledge current as things change
- answers with clear sources

This is the direct target for Weave.

## 3. Mandatory FalkorDB requirement

FalkorDB must be the project's **primary graph database** and must support a central part of the product.

The graph must do real work. A graph used only to draw a visualization on top of ordinary storage is not sufficient. The product should materially stop working if FalkorDB is removed.

### What this means for Weave

The following capabilities must execute against FalkorDB:

- Decision Trace
- Expert Finder
- Impact Analysis
- provenance/evidence path retrieval
- graph-aware context retrieval for the LLM
- Knowledge Freshness relationships and checks

We should be able to tell judges:

> “If FalkorDB is removed, the main reasoning capabilities disappear. The model no longer knows how decisions, people, incidents, code, and services connect.”

## 4. Data restrictions

Only use data the team is allowed to use.

Acceptable categories include:

- synthetic data
- public data
- data owned by the team and safe to publish/use

Do not load private, login-protected, paywalled, personal, or otherwise restricted information into the graph.

### Weave decision

The official demo will use a **synthetic company dataset** named `NovaPay`. This avoids privacy issues and gives the team full control over the evidence chains needed for a reliable demonstration.

## 5. Existing work and pre-hackathon preparation

The rules state that the **main coding and design work must begin after the hackathon starts**.

Before the event, participants may discuss ideas, create notes, sketch the graph model, and prepare diagrams.

General libraries, frameworks, templates, public APIs, third-party tools, and public datasets are allowed. The original implementation submitted for judging must be work completed during the hackathon window.

### Weave policy

Before October 15:

- planning documents are allowed
- architecture discussions are allowed
- graph sketches are allowed
- demo story design is allowed
- studying FalkorDB/GraphRAG documentation is allowed

Do **not** pre-build the hackathon application or FalkorDB implementation.

Create the actual hackathon repository and begin the main implementation after the official start.

## 6. AI coding assistants

AI coding assistants are allowed, but their use must be disclosed.

Every team member must understand the submitted implementation and be able to explain:

- the graph model
- important Cypher queries
- project architecture
- technical choices
- how FalkorDB influences agent behavior

Weave should therefore keep core queries readable and documented rather than hiding everything behind generated abstractions.

## 7. Submission requirements

The current rules require:

- public source-code repository
- README with setup instructions
- README/documentation of the graph data model
- Cypher queries or graph algorithms the product depends on
- demo video showing the working project
- live deployment, or complete local setup instructions if deployment is not possible
- declared track(s)
- disclosure of AI coding-assistant use

## 8. Track strategy

### Primary submission

**Track 3 — Company Brain**

Do not dilute this entry. All must-have engineering work should improve the Track 3 story.

### Optional secondary track

Only after the Track 3 demo is stable, consider a small Track 1 extension:

1. User asks for impact analysis.
2. Weave identifies affected systems and owners through FalkorDB.
3. User confirms an action.
4. Weave creates a task/issue containing the graph-derived impact summary.

This would make the graph result drive an external action, but it is optional.

## 9. Sponsor-technology strategy

FalkorDB should be visible in all four layers:

1. **Storage:** company entities, relationships, chunks, and provenance
2. **Retrieval:** graph traversal plus semantic/full-text retrieval
3. **Reasoning tools:** explicit Cypher-based functions used by the agent
4. **Explanation:** evidence paths displayed in the UI

The FalkorDB GraphRAG SDK may be used for ingestion/retrieval where it accelerates development. Custom Cypher should still power the distinguishing graph-native features so the project is clearly more than an SDK demo.

## 10. Official references

- Main event: https://www.wemakedevs.org/hackathons/falkordb
- Schedule: https://www.wemakedevs.org/hackathons/falkordb/schedule
- Rules: https://www.wemakedevs.org/hackathons/falkordb/rules
- Resources: https://www.wemakedevs.org/hackathons/falkordb/resources
- FalkorDB GraphRAG SDK: https://github.com/FalkorDB/GraphRAG-SDK

## 11. Final compliance check

Before submission, answer **yes** to all of the following:

- Was the main implementation created during the event?
- Is FalkorDB the primary graph database?
- Would core product functionality fail without FalkorDB?
- Is all demo data public, synthetic, or safely owned?
- Is the repository public?
- Does the README explain the graph model?
- Are the important Cypher queries/algorithms documented?
- Is there a working demo video?
- Is there a live deployment or complete local setup?
- Is AI-assistant use disclosed?
- Can every team member explain the architecture and core graph logic?
