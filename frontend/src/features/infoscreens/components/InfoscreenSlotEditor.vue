<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MachinePoolResponse, ProductionMachineResponse } from '@/features/production-machines'
import InfoscreenWidgetFields from './InfoscreenWidgetFields.vue'
import { WIDGET_TYPES, defaultWidget } from '../utils/infoscreenLayouts'

import type { InfoscreenWidgetConfig, InfoscreenWidgetType } from '../types/infoscreenResponse'

/**
 * One position of a page: which widget it shows, or nothing, its optional
 * title and the widget's own settings. Picking another type starts that
 * widget from its defaults and keeps the title.
 */
defineProps<{
  position: number
  machines: ProductionMachineResponse[]
  pools: MachinePoolResponse[]
  submitted: boolean
  idPrefix: string
}>()

const config = defineModel<InfoscreenWidgetConfig | null>('config', { required: true })

const { t } = useI18n()

const EMPTY = 'empty'

const typeOptions = computed(() => [
  { value: EMPTY, label: t('infoscreens.widgets.empty') },
  ...WIDGET_TYPES.map((value) => ({ value, label: t(`infoscreens.widgets.${value}`) })),
])

const selectedType = computed<string>({
  get: () => config.value?.type ?? EMPTY,
  set: (value) => {
    if (value === EMPTY) {
      config.value = null
      return
    }
    const title = config.value?.title ?? null
    config.value = { ...defaultWidget(value as InfoscreenWidgetType), title }
  },
})

function onTitle(value: string | undefined): void {
  if (!config.value) return
  config.value = { ...config.value, title: value ?? null }
}
</script>

<template>
  <div class="slot" :class="{ 'slot--empty': !config }" data-testid="infoscreen-slot">
    <div class="slot-head">
      <span class="slot-position">{{ t('infoscreens.editor.position', { position }) }}</span>
      <Select
        v-model="selectedType"
        :input-id="`${idPrefix}-type`"
        :options="typeOptions"
        option-label="label"
        option-value="value"
        size="small"
        class="slot-type"
        :aria-label="t('infoscreens.editor.widgetType')"
        data-testid="infoscreen-slot-type"
      />
    </div>
    <template v-if="config">
      <div class="field">
        <label :for="`${idPrefix}-title`">{{ t('infoscreens.widgetFields.title') }}</label>
        <InputText
          :id="`${idPrefix}-title`"
          :model-value="config.title ?? ''"
          :placeholder="t('infoscreens.widgetFields.titlePlaceholder')"
          :maxlength="100"
          size="small"
          fluid
          @update:model-value="onTitle"
        />
      </div>
      <InfoscreenWidgetFields
        :widget="config"
        :machines="machines"
        :pools="pools"
        :submitted="submitted"
        :id-prefix="idPrefix"
        @update:widget="config = $event"
      />
    </template>
  </div>
</template>

<style scoped lang="scss">
.slot {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-background);

  &--empty {
    border-style: dashed;
  }
}

.slot-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.slot-position {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.slot-type {
  flex: 1;
  min-width: 0;
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}
</style>
