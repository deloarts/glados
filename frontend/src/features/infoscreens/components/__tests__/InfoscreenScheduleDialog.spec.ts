import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { defaultWidget } from '../../utils/infoscreenLayouts'

import type {
  InfoscreenDisplaySchedule,
  InfoscreenResponse,
  InfoscreenUpdateRequest,
} from '../../types/infoscreenResponse'

const updateMock = vi.fn<(id: number, body: InfoscreenUpdateRequest) => Promise<InfoscreenResponse>>()

vi.mock('../../api/infoscreensApi', () => ({
  updateInfoscreen: (id: number, body: InfoscreenUpdateRequest) => updateMock(id, body),
}))

import InfoscreenScheduleDialog from '../InfoscreenScheduleDialog.vue'

const MISSING = 'This needs the permission Write Infoscreens.'
const EMPTY_WEEK: InfoscreenDisplaySchedule = {
  monday: [],
  tuesday: [],
  wednesday: [],
  thursday: [],
  friday: [],
  saturday: [],
  sunday: [],
}

function makeInfoscreen(overrides: Partial<InfoscreenResponse> = {}): InfoscreenResponse {
  return {
    id: 4,
    name: 'Hall board',
    description: null,
    color_mode: 'dark',
    theme_preset: null,
    primary_color: null,
    rotation_seconds: 30,
    show_banner: true,
    show_header: true,
    header: { left: ['logo', 'title'], center: [], right: ['clock'], text: null },
    show_footer: false,
    footer: { left: [], center: [], right: ['last_updated'], text: null },
    display_schedule_mode: 'own',
    display_schedule: null,
    off_on_holidays: false,
    language: null,
    pages: [{ layout: 'full', slots: [defaultWidget('clock')] }],
    shown_on: [{ id: 1, name: 'Hall 1' }],
    archived: false,
    created: '2026-10-29T08:00:00Z',
    changed: null,
    ...overrides,
  } as InfoscreenResponse
}

let wrapper: VueWrapper | null = null

