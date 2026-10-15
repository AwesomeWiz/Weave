# Weave — Product Design System & UX Specification

**Document:** `docs/design.md`  
**Version:** 1.0 · 15 October 2026  
**Audience:** Codex, frontend engineers, reviewers, and product designers  
**Product:** Weave — *Company Intelligence*  
**Primary demo workspace:** NovaPay (fictional company)  
**Design status:** Implementation specification. Screen references are visual guidance, not pixel-perfect blueprints.

> **Instructions for Codex:** Read this file before building or changing any user-facing screen. Reuse the tokens, components, states, copy rules, and interactions defined here. Do not independently invent new colors, logos, navigation patterns, shadows, or graph styling. When a mockup contradicts this document, **this document wins**. The PRD and API design win for functionality and data contracts. If an interaction is not yet backed by the API, implement an honest disabled/empty state rather than fabricated data.

## 1. Design intent

**Weave helps a person understand *why* a company system is the way it is.** It connects incidents, discussions, decisions, code, people, services, and documents; FalkorDB supplies relationships and provenance; the assistant explains sourced evidence.

The UI must feel like **a serious, calm intelligence workspace**, not a generic AI chat clone, a node-graph toy, or a dashboard of vanity metrics.

### Experience principles

1. **Evidence before spectacle.** The answer and supporting source chain are the heroes. An attractive graph is useful only if a person can follow it and inspect its claims.
2. **Progressive disclosure.** Start with one clear question or concise answer. Reveal provenance, graph, source excerpts, timeline, and detailed properties only when relevant. Never crowd the initial chat screen with every feature at once.
3. **Quiet confidence.** Warm neutrals, precise typography, restrained sage green, sparse decoration, stable layout, and small purposeful transitions convey professional reliability.
4. **Explainable control.** Users must understand where a claim came from, which graph path was traversed, and whether a result is supported or uncertain. Do not label a synthesized inference as verified fact.
5. **Human decisions first.** Every core workflow answers one of four real questions: *Why was this decided? Who knows about it? What might be affected? Which information may be outdated?*
6. **One primary action per region.** Minimize competing buttons. Secondary actions should be text buttons, contextual menus, or tabs; avoid repeated giant colored CTAs.
7. **Predictable spatial memory.** Primary navigation stays on the left; task content stays in the center; sources and object details appear on the right. Keep this pattern across views.
8. **Honest system status.** Only show “Connected,” “Up to date,” counts, last sync, and completed actions when backed by real data. Synthetic NovaPay records are acceptable for the demo but must not masquerade as real integrations.

### Design psychology: why these choices work

| Principle | UX application | Behavioral intention |
|---|---|---|
| Cognitive-load reduction | Large whitespace, 2–4 suggested actions, short answer first | Reduce scanning and decision fatigue |
| Information scent | Specific labels such as “Trace decision” instead of “Explore” | Make the next step predictable |
| Recognition over recall | Persistent recent questions, labeled entities, visible source IDs | Avoid making users remember prior context |
| Trust through inspectability | Inline citations, source snippets, evidence paths, observed timestamps | Let users verify claims, not just trust fluent language |
| Progressive disclosure | Graph/timeline/source tabs and contextual inspector | Keep expert depth available without making every screen dense |
| Visual hierarchy | Display serif for page-level entry points; crisp sans for operations | Separate editorial identity from task-critical data |
| Perceived control | Graph reset, zoom, depth, explicit confirmation before write actions | Make complex exploration feel reversible and safe |
| Error prevention | Clear read-only versus write actions; disabled states with explanations | Avoid accidental graph mutations or external actions |

These are **design goals**, not measured psychology findings or usability-study results.

## 2. Design references and precedence

Bundled references (when present):

- `docs/references/initial-chat.png` — **primary visual reference** for restraint, layout, warm color treatment, whitespace, four simple starting workflows, and the chosen interwoven-knot logo direction.
- `docs/references/active-chat.png` — reference for an evidence-backed response, inline source links, and a focused evidence graph. It is intentionally denser than the empty state.
- `docs/references/knowledge-graph.png` — reference for graph-canvas affordances, labeled relationships, and entity inspector. Its visual graph is illustrative, **not a source of truth for edge directions or entity facts**.

**Precedence:** (1) Product truth: PRD / architecture / API / dataset; (2) this design specification; (3) screenshots for general visual proportion, atmosphere, and composition. Generated references disagree about logo shape, information architecture, fonts, and some graph edges; never propagate those inconsistencies.

**Visual north star:** understated editorial enterprise software. Think thoughtfully aligned borders, precise data visualization, subtle depth—not glow, glassmorphism, gradients on every card, giant emojis, or flashy AI ornamentation.

## 3. Brand and logo

### Brand

- Name: **Weave** (capital W; never EKOS or AEKOS in UI).
- Supporting descriptor: **Company Intelligence** where space permits (header/subtitle), not repeated everywhere.
- Optional tagline for marketing/demo slides only: **“Trace the why behind every company decision.”**
- Tone: direct, informative, technically literate, neutral, slightly warm. Short sentences; no promotional fluff inside task flows.

### Canonical logo specification

Use **one abstract, interwoven-knot symbol** throughout the application, based on the most recent *minimal initial-chat* screenshot, **not** the original EKOS windmill/leaf symbol. The symbol conveys independently stored facts becoming connected paths:

