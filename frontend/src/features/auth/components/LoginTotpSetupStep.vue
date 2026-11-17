<script setup lang="ts">
// The forced two-factor enrolment of the login card: the QR code and the
// secret for manual entry, then the first code, handed to LoginView as soon
// as it has six digits. LoginView submits the code itself because a completed
// enrolment swaps this step out before the request settles, and Vue drops
// events from an unmounted component. The field, description and code input
// styles are the card's form styles, which LoginView owns.
import { ref, useId, watch } from 'vue'
import QRCode from 'qrcode'
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

const setupQrDataUrl = ref<string | null>(null)
const setupCode = ref('')
const secretCopied = ref(false)

async function onCopySecret() {
  if (!authStore.setupSecret) return

  try {
    await navigator.clipboard.writeText(authStore.setupSecret)
    secretCopied.value = true
    setTimeout(() => (secretCopied.value = false), 2000)
  } catch {
    // Clipboard access can be refused; the key stays visible and selectable.
  }
}

// Renders the QR as soon as the store has the URI.
watch(
  () => authStore.setupProvisioningUri,
  async (uri) => {
    if (!uri) {
      setupQrDataUrl.value = null
      return
    }

    try {
      setupQrDataUrl.value = await QRCode.toDataURL(uri, { width: 200, margin: 1 })
    } catch {
      // The secret is shown alongside, so a failed QR render is not fatal.
      setupQrDataUrl.value = null
    }
  },
  { immediate: true },
)

function onSetupInput(value: string) {
  setupCode.value = value
  if (value.length === 6) emit('submit', value)
}

/** Empties the code after LoginView saw it rejected. */
function clear() {
  setupCode.value = ''
}

defineExpose({ clear })
</script>

<template>
  <div class="login-form totp-form">
    <p class="totp-description">
      {{ t('login.totpSetup.description', { name: authStore.setupUsername }) }}
    </p>

    <img
      v-if="setupQrDataUrl"
      :src="setupQrDataUrl"
      :alt="t('login.totpSetup.qrAlt')"
      class="totp-qr"
    />

    <div v-if="authStore.setupSecret" class="totp-secret">
      <span class="totp-secret-label">{{ t('login.totpSetup.manualEntry') }}</span>
      <div class="totp-secret-row">
        <code class="totp-secret-value">{{ authStore.setupSecret }}</code>
        <Button
          type="button"
          :icon="secretCopied ? 'mdi mdi-check' : 'mdi mdi-content-copy'"
          :aria-label="t('common.copy')"
          text
          rounded
          class="totp-secret-copy"
          :class="{ 'is-copied': secretCopied }"
          @click="onCopySecret"
        />
      </div>
    </div>

    <div class="field totp-otp-field">
      <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- InputOtp renders one input per digit, so the label names the group through aria-labelledby -->
      <label :id="`${uid}-code`">{{ t('login.totpSetup.code') }}</label>
      <InputOtp
        role="group"
        :aria-labelledby="`${uid}-code`"
        :model-value="setupCode"
        :length="6"
        integer-only
        :disabled="authStore.loading"
        @update:model-value="onSetupInput($event as string)"
      />
    </div>

    <Message v-if="totpErrorMessage" severity="error" :closable="false">
      {{ totpErrorMessage }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
// Part of the login card, which keeps its fixed dark look in every theme.
.totp-qr {
  align-self: center;
  border-radius: 10px;
  /* The QR itself must stay pure white to scan reliably, the padding is
     what keeps it legible against the dark card. */
  background: var(--paper);
  padding: var(--space-2);
}

.totp-secret {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.totp-secret-label {
  color: var(--auth-text);
  font-size: var(--font-size-xs);
  text-align: center;
}

.totp-secret-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--auth-field);
  border: 1px solid var(--auth-line);
  border-radius: 9px;
  padding: var(--space-1) var(--space-1) var(--space-1) var(--space-2);
}

.totp-secret-value {
  flex: 1;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: var(--font-size-sm);
  /* A base32 secret is typed by hand when the QR cannot be scanned, and
     spacing it out makes character-by-character transcription far easier. */
  letter-spacing: 0.08em;
  word-break: break-all;
  color: var(--auth-text-strong);
}

.totp-secret-copy {
  flex: none;
  color: var(--auth-text) !important;
}

.totp-secret-copy:hover {
  color: var(--auth-text-strong) !important;
  background: var(--auth-field-hover) !important;
}

.totp-secret-copy.is-copied {
  color: var(--p-green-400) !important;
}
</style>
