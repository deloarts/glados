<script setup lang="ts">
/**
 * Presentational half of a thumbnail cell: given a resolved src, renders
 * the image or a placeholder box at a fixed square size. Entity-agnostic:
 * the per-feature cells pair it with useThumbnailSrc.
 */
const props = withDefaults(
  defineProps<{
    src: string | null
    itemName?: string
    size?: string
    noImageIcon?: string
  }>(),
  {
    size: '2.5rem',
    // An empty dashed square is indistinguishable from an image that failed to
    // load. Callers with a domain-specific glyph (a cog for made items, say)
    // still override this; everyone else gets an explicit "no image".
    noImageIcon: 'mdi mdi-image-off-outline',
  },
)
</script>

<template>
  <div class="thumb-cell">
    <img v-if="props.src" :src="props.src" class="thumb-img" :alt="itemName" />
    <div v-else class="thumb-empty">
      <span v-if="noImageIcon" class="placeholder-icon" :class="noImageIcon" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.thumb-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  width: v-bind('props.size');
  height: v-bind('props.size');
}

.thumb-img {
  width: v-bind('props.size');
  height: v-bind('props.size');
  object-fit: contain;
  border-radius: var(--p-border-radius-sm);
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-hover-background);
  padding: var(--space-1);
}

.thumb-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: v-bind('props.size');
  height: v-bind('props.size');
  border-radius: var(--p-border-radius-sm);
  border: 1px dashed var(--p-content-border-color);
}

.placeholder-icon {
  font-size: calc(v-bind('props.size') * 0.6);
  color: var(--p-text-muted-color);
  opacity: 0.4;
}
</style>
