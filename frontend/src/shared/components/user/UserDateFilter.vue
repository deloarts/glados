<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUsersStore } from '@/core/stores/usersStore'
import { formatISODate, toDateKey } from '@/core/utils/dates'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'

/**
 * The row filter of a column that shows when something happened and who did
 * it. One small field sums up what is set, the person and the date range,
 * and opens a panel with a searchable user select above the date range
 * picker. It binds the two filter values the table already keeps, the user
 * id and the date range, so the server side filters stay as they are. A
 * table that filters by several people binds `userIds` instead of `userId`,
 * and the panel then offers a multi select.
 */
type DateRangeValue = Date | Array<Date | null> | null | undefined
type DateRange = [Date, Date | null] | null

const props = defineProps<{
  /** Names the column in the accessible labels. */
  column: string
  /** Shown while nothing is set, the table's usual "any" text. */
  placeholder?: string
  /** Leaves out the date range, for a list the server cannot filter by date. */
  userOnly?: boolean
}>()

const userId = defineModel<number | null>('userId', { default: null })
/** Left unbound for a single person; bound, the panel picks several. */
const userIds = defineModel<number[] | undefined>('userIds')
const range = defineModel<DateRangeValue>('range', { default: null })

const { t } = useI18n()
const users = useUsersStore()

const popover = ref<{ toggle: (event: Event) => void } | null>(null)

// The DatePicker may hand back a bare date or a half picked pair, so the
// range is read as one [from, to] pair, or null while it has no start.
const normalizedRange = computed<DateRange>(() => {
  const value = range.value
  const [from, to] = Array.isArray(value) ? value : [value ?? null, null]
  return from ? [from, to ?? null] : null
})

const multiple = computed(() => userIds.value !== undefined)

const userName = computed(() => {
  const ids = multiple.value ? (userIds.value ?? []) : userId.value != null ? [userId.value] : []
  const names = ids.map((id) => users.getById(id)?.full_name).filter(Boolean)
  return names.length > 0 ? names.join(', ') : null
})

function formatDay(date: Date): string {
  return formatISODate(toDateKey(date))
}

const rangeText = computed(() => {
  const value = normalizedRange.value
  if (!value) return null
  const [from, to] = value
  if (!to) return t('common.userDateFilter.from', { from: formatDay(from) })
  return t('common.userDateFilter.range', { from: formatDay(from), to: formatDay(to) })
})

const summary = computed(() => [userName.value, rangeText.value].filter(Boolean).join(', '))
const hasUser = computed(() => (multiple.value ? (userIds.value ?? []).length > 0 : userId.value != null))
const hasValue = computed(() => hasUser.value || normalizedRange.value !== null)

// The user list loads when the panel first opens, or at once when a person
// is already picked and the summary needs the name.
watch(
  hasUser,
  (picked) => {
    if (picked) void users.ensureLoaded()
  },
  { immediate: true },
)

function toggle(event: Event): void {
  void users.ensureLoaded()
  popover.value?.toggle(event)
}

function onRangeUpdate(value: DateRangeValue): void {
  const [from, to] = Array.isArray(value) ? value : [value ?? null, null]
  range.value = from ? [from, to ?? null] : null
}

function clear(): void {
  if (multiple.value) userIds.value = []
  else userId.value = null
  if (!props.userOnly) range.value = null
}
</script>

<template>
  <div class="user-date-filter">
    <IconField>
      <InputText
        :model-value="summary"
        readonly
        :placeholder="props.placeholder ?? t('common.userDateFilter.any')"
        :title="summary || undefined"
        :aria-label="t('common.filterBy', { column })"
        aria-haspopup="dialog"
        size="small"
        fluid
        class="user-date-filter-field"
        data-testid="user-date-filter-field"
        @click="toggle"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
      />
      <InputIcon
        v-if="hasValue"
        class="mdi mdi-close user-date-filter-clear"
        role="button"
        tabindex="0"
        :aria-label="t('common.clear')"
        data-testid="user-date-filter-clear"
        @click.stop="clear"
        @keydown.enter.prevent="clear"
      />
    </IconField>

    <Popover ref="popover">
      <div class="user-date-filter-panel" data-testid="user-date-filter-panel">
        <MultiSelect
          v-if="multiple"
          :model-value="userIds"
          :options="users.users"
          option-label="full_name"
          option-value="id"
          :loading="users.loading"
          :placeholder="t('common.userDateFilter.anyone')"
          :aria-label="t('common.userDateFilter.userOf', { column })"
          show-clear
          filter
          size="small"
          fluid
          @update:model-value="userIds = $event ?? []"
        />
        <Select
          v-else
          :model-value="userId ?? null"
          :options="users.users"
          option-label="full_name"
          option-value="id"
          :loading="users.loading"
          :placeholder="t('common.userDateFilter.anyone')"
          :aria-label="t('common.userDateFilter.userOf', { column })"
          show-clear
          filter
          size="small"
          fluid
          @update:model-value="userId = $event ?? null"
        />
        <DemandDateRangeFilter
          v-if="!userOnly"
          :model-value="normalizedRange"
          :placeholder="t('common.userDateFilter.anyDate')"
          :aria-label="t('common.userDateFilter.datesOf', { column })"
          @update:model-value="onRangeUpdate"
        />
      </div>
    </Popover>
  </div>
</template>

<style scoped lang="scss">
.user-date-filter {
  min-width: 0;
}

.user-date-filter-field {
  cursor: pointer;
  text-overflow: ellipsis;
}

.user-date-filter-clear {
  cursor: pointer;
}

.user-date-filter-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 16rem;
}
</style>
