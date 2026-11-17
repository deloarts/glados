<script setup lang="ts">
/**
 * The row filter of a column that is searched by several text fields, built
 * like UserDateFilter: one small field sums up what is set and opens a
 * panel with a labelled input per field. It binds the table's own filter
 * values, one string per field key, so the server side filters stay as
 * they are.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

export interface TextFilterField {
  key: string
  label: string
}

const props = defineProps<{
  /** Names the column in the accessible labels. */
  column: string
  fields: TextFilterField[]
  /** Shown while nothing is set, the table's usual "any" text. */
  placeholder?: string
}>()

const values = defineModel<Record<string, string>>({ required: true })

const { t } = useI18n()

const popover = ref<{ toggle: (event: Event) => void } | null>(null)

const summary = computed(() =>
  props.fields
    .filter((field) => values.value[field.key]?.trim())
    .map((field) => `${field.label}: ${values.value[field.key]!.trim()}`)
    .join(', '),
)

function toggle(event: Event): void {
  popover.value?.toggle(event)
}

function update(key: string, value: string | undefined): void {
  values.value = { ...values.value, [key]: value ?? '' }
}

function clear(): void {
  values.value = Object.fromEntries(props.fields.map((field) => [field.key, '']))
}
</script>

<template>
  <div class="text-fields-filter">
    <IconField>
      <InputText
        :model-value="summary"
        readonly
        :placeholder="props.placeholder ?? t('common.userDateFilter.any')"
        :title="summary || undefined"
        :aria-label="t('common.filterBy', { column })"
        aria-haspopup="dialog"
        size="small"
        fluid
        class="text-fields-filter-field"
        data-testid="text-fields-filter-field"
        @click="toggle"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
      />
      <InputIcon
        v-if="summary"
        class="mdi mdi-close text-fields-filter-clear"
        role="button"
        tabindex="0"
        :aria-label="t('common.clear')"
        data-testid="text-fields-filter-clear"
        @click.stop="clear"
        @keydown.enter.prevent="clear"
      />
    </IconField>

    <Popover ref="popover">
      <div class="text-fields-filter-panel" data-testid="text-fields-filter-panel">
        <div v-for="field in fields" :key="field.key" class="text-fields-filter-row">
          <label :for="`text-filter-${column}-${field.key}`">{{ field.label }}</label>
          <InputText
            :id="`text-filter-${column}-${field.key}`"
            :model-value="values[field.key] ?? ''"
            size="small"
            fluid
            :data-testid="`text-fields-filter-${field.key}`"
            @update:model-value="update(field.key, $event)"
          />
        </div>
      </div>
    </Popover>
  </div>
</template>

<style scoped lang="scss">
.text-fields-filter {
  min-width: 0;
}

.text-fields-filter-field {
  cursor: pointer;
  text-overflow: ellipsis;
}

.text-fields-filter-clear {
  cursor: pointer;
}

.text-fields-filter-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 16rem;
}

.text-fields-filter-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  label {
    font-size: var(--font-size-sm);
  }
}
</style>