- Four rounded, interlaced strands/loops around a small central negative space; balanced, symmetric, geometric.
- Solid single-color version in `--brand-700`; light inverse in white for dark backgrounds.
- No leaf shapes, sparkle icons, gradients, 3D bevels, or literal chain-link stock icon.
- `32 × 32` px in sidebar brand row; optional `56 × 56` px on empty chat screen. Leave at least 20% clear space around mark.
- Sidebar wordmark: `Weave` with title/display serif at 28 px; descriptor uses UI sans at 11–12 px.
- The screenshots are raster concept art, **not a production SVG**. Create and approve a single manually drawn `src/assets/weave-mark.svg`, then use that same asset for favicon, sidebar, empty state, and any demo slide. Until approved, use a consistent simple abstract knot placeholder rather than different AI-generated logo variants.

**Logo acceptance test:** legible at 24 px, distinguishable in monochrome, recognizable without the wordmark, no resemblance to prior EKOS petal logo.

## 4. Typography

The source screenshots do not identify their original font files. The following are **recommended implementation fonts selected to reproduce the intended appearance**, not a claim that the screenshots use these exact families.

| Role | Primary | Fallback | Weights | Usage |
|---|---|---|---|---|
| Interface / body | **Inter** | `system-ui, -apple-system, sans-serif` | 400, 500, 600, 700 | Everything operational: buttons, navigation, answers, citations, graph labels, cards, tables |
| Display / editorial | **Instrument Serif** | `Georgia, 'Times New Roman', serif` | 400 | Weave wordmark, welcome statement, *select* page H1 headings |
| IDs / code | **JetBrains Mono** | `ui-monospace, SFMono-Regular, monospace` | 400, 500 | Commit hashes, API identifiers, code snippets—not paragraphs |

Use self-hosted or bundled `@fontsource` packages when practical; use proper font loading/fallback and avoid blocking the whole page on web-font download. **Do not distribute font files as part of the design handoff.**

### Type ramp (desktop)

| Token | Font | Size / line height | Weight | Example |
|---|---|---|---|---|
| `display` | Instrument Serif | 52 / 1.06 | 400 | “Welcome to Weave” |
| `h1` | Instrument Serif | 36 / 1.15 | 400 | Page title when editorial |
| `h1-ui` | Inter | 30 / 1.23 | 600 | Graph and data-heavy views |
| `h2` | Inter | 20 / 1.35 | 600 | Section headings |
| `h3` | Inter | 16 / 1.4 | 600 | Card titles / panel headers |
| `body` | Inter | 14 / 1.6 | 400 | Main explanatory copy |
| `body-strong` | Inter | 14 / 1.55 | 600 | Answer leading claim / labels |
| `small` | Inter | 12 / 1.5 | 400–500 | Metadata and helper text |
| `caption` | Inter | 11 / 1.45 | 500 | Source type, graph relationships |
| `mono` | JetBrains Mono | 12 / 1.5 | 400–500 | `PAY-42`, `8fae2`, `D-007` |

- Do not mix serif and sans within one sentence.
- The actual chat answer, entity names, relationship labels, source snippets, timestamps, inputs, and controls should always be in Inter.
- Reserve serif for **one major moment per page**; it is not a decorative font for all cards.
- Keep paragraphs ~65–80 characters per line where possible; source metadata may be smaller, but interactive controls should not rely on 11 px text alone.
- Prefer sentence case. Avoid uppercase labels except compact graph relationship labels or true IDs.

## 5. Color and semantics

**Palette philosophy:** mostly warm paper and muted neutral surfaces, with forest/sage accents. Green is an intentional brand and action color—not the universal color for every node or status.

### Canonical CSS design tokens

```css
:root {
  /* Brand */
  --brand-900: #243F31;
  --brand-800: #315340;
  --brand-700: #446A52;
  --brand-600: #557B61;
  --brand-100: #E8EEE7;
  --brand-075: #F0F4EE;

  /* Warm neutral surfaces */
  --canvas: #F8F7F3;
  --sidebar: #F0F2EC;
  --inspector: #F2F4F3;
  --surface: #FFFFFF;
  --surface-soft: #FCFCF9;
  --surface-hover: #F3F5F0;
  --surface-selected: #E4ECE3;

  /* Text */
  --text-primary: #1D2420;
  --text-secondary: #53615A;
  --text-muted: #657169;
  --text-inverse: #FFFFFF;
  --text-link: #315A7C;

  /* Lines & focus */
  --border: #E2E6DF;
  --border-strong: #CBD4C9;
  --focus-ring: #356B9B;

  /* Feedback: status is shown with text and icon too */
  --success: #28734A;
  --success-bg: #E9F4EB;
  --warning: #936314;
  --warning-bg: #FFF4DD;
  --danger: #A63F3F;
  --danger-bg: #FCEAEA;
  --info: #315A7C;
  --info-bg: #EAF2F9;

  /* Entity classification in graph */
  --node-service: #385A46;
  --node-service-bg: #E5EFE7;
  --node-person: #376CAA;
  --node-person-bg: #E9F1FB;
  --node-issue: #2766BC;
  --node-issue-bg: #E9F2FF;
  --node-incident: #B14944;
  --node-incident-bg: #FCEBE9;
  --node-decision: #A46A18;
  --node-decision-bg: #FFF0D8;
  --node-technology: #A44542;
  --node-technology-bg: #F9E7E6;
  --node-document: #7155A3;
  --node-document-bg: #F1ECFA;
  --node-repository: #644C87;
  --node-repository-bg: #F0EBF8;
  --node-commit: #6B599A;
  --node-commit-bg: #F1EDF8;
  --node-team: #486D66;
  --node-team-bg: #EAF2F0;

  /* Graph */
  --graph-edge: #94A69A;
  --graph-label-bg: #FBFCF9;
  --graph-active-edge: #315D48;
  --graph-grid-dot: #E4EAE4;

  /* Dimensions */
  --nav-width: 272px;
  --inspector-width: 328px;
  --content-max: 1120px;
  --radius-xs: 6px;
  --radius-sm: 10px;
  --radius-md: 14px;
  --radius-lg: 18px;
  --radius-xl: 24px;
  --radius-pill: 999px;
  --shadow-card: 0 2px 12px rgba(27, 45, 33, 0.035);
  --shadow-popover: 0 12px 35px rgba(27, 45, 33, 0.12);
}
```

