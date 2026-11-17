<script setup lang="ts">
defineProps<{
  table?: boolean
}>()

// A tab without controls (Host) has no bar to keep the card apart from, so
// the card sits as far below the tab strip as it sits from the sidebar.
const slots = defineSlots<{ controls?: () => unknown; default?: () => unknown }>()
</script>

<template>
  <div class="tab-layout">
    <div v-if="slots.controls" class="tab-controls">
      <slot name="controls" />
    </div>
    <div
      :class="[
        'tab-data',
        table ? 'tab-data--table' : 'tab-data--form',
        { 'tab-data--flush': !slots.controls },
      ]"
    >
      <div :class="['card', { 'card--compact': table }]">
        <!-- The card itself stays pinned to the pane; only this body scrolls,
             so a long form never pushes the card's bottom edge off-screen. -->
        <div class="card-body">
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tab-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-controls {
  flex-shrink: 0;
}

.tab-data {
  flex: 1;
  min-height: 0;
  padding-top: var(--space-2);
  // Never scrolls itself: the card fills it (global .card is height: 100%
  // and a flex column) and .card-body below is the one scroll container,
  // for forms and tables alike.
  overflow: hidden;
}

.card {
  // Padding lives on .card-body so a form's scrollbar hugs the card border
  // instead of floating 1rem inside it.
  padding: 0;

  &--compact {
    font-size: var(--font-size-sm);
  }
}

.card-body {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
}

.tab-data--flush {
  padding-top: 0;
}

// A form taller than the pane (General, with its Locales section)
// scrolls inside the card, keeping the card's own edges where they are.
.tab-data--form .card-body {
  overflow-y: auto;
}

// Tables (scrollHeight="flex") size themselves to this flex column and
// scroll their own rows, so the body must not become a second scroller.
.tab-data--table .card-body {
  overflow: hidden;
}
</style>
