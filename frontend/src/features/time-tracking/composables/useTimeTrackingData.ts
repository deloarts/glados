import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { getDisplayTimezone, toDayKey } from '@/core/utils/dates'
import { useMinuteTick } from '@/shared/composables/useMinuteTick'
import { getMyTimeTrackingMonth, getMyTimeTrackingYear } from '../api/timeTrackingApi'
import { liveDeltaSeconds, withLiveToday } from '../utils/timeTrackingLive'
import { monthKeyAt, yearOfMonth } from '../utils/timeTrackingMonth'
import { isCredentialStateError, timeTrackingErrorMessage } from '../utils/timeTrackingErrors'
import type { TimeTrackingMonthResponse, TimeTrackingYearResponse } from '../types/timeTrackingTypes'

/** The backend allows one month and one year fetch per user in this span. */
export const FETCH_COOLDOWN_MS = 5_000

// When the last fetch of each kind was sent. Module scope rather than
// component state, so leaving the tab and coming straight back still waits
// out the server's spacing instead of running into it. Only timestamps live
// here, never data.
let lastMonthFetchAt = 0
let lastYearFetchAt = 0

/** Forgets the fetch spacing; for specs only. */
export function resetTimeTrackingFetchSpacing(): void {
  lastMonthFetchAt = 0
  lastYearFetchAt = 0
}

/**
 * Data of the Time Tracking view: the shown month, the optional year, and
 * the live "now" today's figures tick against. Everything lives in this
 * component's memory only; nothing is cached across mounts, polled, or
 * written to browser storage. The time tracking system is asked only when
 * the caller loads, switches the month, reloads, or opens the year.
 *
 * Requests respect the server's per-user spacing: a switch or reload that
 * comes too soon after the previous fetch waits out the rest of it, and
 * only the latest wish is sent. A response that a newer request has
 * overtaken is dropped. After each month load the reload button rests for
 * the same span.
 */
