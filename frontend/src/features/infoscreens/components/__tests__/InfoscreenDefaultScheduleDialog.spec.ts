import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

import type {
  DisplayScheduleDefault,
  DisplayScheduleDefaultRequest,
  InfoscreenDisplaySchedule,
} from '../../types/infoscreenResponse'

const getMock = vi.fn<() => Promise<DisplayScheduleDefault>>()
const setMock = vi.fn<(body: DisplayScheduleDefaultRequest) => Promise<DisplayScheduleDefault>>()

vi.mock('../../api/infoscreensApi', () => ({
  getDisplayScheduleDefault: () => getMock(),
  setDisplayScheduleDefault: (body: DisplayScheduleDefaultRequest) => setMock(body),
}))

import InfoscreenDefaultScheduleDialog from '../InfoscreenDefaultScheduleDialog.vue'

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

let wrapper: VueWrapper | null = null

async function openDialog(canWrite = true, followingCount = 2) {
  wrapper = mountWithApp(InfoscreenDefaultScheduleDialog, {
    attachTo: document.body,
    props: { visible: false, followingCount, canWrite, missingHint: canWrite ? '' : MISSING },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function save(): Promise<void> {
  byTestId('default-schedule-save')!.click()
  await flushPromises()
}

describe('InfoscreenDefaultScheduleDialog', () => {
  beforeEach(() => {
    getMock.mockReset()
    setMock.mockReset()
    getMock.mockResolvedValue({ display_schedule: null, off_on_holidays: false })
    setMock.mockImplementation(async (body) => ({
      display_schedule: body.display_schedule ?? null,
      off_on_holidays: body.off_on_holidays ?? false,
    }))
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('loads the stored default and saves the grid with the holiday switch', async () => {
    getMock.mockResolvedValue({
      display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:00', end: '18:00' }] },
      off_on_holidays: false,
    })
    const w = await openDialog()

    expect(document.body.textContent).toContain('2 infoscreens follow these times')
    expect(byTestId('default-schedule-schedule-mode')).toBeNull()
    expect(byTestId('default-schedule-schedule-cell-monday-12')!.getAttribute('aria-pressed')).toBe(
      'true',
    )
    byTestId<HTMLInputElement>('default-schedule-off-on-holidays')!.click()
    await flushPromises()
    await save()

    expect(setMock).toHaveBeenCalledTimes(1)
    const body = setMock.mock.calls[0]![0]
    expect(body.off_on_holidays).toBe(true)
    expect(body.display_schedule).toEqual({
      ...EMPTY_WEEK,
      monday: [{ start: '06:00', end: '18:00' }],
    })
    expect(w.emitted('saved')).toHaveLength(1)
  })

  it('keeps the displays on when Always on is ticked', async () => {
    getMock.mockResolvedValue({
      display_schedule: { ...EMPTY_WEEK, monday: [{ start: '06:00', end: '18:00' }] },
      off_on_holidays: false,
    })
    await openDialog()

    byTestId<HTMLInputElement>('default-schedule-schedule-always-on')!.click()
    await flushPromises()
    await save()

    expect(setMock.mock.calls[0]![0]).toEqual({ display_schedule: null, off_on_holidays: false })
  })

  it('opens read only and cannot save without the permission', async () => {
    getMock.mockResolvedValue({ display_schedule: EMPTY_WEEK, off_on_holidays: false })
    await openDialog(false)

    const saveButton = byTestId<HTMLButtonElement>('default-schedule-save')!
    expect(saveButton.disabled).toBe(true)
    expect(byTestId<HTMLButtonElement>('default-schedule-schedule-cell-monday-12')!.disabled).toBe(
      true,
    )
    saveButton.click()
    await flushPromises()
    expect(setMock).not.toHaveBeenCalled()
  })

  it('shows why nothing can be edited when the default does not load, and saves nothing', async () => {
    getMock.mockRejectedValue(new Error('Network Error'))
    await openDialog()

    expect(byTestId('default-schedule-unavailable')).not.toBeNull()
    expect(byTestId('default-schedule-schedule')).toBeNull()
    const saveButton = byTestId<HTMLButtonElement>('default-schedule-save')!
    expect(saveButton.disabled).toBe(true)
    saveButton.click()
    await flushPromises()
    expect(setMock).not.toHaveBeenCalled()
  })

  it('shows a spinner while the default loads', async () => {
    getMock.mockReturnValue(new Promise(() => {}))
    await openDialog()

    expect(byTestId('default-schedule-loading')).not.toBeNull()
    expect(byTestId<HTMLButtonElement>('default-schedule-save')!.disabled).toBe(true)
  })
})
