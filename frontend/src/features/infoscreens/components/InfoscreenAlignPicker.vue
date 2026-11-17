<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { MESSAGE_TEXT_ALIGNS, MESSAGE_VERTICAL_ALIGNS } from '../utils/infoscreenLayouts'

import type { MessageTextAlign, MessageVerticalAlign } from '../types/infoscreenResponse'

/**
 * Where a text sits in its widget, picked on a three by three grid that
 * stands for the widget: the rows are top, middle and bottom, the columns
 * left, centre and right. The picked cell is pressed.
 */
const props = defineProps<{
  textAlign: MessageTextAlign
  verticalAlign: MessageVerticalAlign
  idPrefix: string
  label: string
}>()

// One event for both directions, so a parent that replaces its whole config
// on every change never applies one half over a stale copy of the other.
const emit = defineEmits<{
  pick: [position: { text_align: MessageTextAlign; vertical_align: MessageVerticalAlign }]
}>()

const { t } = useI18n()

function cellLabel(vertical: MessageVerticalAlign, horizontal: MessageTextAlign): string {
  return t('infoscreens.alignment.cell', {
    vertical: t(`infoscreens.alignment.vertical.${vertical}`),
    horizontal: t(`infoscreens.alignment.horizontal.${horizontal}`),
  })
}

function pick(vertical: MessageVerticalAlign, horizontal: MessageTextAlign): void {
  emit('pick', { text_align: horizontal, vertical_align: vertical })
}

function isPicked(vertical: MessageVerticalAlign, horizontal: MessageTextAlign): boolean {
  return props.verticalAlign === vertical && props.textAlign === horizontal
}
</script>

<template>
  <div class="align-picker" role="group" :aria-label="props.label" :data-testid="`${idPrefix}-align`">
    <template v-for="vertical in MESSAGE_VERTICAL_ALIGNS" :key="vertical">
      <button
        v-for="horizontal in MESSAGE_TEXT_ALIGNS"
        :key="`${vertical}-${horizontal}`"
        type="button"
        class="cell"
        :class="{ 'cell--picked': isPicked(vertical, horizontal) }"
        :aria-pressed="isPicked(vertical, horizontal)"
        :aria-label="cellLabel(vertical, horizontal)"
        v-tooltip.top="cellLabel(vertical, horizontal)"
        :data-testid="`${idPrefix}-align-${vertical}-${horizontal}`"
        @click="pick(vertical, horizontal)"
      >
        <span class="dot" aria-hidden="true" />
      </button>
    </template>
  </div>
</template>

<style scoped lang="scss">
.align-picker {
  display: grid;
  grid-template-columns: repeat(3, 1.75rem);
  grid-template-rows: repeat(3, 1.25rem);
  gap: var(--space-1);
  padding: var(--space-1);
  width: max-content;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.cell {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: none;
  border-radius: var(--p-border-radius-sm);
  background: transparent;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--p-content-hover-background);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: -2px;
  }

  &:disabled {
    cursor: default;
    opacity: 0.6;
  }
}

.dot {
  width: 0.4rem;
  height: 0.4rem;
  border-radius: 50%;
  background: var(--p-text-muted-color);
}

.cell--picked {
  background: var(--p-highlight-background);

  .dot {
    width: 0.6rem;
    height: 0.6rem;
    background: var(--p-primary-color);
  }
}
</style>
