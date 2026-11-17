<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { DiffLine } from '../utils/lineDiff'

/** A line diff: kept lines plain, added lines green with a plus, removed lines red with a minus. */
defineProps<{ lines: DiffLine[] }>()

const { t } = useI18n()
const MARK = { same: ' ', added: '+', removed: '−' } as const
</script>

<template>
  <div class="line-diff" data-testid="meeting-line-diff">
    <div v-if="!lines.length" class="empty-note">{{ t('meetings.diff.empty') }}</div>
    <div
      v-for="(line, index) in lines"
      :key="index"
      class="diff-line"
      :class="line.kind"
      :data-kind="line.kind"
    >
      <span class="diff-mark" aria-hidden="true">{{ MARK[line.kind] }}</span>
      <span class="visually-hidden">{{ t(`meetings.diff.${line.kind}`) }}</span>
      <span class="diff-text">{{ line.text || ' ' }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.line-diff {
  max-height: 18rem;
  overflow: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  font-size: var(--font-size-sm);
}

.diff-line {
  display: flex;
  gap: var(--space-2);
  padding: 0 var(--space-2);
  white-space: pre-wrap;
  overflow-wrap: anywhere;

  &.added {
    background: color-mix(in srgb, var(--p-green-500) 14%, transparent);
  }

  &.removed {
    background: color-mix(in srgb, var(--p-red-500) 14%, transparent);
    text-decoration: line-through;
  }
}

.diff-mark {
  flex: 0 0 auto;
  width: 1ch;
  color: var(--p-text-muted-color);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
