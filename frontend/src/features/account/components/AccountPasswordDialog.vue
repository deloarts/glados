<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiErrorCode } from '@/core/utils/errors'
import { updateCurrentUser } from '../api/updateCurrentUser'

/**
 * Changes the signed-in user's own password. The current password proves it
 * is the account's owner changing it, not someone who found the session
 * open, so the backend refuses the change without it.
 */
const visible = defineModel<boolean>('visible', { required: true })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()

const form = reactive({ currentPassword: '', password: '', confirmPassword: '' })
const saving = ref(false)

watch(visible, (open) => {
  if (!open) return
  form.currentPassword = ''
  form.password = ''
  form.confirmPassword = ''
})

/** The translated reason a password change failed, matched on the error code. */
function changeError(err: unknown): string {
  switch (extractApiErrorCode(err)) {
    case 'PasswordConfirmationFailedError':
      return t('accountMe.errors.currentPasswordWrong')
    case 'CurrentPasswordRequiredError':
      return t('accountMe.errors.currentPasswordEmpty')
    case 'LoginLockedError':
      return t('accountMe.errors.tooManyAttempts')
    default:
      return t('accountMe.errors.unknown')
  }
}

async function onChange(): Promise<void> {
  if (!form.currentPassword) {
    appToast.warn(t('accountMe.errors.currentPasswordEmpty'))
    return
  }
  if (!form.password) {
    appToast.warn(t('accountMe.errors.passwordEmpty'))
    return
  }
  if (form.password !== form.confirmPassword) {
    appToast.warn(t('accountMe.errors.passwordMismatch'))
    return
  }
  saving.value = true
  try {
    await updateCurrentUser({ password: form.password, current_password: form.currentPassword })
    visible.value = false
    appToast.success(t('accountMe.passwordChanged'))
  } catch (err) {
    appToast.error(changeError(err))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :header="t('accountMe.password.dialogTitle')"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="settings-fields">
      <div class="field-row field-row--dialog">
        <label :for="`${uid}-current-password`">{{ t('accountMe.password.currentPassword') }}</label>
        <InputText
          v-model="form.currentPassword"
          :id="`${uid}-current-password`"
          type="password"
          autocomplete="current-password"
          data-testid="account-current-password"
        />
      </div>
      <div class="field-row field-row--dialog">
        <label :for="`${uid}-new-password`">{{ t('accountMe.password.newPassword') }}</label>
        <InputText v-model="form.password" :id="`${uid}-new-password`" type="password" autocomplete="new-password" />
      </div>
      <div class="field-row field-row--dialog">
        <label :for="`${uid}-confirm-password`">{{ t('accountMe.password.confirmPassword') }}</label>
        <InputText
          v-model="form.confirmPassword"
          :id="`${uid}-confirm-password`"
          type="password"
          autocomplete="new-password"
        />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="contrast" text @click="visible = false" />
      <Button
        :label="t('accountMe.password.change')"
        icon="mdi mdi-lock-reset"
        :loading="saving"
        @click="onChange"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.field-row--dialog {
  grid-template-columns: 10rem 1fr;
}
</style>
