<script setup lang="ts">
import { computed, onMounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import QRCode from 'qrcode'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { enrollTotp, confirmTotp, disableTotp } from '../api/totp'
import { extractApiErrorCode } from '@/core/utils/errors'
import { HelpButton } from '@/shared/help'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const userStore = useCurrentUserStore()

const totpEnabled = computed(() => userStore.user?.totp_enabled ?? false)
const isSystemUser = computed(() => userStore.user?.is_systemuser ?? false)

// Setup flow: the password is confirmed first, then the QR code is shown.
const askingPassword = ref(false)
const setupPassword = ref('')
const enrolling = ref(false)
const qrDataUrl = ref<string | null>(null)
const secret = ref<string | null>(null)
const confirmCode = ref('')
const setupLoading = ref(false)
const setupError = ref<string | null>(null)
const setupSuccess = ref(false)

// Disable flow
const disabling = ref(false)
const disableCode = ref('')
const disableLoading = ref(false)
const disableError = ref<string | null>(null)

function openSetup() {
  setupError.value = null
  setupPassword.value = ''
  askingPassword.value = true
}

async function startEnroll() {
  if (setupPassword.value === '') return
  setupError.value = null
  setupLoading.value = true
  try {
    const data = await enrollTotp(setupPassword.value)
    secret.value = data.secret
    qrDataUrl.value = await QRCode.toDataURL(data.provisioning_uri, { width: 200, margin: 1 })
    setupPassword.value = ''
    askingPassword.value = false
    enrolling.value = true
  } catch (e: unknown) {
    // Match on `code`, never on the translatable `detail` prose.
    switch (extractApiErrorCode(e)) {
      case 'PasswordConfirmationFailedError':
        setupError.value = t('account.twoFactor.errors.wrongPassword')
        break
      case 'LoginLockedError':
        setupError.value = t('login.errors.lockedOut')
        break
      default:
        setupError.value = t('account.twoFactor.errors.unknown')
    }
  } finally {
    setupLoading.value = false
  }
}

async function onConfirmInput(value: string) {
  confirmCode.value = value
  if (value.length < 6) return

  setupError.value = null
  setupLoading.value = true
  try {
    await confirmTotp(value)
    await userStore.refresh()
    enrolling.value = false
    qrDataUrl.value = null
    secret.value = null
    confirmCode.value = ''
    setupSuccess.value = true
  } catch (e: unknown) {
    // Match on `code`, never on the translatable `detail` prose.
    const code = extractApiErrorCode(e)
    setupError.value =
      code === 'InvalidTOTPCodeError'
        ? t('account.twoFactor.errors.invalidCode')
        : t('account.twoFactor.errors.unknown')
    confirmCode.value = ''
  } finally {
    setupLoading.value = false
  }
}

function cancelDisable() {
  disabling.value = false
  disableCode.value = ''
  disableError.value = null
}

function cancelEnroll() {
  askingPassword.value = false
  setupPassword.value = ''
  enrolling.value = false
  qrDataUrl.value = null
  secret.value = null
  confirmCode.value = ''
  setupError.value = null
}

async function onDisableInput(value: string) {
  disableCode.value = value
  if (value.length < 6) return

  disableError.value = null
  disableLoading.value = true
  try {
    await disableTotp(value)
    await userStore.refresh()
    disabling.value = false
    disableCode.value = ''
  } catch (e: unknown) {
    const code = extractApiErrorCode(e)
    disableError.value =
      code === 'InvalidTOTPCodeError'
        ? t('account.twoFactor.errors.invalidCode')
        : t('account.twoFactor.errors.unknown')
    disableCode.value = ''
  } finally {
    disableLoading.value = false
  }
}

onMounted(() => {
  setupSuccess.value = false
})
</script>

<template>
  <div class="tfa-view">
    <div class="tfa-card card">
      <div class="tfa-header">
        <div class="tfa-title-row">
          <h2 class="tfa-title">{{ t('account.twoFactor.title') }}</h2>
          <Tag
            :value="
              totpEnabled
                ? t('account.twoFactor.status.enabled')
                : t('account.twoFactor.status.disabled')
            "
            :severity="totpEnabled ? 'success' : 'secondary'"
          />
        </div>
      </div>

      <!-- Enabled state -->
      <template v-if="totpEnabled">
        <p class="tfa-description">{{ t('account.twoFactor.status.enabledHint') }}</p>

        <Message v-if="isSystemUser" severity="info" :closable="false">
          {{ t('account.twoFactor.systemUserMandatory') }}
        </Message>

        <template v-else>
          <template v-if="!disabling">
            <Button
              :label="t('account.twoFactor.disable.open')"
              severity="danger"
              outlined
              @click="disabling = true"
            />
          </template>

          <template v-else>
            <div class="tfa-section">
              <p class="tfa-section-description">{{ t('account.twoFactor.disable.description') }}</p>

              <div class="field tfa-otp-field">
                <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- InputOtp renders one input per digit, so the label names the group through aria-labelledby -->
                <label :id="`${uid}-disable-code`">{{ t('account.twoFactor.disable.code') }}</label>
                <InputOtp
                  role="group"
                  :aria-labelledby="`${uid}-disable-code`"
                  :model-value="disableCode"
                  :length="6"
                  integer-only
                  :disabled="disableLoading"
                  @update:model-value="onDisableInput($event as string)"
                />
              </div>

              <Message v-if="disableError" severity="error" :closable="false">
                {{ disableError }}
              </Message>

              <div v-if="disableLoading" class="tfa-actions">
                <Button
                  :label="t('account.twoFactor.disable.submit')"
                  severity="danger"
                  :loading="true"
                  :text="false"
                  disabled
                />
              </div>
              <div v-else class="tfa-actions">
                <Button
                  :label="t('common.cancel')"
                  severity="secondary"
                  text
                  @click="cancelDisable"
                />
              </div>
            </div>
          </template>
        </template>
      </template>

      <!-- Disabled state -->
      <template v-else>
        <p class="tfa-description">{{ t('account.twoFactor.status.disabledHint') }}</p>

        <Message v-if="setupSuccess" severity="success" :closable="false">
          {{ t('account.twoFactor.success.enabled') }}
        </Message>

        <template v-if="!enrolling && !askingPassword">
          <Button :label="t('account.twoFactor.setup.open')" @click="openSetup" />
        </template>

        <form v-else-if="askingPassword" class="tfa-section" @submit.prevent="startEnroll">
          <p class="tfa-section-description">
            {{ t('account.twoFactor.setup.passwordDescription') }}
          </p>
          <div class="field tfa-password-field">
            <label :for="`${uid}-setup-password`">{{ t('account.twoFactor.setup.password') }}</label>
            <Password
              v-model="setupPassword"
              :input-id="`${uid}-setup-password`"
              :feedback="false"
              toggle-mask
              autocomplete="current-password"
              fluid
              autofocus
            />
          </div>

          <Message v-if="setupError" severity="error" :closable="false">
            {{ setupError }}
          </Message>

          <div class="tfa-actions">
            <Button
              type="submit"
              :label="t('account.twoFactor.setup.continue')"
              :loading="setupLoading"
              :disabled="setupPassword === ''"
            />
            <Button
              :label="t('common.cancel')"
              severity="secondary"
              text
              :disabled="setupLoading"
              @click="cancelEnroll"
            />
          </div>
        </form>

        <template v-else>
          <div class="tfa-section">
            <p class="tfa-section-description">{{ t('account.twoFactor.setup.description') }}</p>

            <div class="qr-wrapper">
              <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR Code" class="qr-code" />
            </div>

            <div class="secret-row">
              <span class="secret-label">{{ t('account.twoFactor.setup.secret') }}</span>
              <code class="secret-value">{{ secret }}</code>
            </div>

            <div class="field tfa-otp-field">
              <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- InputOtp renders one input per digit, so the label names the group through aria-labelledby -->
              <label :id="`${uid}-setup-code`">{{ t('account.twoFactor.setup.code') }}</label>
              <InputOtp
                role="group"
                :aria-labelledby="`${uid}-setup-code`"
                :model-value="confirmCode"
                :length="6"
                integer-only
                :disabled="setupLoading"
                @update:model-value="onConfirmInput($event as string)"
              />
            </div>

            <Message v-if="setupError" severity="error" :closable="false">
              {{ setupError }}
            </Message>

            <div v-if="setupLoading" class="tfa-actions">
              <Button :label="t('account.twoFactor.setup.confirm')" :loading="true" disabled />
            </div>
            <div v-else class="tfa-actions">
              <Button :label="t('common.cancel')" severity="secondary" text @click="cancelEnroll" />
            </div>
          </div>
        </template>
      </template>
      <span class="tfa-help">
        <HelpButton slug="account/two-factor" size="small" rounded />
      </span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tfa-view {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

.tfa-card {
  position: relative;
  width: 100%;
  max-width: 480px;
  padding: var(--space-6);

  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tfa-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tfa-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

// Last in the card so the card's own actions come first, and placed in
// the top right corner next to the title.
.tfa-help {
  position: absolute;
  top: var(--space-4);
  right: var(--space-4);
}

.tfa-title {
  margin: 0;
  color: var(--p-text-color);
  font-size: var(--font-size-lg);
}

.tfa-description {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.tfa-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tfa-section-description {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.qr-wrapper {
  display: flex;
  justify-content: center;
}

.qr-code {
  border-radius: 0.5rem;
  background: var(--paper);
  padding: var(--space-2);
}

.secret-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.secret-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.secret-value {
  font-size: var(--font-size-sm);
  word-break: break-all;
  background: var(--p-surface-100);
  padding: var(--space-2) var(--space-2);
  border-radius: 0.375rem;
  color: var(--p-text-color);
}

.p-dark .secret-value {
  background: var(--p-surface-800);
}

.field label {
  color: var(--p-text-color);
  font-size: var(--font-size-sm);
}

// The code's digit boxes share the field's width evenly.
.field {
  --p-inputotp-input-width: 100%;
}

.tfa-otp-field {
  align-items: center;
}

.tfa-password-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tfa-actions {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
