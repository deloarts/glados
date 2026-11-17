<script setup lang="ts">
// The time tracking block of My Account: the user's own credentials for the
// time tracking system, an access check, and their removal. Opening the
// page reads only the Glados-side account state from the shared store; the
// time tracking service is contacted only by Save and Check access, which
// verify the sign-in and report what the account may read. That result is
// shown from the response and never kept. Glados seals the password for the
// service on save and cannot read it afterwards, so a stored password can
// only be re-verified for the same user name, never reused for another.
//
// My Account's single Save button calls save() when this block is dirty,
// independently of the profile save. The first save, and a save after the
// consent text changed, asks for consent first. The password field is never
// prefilled, never stored client-side, and cleared after every attempt.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { useAppToast } from '@/core/composables/useAppToast'
import {
  checkMyTimeTrackingAccess,
  deleteMyTimeTrackingAccount,
  saveMyTimeTrackingAccount,
} from '../api/timeTrackingApi'
import { useTimeTrackingAvailability } from '../composables/useTimeTrackingAvailability'
import { useTimeTrackingAccountStore } from '../stores/timeTrackingAccountStore'
import type { TimeTrackingAccountResponse, TimeTrackingReadRights } from '../types/timeTrackingTypes'
import { isCredentialStateError, timeTrackingErrorMessage } from '../utils/timeTrackingErrors'
import TimeTrackingConsentDialog from './TimeTrackingConsentDialog.vue'

// Mirrors the backend's input rules, so an invalid value is caught before
// it costs a sign-in attempt.
const USER_MAX_LENGTH = 128
const PASSWORD_MAX_LENGTH = 256

function hasControlCharacter(value: string): boolean {
  for (const char of value) {
    const code = char.codePointAt(0) ?? 0
    if (code < 0x20 || code === 0x7f) return true
  }
  return false
}

// Reasons after which the stored password cannot be reused, so a save needs
// it typed again.
const PASSWORD_REENTRY_REASONS = new Set(['undecryptable', 'binding_changed', 'auth_failed'])
const HINTED_REASONS = new Set([
  'undecryptable',
  'binding_changed',
  'auth_failed',
  'consent_outdated',
])

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const store = useTimeTrackingAccountStore()
const { providerName } = useTimeTrackingAvailability()

const account = computed<TimeTrackingAccountResponse | null>(() => store.account)

const form = reactive({ user: '', password: '' })

watch(
  account,
  (value) => {
    form.user = value?.time_tracking_user ?? ''
    form.password = ''
  },
  { immediate: true },
)

onMounted(() => {
  void store.ensureLoaded()
})

interface Verification {
  employeeName: string | null
  rights: TimeTrackingReadRights | null
}

// The result of the last save or check on this page; gone on reload.
const verification = ref<Verification | null>(null)

const hasStoredCredentials = computed(
  () => !!account.value?.time_tracking_user || !!account.value?.time_tracking_password_configured,
)
const invalidReason = computed(() => account.value?.time_tracking_credentials_invalid_reason ?? null)
const invalidHint = computed(() =>
  invalidReason.value && HINTED_REASONS.has(invalidReason.value)
    ? t(`accountMe.timeTracking.invalid.${invalidReason.value}`, { provider: providerName.value })
    : null,
)

const userChanged = computed(
  () =>
    form.user.trim().toLowerCase() !== (account.value?.time_tracking_user ?? '').toLowerCase(),
)

const passwordRequired = computed(
  () =>
    !account.value?.time_tracking_password_configured ||
    userChanged.value ||
    (invalidReason.value !== null && PASSWORD_REENTRY_REASONS.has(invalidReason.value)),
)

const userError = computed(() => {
  const user = form.user.trim()
  if (!user) return null
  if (user.length > USER_MAX_LENGTH || user.includes(':') || hasControlCharacter(user)) {
    return t('accountMe.timeTracking.errors.userInvalid')
  }
  return null
})

const passwordError = computed(() =>
  form.password.length > PASSWORD_MAX_LENGTH || hasControlCharacter(form.password)
    ? t('accountMe.timeTracking.errors.passwordInvalid')
    : null,
)

const isDirty = computed(() => {
  if (!store.loaded) return false
  return form.user.trim() !== (account.value?.time_tracking_user ?? '') || form.password !== ''
})

const saving = ref(false)
const checking = ref(false)
const removing = ref(false)

// ── Consent ─────────────────────────────────────────────────────────────

