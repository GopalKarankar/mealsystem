# Design System Sync to trackintake.co.in — Dev Prompt

**Purpose**: You are updating the "Design System" section in `CLAUDE.md` to reflect the live design of https://trackintake.co.in, the production deployment of this meal-ingestion pipeline. This prompt provides a Before/After snapshot of design tokens, extracted directly from the live site, so the documentation matches reality. The update is documentation-only: `CLAUDE.md` is the sole file to edit in this task.

---

## Context: Before and After

### Current Documented Design (CLAUDE.md, "Design System" section)

```
Colors (defined in `frontend/src/styles/variables.css`):
- **Macros**: Orange (#F97316) = Protein, Blue (#3B82F6) = Carbs, Gold (#D97706) = Fats
- **Status**: Green (#2E7D32) = Success, Red (#D32F2F) = Error, Amber (#F97316) = Warning
- **Base**: White (#FFFFFF) text on Deep Black (#1A1A1A)

Spacing (8px grid): xs=4px, sm=8px, md=16px, lg=24px, xl=32px
Components: Use Tailwind classes with custom colors; refer to Tailwind config for brand colors.
Full design system: See [SPEC.md](./SPEC.md) § 3 (Visual Design System)
```

This is a **dark theme** (black background, white text) with high-contrast status colors for macros and errors.

### Live Website Design (trackintake.co.in, extracted 2026-09-08)

Navigation extracted via computed styles inspection on `/dashboard` and homepage hero sections:

**Colors & Palette**:
- **Accent orange**: `#FF7043` — primary brand color (logo "Track" text, floating action buttons, active pill/filter backgrounds, icon accents)
- **Heading text**: `#263238` (dark gray, bold, for H1/H2)
- **Body text**: `#546E7A` (medium gray, for paragraphs and secondary labels)
- **Background page**: `#FFFDF9` (off-white/cream, very warm)
- **Background section alternates**: `#FAF3EB` (warmer cream, for repeated section blocks)
- **Neutral surface**: `#F3F4F6` (light gray, for disabled/inactive states and form backgrounds)
- **Tinted category chips** (icon + label backgrounds, 60% opacity fills with 700-weight dark text):
  - Orange: `#FFEDD5` bg / `#C2410C` text (meals, food categories)
  - Sky blue: `#E0F2FE` bg / `#0369A1` text (water, hydration)
  - Rose/pink: `#FFE4E6` bg / `#BE123C` text (alerts, metrics like weight)
- **Alert/error red** (solid, no tint): `#D64444` (validation errors, critical warnings)

**Typography**:
- Font family: `Roboto, sans-serif` (throughout; no serif headlines)
- Weight scale: 400 (body), 700 (labels in chips), 800 (logos)
- The wordmark is bipartite: **"Track"** in bold orange (`#FF7043`), **"Intake"** in dark (`#263238`), bold, no decorative icon

**Border radius & spacing**:
- Pills/circular elements: `border-radius: 16px` (filter chips, avatar circles, small FABs)
- Full circles (avatar initials, FAB buttons): `border-radius: 50%` / `rounded-full`
- Card corners: `border-radius: 16px`
- Card header insets: `border-radius: 12px 12px 0px 0px` (top corners only, flat bottom)
- Form inputs: `border-radius: 8px`

**Component patterns**:
- Floating action buttons: Two fixed circular FABs bottom-right (⚡ bolt icon, chat/assistant icon), `#FF7043` orange background, white icons, `32px` diameter
- Filter/category pills: Outlined (light gray `#F3F4F6` bg) when inactive, solid orange (`#FF7043`) when active; rounded-full
- Stat cards: White background, `rounded-2xl` (24px), soft shadow (`box-shadow: 0 2px 8px rgba(0,0,0,0.08)`), numeric value in orange accent, descriptive label in body gray
- User avatar: Circular (`rounded-full`), orange background, white initials (no photo)
- Section dividers: Wavy SVG dividers between major sections (decorative, not structural)
- Meals/water tracker cards: Column layout (icon chip, macro breakdown, timestamp), white card body

