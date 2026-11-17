import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import InfoscreensTable from '../InfoscreensTable.vue'

import type { Schemas } from '@/core/api/generated'
import type { InfoscreenResponse } from '../../types/infoscreenResponse'

function makeInfoscreen(overrides: Partial<InfoscreenResponse> = {}): InfoscreenResponse {
  return {
    id: 4,
    name: 'Hall board',
    description: 'Entrance of hall 1',
    color_mode: 'dark',
    theme_preset: null,
    primary_color: null,
    rotation_seconds: 45,
    show_banner: true,
    pages: [{ layout: 'full', slots: [null] }],
    shown_on: [{ id: 1, name: 'Hall 1' }, { id: 2, name: null }],
    archived: false,
    language: null,
    created: '2026-10-29T08:00:00Z',
    changed: null,
    ...overrides,
  } as InfoscreenResponse
}

function mountTable(
  rows: InfoscreenResponse[],
  canWrite = true,
  defaultLanguage = 'enGB',
  showActions = true,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  usePublicBrandingStore().branding = {
    default_language: defaultLanguage,
  } as Schemas['PublicBrandingResponse']
  return mountWithApp(InfoscreensTable, {
    pinia,
    props: {
      infoscreens: rows,
      showArchived: true,
      showActions,
      canWrite,
      missingHint: canWrite ? '' : 'missing',
    },
  })
}

describe('InfoscreensTable', () => {
  it('lists the terminals a screen is shown on', async () => {
    const wrapper = mountTable([makeInfoscreen()])
    await flushPromises()

    const shownOn = wrapper.get('[data-testid="infoscreen-shown-on"]').text()
    expect(shownOn).toContain('Hall 1')
    expect(shownOn).toContain(i18n.global.t('infoscreens.unnamedTerminal'))
    expect(wrapper.text()).toContain('45 s')
  })

  it('says when a screen is shown nowhere', async () => {
    const wrapper = mountTable([makeInfoscreen({ shown_on: [] })])
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('infoscreens.notShown'))
  })

  it('offers Restore for an archived screen and Archive otherwise', async () => {
    const wrapper = mountTable([makeInfoscreen(), makeInfoscreen({ id: 5, archived: true })])
    await flushPromises()

    expect(wrapper.findAll('[data-testid="infoscreen-archive"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-testid="infoscreen-restore"]')).toHaveLength(1)
  })

  it('disables archiving without write:infoscreens but keeps the preview', async () => {
    const wrapper = mountTable([makeInfoscreen()], false)
    await flushPromises()

    const archive = wrapper.get('[data-testid="infoscreen-archive"]')
    expect(archive.attributes('disabled')).toBeDefined()
    await archive.trigger('click')
    expect(wrapper.emitted('archive')).toBeUndefined()

    await wrapper.get('[data-testid="infoscreen-preview"]').trigger('click')
    expect(wrapper.emitted('preview')).toHaveLength(1)
  })

  it('opens the editor on a row click but not on a click on its actions', async () => {
    const wrapper = mountTable([makeInfoscreen()])
    await flushPromises()

    await wrapper.get('[data-testid="infoscreen-preview"]').trigger('click')
    expect(wrapper.emitted('open')).toBeUndefined()

    await wrapper.get('tbody tr td:nth-child(3)').trigger('click')
    expect(wrapper.emitted('open')).toHaveLength(1)
  })

  it('shows the language of a screen, or the default with what it resolves to', async () => {
    const wrapper = mountTable(
      [makeInfoscreen({ id: 4, language: 'deAT' }), makeInfoscreen({ id: 5, language: null })],
      true,
      'enGB',
    )
    await flushPromises()

    const cells = wrapper.findAll('[data-testid="infoscreen-language"]').map((cell) => cell.text())
    expect(cells).toEqual([
      'Deutsch',
      i18n.global.t('infoscreens.languageDefaultResolved', { language: 'English' }),
    ])
  })

  it('sums up when the displays of each screen are on', async () => {
    const schedule = { monday: [{ start: '06:00', end: '18:00' }] }
    const wrapper = mountTable([
      makeInfoscreen({ id: 4, display_schedule: null, off_on_holidays: false }),
      makeInfoscreen({ id: 5, display_schedule: schedule, off_on_holidays: false }),
      makeInfoscreen({ id: 6, display_schedule: schedule, off_on_holidays: true }),
    ])
    await flushPromises()

    const cells = wrapper.findAll('[data-testid="infoscreen-schedule-summary"]').map((c) => c.text())
    expect(cells).toEqual([
      i18n.global.t('infoscreens.scheduleSummary.alwaysOn'),
      i18n.global.t('infoscreens.scheduleSummary.scheduled'),
      i18n.global.t('infoscreens.scheduleSummary.scheduledHolidays'),
    ])
  })

  it('offers the display schedule as a row action, disabled without write:infoscreens', async () => {
    const screen = makeInfoscreen()
    const wrapper = mountTable([screen])
    await flushPromises()

    await wrapper.get('[data-testid="infoscreen-display-schedule"]').trigger('click')
    expect(wrapper.emitted('schedule')).toEqual([[screen]])

    const readOnly = mountTable([screen], false)
    await flushPromises()
    const button = readOnly.get('[data-testid="infoscreen-display-schedule"]')
    expect(button.attributes('disabled')).toBeDefined()
    await button.trigger('click')
    expect(readOnly.emitted('schedule')).toBeUndefined()
  })

  it('leaves the actions column out while Show Actions is off', async () => {
    const wrapper = mountTable([makeInfoscreen()], true, 'enGB', false)
    await flushPromises()

    expect(wrapper.text()).not.toContain(i18n.global.t('infoscreens.columns.actions'))
    expect(wrapper.find('[data-testid="infoscreen-preview"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="infoscreen-display-schedule"]').exists()).toBe(false)
  })
})

