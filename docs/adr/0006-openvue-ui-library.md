# 0006 OpenVue as the UI component library

- Status: accepted
- Date: 2026-10-05

## context

The frontend was built on PrimeVue 4.5.5, which was archived upstream and would receive no further fixes. Around 550 files use its components, props, slots, pass-through options, `p-` classes and `--p-` CSS variables, so moving to a different library would have touched every screen and changed the look of the app.

## decision

Use OpenVue 1, the MIT-licensed community fork of PrimeVue 4.5.5, with its Aura theme. The switch was made with the official migration codemod as a package rename that keeps component names, APIs, `p-` classes and CSS variables. Styling stays in scoped SCSS on top of the OpenVue theme variables; no utility CSS framework is added, and components never write their own dark mode media queries, because the theme switches through `.p-dark`.

## consequences

Users saw no change, and existing PrimeVue knowledge still applies. Glados now depends on a young fork, so its upgrades deserve a careful read. Tests that select on `.p-*` classes break when OpenVue changes its markup, which is why new specs use roles, labels or `data-testid`. The frontend rules are in [CONTRIBUTING.md section 4](../CONTRIBUTING.md#4-frontend-conventions).