export function useTimeTrackingData(options: { onCredentialStateError: () => void }) {
  const { t } = useI18n()
  const toast = useAppToast()

  const nowMs = ref(Date.now())
  const currentMonth = ref(monthKeyAt(new Date(nowMs.value), getDisplayTimezone()))

  useMinuteTick(() => {
    nowMs.value = Date.now()
    currentMonth.value = monthKeyAt(new Date(nowMs.value), getDisplayTimezone())
  })

  const selectedMonth = ref(currentMonth.value)
  const month = shallowRef<TimeTrackingMonthResponse | null>(null)
  const monthReceivedAt = ref(0)
  const monthLoading = ref(false)
  const monthError = ref<string | null>(null)
  const coolingDown = ref(false)

  const year = shallowRef<TimeTrackingYearResponse | null>(null)
  const yearLoading = ref(false)
  const yearError = ref<string | null>(null)
  // Set once the user opened the year section; switching to another year
  // then loads that year too, and reload refreshes it.
  const yearRequested = ref(false)

  let monthSeq = 0
  let yearSeq = 0
  let monthTimer: ReturnType<typeof setTimeout> | null = null
  let yearTimer: ReturnType<typeof setTimeout> | null = null
  let cooldownTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function clear(timer: ReturnType<typeof setTimeout> | null): null {
    if (timer !== null) clearTimeout(timer)
    return null
  }

  function startCooldown(): void {
    cooldownTimer = clear(cooldownTimer)
    coolingDown.value = true
    cooldownTimer = setTimeout(() => {
      cooldownTimer = null
      coolingDown.value = false
    }, FETCH_COOLDOWN_MS)
  }

  function failureMessage(err: unknown): string {
    if (isCredentialStateError(err)) options.onCredentialStateError()
    return timeTrackingErrorMessage(err, t, t('timeTracking.errors.unknown'))
  }

  async function loadMonth(): Promise<void> {
    const seq = ++monthSeq
    lastMonthFetchAt = Date.now()
    try {
      const result = await getMyTimeTrackingMonth(selectedMonth.value)
      if (disposed || seq !== monthSeq) return
      month.value = result
      monthReceivedAt.value = Date.now()
      monthError.value = null
    } catch (err: unknown) {
      if (disposed || seq !== monthSeq) return
      month.value = null
      monthError.value = failureMessage(err)
      toast.error(t('timeTracking.errors.loadFailed'), monthError.value)
    } finally {
      if (!disposed && seq === monthSeq) {
        monthLoading.value = false
        startCooldown()
      }
    }
  }

  function scheduleMonth(): void {
    monthTimer = clear(monthTimer)
    monthSeq++
    monthLoading.value = true
    const wait = Math.max(0, lastMonthFetchAt + FETCH_COOLDOWN_MS - Date.now())
    if (wait === 0) {
      void loadMonth()
      return
    }
    monthTimer = setTimeout(() => {
      monthTimer = null
      void loadMonth()
    }, wait)
  }

  async function loadYear(): Promise<void> {
    const seq = ++yearSeq
    lastYearFetchAt = Date.now()
    try {
      const result = await getMyTimeTrackingYear(yearOfMonth(selectedMonth.value))
      if (disposed || seq !== yearSeq) return
      year.value = result
      yearError.value = null
    } catch (err: unknown) {
      if (disposed || seq !== yearSeq) return
      year.value = null
      yearError.value = failureMessage(err)
    } finally {
      if (!disposed && seq === yearSeq) yearLoading.value = false
    }
  }

  function scheduleYear(): void {
    yearTimer = clear(yearTimer)
    yearSeq++
    yearLoading.value = true
    const wait = Math.max(0, lastYearFetchAt + FETCH_COOLDOWN_MS - Date.now())
    if (wait === 0) {
      void loadYear()
      return
    }
    yearTimer = setTimeout(() => {
      yearTimer = null
      void loadYear()
    }, wait)
  }

  /** Loads the shown month, used on mount and once credentials are usable. */
  function load(): void {
    scheduleMonth()
  }

  /** Refetches the shown month, and the year when it was opened. */
  function reload(): void {
    if (monthLoading.value || coolingDown.value) return
    scheduleMonth()
    if (yearRequested.value) scheduleYear()
  }

  function goToMonth(key: string): void {
    if (key > currentMonth.value || key === selectedMonth.value) return
    selectedMonth.value = key
    month.value = null
    monthError.value = null
    scheduleMonth()
  }

  function openYear(): void {
    yearRequested.value = true
    if (!year.value && !yearLoading.value) scheduleYear()
  }

  /** Drops everything fetched, for when the credentials stop being usable. */
  function clearData(): void {
    monthTimer = clear(monthTimer)
    yearTimer = clear(yearTimer)
    monthSeq++
    yearSeq++
    month.value = null
    year.value = null
    monthLoading.value = false
    yearLoading.value = false
  }

  watch(
    () => yearOfMonth(selectedMonth.value),
    () => {
      year.value = null
      yearError.value = null
      if (yearRequested.value) scheduleYear()
    },
  )

  onScopeDispose(() => {
    disposed = true
    monthTimer = clear(monthTimer)
    yearTimer = clear(yearTimer)
    cooldownTimer = clear(cooldownTimer)
  })

  const live = computed(() => {
    const value = month.value
    if (!value) return null
    return withLiveToday(
      value,
      liveDeltaSeconds(value.fetched_at, monthReceivedAt.value, nowMs.value),
    )
  })

  // Days after this one have not happened yet; null for a past month.
  const cutoffDate = computed(() => {
    const today = month.value?.totals?.today?.date
    if (today) return today
    if (selectedMonth.value !== currentMonth.value) return null
    return toDayKey(new Date(nowMs.value).toISOString())
  })

  const todayDate = computed(() => month.value?.totals?.today?.date ?? null)

  // Today while clocked in: still running, so left out of the statistics.
  const runningDate = computed(() =>
    live.value?.today?.clocked_in ? (live.value.today.date ?? null) : null,
  )

  const canGoNext = computed(() => selectedMonth.value < currentMonth.value)
  const canReload = computed(() => !monthLoading.value && !coolingDown.value)

  return {
    currentMonth,
    selectedMonth,
    month,
    live,
    monthLoading,
    monthError,
    coolingDown,
    canReload,
    canGoNext,
    cutoffDate,
    todayDate,
    runningDate,
    year,
    yearLoading,
    yearError,
    yearRequested,
    load,
    reload,
    goToMonth,
    openYear,
    clearData,
  }
}
