<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { scopeIconClass } from '../utils/scopeIcons'
import type { MeetingScopeIcon } from '../types/meetingResponse'

/**
 * A card's scope as a small chip: its icon, its text or "No Scope", and a
 * lock with a dashed outline for an internal card, which the printed and
 * sent notes leave out.
 */
const props = defineProps<{
  scope: string | null
  icon: MeetingScopeIcon | null
  internal?: boolean
}>()

const { t } = useI18n()
const iconClass = computed(() => scopeIconClass(props.icon))
const title = computed(() => (props.internal ? t('meetings.card.internalHint') : undefined))
</script>

<template>
  <span class="scope-chip" :class="{ internal }" :title="title" data-testid="meeting-scope-chip">
    <i v-if="iconClass" :class="iconClass" aria-hidden="true" />
    <span :class="{ 'text-muted': !scope }">{{ scope || t('meetings.card.noScope') }}</span>
    <i v-if="internal" class="mdi mdi-lock-outline" :aria-label="t('meetings.card.internal')" role="img" />
  </span>
</template>

<style scoped lang="scss">
.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  font-size: var(--font-size-sm);
  white-space: nowrap;

  &.internal {
    border-style: dashed;
    color: var(--p-text-muted-color);
  }
}
</style>
