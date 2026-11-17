<!--
  Executes one catalogued SOLIDWORKS PDM Web API operation from the admin
  API console: a form generated from the operation's path/query parameters
  (`vaultName` is always skipped, the server fills it from the saved
  connection), a JSON body Textarea when the operation has one, and a
  result section with the raw response. Always mounted by
  PdmApiConsolePanel.vue (never behind v-if), the same convention
  MailTemplateEditorDialog/WebhookFormDialog use, so `watch(visible, ...)`
  below sees a real false -> true transition every time a different row is
  clicked, and reseeds the form for that operation.

  Three separate param-value records (string/number/boolean) rather than one
  loosely-typed record: each OpenVue input component's v-model expects its
  own value type, and keeping them apart lets every field stay strongly
  typed instead of casting through `unknown` at the template boundary.
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { useClipboard } from '@/core/composables/useClipboard'
import { extractApiError, extractApiErrorCode } from '@/core/utils/errors'
import type { InvokePdmOperationCommand, PdmInvokeResult, PdmOperation, PdmParam } from '../../types/adminSettingsTypes'

const { t } = useI18n()
const store = useAdminSettingsStore()
const { copyToClipboard } = useClipboard()

const props = defineProps<{
  operation: PdmOperation | null
  criticalMode: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })

const stringValues = reactive<Record<string, string>>({})
const numberValues = reactive<Record<string, number | null>>({})
const booleanValues = reactive<Record<string, boolean>>({})
const fieldErrors = reactive<Record<string, string>>({})

const bodyText = ref('')
const bodyError = ref<string | null>(null)

const executing = ref(false)
const result = ref<PdmInvokeResult | null>(null)
const invokeError = ref<{ detail: string; code: string | null } | null>(null)

/**
 * `vaultName` is always in the catalogue (the adapter needs it to build
 * the URL) but the server fills it from the saved connection, so it is
 * never rendered here. A "body"-location param documents one field of the
 * JSON body, which this dialog edits as a whole via the Textarea instead
 * of per-field.
 */
const relevantParams = computed<PdmParam[]>(() =>
  (props.operation?.params ?? []).filter(
    (p) => (p.location === 'path' || p.location === 'query') && p.name !== 'vaultName',
  ),
)

function clearRecord(record: Record<string, unknown>): void {
  for (const key of Object.keys(record)) delete record[key]
}

function seedForm(): void {
  clearRecord(stringValues)
  clearRecord(numberValues)
  clearRecord(booleanValues)
  clearRecord(fieldErrors)
  for (const p of relevantParams.value) {
    if (p.type === 'integer') numberValues[p.name] = null
    else if (p.type === 'boolean') booleanValues[p.name] = false
    else stringValues[p.name] = ''
  }
  bodyText.value = props.operation?.has_body ? (props.operation.body_example ?? '') : ''
  bodyError.value = null
  result.value = null
  invokeError.value = null
}

watch(visible, (isVisible) => {
  if (isVisible) seedForm()
})

function isEmptyValue(p: PdmParam): boolean {
  if (p.type === 'integer') return numberValues[p.name] === null || numberValues[p.name] === undefined
  if (p.type === 'boolean') return false
  return (stringValues[p.name] ?? '').trim() === ''
}

/**
 * The value sent on the wire for one param. Booleans always send their
 * current value (there is no "unset" state for a toggle); strings are
 * trimmed; empty optional strings/numbers are dropped entirely in
 * buildPayload rather than sent as "" or null.
 */
function valueFor(p: PdmParam): unknown {
  if (p.type === 'integer') return numberValues[p.name] ?? null
  if (p.type === 'boolean') return booleanValues[p.name] ?? false
  return (stringValues[p.name] ?? '').trim()
}

function validate(): boolean {
  clearRecord(fieldErrors)
  let ok = true
  for (const p of relevantParams.value) {
    if (p.required && isEmptyValue(p)) {
      fieldErrors[p.name] = t('adminSettings.solidworksPdm.pdm.operation.fieldRequiredError')
      ok = false
    }
  }
  bodyError.value = null
  if (props.operation?.has_body && bodyText.value.trim()) {
    try {
      JSON.parse(bodyText.value)
    } catch {
      bodyError.value = t('adminSettings.solidworksPdm.pdm.operation.jsonInvalid')
      ok = false
    }
  }
  return ok
}

function buildPayload(): InvokePdmOperationCommand {
  const pathParams: Record<string, unknown> = {}
  const query: Record<string, unknown> = {}
  for (const p of relevantParams.value) {
    if (!p.required && isEmptyValue(p)) continue
    const target = p.location === 'path' ? pathParams : query
    target[p.name] = valueFor(p)
  }
  const body =
    props.operation?.has_body && bodyText.value.trim() ? (JSON.parse(bodyText.value) as unknown) : null
  return { path_params: pathParams, query, body, allow_mutating: props.criticalMode }
}

