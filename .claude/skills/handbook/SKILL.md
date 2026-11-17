---
name: handbook
description: Add or extend an in-app handbook page and wire the question-mark button that opens it. Load when a page, panel, dialog or field needs an explanation for office users, when someone asks "document this in the handbook", or when a new feature ships without help text.
---

# Glados handbook

How handbook pages work, where they go, how to wire the button, the frontmatter and the style
rules are documented in `docs/reference/handbook-pages.md`. Read it in full before starting; this
skill only adds the interaction around it.

Arguments given: `$ARGUMENTS`

- Empty: ask for the target (component or route) and the questions the page must answer, then
  stop.
- Otherwise read it as `<target>: <what to explain>`. The target is a component name, a file
  path, a route, or a UI element in words. The rest lists the questions the page must answer.
  If either half is missing, infer it from the code and say so in the draft.

## Workflow

1. **Locate the target** and read it, its i18n keys, the backend use case and domain rules
   behind it, and any existing handbook page for the same section. Note what the user can do
   there (fields, buttons, validation, permissions, side effects).
2. **Decide slug and placement** following `docs/reference/handbook-pages.md`.
3. **Write the summary draft and stop.** Before writing any file, reply with:
   - slug, section, page title (both languages),
   - where the button goes and which pattern (element button or dialog header),
   - an outline: the headings and one sentence per heading saying what it will cover,
   - the worked examples you intend to include, one line each,
   - anything you could not verify in the code.
   Wait for the user to confirm or adjust. Do not create files before that.
4. **Write the pages**, English first, German second, and **wire the button**, as described in
   the doc.
5. **Update the index spec** and say in the report that you did.
6. **Run the gates** listed in the doc. Never run prettier.
7. **Report**: slug, files written, where the button sits, gate results verbatim.

## Checklist before reporting

- Both locale files exist and have the same headings.
- Every field named in bold matches the current UI label in both locales.
- Every example was checked against the validation in the code.
- Tooltip and aria label keys added in both locales, `npm run check:i18n` green.
- Index spec updated, handbook specs green.
- No dashes in the prose, no code identifiers in the text.
