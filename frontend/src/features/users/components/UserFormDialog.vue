<script setup lang="ts">
import { extractApiError, extractApiErrorCode } from '@/core/utils/errors'
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useHostStore } from '@/core/host/stores/hostStore'
import { localeEndonym } from '@/core/i18n/localeMessages'
import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { useUserManagementStore } from '../stores/userManagementStore'
import { useUserGroupsStore } from '../stores/userGroupsStore'
import { useUserAccountResets } from '../composables/useUserAccountResets'
import { useUserAvatar } from '../composables/useUserAvatar'
import { useThemeOptions } from '../composables/useThemeOptions'
import UserPermissionsPanel from './UserPermissionsPanel.vue'
import UserThemeFields from './UserThemeFields.vue'
import UserAvatarField from './UserAvatarField.vue'
import { createEmptyUserForm, userFormFromUser, type UserFormState } from '../utils/userFormState'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { AUTH_PROVIDERS } from '@/core/auth/authProviders'
import type { Schemas } from '@/core/api/generated'

import type { UserResponse } from '@/core/types/userResponse'

interface Props {
  user?: UserResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [user: UserResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const usersStore = useUsersStore()
const managementStore = useUserManagementStore()
const groupsStore = useUserGroupsStore()
const avatarsStore = useUserAvatarsStore()
const hostStore = useHostStore()
const { presetOptions, filteredPrimaryColors, filteredSurfaces } = useThemeOptions()

const isEditMode = computed(() => !!props.user)

const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const confirm = useConfirm()
const toast = useAppToast()
const { missing } = useMissingPermission()
const writeSettingsBlocked = computed(() => missing(Permission.WRITE_SETTINGS))

// The 2FA and passkey resets for a lost second factor.
const {
  resettingTotp,
  offerResetTotp,
  canResetTotp,
  onResetTotp,
  resettingPasskeys,
  mayResetPasskeys,
  offerResetPasskeys,
  loadPasskeyCount,
  onResetPasskeys,
} = useUserAccountResets(() => props.user)

// ── Time tracking credentials ────────────────────────────────────────────────

/**
 * Set when a save was refused because the user still has stored time
 * tracking credentials, which a shared account cannot hold. Holders of
 * write:settings may remove them from here and save again.
 */
const timeTrackingBlocked = ref(false)
const removingTimeTracking = ref(false)

const canRemoveTimeTracking = computed(
  () => isEditMode.value && hasPermission(Permission.WRITE_SETTINGS),
)

function onTimeTrackingNotAllowed(): void {
  timeTrackingBlocked.value = true
  const detail = canRemoveTimeTracking.value
    ? t('settings.users.timeTrackingNotAllowedDetail')
    : t('settings.users.timeTrackingNotAllowedNoPermission')
  errorMessage.value = detail
  toast.error(t('settings.users.timeTrackingNotAllowed'), detail)
}

function onRemoveTimeTracking(): void {
  if (!props.user) return
  const target = props.user

  async function onAccept(): Promise<void> {
    removingTimeTracking.value = true
    try {
      await managementStore.removeTimeTrackingCredentials(target.id)
      timeTrackingBlocked.value = false
      errorMessage.value = null
      toast.success(target.username, t('settings.users.removeTimeTrackingDone'))
    } catch (e) {
      toast.error(target.username, extractApiError(e) ?? undefined)
    } finally {
      removingTimeTracking.value = false
    }
  }

  confirm.require({
    header: t('settings.users.removeTimeTracking'),
    message: t('settings.users.removeTimeTrackingConfirm', { name: target.username }),
    icon: 'mdi mdi-clock-remove-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('settings.users.removeTimeTracking'), severity: 'warn' },
    accept: () => void onAccept(),
  })
}

// ── Avatar ───────────────────────────────────────────────────────────────────

const {
  avatarUrl,
  pendingAvatarFile,
  uploadingAvatar,
  deletingAvatar,
  displayAvatarUrl,
  getInitials,
  onAvatarSelected,
  onDeleteAvatar,
  resetAvatarState,
} = useUserAvatar(
  () => props.user,
  () =>
    isEditMode.value
      ? (props.user?.full_name ?? props.user?.username ?? '')
      : form.full_name || form.username,
)

const authProviderOptions = computed(() =>
  AUTH_PROVIDERS.map((value) => ({
    value,
    label: t(`settings.users.authProviders.${value}`),
  })),
)

const languageOptions = [
  { label: localeEndonym('enGB', true), value: 'enGB' },
  { label: localeEndonym('deAT', true), value: 'deAT' },
]

const form = reactive<UserFormState>(createEmptyUserForm(hostStore.defaultLanguage))
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

/**
 * A directory account has no local password, so the field is hidden.
 */
const isLdap = computed(() => form.auth_provider === 'ldap')

/**
 * Required for a local account without a usable hash: a new account, or one
 * moved off the directory, which could otherwise not sign in.
 */
const passwordRequired = computed(
  () => !isLdap.value && (!isEditMode.value || props.user?.auth_provider === 'ldap'),
)

/**
 * Changing your own password here, as anywhere, needs the current one, so
 * its field appears once a new password is typed into your own account.
 * An administrator setting someone else's password is not asked.
 */
const currentPassword = ref('')
const needsCurrentPassword = computed(
  () =>
    isEditMode.value &&
    props.user?.id === currentUserStore.user?.id &&
    !isLdap.value &&
    form.password.trim() !== '',
)

watch(visible, (isVisible) => {
  if (!isVisible) return

  errorMessage.value = null
  timeTrackingBlocked.value = false
  currentPassword.value = ''
  void loadPasskeyCount()

  void usersStore.ensureLoaded()
  void groupsStore.ensureLoaded()

  if (props.user) {
    Object.assign(form, userFormFromUser(props.user))
    resetAvatarState()
    // A failed fetch keeps the placeholder avatar, the rest of the form
    // does not depend on it.
    if (props.user.has_avatar) {
      avatarsStore
        .fetch(props.user.id)
        .then((url) => {
          avatarUrl.value = url
        })
        .catch(() => {})
    }
  } else {
    Object.assign(form, {
      ...createEmptyUserForm(hostStore.defaultLanguage),
      theme_preset: presetOptions.value[0] ?? null,
      theme_primary: filteredPrimaryColors.value[0]?.name ?? null,
      theme_surface: filteredSurfaces.value[0]?.name ?? null,
    })
    resetAvatarState()
  }
})

// A shared account's member list only means something while the toggle is on.
watch(
  () => form.is_shared_account,
  (val) => {
    if (!val) form.member_ids = []
  },
)

const memberOptions = computed(() =>
  usersStore.users.filter((u) => u.is_active && !u.is_shared_account && u.id !== props.user?.id),
)

// The system user passes every check and a service account takes its
// permissions from its API key, so neither joins a group. Nobody changes
// their own groups either; the backend keeps them as they are.
const groupsLocked = computed(
  () =>
    !!props.user &&
    (props.user.is_systemuser ||
      props.user.is_service_account ||
      props.user.id === currentUserStore.user?.id),
)

function isFormValid(): boolean {
  if (!form.username.trim() || !form.full_name.trim() || !form.email.trim()) return false
  if (passwordRequired.value && !form.password.trim()) return false
  if (form.is_shared_account && form.member_ids.length === 0) return false
  return true
}

async function onSubmit(): Promise<void> {
  if (form.is_shared_account && form.member_ids.length === 0) {
    errorMessage.value = t('settings.users.errors.membersRequired')
    return
  }
  if (!isFormValid()) {
    errorMessage.value = t('settings.users.errors.required')
    return
  }
  if (needsCurrentPassword.value && !currentPassword.value) {
    errorMessage.value = t('settings.users.errors.currentPasswordRequired')
    return
  }

  submitting.value = true
  errorMessage.value = null

  try {
    let saved: UserResponse

    if (isEditMode.value && props.user) {
      saved = await managementStore.update(props.user.id, {
        username: form.username.trim(),
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        // null means unchanged; a directory account never sends one.
        password: isLdap.value ? null : form.password.trim() || null,
        current_password: needsCurrentPassword.value ? currentPassword.value : null,
        is_active: form.is_active,
        is_shared_account: form.is_shared_account,
        auth_provider: form.auth_provider,
        member_ids: form.member_ids,
        group_ids: form.group_ids,
        permissions: form.permissions,
        // The pickers only offer server values from these closed vocabularies, so
        // the value is cast at this boundary.
        language: form.language as Schemas['Language'],
        date_format: (form.date_format || null) as Schemas['DateFormat'] | null,
        theme_preset: form.theme_preset as Schemas['ThemePreset'] | null,
        theme_primary: form.theme_primary as Schemas['ThemePrimary'] | null,
        theme_surface: form.theme_surface as Schemas['ThemeSurface'] | null,
        theme_dark_mode: form.theme_dark_mode,
      })
    } else {
      saved = await managementStore.create({
        username: form.username.trim(),
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: isLdap.value ? null : form.password.trim(),
        is_active: form.is_active,
        is_shared_account: form.is_shared_account,
        auth_provider: form.auth_provider,
        member_ids: form.member_ids,
        group_ids: form.group_ids,
        permissions: form.permissions,
        language: form.language as Schemas['Language'],
        date_format: (form.date_format || null) as Schemas['DateFormat'] | null,
        theme_preset: form.theme_preset as Schemas['ThemePreset'] | null,
        theme_primary: form.theme_primary as Schemas['ThemePrimary'] | null,
        theme_surface: form.theme_surface as Schemas['ThemeSurface'] | null,
        theme_dark_mode: form.theme_dark_mode,
      })

      if (pendingAvatarFile.value) {
        await managementStore.uploadAvatar(saved.id, pendingAvatarFile.value)
        resetAvatarState()
      }
    }

    visible.value = false
    emit('saved', saved)
  } catch (e) {
    const code = extractApiErrorCode(e)
    if (code === 'TimeTrackingCredentialsNotAllowedError') {
      onTimeTrackingNotAllowed()
    } else if (code === 'PasswordConfirmationFailedError') {
      errorMessage.value = t('settings.users.errors.currentPasswordWrong')
    } else if (code === 'LoginLockedError') {
      errorMessage.value = t('settings.users.errors.tooManyAttempts')
    } else {
      errorMessage.value = extractApiError(e) ?? t('settings.users.errors.unknown')
    }
  } finally {
    submitting.value = false
  }
}

function onCancel(): void {
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="isEditMode ? t('settings.users.editUser') : t('settings.users.createUser')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    :breakpoints="{ '70rem': '95vw' }"
  >
    <form class="user-form" @submit.prevent="onSubmit">
      <div class="form-layout">
        <div class="form-grid">
          <div class="field">
            <label for="u-username">{{ t('settings.users.fields.username') }} *</label>
            <InputText id="u-username" v-model="form.username" fluid autocomplete="off" />
          </div>

          <div class="field">
            <label for="u-full-name">{{ t('settings.users.fields.fullName') }} *</label>
            <InputText id="u-full-name" v-model="form.full_name" fluid />
          </div>

          <div class="field field-wide">
            <label for="u-email">{{ t('settings.users.fields.email') }} *</label>
            <InputText id="u-email" v-model="form.email" type="email" fluid autocomplete="off" />
          </div>

          <!-- The auth provider sits beside the password it governs; the explanation
               is a tooltip so both stay the same height. -->
          <div class="field">
            <label id="u-auth-provider-label" for="u-auth-provider">{{ t('settings.users.fields.authProvider') }}</label>
            <Select
              id="u-auth-provider"
              aria-labelledby="u-auth-provider-label"
              v-model="form.auth_provider"
              :options="authProviderOptions"
              option-label="label"
              option-value="value"
              :disabled="props.user?.is_systemuser"
              fluid
              v-tooltip.top="t('settings.users.fields.authProviderHint')"
            />
          </div>

          <div class="field">
            <label for="u-password">
              {{ t('settings.users.fields.password') }}
              <span v-if="passwordRequired"> *</span>
            </label>
            <Password
              v-if="!isLdap"
              id="u-password"
              v-model="form.password"
              :placeholder="isEditMode ? t('settings.users.fields.passwordHint') : ''"
              :feedback="false"
              toggle-mask
              fluid
            />
            <span v-else class="hint">{{ t('settings.users.fields.passwordLdapHint') }}</span>
          </div>

          <div v-if="needsCurrentPassword" class="field">
            <label for="u-current-password">
              {{ t('settings.users.fields.currentPassword') }} *
            </label>
            <Password
              id="u-current-password"
              v-model="currentPassword"
              :feedback="false"
              toggle-mask
              fluid
              data-testid="user-current-password"
            />
          </div>

          <!-- PDM user links, read-only; set only through the PDM settings' Match
               PDM Users dialog. One user may have several. -->
          <div v-if="isEditMode" id="u-pdm-links" class="field field-wide">
            <span class="field-caption">{{ t('settings.users.fields.pdmLinks') }}</span>
            <div v-if="props.user?.pdm_links?.length" class="pdm-links-list">
              <Tag
                v-for="link in props.user.pdm_links"
                :key="link.pdm_user_id"
                :value="`${link.pdm_username} (#${link.pdm_user_id})`"
                severity="secondary"
              />
            </div>
            <span v-else class="hint">{{ t('settings.users.fields.pdmLinksNone') }}</span>
          </div>

          <UserAvatarField
            :avatar-url="displayAvatarUrl"
            :initials="getInitials()"
            :uploading="uploadingAvatar"
            :deleting="deletingAvatar"
            @select="onAvatarSelected"
            @remove="onDeleteAvatar"
          />

          <div class="field">
            <label id="u-language-label" for="u-language">{{ t('settings.users.fields.language') }}</label>
            <Select
              id="u-language"
              aria-labelledby="u-language-label"
              v-model="form.language"
              :options="languageOptions"
              option-label="label"
              option-value="value"
              fluid
            />
          </div>

          <div class="field">
            <label id="u-date-format-label" for="u-date-format">{{ t('settings.users.fields.dateFormat') }}</label>
            <Select
              id="u-date-format"
              aria-labelledby="u-date-format-label"
              v-model="form.date_format"
              :options="hostStore.dateFormats"
              :placeholder="
                t('settings.users.fields.dateFormatPlaceholder', {
                  value: hostStore.defaultDateFormat,
                })
              "
              show-clear
              fluid
            />
          </div>

          <UserThemeFields
            v-model:preset="form.theme_preset"
            v-model:dark-mode="form.theme_dark_mode"
            v-model:primary="form.theme_primary"
            v-model:surface="form.theme_surface"
          />

          <div class="field toggles-row">
            <div class="toggle-item">
              <ToggleSwitch
                v-model="form.is_active"
                input-id="u-active"
                :disabled="props.user?.is_systemuser"
              />
              <label for="u-active">{{ t('settings.users.fields.active') }}</label>
            </div>

            <div class="toggle-item">
              <ToggleSwitch v-model="form.is_shared_account" input-id="u-shared-account" />
              <label for="u-shared-account">{{ t('settings.users.fields.sharedAccount') }}</label>
            </div>
          </div>

          <div v-if="form.is_shared_account" class="field field-wide">
            <label id="u-members-label" for="u-members"> {{ t('settings.users.fields.sharedAccountMembers') }} * </label>
            <MultiSelect
              id="u-members"
              aria-labelledby="u-members-label"
              v-model="form.member_ids"
              :options="memberOptions"
              option-label="full_name"
              option-value="id"
              :loading="managementStore.loading"
              :placeholder="t('settings.users.fields.sharedAccountMembersPlaceholder')"
              display="chip"
              filter
              fluid
            />
            <small class="hint">{{ t('settings.users.fields.sharedAccountMembersHint') }}</small>
          </div>

          <div class="field field-wide">
            <label id="u-groups-label" for="u-groups">{{ t('settings.users.fields.groups') }}</label>
            <MultiSelect
              id="u-groups"
              aria-labelledby="u-groups-label"
              v-model="form.group_ids"
              :options="groupsStore.items"
              option-label="name"
              option-value="id"
              :loading="groupsStore.loading"
              :disabled="groupsLocked"
              :placeholder="t('settings.users.fields.groupsPlaceholder')"
              display="chip"
              filter
              fluid
            />
            <small class="hint">
              {{
                groupsLocked
                  ? t('settings.users.fields.groupsLockedHint')
                  : t('settings.users.fields.groupsHint')
              }}
            </small>
          </div>
        </div>

        <!-- Permissions get their own column, since the list is long. -->
        <UserPermissionsPanel v-model:permissions="form.permissions" :group-ids="form.group_ids" />
      </div>

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <!-- An action on the account, so it sits with the buttons. -->
        <span v-if="offerResetTotp" v-tooltip.top="writeSettingsBlocked || undefined">
          <Button
            type="button"
            :label="t('settings.users.resetTotp')"
            icon="mdi mdi-shield-off-outline"
            severity="warn"
            outlined
            :disabled="!canResetTotp"
            :loading="resettingTotp"
            data-testid="user-reset-totp"
            @click="onResetTotp"
          />
        </span>
        <span
          v-if="offerResetPasskeys"
          v-tooltip.top="mayResetPasskeys ? null : t('settings.users.resetPasskeysNoPermission')"
        >
          <Button
            type="button"
            :label="t('settings.users.resetPasskeys')"
            icon="mdi mdi-fingerprint-off"
            severity="warn"
            outlined
            :disabled="!mayResetPasskeys"
            :loading="resettingPasskeys"
            data-testid="user-reset-passkeys"
            @click="onResetPasskeys"
          />
        </span>
        <span
          v-if="timeTrackingBlocked && isEditMode"
          v-tooltip.top="writeSettingsBlocked || undefined"
        >
          <Button
            type="button"
            :label="t('settings.users.removeTimeTracking')"
            icon="mdi mdi-clock-remove-outline"
            severity="warn"
            outlined
            :disabled="!canRemoveTimeTracking"
            :loading="removingTimeTracking"
            data-testid="user-remove-time-tracking"
            @click="onRemoveTimeTracking"
          />
        </span>
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          @click="onCancel"
          :disabled="submitting"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.user-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

// Fields left, permissions right; the panel takes the fields' height.
.form-layout {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-5);
}

.form-grid {
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
  align-content: start;
}

.field {
  label,
  .field-caption {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.field-wide {
  grid-column: 1 / -1;
}

.toggles-row {
  grid-column: 1 / -1;
  flex-direction: row;
  gap: var(--space-6);
}

.toggle-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    font-size: var(--font-size-sm);
    cursor: pointer;
  }
}

.pdm-links-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

// Single column; the permissions panel drops below the fields.
@media (max-width: $bp-lg) {
  .form-layout {
    grid-template-columns: 1fr;
  }
}

.system-note {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
