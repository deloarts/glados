<script setup lang="ts">
/**
 * The label-colour + font-colour pair of every "labeled entity" `FormDialog`:
 * a native colour picker beside a hex text input for each of the two colours,
 * plus a preview tag rendered in them. Renders as three `.field`/`.field-wide`
 * grid cells directly, with no wrapping element, so it drops straight into a
 * caller's `.form-fields` CSS grid.
 *
 * The contrast badge (APCA lightness contrast, see core/utils/contrast) and
 * the "make it readable" fix button are opt-in via `showContrastWarning` and
 * default off, so a dialog shows them only when it asks for them.
 */
import { computed } from 'vue'

import { MIN_TEXT_CONTRAST, readableTextColor, textContrast } from '@/core/utils/contrast'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'

interface Props {
  color: string
  fontColor: string
  colorId: string
  fontColorId: string
  colorLabel: string
  fontColorLabel: string
  previewLabel: string
  /** Already resolved by the caller, e.g. `form.name || t('...placeholder')`. */
  previewText: string
  showContrastWarning?: boolean
  contrastWarningText?: string
  contrastFixLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  showContrastWarning: false,
  contrastWarningText: '',
  contrastFixLabel: '',
})

const emit = defineEmits<{
  'update:color': [value: string]
  'update:fontColor': [value: string]
}>()

const colorModel = computed({
  get: () => props.color,
  set: (value: string) => emit('update:color', value),
})

const fontColorModel = computed({
  get: () => props.fontColor,
  set: (value: string) => emit('update:fontColor', value),
})

// Null while either field holds a half-typed hex code (or when the caller
// hasn't opted in), which keeps the warning from flickering as someone
// types into the text input beside the picker.
const contrast = computed(() =>
  props.showContrastWarning ? textContrast(props.fontColor, props.color) : null,
)
const contrastTooLow = computed(() => contrast.value !== null && contrast.value < MIN_TEXT_CONTRAST)

const { formatNumber } = useLocaleFormat()
const contrastLabel = computed(() =>
  contrast.value === null
    ? ''
    : formatNumber(contrast.value, { maximumFractionDigits: 0 }),
)

function applyReadableFontColor(): void {
  emit('update:fontColor', readableTextColor(props.color))
}
</script>

<template>
  <div class="field">
    <label :for="colorId">{{ colorLabel }}</label>
    <div class="color-row">
      <input :id="colorId" v-model="colorModel" type="color" class="color-input" />
      <InputText v-model="colorModel" size="small" style="flex: 1" />
    </div>
  </div>

  <div class="field">
    <label :for="fontColorId">{{ fontColorLabel }}</label>
    <div class="color-row">
      <input :id="fontColorId" v-model="fontColorModel" type="color" class="color-input" />
      <InputText v-model="fontColorModel" size="small" style="flex: 1" />
    </div>
  </div>

  <div class="field field-wide">
    <span class="field-caption">{{ previewLabel }}</span>
    <div class="label-preview">
      <span class="preview-tag" :style="{ background: color, color: fontColor }">
        {{ previewText }}
      </span>
      <span v-if="contrast !== null" class="contrast-ratio">Lc {{ contrastLabel }}</span>
    </div>

    <!-- These colours show up on every tag rendered with them across the
         app, so an unreadable pair is worth catching before it is saved. It
         stays a warning, not a block: the colours are the user's call. -->
    <Message
      v-if="showContrastWarning && contrastTooLow"
      severity="warn"
      :pt="{ text: { class: 'contrast-warning-text' } }"
      :closable="false"
      class="contrast-warning"
    >
      {{ contrastWarningText }}
      <Button
        type="button"
        :label="contrastFixLabel"
        size="small"
        variant="text"
        @click="applyReadableFontColor"
      />
    </Message>
  </div>
</template>

<style scoped lang="scss">
.color-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.color-input {
  width: 2.5rem;
  height: 2.1rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  cursor: pointer;
  padding: var(--space-1);
  flex-shrink: 0;
}

.label-preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  min-height: 2.5rem;
}

.contrast-ratio {
  margin-left: auto;
  font-size: var(--font-size-xs);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.contrast-warning {
  margin-top: var(--space-2);

  :deep(.contrast-warning-text) {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
}

.preview-tag {
  display: inline-block;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-border-radius-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
}
</style>
