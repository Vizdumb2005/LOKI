# LOKI Web — Design System (DESIGN.md)

Machine-readable styling contract for the `apps/web` séance UI.
**Scope: cosmetics only.** Class names, DOM structure, component props, state,
event handlers, timings with behavioral meaning, and all business logic are
FROZEN. Styling agents may only change values in `src/index.css` (and the
inline flash-avoidance block in `index.html`) following the tokens below.

Conventions: all color tokens are defined as **adaptive pairs**
(`--x` dark-default + light override under `prefers-color-scheme: light` /
`[data-theme="light"]`). Spacing unit `1u = 0.25rem (4px)`. Type in `rem`.

---

## 1. Semantic color tokens (adaptive pairs)

| Token | Dark (default `:root`) | Light (`light` scheme) | Usage |
|---|---|---|---|
| `--bg` | `#0b0d10` | `#f5f1e6` | page background |
| `--bg-elev-1` | `#10141a` | `#efe9d8` | raised surfaces under panels |
| `--panel` | `rgba(255,255,255,0.035)` | `rgba(43,34,8,0.045)` | card / button fill |
| `--panel-hover` | `rgba(255,255,255,0.06)` | `rgba(43,34,8,0.08)` | card / button hover fill |
| `--panel-border` | `rgba(255,255,255,0.09)` | `rgba(43,34,8,0.16)` | hairline borders |
| `--panel-border-strong` | `rgba(255,255,255,0.16)` | `rgba(43,34,8,0.28)` | emphasized borders, table rules |
| `--text` | `#d6d3cb` | `#2a2620` | primary text (AA on `--bg` both schemes) |
| `--text-bright` | `#e8e2d2` | `#1c1917` | serif message / reveal text |
| `--muted` | `#8a877f` | `#6f6a5e` | secondary text, labels (AA-large / non-essential only) |
| `--gold` | `#c9a227` | `#8a6d1a` | accents, reveal-stage, voice feedback |
| `--gold-bright` | `#e6c757` | `#a07f1f` | wordmark, headings, prediction |
| `--gold-glow` | `rgba(201,162,39,0.25)` | `rgba(138,109,26,0.18)` | text-shadow / glow color |
| `--emerald` | `#2fbf8f` | `#14805d` | success, live sensing, meter start |
| `--emerald-soft` | `#a9e4cd` | `#0f6b4d` | correct-answer text, sensing chip |
| `--emerald-glow` | `rgba(47,191,143,0.5)` | `rgba(20,128,93,0.35)` | pulse ring, hover glow |
| `--danger` | `#c05b5b` | `#a03a3a` | errors, destructive |
| `--danger-soft` | `#e4b6b6` | `#7c2d2d` | error text on tinted bg |
| `--danger-glow` | `rgba(192,91,91,0.4)` | `rgba(160,58,58,0.3)` | error borders |
| `--track` | `rgba(255,255,255,0.07)` | `rgba(43,34,8,0.12)` | meter / progress track |
| `--overlay` | `rgba(11,13,16,0.85)` | `rgba(245,241,230,0.88)` | floating sensing pill bg |

Ambient background washes (body, decorative only, `transparent 60%` stops kept):
- wash A: `radial-gradient(60rem 40rem at 15% -10%, <emerald @ 0.09 dark / 0.10 light>, transparent 60%)`
- wash B: `radial-gradient(50rem 35rem at 110% 110%, <gold @ 0.07 dark / 0.10 light>, transparent 60%)`

Focus ring (both schemes): `outline: 2px solid var(--gold); outline-offset: 2px`
on `:focus-visible` for all interactive elements (buttons, inputs, summary, links).

---

## 2. Typography scale (system stacks only — zero webfont dependencies)

```css
--serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
--sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
--mono: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
```

