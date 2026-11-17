import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { extractApiError } from '@/core/utils/errors'
import { useUserManagementStore } from '../stores/userManagementStore'

import type { UserResponse } from '@/core/types/userResponse'

/**
 * The administrative resets the user dialog offers for a lost second factor:
 * the 2FA reset and the passkey reset. Both stay hidden for the system user
 * and for yourself, whose resets go through Account, Security. Without
 * write:settings they stay visible but disabled, naming the permission.
 */
export function useUserAccountResets(user: () => UserResponse | undefined) {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()
  const currentUserStore = useCurrentUserStore()
  const managementStore = useUserManagementStore()
  const confirm = useConfirm()
  const toast = useAppToast()

  const isOtherPerson = computed(() => {
    const target = user()
    return !!target && !target.is_systemuser && target.id !== currentUserStore.user?.id
  })

  // ── Two-factor authentication ──────────────────────────────────────────────

  const resettingTotp = ref(false)
  const offerResetTotp = computed(() => isOtherPerson.value && !!user()?.totp_enabled)
  const canResetTotp = computed(() => offerResetTotp.value && hasPermission(Permission.WRITE_SETTINGS))

  function onResetTotp() {
    const current = user()
    if (!current) return
    const target = current

    async function onAccept(): Promise<void> {
      resettingTotp.value = true
      try {
        await managementStore.resetTotp(target.id)
        toast.success(target.username, t('settings.users.resetTotpDone'))
      } catch (e) {
        toast.error(target.username, extractApiError(e) ?? undefined)
      } finally {
        resettingTotp.value = false
      }
    }

    confirm.require({
      header: t('settings.users.resetTotp'),
      message: t('settings.users.resetTotpConfirm', { name: target.username }),
      icon: 'mdi mdi-shield-off-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('settings.users.resetTotp'), severity: 'warn' },
      accept: () => void onAccept(),
    })
  }

  // ── Passkeys ───────────────────────────────────────────────────────────────

  // How many passkeys the edited user holds, known only to write:settings
  // holders, who are the ones allowed to read them.
  const passkeyCount = ref(0)
  const resettingPasskeys = ref(false)
  const mayResetPasskeys = computed(() => hasPermission(Permission.WRITE_SETTINGS))

  // Without write:settings whether the user has passkeys is unknown, so the
  // reset is offered disabled for every other person; with it, only while
  // the user has any.
  const offerResetPasskeys = computed(
    () => isOtherPerson.value && (!mayResetPasskeys.value || passkeyCount.value > 0),
  )

  async function loadPasskeyCount(): Promise<void> {
    passkeyCount.value = 0
    const target = user()
    if (!target || !mayResetPasskeys.value || target.is_systemuser) return
    if (target.id === currentUserStore.user?.id) return
    try {
      passkeyCount.value = await managementStore.countPasskeys(target.id)
    } catch {
      passkeyCount.value = 0
    }
  }

  function onResetPasskeys() {
    const current = user()
    if (!current) return
    const target = current

    async function onAccept(): Promise<void> {
      resettingPasskeys.value = true
      try {
        const removed = await managementStore.resetPasskeys(target.id)
        passkeyCount.value = 0
        toast.success(target.username, t('settings.users.resetPasskeysDone', { count: removed }))
      } catch (e) {
        toast.error(target.username, extractApiError(e) ?? undefined)
      } finally {
        resettingPasskeys.value = false
      }
    }

    confirm.require({
      header: t('settings.users.resetPasskeys'),
      message: t('settings.users.resetPasskeysConfirm', {
        name: target.username,
        count: passkeyCount.value,
      }),
      icon: 'mdi mdi-fingerprint-off',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('settings.users.resetPasskeys'), severity: 'warn' },
      accept: () => void onAccept(),
    })
  }

  return {
    resettingTotp,
    offerResetTotp,
    canResetTotp,
    onResetTotp,
    resettingPasskeys,
    mayResetPasskeys,
    offerResetPasskeys,
    loadPasskeyCount,
    onResetPasskeys,
  }
}
