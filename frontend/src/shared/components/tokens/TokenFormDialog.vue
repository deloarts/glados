<script setup lang="ts">
import { computed, reactive, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'

import { useGrantablePermissions } from '@/core/composables/useGrantablePermissions'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { useHostStore } from '@/core/host/stores/hostStore'
import { DAY_MS, endOfDayInDisplayZone, todayKey, todayStart } from '@/core/utils/dates'
import { extractApiErrorCode } from '@/core/utils/errors'
import type { TokenStoreInstance } from '@/shared/stores/createTokenStore'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const hostStore = useHostStore()
const secretInputRef = useTemplateRef<{ $el: HTMLInputElement }>('secretInput')

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  store: TokenStoreInstance
  i18nPrefix: string
  // Opens the form pre-filled for the SolidWorks add-in shortcut: a dated
  // name, an expiry through the end of the current year, and the
  // backend-served addin_scopes intersected with what this user may grant.
  // Still the same dialog, still fully editable afterwards.
  addin?: boolean
  // The same shortcut for the PDM vault add-in's PAT, differing only in
  // which backend-served scope set and name prefix it pre-fills.
  pdmAddin?: boolean
}>()

const { grantablePermissions } = useGrantablePermissions()

// Which add-in shortcut, if either, this dialog was opened for. The two
// presets differ only in the scope set and the name they pre-fill.
const addinPreset = computed<'solidworks' | 'pdm' | null>(() =>
  props.pdmAddin ? 'pdm' : props.addin ? 'solidworks' : null,
)
const presetScopes = computed(() =>
  addinPreset.value === 'pdm' ? hostStore.pdmAddinScopes : hostStore.addinScopes,
)

// The add-in scopes this user is actually allowed to grant, versus the ones
// they are not (rendered as an inline notice rather than silently dropped).
const addinGrantablePermissions = computed(() =>
  presetScopes.value.filter((perm) => grantablePermissions.value.includes(perm)),
)
const addinMissingPermissions = computed(() =>
  presetScopes.value.filter((perm) => !grantablePermissions.value.includes(perm)),
)

// The backend's own ceiling on expires_in_days, used when the security
// settings set no lifetime cap.
const WIRE_MAX_DAYS = 36500

// A cap above 0 means every new token needs an expiry within it, so the
// "never expires" switch is shown disabled with the reason in its tooltip.
const capped = computed(() => hostStore.tokenMaxLifetimeDays > 0)
const maxDays = computed(() => (capped.value ? hostStore.tokenMaxLifetimeDays : WIRE_MAX_DAYS))

// Number of whole days from now through the end of 31 December in the
// tenant's timezone, rounded up so the resulting expiry (now + N days) does
// not land before the year is out. Clamped to the configured lifetime cap.
function addinExpiresInDays(): number {
  const now = new Date()
  const endOfYear = endOfDayInDisplayZone(new Date(todayStart(now).getFullYear(), 11, 31))
  const days = Math.max(1, Math.ceil((endOfYear.getTime() - now.getTime()) / DAY_MS))
  return Math.min(days, maxDays.value)
}

const form = reactive({
  name: '',
  permissions: [] as string[],
  neverExpires: false,
  expiresInDays: 30,
  password: '',
})

const saving = ref(false)

// After a successful create the dialog switches to the show-once secret view.
const createdSecret = ref<string | null>(null)

watch(visible, (open) => {
  if (!open) return
  createdSecret.value = null
  form.password = ''
  if (addinPreset.value) {
    const prefix = addinPreset.value === 'pdm' ? 'PDM Addin' : 'SW Addin'
    form.name = `${prefix} ${todayKey()}`
    form.permissions = [...addinGrantablePermissions.value]
    form.neverExpires = false
    form.expiresInDays = addinExpiresInDays()
  } else {
    form.name = ''
    form.permissions = []
    form.neverExpires = false
    form.expiresInDays = 30
  }
})

const isValid = computed(
  () => form.name.trim() !== '' && (!props.store.requiresPassword || form.password !== ''),
)

function tt(key: string, params?: Record<string, unknown>): string {
  return t(`${props.i18nPrefix}.${key}`, params ?? {})
}

async function onSave(): Promise<void> {
  saving.value = true
  try {
    const created = await props.store.create({
      name: form.name.trim(),
      permissions: form.permissions,
      expires_in_days: form.neverExpires && !capped.value ? null : form.expiresInDays,
      ...(props.store.requiresPassword ? { password: form.password } : {}),
    })
    form.password = ''
    createdSecret.value = created.secret
  } catch (err) {
    appToast.error(saveErrorMessage(err))
  } finally {
    saving.value = false
  }
}

