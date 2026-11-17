<script setup lang="ts">
// The card grid of a catalogue item detail page, with two containers.
//
// .head-row holds item, files, processes and source in up to three equal
// auto-placed columns with auto rows, so the row height comes from the
// Item card, the only cell whose content stays in flow. The shorter cells
// stretch to that height, which gives the record-card--scroll cells the
// definite height they need. A 16rem floor covers a short Item card.
//
// .lower-grid holds orders, demands, lots, usedIn and changelog in a
// six-column grid whose minmax(16rem, 1fr) rows share the remaining height
// evenly; every cell there scrolls.
//
// processes and lots exist for made items only, source is made-only too,
// and files depends on storage. Each slot is wrapped in this component's own
// record-card div, since the slotted content is opaque and attrs fallthrough
// cannot reach its Panel. Every wrapper scrolls except item, which must stay
// measurable, and processes, which sizes to its content. The optional
// pieces show up as the --no-files, --processes, --lots and --source
// modifiers on .record-grid.
</script>

<template>
  <div
    class="record-grid"
    :class="{
      'record-grid--no-files': !$slots.files,
      'record-grid--processes': !!$slots.processes,
      'record-grid--lots': !!$slots.lots,
      'record-grid--source': !!$slots.source,
    }"
  >
    <div v-if="$slots.item || $slots.files || $slots.processes || $slots.source" class="head-row">
      <div v-if="$slots.item" class="record-card record-card--stretch area-item">
        <slot name="item" />
      </div>

      <!-- Rendered only when there is something to stack, so no blank column
           appears; without it item spans two columns. -->
      <div v-if="$slots.files || $slots.processes" class="head-middle">
        <div v-if="$slots.files" class="record-card record-card--stretch record-card--scroll area-files">
          <slot name="files" />
        </div>
        <!-- Not scrolling, so processes stays content-sized. -->
        <div v-if="$slots.processes" class="record-card record-card--stretch area-processes">
          <slot name="processes" />
        </div>
      </div>

      <div v-if="$slots.source" class="record-card record-card--stretch record-card--scroll area-source">
        <slot name="source" />
      </div>
    </div>

    <div
      v-if="$slots.orders || $slots.demands || $slots.lots || $slots.usedIn || $slots.changelog"
      class="lower-grid"
    >
      <div v-if="$slots.orders" class="record-card record-card--stretch record-card--scroll area-orders">
        <slot name="orders" />
      </div>
      <div v-if="$slots.demands" class="record-card record-card--stretch record-card--scroll area-demands">
        <slot name="demands" />
      </div>
      <div v-if="$slots.lots" class="record-card record-card--stretch record-card--scroll area-lots">
        <slot name="lots" />
      </div>
      <div v-if="$slots.usedIn" class="record-card record-card--stretch record-card--scroll area-usedin">
        <slot name="usedIn" />
      </div>
      <div v-if="$slots.changelog" class="record-card record-card--stretch record-card--scroll area-changelog">
        <slot name="changelog" />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
// Fills the page's content card and scrolls when both containers together
// are taller, since .head-row is content-sized and .lower-grid floors its
// rows.
.record-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

// ── Head row: item / files / processes / source ────────────────────────
// Auto rows, so the Item card's content sets the height, see the
// component-level comment.
.head-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
  gap: var(--space-4);
  min-height: 16rem;
  flex: 0 0 auto;

  @media (max-width: $bp-lg) {
    grid-template-columns: 1fr;
    min-height: 0;
  }
}

// source claims a third, equal column.
.record-grid--source .head-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));

  @media (max-width: $bp-lg) {
    grid-template-columns: 1fr;
  }
}

// Nothing to stack and no source: a single column.
.record-grid--no-files:not(.record-grid--processes):not(.record-grid--source) .head-row {
  grid-template-columns: minmax(0, 1fr);
}

// Nothing to stack but a source: item spans the two free columns.
.record-grid--no-files:not(.record-grid--processes).record-grid--source .area-item {
  grid-column: span 2;

  @media (max-width: $bp-lg) {
    grid-column: auto;
  }
}

// A flex column rather than a grid track, so processes sizes to its content
// while files fills the rest of the stretched row height.
.head-middle {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
  min-height: 0;
}

.head-middle > .area-files {
  flex: 1;
  min-height: 0;
}

.head-middle > .area-processes {
  flex: 0 0 auto;
}

// Stacked below 70rem, the scrolling cells would collapse to their header,
// so they get a floor. Placed after .head-middle so it wins the equal
// specificity tie at this breakpoint.
@media (max-width: $bp-lg) {
  .head-row .record-card--scroll {
    min-height: 16rem;
  }
}

// ── Lower grid: orders / demands / lots / usedIn / changelog ───────────
// Rows share the remaining height evenly; only --lots affects it.
.lower-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  grid-auto-rows: minmax(16rem, 1fr);
  gap: var(--space-4);

  grid-template-areas:
    'orders orders orders demands   demands   demands'
    'usedin usedin usedin changelog changelog changelog';

  // Single column below 70rem. minmax(16rem, auto), since the whole grid
  // scrolls and a row must be free to grow.
  @media (max-width: $bp-lg) {
    grid-template-columns: 1fr;
    grid-auto-rows: minmax(16rem, auto);
    grid-template-areas:
      'orders'
      'demands'
      'usedin'
      'changelog';
  }
}

.record-grid--lots .lower-grid {
  grid-template-areas:
    'orders orders orders demands   demands   demands'
    'lots   lots   lots   lots      lots      lots'
    'usedin usedin usedin changelog changelog changelog';

  @media (max-width: $bp-lg) {
    grid-template-areas:
      'orders'
      'demands'
      'lots'
      'usedin'
      'changelog';
  }
}

.area-orders {
  grid-area: orders;
}
.area-demands {
  grid-area: demands;
}
.area-lots {
  grid-area: lots;
}
.area-usedin {
  grid-area: usedin;
}
.area-changelog {
  grid-area: changelog;
}

// The layout of .record-card and its modifiers lives in _openvue.scss. The
// slotted Panel is one level in, so --stretch makes it the stretching flex
// column, or the scrolling content collapses to zero. Without --scroll, the
// Panel content's percentage height falls back to its content, which is how
// .head-row measures item.
</style>
