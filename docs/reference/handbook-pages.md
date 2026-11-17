# handbook pages

The workflow and the writing rules for in-app handbook pages and the question-mark buttons that open them. The concept is in [CONTRIBUTING.md section 6](../CONTRIBUTING.md#6-handbook-pages).

- [1 files and rendering](#1-files-and-rendering)
- [2 workflow](#2-workflow)
- [3 writing style](#3-writing-style)

## 1 files and rendering

- The handbook is markdown under `frontend/src/features/handbook/content/<locale>/<section>/<page>.md`.
- A page renders at `/handbook/<section>/<page>` and in a drawer opened from a question-mark button.
- Both the `en-GB` and the `de-AT` page must exist, with the same headings.

## 2 workflow

1. Read the component, its i18n keys, and the use case and rules behind it.
2. Pick the section (`todo`, `workspace`, `catalogue`, `procurement`, `production`, `resources`, `account`) and a kebab-case page name that describes the thing (`order-item-delivery`). Extend an existing page with an anchored section when the target belongs to it.
3. Write the English page, then the German one, with full frontmatter as shown below. `sourceRefs` must point at real files, and `order` is optional.
4. Wire the button for an element by placing `<HelpButton size="small" rounded />` (from `@/shared/help`) next to it. In a controls bar or views bar it drops `size="small"`, see [design-look.md](design-look.md). Without props it opens the page matching the route, and `slug` and `anchor` override that. It renders nothing until the page exists.
5. Wire the button for a dialog by adding a `#header` with the title and a round text `mdi mdi-help` button left of the close icon, and a `<HelpDrawer v-model:visible="..." slug="section/page" />` after the dialog. Copy the header block and its two scoped styles from `orders/components/DeliverItemDialog.vue` or `production/components/AutoPlanDialog.vue`. Pass `:context` when the page should reflect the dialog's current choice (see `useHelpContext`).
6. Put one button per container, not per field, and add its tooltip and aria keys to both locale files.
7. Update `features/handbook/views/__tests__/HandbookIndexView.spec.ts` with the page count and the alphabetical title list per section.
8. Run `npm run type-check`, `npm run lint:check`, `npm run check:i18n`, `npx vitest run src/features/handbook` and the spec of the component you wired.

```
---
title: <2 to 6 words>
summary: <one sentence, what the reader will learn>
sourceRefs:
  - backend/src/... (use cases and rule modules the page describes)
lastVerified: <ISO date>
---
```

- `HelpButton` and `HelpDrawer` show handbook pages through the provider `main.ts` installs, and `mountWithApp` installs it in specs.

## 3 writing style

- Write for an office user who knows the workshop, not the code.
- A page has 250 to 600 words, and an added section 80 to 200. A page whose content is an embedded state-machine table, such as a transitions page, is exempt from the word minimum and the heading rule, because the table carries the content.
- Write permission names in bold exactly as labelled, and say that an action needing a permission shows disabled with a tooltip when the permission is missing.
- Open with one paragraph on what the screen does, then give one `##` heading per question.
- Write field names in bold exactly as labelled.
- Give two to four short worked examples, the normal case first.
- Write plain active sentences, with no dashes, no verbless bullet fragments, no stacked parentheses, no code identifiers and no API or database talk.
- When a field is optional in the normal flow, say so in the first sentence about it.
- Describe consequences ("the line stays partially delivered and waits for the rest") rather than mechanics.
- Check every example against the validation in the code.
- The German page addresses the reader informally, keeps the same headings and examples translated by meaning, and uses the exact German labels from the de-AT locale files.
- Never mention planning notes or ticket labels.
