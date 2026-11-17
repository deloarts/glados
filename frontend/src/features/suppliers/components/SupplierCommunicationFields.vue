<script setup lang="ts">
// One mail block of the supplier form: address, language and template.
// Rendered once for ordering and once for quote requests.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ISO6391 from 'iso-639-1'

import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import SupplierOrderTemplateDialog from './SupplierOrderTemplateDialog.vue'

// Built once at module load, this list is static.
const languageOptions = ISO6391.getLanguages(ISO6391.getAllCodes())
  .sort((a, b) => a.name.localeCompare(b.name))
  .map((l) => ({ label: `${l.name} (${l.nativeName})`, value: l.code }))

interface Props {
  /** Prefixes this block's field ids: 's-order' or 's-request'. */
  idPrefix: string
  emailLabel: string
  languageLabel: string
  templateLabel: string
  /**
   * The preview language. The request block falls back to the order
   * language, so the caller resolves it.
   */
  templateLanguage: string | null
}

defineProps<Props>()

const email = defineModel<string>('email', { required: true })
const language = defineModel<string | null>('language', { required: true })
const template = defineModel<string>('template', { required: true })

const { t } = useI18n()
const showTemplateEditor = ref(false)
</script>

<template>
  <div class="field">
    <label :for="`${idPrefix}-email`">{{ emailLabel }}</label>
    <InputText :id="`${idPrefix}-email`" v-model="email" type="email" fluid autocomplete="off" />
  </div>

  <div class="field">
    <label :id="`${idPrefix}-language-label`" :for="`${idPrefix}-language`">{{ languageLabel }}</label>
    <Select
      :id="`${idPrefix}-language`"
      :aria-labelledby="`${idPrefix}-language-label`"
      v-model="language"
      :options="languageOptions"
      option-label="label"
      option-value="value"
      show-clear
      filter
      fluid
    />
  </div>

  <div class="field field-wide">
    <span class="field-caption">{{ templateLabel }}</span>
    <div class="template-field">
      <div v-if="template" class="template-preview">{{ template }}</div>
      <div v-else class="template-empty">{{ getEmptyPlaceholder() }}</div>
      <Button
        :label="t('resources.suppliers.fields.editTemplate')"
        icon="mdi mdi-pencil"
        severity="secondary"
        outlined
        size="small"
        type="button"
        @click="showTemplateEditor = true"
      />
    </div>
  </div>

  <SupplierOrderTemplateDialog
    v-model:visible="showTemplateEditor"
    :model-value="template"
    :language="templateLanguage"
    @update:model-value="template = $event"
  />
</template>

<style scoped lang="scss">
.field {
  label,
  .field-caption {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}

.template-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.template-preview {
  font-family: monospace;
  font-size: var(--font-size-xs);
  line-height: 1.4;
  padding: var(--space-2) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius);
  background: var(--p-content-background);
  max-height: 5.5rem;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--p-text-muted-color);
}

.template-empty {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
