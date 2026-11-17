<script setup lang="ts">
import { computed } from 'vue'

// The text beside an order's picture: the lot number, the part number and
// the article name, each on its own line, and no times. A value the order
// does not have leaves its line out; an order without any of them shows its
// id, so the card is never blank.
const props = withDefaults(
  defineProps<{
    lotNumber: string | null
    partNumber: string | null
    itemName: string | null
    fallback?: string | number | null
    size?: 'large' | 'normal'
  }>(),
  { fallback: null, size: 'normal' },
)

const lines = computed(() => {
  const set = [props.lotNumber, props.partNumber, props.itemName].filter(
    (value): value is string => !!value,
  )
  if (set.length === 0 && props.fallback !== null) return [String(props.fallback)]
  return set
})
</script>

<template>
  <span class="order-card-text" :class="`order-card-text--${size}`" data-testid="order-card-text">
    <span v-for="(line, index) in lines" :key="index" class="order-card-line">{{ line }}</span>
  </span>
</template>

<style scoped lang="scss">
.order-card-text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.order-card-line {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}

// The first line is the lot number, the one people look for.
.order-card-line:first-child {
  font-weight: 700;
}

.order-card-line:not(:first-child) {
  font-size: 0.8em;
  color: var(--p-text-muted-color);
}

.order-card-text--large .order-card-line:first-child {
  font-size: 1.3em;
}
</style>