The tokens are implementation decisions inspired by the screenshots; they are not extracted exact pixel colors. Check contrast in the actual rendered app: small text and text within light tinted pills must meet **WCAG AA 4.5:1** (normal text), and non-text UI boundaries/focus indicators should reach **3:1** where applicable. Darken text as necessary without changing the underlying hierarchy.

**Use of color:**

- Accent green: selected navigation item, primary action, active tab underline, selected service node.
- Blue: links and source-linked IDs, not every CTA.
- Amber: review-needed / candidate stale, not “incorrect.”
- Red: actual error/high-impact incidents, not generic graph decorations.
- Status meaning is **never encoded by color alone**: always add label/icon.

## 6. Spatial rhythm and surfaces

### Spacing scale

Base 4 px grid. Preferred steps: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

- Sidebar horizontal padding: 16–20 px.
- Main content horizontal padding: 32–40 px desktop; 20–24 px on compact laptops.
- Content sections: 32 px apart on full pages; 20–24 px on dense result pages.
- Cards: 16–20 px internal padding; 12–16 px gaps.
- Form-control heights: 40 px standard; 44–48 px large; composer 56–64 px.
- Source list row: minimum 48 px clickable height.
- Desktop recommended graph controls: 36–40 px buttons, generous click targets.

### Surfaces

- App background is predominantly `--canvas`; sidebar is slightly tinted; inspector is subtly cool neutral.
- Cards use `--surface` and a 1 px border; reserve shadows for meaningful elevation such as the main card, popover, and floating composer.
- Do **not** put every subheading into a card. Blank space, typography and hairline dividers are preferable.
- No thick borders, noisy gradients, blurred glass layers, full-screen dotted background, or dense textured overlays.
- A faint editorial wave on the *empty chat landing screen only* may be rendered with CSS/SVG at extremely low opacity; do not carry decorative texture into data-dense pages.

## 7. Shared application shell

### Desktop layout (>= 1280 px)

```text
┌────────────── 272px ─────────────┬──────────── flexible main ──────────────┬── 328px ──┐
│ Weave mark + name                │ Page title / context                   │ Context     │
│ Primary navigation               │ Main workspace                          │ inspector   │
│ Recent conversations or views    │ Chat, trace, graph, results             │ / sources   │
│                                  │                                         │             │
│ Workspace switcher               │ Bottom composer or contextual controls │             │
│ Profile                          │                                         │             │
└──────────────────────────────────┴─────────────────────────────────────────┴─────────────┘
```

- Sidebar stays anchored left; right inspector scrolls independently if needed.
- Main scrolls naturally. Avoid multiple nested scroll containers on chat unless necessary.
- Right rail is contextual: connected sources on *empty chat*, evidence/source detail on *active chat*, selected entity inspector on *graph*, and affected owners/evidence on *impact*.
- Sidebar active state: tinted `--surface-selected` pill with icon and text. **Only one nav item selected.**
- Workspace name `NovaPay` lives in an easy-to-find switcher; do not show a non-functional dropdown.
- Profile and environment/session status live at bottom; minimize persistent chrome.

### Information architecture

**Primary sidebar navigation (stable order):**

1. **Chat** — `/chat` (new session and conversation history are sub-actions, not separate top-level sections).
2. **Knowledge Graph** — `/graph`.
3. **Decisions** — `/decisions` (decision directory and trace detail).
4. **Services** — `/services` (directory; opens service graph/detail and impact).
5. **People** — `/people` (expert finder entry).
6. **Changes** — `/changes` (freshness alerts and recent knowledge updates).
7. **Connectors** — `/connectors`.

**Avoid** separate top-level duplicates `Decision Trace` and `Impact Analysis` *if* they are already task actions within Decisions/Services. In the hackathon build, a task may be reached via deep link or contextual button without a dedicated nav item. Make links and route titles reflect that decision.

### Responsive behavior

| Width | Layout | Key behavior |
|---|---|---|
| >= 1440 px | Full 3-column shell | Right rail always visible; graph shows inspector |
| 1280–1439 px | Compact 3-column | Narrow padding, hide nonessential metadata, preserve graph readability |
| 1024–1279 px | Sidebar 232–248 px + main | Inspector becomes collapsible sheet/drawer; no squeezed third column |
| 768–1023 px | Collapsible nav + main | Inspectors open as side sheet; tables horizontally scroll with headers |
| < 768 px | Single content column | Drawer navigation; graph may switch to path/list fallback; composer remains accessible |

