<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import LoginMaintenanceBanner from '../components/LoginMaintenanceBanner.vue'
import LoginPasskeyOffer from '../components/LoginPasskeyOffer.vue'
import LoginTotpSetupStep from '../components/LoginTotpSetupStep.vue'
import LoginTotpStep from '../components/LoginTotpStep.vue'
import OtherRememberedUsers from '../components/OtherRememberedUsers.vue'
import RememberedUserHeader from '../components/RememberedUserHeader.vue'
import { useLoginErrorMessage, usePasskeyErrorMessage } from '../composables/useLoginMessages'
import { useAuthStore } from '../stores/authStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { postLoginTarget } from '../utils/postLoginTarget'
import { setUpPasskeyOnThisDevice } from '../utils/passkeySetup'
import {
  findRememberedUser,
  forgetRememberedUser,
  listRememberedUsers,
  updateRememberedUser,
  type RememberedUser,
} from '../utils/rememberedUsers'
import {
  passkeyPromptDismissed,
  passkeysSupported,
  platformAuthenticatorAvailable,
  platformAuthenticatorKind,
} from '../utils/webauthn'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const authStore = useAuthStore()
const publicBrandingStore = usePublicBrandingStore()

// A mid-visit bounce here resets every store including branding, and App.vue
// only fetches it once at page load, so refetch on every mount.
onMounted(() => {
  void publicBrandingStore.fetch()
  void platformAuthenticatorAvailable().then((available) => (canOfferPasskey.value = available))
})

const username = ref('')
const password = ref('')

// Bounce reasons set by the api interceptor; cleared once the user types again.
const sessionExpired = ref(route.query.reason === 'expired')
const maintenanceLockoutReason = ref(route.query.reason === 'maintenance')

const errorMessage = useLoginErrorMessage(sessionExpired, maintenanceLockoutReason)
const passkeyErrorMessage = usePasskeyErrorMessage()

// ── Remembered users ─────────────────────────────────────────────────────────

// Accounts that signed in on this device before. With one remembered, the page
// opens on that account instead of the empty form.
const rememberedUsers = ref<RememberedUser[]>(listRememberedUsers())
const selectedUser = ref<RememberedUser | null>(rememberedUsers.value[0] ?? null)
const switchingUser = ref(selectedUser.value === null)
const askPassword = ref(false)
const chooserHint = ref<string | null>(null)

const passkeysUsable = passkeysSupported()
const canOfferPasskey = ref(false)
const authenticatorKind = platformAuthenticatorKind()

const otherRememberedUsers = computed(() =>
  rememberedUsers.value.filter((u) => u.username !== selectedUser.value?.username),
)

const selectedUsesPasskey = computed(() => passkeysUsable && !!selectedUser.value?.credentialId)

function onSelectRemembered(user: RememberedUser) {
  selectedUser.value = user
  askPassword.value = false
  chooserHint.value = null
  password.value = ''
  authStore.clearPasskeyError()
}

function onSwitchUser() {
  switchingUser.value = true
  username.value = ''
  password.value = ''
  authStore.clearPasskeyError()
}

function onBackToChooser() {
  switchingUser.value = false
  askPassword.value = false
  password.value = ''
}

function onForgetUser() {
  if (!selectedUser.value) return
  forgetRememberedUser(selectedUser.value.username)
  rememberedUsers.value = listRememberedUsers()
  selectedUser.value = rememberedUsers.value[0] ?? null
  switchingUser.value = selectedUser.value === null
  askPassword.value = false
  chooserHint.value = null
}

// The remembered account's sign-in: the passkey this device registered when
// there is one, the password otherwise or when the prompt is dismissed.
async function onChooserSignIn() {
  const user = selectedUser.value
  if (!user) return

  sessionExpired.value = false
  maintenanceLockoutReason.value = false

  if (!selectedUsesPasskey.value) {
    askPassword.value = true
    return
  }

  const outcome = await authStore.loginWithPasskey(user.username, user.credentialId)
  if (outcome === 'signed_in') {
    await finishLogin(true)
    return
  }
  chooserHint.value = outcome === 'dismissed' ? t('login.chooser.usePassword') : null
  askPassword.value = true
}

async function onChooserPasswordSubmit() {
  if (!selectedUser.value) return
  username.value = selectedUser.value.username
  await onSubmit()
}

// A passkey without a remembered account: the browser offers every passkey
// it holds for this site.
async function onPasskeySignIn() {
  sessionExpired.value = false
  maintenanceLockoutReason.value = false

  const outcome = await authStore.loginWithPasskey('', null)
  if (outcome === 'signed_in') await finishLogin(true)
}