async function openDialog(infoscreen: InfoscreenResponse, canWrite = true) {
  wrapper = mountWithApp(InfoscreenScheduleDialog, {
    attachTo: document.body,
    props: { visible: false, infoscreen, canWrite, missingHint: canWrite ? '' : MISSING },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

function cell(day: string, slot: number): HTMLButtonElement {
  return byTestId<HTMLButtonElement>(`schedule-dialog-schedule-cell-${day}-${slot}`)!
}

async function fire(element: Element, type: string): Promise<void> {
  element.dispatchEvent(new Event(type, { bubbles: type !== 'pointerenter' }))
  await flushPromises()
}

async function pickMode(label: string): Promise<void> {
  const options = byTestId('schedule-dialog-schedule-mode')!.querySelectorAll('button')
  const option = [...options].find((button) => button.textContent?.trim() === label)
  option!.click()
  await flushPromises()
}

async function save(): Promise<void> {
  byTestId('schedule-dialog-save')!.click()
  await flushPromises()
}

describe('InfoscreenScheduleDialog', () => {
  beforeEach(() => {
    updateMock.mockReset()
    updateMock.mockImplementation(async (_id, body) => makeInfoscreen(body as Partial<InfoscreenResponse>))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('saves the mode, and its own schedule only while the screen follows it', async () => {
    const w = await openDialog(makeInfoscreen({ display_schedule_mode: 'default' }))
    expect(byTestId('schedule-dialog-schedule-grid')).toBeNull()
    expect(byTestId('schedule-dialog-schedule-default-hint')).not.toBeNull()

    await pickMode('Own Schedule')
    expect(byTestId('schedule-dialog-schedule-grid')).not.toBeNull()
    byTestId<HTMLInputElement>('schedule-dialog-off-on-holidays')!.click()
    await flushPromises()
    await save()

    expect(updateMock).toHaveBeenCalledTimes(1)
    const [id, body] = updateMock.mock.calls[0]!
    expect(id).toBe(4)
    expect(Object.keys(body).sort()).toEqual([
      'display_schedule',
      'display_schedule_mode',
      'off_on_holidays',
    ])
    expect(body.display_schedule_mode).toBe('own')
    expect(body.off_on_holidays).toBe(true)
    expect(body.display_schedule).toEqual({
      ...EMPTY_WEEK,
      monday: [{ start: '06:00', end: '18:00' }],
      tuesday: [{ start: '06:00', end: '18:00' }],
      wednesday: [{ start: '06:00', end: '18:00' }],
      thursday: [{ start: '06:00', end: '18:00' }],
      friday: [{ start: '06:00', end: '18:00' }],
    })
    expect(w.emitted('saved')).toHaveLength(1)
  })

  it('switches a screen to always on and leaves its own schedule as it is', async () => {
    await openDialog(
      makeInfoscreen({
        display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:00', end: '18:00' }] },
      }),
    )
    expect(byTestId('schedule-dialog-schedule-always-on')).toBeNull()

    await pickMode('Always On')
    expect(byTestId('schedule-dialog-schedule-grid')).toBeNull()
    await save()

    expect(updateMock.mock.calls[0]![1]).toEqual({ display_schedule_mode: 'always_on' })
  })

  it('shows every half hour on for an own schedule stored with only the holiday switch', async () => {
    await openDialog(makeInfoscreen({ display_schedule: null, off_on_holidays: true }))
    await save()

    const schedule = updateMock.mock.calls[0]![1].display_schedule!
    expect(schedule.monday).toEqual([{ start: '00:00', end: '24:00' }])
    expect(schedule.sunday).toEqual([{ start: '00:00', end: '24:00' }])
    expect(updateMock.mock.calls[0]![1].off_on_holidays).toBe(true)
  })

  it('switches a cell on a click and paints a rectangle on a drag', async () => {
    await openDialog(makeInfoscreen({ display_schedule: EMPTY_WEEK }))

    // A click from the keyboard has no click count and switches one cell.
    cell('sunday', 0).click()
    await flushPromises()
    expect(cell('sunday', 0).getAttribute('aria-pressed')).toBe('true')

    // A drag from Monday 08:00 to Wednesday 09:30 paints with the new state of its first cell.
    await fire(cell('monday', 16), 'pointerdown')
    await fire(cell('tuesday', 17), 'pointerenter')
    await fire(cell('wednesday', 19), 'pointerenter')
    window.dispatchEvent(new Event('pointerup'))
    await flushPromises()
    // Moving over a cell after the drag ended paints nothing.
    await fire(cell('friday', 30), 'pointerenter')
    await save()

    expect(updateMock.mock.calls[0]![1].display_schedule).toEqual({
      ...EMPTY_WEEK,
      monday: [{ start: '08:00', end: '10:00' }],
      tuesday: [{ start: '08:00', end: '10:00' }],
      wednesday: [{ start: '08:00', end: '10:00' }],
      sunday: [{ start: '00:00', end: '00:30' }],
    })
  })

  it('drags off when the first cell was on, and takes back what the drag left', async () => {
    await openDialog(
      makeInfoscreen({
        display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:00', end: '18:00' }] },
      }),
    )

    await fire(cell('monday', 12), 'pointerdown')
    await fire(cell('monday', 30), 'pointerenter')
    // Moving back shrinks the rectangle, so the cells it left are on again.
    await fire(cell('monday', 15), 'pointerenter')
    window.dispatchEvent(new Event('pointerup'))
    await flushPromises()
    await save()

    expect(updateMock.mock.calls[0]![1].display_schedule!.monday).toEqual([
      { start: '08:00', end: '18:00' },
    ])
  })

  it('switches a whole day from its header and a half hour from its time', async () => {
    await openDialog(makeInfoscreen({ display_schedule: EMPTY_WEEK }))

    byTestId('schedule-dialog-schedule-day-saturday')!.click()
    await flushPromises()
    byTestId('schedule-dialog-schedule-slot-47')!.click()
    await flushPromises()
    await save()

    const schedule = updateMock.mock.calls[0]![1].display_schedule!
    expect(schedule.saturday).toEqual([{ start: '00:00', end: '24:00' }])
    expect(schedule.monday).toEqual([{ start: '23:30', end: '24:00' }])
    expect(schedule.sunday).toEqual([{ start: '23:30', end: '24:00' }])
  })

  it('copies Monday to the weekdays and switches everything on or off', async () => {
    await openDialog(
      makeInfoscreen({
        display_schedule: { ...EMPTY_WEEK, monday: [{ start: '05:30', end: '22:00' }] },
      }),
    )

    byTestId('schedule-dialog-schedule-copy-monday')!.click()
    await flushPromises()
    expect(cell('friday', 10).getAttribute('aria-pressed')).toBe('false')
    expect(cell('friday', 11).getAttribute('aria-pressed')).toBe('true')
    expect(cell('friday', 43).getAttribute('aria-pressed')).toBe('true')
    expect(cell('saturday', 11).getAttribute('aria-pressed')).toBe('false')

    byTestId('schedule-dialog-schedule-all-on')!.click()
    await flushPromises()
    expect(cell('sunday', 0).getAttribute('aria-pressed')).toBe('true')
    byTestId('schedule-dialog-schedule-all-off')!.click()
    await flushPromises()
    expect(cell('monday', 20).getAttribute('aria-pressed')).toBe('false')
  })

  it('shows a stored window off the half hours widened, with a note', async () => {
    await openDialog(
      makeInfoscreen({
        display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:10', end: '17:45' }] },
      }),
    )

    expect(byTestId('schedule-dialog-schedule-rounded')!.textContent).toContain(
      i18n.global.t('infoscreens.schedule.roundedNote'),
    )
    await save()

    expect(updateMock.mock.calls[0]![1].display_schedule!.monday).toEqual([
      { start: '06:00', end: '18:00' },
    ])
  })

  it('refuses a day with more than six windows before calling the server', async () => {
    await openDialog(makeInfoscreen({ display_schedule: EMPTY_WEEK }))

    for (const slot of [0, 2, 4, 6, 8, 10, 12]) {
      cell('thursday', slot).click()
      await flushPromises()
    }
    await save()

    expect(updateMock).not.toHaveBeenCalled()
    expect(byTestId('schedule-dialog-schedule-thursday-error')).not.toBeNull()
    expect(document.body.textContent).toContain(i18n.global.t('infoscreens.errors.schedule'))
  })

  it('opens read only and keeps Save disabled without write:infoscreens', async () => {
    await openDialog(
      makeInfoscreen({
        display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:00', end: '18:00' }] },
      }),
      false,
    )

    expect(cell('monday', 0).disabled).toBe(true)
    expect(byTestId<HTMLButtonElement>('schedule-dialog-schedule-all-on')!.disabled).toBe(true)
    const button = byTestId<HTMLButtonElement>('schedule-dialog-save')!
    expect(button.disabled).toBe(true)
    button.click()
    await flushPromises()
    expect(updateMock).not.toHaveBeenCalled()
  })
})
