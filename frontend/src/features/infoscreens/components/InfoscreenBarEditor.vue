<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { BAR_AREAS, BAR_ITEMS, barItems } from '../utils/infoscreenLayouts'

import type {
  InfoscreenBarArea,
  InfoscreenBarItem,
  InfoscreenBarState,
} from '../types/infoscreenResponse'

/**
 * The header or the footer of a screen: whether it shows, and which items
 * sit in its left, middle and right area, each from left to right. An item
 * appears at most once in the whole bar; the custom text item brings a
 * text field of its own.
 */
const props = defineProps<{
  label: string
  idPrefix: string
  /** Shows the missing text error once the form was submitted. */
  submitted: boolean
}>()

const show = defineModel<boolean>('show', { required: true })
const bar = defineModel<InfoscreenBarState>('bar', { required: true })

const { t } = useI18n()

const used = computed(() => barItems(bar.value))

const available = computed(() =>
  BAR_ITEMS.filter((item) => !used.value.includes(item)).map((value) => ({
    value,
    label: t(`infoscreens.barItems.${value}`),
  })),
)

const hasText = computed(() => used.value.includes('text'))
const textMissing = computed(
  () => props.submitted && show.value && hasText.value && (bar.value.text?.trim() ?? '') === '',
)

function setArea(area: InfoscreenBarArea, items: InfoscreenBarItem[]): void {
  bar.value = { ...bar.value, [area]: items }
}

function add(area: InfoscreenBarArea, item: InfoscreenBarItem | null): void {
  if (item && !used.value.includes(item)) setArea(area, [...bar.value[area], item])
}

function move(area: InfoscreenBarArea, index: number, delta: number): void {
  const items = [...bar.value[area]]
  const target = index + delta
  if (target < 0 || target >= items.length) return
  const [item] = items.splice(index, 1)
  if (item) items.splice(target, 0, item)
  setArea(area, items)
}

/** Moves an item into the neighbouring area, at the end that faces it. */
function shift(area: InfoscreenBarArea, index: number, delta: -1 | 1): void {
  const targetArea = BAR_AREAS[BAR_AREAS.indexOf(area) + delta]
  const item = bar.value[area][index]
  if (!targetArea || !item) return
  const target = bar.value[targetArea]
  bar.value = {
    ...bar.value,
    [area]: bar.value[area].filter((_, position) => position !== index),
    [targetArea]: delta === 1 ? [item, ...target] : [...target, item],
  }
}

function remove(area: InfoscreenBarArea, index: number): void {
  setArea(
    area,
    bar.value[area].filter((_, position) => position !== index),
  )
}
</script>

<template>
  <div class="bar-editor" :data-testid="`${idPrefix}-editor`">
    <label class="check-row">
      <Checkbox v-model="show" binary :input-id="`${idPrefix}-show`" :data-testid="`${idPrefix}-show`" />
      {{ label }}
    </label>
    <template v-if="show">
      <div class="areas">
        <section
          v-for="(area, areaIndex) in BAR_AREAS"
          :key="area"
          class="area"
          :data-testid="`${idPrefix}-${area}`"
        >
          <h3 class="area-title">{{ t(`infoscreens.barAreas.${area}`) }}</h3>
          <ol class="items" :data-testid="`${idPrefix}-${area}-items`">
            <li v-for="(item, index) in bar[area]" :key="item" class="item">
              <span class="item-label">{{ t(`infoscreens.barItems.${item}`) }}</span>
              <span class="item-actions">
                <Button
                  type="button"
                  icon="mdi mdi-arrow-up"
                  size="small"
                  text
                  severity="secondary"
                  :disabled="index === 0"
                  :aria-label="t('infoscreens.editor.moveEarlier')"
                  v-tooltip.top="t('infoscreens.editor.moveEarlier')"
                  :data-testid="`${idPrefix}-earlier-${item}`"
                  @click="move(area, index, -1)"
                />
                <Button
                  type="button"
                  icon="mdi mdi-arrow-down"
                  size="small"
                  text
                  severity="secondary"
                  :disabled="index === bar[area].length - 1"
                  :aria-label="t('infoscreens.editor.moveLater')"
                  v-tooltip.top="t('infoscreens.editor.moveLater')"
                  :data-testid="`${idPrefix}-later-${item}`"
                  @click="move(area, index, 1)"
                />
                <Button
                  v-if="areaIndex > 0"
                  type="button"
                  icon="mdi mdi-arrow-left"
                  size="small"
                  text
                  severity="secondary"
                  :aria-label="t('infoscreens.editor.moveLeftArea')"
                  v-tooltip.top="t('infoscreens.editor.moveLeftArea')"
                  :data-testid="`${idPrefix}-left-${item}`"
                  @click="shift(area, index, -1)"
                />
                <Button
                  v-if="areaIndex < BAR_AREAS.length - 1"
                  type="button"
                  icon="mdi mdi-arrow-right"
                  size="small"
                  text
                  severity="secondary"
                  :aria-label="t('infoscreens.editor.moveRightArea')"
                  v-tooltip.top="t('infoscreens.editor.moveRightArea')"
                  :data-testid="`${idPrefix}-right-${item}`"
                  @click="shift(area, index, 1)"
                />
                <Button
                  type="button"
                  icon="mdi mdi-close"
                  size="small"
                  text
                  severity="danger"
                  :aria-label="t('infoscreens.editor.removeItem')"
                  v-tooltip.top="t('infoscreens.editor.removeItem')"
                  :data-testid="`${idPrefix}-remove-${item}`"
                  @click="remove(area, index)"
                />
              </span>
            </li>
            <li v-if="bar[area].length === 0" class="empty">{{ t('infoscreens.editor.areaEmpty') }}</li>
          </ol>
          <Select
            :model-value="null"
            :options="available"
            option-label="label"
            option-value="value"
            :placeholder="t('infoscreens.editor.addItem')"
            :disabled="available.length === 0"
            :aria-label="`${t('infoscreens.editor.addItem')}, ${t(`infoscreens.barAreas.${area}`)}`"
            size="small"
            fluid
            :data-testid="`${idPrefix}-${area}-add`"
            @update:model-value="add(area, $event)"
          />
        </section>
      </div>
      <div v-if="hasText" class="field">
        <label :for="`${idPrefix}-text`">{{ t('infoscreens.fields.barText') }} *</label>
        <InputText
          :id="`${idPrefix}-text`"
          :model-value="bar.text ?? ''"
          :maxlength="200"
          :invalid="textMissing"
          size="small"
          fluid
          :data-testid="`${idPrefix}-text`"
          @update:model-value="bar = { ...bar, text: $event ?? null }"
        />
        <small v-if="textMissing" class="field-error">{{ t('infoscreens.errors.barText') }}</small>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.bar-editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.check-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.areas {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.area {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  padding: var(--space-2);
  border: 1px dashed var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.area-title {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
}

.items {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-1);
  padding-left: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.item-label {
  font-size: var(--font-size-sm);
  min-width: 0;
  overflow-wrap: anywhere;
}

.item-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.empty {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
