<!--
  One titled block of a detail page's Overview tab. Fields go in as a
  `<dl>` of `<dt>` label and `<dd>` value pairs, which this component lays
  out as a two-column list; a `<dd class="empty">` greys out a missing
  value. With `flush` the content runs to the block's edges, for a list of
  `OverviewRelatedRow`s. The `title-end` slot puts a control of the block,
  such as Link Contact, at the end of its title row.
-->
<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    hint?: string
    /** Width of the label column. */
    labelWidth?: string
    flush?: boolean
  }>(),
  { hint: undefined, labelWidth: '9rem', flush: false },
)
</script>

<template>
  <section class="overview-section" :class="{ flush }" :style="{ '--overview-label-width': labelWidth }">
    <div v-if="$slots['title-end']" class="section-title-row">
      <h2 class="section-title">{{ title }}</h2>
      <slot name="title-end" />
    </div>
    <h2 v-else class="section-title">{{ title }}</h2>
    <p v-if="hint" class="section-hint">{{ hint }}</p>
    <slot />
  </section>
</template>

<style scoped lang="scss">
.overview-section {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-4) var(--space-4) var(--space-2);

  &.flush {
    padding: var(--space-4) var(--space-2) var(--space-2);

    .section-title,
    .section-title-row {
      padding: 0 var(--space-3);
    }

    .section-title-row .section-title {
      padding: 0;
    }
  }
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin: 0 0 var(--space-2);

  .section-title {
    margin: 0;
  }
}

.section-title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-md);
  font-weight: 600;
}

.section-hint {
  margin: -0.35rem 0 var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

:slotted(dl) {
  margin: 0;
  display: grid;
  grid-template-columns: var(--overview-label-width) minmax(0, 1fr);
}

:slotted(dt),
:slotted(dd) {
  margin: 0;
  padding: var(--space-3) 0;
  border-top: 1px solid var(--p-content-border-color);
}

:slotted(dt) {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

:slotted(dd) {
  font-weight: 500;
  display: flex;
  align-items: center;
  min-width: 0;
  overflow-wrap: anywhere;
}

:slotted(dd.empty) {
  color: var(--p-text-muted-color);
  font-weight: 400;
}
</style>
