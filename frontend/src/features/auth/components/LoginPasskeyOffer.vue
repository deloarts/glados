<script setup lang="ts">
// The login card's offer, right after a password sign-in, to set up a
// passkey on this device. The description, button and back link styles are
// the card's form styles, which LoginView owns.
import { useI18n } from 'vue-i18n'

import type { PlatformAuthenticator } from '../utils/webauthn'

defineProps<{
  authenticatorKind: PlatformAuthenticator
  loading: boolean
  error: string | null
}>()

const emit = defineEmits<{
  accept: []
  decline: []
}>()

const { t } = useI18n()
</script>

<template>
  <div class="login-form totp-form">
    <span class="mdi mdi-fingerprint offer-icon" aria-hidden="true" />
    <p class="totp-description">{{ t('login.passkey.offer.description') }}</p>

    <Message v-if="error" severity="warn" :closable="false">
      {{ error }}
    </Message>

    <Button
      type="button"
      :label="t(`login.passkey.offer.accept.${authenticatorKind}`)"
      icon="mdi mdi-fingerprint"
      :loading="loading"
      class="login-submit"
      data-testid="login-passkey-accept"
      @click="emit('accept')"
    />

    <button
      type="button"
      class="back-btn"
      :disabled="loading"
      data-testid="login-passkey-decline"
      @click="emit('decline')"
    >
      {{ t('login.passkey.offer.notNow') }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.offer-icon {
  align-self: center;
  font-size: var(--font-size-4xl);
  color: var(--auth-accent-text);
}
</style>