async function onExecute(): Promise<void> {
  if (!props.operation) return
  if (!validate()) return

  executing.value = true
  invokeError.value = null
  try {
    result.value = await store.invokePdmOperation(props.operation.id, buildPayload())
  } catch (err: unknown) {
    result.value = null
    invokeError.value = {
      detail: extractApiError(err) ?? t('adminSettings.solidworksPdm.pdm.operation.invokeFailed'),
      code: extractApiErrorCode(err),
    }
  } finally {
    executing.value = false
  }
}

function statusSeverity(code: number): string {
  if (code >= 200 && code < 300) return 'success'
  if (code >= 400 && code < 500) return 'warn'
  return 'danger'
}

const prettyResult = computed(() => {
  if (!result.value) return ''
  if (result.value.response_json !== null && result.value.response_json !== undefined) {
    return JSON.stringify(result.value.response_json, null, 2)
  }
  return result.value.response_text ?? ''
})

async function copyResult(): Promise<void> {
  await copyToClipboard(prettyResult.value)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
    :header="operation ? `${operation.method} ${operation.path}` : ''"
  >
    <div v-if="operation" class="operation-body">
      <p v-if="operation.description" class="operation-description">{{ operation.description }}</p>

      <div v-for="p in relevantParams" :key="p.name" class="field-row">
        <label :for="`pdm-op-param-${p.name}`">
          {{ p.name }}<span v-if="p.required" class="required-mark"> *</span>
          <small v-if="p.description" class="hint">{{ p.description }}</small>
        </label>
        <div class="field-input">
          <InputNumber
            v-if="p.type === 'integer'"
            :input-id="`pdm-op-param-${p.name}`"
            v-model="numberValues[p.name]"
            :use-grouping="false"
            :invalid="!!fieldErrors[p.name]"
          />
          <ToggleSwitch
            v-else-if="p.type === 'boolean'"
            :input-id="`pdm-op-param-${p.name}`"
            v-model="booleanValues[p.name]"
          />
          <InputText
            v-else
            :id="`pdm-op-param-${p.name}`"
            v-model="stringValues[p.name]"
            :invalid="!!fieldErrors[p.name]"
          />
          <small v-if="fieldErrors[p.name]" class="field-error">{{ fieldErrors[p.name] }}</small>
        </div>
      </div>

      <div v-if="operation.has_body" class="field-row field-row--body">
        <label for="pdm-op-body">{{ t('adminSettings.solidworksPdm.pdm.operation.bodySection') }}</label>
        <div class="field-input">
          <Textarea
            id="pdm-op-body"
            v-model="bodyText"
            :rows="10"
            class="body-textarea"
            :invalid="!!bodyError"
          />
          <small v-if="bodyError" class="field-error">{{ bodyError }}</small>
        </div>
      </div>

      <Message v-if="invokeError" severity="error" :closable="false">
        <div>{{ invokeError.detail }}</div>
        <div v-if="invokeError.code" class="error-code">{{ invokeError.code }}</div>
      </Message>

      <section v-if="result" class="result-section">
        <h4>{{ t('adminSettings.solidworksPdm.pdm.operation.resultSection') }}</h4>
        <div class="result-meta">
          <Tag :severity="statusSeverity(result.status_code)" :value="String(result.status_code)" />
          <code class="result-url">{{ result.url }}</code>
          <span class="result-elapsed">{{ result.elapsed_ms }} ms</span>
          <Button
            icon="mdi mdi-content-copy"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('common.copy')"
            :aria-label="t('common.copy')"
            @click="copyResult"
          />
        </div>
        <pre class="result-body">{{ prettyResult }}</pre>
      </section>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="contrast" text @click="visible = false" />
      <Button
        :label="t('adminSettings.solidworksPdm.pdm.operation.execute')"
        icon="mdi mdi-play"
        :loading="executing"
        @click="onExecute"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.operation-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.operation-description {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.field-row {
  display: grid;
  grid-template-columns: 12rem 1fr;
  align-items: start;
  gap: var(--space-3);

  label {
    font-size: var(--font-size-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding-top: var(--space-2);
  }
}

.required-mark {
  color: var(--p-red-500);
}

.hint {
  font-size: var(--font-size-xs);
  font-weight: normal;
}

.field-input {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.field-error {
  font-size: var(--font-size-xs);
  color: var(--p-red-500);
}

.body-textarea {
  width: 100%;
  font-family: monospace;
  font-size: var(--font-size-sm);
}

.error-code {
  font-family: monospace;
  font-size: var(--font-size-xs);
  opacity: 0.8;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);

  h4 {
    margin: 0;
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--p-text-muted-color);
  }
}

.result-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.result-url {
  font-family: monospace;
  font-size: var(--font-size-xs);
  overflow-wrap: anywhere;
}

.result-elapsed {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.result-body {
  margin: 0;
  max-height: 16rem;
  overflow: auto;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--p-content-border-radius);
  background: var(--p-surface-100);
  font-family: monospace;
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
</style>
