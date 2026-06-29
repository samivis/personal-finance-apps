# Personal Finance Dashboard — Web App Design Reference

A design-system reference for the future web-app version of the personal finance
dashboard (currently a Python + Google Sheets automation). The aesthetic is
**quiet luxury / editorial minimalism**: monochrome, enormous whitespace, calm,
confident, with numerals as the hero.

---

## 1. Design Principles / Mood

- **Numerals are the hero.** Money figures are the largest, most deliberate
  elements on every screen. Everything else (labels, nav, structure) recedes to
  let the numbers speak. Use lining + tabular numerals so figures align and feel
  engineered.
- **Restraint over decoration.** No color, no charts, no gradients-as-ornament,
  no shadows, no icons-for-icons'-sake. Meaning is carried by typography,
  spacing, and a single hairline rule.
- **Enormous whitespace = confidence.** Generous margins and vertical rhythm
  signal that the data is in control. Never crowd. When in doubt, add space.
- **Monochrome is a deliberate constraint, not a limitation.** The absence of
  color is the brand. Color is *reserved* — held back for a single future
  semantic moment (e.g. an overspend warning), never used decoratively.
- **Quiet, slow motion.** Transitions are subtle fades and soft eases. Nothing
  bounces, nothing slides aggressively. The interface feels considered, never
  playful.

---

## 2. Color Tokens

Color is intentionally **absent**. The palette is a monochrome warm-gray ramp.
Reserve true color exclusively for a future critical semantic state.

| Token                 | Hex       | Usage                                                        |
|-----------------------|-----------|-------------------------------------------------------------|
| `--canvas`            | `#F2F1EC` | Outer page background — warm off-white / bone.              |
| `--panel`             | `#FFFFFF` | Inset content panel — pure white.                           |
| `--ink`               | `#111111` | Primary text: metric values, card amounts, active nav, bar fill. |
| `--ink-soft`          | `#5A5A5A` | Secondary body text (rare; supporting copy).                |
| `--label`             | `#9A9A9A` | Uppercase wide-tracked labels (metric labels, card labels). |
| `--nav-inactive`      | `#B0B0B0` | Inactive nav items.                                          |
| `--hairline`          | `#E5E5E2` | 1px section rules and dividers.                             |
| `--track`             | `#E8E8E5` | Proportion-bar track (unfilled).                            |
| `--placeholder-from`  | `#F4F4F2` | Allocation image placeholder gradient start.                |
| `--placeholder-to`    | `#EDEDEA` | Allocation image placeholder gradient end.                  |
| `--reserved-alert`    | `#B4452E` | RESERVED. Only for a critical overspend state. Not used in v1. |

Notes:
- The warm tint (canvas slightly toward yellow, not blue-gray) is essential to
  the "bone / paper" feel. Avoid cool grays.
- `--ink` is `#111`, never pure `#000` — softer, more editorial.

---

## 3. Typography

**Recommended face:** a clean neutral grotesque — *Söhne*, *Neue Haas Grotesk*,
*Suisse Int'l*, or *Helvetica Now*. For a no-license web fallback use **Inter**
(Google Fonts) which shares the neutral-grotesque skeleton.

```
font-family: "Söhne", "Suisse Int'l", "Neue Haas Grotesk", "Inter",
             -apple-system, "Helvetica Neue", Arial, sans-serif;
font-feature-settings: "lnum" 1, "tnum" 1;  /* lining + tabular numerals */
```

All numerals use **lining + tabular** figures so columns of money align.

| Role            | Size   | Weight        | Letter-spacing | Transform | Color     | Numerals      |
|-----------------|--------|---------------|----------------|-----------|-----------|---------------|
| Nav link        | 12px   | 500 (medium)  | 0.12em         | uppercase | ink / inactive | —        |
| Metric label    | 11px   | 500           | 0.14em         | uppercase | label     | —             |
| Metric value    | 44px   | 350–400 light-reg | -0.01em    | none      | ink       | lining/tabular|
| Section header  | 11px   | 500           | 0.14em         | uppercase | label     | —             |
| Card label      | 11px   | 500           | 0.13em         | uppercase | label     | —             |
| Card amount     | 22px   | 400           | -0.005em       | none      | ink       | lining/tabular|

Line-height: labels ~1.2; large values ~1.0 (tight, since single-line).

---

## 4. Spacing & Layout

- **Base unit:** 8px. All spacing is a multiple (8 / 16 / 24 / 32 / 48 / 64 / 96).
- **Outer canvas:** full viewport, `--canvas` background.
- **Inset white panel:** centered, `max-width: 1120px`, `--panel` background,
  `border-radius: 6px` (very subtle), margin of ~40px from canvas edges on
  desktop (responsive down to ~16px on mobile). Inner padding ~64px desktop /
  24px mobile.
- **Grids:** two 3-column grids (`display: grid; grid-template-columns: repeat(3, 1fr)`),
  collapsing to 1 column under ~720px.
  - Metric row: 3 equal columns, gap 48px.
  - Allocation cards: 3 equal columns, gap 32px.