| Step | size / lh / spacing | family | used by |
|---|---|---|---|
| `--t-display` | `2.6rem / 1.1 / 0.35em` | serif 400 | `.wordmark` |
| `--t-reveal` | `2.4rem / 1.15 / 0` | serif 400 | `.prediction` |
| `--t-message` | `1.45rem / 1.5 / 0, italic` | serif | `.message` |
| `--t-h2` | `1.25rem / 1.35 / 0` | serif 400 | `.effect-card h2` |
| `--t-body` | `0.98rem / 1.55 / 0` | sans | body, `.option-btn` |
| `--t-small` | `0.9rem / 1.5 / 0` | sans | meta, survey, ledger |
| `--t-caption` | `0.8rem / 1.45 / 0` | sans/mono per component | meter labels, table heads |
| `--t-micro` | `0.75rem / 1.4 / 0` | mono | counts, chips, sparkline label |
| `--t-eyebrow` | `0.8rem / 1.4 / 0.2em, uppercase` | sans | `.reveal-label` |

Wordmark glow: `0 0 24px var(--gold-glow)`. Prediction glow: `0 0 30px var(--gold-glow)`.
Message ink uses `--text-bright` with gold left rule `3px solid <gold @ 0.45>`.

---

## 3. Spacing, radius, grid

Spacing scale (multiples of `1u = 0.25rem`): `1u 2u 3u 4u 5u 6u 8u 10u 14u`.
Page container: `max-width: 860px; padding: 2.5rem 1.25rem 4rem` (`.app` — frozen).
Grid: `.effect-grid` → `repeat(auto-fit, minmax(260px, 1fr))`, gap `1.1rem` (frozen).
Breakpoints (no media queries in v1 except light scheme + reduced motion; grid is
fluid by construction — do not add breakpoints without a layout bug).

Radii: `--r-sm: 4px` (key hints) · `--r-md: 8px` (video, stop btn) ·
`--r-lg: 10px` (buttons, inputs, error) · `--r-xl: 12px` (banners, sensing pill) ·
`--r-2xl: 14px` (effect cards). Pills/capsules where already round stay round.

---

## 4. Shadow depths (layered, color-matched)

```css
--shadow-1: 0 1px 2px rgba(0,0,0,0.35);
--shadow-2: 0 4px 14px rgba(0,0,0,0.35);
--shadow-3: 0 10px 32px rgba(0,0,0,0.45);
--shadow-gold: 0 0 14px rgba(212,175,55,0.22);   /* salient / reveal glow */
--shadow-emerald: 0 0 12px rgba(47,191,143,0.25); /* live / success glow */
```
Light scheme: same shapes at `rgba(43,34,8,…)` neutrals, alpha × 0.6.

## 5. Gradient borders (premium cards & primary buttons)

Recipe (no extra DOM): keep `border: 1px solid transparent` + layered background
```css
background:
  linear-gradient(var(--bg-elev-1), var(--bg-elev-1)) padding-box,
  linear-gradient(135deg, <gold @ 0.55>, <panel-border> 40%, <emerald @ 0.35>) border-box;
```
Applied to: `.effect-card:hover`, `.option-btn:hover` (emerald-leaning variant),
`.sensing-live` (emerald-leaning, always-on). Base (non-hover) state keeps the
flat hairline — gradient appears only on hover/focus/active to avoid a noisy wall.

## 6. Motion (timings with behavioral meaning are FROZEN)

| Token | value | use |
|---|---|---|
| `--dur-instant` | `0.15s ease-out` | button hovers, chip fades |
| `--dur-swift` | `0.2s ease-out` | card hover border |
| `--dur-lift` | `0.15s ease-out` | card translateY |
| `--dur-flow` | `0.5s ease` | meter / prob-bar width (FROZEN) |
| `--ease-premium` | `cubic-bezier(0.22, 1, 0.36, 1)` | reveals, lifts (easeOutExpo-ish, frictionless) |

FROZEN (encode UX research — never retime): `salient-in 0.9s ease 1.2s both`
(delayed emphasis onset), `stage-in 0.6s ease both`, `pulse 1.4s ease-in-out
infinite`. Only shadow/color richness inside these keyframes may evolve.

Micro-interactions: card hover `translateY(-2px) + shadow-2 + gold border`;
button hover `translateY(-1px)` + tinted fill; button `:active` `translateY(0)
scale(0.99)`; focus-visible ring (§1); disabled = `opacity 0.5–0.55, cursor: wait`
(unchanged semantics).

