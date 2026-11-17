import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'
import { extractApiError } from '@/core/utils/errors'
import { useUserManagementStore } from '../stores/userManagementStore'

import type { UserResponse } from '@/core/types/userResponse'

/**
 * The avatar field of the user dialog. An existing user's avatar uploads and
 * deletes at once; a new user's picked file is only previewed and staged in
 * `pendingAvatarFile`, which the dialog uploads after the account exists.
 */
export function useUserAvatar(user: () => UserResponse | undefined, displayName: () => string) {
  const { t } = useI18n()
  const toast = useAppToast()
  const managementStore = useUserManagementStore()
  const avatarsStore = useUserAvatarsStore()

  const avatarUrl = ref<string | null>(null) // server URL (edit mode)
  const pendingAvatarFile = ref<File | null>(null) // selected but not yet uploaded (create mode)
  const pendingAvatarPreviewUrl = ref<string | null>(null)
  const uploadingAvatar = ref(false)
  const deletingAvatar = ref(false)

  const displayAvatarUrl = computed(() => avatarUrl.value ?? pendingAvatarPreviewUrl.value)

  function getInitials(): string {
    return displayName()
      .split(' ')
      .map((p) => p[0] ?? '')
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  async function onAvatarSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    input.value = ''

    const target = user()
    if (target) {
      uploadingAvatar.value = true
      try {
        const updated = await managementStore.uploadAvatar(target.id, file)
        avatarUrl.value = await avatarsStore.fetch(updated.id)
      } catch (e) {
        toast.error(
          target.username,
          extractApiError(e) ?? t('settings.users.errors.avatarUploadFailed'),
        )
      } finally {
        uploadingAvatar.value = false
      }
    } else {
      if (pendingAvatarPreviewUrl.value) URL.revokeObjectURL(pendingAvatarPreviewUrl.value)
      pendingAvatarFile.value = file
      pendingAvatarPreviewUrl.value = URL.createObjectURL(file)
    }
  }

  async function onDeleteAvatar(): Promise<void> {
    const target = user()
    if (target) {
      deletingAvatar.value = true
      try {
        await managementStore.deleteAvatar(target.id)
        avatarUrl.value = null
      } catch (e) {
        toast.error(
          target.username,
          extractApiError(e) ?? t('settings.users.errors.avatarDeleteFailed'),
        )
      } finally {
        deletingAvatar.value = false
      }
    } else {
      if (pendingAvatarPreviewUrl.value) URL.revokeObjectURL(pendingAvatarPreviewUrl.value)
      pendingAvatarFile.value = null
      pendingAvatarPreviewUrl.value = null
    }
  }

  function resetAvatarState(): void {
    avatarUrl.value = null
    if (pendingAvatarPreviewUrl.value) URL.revokeObjectURL(pendingAvatarPreviewUrl.value)
    pendingAvatarFile.value = null
    pendingAvatarPreviewUrl.value = null
  }

  return {
    avatarUrl,
    pendingAvatarFile,
    uploadingAvatar,
    deletingAvatar,
    displayAvatarUrl,
    getInitials,
    onAvatarSelected,
    onDeleteAvatar,
    resetAvatarState,
  }
}