// ── After a successful sign-in ───────────────────────────────────────────────

const offeringPasskey = ref(false)
const passkeySetupLoading = ref(false)
const passkeySetupError = ref<string | null>(null)

/** Whether to offer a passkey for this device right after a password sign-in. */
function shouldOfferPasskey(): boolean {
  const user = useCurrentUserStore().user
  if (!user || !canOfferPasskey.value) return false
  if (user.is_systemuser) return false
  const remembered = findRememberedUser(user.username)
  return !remembered?.credentialId && !remembered?.passkeyDeclined
}

async function finishLogin(viaPasskey: boolean) {
  await authStore.rememberSignedInUser()
  if (!viaPasskey && shouldOfferPasskey()) {
    offeringPasskey.value = true
    return
  }
  password.value = ''
  void router.push(postLoginTarget(route.query.redirect))
}

// The forced enrolment and the two-factor challenge both end the password
// sign-in once their code is accepted. The store flips the step flag before it
// returns, so the step is gone by then and cannot report success itself.
async function submitSecondFactor(submit: Promise<void>, step: { clear: () => void } | null) {
  try {
    await submit
  } catch {
    return step?.clear()
  }
  await finishLogin(false)
}
const onTotpSubmit = (code: string) => submitSecondFactor(authStore.submitTotp(code), totpStep.value)
const onEnrolmentSubmit = (code: string) =>
  submitSecondFactor(authStore.submitForcedEnrolment(code), totpSetupStep.value)

async function onAcceptPasskey() {
  const user = useCurrentUserStore().user
  if (!user) return

  passkeySetupLoading.value = true
  passkeySetupError.value = null
  try {
    await setUpPasskeyOnThisDevice(
      password.value,
      t(`login.passkey.deviceName.${authenticatorKind}`),
      user,
    )
    onLeaveOffer()
  } catch (e) {
    passkeySetupError.value = passkeyPromptDismissed(e)
      ? t('login.passkey.offer.dismissed')
      : t('login.passkey.offer.failed')
  } finally {
    passkeySetupLoading.value = false
  }
}

function onDeclinePasskey() {
  const user = useCurrentUserStore().user
  if (user) updateRememberedUser(user.username, { passkeyDeclined: true })
  onLeaveOffer()
}

function onLeaveOffer() {
  offeringPasskey.value = false
  password.value = ''
  void router.push(postLoginTarget(route.query.redirect))
}

// ── Credentials ──────────────────────────────────────────────────────────────

const totpStep = ref<InstanceType<typeof LoginTotpStep> | null>(null)
const totpSetupStep = ref<InstanceType<typeof LoginTotpSetupStep> | null>(null)

function onStepEnter() {
  if (authStore.totpRequired) totpStep.value?.focus()
}

// Empty fields would get an unmapped 422 from the backend instead of a 401,
// so they are never submitted.
const canSubmit = computed(() => username.value.trim() !== '' && password.value !== '')