**This is a light, warm, modern design** (cream/white backgrounds, warm orange accent, sans-serif, rounded soft corners) — the opposite of the dark documented spec.

---

## Current Architecture

**File**: `CLAUDE.md`, section "## Design System" (lines ~390-410 in current version)

**File references in the design section**:
- `frontend/src/styles/variables.css` — defines color CSS custom properties and shadows
- `frontend/tailwind.config.js` — extends Tailwind colors with `primary`, `accent`, `status` groups, plus borderRadius and boxShadow
- `frontend/src/styles/globals.css` — imports variables, sets Tailwind base styles
- Implicit references to components:
  - `frontend/src/components/*/` — use Tailwind classes + CSS variables to style
  - Specific example: `frontend/src/components/layout/Navbar.jsx` (logo area) and `frontend/src/pages/Login.jsx` (background gradients) don't match the documented palette

**Current code state** (out of sync with the documented spec, and further from the live site):
- `Navbar.jsx:8-9` — uses 🍽️ emoji + "Meal Tracker" text; live site has "Track" (orange) + "Intake" (dark) wordmark
- `Login.jsx:28` — uses emerald/lime gradient background; live site has warm cream `#FFFDF9`
- `variables.css` — defines `--color-primary-black: #1A1A1A` and macro colors like protein `#F97316`; live site uses `#FF7043` and dark heading color `#263238`
- `tailwind.config.js` — no `fontFamily` override; live site uses Roboto explicitly

**Information architecture note** (out of scope for this sync):
The live site's hamburger menu exposes a larger navigation tree (Home, Tools, Health, Diet, Progress, Blogs, Appointments, Plans) than the current codebase implements. This is an IA difference, not a design-token difference. This sync focuses on colors, typography, and spacing only.

---

## Target Architecture

Replace the **entire** "## Design System" section in `CLAUDE.md` with the following block:

