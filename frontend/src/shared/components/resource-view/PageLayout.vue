<script setup lang="ts">
// The app's common page layout: the one component that holds the default
// page anatomy, so every view draws the same boundaries:
//
//   ┌ menu ─────────────────────────────────────────────────────┐
//   │  #info      identity strip above the bars (detail views)  │
//   │  #controls  ControlsBar, the page's actions               │
//   │  #views     ViewsBar, sync/group/sort/filter/search       │
//   │  #menu      escape hatch for nonstandard bars             │
//   ├ data ─────────────────────────────────────────────────────┤
//   │  #panels      side panels BEFORE the content card, left   │
//   │               in a row-shaped data area (an edit panel,   │
//   │               its resize handle, ...)                     │
//   │  default      the page content, wrapped in the standard   │
//   │               content card unless `card` is disabled      │
//   │  #panels-end  side panels AFTER the card, right in a      │
//   │               row (a docs panel, a files panel, ...)      │
//   └───────────────────────────────────────────────────────────┘
//
// Horizontal router tabs are deliberately NOT part of this layout: section
// wrapper views (CatalogueView, ...) own the tab strip and mount one
// PageLayout page per tab panel.
//
// A plain `class="..."` passed on the component tag falls through to the
// .view-scope root automatically (Vue's single-root attrs inheritance), so no
// prop is needed for that. `dataClass` exists separately because .view-data is
// an inner element, which fallthrough can't reach.
withDefaults(
  defineProps<{
    /** Extra class applied to the data area, for features that need a non-default layout (e.g. a row of panels). */
    dataClass?: string
    /**
     * The default: the default slot lands in one standard content card.
     * Disable for pages whose data area is several sections/cards or fully
     * custom, since those own their card chrome themselves.
     */
    card?: boolean
    /**
     * Toolbar buttons wrap onto a new line as a whole instead of breaking
     * their labels, for detail pages with many actions.
     */
    wrapMenu?: boolean
  }>(),
  { dataClass: undefined, card: true, wrapMenu: false },
)
</script>

<template>
  <div class="view-scope">
    <div class="view-content">
      <div class="view-menu" :class="{ 'view-menu--wrap': wrapMenu }">
        <slot name="info" />
        <slot name="controls" />
        <slot name="views" />
        <slot name="menu" />
      </div>
      <div class="view-data" :class="dataClass">
        <slot name="panels" />
        <div v-if="card" class="card">
          <slot />
        </div>
        <slot v-else />
        <slot name="panels-end" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.view-scope {
  height: 100%;
}

.view-content {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  // Same rhythm as .view-menu's bar gap, so the space between the last bar
  // and the data area matches the space between the bars themselves.
  gap: var(--space-1);
}

.view-menu {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex-shrink: 0;
}

.view-data {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-top: var(--space-1);
}

.view-data > .card {
  // The global .card's height:100% does the work in the default block-flow
  // data area; this rule matters when `dataClass` turns the data area into a
  // flex row of panels, where the card must claim the width left over next
  // to fixed-width side panels instead of shrinking to its content.
  flex: 1 1 auto;
  min-width: 0;
}
</style>
