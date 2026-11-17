import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  addDays,
  endOfWeek,
  formatISODate,
  startOfDay,
  toDateKey,
  todayStart as tenantTodayStart,
  weekdayName,
} from '@/core/utils/dates'

export { startOfDay } from '@/core/utils/dates'

// Every day in the range is a draggable list in every column, so a wide
// pick would create thousands of Sortable instances.
const MAX_RANGE_DAYS = 31

export interface BoardDay {
  key: string
  label: string
  isToday: boolean
}

/**
 * The board's default range, today through the Sunday that ends the week,
 * so the board shows the rest of the working week. On a Sunday it is that
 * day alone.
 */
function defaultRange(today: Date): [Date, Date] {
  return [today, endOfWeek(today)]
}

/**
 * Visible date range of the production queue board. It defaults to the
 * rest of the current week; changing it pulls other days' work onto the
 * board, and anything projected past its end stays off it.
 */
export function useQueueBoardDateRange() {
  const { t } = useI18n()

  const todayStart = ref(tenantTodayStart())
  const dateRange = ref<[Date, Date]>(defaultRange(todayStart.value))

  // The picker yields `[Date]` while half picked and `null` after Clear, so
  // neither end can be trusted.
  const rangeDays = computed<Date[]>(() => {
    const [from, to] = dateRange.value ?? []
    const start = startOfDay(from ?? todayStart.value)
    const end = startOfDay(to ?? from ?? todayStart.value)
    const days: Date[] = []
    for (let day = start; day <= end && days.length < MAX_RANGE_DAYS; day = addDays(day, 1)) {
      days.push(day)
    }
    return days
  })

  const dayKeys = computed<string[]>(() => rangeDays.value.map((day) => toDateKey(day)))
  const todayKey = computed(() => toDateKey(todayStart.value))

  // The weekday is what the shop floor reads a multi-day board by.
  const boardDays = computed<BoardDay[]>(() =>
    rangeDays.value.map((day) => {
      const key = toDateKey(day)
      const weekday = weekdayName(day)
      const label = `${weekday} ${formatISODate(key)}`
      return {
        key,
        isToday: key === todayKey.value,
        label:
          key === todayKey.value ? `${t('productionQueue.board.groups.today')} · ${label}` : label,
      }
    }),
  )

  // Moves "today" forward after midnight and reports whether it did. A
  // board still on the untouched default range rolls over with the day; a
  // range the user picked stays where it is.
  function rollOverDay(): boolean {
    const today = tenantTodayStart()
    if (today.getTime() === todayStart.value.getTime()) return false

    const [from, to] = dateRange.value ?? []
    const [defaultFrom, defaultTo] = defaultRange(todayStart.value)
    const onDefaultRange =
      from?.getTime() === defaultFrom.getTime() && (to ?? from)?.getTime() === defaultTo.getTime()

    todayStart.value = today
    if (onDefaultRange) dateRange.value = defaultRange(today)
    return true
  }

  return { todayStart, dateRange, rangeDays, dayKeys, boardDays, rollOverDay }
}
