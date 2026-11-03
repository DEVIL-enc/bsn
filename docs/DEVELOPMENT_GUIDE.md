# Developer Guide & Code Section Map

This guide provides developers with a clear roadmap to navigate the codebase, understand how files are partitioned into sections, and add new features without unnecessary reading time.

---

## 1. Project Directory Structure

```
PSN_Game_Fetcher_CLI/
├── docs/                       # Architectural and technical documentation
│   ├── ARCHITECTURE.md         # System data flow and SSE pipeline
│   ├── API_REFERENCE.md        # Complete REST & SSE API endpoints
│   ├── FRONTEND.md             # UI/UX, Flexbox squash protection, 1:1 artwork
│   ├── SECURITY.md             # NPSSO handling, headers, rate limits
│   └── DEVELOPMENT_GUIDE.md    # This file: navigation & contributor guide
├── public/                     # Zero-dependency frontend client
│   ├── app.js                  # Client logic, SSE listener, modal handlers
│   ├── style.css               # Pure OLED styles, layout, and animations
│   ├── index.html              # HTML shell, preloader, and modal templates
│   ├── author-avatar.png       # Author profile picture
│   └── favicon.png             # Site favicon
├── server.mjs                  # Native Node.js HTTP server & PSN API gateway
├── fetcher.mjs                 # Standalone CLI fetching utility
├── package.json                # Project dependencies and npm scripts
└── README.md                   # Repository overview and master index
```

---

## 2. Code Section Navigation Map

To accelerate development and eliminate code reading fatigue, all primary code files are partitioned into numbered sections with standardized comment headers.

### `server.mjs` Section Index
| Section | Title | Key Responsibilities |
| :--- | :--- | :--- |
| **Section 1** | Configuration & Constants | Port, directories, MIME dictionary, rate window constants |
| **Section 2** | Security & Headers | IP rate limiter, security headers (CSP, nosniff), token sanitizer |
| **Section 3** | Utility Parsers | ISO 8601 duration parser (`parseDuration`), CSV string escaper |
| **Section 4** | Sony PSN API Engine | OAuth token exchange, GraphQL `getPurchasedGames`, activity queries |
| **Section 5** | SSE Streaming Pipeline | EventSource writer (`sendSSE`), multi-page fetch orchestration |
| **Section 6** | HTTP Router & Dispatcher | Route dispatcher (`/api/health`, `/api/library`, `/api/download/*`, static) |
| **Section 7** | Server Lifecycle | Server startup listener and graceful shutdown handlers |

---

### `public/app.js` Section Index
| Section | Title | Key Responsibilities |
| :--- | :--- | :--- |
| **Section 1** | State & DOM Cache | Global state object (`state`), cached element selectors (`els`) |
| **Section 2** | Utilities & Sanitization | Toast notifications, HTTPS URL sanitizer, dynamic fallback artwork |
| **Section 3** | Accordion Drawers | Animated drawer toggles for tutorial and live log stream |
| **Section 4** | Game List & Rows | Row DOM generation, squash-proof height enforcement, tap animation |
| **Section 5** | Tabs & Stats Dashboard | Tab switching (`switchTab`), counts badge updates, PS Plus stats |
| **Section 6** | Modal System | Game spec inspector (`inspectGame`), copy simple list, About modal |
| **Section 7** | Real-Time SSE Listener | `EventSource` subscriber for `/api/fetch-stream`, live progress bars |
| **Section 8** | Lifecycle & Init | Keyboard listeners (`Escape`), event bindings, DOMContentLoaded init |

---

### `public/style.css` Section Index
| Section | Title | Key Responsibilities |
| :--- | :--- | :--- |
| **Section 1** | Design Tokens & Reset | OLED CSS variables (`--bg-oled`), typography, custom scrollbars |
| **Section 2** | App Shell & Top Bar | Minimalist header, brand badge, online ID pill, logout action |
| **Section 3** | Token Input & Logs | Input group, accordion drawers, animated log stream |
| **Section 4** | Tabs & Search Bar | Tab bar navigation, active underline indicators, filter input |
| **Section 5** | Game List Rows | **Squash-Proof Flexbox rules**, `flex-shrink: 0`, 1:1 square artwork |
| **Section 6** | PS Plus Stats Pane | Subscription status tag, benefits grid, membership links |
| **Section 7** | Modal System | Spring zoom entrance animations, guaranteed 1:1 cover boxes |
| **Section 8** | Toast & Floating Pill | Ephemeral toast messages, bottom-left author profile pill |
| **Section 9** | Mobile Responsiveness | Horizontal scroll tabs, full-width search, touch ergonomics |

---

## 3. How to Add a New Feature

### Example: Adding a New Tab (e.g., "Recently Played")
1. **Frontend HTML (`public/index.html`)**:
   - Add a new `<button>` inside `#oledTabsNav` with `data-oled-tab="recent"`.
   - Add a matching `<div class="oled-tab-pane hidden" id="paneOledRecent">` with a list container `<div id="listRecent">`.
2. **Frontend Logic (`public/app.js`)**:
   - In `Section 1`: Add `paneRecent` and `listRecent` to `els.panes` and `els.lists`.
   - In `Section 5`: Add filtering logic inside `renderCurrentTab()` to filter games played in the last 30 days.
3. **Backend (`server.mjs`)**:
   - If new API fields are required, update the Sony GraphQL or Activity query in `Section 4`.
