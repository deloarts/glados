import { describe, it, expect } from 'vitest'

import {
  SCHEDULE_WEEKDAYS,
  SLOTS_PER_DAY,
  copyMondayToWeekdays,
  countWindows,
  defaultGrid,
  filledGrid,
  isGridValid,
  overfullDays,
  paintRectangle,
  scheduleSummary,
  slotTime,
  slotsToWindows,
  toScheduleGrid,
  toScheduleRequest,
  toggleDay,
  toggleSlot,
  windowsToSlots,
} from '../displaySchedule'

/** The slots that are on, as their indexes. */
function onSlots(slots: boolean[]): number[] {
  return slots.flatMap((on, slot) => (on ? [slot] : []))
}

function range(first: number, last: number): number[] {
  return Array.from({ length: last - first + 1 }, (_, index) => first + index)
}

describe('displaySchedule slots and windows', () => {
  it('has 48 half hours a day, the last one ending at 24:00', () => {
    expect(SLOTS_PER_DAY).toBe(48)
    expect(slotTime(0)).toBe('00:00')
    expect(slotTime(13)).toBe('06:30')
    expect(slotTime(48)).toBe('24:00')
  })

  it('turns windows into slots and back without loss', () => {
    const windows = [
      { start: '00:00', end: '06:00' },
      { start: '07:30', end: '12:00' },
      { start: '22:00', end: '24:00' },
    ]

    const { slots, rounded } = windowsToSlots(windows)

    expect(rounded).toBe(false)
    expect(onSlots(slots)).toEqual([...range(0, 11), ...range(15, 23), 44, 45, 46, 47])
    expect(slotsToWindows(slots)).toEqual(windows)
  })

  it('joins windows that touch into one', () => {
    const { slots } = windowsToSlots([
      { start: '06:00', end: '12:00' },
      { start: '12:00', end: '18:00' },
    ])

    expect(slotsToWindows(slots)).toEqual([{ start: '06:00', end: '18:00' }])
  })

  it('widens a window off the half hours to the half hours around it and says so', () => {
    const { slots, rounded } = windowsToSlots([{ start: '06:10', end: '17:45' }])

    expect(rounded).toBe(true)
    expect(slotsToWindows(slots)).toEqual([{ start: '06:00', end: '18:00' }])
  })

  it('loads a stored schedule, fills the days the server left out and reports rounding', () => {
    expect(toScheduleGrid(null)).toEqual({ grid: null, rounded: false })

    const exact = toScheduleGrid({ monday: [{ start: '07:00', end: '17:00' }] })
    expect(exact.rounded).toBe(false)
    expect(Object.keys(exact.grid!)).toEqual([...SCHEDULE_WEEKDAYS])
    expect(onSlots(exact.grid!.monday)).toEqual(range(14, 33))
    expect(onSlots(exact.grid!.sunday)).toEqual([])

    expect(toScheduleGrid({ friday: [{ start: '07:15', end: '17:00' }] }).rounded).toBe(true)
  })

  it('sends every day with its windows in time order', () => {
    const grid = filledGrid(false)
    grid.monday = windowsToSlots([
      { start: '13:00', end: '18:00' },
      { start: '06:00', end: '12:00' },
    ]).slots

    const request = toScheduleRequest(grid)

    expect(request.monday).toEqual([
      { start: '06:00', end: '12:00' },
      { start: '13:00', end: '18:00' },
    ])
    expect(request.sunday).toEqual([])
    expect(Object.keys(request)).toEqual([...SCHEDULE_WEEKDAYS])
  })

  it('starts a new schedule with six to six on working days and the weekend off', () => {
    const request = toScheduleRequest(defaultGrid())

    for (const day of ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'] as const) {
      expect(request[day]).toEqual([{ start: '06:00', end: '18:00' }])
    }
    expect(request.saturday).toEqual([])
    expect(request.sunday).toEqual([])
  })
})

describe('displaySchedule six windows a day', () => {
  // Every other half hour from midnight: one window per on slot.
  function alternating(windows: number): boolean[] {
    return Array.from({ length: SLOTS_PER_DAY }, (_, slot) => slot % 2 === 0 && slot < windows * 2)
  }

  it('counts the windows a day would be stored as', () => {
    expect(countWindows(alternating(0))).toBe(0)
    expect(countWindows(alternating(6))).toBe(6)
    expect(countWindows(filledGrid(true).monday)).toBe(1)
  })

  it('accepts six windows and refuses a seventh', () => {
    const grid = filledGrid(false)
    grid.tuesday = alternating(6)
    expect(overfullDays(grid)).toEqual([])
    expect(isGridValid(grid)).toBe(true)

    grid.tuesday = alternating(7)
    expect(overfullDays(grid)).toEqual(['tuesday'])
    expect(isGridValid(grid)).toBe(false)
  })

  it('always accepts no schedule', () => {
    expect(isGridValid(null)).toBe(true)
    expect(overfullDays(null)).toEqual([])
  })
})