const consentVisible = ref(false)
let resolveConsent: ((confirmed: boolean) => void) | null = null

function requestConsent(): Promise<boolean> {
  consentVisible.value = true
  return new Promise<boolean>((resolve) => {
    resolveConsent = resolve
  })
}

function settleConsent(confirmed: boolean): void {
  consentVisible.value = false
  resolveConsent?.(confirmed)
  resolveConsent = null
}

// ── Save ────────────────────────────────────────────────────────────────

function validate(): boolean {
  const provider = providerName.value
  if (!form.user.trim()) {
    toast.warn(t('accountMe.timeTracking.errors.userRequired', { provider }))
    return false
  }
  if (passwordRequired.value && !form.password) {
    toast.warn(t('accountMe.timeTracking.errors.passwordRequired', { provider }))
    return false
  }
  if (userError.value || passwordError.value) {
    toast.warn(t('accountMe.timeTracking.errors.invalidInput'))
    return false
  }
  return true
}

/** Saves the block; resolves once done, declined or failed, never throws. */
async function save(): Promise<void> {
  const current = account.value
  if (!current || saving.value || !validate()) return

  if (!current.time_tracking_consent_current) {
    const confirmed = await requestConsent()
    if (!confirmed) return
  }

  saving.value = true
  const provider = providerName.value
  try {
    const result = await saveMyTimeTrackingAccount({
      time_tracking_user: form.user.trim(),
      time_tracking_password: form.password || null,
      time_tracking_consent_version: current.time_tracking_consent_version,
    })
    verification.value = {
      employeeName: result.time_tracking_employee_name,
      rights: result.time_tracking_rights,
    }
    store.setAccount(result)
    toast.success(t('accountMe.timeTracking.saved', { provider }))
  } catch (err: unknown) {
    toast.error(
      t('accountMe.timeTracking.saveFailed', { provider }),
      timeTrackingErrorMessage(err, t, t('accountMe.errors.unknown')),
    )
    if (isCredentialStateError(err)) void store.refresh()
  } finally {
    form.password = ''
    saving.value = false
  }
}

// ── Check access ────────────────────────────────────────────────────────

const canCheck = computed(() => store.credentialsValid && !isDirty.value)

// Why Check access is off: it re-tests the stored credentials, so there must
// be usable ones and no unsaved edit.
const checkBlocked = computed<string | undefined>(() => {
  if (isDirty.value) return t('accountMe.timeTracking.checkBlocked.unsaved')
  if (store.credentialsValid) return undefined
  if (invalidReason.value === 'consent_outdated') {
    return t('accountMe.timeTracking.checkBlocked.consent')
  }
  if (invalidReason.value && PASSWORD_REENTRY_REASONS.has(invalidReason.value)) {
    return t('accountMe.timeTracking.checkBlocked.password')
  }
  return t('accountMe.timeTracking.checkBlocked.missing')
})

async function onCheck(): Promise<void> {
  checking.value = true
  try {
    const result = await checkMyTimeTrackingAccess()
    verification.value = {
      employeeName: result.time_tracking_employee_name,
      rights: result.time_tracking_rights,
    }
    store.setAccount(result)
  } catch (err: unknown) {
    verification.value = null
    toast.error(
      t('accountMe.timeTracking.checkFailed'),
      timeTrackingErrorMessage(err, t, t('accountMe.errors.unknown')),
    )
    if (isCredentialStateError(err)) void store.refresh()
  } finally {
    checking.value = false
  }
}

// ── Remove ──────────────────────────────────────────────────────────────

