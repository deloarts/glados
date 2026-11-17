<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  archiveInfoscreen,
  getInfoscreens,
  restoreInfoscreen,
} from '../api/infoscreensApi'
import InfoscreenDefaultScheduleDialog from '../components/InfoscreenDefaultScheduleDialog.vue'
import InfoscreenEditorDialog from '../components/InfoscreenEditorDialog.vue'
import InfoscreenScheduleDialog from '../components/InfoscreenScheduleDialog.vue'
import InfoscreensTable from '../components/InfoscreensTable.vue'

import type { InfoscreenResponse } from '../types/infoscreenResponse'

const { t } = useI18n()
const router = useRouter()
const confirm = useConfirm()
const toast = useAppToast()
const { withErrorToast, toastOnError } = useErrorToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canWrite = computed(() => hasPermission(Permission.WRITE_INFOSCREENS))
const missingWrite = computed(() => missing(Permission.WRITE_INFOSCREENS))

const infoscreens = ref<InfoscreenResponse[]>([])
const loading = ref(false)
const showArchived = ref(false)
// The actions column is off by default, as on the other resource pages, and
// the row context menu offers the same actions.
const showActions = ref(false)
const search = ref('')
watchLoadingBar(loading)

const visibleRows = computed(() => {
  const needle = search.value.trim().toLowerCase()
  if (!needle) return infoscreens.value
  return infoscreens.value.filter(
    (row) =>
      row.name.toLowerCase().includes(needle) ||
      (row.description ?? '').toLowerCase().includes(needle),
  )
})

async function load(): Promise<void> {
  loading.value = true
  try {
    infoscreens.value = await getInfoscreens(showArchived.value)
  } finally {
    loading.value = false
  }
}

function refresh(): void {
  load().catch(toastOnError())
}

onMounted(refresh)
watch(showArchived, refresh)
// The "shown on" lists change when a terminal is assigned another screen.
useLiveRefresh([LiveResource.INFOSCREENS, LiveResource.TERMINALS], load)

const editorVisible = ref(false)
const editing = ref<InfoscreenResponse | null>(null)

function openCreate(): void {
  editing.value = null
  editorVisible.value = true
}

function openEdit(infoscreen: InfoscreenResponse): void {
  editing.value = infoscreen
  editorVisible.value = true
}

const scheduleVisible = ref(false)
const scheduling = ref<InfoscreenResponse | null>(null)

function openSchedule(infoscreen: InfoscreenResponse): void {
  scheduling.value = infoscreen
  scheduleVisible.value = true
}

const defaultScheduleVisible = ref(false)
// The live screens the default schedule applies to, for the dialog's intro.
const followingDefault = computed(
  () =>
    infoscreens.value.filter((row) => !row.archived && row.display_schedule_mode === 'default')
      .length,
)

function onDefaultScheduleSaved(): void {
  toast.success(
    t('infoscreens.defaultScheduleDialog.title'),
    t('infoscreens.toasts.defaultScheduleSaved'),
  )
}

function upsert(infoscreen: InfoscreenResponse): void {
  const exists = infoscreens.value.some((row) => row.id === infoscreen.id)
  infoscreens.value = exists
    ? infoscreens.value.map((row) => (row.id === infoscreen.id ? infoscreen : row))
    : [...infoscreens.value, infoscreen]
}

function onSaved(infoscreen: InfoscreenResponse): void {
  upsert(infoscreen)
  toast.success(infoscreen.name, t('infoscreens.toasts.saved'))
}

/** The preview runs in its own tab with the bare kiosk layout, as a TV shows it. */
function openPreview(infoscreen: InfoscreenResponse): void {
  const href = router.resolve(`/infoscreen/preview/${infoscreen.id}`).href
  window.open(href, '_blank', 'noopener')
}

function onArchive(infoscreen: InfoscreenResponse): void {
  async function onAccept(): Promise<void> {
    const archived = await withErrorToast(() => archiveInfoscreen(infoscreen.id), {
      summary: infoscreen.name,
      fallbackMessage: t('infoscreens.errors.unknown'),
    })
    if (!archived) return
    if (showArchived.value) upsert(archived)
    else infoscreens.value = infoscreens.value.filter((row) => row.id !== infoscreen.id)
    toast.success(infoscreen.name, t('infoscreens.toasts.archived'))
  }

  const shownOn = infoscreen.shown_on.length
  confirm.require({
    header: t('common.archive'),
    message:
      shownOn > 0
        ? t('infoscreens.archiveConfirmShown', { name: infoscreen.name, count: shownOn }, shownOn)
        : t('common.archiveConfirm', { name: infoscreen.name }),
    icon: 'mdi mdi-archive-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.archive'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

async function onRestore(infoscreen: InfoscreenResponse): Promise<void> {
  const restored = await withErrorToast(() => restoreInfoscreen(infoscreen.id), {
    summary: infoscreen.name,
    fallbackMessage: t('infoscreens.errors.unknown'),
  })
  if (!restored) return
  upsert(restored)
  toast.success(infoscreen.name, t('infoscreens.toasts.restored'))
}

function clearAll(): void {
  search.value = ''
  showArchived.value = false
}
</script>

<template>

  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-tooltip.bottom="missingWrite || undefined">
            <Button
              :label="t('infoscreens.controls.new')"
              icon="mdi mdi-plus"
              severity="contrast"
              text
              :disabled="!canWrite"
              data-testid="infoscreens-new"
              @click="openCreate"
            />
          </span>
          <span v-tooltip.bottom="missingWrite || undefined">
            <Button
              :label="t('infoscreens.controls.setDefaultSchedule')"
              icon="mdi mdi-calendar-clock"
              severity="contrast"
              text
              :disabled="!canWrite"
              data-testid="infoscreens-default-schedule"
              @click="defaultScheduleVisible = true"
            />
          </span>
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="infoscreens"
        :syncing="loading"
        :show-actions="showActions"
        :has-active-filters="search !== '' || showArchived"
        :show-archived="showArchived"
        v-model:search="search"
        :search-placeholder="t('infoscreens.controls.search')"
        @sync="refresh"
        @clear="clearAll"
        @toggle-show-archived="showArchived = !showArchived"
        @toggle-show-actions="showActions = !showActions"
      />
    </template>

    <InfoscreensTable
      :infoscreens="visibleRows"
      :show-archived="showArchived"
      :show-actions="showActions"
      :can-write="canWrite"
      :missing-hint="missingWrite"
      @open="openEdit"
      @preview="openPreview"
      @schedule="openSchedule"
      @archive="onArchive"
      @restore="(row) => void onRestore(row)"
    />
  </PageLayout>

  <InfoscreenEditorDialog
    v-model:visible="editorVisible"
    :infoscreen="editing"
    :can-write="canWrite"
    :missing-hint="missingWrite"
    @saved="onSaved"
    @preview="openPreview"
  />
  <InfoscreenDefaultScheduleDialog
    v-model:visible="defaultScheduleVisible"
    :following-count="followingDefault"
    :can-write="canWrite"
    :missing-hint="missingWrite"
    @saved="onDefaultScheduleSaved"
  />
  <InfoscreenScheduleDialog
    v-model:visible="scheduleVisible"
    :infoscreen="scheduling"
    :can-write="canWrite"
    :missing-hint="missingWrite"
    @saved="onSaved"
  />
</template>
