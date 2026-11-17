<script setup lang="ts">
// Creates a personal access token for an AI agent from one of the two
// presets the backend serves: Read (use:mcp) or Read and Draft, which adds
// the write permissions the draft tools need. The expiry is capped at the
// agent token lifetime, which holds even when the general token cap is
// lifted. After creating, the dialog shows the token once together with
// the command that connects Claude Code to Glados.
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'
import { useGrantablePermissions } from '@/core/composables/useGrantablePermissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { todayKey } from '@/core/utils/dates'
import { extractApiError, extractApiErrorCode } from '@/core/utils/errors'
import { createTokenApi } from '@/shared/api/createTokenApi'
import { permissionLabel } from '@/shared/utils/permissionLabels'

type Preset = 'read' | 'draft'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

const visible = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{
  created: []
}>()

const { t } = useI18n()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const hostStore = useHostStore()
const { grantablePermissions } = useGrantablePermissions()
const patsApi = createTokenApi('/users/me/personal-access-tokens')

const form = reactive({
  name: '',
  preset: 'read' as Preset,
  expiresInDays: 30,
  password: '',
})
const saving = ref(false)
const error = ref<string | null>(null)
const createdSecret = ref<string | null>(null)

const maxDays = computed(() => Math.max(1, hostStore.agentTokenMaxLifetimeDays))

watch(visible, (open) => {
  if (!open) return
  createdSecret.value = null
  error.value = null
  form.name = `Agent ${todayKey()}`
  form.preset = 'read'
  form.expiresInDays = maxDays.value
  form.password = ''
})

const presetScopes = computed(() =>
  form.preset === 'draft' ? hostStore.agentDraftScopes : hostStore.agentReadScopes,
)

// A preset grants only what the user holds; the rest is named, not dropped silently.
const grantedScopes = computed(() =>
  presetScopes.value.filter((perm) => grantablePermissions.value.includes(perm)),
)
const missingScopeLabels = computed(() =>
  presetScopes.value
    .filter((perm) => !grantablePermissions.value.includes(perm))
    .map((perm) => permissionLabel(t, perm))
    .join(', '),
)

const presetOptions = computed(() => [
  { value: 'read', label: t('agents.token.presets.read'), hint: t('agents.token.presets.readHint') },
  {
    value: 'draft',
    label: t('agents.token.presets.draft'),
    hint: t('agents.token.presets.draftHint'),
  },
])

const isValid = computed(
  () => form.name.trim() !== '' && grantedScopes.value.length > 0 && form.password !== '',
)

const endpoint = computed(() => `${API_ROOT || window.location.origin}/api/v1/mcp`)

const command = computed(
  () =>
    `claude mcp add --transport http glados ${endpoint.value} --header "Authorization: Bearer ${createdSecret.value ?? ''}"`,
)

async function onSave(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const created = await patsApi.create({
      name: form.name.trim(),
      permissions: grantedScopes.value,
      expires_in_days: Math.min(form.expiresInDays, maxDays.value),
      password: form.password,
    })
    form.password = ''
    createdSecret.value = created.secret
    emit('created')
  } catch (err) {
    error.value = saveErrorMessage(err)
  } finally {
    saving.value = false
  }
}

/** The translated reason a create failed, the backend's own text otherwise. */
function saveErrorMessage(err: unknown): string {
  switch (extractApiErrorCode(err)) {
    case 'PasswordConfirmationFailedError':
      return t('agents.token.wrongPassword')
    case 'LoginLockedError':
      return t('login.errors.lockedOut')
    default:
      return extractApiError(err) ?? t('agents.token.saveFailed')
  }
}

async function onCopy(text: string): Promise<void> {
  const copied = await copyToClipboard(text, t('agents.token.copied'))
  if (!copied) appToast.error(t('agents.token.copyFailed'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="createdSecret ? t('agents.token.createdTitle') : t('agents.token.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    data-testid="agent-token-dialog"
  >
    <div v-if="createdSecret" class="created">
      <Message severity="warn" :closable="false">{{ t('agents.token.secretWarning') }}</Message>
      <div class="field">
        <label for="agent-token-secret">{{ t('agents.token.secret') }}</label>
        <div class="copy-row">
          <InputText
            id="agent-token-secret"
            :model-value="createdSecret"
            readonly
            fluid
            class="mono"
            data-testid="agent-token-secret"
          />
          <Button
            icon="mdi mdi-content-copy"
            severity="secondary"
            :aria-label="t('common.copy')"
            @click="onCopy(createdSecret)"
          />
        </div>
      </div>
      <div class="field">
        <span class="field-label">{{ t('agents.token.connect') }}</span>
        <p class="hint">{{ t('agents.token.connectHint') }}</p>
        <div class="copy-row">
          <code class="command" data-testid="agent-token-command">{{ command }}</code>
          <Button
            icon="mdi mdi-content-copy"
            severity="secondary"
            :aria-label="t('common.copy')"
            @click="onCopy(command)"
          />
        </div>
        <p class="hint">{{ t('agents.token.otherClients', { endpoint }) }}</p>
      </div>
    </div>

    <div v-else class="form">
      <div class="field">
        <label for="agent-token-name">{{ t('agents.token.name') }}</label>
        <InputText id="agent-token-name" v-model="form.name" fluid autofocus />
      </div>
      <fieldset class="dialog-section">
        <legend>{{ t('agents.token.preset') }}</legend>
        <div v-for="option in presetOptions" :key="option.value" class="preset">
          <RadioButton
            v-model="form.preset"
            :input-id="`agent-preset-${option.value}`"
            :value="option.value"
            name="agent-preset"
          />
          <label :for="`agent-preset-${option.value}`">
            {{ option.label }}
            <small class="hint">{{ option.hint }}</small>
          </label>
        </div>
        <Message v-if="missingScopeLabels" severity="warn" :closable="false">
          {{ t('agents.token.missingPermissions', { permissions: missingScopeLabels }) }}
        </Message>
      </fieldset>
      <div class="field">
        <label for="agent-token-expiry">{{ t('agents.token.expiresInDays') }}</label>
        <InputNumber
          v-model="form.expiresInDays"
          input-id="agent-token-expiry"
          :min="1"
          :max="maxDays"
          fluid
        />
        <small class="field-hint">{{ t('agents.token.expiresInDaysHint', { days: maxDays }) }}</small>
      </div>
      <div class="field">
        <label for="agent-token-password">{{ t('agents.token.password') }}</label>
        <Password
          v-model="form.password"
          input-id="agent-token-password"
          :feedback="false"
          toggle-mask
          autocomplete="current-password"
          fluid
          data-testid="agent-token-password"
        />
        <small class="field-hint">{{ t('agents.token.passwordHint') }}</small>
      </div>
    </div>

    <template #footer>
      <template v-if="createdSecret">
        <Button :label="t('common.close')" @click="visible = false" />
      </template>
      <template v-else>
        <Message v-if="error" severity="error" :closable="false" class="footer-error">
          {{ error }}
        </Message>
        <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
        <Button
          :label="t('agents.token.create')"
          icon="mdi mdi-plus"
          :loading="saving"
          :disabled="!isValid"
          data-testid="agent-token-create"
          @click="onSave"
        />
      </template>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.form,
.created {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.preset {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);

  label {
    display: flex;
    flex-direction: column;
  }
}

.copy-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.mono,
.command {
  font-family: monospace;
}

.command {
  flex: 1;
  min-width: 0;
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  font-size: var(--font-size-sm);
  word-break: break-all;
  user-select: all;
}

.hint {
  margin: 0;
}

.footer-error {
  margin-right: auto;
}
</style>
