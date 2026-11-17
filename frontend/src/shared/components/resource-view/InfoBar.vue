<script setup lang="ts">
// The identity strip a detail view (an order, a project, ...) puts above
// its ControlsBar/ViewsBar: a compact, borderless Toolbar holding whatever
// fields identify the record, such as a number, a status tag, or a customer name.
// Bare shell, same family as ControlsBar: it owns the Toolbar chrome, the
// caller owns the content, which lands in the default slot and therefore
// compiles in the caller's own scope.
</script>

<template>
  <div class="info-bar">
    <Toolbar class="info-toolbar" :pt="{ start: { class: 'info-toolbar-start' } }">
      <template #start>
        <slot />
      </template>
    </Toolbar>
  </div>
</template>

<style scoped lang="scss">
.info-bar {
  // Height, border and right-hand padding stay identical to
  // ControlsBar/ViewsBar's chrome on purpose, which is what keeps the three
  // bars the same height. Left padding is the one deliberate divergence: the
  // identity strip reads better with more breathing room before its first
  // field than a button row needs before its first icon. Added on top of the
  // shared toolbar padding via calc(), not a hardcoded replacement, so it
  // tracks the same base the sibling bars use.
  .info-toolbar {
    padding-left: calc(var(--p-toolbar-padding, 0.5rem) + 0.6rem);
  }

  // The content row still needs a floor: the sibling bars are sized by
  // their buttons, and a bar holding only text and a Tag would come out
  // shorter. The theme's icon-only width is by definition a default
  // button's height (it is what makes icon-only buttons square), so it is
  // that floor, by token rather than by a number that goes stale when the
  // theme changes.
  :deep(.info-toolbar-start) {
    flex-wrap: wrap;
    align-items: center;
    min-height: var(--p-button-icon-only-width, 2.5rem);
  }

  // An icon in front of its text, such as the calendar before a deadline or
  // the icon inside a status tag, gets more room than the theme's default
  // gap, so the icon reads as a label of the value rather than part of it.
  // The bar sets it for every caller: a tag through the theme's own gap
  // token, and a caller's field through any flex container whose first
  // element is an icon, which outranks the caller's own scoped gap.
  --p-tag-gap: var(--space-2);

  :deep(.info-toolbar-start :has(> i.mdi:first-child)) {
    gap: var(--space-2);
  }

  // The thin vertical divider a caller puts between two fields as
  // `<span class="info-sep" />`. It lives here so every info bar spaces its
  // fields the same way, and callers carry no rule of their own for it.
  :deep(.info-sep) {
    display: inline-block;
    flex-shrink: 0;
    width: 1px;
    height: 1.1rem;
    margin: 0 var(--space-3);
    vertical-align: middle;
    background: var(--p-surface-300);
  }
}
</style>
