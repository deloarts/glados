<script setup lang="ts">
// The card every widget sits in: a title with an optional count, and a body
// that clips instead of scrolling, since nobody scrolls a wall display. The
// card is a size container, so the widgets inside scale their type with the
// slot they are given (cqmin) rather than with the whole screen.
withDefaults(defineProps<{ title?: string | null; count?: number | null }>(), {
  title: null,
  count: null,
})
</script>

<template>
  <article class="widget-frame">
    <header v-if="title" class="widget-frame-header">
      <h2 class="widget-frame-title">{{ title }}</h2>
      <span v-if="count !== null" class="widget-frame-count" data-testid="widget-count">
        {{ count }}
      </span>
    </header>
    <div class="widget-frame-body">
      <slot />
    </div>
  </article>
</template>

<style scoped lang="scss">
.widget-frame {
  container-type: size;
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
}

.widget-frame-header {
  flex: 0 0 auto;
  display: flex;
  align-items: baseline;
  gap: 0.6em;
  padding: 0.5em 0.8em 0.3em;
  // The vmin size is the fallback where container units are missing.
  // stylelint-disable-next-line declaration-block-no-duplicate-properties
  font-size: clamp(1rem, 2.6vmin, 3.5rem);
  font-size: clamp(0.85rem, 6cqmin, 3.5rem);
}

.widget-frame-title {
  margin: 0;
  font-size: 1em;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.widget-frame-count {
  font-weight: 700;
  color: var(--p-text-muted-color);
}

.widget-frame-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  padding: 0 0.8em 0.6em;
  // The vmin size is the fallback where container units are missing.
  // stylelint-disable-next-line declaration-block-no-duplicate-properties
  font-size: clamp(0.9rem, 2.1vmin, 2.8rem);
  font-size: clamp(0.75rem, 4.6cqmin, 2.8rem);
  // A list longer than the slot fades out at the bottom instead of being
  // cut through the middle of a line. A mask reads only the alpha, so the
  // black here is opacity, not a colour.
  // stylelint-disable-next-line declaration-property-value-disallowed-list
  mask-image: linear-gradient(to bottom, #000 calc(100% - 1.5em), transparent);
}
</style>
