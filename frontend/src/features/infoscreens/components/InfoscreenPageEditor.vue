<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import InfoscreenSlotEditor from './InfoscreenSlotEditor.vue'
import { LAYOUTS, changeLayout } from '../utils/infoscreenLayouts'

import type {
  InfoscreenLayout,
  InfoscreenPage,
  InfoscreenWidgetConfig,
} from '../types/infoscreenResponse'

/**
 * One page of a screen: its layout and a slot editor per layout position,
 * drawn in the shape the TV shows them. Moving and removing the page is
 * left to the editor, which owns the page list.
 */
const props = defineProps<{
  index: number
  count: number
  machines: ProductionMachineResponse[]
  pools: MachinePoolResponse[]
  submitted: boolean
}>()

const emit = defineEmits<{
  'move-up': []
  'move-down': []
  remove: []
}>()

const page = defineModel<InfoscreenPage>('page', { required: true })

const { t } = useI18n()

const layoutOptions = computed(() =>
  LAYOUTS.map((value) => ({ value, label: t(`infoscreens.layouts.${value}`) })),
)

const layout = computed<InfoscreenLayout>({
  get: () => page.value.layout,
  set: (value) => {
    page.value = changeLayout(page.value, value)
  },
})

function setSlot(position: number, widget: InfoscreenWidgetConfig | null): void {
  page.value = {
    ...page.value,
    slots: page.value.slots.map((current, index) => (index === position ? widget : current)),
  }
}

const idPrefix = computed(() => `infoscreen-page-${props.index}`)
</script>

<template>
  <div class="page" data-testid="infoscreen-page">
    <div class="page-head">
      <span class="page-title">{{ t('infoscreens.editor.pageTitle', { number: index + 1 }) }}</span>
      <Select
        v-model="layout"
        :input-id="`${idPrefix}-layout`"
        :options="layoutOptions"
        option-label="label"
        option-value="value"
        size="small"
        class="page-layout"
        :aria-label="t('infoscreens.editor.layout')"
        data-testid="infoscreen-page-layout"
      />
      <div class="page-actions">
        <Button
          type="button"
          icon="mdi mdi-arrow-up"
          size="small"
          text
          severity="secondary"
          :disabled="index === 0"
          :aria-label="t('infoscreens.editor.moveUp')"
          v-tooltip.top="t('infoscreens.editor.moveUp')"
          data-testid="infoscreen-page-up"
          @click="emit('move-up')"
        />
        <Button
          type="button"
          icon="mdi mdi-arrow-down"
          size="small"
          text
          severity="secondary"
          :disabled="index === count - 1"
          :aria-label="t('infoscreens.editor.moveDown')"
          v-tooltip.top="t('infoscreens.editor.moveDown')"
          data-testid="infoscreen-page-down"
          @click="emit('move-down')"
        />
        <Button
          type="button"
          icon="mdi mdi-close"
          size="small"
          text
          severity="danger"
          :disabled="count === 1"
          :aria-label="t('infoscreens.editor.removePage')"
          v-tooltip.top="t('infoscreens.editor.removePage')"
          data-testid="infoscreen-page-remove"
          @click="emit('remove')"
        />
      </div>
    </div>
    <div class="slots" :class="`slots--${page.layout}`">
      <InfoscreenSlotEditor
        v-for="(widget, position) in page.slots"
        :key="`${page.layout}-${position}`"
        :config="widget"
        :position="position + 1"
        :machines="machines"
        :pools="pools"
        :submitted="submitted"
        :id-prefix="`${idPrefix}-slot-${position}`"
        @update:config="setSlot(position, $event)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.page {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.page-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.page-title {
  font-weight: 600;
  white-space: nowrap;
}

.page-layout {
  width: 14rem;
}

.page-actions {
  display: flex;
  margin-left: auto;
}

.slots {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: minmax(0, 1fr);

  // The editor draws the positions in the order and shape the TV shows
  // them: rows stack, a 2x3 grid has two columns and a 3x2 grid three.
  &--two_columns,
  &--grid_2x2,
  &--grid_2x3 {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  &--grid_3x2 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  &--main_side {
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  }
}
</style>
