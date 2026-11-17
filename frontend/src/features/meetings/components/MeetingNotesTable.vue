<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useConfirm } from 'openvue/useconfirm'
import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta, DataTableRowClickEvent, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { Permission } from '@/core/auth/permissions'
import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { formatISODate } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { useMeetingNotesDrafts } from '../composables/useMeetingNotesDrafts'
import MeetingNotesDraftsNotice from './MeetingNotesDraftsNotice.vue'
import { deleteMeeting, getMeeting, getMeetingTagSuggestions, getMeetings } from '../api/meetingsApi'
import { useMeetingNotesViewStore } from '../stores/meetingNotesViewStore'
import type { MeetingSort } from '../stores/meetingNotesViewStore'
import { formatMeetingTimes } from '../utils/meetingDates'
import { filterMeetingRows } from '../utils/meetingListFilters'
import { useMeetingListFilterOptions } from '../composables/useMeetingListFilterOptions'
import { meetingPath } from '../utils/meetingRoutes'
import MeetingScopeChip from './MeetingScopeChip.vue'
import type { MeetingListRowResponse } from '../types/meetingResponse'

/**
 * The Meeting Notes tab of a project or a product: its meetings, on a
 * product also those of its projects unless Hide Projects is pressed. A
 * row opens the meeting's page. The list is not paged on the server, so the
 * table sorts and pages it here, and it follows other users' changes live.
 * The Tags column filters the list on the server by one of the tags in use;
 * the other column filters work on the loaded list.
 */
const props = defineProps<{
  ownerKind: 'project' | 'product'
  ownerId: number
}>()

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()
const confirm = useConfirm()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const view = useMeetingNotesViewStore()
const { showInvalid, hideProjects, groupByProject, showProjectColumn, tagFilter, filters } = storeToRefs(view)
const { sortBy, showActions, refreshTrigger } = storeToRefs(view)
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const rows = ref<MeetingListRowResponse[]>([])
// The user's own drafts of new meetings here, which an AI agent prepared.
const { drafts } = useMeetingNotesDrafts(() =>
  props.ownerKind === 'project' ? { project_id: props.ownerId } : { product_id: props.ownerId },
)
const loading = ref(false)
const loaded = ref(false)
const failed = ref(false)
const first = ref(0)
const pageRows = ref(TABLE_DEFAULT_ROWS)
watchLoadingBar(loading)

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const FILTERS: DataTableFilterMeta = Object.fromEntries(
  ['status', 'starts_at', 'owner', 'scopes', 'name', 'tags', 'notes', 'open_todo_count', 'attendees', 'location'].map(
    (field) => [field, { value: null, matchMode: FilterMatchMode.EQUALS }],
  ),
)

const tagOptions = ref<string[]>([])

/** The tags in use for the filter, the selected one kept while no meeting carries it any more. */
async function loadTagOptions(): Promise<void> {
  try {
    const response = await getMeetingTagSuggestions({ limit: 100 })
    tagOptions.value = response.suggestions.map((suggestion) => suggestion.name)
  } catch {
    // Without suggestions the filter only offers the tag already chosen.
  }
}

const tagFilterOptions = computed(() => {
  const selected = tagFilter.value
  if (!selected || tagOptions.value.some((tag) => tag.toLocaleLowerCase() === selected.toLocaleLowerCase())) {
    return tagOptions.value
  }
  return [selected, ...tagOptions.value]
})

const isProduct = computed(() => props.ownerKind === 'product')
const withProjects = computed(() => isProduct.value && !hideProjects.value)
let epoch = 0

/** Reads the list; a refetch after a live signal runs without the loading bar. */
async function load(quiet = false): Promise<void> {
  const current = ++epoch
  if (!quiet) loading.value = true
  try {
    const list = await getMeetings({
      ...(isProduct.value ? { product_id: props.ownerId } : { project_id: props.ownerId }),
      include_projects: withProjects.value,
      include_invalid: showInvalid.value,
      ...(tagFilter.value ? { tag: tagFilter.value } : {}),
    })
    if (current !== epoch) return
    rows.value = list
    failed.value = false
  } catch {
    if (current === epoch && !quiet) failed.value = true
  } finally {
    if (current === epoch) {
      loading.value = false
      loaded.value = true
    }
  }
}

watch([() => props.ownerKind, () => props.ownerId, showInvalid, withProjects, tagFilter, refreshTrigger], () => {
  first.value = 0
  void load()
  void loadTagOptions()
}, { immediate: true })

useLiveRefresh([LiveResource.MEETINGS], () => {
  void loadTagOptions()
  return load(true)
})