describe('InfoscreensTable context menu', () => {
  type Item = { label?: string; separator?: boolean; disabled?: boolean; title?: string; command?: () => void }

  async function openMenu(row: InfoscreenResponse, canWrite = true) {
    const wrapper = mountTable([row], canWrite, 'enGB', false)
    await flushPromises()
    await wrapper.get('tbody tr').trigger('contextmenu')
    await flushPromises()
    const items = wrapper.findComponent({ name: 'ContextMenu' }).props('model') as Item[]
    return { wrapper, items }
  }

  function shape(items: Item[]): (string | undefined)[] {
    return items.map((item) => (item.separator ? '---' : item.label))
  }

  it('offers Edit, Preview, Display Schedule and Archive in the fixed shape', async () => {
    const screen = makeInfoscreen()
    const { wrapper, items } = await openMenu(screen)

    expect(shape(items)).toEqual([
      i18n.global.t('infoscreens.actions.edit'),
      i18n.global.t('infoscreens.actions.preview'),
      '---',
      i18n.global.t('infoscreens.actions.schedule'),
      '---',
      i18n.global.t('common.archive'),
    ])
    expect(items.some((item) => item.disabled)).toBe(false)

    for (const item of items) item.command?.()
    expect(wrapper.emitted('open')).toEqual([[screen]])
    expect(wrapper.emitted('preview')).toEqual([[screen]])
    expect(wrapper.emitted('schedule')).toEqual([[screen]])
    expect(wrapper.emitted('archive')).toEqual([[screen]])
  })

  it('offers Restore for an archived screen', async () => {
    const { items } = await openMenu(makeInfoscreen({ archived: true }))

    expect(shape(items).at(-1)).toBe(i18n.global.t('common.restore'))
  })

  it('disables the schedule and archiving without write:infoscreens and names the reason', async () => {
    const { items } = await openMenu(makeInfoscreen(), false)

    const byLabel = (label: string) => items.find((item) => item.label === label)!
    expect(byLabel(i18n.global.t('infoscreens.actions.edit')).disabled).toBeFalsy()
    expect(byLabel(i18n.global.t('infoscreens.actions.preview')).disabled).toBeFalsy()
    for (const label of [i18n.global.t('infoscreens.actions.schedule'), i18n.global.t('common.archive')]) {
      expect(byLabel(label).disabled).toBe(true)
      expect(byLabel(label).title).toBe('missing')
    }
  })
})