The judged/demo experience is **desktop-first** (aim for 1440 × 900 and 1280 × 800). The interface must not overflow or crop crucial buttons at 1280 × 800. Mobile perfection is not P0, but navigation, citations, and controls must remain operable.

## 8. Core component library

Build reusable typed components instead of copying screen-specific JSX:

| Component | Responsibilities and rules |
|---|---|
| `AppShell` | Sidebar, main region, optional inspector slot, workspace context |
| `SidebarNav` / `WorkspaceSwitcher` | Stable routes, active item, controlled expand/collapse |
| `BrandLockup` | Reuses single canonical SVG; never recreates logo using CSS per page |
| `PageHeader` | Title, one-line description, optional context actions |
| `Button` | `primary`, `secondary`, `ghost`, `danger`; `sm`, `md`, `lg`; loading and disabled |
| `Card` / `Panel` | Neutral surface variants with consistent borders and radii |
| `SourceCitation` | ID, title, type, deep link, click to preview/open source |
| `SourceInspector` | Source metadata, original excerpt, provenance and external-link action |
| `EntityPill` / `EntityRow` | Type icon, name, subtype, optional source status |
| `StatusBadge` | Explicit label + accessible icon; `connected`, `loading`, `stale-candidate`, `error` |
| `PromptComposer` | Multiline text entry, submit, keyboard hints, loading/cancel behavior |
| `StarterPrompt` | Single accessible clickable suggested question |
| `GraphCanvas` | Pan/zoom, fit, bounded depth, click selection, highlighted evidence path |
| `GraphNode` / `GraphEdgeLabel` | Color by type, accessible labels, provenance, no ambiguous edge direction |
| `EvidencePath` | Compact linear path for reading; supports step-click to inspect |
| `Timeline` | Chronological event list, timestamps, event/source links |
| `EntityInspector` | Summary, metadata, relationships, cited evidence |
| `ImpactRow` | Affected entity, relationship path, severity rationale, owner |
| `FreshnessRow` | Document, last update, newer evidence, “review candidate” state |
| `EmptyState` / `ErrorState` / `Skeleton` | Standard feedback, actionable recovery |
| `ConfirmDialog` | For mutation/write actions only; previews effects and requires explicit confirmation |

Icon system: **Lucide** 18–20 px regular stroke (1.75–2 px). Graph nodes may use matching small Lucide icons. External service icons (GitHub, Jira, Slack, docs) should use recognizable official icons only if permitted/available, otherwise a consistent generic source icon; don't invent inaccurate provider marks. Avoid emojis for interface iconography.

## 9. Page specifications

### 9.1 Initial Chat (`/chat`, empty conversation)

**Goal:** Help the user ask a meaningful company question without imposing a complex dashboard.

**Visual layout:**

- Left navigation and narrow right contextual panel; main center is intentionally spacious.
- Place canonical knot mark `56px` near upper central focal region; below it, editorial `Welcome to Weave` (48–52 px), then one concise subtitle.
- Exactly **four entry cards in a 2×2 grid**: `Decision Trace`, `Expert Finder`, `Impact Analysis`, `Knowledge Freshness`. One-sentence descriptor each; a quiet arrow on each card.
- Optional **three** plain-text question chips below the grid, not additional card walls. E.g. `Why was Redis introduced?`, `Who owns Payment Service?`, `Are the docs current?`.
- Chat composer near bottom of central viewport, visually dominant only after the greeting. Input placeholder: `Ask about your company's knowledge…`.
- Right rail: at most **two cards**: `Connected sources` (compact real connection states) and `Knowledge status` (real sync status). Don't show extra recent-conversation cards here: recent history belongs in the sidebar.
- **Do not** include entity-count KPIs, workflow marketing blocks, fake activity feeds, or an overlong source catalog on this page.

**Action mapping:** Clicking a workflow card either prefills an example prompt or navigates to that feature with a relevant default entity; one consistent behavior per card. Clicking a question chip submits or fills the composer (choose one interaction and apply uniformly). A user should understand the next step without guessing.

**Empty states:** If no sources connected, right rail says `No sources connected` with `Configure sources`, not `Up to date`. If graph has no entities, show a guided start state.

### 9.2 Active Chat (`/chat/:sessionId` or equivalent state)

**Goal:** Give a succinct answer while making every important claim inspectable.

**Default hierarchy:**

1. User prompt as modest right-aligned bubble (not oversized).
2. Assistant **two- to four-sentence direct answer** with source-linked IDs embedded.
3. Supporting explanation in 1–3 short paragraphs or steps as needed.
4. Contextual `Evidence graph | Timeline | Key sources` tabs (only show views backed by data).
5. Focused evidence path/subgraph (not the entire company graph).
6. Small next-step action row: `Explore in graph`, `Find experts`, `Analyze impact`, `Check document freshness`.
7. Fixed/sticky composer at bottom of chat main area; don't cover content.
8. Right `Sources` list, `Related entities`, and (only if useful) `Key takeaways`.

**Source interactions:** Inline `PAY-42`, `D-007`, `ADR-7`, and `8fae2` references are **real focusable buttons/links**, not blue static text. Clicking opens a source preview in the right inspector; an external-link affordance opens the original URL if valid. Hover/focus highlights corresponding graph entity when mapped. If a source has no valid URL, show `View source details` rather than broken external link.

