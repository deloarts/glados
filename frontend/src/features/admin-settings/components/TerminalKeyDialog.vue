<script setup lang="ts">
import { computed, reactive, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'
import { useHostStore } from '@/core/host/stores/hostStore'
import { DAY_MS, addDays, endOfDayInDisplayZone, todayStart } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import { createTerminalKey } from '../api/apiKeysApi'

/**
 * Creates a terminal key. Unlike a normal API key it has no permission
 * picker: its service account holds exactly the permission to connect
 * terminals. After the create call the dialog shows the raw key once, as
 * the line that goes into the terminal's .env file.
 */
const emit = defineEmits<{ created: [] }>()
const visible = defineModel<boolean>('visible', { required: true })

const { t } = useI18n()
const hostStore = useHostStore()
const { copyToClipboard } = useClipboard()
const secretInputRef = useTemplateRef<{ $el: HTMLInputElement }>('secretInput')

const form = reactive({ name: '', expiresOn: null as Date | null })
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const createdSecret = ref<string | null>(null)
const explainVisible = ref(false)

const nameError = computed(() =>
  submitted.value && form.name.trim() === '' ? t('settings.apiKeys.terminalKey.nameRequired') : null,
)

// While the security settings cap token lifetimes, a key needs an expiry
// within the cap; a cap of 0 lifts both.
const capped = computed(() => hostStore.tokenMaxLifetimeDays > 0)
const expiryError = computed(() =>
  submitted.value && capped.value && form.expiresOn === null
    ? t('settings.apiKeys.terminalKey.expiryRequired')
    : null,
)

// Days on the tenant's calendar, like the expiry they lead to. The last day
// is the one whose end still lies within the lifetime cap, as the backend
// refuses a key living the full cap or longer.
const minDate = computed(() => addDays(todayStart(), 1))
const maxDate = computed(() =>
  capped.value
    ? addDays(todayStart(new Date(Date.now() + hostStore.tokenMaxLifetimeDays * DAY_MS)), -1)
    : undefined,
)

const envLine = computed(() =>
  createdSecret.value ? `IDENTITY__API_KEY=${createdSecret.value}` : '',
)

watch(visible, (open) => {
  if (!open) return
  form.name = ''
  form.expiresOn = null
  submitted.value = false
  errorMessage.value = null
  createdSecret.value = null
})

/** The key lasts through the whole chosen day in the tenant's timezone. */
function endOfDay(day: Date): string {
  return endOfDayInDisplayZone(day).toISOString()
}

async function onSave(): Promise<void> {
  submitted.value = true
  if (nameError.value || expiryError.value) return
  saving.value = true
  errorMessage.value = null
  try {
    const created = await createTerminalKey({
      name: form.name.trim(),
      expires_at: form.expiresOn ? endOfDay(form.expiresOn) : null,
    })
    createdSecret.value = created.secret
    emit('created')
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('settings.apiKeys.terminalKey.saveFailed')
  } finally {
    saving.value = false
  }
}

async function onCopy(): Promise<void> {
  if (!envLine.value) return
  const copied = await copyToClipboard(envLine.value, t('settings.apiKeys.terminalKey.copied'))
  if (!copied) secretInputRef.value?.$el.select()
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">
          {{
            createdSecret
              ? t('settings.apiKeys.terminalKey.createdTitle')
              : t('settings.apiKeys.terminalKey.title')
          }}
        </span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('settings.apiKeys.terminalKey.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('settings.apiKeys.terminalKey.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div v-if="createdSecret" class="dialog-body" data-testid="terminal-key-created">
      <Message severity="warn" :closable="false">
        {{ t('settings.apiKeys.terminalKey.secretWarning') }}
      </Message>
      <div class="secret-row">
        <InputText
          ref="secretInput"
          :model-value="envLine"
          readonly
          fluid
          class="secret-input"
          :aria-label="t('settings.apiKeys.terminalKey.createdTitle')"
          data-testid="terminal-key-env-line"
        />
        <Button
          icon="mdi mdi-content-copy"
          severity="secondary"
          :aria-label="t('common.copy')"
          data-testid="terminal-key-copy"
          @click="onCopy"
        />
      </div>
      <p class="hint">{{ t('settings.apiKeys.terminalKey.secretWhere') }}</p>
    </div>

    <form v-else class="dialog-body" @submit.prevent="onSave">
      <p class="hint">{{ t('settings.apiKeys.terminalKey.intro') }}</p>
      <div class="field">
        <label for="terminal-key-name">{{ t('settings.apiKeys.terminalKey.fields.name') }} *</label>
        <InputText
          id="terminal-key-name"
          v-model="form.name"
          :placeholder="t('settings.apiKeys.terminalKey.fields.namePlaceholder')"
          :invalid="!!nameError"
          :maxlength="100"
          autocomplete="off"
          fluid
          autofocus
          data-testid="terminal-key-name"
        />
        <small v-if="nameError" class="field-error">{{ nameError }}</small>
      </div>
      <div class="field">
        <label for="terminal-key-expires">
          {{ t('settings.apiKeys.terminalKey.fields.expiresAt') }}<span v-if="capped"> *</span>
        </label>
        <DatePicker
          v-model="form.expiresOn"
          input-id="terminal-key-expires"
          :min-date="minDate"
          :max-date="maxDate"
          :invalid="!!expiryError"
          show-icon
          show-button-bar
          fluid
        />
        <small v-if="expiryError" class="field-error">{{ expiryError }}</small>
        <small class="hint">
          {{
            capped
              ? t('settings.apiKeys.terminalKey.fields.expiresAtCappedHint', {
                  days: hostStore.tokenMaxLifetimeDays,
                })
              : t('settings.apiKeys.terminalKey.fields.expiresAtHint')
          }}
        </small>
      </div>
    </form>

    <template #footer>
      <template v-if="createdSecret">
        <Button :label="t('common.close')" @click="visible = false" />
      </template>
      <template v-else>
        <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
          {{ errorMessage }}
        </Message>
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          text
          :disabled="saving"
          @click="visible = false"
        />
        <Button
          :label="t('settings.apiKeys.terminalKey.button')"
          icon="mdi mdi-key-plus"
          :loading="saving"
          data-testid="terminal-key-save"
          @click="onSave"
        />
      </template>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/terminals" anchor="terminal-key" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.hint {
  margin: 0;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}

.secret-row {
  display: flex;
  gap: var(--space-2);
}

.secret-input {
  font-family: monospace;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
