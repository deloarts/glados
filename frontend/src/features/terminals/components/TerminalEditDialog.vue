<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { updateTerminal } from '../api/terminalsApi'
import { LOCATION_MAX_LENGTH } from '../utils/terminalStatus'

import type { TerminalResponse, TerminalScreenOption } from '../types/terminalResponse'

/**
 * Edits a terminal's name and location, or changes the screen it shows,
 * since the two row actions answer different questions. Clearing the
 * location removes it; clearing the screen unassigns it, and the TV then
 * says it waits for a screen.
 */
const props = defineProps<{
  terminal: TerminalResponse | null
  field: 'name' | 'screen'
  screens: TerminalScreenOption[]
}>()

const emit = defineEmits<{ saved: [terminal: TerminalResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const name = ref('')
const location = ref('')
const infoscreenId = ref<number | null>(null)
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)

watch(visible, (open) => {
  if (!open) return
  name.value = props.terminal?.name ?? ''
  location.value = props.terminal?.location ?? ''
  infoscreenId.value = props.terminal?.infoscreen_id ?? null
  submitted.value = false
  errorMessage.value = null
})

const title = computed(() =>
  props.field === 'name' ? t('terminals.edit.renameTitle') : t('terminals.edit.screenTitle'),
)

const nameError = computed(() =>
  submitted.value && props.field === 'name' && name.value.trim() === ''
    ? t('terminals.approve.errors.nameRequired')
    : null,
)

async function onSave(): Promise<void> {
  submitted.value = true
  if (nameError.value || !props.terminal) return
  saving.value = true
  errorMessage.value = null
  try {
    const body =
      props.field === 'name'
        ? { name: name.value.trim(), location: location.value.trim() || null }
        : { infoscreen_id: infoscreenId.value }
    const saved = await updateTerminal(props.terminal.id, body)
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="title" :style="{ width: 'var(--dialog-width-sm)' }">
    <form class="dialog-body" @submit.prevent="onSave">
      <template v-if="field === 'name'">
        <div class="field">
          <label for="terminal-edit-name">{{ t('terminals.approve.fields.name') }} *</label>
          <InputText
            id="terminal-edit-name"
            v-model="name"
            :maxlength="100"
            :invalid="!!nameError"
            autocomplete="off"
            fluid
            autofocus
            data-testid="terminal-edit-name"
          />
          <small v-if="nameError" class="field-error">{{ nameError }}</small>
        </div>
        <div class="field">
          <label for="terminal-edit-location">{{ t('terminals.approve.fields.location') }}</label>
          <InputText
            id="terminal-edit-location"
            v-model="location"
            :placeholder="t('terminals.approve.fields.locationPlaceholder')"
            :maxlength="LOCATION_MAX_LENGTH"
            autocomplete="off"
            fluid
            data-testid="terminal-edit-location"
          />
          <small class="hint">{{ t('terminals.approve.fields.locationHint') }}</small>
        </div>
      </template>
      <div v-else class="field">
        <label id="terminal-edit-screen-label" for="terminal-edit-screen">{{ t('terminals.approve.fields.screen') }}</label>
        <Select
          v-model="infoscreenId"
          input-id="terminal-edit-screen"
          aria-labelledby="terminal-edit-screen-label"
          :options="screens"
          option-label="name"
          option-value="id"
          :placeholder="t('terminals.approve.fields.screenPlaceholder')"
          show-clear
          filter
          fluid
          data-testid="terminal-edit-screen"
        />
        <small class="hint">{{ t('terminals.edit.screenHint') }}</small>
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
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :loading="saving"
        data-testid="terminal-edit-save"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
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

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
