# Frontend Architecture & Design System

This document outlines the UI/UX architecture, OLED styling tokens, responsive layout rules, squash-proof Flexbox safeguards, and interactive micro-animations in `public/`.

---

## 1. Design Tokens & Palette

The design is built on a pure OLED dark palette with strict high-contrast monochromatic accents:

| Token Name | Value | Purpose |
| :--- | :--- | :--- |
| `--bg-oled` | `#000000` | Deep black background for true OLED displays |
| `--bg-surface` | `#0a0a0a` | Elevated surface for cards, game rows, and drawers |
| `--bg-card` | `#111111` | Dialog bodies, popovers, and badges |
| `--border-subtle` | `#1f1f1f` | Divider lines and row borders |
| `--border-strong` | `#333333` | Interactive buttons, inputs, and active borders |
| `--text-primary` | `#ffffff` | Primary game titles, headers, and active tabs |
| `--text-secondary`| `#999999` | Subtitles, descriptions, and metadata |
| `--text-muted` | `#555555` | Counter tags, timestamp labels, step numbers |
| `--accent-gold` | `#f59e0b` | PlayStation Plus tier highlights and badges |
| `--accent-blue` | `#0070d1` | Sony PlayStation interactive blue |
| `--accent-green`| `#22c55e` | Active membership indicators |
| `--accent-red` | `#ef4444` | Error states and validation shakes |
| `--font-main` | `Google Sans` | Primary sans-serif typography |
| `--font-mono` | `JetBrains Mono` | IDs, tokens, playtime stats, and counts |

---

## 2. Squash-Proof Flexbox Architecture

### The Problem
When displaying a large dataset (e.g., 100+ items) inside a scrollable flex container (`display: flex; flex-direction: column; max-height: 540px; overflow-y: auto;`), CSS Flexbox defaults to `flex-shrink: 1` on every child element. Without protection, Flexbox attempts to shrink all 100+ rows into the 540px container height, collapsing each row down to ~24px and crushing thumbnails into flattened horizontal slivers.

### The Solution
```css
/* Container */
.scrollable-games {
  max-height: 540px;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}

/* Child Item Protection */
.oled-game-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  min-height: 64px;       /* Guaranteed height */
  box-sizing: border-box;
  flex: 0 0 auto;         /* Never grow, never shrink below content */
  flex-shrink: 0;         /* Critical: prevents flex container crushing */
}
```

---

## 3. Strict 1:1 Square Artwork Rule

PlayStation box art is formatted in a 1:1 square ratio. To prevent distorting thumbnails or modal artwork into rectangles:

```css
/* List Item Thumbnail */
.oled-game-icon {
  width: 48px;
  height: 48px;
  min-width: 48px;
  min-height: 48px;
  max-width: 48px;
  max-height: 48px;
  flex: 0 0 48px;
  flex-shrink: 0;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  border-radius: 4px;
}

/* Modal Hero Boxart */
.modal-cover-square-box {
  width: 130px;
  height: 130px;
  min-width: 130px;
  min-height: 130px;
  max-width: 130px;
  max-height: 130px;
  aspect-ratio: 1 / 1;
  flex: 0 0 130px;
  flex-shrink: 0;
  border-radius: 6px;
  overflow: hidden;
}

.modal-square-artwork {
  width: 100%;
  height: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
  display: block;
}
```

---

## 4. Mobile & Touch Ergonomics

On small screens (`<=768px` and `<=560px`):

1. **Horizontal Scroll Tabs (`.oled-tabs-nav`)**:
   - `flex-wrap: nowrap;`
   - `overflow-x: auto;`
   - `-webkit-overflow-scrolling: touch;`
   - `scrollbar-width: none;`
   - `.oled-tab-btn { flex-shrink: 0; white-space: nowrap; }`
   This allows users to swipe naturally across all tabs (PS Plus, PS4 Owned, PS5 Owned, PS4 PS+, PS5 PS+) without stacking or wrapping into awkward multi-line buttons.

2. **Full-Width Filter Input**:
   - The search filter drops neatly below the horizontal tab bar with 100% width, providing ample touch target area for mobile keyboards.

3. **Compact Row Heights**:
   - On mobile, `.oled-game-item` maintains `min-height: 60px;` and uses a `44px x 44px` icon with unclipped typography.

---

## 5. Micro-Animations & Haptics

- **Row Tap Feedback**: Clicking/tapping any game triggers an instant haptic scaling effect (`transform: scale(0.98)`), background illumination (`#1c1c1c`), and a subtle radial flash pseudo-element (`tapFlash`) before opening the modal.
- **Spring Modal Transition**: Modals enter with an exponential ease-out curve (`cubic-bezier(0.16, 1, 0.3, 1)`) scaling up from 0.92 with blur clearance, and dismiss smoothly with keyboard `Escape` or backdrop touch.
- **Accordion Drawers**: Tutorial and log streams utilize CSS grid transition (`grid-template-rows: 0fr -> 1fr`) for zero-layout-shift animated opening.
