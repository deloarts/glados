<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import { approveTerminal } from '../api/terminalsApi'
import {
  LOCATION_MAX_LENGTH,
  PAIRING_CODE_LENGTH,
  isPairingCodeFormat,
  normalisePairingCode,
} from '../utils/terminalStatus'

import type {
  TerminalMode,
  TerminalResponse,
  TerminalScreenOption,
} from '../types/terminalResponse'

/**
 * Approves a pending terminal. The person types the code the TV shows,
 * which proves they stand in front of that display; the format is checked
 * here and the match by the server, which answers 422 on a wrong or expired
 * code. Only the infoscreen mode exists so far, the kiosk mode is listed
 * but cannot be picked.
 */
const props = defineProps<{
  terminal: TerminalResponse | null
  screens: TerminalScreenOption[]
}>()

const emit = defineEmits<{ approved: [terminal: TerminalResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const form = reactive({
  code: '',
  name: '',
  location: '',
  mode: 'infoscreen' as TerminalMode,
  infoscreenId: null as number | null,
})
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)

watch(visible, (open) => {
  if (!open) return
  form.code = ''
  form.name = ''
  form.location = ''
  form.mode = 'infoscreen'
  form.infoscreenId = null
  submitted.value = false
  errorMessage.value = null
})

const normalisedCode = computed(() => normalisePairingCode(form.code))

const codeError = computed(() => {
  if (!submitted.value) return null
  if (normalisedCode.value === '') return t('terminals.approve.errors.codeRequired')
  if (!isPairingCodeFormat(normalisedCode.value)) return t('terminals.approve.errors.codeFormat')
  return null
})

const nameError = computed(() =>
  submitted.value && form.name.trim() === '' ? t('terminals.approve.errors.nameRequired') : null,
)

const modeOptions = computed(() => [
  { value: 'infoscreen', label: t('terminals.modes.infoscreen'), disabled: false },
  {
    value: 'kiosk',
    label: `${t('terminals.modes.kiosk')} (${t('terminals.approve.modeComingLater')})`,
    disabled: true,
  },
])

async function onApprove(): Promise<void> {
  submitted.value = true
  if (codeError.value || nameError.value || !props.terminal) return
  saving.value = true
  errorMessage.value = null
  try {
    const location = form.location.trim()
    const approved = await approveTerminal(props.terminal.id, {
      pairing_code: normalisedCode.value,
      name: form.name.trim(),
      mode: form.mode,
      infoscreen_id: form.infoscreenId,
      // Left out when empty, which the server reads as no location.
      ...(location ? { location } : {}),
    })
    visible.value = false
    emit('approved', approved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.approve.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-sm)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('terminals.approve.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('terminals.approve.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('terminals.approve.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <form class="dialog-body" @submit.prevent="onApprove">
      <p class="hint">{{ t('terminals.approve.intro') }}</p>
      <div class="field">
        <label for="terminal-approve-code">{{ t('terminals.approve.fields.code') }} *</label>
        <InputText
          id="terminal-approve-code"
          v-model="form.code"
          class="code-input"
          :maxlength="PAIRING_CODE_LENGTH + 2"
          :invalid="!!codeError"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          fluid
          autofocus
          data-testid="terminal-approve-code"
        />
        <small class="hint">{{ t('terminals.approve.fields.codeHint') }}</small>
        <small v-if="codeError" class="field-error" data-testid="terminal-approve-code-error">
          {{ codeError }}
        </small>
      </div>
      <div class="field">
        <label for="terminal-approve-name">{{ t('terminals.approve.fields.name') }} *</label>
        <InputText
          id="terminal-approve-name"
          v-model="form.name"
          :placeholder="t('terminals.approve.fields.namePlaceholder')"
          :maxlength="100"
          :invalid="!!nameError"
          autocomplete="off"
          fluid
          data-testid="terminal-approve-name"
        />
        <small v-if="nameError" class="field-error">{{ nameError }}</small>
      </div>
      <div class="field">
        <label for="terminal-approve-location">{{ t('terminals.approve.fields.location') }}</label>
        <InputText
          id="terminal-approve-location"
          v-model="form.location"
          :placeholder="t('terminals.approve.fields.locationPlaceholder')"
          :maxlength="LOCATION_MAX_LENGTH"
          autocomplete="off"
          fluid
          data-testid="terminal-approve-location"
        />
        <small class="hint">{{ t('terminals.approve.fields.locationHint') }}</small>
      </div>
      <div class="field">
        <label id="terminal-approve-mode-label" for="terminal-approve-mode">{{ t('terminals.approve.fields.mode') }}</label>
        <Select
          v-model="form.mode"
          input-id="terminal-approve-mode"
          aria-labelledby="terminal-approve-mode-label"
          :options="modeOptions"
          option-label="label"
          option-value="value"
          option-disabled="disabled"
          fluid
          data-testid="terminal-approve-mode"
        />
      </div>
      <div class="field">
        <label id="terminal-approve-screen-label" for="terminal-approve-screen">{{ t('terminals.approve.fields.screen') }}</label>
        <Select
          v-model="form.infoscreenId"
          input-id="terminal-approve-screen"
          aria-labelledby="terminal-approve-screen-label"
          :options="screens"
          option-label="name"
          option-value="id"
          :placeholder="t('terminals.approve.fields.screenPlaceholder')"
          show-clear
          filter
          fluid
          data-testid="terminal-approve-screen"
        />
        <small class="hint">{{ t('terminals.approve.fields.screenHint') }}</small>
      </div>
    </form>

    <template #footer>
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
        :label="t('terminals.actions.approve')"
        icon="mdi mdi-check"
        :loading="saving"
        data-testid="terminal-approve-submit"
        @click="onApprove"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/terminals" anchor="approve" />
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

.code-input {
  font-family: monospace;
  font-size: var(--font-size-lg);
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.hint {
  margin: 0;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