const COMPARE: Record<MeetingSort, (a: MeetingListRowResponse, b: MeetingListRowResponse) => number> = {
  startsDesc: (a, b) => b.starts_at.localeCompare(a.starts_at),
  startsAsc: (a, b) => a.starts_at.localeCompare(b.starts_at),
  numberDesc: (a, b) => b.meeting_number.localeCompare(a.meeting_number),
  numberAsc: (a, b) => a.meeting_number.localeCompare(b.meeting_number),
  nameAsc: (a, b) => a.name.localeCompare(b.name),
  nameDesc: (a, b) => b.name.localeCompare(a.name),
}

function ownerLabel(row: MeetingListRowResponse): string {
  return row.owner.kind === 'product'
    ? t('meetings.list.productGroup', { number: row.owner.number })
    : t('meetings.list.projectGroup', { number: row.owner.number })
}

type ShownRow = MeetingListRowResponse & { _ownerGroup: string }

const { statusOptions, todoOptions, ownerOptions, attendeeOptions } = useMeetingListFilterOptions(rows)

watch(filters, () => (first.value = 0), { deep: true })

const shownRows = computed<ShownRow[]>(() => {
  const sorted = filterMeetingRows(rows.value, filters.value).sort(COMPARE[sortBy.value])
  const withGroup = sorted.map((row) => ({ ...row, _ownerGroup: ownerLabel(row) }))
  if (!(withProjects.value && groupByProject.value)) return withGroup
  // The product's own meetings first, then its projects by number; the sort
  // holds inside each group.
  const rank = (row: ShownRow) => (row.owner.kind === 'product' ? '' : row.owner.number)
  return withGroup.sort((a, b) => rank(a).localeCompare(rank(b)))
})

const grouped = computed(() => withProjects.value && groupByProject.value)

function groupCount(label: string): number {
  return shownRows.value.filter((row) => row._ownerGroup === label).length
}

function open(row: MeetingListRowResponse): void {
  void router.push(meetingPath(row))
}

function onRowClick(event: DataTableRowClickEvent): void {
  open(event.data as MeetingListRowResponse)
}

function attendeeLabel(row: MeetingListRowResponse): string {
  return row.attendees.map((attendee) => attendee.name).join(', ')
}

// ── Context menu ──────────────────────────────────────────────────────

const cm = ref<{ show: (event: Event) => void } | null>(null)
const menuRow = ref<MeetingListRowResponse | null>(null)
const canManage = computed(() => hasPermission(Permission.MANAGE_MEETINGS))

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  menuRow.value = event.data as MeetingListRowResponse
  cm.value?.show(event.originalEvent)
}

const menuItems = computed<MenuItem[]>(() => {
  const row = menuRow.value
  if (!row) return []
  return [
    { label: t('meetings.list.open'), icon: 'mdi mdi-open-in-app', command: () => open(row) },
    {
      label: t('meetings.list.openInNewTab'),
      icon: 'mdi mdi-open-in-new',
      command: () => {
        window.open(router.resolve(meetingPath(row)).href, '_blank', 'noopener')
      },
    },
    { separator: true },
    {
      label: t('meetings.list.delete'),
      icon: 'mdi mdi-delete-outline',
      disabled: !canManage.value,
      title: missing(Permission.MANAGE_MEETINGS) || undefined,
      command: () => askDelete(row),
    },
  ]
})

function askDelete(row: MeetingListRowResponse): void {
  confirm.require({
    header: t('meetings.list.deleteHeader'),
    message: t('meetings.list.deleteConfirm', { number: row.meeting_number }),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary', text: true },
    acceptProps: { label: t('meetings.list.delete'), severity: 'danger', icon: 'mdi mdi-delete-outline' },
    accept: () => void runDelete(row),
  })
}

async function runDelete(row: MeetingListRowResponse): Promise<void> {
  try {
    const meeting = await getMeeting(row.id)
    await deleteMeeting(row.id, meeting.edit_version)
    toast.success(row.meeting_number, t('meetings.toasts.deleted'))
    await load(true)
  } catch (err) {
    toast.error(row.meeting_number, extractApiError(err) ?? t('meetings.errors.unknown'))
  }
}
</script>

