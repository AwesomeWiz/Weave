# Weave — Submission Checklist

> **Pre-hackathon planning note:** This document is a planning/reference artifact only. The hackathon rules require the main coding and design work to begin after the event starts. Treat examples and proposed contracts here as hypotheses to confirm/refine during the official build window.

Use this file from Day 2 onward. Do not leave submission work until the final hour.

## 1. Rule compliance

- [ ] Team contains no more than 4 members.
- [ ] Every participant is on only one team.
- [ ] Main Weave implementation began after the official hackathon start.
- [ ] FalkorDB is the primary graph database.
- [ ] FalkorDB is central to product functionality, not only visualization.
- [ ] All data used is synthetic, public, or safely owned.
- [ ] No secrets/private data appear in repository or video.
- [ ] AI coding-assistant use is disclosed.
- [ ] Every team member understands the architecture and core graph logic.

## 2. Repository

- [ ] Repository is public before submission.
- [ ] Project name and short description are clear.
- [ ] `.env` is gitignored.
- [ ] `.env.example` is present.
- [ ] No API keys/tokens are committed.
- [ ] Unused experiments/dead files are removed.
- [ ] Main branch runs from documented steps.
- [ ] License is included if desired/appropriate.

## 3. README minimum sections

- [ ] What is Weave?
- [ ] Problem
- [ ] Why a graph?
- [ ] Why FalkorDB is essential
- [ ] Track: Company Brain
- [ ] Architecture diagram
- [ ] Graph data model
- [ ] Core features
- [ ] Important Cypher queries/algorithms
- [ ] Setup instructions
- [ ] Seed dataset instructions
- [ ] How to run frontend/backend
- [ ] Demo questions
- [ ] Screenshots/GIFs if useful
- [ ] AI-assistant disclosure
- [ ] Team members

## 4. Graph documentation

- [ ] Node labels documented.
- [ ] Relationship types documented.
- [ ] Decision node explained as a core concept.
- [ ] Canonical evidence path shown.
- [ ] Decision Trace query documented.
- [ ] Expert Finder logic documented.
- [ ] Impact Analysis traversal documented.
- [ ] Freshness heuristic documented.

## 5. Application

- [ ] FalkorDB starts reliably.
- [ ] Dataset seeds reliably.
- [ ] Seed is idempotent or reset path is documented.
- [ ] Backend health endpoint works.
- [ ] Frontend connects to correct backend.
- [ ] LLM provider configured.
- [ ] Source citations display.
- [ ] Evidence graph displays.
- [ ] Insufficient-evidence behavior works.

## 6. Golden-query QA

Run all golden questions after the final seed.

- [ ] Why does Payment Service use Redis?
- [ ] What incident led to the Redis decision?
- [ ] Who approved D-007?
- [ ] Which commit implemented D-007?
- [ ] Who knows Payment Service best?
- [ ] Why is the top expert ranked first?
- [ ] What depends on Payment Service?
- [ ] What would be affected if Redis were removed?
- [ ] Which documents describe Payment Service?
- [ ] Which documents may be stale?
- [ ] Can the UI show the source for the Redis rationale?
- [ ] Does an unsupported question return insufficient evidence?

## 7. Demo video

- [ ] Video begins with the problem, not setup.
- [ ] Product is visible within the first 20–30 seconds.
- [ ] Decision Trace is demonstrated.
- [ ] Graph evidence path is visible.
- [ ] At least one of Expert Finder / Impact Analysis is demonstrated clearly.
- [ ] Sources are visible.
- [ ] FalkorDB's role is explained explicitly.
- [ ] Video has readable text and clear audio.
- [ ] No secrets are visible.
- [ ] Video ends with concise product value statement.

Recommended final line:

> “Search tells you where information is. Weave tells you how the company got here.”

## 8. Deployment / setup

Preferred:

- [ ] Live frontend URL works.
- [ ] Backend is reachable.
- [ ] FalkorDB deployment is stable.

If not deploying:

- [ ] Docker/local setup is complete.
- [ ] Exact commands are in README.
- [ ] A judge can seed data and run the app from a clean clone.

## 9. Submission form

- [ ] Project title: Weave
- [ ] Track 3 — Company Brain selected.
- [ ] Any additional track selected only if the feature genuinely qualifies.
- [ ] Public repository link supplied.
- [ ] Demo video supplied.
- [ ] Deployment/setup information supplied.
- [ ] Project description proofread.
- [ ] Team members correct.

## 10. Optional blog side prize

Suggested article angle:

**Why Vector RAG Isn't Enough for a Company Brain: Building Decision Intelligence with FalkorDB**

Outline:

1. fragmented company knowledge problem
2. why vector search alone loses relationships
3. Decision as a first-class graph entity
4. provenance path example
5. Expert Finder and Impact Analysis
6. architecture and Cypher tools
7. lessons from building Weave
8. demo screenshots

Do not write the article until the implementation exists; describe what was actually built.

## 11. Final 30-minute check

- [ ] Fresh clone/setup instructions sanity checked.
- [ ] Main demo queries tested.
- [ ] Repository visibility public.
- [ ] README rendering checked.
- [ ] Demo link permissions checked.
- [ ] Submission saved/submitted.
- [ ] Confirmation captured.

## 12. Post-submission

After submission:

- tag the final commit
- save the demo dataset/version used
- keep the deployment running through judging if feasible
- avoid breaking main with optional experiments

---

## Winning-demo QA additions

- [ ] Same impact query returns different graph-grounded results before/after a real FalkorDB dependency-edge change.
- [ ] Graph visualization and cited evidence match both results.
- [ ] Reset/re-seed restores the original graph and result.
- [ ] Older Architecture Overview is flagged as a review candidate with timestamp/evidence rationale.
- [ ] Updating the same document node clears the *specific* freshness warning without creating duplicates.
- [ ] All 10–15 golden questions and an unsupported question pass.
- [ ] Demo video visibly proves FalkorDB is essential, not merely used for graph rendering.
- [ ] Optional review-task creation requires confirmation and reports actual success/failure.
- [ ] No stretch feature displaces README, video, clean setup, compliance, or Oct 18 submission.