```markdown
## Design System

**Colors** (defined in `frontend/src/styles/variables.css`):
- **Brand accent**: Orange (#FF7043) — primary color for buttons, active states, highlights, and logo wordmark
- **Text**:
  - Heading: #263238 (dark gray, 700+ weight for contrast)
  - Body/secondary: #546E7A (medium gray, regular weight)
  - On orange: #FFFFFF (white, for button text and light overlays)
- **Backgrounds**:
  - Page default: #FFFDF9 (warm off-white, very light cream)
  - Section alternate: #FAF3EB (warmer cream, for repeated blocks)
  - Neutral/disabled: #F3F4F6 (light gray, for inputs and inactive states)
  - Card: #FFFFFF (white, with soft shadow)
- **Category/macro tints** (60% opacity background + 700-weight dark text for badges and chips):
  - Protein/meals: #FFEDD5 background / #C2410C text
  - Water/hydration: #E0F2FE background / #0369A1 text
  - Weight/alerts: #FFE4E6 background / #BE123C text
- **Status**:
  - Error/validation: #D64444 (solid red, no tint)
  - Success: #2E7D32 (kept for compatibility with existing logic; refine to match accent if needed)
  - Info: #0369A1 (blue, from water tint)

**Typography**:
- Font family: Roboto, sans-serif (no serifs)
- Weight scale:
  - 400 (regular): body text, labels
  - 700 (bold): category chips, secondary labels
  - 800 (extra-bold): logo wordmark "Track" and "Intake"
- Sizing: Responsive; heading (H1) is 36px on desktop, scaled down on mobile

**Spacing** (8px grid, **unchanged from current**):
- xs=4px, sm=8px, md=16px, lg=24px, xl=32px

**Border radius**:
- Pill shapes (filter chips, circular avatars, FABs): `border-radius: 50%` / Tailwind `rounded-full`
- Card corners: `border-radius: 16px` / Tailwind `rounded-2xl`
- Card header top corners only: `border-radius: 12px 12px 0px 0px` / custom
- Form inputs: `border-radius: 8px` / Tailwind `rounded-sm`

**Shadows**:
- Card/lift effect: `0 2px 8px rgba(0, 0, 0, 0.08)` (soft, subtle)
- Hover/active elevation: `0 4px 12px rgba(0, 0, 0, 0.12)` (slightly darker/larger)
- Modal/overlay shadow: `0 8px 24px rgba(0, 0, 0, 0.15)` (deep shadow for overlays)
(These already exist in `variables.css` and can be kept unchanged.)

**Key component patterns**:
- **Logo/wordmark**: Bipartite: "Track" in bold orange (#FF7043), "Intake" in bold dark (#263238). No emoji or icon.
- **Floating action buttons**: Two fixed circular FABs (bottom-right corner), orange background, white icons, 32px diameter, soft shadow.
- **Filter/category pills**: Outlined (light gray #F3F4F6 background, dark text) when inactive; solid orange (#FF7043) background, white text when active. Rounded-full.
- **Stat cards**: Column layout, white background (#FFFFFF), rounded-2xl corners, soft shadow. Icon in orange-tinted chip (top-right), numeric value in orange accent, descriptive label in body gray.
- **Avatar**: Circular (rounded-full), orange background, white initials text (no photo).
- **Water/meal tracker**: Cards stacked, each with icon, macro breakdown, timestamp. Tinted category chip for the food/water type.
- **Section dividers**: Wavy SVG ornaments between major sections (decorative, not load-bearing for semantics).

**Design principles**:
- Warm, inviting aesthetic: cream backgrounds with orange accent create a friendly, approachable feel.
- Accessible contrast: heading #263238 on cream #FFFDF9 meets 4.5:1 WCAG AA standard; body text #546E7A on same background meets 3:1.
- Rounded, soft corners everywhere (no sharp edges): fosters trust and calm.
- Orange (#FF7043) as the single call-to-action color: all primary CTAs and active states use this to guide user attention.

**Related files**:
- `frontend/src/styles/variables.css` — CSS custom properties for colors, shadows, transitions
- `frontend/tailwind.config.js` — Tailwind theme extensions (colors, borderRadius, boxShadow)
- `frontend/src/components/layout/Navbar.jsx` — logo wordmark ("Track" + "Intake")
- `frontend/src/pages/Login.jsx` — background, card styling
```

---

## Rules You Must Preserve

1. **Section title and location**: Keep "## Design System" as a top-level section in `CLAUDE.md`. Do not rename or move it.

2. **No SPEC.md cross-reference**: The original section ends with "Full design system: See [SPEC.md](./SPEC.md) § 3 (Visual Design System)". Since `SPEC.md` does not exist in the repo (also noted in `docs/parakeet-stt-swap-prompt.md`), the target block removes this reference. If `SPEC.md` is created later, re-add the cross-reference then.

3. **Preserve surrounding sections**: Do not edit any other section in `CLAUDE.md`. The sections before ("## Accessibility & Responsive Design") and after (if any) remain unchanged.

4. **File paths remain the same**: The prompt specifies files to be *documented* (like `variables.css`, `tailwind.config.js`), not to be edited. Only `CLAUDE.md` is edited.

5. **Tone and detail level**: Match the current CLAUDE.md voice: practical, implementation-focused, with code examples and file cross-references where relevant. Avoid overly technical jargon; this is a guide for developers using the codebase, not a design-theory paper.

---

## Known Pitfalls

1. **Doc-first, code-second**: After this prompt is run, `CLAUDE.md`'s Design System section will describe the live site look, but `frontend/src/styles/variables.css`, `tailwind.config.js`, `Navbar.jsx`, and `Login.jsx` will still reflect the old dark theme. These files are intentionally *not* edited by this prompt. To bring the code in line with the live site *and* this updated doc, a follow-up task (separate from this prompt) will be needed. See "Optional Follow-Up" below.

