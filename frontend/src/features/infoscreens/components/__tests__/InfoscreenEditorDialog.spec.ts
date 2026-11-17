import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { defaultWidget } from '../../utils/infoscreenLayouts'

import type {
  InfoscreenCreateRequest,
  InfoscreenResponse,
  InfoscreenUpdateRequest,
} from '../../types/infoscreenResponse'

const createMock = vi.fn<(body: InfoscreenCreateRequest) => Promise<InfoscreenResponse>>()
const updateMock = vi.fn<(id: number, body: InfoscreenUpdateRequest) => Promise<InfoscreenResponse>>()

vi.mock('../../api/infoscreensApi', () => ({
  createInfoscreen: (body: InfoscreenCreateRequest) => createMock(body),
  updateInfoscreen: (id: number, body: InfoscreenUpdateRequest) => updateMock(id, body),
}))

vi.mock('@/features/production-machines', () => ({
  getProductionMachines: async () => ({ items: [], total: 0, limit: 100, skip: 0 }),
  getMachinePools: async () => ({ items: [], total: 0, limit: 100, skip: 0 }),
}))

import InfoscreenEditorDialog from '../InfoscreenEditorDialog.vue'

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
    pages: [{ layout: 'two_columns', slots: [defaultWidget('clock'), null] }],
    shown_on: [],
    archived: false,
    created: '2026-10-29T08:00:00Z',
    changed: null,
    ...overrides,
  } as InfoscreenResponse
}

let wrapper: VueWrapper | null = null

