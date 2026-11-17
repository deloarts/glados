<script setup lang="ts">
// The two-factor challenge of the login card: the six digit code, handed to
// LoginView as soon as it is complete, and the option to trust this device.
// LoginView submits the code itself because an accepted code swaps this step
// out before the request settles, and Vue drops events from an unmounted
// component. Its styles are the card's form styles, which LoginView owns.
import { ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAuthStore } from '../stores/authStore'
import { useTotpErrorMessage } from '../composables/useLoginMessages'

const emit = defineEmits<{
  submit: [code: string]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const authStore = useAuthStore()
const totpErrorMessage = useTotpErrorMessage()

const totpCode = ref('')
const otpRef = ref()

function onTotpInput(value: string) {
  totpCode.value = value
  if (value.length === 6) emit('submit', value)
}

/** Empties the code after LoginView saw it rejected. */
function clear() {
  totpCode.value = ''
}

function onTotpBack() {
  totpCode.value = ''
  authStore.cancelTotp()
}

/** Puts the cursor into the first digit once the step has slid in. */
function focus() {
  otpRef.value?.$el?.querySelector('input')?.focus()
}

defineExpose({ focus, clear })
</script>

<template>
  <div class="login-form totp-form">
    <p class="totp-description">{{ t('login.totp.description') }}</p>

    <div class="field totp-otp-field">
      <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- InputOtp renders one input per digit, so the label names the group through aria-labelledby -->
      <label :id="`${uid}-code`">{{ t('login.totp.code') }}</label>
      <InputOtp
        role="group"
        :aria-labelledby="`${uid}-code`"
        ref="otpRef"
        :model-value="totpCode"
        :length="6"
        integer-only
        :disabled="authStore.loading"
        @update:model-value="onTotpInput($event as string)"
      />
    </div>

    <div v-if="authStore.trustedDeviceDays > 0" class="field trust-device-field">
      <Checkbox
        v-model="authStore.trustDevice"
        input-id="trust-device"
        binary
        :disabled="authStore.loading"
      />
      <label for="trust-device">
        {{ t('login.totp.trustDevice', { days: authStore.trustedDeviceDays }) }}
      </label>
    </div>

    <Message v-if="totpErrorMessage" severity="error" :closable="false">
      {{ totpErrorMessage }}
    </Message>

    <Button
      v-if="authStore.loading"
      :label="t('login.totp.submit')"
      :loading="true"
      class="login-submit"
      disabled
    />

    <button
      v-else
      type="button"
      class="back-btn"
      :disabled="authStore.loading"
      @click="onTotpBack"
    >
      <span class="mdi mdi-arrow-left" />
      {{ t('login.totp.back') }}
    </button>
  </div>
</template>

