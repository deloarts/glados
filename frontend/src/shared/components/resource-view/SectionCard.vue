<!--
  A card with its title inside, for pages whose data area is several cards
  (`PageLayout :card="false"`). The header matches the Overview tab's
  `OverviewSection`, so every titled card in the app reads the same. With
  `flush` the body runs close to the card's edges, for a `DataTable`; with
  `fill` the card shares the height of a flex column or grid row with its
  siblings and its body hands the rest down, so a table inside can scroll
  with `scroll-height="flex"`. A card whose height is capped scrolls its
  body under a header that stays in place.
-->
<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    hint?: string
    /** An `mdi` icon class shown before the title. */
    icon?: string
    flush?: boolean
    fill?: boolean
  }>(),
  { hint: undefined, icon: undefined, flush: false, fill: false },
)
</script>

<template>
  <section class="card section-card" :class="{ flush, fill }">
    <header class="section-card-header">
      <div class="section-card-heading">
        <i v-if="icon" :class="['mdi', icon, 'section-card-icon']" aria-hidden="true" />
        <h2 class="section-card-title">{{ title }}</h2>
        <slot name="title-end" />
      </div>
      <p v-if="hint" class="section-card-hint">{{ hint }}</p>
    </header>
    <div class="section-card-body">
      <slot />
    </div>
  </section>
</template>

<style scoped lang="scss">
.section-card {
  height: auto;
  padding: 0;

  &.fill {
    flex: 1 1 0;
    min-height: 0;
  }
}

.section-card-header {
  flex-shrink: 0;
  padding: var(--space-4) var(--space-4) 0;
}

.section-card-heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.section-card-icon {
  font-size: var(--font-size-md);
  color: var(--p-text-muted-color);
}

.section-card-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.section-card-hint {
  margin: -0.35rem 0 var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.section-card-body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  overflow-y: auto;
  padding: 0 var(--space-4) var(--space-4);

  .flush & {
    padding: 0 var(--space-2) var(--space-2);
  }
}
</style>