async function openEditor(infoscreen: InfoscreenResponse | null, canWrite = true) {
  wrapper = mountWithApp(InfoscreenEditorDialog, {
    attachTo: document.body,
    props: {
      visible: false,
      infoscreen,
      canWrite,
      missingHint: canWrite ? '' : 'This needs the permission Write Infoscreens.',
    },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function typeName(value: string): Promise<void> {
  const input = byTestId<HTMLInputElement>('infoscreen-name')!
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

async function save(): Promise<void> {
  byTestId('infoscreen-save')!.click()
  await flushPromises()
}

describe('InfoscreenEditorDialog', () => {
  beforeEach(() => {
    createMock.mockReset()
    updateMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('creates a dark screen with one full page by default', async () => {
    createMock.mockResolvedValue(makeInfoscreen())
    const w = await openEditor(null)

    await typeName(' Hall board ')
    await save()

    expect(createMock).toHaveBeenCalledWith({
      name: 'Hall board',
      description: null,
      color_mode: 'dark',
      theme_preset: null,
      primary_color: null,
      language: null,
      rotation_seconds: 30,
      show_banner: true,
      show_header: true,
      header: { left: ['logo', 'title'], center: [], right: ['clock'], text: null },
      show_footer: false,
      footer: { left: [], center: [], right: ['last_updated'], text: null },
      display_schedule_mode: 'default',
      display_schedule: null,
      off_on_holidays: false,
      pages: [{ layout: 'full', slots: [null] }],
    })
    expect(w.emitted('saved')).toHaveLength(1)
  })

  it('lets a new screen follow the default schedule without a grid', async () => {
    await openEditor(null)

    expect(byTestId('infoscreen-schedule-default-hint')).not.toBeNull()
    expect(byTestId('infoscreen-schedule-grid')).toBeNull()
  })

  it('asks for a name first', async () => {
    await openEditor(null)

    await save()

    expect(createMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('infoscreens.errors.nameRequired'))
  })

  it('adds a page and saves the edited screen with its pages', async () => {
    updateMock.mockResolvedValue(makeInfoscreen())
    await openEditor(makeInfoscreen())

    byTestId('infoscreen-add-page')!.click()
    await flushPromises()
    expect(document.body.querySelectorAll('[data-testid="infoscreen-page"]')).toHaveLength(2)

    await save()

    expect(updateMock).toHaveBeenCalledWith(
      4,
      expect.objectContaining({
        pages: [
          { layout: 'two_columns', slots: [defaultWidget('clock'), null] },
          { layout: 'full', slots: [null] },
        ],
      }),
    )
  })

  it('refuses a message widget without text', async () => {
    await openEditor(
      makeInfoscreen({ pages: [{ layout: 'full', slots: [defaultWidget('message')] }] }),
    )

    await save()

    expect(updateMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('infoscreens.errors.messageText'))
  })

  it('saves a footer with a custom text and asks for that text first', async () => {
    updateMock.mockResolvedValue(makeInfoscreen())
    await openEditor(
      makeInfoscreen({
        show_footer: true,
        footer: { left: ['text'], center: [], right: ['last_updated'], text: null },
      }),
    )

    await save()
    expect(updateMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('infoscreens.errors.barText'))

    const input = byTestId<HTMLInputElement>('infoscreen-footer-text')!
    input.value = ' Visitors please register at reception '
    input.dispatchEvent(new Event('input'))
    await flushPromises()
    await save()

    expect(updateMock).toHaveBeenCalledWith(
      4,
      expect.objectContaining({
        show_footer: true,
        footer: {
          left: ['text'],
          center: [],
          right: ['last_updated'],
          text: 'Visitors please register at reception',
        },
      }),
    )
  })

  it('saves display times and switching off on holidays', async () => {
    updateMock.mockResolvedValue(makeInfoscreen())
    await openEditor(makeInfoscreen())
    // An own schedule is always a grid, starting with the usual working hours.
    expect(byTestId('infoscreen-schedule-always-on')).toBeNull()

    byTestId('infoscreen-schedule-day-saturday')!.click()
    await flushPromises()
    byTestId<HTMLInputElement>('infoscreen-off-on-holidays')!.click()
    await flushPromises()
    await save()

    const body = updateMock.mock.calls[0]![1]
    expect(body.display_schedule_mode).toBe('own')
    expect(body.off_on_holidays).toBe(true)
    expect(body.display_schedule).toEqual({
      monday: [{ start: '06:00', end: '18:00' }],
      tuesday: [{ start: '06:00', end: '18:00' }],
      wednesday: [{ start: '06:00', end: '18:00' }],
      thursday: [{ start: '06:00', end: '18:00' }],
      friday: [{ start: '06:00', end: '18:00' }],
      saturday: [{ start: '00:00', end: '24:00' }],
      sunday: [],
    })
  })

  it('shows a stored schedule in the grid and sends it back unchanged', async () => {
    updateMock.mockResolvedValue(makeInfoscreen())
    await openEditor(
      makeInfoscreen({
        display_schedule: {
          monday: [{ start: '22:00', end: '24:00' }],
          tuesday: [{ start: '00:00', end: '06:00' }],
          wednesday: [],
          thursday: [],
          friday: [],
          saturday: [],
          sunday: [],
        },
      }),
    )

    const lastMonday = byTestId('infoscreen-schedule-cell-monday-47')!
    expect(lastMonday.getAttribute('aria-pressed')).toBe('true')
    expect(byTestId('infoscreen-schedule-cell-monday-43')!.getAttribute('aria-pressed')).toBe('false')
    expect(byTestId('infoscreen-schedule-rounded')).toBeNull()
    await save()

    expect(updateMock.mock.calls[0]![1].display_schedule).toMatchObject({
      monday: [{ start: '22:00', end: '24:00' }],
      tuesday: [{ start: '00:00', end: '06:00' }],
    })
  })

  it('refuses a day with more than six display times before calling the server', async () => {
    await openEditor(
      makeInfoscreen({
        display_schedule: {
          monday: ['00', '02', '04', '06', '08', '10', '12'].map((hour) => ({
            start: `${hour}:00`,
            end: `${hour}:30`,
          })),
          tuesday: [],
          wednesday: [],
          thursday: [],
          friday: [],
          saturday: [],
          sunday: [],
        },
      }),
    )

    await save()

    expect(updateMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('infoscreens.errors.schedule'))
    expect(byTestId('infoscreen-schedule-monday-error')).not.toBeNull()
  })

  it('offers the default of this installation and each app language', async () => {
    const w = await openEditor(makeInfoscreen({ language: 'deAT' }))

    const select = w
      .findAllComponents({ name: 'Select' })
      .find((c) => c.attributes('data-testid') === 'infoscreen-language')!
    expect(select.props('modelValue')).toBe('deAT')
    expect((select.props('options') as { value: string | null }[]).map((o) => o.value)).toEqual([
      null,
      'enGB',
      'deAT',
    ])
  })

  it('keeps Save visible but disabled without write:infoscreens', async () => {
    await openEditor(makeInfoscreen(), false)

    const button = byTestId<HTMLButtonElement>('infoscreen-save')!
    expect(button.disabled).toBe(true)
    button.click()
    await flushPromises()
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('offers a preview for a saved screen only', async () => {
    const w = await openEditor(makeInfoscreen())
    const preview = [...document.body.querySelectorAll('button')].find((b) =>
      b.textContent?.includes(i18n.global.t('infoscreens.actions.preview')),
    )
    preview!.click()
    await flushPromises()
    expect(w.emitted('preview')).toHaveLength(1)

    w.unmount()
    document.body.innerHTML = ''
    await openEditor(null)
    const none = [...document.body.querySelectorAll('button')].find((b) =>
      b.textContent?.includes(i18n.global.t('infoscreens.actions.preview')),
    )
    expect(none).toBeUndefined()
  })
})
