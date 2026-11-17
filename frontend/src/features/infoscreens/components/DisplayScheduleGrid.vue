<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { weekdayName } from '@/core/utils/dates'
import {
  SCHEDULE_WEEKDAYS,
  SLOTS_PER_DAY,
  paintRectangle,
  slotTime,
  toggleDay,
  toggleSlot,
  type ScheduleCell,
  type ScheduleGrid,
  type ScheduleWeekday,
} from '../utils/displaySchedule'

/**
 * The display times of a week as a grid, the weekdays as columns and the
 * half hours as rows, each cell on or off. A click switches one cell, and a
 * drag paints the rectangle it spans with the new state of the cell it
 * started on. A weekday header switches the whole day and a time label the
 * half hour across the week. The arrow keys move between the cells, and
 * Space or Enter switches the focused one.
 */
const props = withDefaults(
  defineProps<{
    idPrefix: string
    disabled?: boolean
    /** Days whose header is marked, because they hold more windows than the server keeps. */
    invalidDays?: readonly ScheduleWeekday[]
  }>(),
  { disabled: false, invalidDays: () => [] },
)

const grid = defineModel<ScheduleGrid>({ required: true })

const { t } = useI18n()

const SLOTS = Array.from({ length: SLOTS_PER_DAY }, (_, slot) => slot)
// The first working hour is where a keyboard user usually starts.
const FIRST_FOCUS: ScheduleCell = { day: 0, slot: 12 }

// 1 January 2024 was a Monday, so day index 0 is Monday.
function dayLabel(index: number, style: 'long' | 'short'): string {
  return weekdayName(new Date(2024, 0, 1 + index), style)
}

function cellLabel(index: number, slot: number): string {
  return t('infoscreens.schedule.cell', {
    day: dayLabel(index, 'long'),
    start: slotTime(slot),
    end: slotTime(slot + 1),
  })
}

const root = ref<HTMLElement | null>(null)
const focused = ref<ScheduleCell>({ ...FIRST_FOCUS })

function isFocused(day: number, slot: number): boolean {
  return focused.value.day === day && focused.value.slot === slot
}

interface DragState {
  anchor: ScheduleCell
  on: boolean
  base: ScheduleGrid
}

let drag: DragState | null = null

function endDrag(): void {
  drag = null
  window.removeEventListener('pointerup', endDrag)
  window.removeEventListener('pointercancel', endDrag)
}

onBeforeUnmount(endDrag)

function onCellPointerDown(event: PointerEvent, cell: ScheduleCell): void {
  if (props.disabled || event.button > 0) return
  event.preventDefault()
  // A touch keeps its pointer on the first cell; releasing it lets the
  // cells under the finger see the drag as a mouse drag does.
  const target = event.currentTarget as HTMLElement | null
  if (target?.hasPointerCapture?.(event.pointerId)) target.releasePointerCapture(event.pointerId)
  target?.focus()
  focused.value = cell
  const day = SCHEDULE_WEEKDAYS[cell.day]!
  const on = !grid.value[day][cell.slot]
  drag = { anchor: cell, on, base: grid.value }
  grid.value = paintRectangle(drag.base, cell, cell, on)
  window.addEventListener('pointerup', endDrag)
  window.addEventListener('pointercancel', endDrag)
}

function onCellPointerEnter(cell: ScheduleCell): void {
  if (!drag) return
  grid.value = paintRectangle(drag.base, drag.anchor, cell, drag.on)
}

// A pointer has switched the cell on pointerdown already; only a click from
// the keyboard, which has no click count, switches it here.
function onCellClick(event: MouseEvent, cell: ScheduleCell): void {
  if (props.disabled || event.detail !== 0) return
  focused.value = cell
  const day = SCHEDULE_WEEKDAYS[cell.day]!
  grid.value = paintRectangle(grid.value, cell, cell, !grid.value[day][cell.slot])
}

const KEY_MOVES: Record<string, ScheduleCell> = {
  ArrowUp: { day: 0, slot: -1 },
  ArrowDown: { day: 0, slot: 1 },
  ArrowLeft: { day: -1, slot: 0 },
  ArrowRight: { day: 1, slot: 0 },
}

function onCellKeydown(event: KeyboardEvent): void {
  const move = KEY_MOVES[event.key]
  if (!move) return
  event.preventDefault()
  const day = Math.min(Math.max(focused.value.day + move.day, 0), SCHEDULE_WEEKDAYS.length - 1)
  const slot = Math.min(Math.max(focused.value.slot + move.slot, 0), SLOTS_PER_DAY - 1)
  focused.value = { day, slot }
  void nextTick(() => {
    root.value?.querySelector<HTMLElement>(`[data-cell="${day}-${slot}"]`)?.focus()
  })
}