**Evidence correctness:** Use API `support_status`:

- `supported` → plain `Backed by N sources` with actual provenance.
- `partially_supported` → `Partial evidence` and indicate unsupported segments.
- `insufficient_evidence` → explicitly say evidence is insufficient, avoid inventing a path or sources.

**Streaming/latency:** Show initial user message immediately; then `Searching company knowledge…` / `Traversing relationships…` / `Preparing response…` *only if these stages are actually known*. Use skeletons for sources/graph; never fake tool progress or fabricate latency metrics.

**Interaction consistency:** Selecting `Timeline` changes the middle panel but retains the answer and source inspector. `Explore in graph` deep-links to `/graph?focus=...` and selects the same entity/path. Chat scroll stays pinned to bottom only if the user was already near bottom; don't yank position while reading citations.

### 9.3 Knowledge Graph Explorer (`/graph`)

**Goal:** Let users follow and verify a focused neighborhood of connected knowledge.

- Header `Knowledge Graph`, short subtitle, workspace switcher.
- Compact toolbar: entity search (dominant width), `Filter`, `1 / 2 / 3 hops` selector, `Fit to view`, optional `Layout` switch.
- Central graph fills most of the page. Use muted point grid *only inside canvas*.
- By default focus on a meaningful NovaPay entity (`Payment Service`) and **1–2 hops**. Do not auto-render the full graph on load.
- Select the focused node using filled dark sage service styling; other node types use low-saturation semantic tints.
- Labels: visible entity name, muted entity type; edges have readable short uppercase relationship labels, an arrowhead showing direction, and path tooltips where needed.
- Right inspector shows selected entity name/type, concise description, owner/team, selected relationship list, linked sources, and actions `Trace decision` / `Analyze impact` when relevant.
- Graph tools: zoom in/out, fit, reset filters, keyboard focus when possible; minimap optional if it stays legible.
- Optional bottom panel: `Relationships | Decisions | Documents | Activity`, using a readable list/table. Hide entirely if empty or if screen height is constrained.

**Graph interactions:**

- Single click selects entity and updates inspector; hover emphasizes adjacent edges; Escape clears selection.
- Double click or explicit `Expand neighbors` expands node by bounded depth; do not unexpectedly reorganize entire layout after simple select.
- Search selects and centers matching entity, gives helpful disambiguation if multiple matches.
- Filters visibly indicate active values; `Reset view` returns to the original focus and removes transient filtering.
- Contextual `Trace decision` opens the dedicated trace workflow with current entity; preserve context via route state or query parameter.

**Graph rendering correctness:** respect edge direction returned from backend; do not reverse arrows to achieve visual symmetry. Distinguish `USES` from `DEPENDS_ON` and `DOCUMENTED_IN` semantically. Never show an edge that the backend did not provide just to make layout more attractive. Reduce collisions, truncate only with tooltip, prefer stable deterministic layout for demo.

### 9.4 Decision Trace (`/decisions/:id` or `/decisions/trace?entity=...`)

**Goal:** Make decision causality readable in 10 seconds and verifiable on inspection.

**This is a dedicated task view, not another generic graph browser.**

**Layout:**

- Page title: `Why was Redis introduced?` or `Decision D-007 — Introduce Redis caching`.
- Header metadata: decision date, status (`Accepted` or real graph status), owners/approvers, affected service.
- **Primary top section:** concise `The reason` summary with 2–3 cited claims.
- **Central visual:** a clear left-to-right or vertical **chronological decision trail** with 5–6 labeled stages:
  `INC-17 Incident → PAY-42 Issue → Slack discussion → D-007 Decision → 8fae2 Commit → ADR-7 Documentation`.
- Each stage card shows source ID, date, role in chain, and a small action to inspect evidence. Decisions have strongest visual emphasis; predecessors and downstream effects are quieter.
- Under the trail: `Participants`, `Implemented in`, `Affected services`, `Evidence used`. Optional toggle `Show graph relationships` reveals the exact multi-hop FalkorDB subgraph.
- Right rail: selected step's source excerpt/provenance, not a duplicate of the whole page.

**Essential controls:** change focused decision; click stages; open cited source; `Explore this path in graph`; `Analyze downstream impact`. If the chain is incomplete, indicate `Missing evidence between X and Y`, not a fabricated connector.

**Required NovaPay story:** Redis was introduced to address Payment Service latency following INC-17/PAY-42, debated in a Slack thread, approved as D-007, implemented in commit `8fae2`, and documented in ADR-7 **if and only if these graph facts exist in the seeded dataset**.

### 9.5 Impact Analysis (`/services/:id/impact` or `/impact?entity=...`)

**Goal:** Help a developer preview potentially affected systems and people before a risky change.

**This is not a duplicate Knowledge Graph page.**

**Layout and priorities:**

1. Clear scenario banner: `Impact of removing Redis from Payment Service` (read-only analysis, **not** an actual deletion).
2. Summary band: `Directly connected`, `Downstream services`, `Relevant owners`, `Evidence gaps` using actual counts; no dramatic ungrounded percentage scores.
3. **Primary central dependency diagram:** source technology → using service → services dependent on it, with directional arrows, limited to 2–3 hops; affected paths emphasized while unrelated nodes fade or are omitted.
4. Adjacent/under graph: sorted `Potentially affected` table/list with `Entity`, `How connected`, `What could be affected`, `Owner`, `Evidence`, and **qualitative** risk status only if defensible.
5. Right rail: `Change context`, `Evidence`, `Owners to consult`, and `Unknowns / assumptions`.
6. Action: `Prepare review task` **optional P2**. On click, preview the description, selected affected entities, owners, and sources; then require explicit confirmation before creating any external issue.