function onRemove(): void {
  const provider = providerName.value
  async function onAccept(): Promise<void> {
    removing.value = true
    try {
      await deleteMyTimeTrackingAccount()
      verification.value = null
      await store.refresh()
      toast.success(t('accountMe.timeTracking.removed', { provider }))
    } catch (err: unknown) {
      toast.error(
        t('accountMe.timeTracking.removeFailed'),
        timeTrackingErrorMessage(err, t, t('accountMe.errors.unknown')),
      )
    } finally {
      removing.value = false
    }
  }

  confirm.require({
    group: 'account-time-tracking',
    header: t('accountMe.timeTracking.remove', { provider }),
    message: t('accountMe.timeTracking.removeConfirm', { provider }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('accountMe.timeTracking.remove', { provider }), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

// ── Rights chips ────────────────────────────────────────────────────────

const rightChips = computed(() => {
  const rights = verification.value?.rights
  if (!rights) return []
  return (['days', 'month', 'year'] as const).map((key) => ({
    key,
    label: t(`accountMe.timeTracking.rights.${key}`),
    allowed: rights[key] === true,
  }))
})

defineExpose({ isDirty, saving, save })
</script>

<template>
  <div class="time-tracking-section" data-testid="account-time-tracking-section">
    <p class="section-label">
      {{ t('accountMe.timeTracking.title', { provider: providerName }) }}
    </p>

    <Message v-if="invalidHint" severity="warn" :closable="false" data-testid="time-tracking-invalid-hint">
      {{ invalidHint }}
    </Message>

    <div class="field-row">
      <label for="account-time-tracking-user">
        {{ t('accountMe.timeTracking.user', { provider: providerName }) }}
      </label>
      <div class="time-tracking-field">
        <InputText
          id="account-time-tracking-user"
          v-model="form.user"
          autocomplete="off"
          :invalid="!!userError"
          fluid
        />
        <small v-if="userError" class="field-error">{{ userError }}</small>
      </div>
    </div>

    <div class="field-row">
      <label for="account-time-tracking-password">
        {{ t('accountMe.timeTracking.password', { provider: providerName }) }}
      </label>
      <div class="time-tracking-field">
        <InputText
          id="account-time-tracking-password"
          v-model="form.password"
          type="password"
          autocomplete="new-password"
          :invalid="!!passwordError"
          :placeholder="
            account?.time_tracking_password_configured && !passwordRequired
              ? t('accountMe.timeTracking.passwordSaved')
              : ''
          "
          fluid
        />
        <small v-if="passwordError" class="field-error">{{ passwordError }}</small>
      </div>
    </div>

    <div class="field-row">
      <span />
      <div class="time-tracking-actions">
        <span v-tooltip.top="checkBlocked" data-testid="time-tracking-check-access-tooltip">
          <Button
            :label="t('accountMe.timeTracking.checkAccess')"
            icon="mdi mdi-account-check-outline"
            severity="contrast"
            text
            size="small"
            :loading="checking"
            :disabled="!canCheck"
            data-testid="time-tracking-check-access"
            @click="onCheck"
          />
        </span>
        <Button
          v-if="invalidReason === 'consent_outdated'"
          :label="t('accountMe.timeTracking.confirmConsent')"
          icon="mdi mdi-file-sign"
          severity="contrast"
          text
          size="small"
          :loading="saving"
          data-testid="time-tracking-confirm-consent"
          @click="save"
        />
        <Button
          v-if="hasStoredCredentials"
          :label="t('accountMe.timeTracking.remove', { provider: providerName })"
          icon="mdi mdi-delete-outline"
          severity="danger"
          text
          size="small"
          :loading="removing"
          data-testid="time-tracking-remove"
          @click="onRemove"
        />
      </div>
    </div>

    <div v-if="verification" class="field-row" data-testid="time-tracking-verification">
      <span />
      <div class="time-tracking-verification">
        <span v-if="verification.employeeName" class="signed-in-as">
          <i class="mdi mdi-check-circle-outline" aria-hidden="true" />
          {{ t('accountMe.timeTracking.signedInAs', { name: verification.employeeName }) }}
        </span>
        <div class="rights-chips">
          <Tag
            v-for="chip in rightChips"
            :key="chip.key"
            :severity="chip.allowed ? 'success' : 'danger'"
            :icon="chip.allowed ? 'mdi mdi-check' : 'mdi mdi-close'"
            :value="chip.label"
            :aria-label="
              `${chip.label}: ${
                chip.allowed
                  ? t('accountMe.timeTracking.rights.allowed')
                  : t('accountMe.timeTracking.rights.notAllowed')
              }`
            "
            :data-testid="`time-tracking-right-${chip.key}`"
            :data-allowed="chip.allowed"
          />
        </div>
      </div>
    </div>

    <TimeTrackingConsentDialog
      :visible="consentVisible"
      :provider-name="providerName"
      :privacy-policy-url="account?.time_tracking_privacy_policy_url ?? null"
      @confirm="settleConsent(true)"
      @cancel="settleConsent(false)"
    />
    <ConfirmDialog group="account-time-tracking" />
  </div>
</template>

<style scoped lang="scss">
.time-tracking-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.time-tracking-field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  min-width: 0;
  max-width: 24rem;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-xs);
}

.time-tracking-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.time-tracking-verification {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.signed-in-as {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
}

.rights-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