function onDayClick(day: ScheduleWeekday): void {
  if (!props.disabled) grid.value = toggleDay(grid.value, day)
}

function onSlotClick(slot: number): void {
  if (!props.disabled) grid.value = toggleSlot(grid.value, slot)
}
</script>

<template>
  <div ref="root" class="grid-scroll" :data-testid="`${idPrefix}-schedule-grid`">
    <table class="schedule-grid">
      <thead>
        <tr>
          <th scope="col" class="corner">
            <span class="sr-only">{{ t('infoscreens.schedule.time') }}</span>
          </th>
          <th v-for="(day, dayIndex) in SCHEDULE_WEEKDAYS" :key="day" scope="col">
            <button
              type="button"
              class="day-toggle"
              :class="{ invalid: invalidDays.includes(day) }"
              :disabled="disabled"
              :aria-label="t('infoscreens.schedule.toggleDay', { day: dayLabel(dayIndex, 'long') })"
              :title="t('infoscreens.schedule.toggleDay', { day: dayLabel(dayIndex, 'long') })"
              :data-testid="`${idPrefix}-schedule-day-${day}`"
              @click="onDayClick(day)"
            >
              {{ dayLabel(dayIndex, 'short') }}
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="slot in SLOTS" :key="slot" :class="{ 'hour-start': slot % 2 === 0 }">
          <th scope="row" class="time">
            <button
              type="button"
              class="slot-toggle"
              :class="{ 'half-hour': slot % 2 === 1 }"
              :disabled="disabled"
              :aria-label="t('infoscreens.schedule.toggleSlot', { time: slotTime(slot) })"
              :title="t('infoscreens.schedule.toggleSlot', { time: slotTime(slot) })"
              :data-testid="`${idPrefix}-schedule-slot-${slot}`"
              @click="onSlotClick(slot)"
            >
              {{ slotTime(slot) }}
            </button>
          </th>
          <td v-for="(day, dayIndex) in SCHEDULE_WEEKDAYS" :key="day">
            <button
              type="button"
              class="cell"
              :class="{ on: grid[day][slot] }"
              :disabled="disabled"
              :tabindex="isFocused(dayIndex, slot) ? 0 : -1"
              :aria-pressed="grid[day][slot]"
              :aria-label="cellLabel(dayIndex, slot)"
              :data-cell="`${dayIndex}-${slot}`"
              :data-testid="`${idPrefix}-schedule-cell-${day}-${slot}`"
              @pointerdown="onCellPointerDown($event, { day: dayIndex, slot })"
              @pointerenter="onCellPointerEnter({ day: dayIndex, slot })"
              @click="onCellClick($event, { day: dayIndex, slot })"
              @keydown="onCellKeydown"
            />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped lang="scss">
.grid-scroll {
  max-height: min(55vh, 30rem);
  overflow: auto;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  user-select: none;
}

.schedule-grid {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  table-layout: fixed;

  th,
  td {
    padding: 0;
  }
}

thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
}

.corner {
  width: 3.5rem;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

.day-toggle,
.slot-toggle {
  display: block;
  width: 100%;
  padding: var(--space-1);
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: var(--p-content-hover-background);
  }

  &:disabled {
    cursor: default;
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: -2px;
  }
}

.day-toggle {
  font-size: var(--font-size-sm);
  font-weight: 600;

  &.invalid {
    color: var(--p-red-500);
  }
}

.slot-toggle {
  padding: 0 var(--space-2) 0 0;
  font-size: var(--font-size-xs);
  line-height: 0.875rem;
  text-align: right;
  font-variant-numeric: tabular-nums;

  &.half-hour {
    color: var(--p-text-muted-color);
  }
}

.cell {
  display: block;
  width: 100%;
  height: 0.875rem;
  padding: 0;
  border: 0;
  border-left: 1px solid var(--p-content-border-color);
  background: transparent;
  cursor: pointer;
  touch-action: none;

  &:hover:not(:disabled) {
    background: var(--p-content-hover-background);
  }

  &.on {
    background: var(--p-primary-color);
  }

  &.on:hover:not(:disabled) {
    background: var(--p-primary-hover-color);
  }

  &:disabled {
    cursor: default;
  }

  // The text colour stands out on a cell that is on as well as off.
  &:focus-visible {
    outline: 2px solid var(--p-text-color);
    outline-offset: -2px;
  }
}

tr.hour-start > th,
tr.hour-start > td {
  border-top: 1px solid var(--p-content-border-color);
}

tbody tr:first-child > th,
tbody tr:first-child > td {
  border-top: 0;
}
</style>
