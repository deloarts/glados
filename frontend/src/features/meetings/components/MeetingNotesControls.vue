<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useMeetingNotesViewStore } from '../stores/meetingNotesViewStore'
import { meetingPath } from '../utils/meetingRoutes'
import MeetingFormDialog from './MeetingFormDialog.vue'
import MeetingScopeRenameDialog from './MeetingScopeRenameDialog.vue'
import type { MeetingResponse } from '../types/meetingResponse'

/**
 * The actions of the Meeting Notes tab in the page's controls bar: New
 * Meeting, which opens the new meeting's page once it is saved, and Rename
 * Scope across the owner's meetings.
 */
const props = defineProps<{ ownerKind: 'project' | 'product'; ownerId: number }>()

const { t } = useI18n()
const router = useRouter()
const view = useMeetingNotesViewStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canWrite = computed(() => hasPermission(Permission.WRITE_MEETINGS))
const blocked = computed(() => missing(Permission.WRITE_MEETINGS))
const createVisible = ref(false)
const renameVisible = ref(false)

function onCreated(meeting: MeetingResponse): void {
  void router.push(meetingPath(meeting))
}
</script>

<template>
  <span v-tooltip.bottom="blocked || undefined">
    <Button
      icon="mdi mdi-plus"
      :label="t('meetings.newMeeting')"
      severity="contrast"
      text
      :disabled="!canWrite"
      data-testid="meeting-new"
      @click="createVisible = true"
    />
  </span>
  <span v-tooltip.bottom="blocked || undefined">
    <Button
      icon="mdi mdi-rename-outline"
      :label="t('meetings.scopeRename.button')"
      severity="contrast"
      text
      :disabled="!canWrite"
      data-testid="meeting-scope-rename"
      @click="renameVisible = true"
    />
  </span>

  <MeetingFormDialog
    v-model:visible="createVisible"
    :owner-kind="props.ownerKind"
    :owner-id="props.ownerId"
    @saved="onCreated"
  />
  <MeetingScopeRenameDialog
    v-model:visible="renameVisible"
    :owner-kind="props.ownerKind"
    :owner-id="props.ownerId"
    @renamed="view.triggerRefresh()"
  />
</template>
