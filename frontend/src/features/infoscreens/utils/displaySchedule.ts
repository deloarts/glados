import type { InfoscreenDisplaySchedule, InfoscreenResponse } from '../types/infoscreenResponse'

/** The days of a schedule, Monday first, as the server names them. */
export const SCHEDULE_WEEKDAYS = [
  'monday',
  'tuesday',
  'wednesday',
  'thursday',
  'friday',
  'saturday',
  'sunday',
] as const

export type ScheduleWeekday = (typeof SCHEDULE_WEEKDAYS)[number]

/** The server keeps a day to this many windows. */
export const MAX_WINDOWS_PER_DAY = 6

/** The editor works in half hours, so a day has 48 slots. */
export const SLOT_MINUTES = 30
export const SLOTS_PER_DAY = (24 * 60) / SLOT_MINUTES

/** The window of a working day in a new schedule. */
export const DEFAULT_WINDOW = { start: '06:00', end: '18:00' } as const

const WORKING_DAYS = 5
const TIME_PATTERN = /^([01]\d|2[0-4]):([0-5]\d)$/

/**
 * An on-window as the server stores it, start and end as `HH:MM` in the
 * tenant timezone. An end of `24:00` is the following midnight.
 */
export interface ScheduleWindow {
  start: string
  end: string
}

/**
 * A schedule as the grid holds it: per weekday one flag per half hour,
 * true while the displays are on.
 */
export type ScheduleGrid = Record<ScheduleWeekday, boolean[]>

/** One cell of the grid, the weekday by its index from Monday and the slot from midnight. */
export interface ScheduleCell {
  day: number
  slot: number
}

/** A schedule loaded into the grid, and whether a stored window had to be widened to half hours. */
export interface LoadedSchedule {
  grid: ScheduleGrid | null
  rounded: boolean
}

/** How the list sums up the display times of a screen. */
export type ScheduleSummary =
  | 'default'
  | 'alwaysOn'
  | 'alwaysOnHolidays'
  | 'scheduled'
  | 'scheduledHolidays'

/** `HH:MM` as minutes after midnight, or NaN when it is not a time. */
export function toMinutes(value: string): number {
  const match = TIME_PATTERN.exec(value)
  if (!match) return Number.NaN
  const minutes = Number(match[1]) * 60 + Number(match[2])
  return minutes > 24 * 60 ? Number.NaN : minutes
}

