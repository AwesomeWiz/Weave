# UI refinement verification — October 16, 2026

Implemented as a frontend-only refinement. Backend code, API types/contracts, graph IDs/directions, retrieval, context building, citation validation, LLM behavior and support semantics are unchanged. The original knot and warm paper/forest palette remain in use. Unfinished features remain labeled coming later; development data remains explicitly labeled.

## Implemented behavior

- Bundled Source Serif 4 variable font (OFL-1.1), with optical sizing, weight 500 greetings and weight 600 page headings/wordmark. Inter remains the body font. System monospace replaces the extra downloaded code font. No external font request at runtime.
- Curated morning, afternoon, evening and late-night greeting pairs selected with browser-local `Date.getHours()`. The pair is chosen once in app state and retained in sessionStorage across reloads. No timers or external services. Corrupt/blocked storage is handled gracefully.
- Optional preferred name under the sidebar's pencil control. The browser-local preference is trimmed, control characters removed and capped at 32 Unicode characters; users can save, edit or clear it. No employee names or identity inference. React renders it as text. Storage failure leaves the current in-memory preference usable.
- Welcome composer shares submission code with the active composer and sits 28px below suggestions (26px on mobile). The welcome stack is centered when it fits and scrolls on shorter screens. Active composer occupies its own bottom row and never covers conversation content. Enter, Shift+Enter, IME handling, request/loading/error states and workspace context remain.
- Viewport-height CSS Grid shell: independently scrollable navigation, center and inspector. Right details have a sticky header. Selection changes reset only inspector content to its top; the main conversation is not scrolled.
- Independent left/right collapse preferences in localStorage. Left becomes an icon rail; right releases its full width. Selecting a node/source reopens the inspector. Collapse preserves selection; X or Escape clears selection and closes details. Accessible buttons describe those different actions.
- Tablet navigation uses a compact rail and expandable drawer; tablet/mobile details use a focus-contained modal-style drawer. Background main content is inert while a drawer is open; Escape dismisses it and focus returns to the trigger. Desktop panels do not trap focus.
- Increased graph lane/Dagre spacing, clearer label surfaces, selected node/neighbor borders and connected-edge emphasis. Selection does not rerun layout. The graph stays mounted across tabs and retains pan/zoom across sidebar changes. First fit waits for visible, measured nodes and a nonzero canvas, including rapid tab changes during lazy loading. A viewport-size change preserves pan/zoom; Fit view remains available to recenter.
- Graph bundle loads on demand. Timeline ordering uses parsed timestamps, with unknown dates last. Sources show genuine titles, canonical IDs, types and available dates. Inspector timestamps use a consistent UTC label; missing values are explicit. Relationship table wraps within mobile width. Tabs support Left/Right/Home/End keys and visible focus.

## Automated checks

| Check | Result |
| --- | --- |
| Frontend Vitest | 41 passed (18 API, 8 workflow/preferences, 15 greeting/date cases) |
| ESLint | Passed |
| TypeScript | Passed |
| Production build | Passed; graph split into a separate chunk, no size warning |

New cases cover all daypart boundaries, session stability, optional/stored/long names, malformed/unavailable storage, UTC/invalid dates, independent sidebar preferences, selected-node preservation, Escape, related-entity navigation, keyboard tabs and welcome/active composer placement. Component workflow tests stub the graph; browser checks below exercise real React Flow. Backend tests were not rerun for this frontend-only change; their last recorded result remains 49 passed and one real integration test skipped.

## Rendered browser checks

Used Playwright against the existing Vite server and FastAPI in explicit fixture mode, without intercepted API responses. Those servers predated this work and were left running. No successful new owned preview server was started.

- Visually inspected 1920×1080, 1440×900, 1366×768, 1024×768 and 390×844 layouts. No horizontal document overflow in measured views. Long names wrap; shorter/mobile screens scroll the welcome stack naturally.
- Confirmed the loaded heading font is Source Serif 4 Variable, weight 500. Checked source font package license and bundled font files.
- At 1440px, measured main widths for all panel configurations: both expanded 874px; left collapsed 1054px; both collapsed 1364px; right collapsed 1184px. Preferences survive reload.
- Selected D-007 after scrolling down: main scrollTop remained 295 before/after; the graph viewport transform was identical. Inspector header remained in the viewport while its own content scrolled.
- Collapsing/reopening details preserves D-007 selection. Graph → Timeline → Key sources → Relationships → Graph preserves graph transform and selection. Actual returned counts: 6 sources, 6 timeline records, 14 relationships.
- Reproduced and fixed hidden-canvas first-fit timing by immediately switching away from the graph while loading, then returning. The graph fits the visible canvas rather than fitting a zero-size container.
- Mobile/tablet details open within viewport boundaries. Related navigation from D-007 to PAY-42 works. Escape closes the drawer and returns focus to the original graph node. Navigation drawer and Shift+Tab focus containment were exercised.
- Mobile relationship table measured 342px content width and 342px scroll width, so all three columns remain available without horizontal clipping. A 390×480 reduced-height viewport keeps the multiline active composer visible.
- Final desktop interaction pass recorded no browser console warnings/errors. Development hot replacement emitted transient React Flow type-registration warnings during edits; the fresh-page final pass did not reproduce them.

Screenshots are ignored local QA artifacts under `.local/refined-*.png`, including `refined-home-1440.png`, `refined-active-1366.png`, `refined-desktop-final.png`, `refined-mobile-inspector.png` and `refined-mobile-final.png`. Some stress-test screenshots intentionally contain a long temporary preferred name; that browser preference was cleared after testing.

## Remaining limits

- Physical phone virtual-keyboard behavior was not tested. Desktop browser viewport resizing tested reduced height, and the shell uses `dvh`, safe-area padding and a 16px mobile textarea.
- No broad screen-reader or WCAG conformance audit was performed. Keyboard, focus, responsive layout and drawer interactions were exercised.
- Real FalkorDB retrieval remains blocked on teammate integration and seeded evidence, as documented in `REAL_INTEGRATION_HANDOFF.md`. UI fixture verification does not establish real graph success.

## Changed files

`frontend/src/App.tsx`, `components/Inspector.tsx`, `components/EvidenceGraph.tsx`, new `components/WorkspacePanel.tsx`, new `preferences.ts`, `format.ts`, `main.tsx`, `styles/tokens.css`, `styles/globals.css`, `App.test.tsx`, new `preferences.test.ts`, `frontend/package.json`, `frontend/package-lock.json`, and the design/verification documentation.
