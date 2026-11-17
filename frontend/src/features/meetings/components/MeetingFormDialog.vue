<script setup lang="ts">
import { computed, reactive, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { instantToPickerDate, pickerDateToInstant, toLocalDayStart } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { createMeeting, updateMeeting } from '../api/meetingsApi'
import { attendeeKey, attendeeRequest, draftFromAttendee } from '../utils/attendees'
import type { AttendeeDraft } from '../utils/attendees'
import { TAG_MAX, TAGS_MAX } from '../utils/meetingTags'
import MeetingAttendeePicker from './MeetingAttendeePicker.vue'
import MeetingTagInput from './MeetingTagInput.vue'
import type { MeetingResponse } from '../types/meetingResponse'

/**
 * Creates a meeting of a project or a product, or edits one: its name, date
 * and times, location, tags, the next meeting as agreed, and the attendees
 * with their status. A new meeting starts with the current user as attendee.
 */
const props = defineProps<{
  /** The meeting to edit; without it the dialog creates one for the owner. */
  meeting?: MeetingResponse | null
  ownerKind?: 'project' | 'product'
  ownerId?: number
}>()

const emit = defineEmits<{ saved: [meeting: MeetingResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const uid = useId()
const toast = useAppToast()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canWrite = computed(() => hasPermission(Permission.WRITE_MEETINGS))
const isEdit = computed(() => !!props.meeting)

interface Form {
  name: string
  date: Date | null
  start: Date | null
  end: Date | null
  location: string
  tags: string[]
  nextDate: Date | null
  nextTime: Date | null
  nextLocation: string
  attendees: AttendeeDraft[]
}

const form = reactive<Form>({
  name: '',
  date: null,
  start: null,
  end: null,
  location: '',
  tags: [],
  nextDate: null,
  nextTime: null,
  nextLocation: '',
  attendees: [],
})
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref('')

function clock(hours: number, minutes = 0): Date {
  const date = new Date()
  date.setHours(hours, minutes, 0, 0)
  return date
}

function wallTime(value: string): Date {
  const [hours, minutes] = value.split(':').map(Number)
  return clock(hours ?? 0, minutes ?? 0)
}

function reset(): void {
  submitted.value = false
  errorMessage.value = ''
  const meeting = props.meeting
  if (meeting) {
    const starts = instantToPickerDate(meeting.starts_at)
    form.name = meeting.name
    form.date = starts
    form.start = starts
    form.end = instantToPickerDate(meeting.ends_at)
    form.location = meeting.location ?? ''
    form.tags = [...meeting.tags]
    form.nextDate = meeting.next_meeting_date ? toLocalDayStart(meeting.next_meeting_date) : null
    form.nextTime = meeting.next_meeting_time ? wallTime(meeting.next_meeting_time) : null
    form.nextLocation = meeting.next_meeting_location ?? ''
    form.attendees = meeting.attendees.map(draftFromAttendee)
    return
  }
  const user = currentUserStore.user
  form.name = ''
  form.date = instantToPickerDate(new Date())
  form.start = clock(9)
  form.end = clock(10)
  form.location = ''
  form.tags = []
  form.nextDate = null
  form.nextTime = null
  form.nextLocation = ''
  form.attendees = user
    ? [
        {
          key: attendeeKey('user', user.id),
          kind: 'user',
          status: 'present',
          userId: user.id,
          contactId: null,
          attendeeId: null,
          name: user.full_name,
          email: null,
          detail: null,
        },
      ]
    : []
}

watch(visible, (open) => {
  if (open) reset()
})

function at(day: Date, time: Date): Date {
  const combined = new Date(day)
  combined.setHours(time.getHours(), time.getMinutes(), 0, 0)
  return pickerDateToInstant(combined)
}

function dateKey(day: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

function timeKey(time: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(time.getHours())}:${pad(time.getMinutes())}:00`
}

const nameError = computed(() => (submitted.value && !form.name.trim() ? t('meetings.form.nameRequired') : ''))
const timeError = computed(() => {
  if (!submitted.value) return ''
  if (!form.date || !form.start || !form.end) return t('meetings.form.timesRequired')
  return at(form.date, form.end) < at(form.date, form.start) ? t('meetings.form.endBeforeStart') : ''
})

const tagsError = computed(() => {
  if (!submitted.value) return ''
  if (form.tags.length > TAGS_MAX) return t('meetings.form.tagsTooMany', { max: TAGS_MAX })
  return form.tags.some((tag) => tag.length > TAG_MAX) ? t('meetings.form.tagTooLong', { max: TAG_MAX }) : ''
})

const tagInput = useTemplateRef<{ commitPending: () => void }>('tagInput')

async function onSave(): Promise<void> {
  tagInput.value?.commitPending()
  submitted.value = true
  if (nameError.value || timeError.value || tagsError.value || !form.date || !form.start || !form.end) return
  saving.value = true
  errorMessage.value = ''
  const fields = {
    name: form.name.trim(),
    starts_at: at(form.date, form.start).toISOString(),
    ends_at: at(form.date, form.end).toISOString(),
    location: form.location.trim() || null,
    tags: [...form.tags],
    next_meeting_date: form.nextDate ? dateKey(form.nextDate) : null,
    next_meeting_time: form.nextDate && form.nextTime ? timeKey(form.nextTime) : null,
    next_meeting_location: form.nextDate ? form.nextLocation.trim() || null : null,
    attendees: form.attendees.map(attendeeRequest),
  }
  try {
    const saved = props.meeting
      ? await updateMeeting(props.meeting.id, { ...fields, expected_edit_version: props.meeting.edit_version })
      : await createMeeting({
          ...fields,
          ...(props.ownerKind === 'product' ? { product_id: props.ownerId } : { project_id: props.ownerId }),
        })
    toast.success(saved.meeting_number, t(isEdit.value ? 'meetings.toasts.saved' : 'meetings.toasts.created'))
    visible.value = false
    emit('saved', saved)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    saving.value = false
  }
}

const header = computed(() => (isEdit.value ? t('meetings.form.editTitle') : t('meetings.form.newTitle')))
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-md)' }">
    <div class="dialog-body">
      <fieldset class="dialog-section">
        <legend>{{ t('meetings.form.sections.meeting') }}</legend>
        <div class="field">
          <label :for="`${uid}-name`">{{ t('meetings.form.name') }} *</label>
          <InputText
            :id="`${uid}-name`"
            v-model="form.name"
            :invalid="!!nameError"
            maxlength="200"
            autocomplete="off"
            fluid
            data-testid="meeting-form-name"
          />
          <small v-if="nameError" class="field-error">{{ nameError }}</small>
        </div>
        <div class="times-grid">
          <div class="field">
            <label :for="`${uid}-date`">{{ t('meetings.form.date') }} *</label>
            <DatePicker v-model="form.date" :input-id="`${uid}-date`" show-icon fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-start`">{{ t('meetings.form.start') }} *</label>
            <DatePicker v-model="form.start" :input-id="`${uid}-start`" time-only hour-format="24" fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-end`">{{ t('meetings.form.end') }} *</label>
            <DatePicker v-model="form.end" :input-id="`${uid}-end`" time-only hour-format="24" fluid />
          </div>
        </div>
        <small v-if="timeError" class="field-error">{{ timeError }}</small>
        <div class="field">
          <label :for="`${uid}-location`">{{ t('meetings.form.location') }}</label>
          <InputText
            :id="`${uid}-location`"
            v-model="form.location"
            maxlength="200"
            :placeholder="t('meetings.form.locationPlaceholder')"
            fluid
          />
        </div>
        <div class="field">
          <label :for="`${uid}-tags`">{{ t('meetings.form.tags') }}</label>
          <MeetingTagInput
            ref="tagInput"
            v-model="form.tags"
            :input-id="`${uid}-tags`"
            :invalid="!!tagsError"
            :placeholder="t('meetings.form.tagsPlaceholder')"
          />
          <small v-if="tagsError" class="field-error">{{ tagsError }}</small>
          <small v-else class="hint">{{ t('meetings.form.tagsHint', { max: TAGS_MAX }) }}</small>
        </div>
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('meetings.form.sections.attendees') }}</legend>
        <MeetingAttendeePicker v-model="form.attendees" />
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('meetings.form.sections.next') }}</legend>
        <div class="times-grid">
          <div class="field">
            <label :for="`${uid}-next-date`">{{ t('meetings.form.nextDate') }}</label>
            <DatePicker v-model="form.nextDate" :input-id="`${uid}-next-date`" show-icon show-clear fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-next-time`">{{ t('meetings.form.nextTime') }}</label>
            <DatePicker
              v-model="form.nextTime"
              :input-id="`${uid}-next-time`"
              time-only
              hour-format="24"
              :disabled="!form.nextDate"
              fluid
            />
          </div>
        </div>
        <div class="field">
          <label :for="`${uid}-next-location`">{{ t('meetings.form.nextLocation') }}</label>
          <InputText
            :id="`${uid}-next-location`"
            v-model="form.nextLocation"
            maxlength="200"
            :disabled="!form.nextDate"
            fluid
          />
          <small class="hint">{{ t('meetings.form.nextHint') }}</small>
        </div>
      </fieldset>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <span v-tooltip.top="missing(Permission.WRITE_MEETINGS) || undefined">
        <Button
          type="button"
          :label="isEdit ? t('meetings.form.save') : t('meetings.form.create')"
          :icon="isEdit ? 'mdi mdi-check' : 'mdi mdi-plus'"
          :loading="saving"
          :disabled="!canWrite"
          data-testid="meeting-form-save"
          @click="onSave"
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

.times-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
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
