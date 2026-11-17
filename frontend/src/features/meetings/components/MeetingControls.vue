<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ShareButton from '@/shared/components/resource-view/ShareButton.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpButton } from '@/shared/help'
import type { MeetingResponse } from '../types/meetingResponse'

/**
 * The actions of the meeting page. Editing needs write:meetings, marking
 * invalid and restoring manage:meetings; without them the buttons stay
 * disabled and say why. An invalid meeting is read-only, so its editing
 * actions are not offered at all and Restore takes the place of Mark
 * Invalid. Print and Send are emitted for the page to carry out.
 */
const props = withDefaults(
  defineProps<{
    meeting: MeetingResponse | null
    /** Whether the page can print and send yet; until then the two stay disabled. */
    canDistribute?: boolean
    busy?: boolean
  }>(),
  { canDistribute: false, busy: false },
)

const emit = defineEmits<{
  back: []
  edit: []
  'add-card': []
  'add-file': []
  print: []
  send: []
  history: []
  invalidate: []
  restore: []
  'follow-up': []
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const valid = computed(() => props.meeting?.valid ?? false)
const canWrite = computed(() => hasPermission(Permission.WRITE_MEETINGS))
const canManage = computed(() => hasPermission(Permission.MANAGE_MEETINGS))
const writeBlocked = computed(() => missing(Permission.WRITE_MEETINGS))
const manageBlocked = computed(() => missing(Permission.MANAGE_MEETINGS))
const sendBlocked = computed(() => missing(Permission.WRITE_MEETINGS, Permission.SEND_MAIL))
const canSend = computed(() => canWrite.value && hasPermission(Permission.SEND_MAIL))
</script>

<template>
  <ControlsBar data-testid="meeting-controls">
    <template #start>
      <Button
        icon="mdi mdi-arrow-left"
        :label="t('meetings.back')"
        severity="contrast"
        text
        data-testid="meeting-back"
        @click="emit('back')"
      />
      <template v-if="meeting && valid">
        <span v-tooltip.bottom="writeBlocked || undefined">
          <Button
            icon="mdi mdi-pencil"
            :label="t('meetings.editMeeting')"
            severity="contrast"
            text
            :disabled="!canWrite"
            data-testid="meeting-edit"
            @click="emit('edit')"
          />
        </span>
        <span v-tooltip.bottom="writeBlocked || undefined">
          <Button
            icon="mdi mdi-card-plus-outline"
            :label="t('meetings.addCard')"
            severity="contrast"
            text
            :disabled="!canWrite || busy"
            data-testid="meeting-add-card"
            @click="emit('add-card')"
          />
        </span>
        <span v-tooltip.bottom="writeBlocked || undefined">
          <Button
            icon="mdi mdi-paperclip"
            :label="t('meetings.addFile')"
            severity="contrast"
            text
            :disabled="!canWrite"
            data-testid="meeting-add-file"
            @click="emit('add-file')"
          />
        </span>
      </template>
      <template v-if="meeting">
        <Divider layout="vertical" />
        <Button
          icon="mdi mdi-printer-outline"
          :label="t('meetings.print')"
          severity="contrast"
          text
          :disabled="!canDistribute"
          data-testid="meeting-print"
          @click="emit('print')"
        />
        <span v-if="valid" v-tooltip.bottom="sendBlocked || undefined">
          <Button
            icon="mdi mdi-email-fast-outline"
            :label="t('meetings.send')"
            severity="contrast"
            text
            :disabled="!canDistribute || !canSend"
            data-testid="meeting-send"
            @click="emit('send')"
          />
        </span>
        <Button
          icon="mdi mdi-history"
          :label="t('meetings.history.button')"
          severity="contrast"
          text
          data-testid="meeting-history"
          @click="emit('history')"
        />
        <span v-tooltip.bottom="manageBlocked || undefined">
          <Button
            v-if="valid"
            icon="mdi mdi-cancel"
            :label="t('meetings.markInvalid')"
            severity="contrast"
            text
            :disabled="!canManage"
            data-testid="meeting-mark-invalid"
            @click="emit('invalidate')"
          />
          <Button
            v-else
            icon="mdi mdi-restore"
            :label="t('meetings.restore')"
            severity="contrast"
            text
            :disabled="!canManage"
            data-testid="meeting-restore"
            @click="emit('restore')"
          />
        </span>
        <span v-if="valid" v-tooltip.bottom="writeBlocked || undefined">
          <Button
            icon="mdi mdi-calendar-arrow-right"
            :label="t('meetings.followUp')"
            severity="contrast"
            text
            :disabled="!canWrite || busy"
            data-testid="meeting-follow-up"
            @click="emit('follow-up')"
          />
        </span>
      </template>
    </template>
    <template #handbook>
      <ShareButton :public-id="meeting?.public_id" />
      <HelpButton rounded slug="workspace/meeting" />
    </template>
  </ControlsBar>
</template>
