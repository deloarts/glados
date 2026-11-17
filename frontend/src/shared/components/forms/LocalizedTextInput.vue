<script setup lang="ts">
import { computed, useId } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
import { localeEndonym } from '@/core/i18n/localeMessages'
import type { LocalizedText } from '@/shared/utils/localizedText'

/**
 * One text input per UI language the instance offers, for a label that is
 * maintained in every language at once. The input of the default language
 * is marked required when `required` is set; the backend enforces the same.
 */
const props = defineProps<{
  label: string
  required?: boolean
  disabled?: boolean
  maxlength?: number
  /** Inputs side by side, each labelled on its border with the label and language, for list rows. */
  compact?: boolean
  /** A growing text area per language instead of a single line, for descriptions. */
  multiline?: boolean
}>()

const model = defineModel<LocalizedText>({ required: true })

const host = useHostStore()
const groupId = useId()

const languages = computed(() => {
  const list = host.languages.length ? [...host.languages] : [host.defaultLanguage]
  // The default language first, since it is the one that must be filled.
  return list.sort((a, b) => Number(b === host.defaultLanguage) - Number(a === host.defaultLanguage))
})

function isRequired(language: string): boolean {
  return Boolean(props.required) && language === host.defaultLanguage
}

function update(language: string, value: string | undefined): void {
  model.value = { ...model.value, [language]: value ?? '' }
}
</script>

<template>
  <fieldset
    class="localized-text-input"
    :class="{ compact }"
    :aria-labelledby="`${groupId}-legend`"
  >
    <legend :id="`${groupId}-legend`" :class="{ 'sr-only': compact }">{{ label }}</legend>
    <template v-if="compact">
      <div v-for="language in languages" :key="language" class="language-row">
        <FloatLabel variant="on">
          <InputText
            :id="`${groupId}-${language}`"
            :model-value="model[language] ?? ''"
            :disabled="disabled"
            :maxlength="maxlength"
            :aria-required="isRequired(language) ? 'true' : undefined"
            :data-testid="`localized-text-${language}`"
            size="small"
            fluid
            @update:model-value="update(language, $event)"
          />
          <label :for="`${groupId}-${language}`">
            {{ label }} ({{ localeEndonym(language) }})<span v-if="isRequired(language)" aria-hidden="true"> *</span>
          </label>
        </FloatLabel>
      </div>
    </template>
    <template v-else>
      <div v-for="language in languages" :key="language" class="language-row">
        <label :for="`${groupId}-${language}`" class="language-label">
          {{ localeEndonym(language) }}<span v-if="isRequired(language)" aria-hidden="true"> *</span>
        </label>
        <Textarea
          v-if="multiline"
          :id="`${groupId}-${language}`"
          :model-value="model[language] ?? ''"
          :disabled="disabled"
          :maxlength="maxlength"
          :aria-required="isRequired(language) ? 'true' : undefined"
          :data-testid="`localized-text-${language}`"
          rows="2"
          auto-resize
          fluid
          @update:model-value="update(language, $event)"
        />
        <InputText
          v-else
          :id="`${groupId}-${language}`"
          :model-value="model[language] ?? ''"
          :disabled="disabled"
          :maxlength="maxlength"
          :aria-required="isRequired(language) ? 'true' : undefined"
          :data-testid="`localized-text-${language}`"
          fluid
          @update:model-value="update(language, $event)"
        />
      </div>
    </template>
  </fieldset>
</template>

<style scoped lang="scss">
.localized-text-input {
  border: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  legend {
    padding: 0;
    margin-bottom: var(--space-1);
  }
}

.language-row {
  display: grid;
  grid-template-columns: 6rem 1fr;
  align-items: center;
  gap: var(--space-2);
}

.language-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.compact {
  flex-direction: row;
  gap: var(--space-1);

  .language-row {
    display: block;
    flex: 1;
    min-width: 0;
  }

  // The label on the border stays on one line and is cut short when the input is narrow.
  :deep(.p-floatlabel label) {
    max-width: calc(100% - 1rem);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