<template>
  <DataTable
    :value="shownRows"
    v-model:context-menu-selection="menuRow"
    v-model:first="first"
    v-model:rows="pageRows"
    data-key="id"
    filter-display="row"
    :filters="FILTERS"
    paginator
    always-show-paginator
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    :row-group-mode="grouped ? 'subheader' : undefined"
    :group-rows-by="grouped ? '_ownerGroup' : undefined"
    :row-class="(row: MeetingListRowResponse) => (row.valid ? undefined : 'meeting-row-invalid')"
    class="meetings-table clickable-rows"
    data-testid="meetings-table"
    @row-click="onRowClick"
    @row-contextmenu="onRowContextMenu"
  >
    <template v-if="grouped" #groupheader="{ data }">
      <div class="group-header">
        <i class="mdi mdi-folder-outline" aria-hidden="true" />
        <span class="group-header-label">{{ data._ownerGroup }}</span>
        <span class="text-muted">({{ groupCount(data._ownerGroup) }})</span>
      </div>
    </template>
    <template v-if="drafts.length" #header>
      <MeetingNotesDraftsNotice :drafts="drafts" />
    </template>
    <template #empty>
      <EmptyState
        v-if="loaded"
        icon="mdi mdi-forum-outline"
        :message="failed ? t('meetings.errors.listLoad') : t('meetings.list.empty')"
      />
    </template>

    <Column header="#" body-class="row-number" class="column-fit">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>

    <Column v-if="showActions" :header="t('meetings.list.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <div class="row-actions">
          <span v-tooltip.top="missing(Permission.MANAGE_MEETINGS) || undefined">
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canManage"
              :aria-label="t('meetings.list.delete')"
              @click.stop="askDelete(data)"
            />
          </span>
        </div>
      </template>
    </Column>

    <Column field="status" :header="t('meetings.list.columns.status')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span class="status-cell">
          <Tag
            :value="data.valid ? t('meetings.valid') : t('meetings.invalid')"
            :severity="data.valid ? 'success' : 'danger'"
          />
          <i
            v-if="data.sent"
            v-tooltip.top="t('meetings.list.sent')"
            class="mdi mdi-email-fast-outline status-icon"
            :aria-label="t('meetings.list.sent')"
            role="img"
            data-testid="meeting-sent-icon"
          />
          <i
            v-if="data.printed"
            v-tooltip.top="t('meetings.list.printed')"
            class="mdi mdi-printer-outline status-icon"
            :aria-label="t('meetings.list.printed')"
            role="img"
            data-testid="meeting-printed-icon"
          />
        </span>
      </template>
      <template #filter>
        <Select
          v-model="filters.status"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('meetings.list.filters.any')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.status') })"
          show-clear
          size="small"
          fluid
          data-testid="meeting-status-filter"
        />
      </template>
    </Column>

    <Column field="starts_at" :header="t('meetings.list.columns.when')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <div class="stacked">
          <span>{{ formatISODate(data.starts_at) }}</span>
          <small class="text-muted">{{ formatMeetingTimes(data.starts_at, data.ends_at) }}</small>
        </div>
      </template>
      <template #filter>
        <DatePicker
          v-model="filters.dates"
          selection-mode="range"
          :manual-input="false"
          show-clear
          :placeholder="t('meetings.list.filters.anyDay')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.when') })"
          size="small"
          class="filter-dates"
          fluid
          data-testid="meeting-date-filter"
        />
      </template>
    </Column>

    <Column field="name" :header="t('meetings.list.columns.name')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <div class="stacked">
          <span class="meeting-name">{{ data.name }}</span>
          <small class="text-muted">{{ data.meeting_number }}</small>
        </div>
      </template>
      <template #filter>
        <InputText
          v-model="filters.name"
          :placeholder="t('meetings.list.filters.search')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.name') })"
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-name-filter"
        />
      </template>
    </Column>

    <Column
      v-if="withProjects && showProjectColumn"
      field="owner"
      :header="t('meetings.list.columns.project')"
      :show-filter-menu="false"
      class="column-fit"
    >
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.owner.kind === 'product'" class="text-muted">{{ t('meetings.list.product') }}</span>
        <RouterLink
          v-else
          :to="`/workspace/projects/${data.owner.id}/meeting-notes`"
          class="table-link"
          @click.stop
        >
          {{ data.owner.number }}
        </RouterLink>
      </template>
      <template #filter>
        <MultiSelect
          v-model="filters.owners"
          :options="ownerOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('meetings.list.filters.any')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.project') })"
          :max-selected-labels="1"
          filter
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-owner-filter"
        />
      </template>
    </Column>

    <Column field="scopes" :header="t('meetings.list.columns.scope')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.scopes.length" class="scope-chips">
          <MeetingScopeChip
            v-for="(chip, index) in data.scopes"
            :key="index"
            :scope="chip.scope"
            :icon="chip.icon"
            :internal="chip.internal"
          />
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter>
        <InputText
          v-model="filters.scope"
          :placeholder="t('meetings.list.filters.search')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.scope') })"
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-scope-filter"
        />
      </template>
    </Column>

    <Column field="tags" :header="t('meetings.list.columns.tags')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.tags.length" class="tag-chips" data-testid="meeting-tags">
          <Tag v-for="tag in data.tags" :key="tag" :value="tag" icon="mdi mdi-tag-outline" severity="secondary" />
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter>
        <Select
          v-model="tagFilter"
          :options="tagFilterOptions"
          :placeholder="t('meetings.list.anyTag')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.tags') })"
          show-clear
          filter
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-tag-filter"
        />
      </template>
    </Column>

    <Column field="notes" :header="t('meetings.list.columns.notes')" :show-filter-menu="false">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.notes" class="notes-short" :title="data.notes">{{ data.notes }}</span>
        <span v-else class="text-muted">{{ t('meetings.list.noNotes') }}</span>
      </template>
      <template #filter>
        <InputText
          v-model="filters.notes"
          :placeholder="t('meetings.list.filters.search')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.notes') })"
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-notes-filter"
        />
      </template>
    </Column>

    <Column
      field="open_todo_count"
      :header="t('meetings.list.columns.openTodos')"
      :show-filter-menu="false"
      class="column-fit"
    >
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.open_todo_count" class="todo-count" data-testid="meeting-open-todos">
          {{ data.open_todo_count }}
          <span
            v-if="data.overdue_todo_count"
            class="todo-overdue"
            data-testid="meeting-overdue-todos"
          >{{ t('meetings.list.overdue', { count: data.overdue_todo_count }) }}</span>
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter>
        <Select
          v-model="filters.todos"
          :options="todoOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('meetings.list.filters.any')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.openTodos') })"
          show-clear
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-todo-filter"
        />
      </template>
    </Column>

    <Column field="attendees" :header="t('meetings.list.columns.attendees')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.attendees.length" class="attendees" :title="attendeeLabel(data)">
          <Tag
            v-for="(attendee, index) in data.attendees.slice(0, 4)"
            :key="index"
            :value="attendee.name"
            :icon="attendee.kind === 'user' ? 'mdi mdi-account-outline' : 'mdi mdi-card-account-mail-outline'"
            severity="secondary"
          />
          <span v-if="data.attendees.length > 4" class="text-muted">+{{ data.attendees.length - 4 }}</span>
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter>
        <MultiSelect
          v-model="filters.attendees"
          :options="attendeeOptions"
          :placeholder="t('meetings.list.filters.any')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.attendees') })"
          :max-selected-labels="1"
          filter
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-attendee-filter"
        />
      </template>
    </Column>

    <Column field="location" :header="t('meetings.list.columns.location')" :show-filter-menu="false" class="column-fit">
      <template #body="{ data }: { data: MeetingListRowResponse }">
        <span v-if="data.location">{{ data.location }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
      <template #filter>
        <InputText
          v-model="filters.location"
          :placeholder="t('meetings.list.filters.search')"
          :aria-label="t('common.filterBy', { column: t('meetings.list.columns.location') })"
          size="small"
          class="filter-wide"
          fluid
          data-testid="meeting-location-filter"
        />
      </template>
    </Column>

    <Column />
  </DataTable>

  <ContextMenu ref="cm" :model="menuItems" :pt="disabledItemTooltipPt" @hide="menuRow = null" />
</template>

<style scoped lang="scss">
.meetings-table {
  width: 100%;
}

.stacked {
  display: flex;
  flex-direction: column;
}

.meeting-name {
  font-weight: 600;
}

.status-cell,
.scope-chips,
.tag-chips,
.attendees {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.attendees {
  // Room for two attendees side by side before the tags wrap.
  min-width: 18rem;
  max-width: 24rem;
}

.tag-chips {
  max-width: 18rem;
}

// The column fits its content, so the filter above it sets a floor that
// keeps the chosen tag readable.
.filter-wide {
  min-width: 10rem;
}

.filter-dates {
  min-width: 13rem;
}

.status-icon {
  color: var(--p-text-muted-color);
}

// One line that ends in an ellipsis; the full text is in the tooltip.
.notes-short {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 12rem;
  max-width: 28rem;
}

.todo-count {
  display: inline-flex;
  gap: var(--space-2);
  white-space: nowrap;
}

.todo-overdue {
  color: var(--p-red-500);
  font-weight: 600;
}

.table-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    color: var(--p-primary-color);
    text-decoration: underline;
  }
}

.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.group-header-label {
  font-weight: bold;
}

:deep(.meeting-row-invalid) {
  color: var(--p-text-muted-color);
}
</style>