**Language constraint:** Say `Potential impact` / `May affect` where graph dependency alone does not prove breakage. A graph edge is not a simulation of runtime failure. Avoid `Will break Checkout` unless there is specific supporting evidence.

**Graph-causality demo mode:** An explicitly labeled developer/demo control may change a real FalkorDB relationship in a controlled environment. UI must show what changed, prompt before mutation, re-fetch actual impact, highlight differences (`Removed relationship`, `Newly affected`, `No longer affected`), and offer `Restore seeded graph`. Never simulate a backend change solely in local React state.

### 9.6 Expert Finder (`/people` or `/people/experts?entity=...`)

- Search/select `Payment Service` or another entity.
- Show **ranked people in a clean list**, not a decorative leaderboard or gamified contest.
- Each row: person name, role/team if known, match reason, small evidence chips (ownership, commit, decision, issue, document), and `View evidence` action.
- Optional numeric heuristic score may be shown **only with label** `Evidence score` and a brief `How ranking works` explanation. Do not represent this as universal skill or employee performance.
- Selecting an expert reveals linked work and paths in inspector. Provide a calm `No evidence-backed expert found` state when needed.

### 9.7 Knowledge Freshness / Changes (`/changes`)

- Page title `Knowledge freshness`; subtitle: `Find documents that may need review after system changes.`
- Main content is a **scannable document table**, not a giant graph: `Document`, `Service`, `Last updated`, `Newer related evidence`, `Status`, `Review`.
- States: `Current based on known evidence`, `Review candidate`, `Checking`, `Insufficient history`. **Never claim a document is definitely outdated simply because its timestamp is older.**
- A selected document opens a side-by-side evidence drawer: `Document says` versus `Newer relevant change`; include timestamp, source IDs and `Why flagged` logic.
- **Live update demo:** initial old `Architecture Overview` flagged after D-007/commit; ingest a newer version; show progress, then refresh/re-query; only remove this particular warning when backend results actually change. Show `Updated just now` timestamp if backend returns one; don't make up sync details.
- Optional `Open document` and `Mark for review` actions only if supported.

### 9.8 Connectors (`/connectors`)

- Minimal cards/rows by source category: GitHub, Jira, Slack, Markdown/ADRs, with exact states `Connected`, `Not connected`, `Syncing`, `Error`, or `Demo dataset`.
- If the demo uses fixture data rather than authenticated live provider APIs, mark it as `Demo data` or `Seeded dataset`, not `GitHub connected`.
- Each row: provider, description, state, last successful ingestion (if known), available actions `View details`, `Sync now` (only if implemented), `Connect` (only if implemented).
- Show permissions/scope before real authorization. Avoid dead `Connect` buttons that do nothing.

## 10. Interaction and state machine rules

### Essential flows

**A. Ask → verify → explore**

`Empty Chat → Submit question → Loading → Sourced answer → Select citation → Source inspector → Explore corresponding graph path → Return to chat with context retained`

**B. Decision reasoning → impact**

`Answer about Redis → Open D-007 → Inspect timeline + evidence → Analyze impact of removing Redis → Highlight dependents/owners → Inspect assumptions`

**C. Freshness update**

`Open review candidate → Inspect newer evidence → Ingest updated doc → Wait for verified completion → Re-run freshness query → Update status + evidence list`

**D. Optional write-back**

`Preview review task → See exact payload and destination → Explicit Confirm → Pending → Success with issue link / actionable Error`; no automatic write on mere click of a graph node.

### Standard component states

Every actionable element needs `default`, `hover`, `focus-visible`, `active/selected` (if appropriate), `disabled`, `loading`, and error behavior as relevant. Every query view needs:

- **Loading:** stable skeleton in same layout footprint; input feedback; no shifting columns.
- **Empty:** explicit reason and relevant next action. Differentiate zero records from failed request.
- **Error:** human description, retry, preserve user input; show backend code/details only in expandable diagnostics if safe.
- **Partial evidence:** show what was found and what was not; do not fake citations.
- **Unsupported question:** `I couldn't find enough connected evidence to answer that.` with related suggestions, when available.
- **Long text:** clamp card descriptions, expand via `Show more`; never hide actual citation identifiers.
- **Unlinked source:** show visible `Source unavailable` instead of a broken anchor.

### Keyboard and controls

- `Enter` submits chat; `Shift+Enter` inserts a newline; explicit hint below composer where appropriate.
- `Escape` closes menus, dialogs, source previews, and selection before leaving the page.
- `/` may focus global search **only if implemented** and not while user types in input.
- All clickable card surfaces must be actual buttons or links, keyboard accessible with visible focus.
- Use tooltips for icon-only controls and `aria-label` for screen readers.
- Never use color alone to express selected, stale, high impact, success, or failure.
- Fullscreen graph must have an accessible list/path fallback for non-pointer navigation.

## 11. Motion and microinteractions

Motion should reassure, not entertain:

