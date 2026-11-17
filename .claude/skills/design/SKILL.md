---
name: design
description: Building or changing any Glados UI: a page, tab, view, dialog, table, settings tab or button. Load before writing or restyling Vue templates so the result follows the Glados look.
---

# Glados look

The Glados look is documented in `docs/reference/design-look.md` (page skeleton with info,
controls and views bars, buttons, tables, dialogs and forms, feedback, settings tabs, visual
language, copy). Read it in full before building UI, then read one or two existing pages of the
same kind and copy their structure: `features/checklists/views/ChecklistDetailView.vue` for a
document page, `features/products/views/ProductDetailView.vue` for a page with tabs that feed the
controls bar, a catalogue view for a list with a views bar, and two `AdminSettingsTab*.vue`
siblings for a settings tab.

## When a request contradicts the look

If the user asks for UI that goes against the look, say so before building it: name the rule
it breaks and offer the conforming alternative. Build what the user then decides. If they keep
the deviation as the better way, propose the matching change to `design-look.md` so the rule and the
code agree, and change the doc only once they confirm.

## Before calling UI work done

- Every button label is Title Case; buttons without rights are disabled with the reason, not
  hidden.
- Actions sit in the page's controls bar, list views in the views bar, no toolbar inside a tab.
- Dialogs use a `--dialog-width-*` token, lists refresh live, empty states use `EmptyState`.
- Both locales carry every new label; German in informal "Du".