async function onSubmit() {
  if (!canSubmit.value) return

  sessionExpired.value = false
  maintenanceLockoutReason.value = false

  try {
    await authStore.login({ username: username.value, password: password.value })

    // The 2FA challenge and forced enrolment continue on this page; navigating
    // without a session would bounce off the router guard.
    if (!authStore.totpRequired && !authStore.totpSetupRequired) {
      await finishLogin(false)
    }
  } catch {
    // error surfaced via authStore.error / errorMessage
  }
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card">
      <span class="brand-name">Glados</span>
      <hr class="brand-divider" />

      <div class="step-container">
        <Transition name="step" mode="out-in" @after-enter="onStepEnter">
          <LoginPasskeyOffer
            v-if="offeringPasskey"
            key="passkey-offer"
            :authenticator-kind="authenticatorKind"
            :loading="passkeySetupLoading"
            :error="passkeySetupError"
            @accept="onAcceptPasskey"
            @decline="onDeclinePasskey"
          />

          <div
            v-else-if="
              selectedUser && !switchingUser && !authStore.totpRequired && !authStore.totpSetupRequired
            "
            key="chooser"
            class="login-form"
          >
            <LoginMaintenanceBanner />

            <RememberedUserHeader :user="selectedUser" />

            <form v-if="askPassword" class="login-form" @submit.prevent="onChooserPasswordSubmit">
              <p v-if="chooserHint" class="totp-description">{{ chooserHint }}</p>

              <div class="field">
                <label for="login-chooser-password">{{ t('login.password') }}</label>
                <Password
                  id="login-chooser-password"
                  v-model="password"
                  :feedback="false"
                  toggle-mask
                  autofocus
                  autocomplete="current-password"
                  input-class="w-full"
                />
              </div>

              <Message v-if="passkeyErrorMessage || errorMessage" severity="error" :closable="false">
                {{ errorMessage || passkeyErrorMessage }}
              </Message>

              <Button
                type="submit"
                :label="t('login.submit')"
                :loading="authStore.loading"
                :disabled="password === ''"
                class="login-submit"
              />
            </form>

            <template v-else>
              <Message v-if="errorMessage" severity="error" :closable="false">
                {{ errorMessage }}
              </Message>

              <Button
                type="button"
                :label="t('login.submit')"
                :icon="selectedUsesPasskey ? 'mdi mdi-fingerprint' : undefined"
                :loading="authStore.loading"
                class="login-submit"
                data-testid="login-chooser-sign-in"
                @click="onChooserSignIn"
              />
            </template>

            <div class="chooser-actions">
              <button
                type="button"
                class="back-btn"
                :disabled="authStore.loading"
                data-testid="login-switch-user"
                @click="onSwitchUser"
              >
                <span class="mdi mdi-account-switch" />
                {{ t('login.chooser.switchUser') }}
              </button>
              <button
                type="button"
                class="back-btn"
                :disabled="authStore.loading"
                data-testid="login-forget-user"
                @click="onForgetUser"
              >
                <span class="mdi mdi-account-remove" />
                {{ t('login.chooser.forget') }}
              </button>
            </div>

            <OtherRememberedUsers
              :users="otherRememberedUsers"
              :disabled="authStore.loading"
              @select="onSelectRemembered"
            />
          </div>

          <form
            v-else-if="!authStore.totpRequired && !authStore.totpSetupRequired"
            key="credentials"
            class="login-form"
            @submit.prevent="onSubmit"
          >
            <LoginMaintenanceBanner />

            <div class="field">
              <label for="login-username">{{ t('login.username') }}</label>
              <InputText id="login-username" v-model="username" autofocus autocomplete="username" />
            </div>

            <div class="field">
              <label for="login-password">{{ t('login.password') }}</label>
              <Password
                id="login-password"
                v-model="password"
                :feedback="false"
                toggle-mask
                autocomplete="current-password"
                input-class="w-full"
              />
            </div>

            <Message v-if="errorMessage" severity="error" :closable="false">
              {{ errorMessage }}
            </Message>

            <Message v-if="passkeyErrorMessage" severity="error" :closable="false">
              {{ passkeyErrorMessage }}
            </Message>

            <Button
              type="submit"
              :label="t('login.submit')"
              :loading="authStore.loading"
              :disabled="!canSubmit"
              class="login-submit"
            />

            <button
              v-if="passkeysUsable"
              type="button"
              class="back-btn"
              :disabled="authStore.loading"
              data-testid="login-passkey-sign-in"
              @click="onPasskeySignIn"
            >
              <span class="mdi mdi-fingerprint" />
              {{ t('login.passkey.signIn') }}
            </button>

            <button
              v-if="rememberedUsers.length > 0"
              type="button"
              class="back-btn"
              :disabled="authStore.loading"
              @click="onBackToChooser"
            >
              <span class="mdi mdi-arrow-left" />
              {{ t('login.totp.back') }}
            </button>
          </form>

          <LoginTotpSetupStep
            v-else-if="authStore.totpSetupRequired"
            key="totp-setup"
            ref="totpSetupStep"
            @submit="onEnrolmentSubmit"
          />

          <LoginTotpStep v-else key="totp" ref="totpStep" @submit="onTotpSubmit" />
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
// This screen deliberately does not participate in app theming (no
// --p-surface-*/--p-primary-* dark-mode variables): it renders before a
// user session exists, so there is no user preference to read yet, and it
// always shows this same fixed dark card over the animated backdrop.
.login-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  animation: appear 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

// ── Card ─────────────────────────────────────────────────────────────────────

.login-card {
  position: relative;
  width: 22rem;
  padding: var(--space-6) var(--space-6) var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);

  background: var(--auth-card);
  backdrop-filter: blur(32px) saturate(1.6);
  -webkit-backdrop-filter: blur(32px) saturate(1.6);
  border-radius: 18px;
  box-shadow: var(--auth-card-shadow);
}

// ── Brand ─────────────────────────────────────────────────────────────────────