/** The time at which a slot starts, `24:00` for the slot after the last one. */
export function slotTime(slot: number): string {
  const minutes = slot * SLOT_MINUTES
  const hours = Math.floor(minutes / 60)
  return `${String(hours).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

function filledDay(on: boolean): boolean[] {
  return Array.from({ length: SLOTS_PER_DAY }, () => on)
}

/** A grid with every slot of the week on or off. */
export function filledGrid(on: boolean): ScheduleGrid {
  return Object.fromEntries(SCHEDULE_WEEKDAYS.map((day) => [day, filledDay(on)])) as ScheduleGrid
}

/** A new schedule: on from six to six on working days and off at the weekend. */
export function defaultGrid(): ScheduleGrid {
  const workingDay = windowsToSlots([DEFAULT_WINDOW]).slots
  return Object.fromEntries(
    SCHEDULE_WEEKDAYS.map((day, index) => [
      day,
      index < WORKING_DAYS ? [...workingDay] : filledDay(false),
    ]),
  ) as ScheduleGrid
}

/**
 * The slots of a day from its stored windows. A window that does not start
 * and end on a half hour is widened to the half hours around it, so the
 * displays are never off when the stored schedule had them on; `rounded`
 * says that this happened.
 */
export function windowsToSlots(windows: readonly ScheduleWindow[]): {
  slots: boolean[]
  rounded: boolean
} {
  const slots = filledDay(false)
  let rounded = false
  for (const window of windows) {
    const start = toMinutes(window.start)
    const end = toMinutes(window.end)
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) continue
    const first = Math.floor(start / SLOT_MINUTES)
    const last = Math.ceil(end / SLOT_MINUTES)
    if (first * SLOT_MINUTES !== start || last * SLOT_MINUTES !== end) rounded = true
    for (let slot = first; slot < last; slot++) slots[slot] = true
  }
  return { slots, rounded }
}

/** The windows of a day, one per run of slots that are on, in time order. */
export function slotsToWindows(slots: readonly boolean[]): ScheduleWindow[] {
  const windows: ScheduleWindow[] = []
  let start: number | null = null
  for (let slot = 0; slot <= slots.length; slot++) {
    const on = slots[slot] === true
    if (on && start === null) start = slot
    if (!on && start !== null) {
      windows.push({ start: slotTime(start), end: slotTime(slot) })
      start = null
    }
  }
  return windows
}

/** How many windows a day would be stored as. */
export function countWindows(slots: readonly boolean[]): number {
  return slots.filter((on, slot) => on && slots[slot - 1] !== true).length
}

/** A schedule from the server in the grid's shape; no schedule stays null, the displays are always on. */
export function toScheduleGrid(schedule: InfoscreenDisplaySchedule | null | undefined): LoadedSchedule {
  if (!schedule) return { grid: null, rounded: false }
  let rounded = false
  const grid = Object.fromEntries(
    SCHEDULE_WEEKDAYS.map((day) => {
      const loaded = windowsToSlots(schedule[day] ?? [])
      rounded ||= loaded.rounded
      return [day, loaded.slots]
    }),
  ) as ScheduleGrid
  return { grid, rounded }
}

/** The schedule as it is sent, every day present with its windows in time order. */
export function toScheduleRequest(grid: ScheduleGrid): InfoscreenDisplaySchedule {
  return Object.fromEntries(
    SCHEDULE_WEEKDAYS.map((day) => [day, slotsToWindows(grid[day])]),
  ) as InfoscreenDisplaySchedule
}

/** The days that would need more windows than the server keeps. */
export function overfullDays(grid: ScheduleGrid | null): ScheduleWeekday[] {
  if (!grid) return []
  return SCHEDULE_WEEKDAYS.filter((day) => countWindows(grid[day]) > MAX_WINDOWS_PER_DAY)
}

/** Whether the grid can be saved; no schedule always can. */
export function isGridValid(grid: ScheduleGrid | null): boolean {
  return overfullDays(grid).length === 0
}

/**
 * The grid with every cell of the rectangle between two corners set to one
 * state, the way a drag paints. The corners may come in any order.
 */
export function paintRectangle(
  grid: ScheduleGrid,
  from: ScheduleCell,
  to: ScheduleCell,
  on: boolean,
): ScheduleGrid {
  const [firstDay, lastDay] = [Math.min(from.day, to.day), Math.max(from.day, to.day)]
  const [firstSlot, lastSlot] = [Math.min(from.slot, to.slot), Math.max(from.slot, to.slot)]
  return Object.fromEntries(
    SCHEDULE_WEEKDAYS.map((day, index) => [
      day,
      index < firstDay || index > lastDay
        ? [...grid[day]]
        : grid[day].map((value, slot) => (slot >= firstSlot && slot <= lastSlot ? on : value)),
    ]),
  ) as ScheduleGrid
}

/** Switches a whole day on, or off when it is on all day already. */
export function toggleDay(grid: ScheduleGrid, day: ScheduleWeekday): ScheduleGrid {
  const on = !grid[day].every(Boolean)
  return { ...grid, [day]: filledDay(on) }
}

/** Switches one half hour on across the week, or off when it is on every day already. */
export function toggleSlot(grid: ScheduleGrid, slot: number): ScheduleGrid {
  const on = !SCHEDULE_WEEKDAYS.every((day) => grid[day][slot])
  return paintRectangle(grid, { day: 0, slot }, { day: SCHEDULE_WEEKDAYS.length - 1, slot }, on)
}

/** Gives Tuesday to Friday the slots of Monday, the usual week in one click. */
export function copyMondayToWeekdays(grid: ScheduleGrid): ScheduleGrid {
  const copy = { ...grid }
  for (const day of SCHEDULE_WEEKDAYS.slice(1, WORKING_DAYS)) copy[day] = [...grid.monday]
  return copy
}

/** Which summary the list shows for a screen. */
export function scheduleSummary(
  infoscreen: Pick<
    InfoscreenResponse,
    'display_schedule_mode' | 'display_schedule' | 'off_on_holidays'
  >,
): ScheduleSummary {
  if (infoscreen.display_schedule_mode === 'default') return 'default'
  if (infoscreen.display_schedule_mode === 'always_on') return 'alwaysOn'
  const holidays = infoscreen.off_on_holidays === true
  if (!infoscreen.display_schedule) return holidays ? 'alwaysOnHolidays' : 'alwaysOn'
  return holidays ? 'scheduledHolidays' : 'scheduled'
}