- Hover/focus: `120–160ms` ease-out; subtle border/background change (not transform scales on every card).
- Inspector/drawer: `180–220ms` ease-out with no massive travel.
- Tab switch: immediate content change with small underline transition.
- Graph path highlight: `150–240ms`, no endlessly pulsing nodes.
- Loading: subtle skeleton shimmer or spinner; disable animation under `prefers-reduced-motion`.
- No parallax on main data pages; avoid heavy blurred animated backdrops and rotating logo.

## 12. Graph semantics and visual encoding

**Entity nodes:** consistent icon, label, accessible textual type. Use type colors from tokens. Source-bearing nodes must link to a valid source inspector if source data exists. Make central service slightly larger than peripheral nodes; avoid huge circles that crowd the viewport.

**Edges:** directional, 1.3–1.8px neutral by default, 2.4px brand tone when on selected evidence path. Display labels such as `USES`, `DEPENDS_ON`, `DECIDED_BY`, `IMPLEMENTED_BY`, `DOCUMENTED_IN` using real backend type names. Relationship direction matters: if graph says `Checkout Service DEPENDS_ON Payment Service`, the arrow must match. When explaining inverse effects, use UI language to make the meaning clear without silently inverting the stored edge.

**Graph evidence contract:** frontend accepts `nodes[]`, `edges[]`, `sources[]`, and any explicit path metadata; graph traversal results come from API/FalkorDB, not a hardcoded diagram. Use stable IDs for React keys and tooltip mapping. If the backend sends only entities but no explicit path ranking, do not claim the UI highlighted the “reasoning path” without deriving and validating it.

**Layout:** bounded directed graph for traces/impact; stable force/radial layout for exploratory local neighborhoods; deterministic seed if layout is force-based. Use `@xyflow/react` or equivalent for pan/zoom/select if it speeds implementation, but the library choice is secondary to readability and correctness.

**Reference limits:** aim for < 20 visible nodes at first load; collapse/expand beyond that. Labels must not overlap at common 1280px widths. Edge clutter should be minimized with filtering, not by hiding critical causal links.

## 13. Copywriting and content guidelines

| Avoid | Prefer |
|---|---|
| “AI has discovered amazing insights!” | “Redis was introduced after PAY-42 to reduce latency.” |
| “This will definitely break checkout.” | “Checkout Service may be affected because it depends on Payment Service.” |
| “Architecture.md is wrong.” | “Architecture Overview may need review; related changes were made later.” |
| “100% accurate” | “Backed by 6 sources” (when true) |
| “Ask me anything!” | “Ask about decisions, services, people, and docs.” |
| “No results” | “No connected evidence found for this question.” |

- Use IDs exactly as returned (`INC-17`, `PAY-42`, `D-007`, `ADR-7`, `8fae2`).
- When company/person values are unknown, show `Not available`, not an invented placeholder.
- `Source` means a real retrievable record; `Related entity` is not automatically a supporting citation.
- Avoid implying a high-confidence answer if the provenance chain is incomplete.
- Use readable human dates in locale and absolute dates in source inspector when recency matters; relative time alone is insufficient for decision history.

## 14. Accessibility and usability bar

- WCAG 2.2 AA aim: normal text >= 4.5:1, large text >= 3:1, non-text controls / focus >= 3:1 as relevant.
- Minimum target size **44 × 44px preferred** for touch-accessible primary controls; 24 × 24px WCAG minimum where exceptions apply.
- Clear and visible focus ring; consistent keyboard navigation order: sidebar → page header/tools → main content → inspector → composer (adapt logically per view).
- Semantic headings, lists and tables, `aria-live` for query result updates, descriptive names for graph buttons, real labels for input.
- Don't use color alone; source icons have text labels; status icons have text.
- Responsive reflow; 200% browser zoom should remain usable, with inspector collapsing rather than obscuring core content.
- Graph view offers a text evidence path or table alternative. No important relationship can be accessed only by hovering.
- Prefer one scrollable main surface; avoid mouse-trap nested scrolling and automatically stealing focus on answer arrival.

## 15. Implementation guidance for Codex

### Architecture and styling

- UI stack follows project plan: **React + TypeScript + Vite + Tailwind CSS**, backend FastAPI and FalkorDB.
- Create `src/styles/tokens.css` from the token block in §5 and map to Tailwind semantic names; do not use ad hoc `bg-[#...]` throughout JSX.
- Suggested folders (adapt to actual repository):

```text
src/
  assets/weave-mark.svg
  components/
    layout/       AppShell, SidebarNav, ContextInspector
    common/       Button, Card, Badge, PageHeader, EmptyState, Skeleton
    chat/         PromptComposer, Message, EvidenceTabs, SourceCitation
    graph/        GraphCanvas, GraphNode, EntityInspector, EvidencePath
    workflows/    DecisionTrail, ImpactTable, ExpertList, FreshnessTable
  pages/          ChatPage, GraphPage, DecisionsPage, ImpactPage,
                  PeoplePage, ChangesPage, ConnectorsPage
  styles/         tokens.css, globals.css
  lib/            api.ts, routeHelpers.ts, graphAdapters.ts
```

