<!--
  The controls bar every resource view puts at the top of its menu area.
  Wraps OpenVue's Toolbar with the same slots. It does not render the
  explain button itself, since only the caller knows which doc explains its
  view. The `#handbook` slot lets a caller drop its own `<HelpButton>` from
  `@/shared/help` in at the far right of the bar, after `#end`. This
  component does not know or care what goes there.

  On a phone the `#start` and `#center` actions move into one Actions menu
  that drops down below the bar, while `#end` and `#handbook` keep their place.
  The menu is shown and hidden rather than mounted on demand, so a dialog a
  caller keeps inside its actions stays open after the menu closes.
-->
<script setup lang="ts">
import { computed, ref, useSlots, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { onClickOutside, useEventListener } from '@vueuse/core'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

const { t } = useI18n()
const slots = useSlots()
const { isPhone } = usePhoneLayout()

const hasActions = computed(() => !!slots.start || !!slots.center)
const menuOpen = ref(false)
const phoneBar = useTemplateRef<HTMLElement>('phoneBar')
const phoneMenu = useTemplateRef<HTMLElement>('phoneMenu')

onClickOutside(phoneBar, () => {
  menuOpen.value = false
})

// A tap on an action runs it and closes the menu, as a menu item does. The
// listener sits on the menu itself because the clicks bubble up from the
// action buttons, which bring their own keyboard handling.
useEventListener(phoneMenu, 'click', (event: MouseEvent) => {
  if (event.target instanceof Element && event.target.closest('button, a')) {
    menuOpen.value = false
  }
})
</script>

<template>
  <div v-if="isPhone" ref="phoneBar" class="controls-bar controls-bar--phone">
    <Toolbar class="controls-bar-phone-toolbar">
      <template #start>
        <Button
          v-if="hasActions"
          :label="t('common.actions')"
          :icon="menuOpen ? 'mdi mdi-chevron-up' : 'mdi mdi-chevron-down'"
          icon-pos="right"
          severity="contrast"
          :text="!menuOpen"
          :aria-expanded="menuOpen"
          data-testid="controls-bar-actions"
          @click="menuOpen = !menuOpen"
        />
      </template>
      <template #end>
        <slot name="end" />
        <slot name="handbook" />
      </template>
    </Toolbar>
    <div
      v-show="menuOpen"
      ref="phoneMenu"
      class="controls-bar-menu phone-actions-menu"
      data-testid="controls-bar-menu"
    >
      <slot name="start" />
      <slot name="center" />
    </div>
  </div>

  <Toolbar
    v-else
    class="controls-bar"
    :pt="{
      start: { class: 'controls-bar-start', 'data-testid': 'controls-bar-start' },
      center: { class: 'controls-bar-side' },
      end: { class: 'controls-bar-side', 'data-testid': 'controls-bar-end' },
    }"
  >
    <template v-if="$slots.start" #start>
      <slot name="start" />
    </template>

    <template v-if="$slots.center" #center>
      <slot name="center" />
    </template>

    <template #end>
      <slot name="end" />
      <slot name="handbook" />
    </template>
  </Toolbar>
</template>

<style scoped lang="scss">
// The toolbar wraps its groups as whole blocks, so a start group wider
// than the bar pushed the end group (share and handbook buttons) onto a row
// of its own. The start group wraps its own buttons instead and the end
// group keeps its place at the right.
.controls-bar {
  flex-wrap: nowrap;

  :deep(.controls-bar-start) {
    flex: 1 1 auto;
    min-width: 0;
    flex-wrap: wrap;
  }

  :deep(.controls-bar-side) {
    flex: 0 0 auto;
  }
}

.controls-bar--phone {
  position: relative;
}

// Drops down over the page below the bar, one action per row.
.controls-bar-menu {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-1);
  padding: var(--space-2);
  margin-top: var(--space-1);

  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  box-shadow: var(--shadow-md);
}
</style>
