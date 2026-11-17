<script setup lang="ts">
/**
 * The device markers of the overview canvas, each the device's number in a
 * circle centred on its spot, and in the detailed view a small card with the
 * device's name, type and rendering. Outside the detailed view a marker shows
 * the device's name while it is highlighted. The canvas places this layer
 * over the image without scaling it and moves the markers through CSS variables, so a
 * zoom or a drag changes no marker's props and never re-renders this
 * component.
 */
export interface OverviewMarker {
  id: number
  // The device's number in the list beside the overview.
  number: number
  x: number
  y: number
  label: string
  highlighted: boolean
  // The device's kind and driving medium, shown on the card in the detailed view.
  typeLabel?: string
  imageUrl?: string | null
}

defineProps<{
  markers: OverviewMarker[]
  detailed?: boolean
}>()

const emit = defineEmits<{
  'marker-enter': [id: number]
  'marker-leave': [id: number]
}>()
</script>

<template>
  <span
    v-for="marker in markers"
    :key="marker.id"
    class="marker"
    :class="{ highlighted: marker.highlighted }"
    :style="{ '--marker-x': marker.x, '--marker-y': marker.y }"
    data-testid="device-overview-marker"
    @pointerenter="emit('marker-enter', marker.id)"
    @pointerleave="emit('marker-leave', marker.id)"
  >
    <span class="marker-number">{{ marker.number }}</span>
    <span
      v-if="detailed"
      class="marker-card"
      :class="{ highlighted: marker.highlighted }"
      data-testid="device-overview-card"
    >
      <span class="card-image">
        <img v-if="marker.imageUrl" :src="marker.imageUrl" :alt="marker.label" draggable="false" />
        <i v-else class="mdi mdi-image-outline" aria-hidden="true" />
      </span>
      <span class="card-name">{{ marker.label }}</span>
      <span v-if="marker.typeLabel" class="card-type">{{ marker.typeLabel }}</span>
    </span>
    <span v-else-if="marker.highlighted" class="marker-label">{{ marker.label }}</span>
  </span>
</template>

<style scoped lang="scss">
// The marker point is the anchor, moved onto its spot from the view the
// canvas sets on the layer: the image's offset and its drawn size. The
// numbered circle is centred on the point.
.marker {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  transform: translate(
    calc(var(--view-x) + var(--marker-x) * var(--view-width)),
    calc(var(--view-y) + var(--marker-y) * var(--view-height))
  );
  pointer-events: auto;

  // A highlighted device's marker and card are drawn above the others.
  &.highlighted {
    z-index: 10;
  }

  &.highlighted .marker-number {
    background: var(--p-red-500);
  }
}

.marker-number {
  position: absolute;
  left: -0.75rem;
  top: -0.75rem;
  width: 1.5rem;
  height: 1.5rem;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 2px solid var(--p-surface-0);
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1;
  box-shadow: var(--shadow-sm);
}

// The card sits above and right of the circle, so the circle still marks
// the exact spot.
.marker-card {
  position: absolute;
  left: 0.8rem;
  bottom: 0.8rem;
  width: 9.5rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-1);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--shadow-sm);

  &.highlighted {
    border-color: var(--p-red-500);
    z-index: 2;
  }
}

.card-image {
  height: 5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-border-radius-sm);
  background: var(--p-surface-0);
  overflow: hidden;

  img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  i {
    font-size: var(--font-size-2xl);
    color: var(--p-text-muted-color);
  }
}

.card-name {
  font-size: var(--font-size-xs);
  font-weight: 600;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.card-type {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.marker-label {
  position: absolute;
  left: 0.95rem;
  top: -0.65rem;
  white-space: nowrap;
  padding: var(--space-1) var(--space-1);
  border-radius: var(--p-border-radius-sm);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  font-size: var(--font-size-xs);
}
</style>