- **Vertical rhythm (within panel, top→bottom):**
  - Nav → 64px → Metric row → 80px → Section header → 32px → Allocation cards.
- **Margins:** keep at least 64px breathing room above/below major groups on
  desktop. Whitespace is a feature.

---

## 5. Component Specs

### `NavLink`
- **Anatomy:** single uppercase text item; horizontal group right-aligned in the
  header (`OVERVIEW  HISTORY  SETTINGS`), gap ~32px.
- **Tokens:** 12px / 500 / `0.12em` / uppercase.
- **States:**
  - *active:* `--ink` (`#111`).
  - *inactive:* `--nav-inactive` (`#B0B0B0`).
  - *hover (inactive):* fade to `--ink` over 200ms.
  - *focus:* 1px `--ink` underline offset 4px (keyboard only).

### `MetricStat`
- **Anatomy:** vertical stack — `MetricLabel` (top) + `MetricValue` (below),
  ~8px gap.
- **Tokens:** label = metric-label spec (`--label`); value = metric-value spec
  (`--ink`, 44px, lining/tabular).
- **States:** static. On data refresh, value cross-fades (see Motion).

### `SectionHeader`
- **Anatomy:** uppercase wide-tracked label, then a full-width 1px hairline rule
  directly beneath (gap ~16px).
- **Tokens:** label = section-header spec (`--label`); rule = 1px solid
  `--hairline`, full panel width.
- **States:** static.

### `AllocationCard`
- **Anatomy (top→bottom):**
  1. **Image placeholder** — square (aspect-ratio 1/1), `border-radius: 4px`,
     linear-gradient `--placeholder-from` → `--placeholder-to` (135deg).
  2. **Card label** — uppercase wide-tracked, `--label`, ~16px top margin.
  3. **Card amount** — `--ink`, 22px, lining/tabular, ~4px below label.
  4. **Proportion bar** — thin horizontal bar (~4px tall, `border-radius: 2px`),
     `--track` background with a `--ink` filled segment whose width = spend /
     budget fraction. ~12px below amount.
- **Tokens:** as listed above.
- **States:**
  - *default:* fill width = fraction (e.g. 92%, 54%, 28%).
  - *over budget (future):* fill reaches 100% and uses `--reserved-alert`
    (the one reserved color moment).
  - *hover:* placeholder gradient brightens ~2% over 250ms (optional, subtle).

---

## 6. Motion

- **Principle:** subtle, slow, no bounce. Motion confirms; it never entertains.
- **Fades:** opacity transitions for nav hover, value refresh: `200–250ms`.
- **Value cross-fade on data sync:** old number fades out / new fades in,
  `300ms`.
- **Proportion bar fill on load:** width animates from 0 to target, `600ms`,
  once, on first paint.
- **Easing:** `cubic-bezier(0.4, 0.0, 0.2, 1)` (standard ease) or a gentle
  `ease-out`. Never overshoot / spring.
- **Reduced motion:** respect `prefers-reduced-motion` — disable bar-fill and
  cross-fade, snap to final state.

---

## 7. Mapping Existing Data → UI

The current automation models **weekly Sun–Sat tabs**, a **cascading rollover
budget** (unspent budget carries into the next week), and **spend categories**.
That maps to three screens:

### Overview (default screen — what the mockup shows)
- **Metric row:**
  - `TOTAL LIQUIDITY` — current total balance across tracked accounts.
  - `MONTHLY BURN` — rolling monthly spend (sum of weekly tabs in the month).
  - `LAST SYNC` — timestamp of the most recent Sheets/automation pull.
- **Top Allocations / Current Month:** the largest spend categories
  (Housing/Fixed, Food & Leisure, Transportation, …) as `AllocationCard`s. The
  proportion bar encodes **spend vs. category budget** for the period — first
  card near-full = nearly at budget; partial bars = headroom remaining. This is
  where the **rollover** shows up: a category's effective budget = base budget +
  carried-over remainder, so the bar denominator reflects rollover.

### History
- Per-week view driven by the **Sun–Sat tabs**. A list/stack of weeks, each
  showing that week's burn, budget, and rollover delta (what carried into the
  next week). Same monochrome `MetricStat` + `SectionHeader` language; weeks are
  rows, not colorful charts. Selecting a week reveals its transactions
  (category, amount) as a quiet table.

### Settings
- Category definitions and base budgets, rollover behavior toggle (cascade
  on/off), account/sheet connection, and sync cadence. Plain labeled rows,
  monochrome, no decorative chrome.

**Where each concept surfaces:**
- *Budget* → card proportion-bar denominator + Settings base budgets.
- *Rollover* → adjusts the per-category budget used by Overview bars; explicit
  carried-over delta shown in History.
- *Transactions* → History week detail (and feed the category sums on Overview).
- *Categories* → Overview allocation cards + Settings management.