2. **Information architecture gap**: The live site's navigation tree is much larger (Home, Tools, Health, Diet, Progress, Blogs, Appointments, Plans) than what the codebase currently implements. This sync addresses *design tokens only*; IA changes are out of scope and belong to a separate roadmap/epic.

3. **Avatar and initials pattern**: The live site shows user avatars with initials (not photos). If photos are added later, update the component note in the Design System section to reflect that change.

4. **Emoji removal**: The current Navbar uses 🍽️ emoji as a logo; the target wordmark "Track"+"Intake" has no emoji. Callers of the Navbar component should expect the logo to be text-only going forward (important for accessibility and mobile layouts).

---

## Optional Follow-Up (Not Required by This Prompt)

**If the team wants code to match the updated doc**, a separate pass will be needed to update:
- `frontend/src/styles/variables.css` — swap color values (e.g., `--color-primary-black` → `#263238`, accent orange → `#FF7043`)
- `frontend/tailwind.config.js` — add `fontFamily: { sans: ['Roboto', 'sans-serif'] }` and update color palette
- `frontend/src/components/layout/Navbar.jsx` — replace emoji + "Meal Tracker" with "Track" + "Intake" wordmark, update background color to `#FFFDF9`
- `frontend/src/pages/Login.jsx` — replace emerald/lime gradient with `#FFFDF9` background, update card styling to match Design System
- Any other component files that hard-code colors or use the old black theme

This follow-up is **not** part of the current prompt; it is noted here for future planning.

---

## Testing & Verification Checklist

- [ ] `CLAUDE.md` opens and renders correctly in markdown reader or browser (check for syntax errors)
- [ ] The "## Design System" section is the only section modified (use `git diff CLAUDE.md` to verify no accidental edits to other sections)
- [ ] All color hex codes in the target block are valid (8-digit format, `#RRGGBB`)
- [ ] File paths mentioned (`frontend/src/styles/variables.css`, etc.) exist in the repo (confirmed at research time; no deletions expected)
- [ ] Dangling reference to `SPEC.md` is deliberately removed (not an oversight)
- [ ] The new block is self-contained and makes sense without reference to prior context (someone reading it for the first time should understand the palette and component patterns)
- [ ] Tone matches the rest of `CLAUDE.md` (practical, file-focused, actionable for developers)
- [ ] If pasting the target block manually, ensure no trailing whitespace or formatting breaks

---

## Sources & References

- **Live reference**: https://trackintake.co.in/dashboard (desktop, logged-in view showing hero + meals list)
- **Live reference (auth)**: https://trackintake.co.in/login (login page, showing Navbar logo and background)
- **Extracted via**: Browser DevTools → Inspect → Computed Styles on elements (Navbar, hero H1, buttons, cards, avatar, filter pills)
- **Current doc**: `CLAUDE.md`, "## Design System" section (lines ~390-410)
- **Format reference**: `docs/parakeet-stt-swap-prompt.md` (structure: Purpose → Before/After → Current Architecture → Target → Rules → Pitfalls → Checklist)
- **Related prompt**: `docs/parakeet-stt-swap-prompt.md` (note on dangling SPEC.md reference, same issue)
- **Codebase files** (documented, not edited):
  - `frontend/src/styles/variables.css` — current CSS custom properties
  - `frontend/tailwind.config.js` — current Tailwind theme
  - `frontend/src/components/layout/Navbar.jsx` — current logo implementation
  - `frontend/src/pages/Login.jsx` — current background styling
  - `frontend/src/styles/globals.css` — baseline styles

---

## Summary

This prompt updates the **documentation only** to reflect the live design of trackintake.co.in. The target "Design System" section in `CLAUDE.md` will document a warm, light, modern aesthetic with a single orange accent, Roboto typography, and rounded soft corners — replacing the current dark theme with white text on black. This brings the documented spec into alignment with what users see on the live site. Follow-up code changes (to `variables.css`, `tailwind.config.js`, `Navbar.jsx`, etc.) are not included in this prompt but are noted as a future task if full parity is desired.
