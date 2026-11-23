<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { TABLE_COLUMN_KEYS, buildOrderMailPreviewHtml, SAMPLE_ORDER_MAIL_VARS } from '@/shared/order-mail'
import type { TableColumnLabels } from '@/shared/order-mail'
import { appLocaleForLanguage } from '@/core/i18n'
import { useCaretInsert } from '@/shared/composables/useCaretInsert'
import { HelpButton } from '@/shared/help'

const props = defineProps<{
  modelValue: string
  /** ISO 639-1 language the template is written in; the preview table renders in this language. */
  language?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const localTemplate = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

watch(visible, (v) => {
  if (v) localTemplate.value = props.modelValue
})

// ── Variable chips ────────────────────────────────────────────────────────────

const SIMPLE_VARS = [
  'order_number',
  'supplier_order_numbers',
  'supplier',
  'note',
  'ordered_date',
  'expected_delivery',
  'total',
  'total_price',
  'user_full_name',
  'user_email',
] as const

const { insertVar, insertTableToken } = useCaretInsert(textareaRef, localTemplate)

const previewLocale = computed(() => appLocaleForLanguage(props.language))

const sampleColumnLabels = computed<TableColumnLabels>(
  () =>
    Object.fromEntries(
      TABLE_COLUMN_KEYS.map((k) => [
        k,
        t(`orders.mail.columns.${k}`, {}, { locale: previewLocale.value }),
      ]),
    ) as TableColumnLabels,
)

// The template is user-controlled and shown to others, so the preview
// builder escapes the sample values and sanitizes the markup before v-html.
const previewHtml = computed(() =>
  buildOrderMailPreviewHtml(
    localTemplate.value,
    sampleColumnLabels.value,
    previewLocale.value,
    SAMPLE_ORDER_MAIL_VARS,
  ),
)

function onSave(): void {
  emit('update:modelValue', localTemplate.value)
  visible.value = false
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-full)', maxWidth: '1400px' }"
    :content-style="{ padding: '0' }"
  >
    <template #header>
      <div class="template-editor-header">
        <span class="p-dialog-title">{{ t('resources.suppliers.templateEditor.title') }}</span>
        <span class="template-editor-help">
          <HelpButton slug="resources/suppliers" anchor="mails" icon="mdi mdi-help" rounded />
        </span>
      </div>
    </template>
    <div class="template-editor">
      <!-- Variable chips -->
      <div class="vars-bar">
        <!-- Simple vars -->
        <div class="vars-group">
          <span class="vars-label">{{ t('resources.suppliers.templateEditor.variables') }}</span>
          <div class="vars-chips">
            <Tag
              v-for="v in SIMPLE_VARS"
              :key="v"
              :value="`{{ ${v} }}`"
              severity="secondary"
              class="var-chip"
              role="button"
              tabindex="0"
              v-tooltip.focus="t('resources.suppliers.templateEditor.insertVar')"
              @click="insertVar(v)"
              @keydown.enter="insertVar(v)"
              @keydown.space.prevent="insertVar(v)"
            />
          </div>
        </div>

        <!-- Table column vars -->
        <div class="vars-group">
          <span class="vars-label">{{ t('resources.suppliers.templateEditor.tableColumns') }}</span>
          <div class="vars-chips">
            <Tag
              v-for="col in TABLE_COLUMN_KEYS"
              :key="col"
              :value="col"
              severity="info"
              class="var-chip"
              role="button"
              tabindex="0"
              v-tooltip.focus="t('resources.suppliers.templateEditor.insertTableCol')"
              @click="insertTableToken(col)"
              @keydown.enter="insertTableToken(col)"
              @keydown.space.prevent="insertTableToken(col)"
            />
          </div>
        </div>
      </div>

      <!-- Split pane -->
      <div class="split-pane">
        <div class="pane pane-editor">
          <div class="pane-header">{{ t('resources.suppliers.templateEditor.editor') }}</div>
          <textarea
            ref="textareaRef"
            v-model="localTemplate"
            :aria-label="t('resources.suppliers.templateEditor.editor')"
            class="html-textarea"
            spellcheck="false"
            autocomplete="off"
          />
        </div>

        <div class="pane pane-preview">
          <div class="pane-header">{{ t('resources.suppliers.templateEditor.preview') }}</div>
          <div class="preview-content" v-html="previewHtml" />
        </div>
      </div>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined @click="onCancel" />
      <Button :label="t('common.save')" icon="mdi mdi-content-save" @click="onSave" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.template-editor-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.template-editor-help :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.template-editor {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.vars-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.vars-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.vars-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
  white-space: nowrap;
  min-width: 6rem;
}

.vars-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.var-chip {
  cursor: pointer;
  font-family: monospace;
  font-size: var(--font-size-xs);
  user-select: none;

  &:hover {
    opacity: 0.75;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.split-pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  flex: 1 1 0;
  min-height: 0;
}

.pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;

  &:first-child {
    border-right: 1px solid var(--p-content-border-color);
  }
}

.pane-header {
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
}

.html-textarea {
  flex: 1 1 0;
  width: 100%;
  resize: none;
  border: none;
  outline: none;
  padding: var(--space-3) var(--space-4);
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-sm);
  line-height: 1.5;
  background: var(--p-content-background);
  color: var(--p-text-color);
}

.preview-content {
  flex: 1 1 0;
  overflow: auto;
  padding: var(--space-4);
  font-family: sans-serif;
  font-size: var(--font-size-md);
  line-height: 1.5;
}
</style>