- Reuse source records and entity IDs across all pages; do not clone disconnected demo content in each component.
- Mock data may be used during scaffolding, but **label it clearly** and keep components wired to injectable typed data interfaces; production/demo mode must consume actual API responses.
- Only show a source link when `url` exists and is valid; open links with `rel="noopener noreferrer"` when appropriate.
- Graph mutations/re-ingestion must hit real API and invalidate/re-fetch query caches; do not manufacture the changed answer in component local state.
- Use SVG/CSS for the knot logo only after matching the canonical direction; source screenshot pixels are not a scalable production logo.

### Suggested semantic frontend types

```ts
type SupportStatus = 'supported' | 'partially_supported' | 'insufficient_evidence';
type SourceKind = 'incident' | 'issue' | 'message' | 'decision' | 'commit' | 'document' | 'repository';

type EvidenceSource = {
  id: string;
  kind: SourceKind;
  title: string;
  snippet?: string;
  url?: string;
  timestamp?: string;
};

type GraphEntity = {
  id: string;
  type: string;
  name: string;
  properties?: Record<string, unknown>;
};

type GraphRelationship = {
  id: string;
  from: string;
  to: string;
  type: string;
  sourceIds?: string[];
};

type GroundedAnswer = {
  text: string;
  supportStatus: SupportStatus;
  sources: EvidenceSource[];
  nodes: GraphEntity[];
  edges: GraphRelationship[];
};
```

These frontend types are **illustrative adapters**, not a replacement for `08_API_DESIGN.md`. Map real backend response fields carefully; do not silently assume undocumented server payloads.

### Build sequence (time-boxed for hackathon)

**P0 — essential**

1. Implement tokens, fonts, brand lockup, shell and shared controls.
2. Implement minimal initial chat and active grounded chat with source inspector.
3. Implement focused evidence graph with correct node/edge semantics and selection.
4. Implement Decision Trace + Impact as task-focused views or overlays; connect to real API.
5. Add loading/error/partial-evidence states and test with NovaPay golden queries.

**P1 — strong differentiators**

6. Implement freshness list and one verified before/after document ingestion.
7. Implement expert finder ranks with graph-backed explanations.
8. Add demo-only graph change + restore with real persistence (guarded, explicit).

**P2 — optional**

9. Confirmed review-task creation; additional page animations or broad connector marketplace are not priorities.

### Guardrails for Codex

**DO:** respect supplied structure, create real components, use consistent state management, make every control functional or visibly disabled, show evidence and uncertainty, keep layout calm, test at common widths.

**DON'T:** overdecorate, introduce another brand mark, replace task UX with generic chatbot cards, add dashboards of made-up counts, invent graph paths/relationships, add dead buttons, exaggerate document freshness, or mutate records without confirmation.

## 16. Acceptance checklist / visual QA

### Brand and consistency

- [ ] Same interwoven-knot SVG and wordmark on every page; no former EKOS symbol.
- [ ] Inter for UI, Instrument Serif for selected display headings, JetBrains Mono for IDs.
- [ ] One green active navigation row and a consistent sidebar order.
- [ ] No ad hoc color hexes, uncontrolled radius variations, or unapproved decorative effects.
- [ ] Consistent spacing, alignment, inspector width and button states.

### Flow and usability

- [ ] At 1440×900, empty Chat is **uncluttered**: greeting + four cards + question chips + composer + two right cards.
- [ ] At 1280×800, no horizontal overflow, clipped submit button, unreadable graph labels or composer obscuring answer.
- [ ] Active chat has grounded answer, actionable inline citations, evidence path and stable source inspector.
- [ ] Clicking a citation shows the matching snippet/source without losing chat context.
- [ ] Knowledge Graph shows directed relationships correctly and explains selected entities.
- [ ] Decision Trace visibly connects why → discussion → approval → implementation → documentation.
- [ ] Impact Analysis is **visually distinct** from the general graph explorer and uses cautious impact wording.
- [ ] Freshness view shows newer evidence and updates only after successful backend ingestion/re-query.
- [ ] Every loading, error, zero-result and insufficient-evidence path is understandable.
- [ ] All visible buttons/links work, or have an honest disabled state.

### Grounding and demo integrity

- [ ] Source IDs, counts, timestamps and connection states come from actual fixtures/API responses.
- [ ] No fabricated confidence percentages, owner identities, source URLs or success messages.
- [ ] Graph change demo changes FalkorDB and re-queries results rather than changing only frontend state.
- [ ] Demo mutation can be restored deterministically.
- [ ] All NovaPay golden questions are readable and stable during screen recording.

### Accessibility

- [ ] Keyboard reaches all inputs/buttons/links and can dismiss menus/dialogs.
- [ ] Visible focus ring and tested text contrast.
- [ ] Reduced-motion setting respected.
- [ ] Graph provenance also exists in textual form.
- [ ] 200% zoom and inspector-collapse behavior tested.

## 17. Reusable prompt for Codex

> Read `docs/design.md`, the updated PRD, architecture/API specifications, and any `docs/references/*.png` images before coding. Implement **[specific page]** as a production-quality React/TypeScript screen using the design tokens and shared components defined in the design specification. Favor calm editorial hierarchy, accessible interactions, typed data, and evidence-first UX; do not invent statuses, graph facts, logos, or new patterns. Build all described states, use the actual API where available, and provide a brief checklist showing which design requirements are complete and which remain blocked by missing backend contracts.

---

**One-sentence review heuristic:** *Does this screen help a developer understand a connected company fact faster, and can they see exactly why the system believes it?* If not, remove decoration or surface the evidence.
