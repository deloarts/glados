<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useDebounceFn } from '@vueuse/core'

import {
  TABLE_COLUMN_KEYS,
  buildOrderMailPreviewHtml,
  SAMPLE_ORDER_MAIL_VARS,
} from '@/shared/order-mail'
import type { TableColumnLabels } from '@/shared/order-mail'
import { appLocaleForLanguage } from '@/core/i18n'
import { extractApiError } from '@/core/utils/errors'
import { useCaretInsert } from '@/shared/composables/useCaretInsert'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { previewMailTemplate } from '../api/previewMailTemplate'
import { useTemplateFileTransfer } from '@/shared/composables/useTemplateFileTransfer'
import { TemplateFileError } from '@/shared/utils/templateFile'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import {
  mailTemplateFileName,
  mailTemplateFileTarget,
  parseMailTemplateFile,
  serializeMailTemplateFile,
} from '../utils/mailTemplateFile'
import type {
  AdminMailTemplate,
  MailTemplateFamily,
  MailTemplateKind,
} from '../types/adminSettingsTypes'
import type { Schemas } from '@/core/api/generated'

/**
 * Edits every language of one admin-authored mail template kind, with the
 * split-pane layout of SupplierOrderTemplateDialog.vue.
 */
const props = defineProps<{
  kind: MailTemplateKind
  family: MailTemplateFamily
  /** From the API's spec registry, so a new kind needs no change here. */
  variables: string[]
  /**
   * One row per host language; a language without a saved row arrives
   * with an empty subject and body.
   */
  entries: AdminMailTemplate[]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

// ── Per-language drafts ──────────────────────────────────────────────────
// Hydrated on every open, so a cancelled dialog never leaks a draft into the
// next session.

interface Draft {
  subject: string
  body: string
}

const drafts = ref<Record<string, Draft>>({})
const selectedLanguage = ref('')
const languages = computed(() => props.entries.map((e) => e.language))

function currentDraft(): Draft {
  const language = selectedLanguage.value
  if (!drafts.value[language]) {
    drafts.value[language] = { subject: '', body: '' }
  }
  return drafts.value[language]!
}

const subjectModel = computed<string>({
  get: () => drafts.value[selectedLanguage.value]?.subject ?? '',
  set: (value) => {
    currentDraft().subject = value
  },
})

const bodyModel = computed<string>({
  get: () => drafts.value[selectedLanguage.value]?.body ?? '',
  set: (value) => {
    currentDraft().body = value
  },
})

// ── Preview ────────────────────────────────────────────────────────────
// Branches on family, never on kind. A supplier template is resolved
// client-side like the order composer does. A system template is a full Jinja
// document with control flow, so the server renders the draft exactly as a
// send would. Declared before the visibility watch, which calls into it
// immediately.

const previewLocale = computed(() => appLocaleForLanguage(selectedLanguage.value))

const sampleColumnLabels = computed<TableColumnLabels>(
  () =>
    Object.fromEntries(
      TABLE_COLUMN_KEYS.map((k) => [
        k,
        t(`orders.mail.columns.${k}`, {}, { locale: previewLocale.value }),
      ]),
    ) as TableColumnLabels,
)

const supplierPreviewHtml = computed(() =>
  props.family === 'supplier'
    ? buildOrderMailPreviewHtml(
        bodyModel.value,
        sampleColumnLabels.value,
        previewLocale.value,
        SAMPLE_ORDER_MAIL_VARS,
      )
    : '',
)

const systemPreviewSubject = ref('')
const systemPreviewHtml = ref('')
const previewLoading = ref(false)
const previewError = ref<string | null>(null)

async function runSystemPreview(): Promise<void> {
  // The language is not sent, but a missing one means the drafts are not
  // hydrated yet and still hold a previous kind's text.
  if (props.family !== 'system' || !selectedLanguage.value) return
  previewLoading.value = true
  previewError.value = null
  try {
    const result = await previewMailTemplate(props.kind, {
      subject: subjectModel.value,
      body: bodyModel.value,
    })
    systemPreviewSubject.value = result.subject
    systemPreviewHtml.value = result.html
  } catch (e) {
    systemPreviewHtml.value = ''
    previewError.value = extractApiError(e) ?? t('adminSettings.mail.templates.editor.previewError')
  } finally {
    previewLoading.value = false
  }
}

const debouncedSystemPreview = useDebounceFn(runSystemPreview, 400)

// Set while hydration repopulates the drafts, so it does not also queue a
// debounced preview that could outlive the dialog. Cleared on nextTick() so
// every watcher of the same update sees it.
let suppressAutoPreview = false

watch([subjectModel, bodyModel, selectedLanguage], () => {
  if (suppressAutoPreview) return
  if (visible.value && props.family === 'system') void debouncedSystemPreview()
})

// The supplier preview is already sanitized. A system body is never sanitized,
// since the allowlist would gut a full Jinja document, so it renders in a
// sandboxed iframe instead of v-html.
const previewHtml = computed(() => (props.family === 'supplier' ? supplierPreviewHtml.value : ''))

// Immediate so a caller mounting the dialog already visible still hydrates it.
watch(
  visible,
  (v) => {
    if (!v) return
    suppressAutoPreview = true
    drafts.value = Object.fromEntries(
      props.entries.map((e) => [e.language, { subject: e.subject, body: e.body }]),
    )
    selectedLanguage.value = props.entries[0]?.language ?? ''
    previewError.value = null
    if (props.family === 'system') void runSystemPreview()
    void nextTick(() => {
      suppressAutoPreview = false
    })
  },
  { immediate: true },
)

// ── Variable chips and caret insert ──

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const { insertVar, insertTableToken } = useCaretInsert(textareaRef, bodyModel)

// ── Save ──────────────────────────────────────────────────────────────

const saving = ref(false)

async function onSave(): Promise<void> {
  saving.value = true
  try {
    // Keys come from hostStore.languages, a subset of the wire vocabulary.
    const entries = Object.entries(drafts.value).map(([language, draft]) => ({
      language: language as Schemas['Language'],
      subject: draft.subject,
      body: draft.body,
    }))
    await store.saveMailTemplates(props.kind, { entries })
    appToast.success(t('adminSettings.saved'))
    visible.value = false
  } catch {
    appToast.error(t('adminSettings.errors.unknown'))
  } finally {
    saving.value = false
  }
}

function onCancel(): void {
  visible.value = false
}

// ── Template file ──
// An import fills one language's draft: the language the file name names,
// or the selected one for a file named otherwise. The export writes the
// selected language's draft.

const { importFiles, exportText } = useTemplateFileTransfer()

const importBlocked = computed(() =>
  canWrite ? '' : t('common.permissionMissing', { permission: permissionLabel(t, Permission.WRITE_SETTINGS) }),
)

function onImportFile(): void {
  void importFiles('.html,.htm', ([file]) => {
    const target = mailTemplateFileTarget(file!.name)
    if (target && target.kind !== props.kind) throw new TemplateFileError('wrongTarget', target.kind)
    const { subject, body } = parseMailTemplateFile(file!.text)
    if (target && languages.value.includes(target.language as Schemas['Language'])) {
      selectedLanguage.value = target.language
    }
    const draft = currentDraft()
    draft.subject = subject
    draft.body = body
    return []
  })
}

function onExportFile(): void {
  exportText(
    serializeMailTemplateFile({ subject: subjectModel.value, body: bodyModel.value }),
    mailTemplateFileName(props.kind, selectedLanguage.value),
    'text/html',
  )
}

const dialogTitle = computed(
  () =>
    `${t('adminSettings.mail.templates.editor.title')}: ${t(
      `adminSettings.mail.templates.${props.kind}.label`,
    )}`,
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="dialogTitle"
    :style="{ width: 'var(--dialog-width-full)', maxWidth: '1400px' }"
    :content-style="{ padding: '0' }"
  >
    <div class="template-editor">
      <div class="editor-top">
        <div class="editor-top-field">
          <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- SelectButton is a group of buttons, so the label names it through aria-labelledby -->
          <label :id="`${uid}-language`">{{ t('adminSettings.mail.templates.editor.language') }}</label>
          <SelectButton
            v-model="selectedLanguage"
            :aria-labelledby="`${uid}-language`"
            :options="languages"
            :allow-empty="false"
          />
        </div>
        <div class="editor-top-field editor-top-field--grow">
          <label :for="`${uid}-subject`">{{ t('adminSettings.mail.templates.editor.subject') }}</label>
          <InputText
            :id="`${uid}-subject`"
            v-model="subjectModel"
            fluid
            :placeholder="t('adminSettings.mail.templates.editor.subjectPlaceholder')"
          />
        </div>
      </div>

      <div class="vars-bar">
        <div class="vars-group">
          <span class="vars-label">{{ t('adminSettings.mail.templates.editor.variables') }}</span>
          <div class="vars-chips">
            <Tag
              v-for="v in props.variables"
              :key="v"
              :value="`{{ ${v} }}`"
              severity="secondary"
              class="var-chip"
              role="button"
              tabindex="0"
              v-tooltip.focus="t('adminSettings.mail.templates.editor.insertVar')"
              @click="insertVar(v)"
              @keydown.enter="insertVar(v)"
              @keydown.space.prevent="insertVar(v)"
            />
          </div>
        </div>

        <!-- The {{ table }} token is a supplier-template convention that
             system Jinja documents do not understand. -->
        <div v-if="family === 'supplier'" class="vars-group">
          <span class="vars-label">{{
            t('adminSettings.mail.templates.editor.tableColumns')
          }}</span>
          <div class="vars-chips">
            <Tag
              v-for="col in TABLE_COLUMN_KEYS"
              :key="col"
              :value="col"
              severity="info"
              class="var-chip"
              role="button"
              tabindex="0"
              v-tooltip.focus="t('adminSettings.mail.templates.editor.insertTableCol')"
              @click="insertTableToken(col)"
              @keydown.enter="insertTableToken(col)"
              @keydown.space.prevent="insertTableToken(col)"
            />
          </div>
        </div>
      </div>

      <div class="split-pane">
        <div class="pane pane-editor">
          <div class="pane-header">{{ t('adminSettings.mail.templates.editor.editor') }}</div>
          <textarea
            ref="textareaRef"
            v-model="bodyModel"
            :aria-label="t('adminSettings.mail.templates.editor.editor')"
            class="html-textarea"
            spellcheck="false"
            autocomplete="off"
          />
        </div>

        <div class="pane pane-preview">
          <div class="pane-header">{{ t('adminSettings.mail.templates.editor.preview') }}</div>
          <template v-if="family === 'system'">
            <small class="preview-note">
              {{ t('adminSettings.mail.templates.editor.previewNote') }}
            </small>
            <Message v-if="previewError" severity="error" class="preview-error">
              {{ previewError }}
            </Message>
            <iframe
              v-else
              :srcdoc="systemPreviewHtml"
              sandbox=""
              class="preview-iframe"
              :title="systemPreviewSubject || dialogTitle"
            />
          </template>
          <div v-else class="preview-content" v-html="previewHtml" />
        </div>
      </div>
    </div>

    <template #footer>
      <span v-tooltip.top="importBlocked">
        <Button
          :label="t('templateFiles.importFile')"
          icon="mdi mdi-file-import-outline"
          severity="secondary"
          text
          :disabled="!canWrite"
          data-testid="mail-template-import"
          @click="onImportFile"
        />
      </span>
      <Button
        :label="t('templateFiles.exportFile')"
        icon="mdi mdi-file-export-outline"
        severity="secondary"
        text
        class="file-action"
        :disabled="!selectedLanguage"
        data-testid="mail-template-export"
        @click="onExportFile"
      />
      <Button :label="t('common.cancel')" severity="secondary" outlined @click="onCancel" />
      <Button
        :label="t('common.save')"
        icon="mdi mdi-content-save"
        :loading="saving"
        :disabled="!canWrite"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.template-editor {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.editor-top {
  display: flex;
  align-items: flex-end;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--p-content-border-color);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.editor-top-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  &--grow {
    flex: 1 1 16rem;
  }

  label {
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--p-text-muted-color);
  }
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

.preview-note {
  padding: var(--space-2) var(--space-4) 0;
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.preview-error {
  margin: var(--space-3) var(--space-4);
}

.file-action {
  margin-right: auto;
}

.preview-iframe {
  flex: 1 1 0;
  width: 100%;
  border: none;
  background: var(--paper);
}
</style>
