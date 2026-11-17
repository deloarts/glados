<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'
import { getMeetingScopeSuggestions } from '../api/meetingsApi'
import { SCOPE_ICON_VALUES, scopeIconClass } from '../utils/scopeIcons'
import type { MeetingScopeIcon } from '../types/meetingResponse'

/**
 * Sets the scope of a card: free text with the scopes the owner's cards
 * already use as suggestions, most used first, a hint when the text nearly
 * repeats an existing scope, and an optional icon from the fixed twelve.
 * The scope links to nothing in Glados.
 */
const props = defineProps<{
  scope: string | null
  icon: MeetingScopeIcon | null
  owner: { project_id: number } | { product_id: number }
}>()

const emit = defineEmits<{ apply: [value: { scope: string | null; icon: MeetingScopeIcon | null }] }>()

const { t } = useI18n()
const uid = useId()

const popover = ref<{ toggle: (event: Event) => void; show: (event: Event) => void; hide: () => void } | null>(null)
const text = ref('')
const selectedIcon = ref<MeetingScopeIcon | null>(null)
const suggestions = ref<{ scope: string; icon: MeetingScopeIcon | null; count: number }[]>([])
const nearDuplicate = ref<string | null>(null)
let timer: ReturnType<typeof setTimeout> | null = null
let epoch = 0

async function loadSuggestions(): Promise<void> {
  const current = ++epoch
  const query = text.value.trim()
  try {
    const result = await getMeetingScopeSuggestions({ ...props.owner, q: query || null, limit: 8 })
    if (current !== epoch) return
    suggestions.value = result.suggestions.filter((entry) => entry.scope !== query)
    nearDuplicate.value = result.near_duplicate && result.near_duplicate !== query ? result.near_duplicate : null
  } catch {
    if (current === epoch) {
      suggestions.value = []
      nearDuplicate.value = null
    }
  }
}

watch(text, () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => void loadSuggestions(), SEARCH_DEBOUNCE_MS)
})

function open(event: Event): void {
  text.value = props.scope ?? ''
  selectedIcon.value = props.icon
  nearDuplicate.value = null
  void loadSuggestions()
  popover.value?.show(event)
}

function pick(scope: string, scopeIcon: MeetingScopeIcon | null): void {
  text.value = scope
  if (!selectedIcon.value && scopeIcon) selectedIcon.value = scopeIcon
}

function toggleIcon(value: MeetingScopeIcon): void {
  selectedIcon.value = selectedIcon.value === value ? null : value
}

function apply(): void {
  emit('apply', { scope: text.value.trim() || null, icon: selectedIcon.value })
  popover.value?.hide()
}

const iconOptions = computed(() =>
  SCOPE_ICON_VALUES.map((value) => ({ value, icon: scopeIconClass(value) ?? '', label: t(`meetings.scopeIcons.${value}`) })),
)

defineExpose({ open })
</script>

<template>
  <Popover ref="popover" data-testid="meeting-scope-popover">
    <div class="scope-form">
      <label :for="`${uid}-scope`" class="field-caption">{{ t('meetings.scope.label') }}</label>
      <InputText
        :id="`${uid}-scope`"
        v-model="text"
        maxlength="80"
        :placeholder="t('meetings.scope.placeholder')"
        autocomplete="off"
        fluid
        data-testid="meeting-scope-input"
        @keydown.enter.prevent="apply"
      />
      <Message v-if="nearDuplicate" severity="info" size="small" data-testid="meeting-scope-near-duplicate">
        {{ t('meetings.scope.nearDuplicate', { scope: nearDuplicate }) }}
        <Button
          :label="t('meetings.scope.useExisting')"
          size="small"
          text
          @click="pick(nearDuplicate, null)"
        />
      </Message>
      <div v-if="suggestions.length" class="suggestions" role="list" :aria-label="t('meetings.scope.suggestions')">
        <Button
          v-for="entry in suggestions"
          :key="entry.scope"
          :icon="scopeIconClass(entry.icon) ?? undefined"
          :label="entry.scope"
          :badge="String(entry.count)"
          size="small"
          severity="secondary"
          outlined
          role="listitem"
          data-testid="meeting-scope-suggestion"
          @click="pick(entry.scope, entry.icon)"
        />
      </div>

      <span class="field-caption">{{ t('meetings.scope.icon') }}</span>
      <div class="icon-grid" role="group" :aria-label="t('meetings.scope.icon')">
        <Button
          v-for="option in iconOptions"
          :key="option.value"
          :icon="option.icon"
          size="small"
          severity="secondary"
          :text="selectedIcon !== option.value"
          :aria-pressed="selectedIcon === option.value"
          :aria-label="option.label"
          v-tooltip.top="option.label"
          :data-testid="`meeting-scope-icon-${option.value}`"
          @click="toggleIcon(option.value)"
        />
      </div>

      <div class="scope-actions">
        <Button
          :label="t('meetings.scope.noIcon')"
          severity="secondary"
          text
          size="small"
          data-testid="meeting-scope-no-icon"
          @click="selectedIcon = null"
        />
        <Button
          :label="t('meetings.scope.apply')"
          icon="mdi mdi-check"
          size="small"
          data-testid="meeting-scope-apply"
          @click="apply"
        />
      </div>
    </div>
  </Popover>
</template>

<style scoped lang="scss">
.scope-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 22rem;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(6, auto);
  justify-content: start;
  gap: var(--space-1);
}

.scope-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-1);
}
</style>