.brand-name {
  font-family: var(--font-brand);
  font-size: var(--font-size-4xl);
  letter-spacing: 0.03em;
  text-align: center;
  background: var(--auth-ink);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-divider {
  border: none;
  height: 1px;
  margin: 0;
  background: linear-gradient(90deg, transparent, var(--auth-line), transparent);
}

// ── Form ──────────────────────────────────────────────────────────────────────

// The passkey offer and the two-factor steps are child components, so the
// card's form styles reach into the steps rather than stopping at this
// component's own elements.
.step-container {
  min-height: 15rem;

  :deep(.login-form) {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  :deep(.totp-form) {
    align-items: stretch;
  }

  :deep(.field) {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  :deep(.field label) {
    font-family: 'Play', sans-serif;
    font-size: var(--font-size-xs);
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--auth-text);
  }

  /* stylelint-disable selector-disallowed-list -- the sign-in screen draws its own input skin, with hover and focus states the input tokens cannot express */
  :deep(.field .p-password),
  :deep(.field .p-inputtext) {
    width: 100%;
  }

  // ── Inputs ──────────────────────────────────────────────────────────────────

  :deep(.field .p-inputtext) {
    background: var(--auth-field) !important;
    border: 1px solid var(--auth-line) !important;
    border-radius: 9px !important;
    color: var(--auth-text-strong) !important;
    padding: var(--space-2) var(--space-3) !important;
    transition:
      border-color 0.18s ease,
      box-shadow 0.18s ease,
      background 0.18s ease;

    &::placeholder {
      color: var(--auth-text-faint);
    }

    &:hover {
      background: var(--auth-field-hover) !important;
      border-color: var(--auth-hover-border) !important;
    }

    &:focus {
      background: var(--auth-focus-fill) !important;
      border-color: var(--auth-focus-border) !important;
      box-shadow: var(--auth-focus-glow) !important;
    }
  }

  // ── TOTP inputs ─────────────────────────────────────────────────────────────

  :deep(.totp-otp-field) {
    align-items: center;
  }

  :deep(.trust-device-field) {
    flex-direction: row;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
  }

  :deep(.trust-device-field label) {
    margin: 0;
    color: var(--auth-text);
    font-size: var(--font-size-sm);
    cursor: pointer;
  }

  :deep(.totp-description) {
    margin: 0;
    color: var(--auth-text);
    font-size: var(--font-size-sm);
    line-height: 1.6;
    text-align: center;
  }

  :deep(.p-inputotp .p-inputotp-input) {
    background: var(--auth-field) !important;
    border: 1px solid var(--auth-line) !important;
    border-radius: 9px !important;
    color: var(--auth-text-strong) !important;
    font-size: var(--font-size-lg);
    transition:
      border-color 0.18s ease,
      box-shadow 0.18s ease;

    &:focus {
      background: var(--auth-focus-fill) !important;
      border-color: var(--auth-focus-border) !important;
      box-shadow: var(--auth-focus-glow) !important;
    }
  }
  /* stylelint-enable selector-disallowed-list */

  // ── Submit button ───────────────────────────────────────────────────────────

  :deep(.login-submit) {
    position: relative;
    overflow: hidden;
    margin-top: var(--space-1);
    border-radius: 9px !important;
    background: var(--auth-accent) !important;
    border: none !important;
    color: var(--on-accent) !important;
    font-family: 'Play', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.07em !important;
    box-shadow: var(--auth-submit-shadow);
    transition:
      background 0.18s ease,
      box-shadow 0.18s ease,
      transform 0.14s ease !important;

    // shimmer sweep
    &::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(
        105deg,
        transparent 30%,
        var(--auth-sheen) 50%,
        transparent 70%
      );
      transform: translateX(-100%);
      transition: transform 0.55s ease;
    }

    &:hover:not(:disabled) {
      background: var(--auth-accent-hover) !important;
      box-shadow: var(--auth-submit-shadow-hover);
      transform: translateY(-1px);

      &::after {
        transform: translateX(100%);
      }
    }

    &:active:not(:disabled) {
      background: var(--auth-accent-active) !important;
      transform: translateY(0);
      box-shadow: var(--auth-submit-shadow-active);
    }
  }

  // ── Back button ─────────────────────────────────────────────────────────────

  :deep(.back-btn) {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-1);
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--auth-text-muted);
    font-size: var(--font-size-xs);
    font-family: inherit;
    letter-spacing: 0.03em;
    transition: color 0.15s ease;

    .mdi {
      font-size: var(--font-size-sm);
    }

    &:hover:not(:disabled) {
      color: var(--auth-text);
    }

    &:disabled {
      cursor: default;
    }
  }
}

// ── Remembered user ───────────────────────────────────────────────────────────

.chooser-actions {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
}

// ── Step transition ───────────────────────────────────────────────────────────

.step-enter-active,
.step-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}

.step-enter-from {
  opacity: 0;
  transform: translateX(16px);
}

.step-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}

// ── Entrance animation ────────────────────────────────────────────────────────

@keyframes appear {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
