<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { invalidateMeeting, restoreMeeting } from '../api/meetingsApi'
import type { MeetingResponse } from '../types/meetingResponse'

/**
 * Marks a meeting invalid with a reason, which turns its notes read-only and
 * takes its open todos off the todo page, or restores an invalid meeting
 * with an optional note. Both need manage:meetings and land in the
 * meeting's history.
 */
const props = defineProps<{ meeting: MeetingResponse; mode: 'invalidate' | 'restore' }>()
const emit = defineEmits<{ saved: [meeting: MeetingResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const uid = useId()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const text = ref('')
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref('')

const canManage = computed(() => hasPermission(Permission.MANAGE_MEETINGS))
const invalidating = computed(() => props.mode === 'invalidate')
const reasonError = computed(() =>
  invalidating.value && submitted.value && !text.value.trim() ? t('meetings.validity.reasonRequired') : '',
)

watch(visible, (open) => {
  if (!open) return
  text.value = ''
  submitted.value = false
  errorMessage.value = ''
})

async function onConfirm(): Promise<void> {
  submitted.value = true
  if (reasonError.value) return
  saving.value = true
  errorMessage.value = ''
  try {
    const saved = invalidating.value
      ? await invalidateMeeting(props.meeting.id, text.value.trim())
      : await restoreMeeting(props.meeting.id, text.value.trim() || null)
    toast.success(
      saved.meeting_number,
      invalidating.value ? t('meetings.validity.invalidated') : t('meetings.validity.restored'),
    )
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="invalidating ? t('meetings.validity.invalidateTitle') : t('meetings.validity.restoreTitle')"
    :style="{ width: 'var(--dialog-width-sm)' }"
    data-testid="meeting-validity-dialog"
  >
    <div class="dialog-body">
      <p class="intro">
        {{ invalidating ? t('meetings.validity.invalidateIntro') : t('meetings.validity.restoreIntro') }}
      </p>
      <div class="field">
        <label :for="`${uid}-text`">
          {{ invalidating ? t('meetings.validity.reason') : t('meetings.validity.note') }}
        </label>
        <Textarea
          :id="`${uid}-text`"
          v-model="text"
          rows="3"
          auto-resize
          maxlength="1000"
          :invalid="!!reasonError"
          :placeholder="invalidating ? t('meetings.validity.reasonPlaceholder') : t('meetings.validity.notePlaceholder')"
          fluid
          data-testid="meeting-validity-text"
        />
        <small v-if="reasonError" class="field-error">{{ reasonError }}</small>
      </div>
    </div>
    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button :label="t('common.cancel')" severity="secondary" text :disabled="saving" @click="visible = false" />
      <span v-tooltip.top="missing(Permission.MANAGE_MEETINGS) || undefined">
        <Button
          :label="invalidating ? t('meetings.markInvalid') : t('meetings.restore')"
          :icon="invalidating ? 'mdi mdi-cancel' : 'mdi mdi-restore'"
          :severity="invalidating ? 'danger' : undefined"
          :loading="saving"
          :disabled="!canManage"
          data-testid="meeting-validity-confirm"
          @click="onConfirm"
        />
      </span>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.intro {
  margin: 0;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}
</style>