`@media (prefers-reduced-motion: reduce)`: ALL animations/transitions
`none` — mandatory accessibility guard (new; behavior-neutral).

---

## 7. Component spec (class names FROZEN — values only)

- `.effect-card`: panel fill, hairline, r-2xl, pad `1.4rem 1.5rem`; hover →
  gradient border (§5) + lift + shadow-2. h2 gold-bright serif; p muted; `.begin` emerald.
- `.option-btn`: panel fill, hairline, r-lg, pad `0.7rem 1.2rem`; hover →
  emerald tint fill + gradient border (emerald variant) + lift-1px; `.correct` /
  `.wrong` tinted borders + soft text (tokens §1); `.subtle` muted → text on hover;
  `.mic-btn` dashed border kept. `.option-salient`: FROZEN animation, gold end-state.
- `.message`: serif italic message step, bright ink, gold left rule, min-height kept.
- `.reveal` / `.prediction` / `.confidence`: centered; prediction reveal-step +
  gold glow; confidence mono muted.
- `.meter` / `.prob-bar`: track token; fills emerald→gold gradient (meter) /
  emerald (prob); FROZEN 0.5s width transition.
- `.curtain`, `.ledger`: top hairline sections; `summary` muted → text on hover;
  tables: muted 500 heads, hairline row rules; mono stats.
- `.survey`: top hairline, column gap; invite gold italic; range inputs full-width
  with gold/emerald accent (`accent-color: var(--gold)`).
- `.sensing-live`: fixed pill, overlay bg + blur(6px), emerald hairline → gradient
  border always-on, shadow-2; `.pulse` FROZEN keyframes; video mirrored (FROZEN transform).
- `.error`: danger tint bg + danger-glow border, r-lg, soft-danger text.
- `.app-header` / `.wordmark` / `.tagline` / `.app-footer`: centered; wordmark
  display step + glow; footer muted small.
- `.sensing-banner`: emerald tint panel + emerald hairline, r-xl.
- `.freetext-row input`: panel fill, hairline, r-lg; focus → emerald border
  (outline none + ring, §1).
- `.delete-btn`: ghost; hover → danger text + danger-glow border.
- `.key-hint`, `.counts`, `.sparkline`, `.voice-feedback`, `.reveal-stage`,
  `.archived-note`, `.survey-invite`, `.curtain-note`, `.debrief` (shares
  `.curtain-note` class): token re-skins only, layout untouched.

Contrast floors: body text ≥ 4.5:1 on bg both schemes; muted used for
large/secondary/non-essential text only; gold text on dark ≥ 3:1 (decorative +
large); light-scheme golds darkened to hold AA for body-size use.

---

## 8. Phase 3 — refactor roadmap (for downstream agents)

R0. DONE in this pass: full token system in `src/index.css`, light-scheme
overrides (CSS-only, zero JS), premium hover/gradient/focus/reduced-motion layer.
R1. Webfont swap (optional): add `<link>` for Fraunces (display serif) +
Inter (sans) in `index.html`, prepend to `--serif`/`--sans`, keep system
fallbacks; verify offline fallback still AA. Do NOT add font-loading JS.
R2. If Tailwind is ever adopted: map tokens 1:1 into `tailwind.config`
(`colors.*` ← §1, `fontFamily` ← §2, `boxShadow` ← §4, `borderRadius` ← §3,
`transitionTimingFunction.premium` ← §6); components keep class names until a
dedicated migration milestone renames them with snapshot tests.
R3. Component-library extraction (only if a 2nd surface appears): lift
`.option-btn`, `.effect-card`, `.meter` into shared CSS partials
(`styles/tokens.css`, `styles/components.css`) imported by `index.css` —
no CSS-in-JS, no new deps.
R4. Never in cosmetic passes: DOM/class/prop/state/event/endpoint/schema changes;
retiming FROZEN animations; tuning κ or thresholds; touching `services/`,
`simulator/`, `experiments/`, tests (except snapshot updates with approval).
