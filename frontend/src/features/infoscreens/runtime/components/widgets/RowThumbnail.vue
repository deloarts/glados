<script setup lang="ts">
import { computed, ref, watch } from 'vue'

// The item picture at the start of a widget row. The URL is signed by the
// server, so a plain image request needs no header. The box is square and
// sized in em, so it follows the row's text down into the small slots of the
// 6-slot grids, and it keeps its size with a muted placeholder when the item
// has no picture or the picture does not load, so the row never shifts.
const props = withDefaults(defineProps<{ url: string | null; size?: string }>(), {
  size: '2.4em',
})

// The backend hands out root-relative paths. In production nginx serves the
// API on the page's origin, but the dev server talks to the backend on its
// own port, so the path is prefixed the way the branding logo URLs are.
const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const src = computed(() =>
  props.url && props.url.startsWith('/') ? `${API_ROOT}${props.url}` : props.url,
)

const failed = ref(false)

watch(
  () => props.url,
  () => {
    failed.value = false
  },
)
</script>

<template>
  <span class="row-thumbnail" :style="{ '--row-thumbnail-size': size }" aria-hidden="true">
    <img
      v-if="src && !failed"
      class="row-thumbnail-image"
      :src="src"
      alt=""
      loading="lazy"
      data-testid="row-thumbnail"
      @error="failed = true"
    />
    <i
      v-else
      class="mdi mdi-image-off-outline row-thumbnail-placeholder"
      data-testid="row-thumbnail-placeholder"
    />
  </span>
</template>

<style scoped lang="scss">
.row-thumbnail {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--row-thumbnail-size);
  height: var(--row-thumbnail-size);
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-background);
}

.row-thumbnail-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.row-thumbnail-placeholder {
  font-size: calc(var(--row-thumbnail-size) * 0.5);
  line-height: 1;
  color: var(--p-text-muted-color);
}
</style>
