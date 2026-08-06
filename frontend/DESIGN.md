# Memory OS — design system

Single source of truth for visual decisions. Every token lives in
`src/index.css`; nothing here should be re-specified in component files.

## Principles

1. **Dark-first.** This is a developer tool that sits next to an editor. Light
   mode is fully supported and flips at runtime via `data-theme` on `<html>`.
2. **One accent, used sparingly.** Amber-gold appears on the logo mark, primary
   buttons, and the active nav indicator. Nowhere else. If everything is
   highlighted, nothing is.
3. **Colour carries meaning, not decoration.** The only other hues in the
   product are the four memory tiers. A reader should be able to learn the
   mapping once and trust it everywhere.
4. **No stock imagery.** Illustrations are inline SVG (`components/brand.tsx`),
   so they theme correctly, cost nothing to load, and work offline — which the
   product claims to do.

## Colour

### Surfaces (4 steps of elevation)

| Token | Dark | Light | Used for |
|---|---|---|---|
| `canvas` | `#0f1014` | `#faf9f7` | Page background |
| `surface` | `#16181e` | `#ffffff` | Cards, sidebar |
| `surface-2` | `#1d2027` | `#f4f3f0` | Inputs, hover, inset panels |
| `surface-3` | `#252932` | `#ebeae6` | Active nav row, toggle track |

### Lines and text

`line` / `line-strong` for borders; `ink` / `ink-2` / `ink-3` for primary,
secondary and tertiary text. Never drop below `ink-3` — it is already at the
contrast floor for small text.

### Brand

`brand` `#d4a24c` (dark) / `#a97724` (light). The light value is darkened to
hold 4.5:1 against white — do not reuse the dark value on light backgrounds.
`brand-soft` is the 12% tint for selected states.

### Memory tiers

Four hues, each ≥30° apart so they stay distinguishable at 6px chip size:

| Tier | Hue | Meaning |
|---|---|---|
| Identity | violet `#8b7fd4` | Stable facts about the person |
| Project | teal `#4fa8a0` | Scope and state of an area of work |
| Session | slate `#7a8394` | Ephemeral. Deliberately the least saturated. |
| Decision | rose `#c25b6e` | A choice, its reasoning, and what it replaced |

Session is muted on purpose: it is the tier you should care about least, and
the palette should say so before the label does.

## Type

System stack (`ui-sans-serif` → `-apple-system` → `Segoe UI Variable`). No web
font: the product is local-first and an offline install should not lose its
typography.

| Role | Size | Treatment |
|---|---|---|
| Page display | 20–30px | `.display` — `-0.028em` tracking, 600 weight |
| Wordmark | 15px | `.wordmark` — `-0.021em` tracking, 600 weight |
| Body | 13px | 1.6 line-height for paragraphs |
| Meta / label | 11px (`text-2xs`) | `ink-3`; uppercase labels get `0.12em` tracking |
| Code | 12.5–13px | `font-mono` |

13px body is intentional — this is a dense information tool, closer to an IDE
than a marketing page.

## Layout

- Sidebar: fixed **264px**, collapses to a drawer below `md`.
- Content: `max-w-4xl` for lists, `max-w-2xl` for settings forms. Full-bleed
  page headers with a bottom hairline.
- Radii: `8px` controls, `12px` cards (`rounded-card`), `999px` pills.
- Spacing: 4px base. Card padding 16–20px; page gutters 24px (32px ≥ `sm`).

## Interaction

- **Focus:** one treatment globally — 2px `brand` outline, 2px offset. Never
  removed, never restyled per component.
- **Hover:** background steps up one surface level. Borders go `line` →
  `line-strong`. 100–150ms, no easing curves longer than that.
- **Motion:** entrances use `.animate-fade-up` (6px rise, 400ms). Everything is
  disabled under `prefers-reduced-motion`.

## Sidebar model (adapted from Slite)

Slite's hierarchy is: workspace switcher → search → AI entry → collapsible
collections → user footer. We keep the shape and swap the middle:

| Slite | Memory OS |
|---|---|
| Collections (doc folders) | **Tiers** — the four memory classes |
| Channels | **Spaces** — projects and areas |
| — | **Sources** — connected tools, each with a live status dot |

Sources carry a status dot rather than a count because a stale connection is
the failure users need to see. Counts sit right-aligned in mono so they form a
scannable column.

## Component inventory

`components/ui.tsx` — `Button` (4 variants × 3 sizes), `Field`, `Card`,
`TierBadge`, `StatusDot`, `SectionTitle`, `cx`.
`components/brand.tsx` — `Mark`, `Wordmark`, `SourceTile`, `ContextGraph`.

Add to these rather than styling inline. If a component needs a fifth button
variant, that is a signal the design needs a decision, not a one-off class.