describe('displaySchedule painting', () => {
  it('paints the rectangle between two corners in either order and leaves the rest', () => {
    const grid = filledGrid(false)
    grid.sunday[0] = true

    const painted = paintRectangle(grid, { day: 3, slot: 20 }, { day: 1, slot: 17 }, true)

    for (const day of ['tuesday', 'wednesday', 'thursday'] as const) {
      expect(onSlots(painted[day])).toEqual(range(17, 20))
    }
    expect(onSlots(painted.monday)).toEqual([])
    expect(onSlots(painted.friday)).toEqual([])
    expect(onSlots(painted.sunday)).toEqual([0])
    // The grid it started from stays as it was.
    expect(onSlots(grid.tuesday)).toEqual([])
  })

  it('paints off as well as on', () => {
    const painted = paintRectangle(filledGrid(true), { day: 0, slot: 0 }, { day: 0, slot: 11 }, false)

    expect(slotsToWindows(painted.monday)).toEqual([{ start: '06:00', end: '24:00' }])
    expect(slotsToWindows(painted.tuesday)).toEqual([{ start: '00:00', end: '24:00' }])
  })

  it('switches a day on, and off once it is on all day', () => {
    const grid = defaultGrid()

    const on = toggleDay(grid, 'monday')
    expect(on.monday.every(Boolean)).toBe(true)
    expect(toggleDay(on, 'monday').monday.some(Boolean)).toBe(false)
    expect(on.tuesday).toEqual(grid.tuesday)
  })

  it('switches a half hour across the week, and off once it is on every day', () => {
    const grid = defaultGrid()

    const on = toggleSlot(grid, 4)
    expect(SCHEDULE_WEEKDAYS.every((day) => on[day][4])).toBe(true)
    const off = toggleSlot(on, 4)
    expect(SCHEDULE_WEEKDAYS.some((day) => off[day][4])).toBe(false)
  })

  it('copies Monday to Tuesday to Friday and keeps the weekend', () => {
    const grid = filledGrid(false)
    grid.monday = windowsToSlots([{ start: '05:30', end: '22:00' }]).slots
    grid.saturday = windowsToSlots([{ start: '06:00', end: '12:00' }]).slots

    const copied = copyMondayToWeekdays(grid)

    for (const day of ['tuesday', 'wednesday', 'thursday', 'friday'] as const) {
      expect(slotsToWindows(copied[day])).toEqual([{ start: '05:30', end: '22:00' }])
    }
    expect(slotsToWindows(copied.saturday)).toEqual([{ start: '06:00', end: '12:00' }])
    expect(copied.tuesday).not.toBe(copied.monday)
  })
})

describe('displaySchedule summary', () => {
  it('sums up an own schedule as always on or scheduled, with or without holidays', () => {
    const schedule = { monday: [{ start: '06:00', end: '18:00' }] }
    const own = 'own' as const

    expect(
      scheduleSummary({ display_schedule_mode: own, display_schedule: null, off_on_holidays: false }),
    ).toBe('alwaysOn')
    expect(
      scheduleSummary({ display_schedule_mode: own, display_schedule: null, off_on_holidays: true }),
    ).toBe('alwaysOnHolidays')
    expect(
      scheduleSummary({ display_schedule_mode: own, display_schedule: schedule, off_on_holidays: false }),
    ).toBe('scheduled')
    expect(
      scheduleSummary({ display_schedule_mode: own, display_schedule: schedule, off_on_holidays: true }),
    ).toBe('scheduledHolidays')
  })

  it('sums up a screen following the default or always on by its mode alone', () => {
    const schedule = { monday: [{ start: '06:00', end: '18:00' }] }

    expect(
      scheduleSummary({ display_schedule_mode: 'default', display_schedule: schedule, off_on_holidays: true }),
    ).toBe('default')
    expect(
      scheduleSummary({
        display_schedule_mode: 'always_on',
        display_schedule: schedule,
        off_on_holidays: true,
      }),
    ).toBe('alwaysOn')
  })
})