/** The translated reason a create failed, matched on the error code. */
function saveErrorMessage(err: unknown): string {
  const days = hostStore.tokenMaxLifetimeDays
  switch (extractApiErrorCode(err)) {
    case 'TokenExpiryRequiredError':
      return tt('expiryRequired', { days })
    case 'TokenLifetimeExceededError':
      return tt('lifetimeExceeded', { days })
    case 'PasswordConfirmationFailedError':
      return tt('wrongPassword')
    case 'LoginLockedError':
      return t('login.errors.lockedOut')
    default:
      return tt('saveFailed')
  }
}

const addinMissingPermissionLabels = computed(() =>
  addinMissingPermissions.value.map((perm) => permissionLabel(t, perm)).join(', '),
)

async function onCopySecret(): Promise<void> {
  if (!createdSecret.value) return
  const copied = await copyToClipboard(createdSecret.value, tt('copied'))
  if (!copied) secretInputRef.value?.$el.select()
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="createdSecret ? tt('createdTitle') : tt('createButton')"
    style="width: var(--dialog-width-md)"
  >
    <template v-if="createdSecret">
      <Message severity="warn" :closable="false">
        {{ tt('secretWarning') }}
      </Message>
      <div class="secret-row">
        <InputText
          ref="secretInput"
          :model-value="createdSecret"
          readonly
          fluid
          class="secret-input"
        />
        <Button icon="mdi mdi-content-copy" severity="secondary" :aria-label="t('common.copy')" @click="onCopySecret" />
      </div>
      <div class="dialog-footer">
        <Button :label="t('common.close')" @click="visible = false" />
      </div>
    </template>

    <template v-else>
      <div class="form-fields">
        <div class="form-field">
          <label :for="`${uid}-name`">{{ tt('fields.name') }}</label>
          <InputText v-model="form.name" :id="`${uid}-name`" fluid autofocus />
        </div>

        <div class="form-field">
          <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
          <label :id="`${uid}-permissions`">{{ tt('fields.permissions') }}</label>
          <div role="group" :aria-labelledby="`${uid}-permissions`" class="permissions-grid">
            <div v-for="perm in grantablePermissions" :key="perm" class="permission-item">
              <Checkbox :input-id="`tok-perm-${perm}`" v-model="form.permissions" :value="perm" />
              <label :for="`tok-perm-${perm}`">{{ permissionLabel(t, perm) }}</label>
            </div>
          </div>
          <Message
            v-if="addinPreset && addinMissingPermissions.length > 0"
            severity="warn"
            :closable="false"
          >
            {{ tt('addinMissingPermission', { permissions: addinMissingPermissionLabels }) }}
          </Message>
        </div>

        <div class="form-field">
          <label :for="`${uid}-expires-in-days`">{{ tt('fields.expiresInDays') }}</label>
          <div class="expiry-row">
            <InputNumber
              v-model="form.expiresInDays"
              :input-id="`${uid}-expires-in-days`"
              :min="1"
              :max="maxDays"
              :disabled="form.neverExpires && !capped"
              fluid
            />
          </div>
          <small class="hint">
            {{
              capped
                ? tt('fields.expiresInDaysHint', { days: hostStore.tokenMaxLifetimeDays })
                : tt('fields.expiresInDaysNoCapHint')
            }}
          </small>
          <div
            v-tooltip.top="
              capped
                ? tt('fields.neverExpiresCapped', { days: hostStore.tokenMaxLifetimeDays })
                : undefined
            "
            class="toggle-item"
            data-testid="tok-never-expires-row"
          >
            <ToggleSwitch
              v-model="form.neverExpires"
              input-id="tok-never-expires"
              :disabled="capped"
            />
            <label for="tok-never-expires">{{ tt('fields.neverExpires') }}</label>
          </div>
          <Message v-if="form.neverExpires && !capped" severity="warn" :closable="false">
            {{ tt('neverExpiresWarning') }}
          </Message>
        </div>

        <div v-if="store.requiresPassword" class="form-field">
          <label :for="`${uid}-password`">{{ tt('fields.password') }}</label>
          <Password
            v-model="form.password"
            :input-id="`${uid}-password`"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            fluid
          />
          <small class="hint">{{ tt('fields.passwordHint') }}</small>
        </div>
      </div>

      <div class="dialog-footer">
        <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save"
          :loading="saving"
          :disabled="!isValid"
          @click="onSave"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.permissions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  max-height: 14rem;
  overflow-y: auto;
  padding: var(--space-1);
}

.permission-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-color);
  }
}

.expiry-row {
  display: flex;
  gap: var(--space-2);
}

.hint {
  font-size: var(--font-size-xs);
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-color);
  }
}

.secret-row {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.secret-input {
  font-family: monospace;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}
</style>
