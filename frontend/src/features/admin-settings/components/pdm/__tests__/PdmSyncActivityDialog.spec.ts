import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { PdmSyncActivity, PdmSyncRun, PdmSyncRunEntry } from '../../../types/adminSettingsTypes'

const getPdmSyncActivityMock = vi.fn<() => Promise<PdmSyncActivity>>()

vi.mock('../../../api/getPdmSyncActivity', () => ({
  getPdmSyncActivity: () => getPdmSyncActivityMock(),
}))

import PdmSyncActivityDialog from '../PdmSyncActivityDialog.vue'

function makeRun(overrides: Partial<PdmSyncRun> = {}): PdmSyncRun {
  const now = new Date().toISOString()
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    started_at: now,
    finished_at: null,
    trigger: 'manual',
    files_seen: 40,
    changed: 8,
    ingested: 3,
    skipped: 1,
    conflicts: 0,
    errors: 0,
    missing: 0,
    error: null,
    summary: null,
    folders_walked: 2,
    folders_skipped_cold: 0,
    phase: 'ingesting',
    current_path: '\\Development\\Local',
    files_queued: 8,
    files_processed: 4,
    progress_at: now,
    ...overrides,
  }
}

function makeEntry(overrides: Partial<PdmSyncRunEntry> = {}): PdmSyncRunEntry {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    run_id: 1,
    vault_id: 'V1',
    file_id: 2123,
    name: 'I-26-00040.SLDPRT',
    path: '\\Development\\Local\\I-26-00040.SLDPRT',
    kind: 'made',
    action: 'created',
    item_id: 9,
    message: 'PDM ingest: created',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

async function mountDialog(activity: PdmSyncActivity) {
  getPdmSyncActivityMock.mockResolvedValue(activity)
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  const wrapper = mountWithApp(PdmSyncActivityDialog, {
    props: { visible: true },
    pinia,
    attachTo: document.body,
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

function bodyText(): string {
  return document.body.textContent ?? ''
}

describe('PdmSyncActivityDialog', () => {
  beforeEach(() => {
    getPdmSyncActivityMock.mockReset()
    document.body.innerHTML = ''
  })

  it('shows the running phase, folder and progress of the poll', async () => {
    const wrapper = await mountDialog({ requested: false, run: makeRun(), recent_entries: [] })

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncActivity.phase.ingesting'))
    expect(bodyText()).toContain('\\Development\\Local')
    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.pdmSyncActivity.processed', { processed: 4, queued: 8 }),
    )
    expect(wrapper.findComponent({ name: 'ProgressBar' }).props('value')).toBe(50)

    wrapper.unmount()
  })

  it('shows a requested synchronisation that waits for the scheduler', async () => {
    const wrapper = await mountDialog({ requested: true, run: null, recent_entries: [] })

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncActivity.requested'))
    expect(wrapper.findComponent({ name: 'ProgressBar' }).props('value')).toBe(0)

    wrapper.unmount()
  })

  it('keeps every field in place with placeholders while nothing runs', async () => {
    const wrapper = await mountDialog({ requested: false, run: null, recent_entries: [] })

    for (const field of ['run', 'folder', 'progress']) {
      expect(bodyText()).toContain(i18n.global.t(`adminSettings.pdmSyncActivity.fields.${field}`))
    }
    // The dialog is teleported to the body, outside the wrapper's own DOM.
    const counters = [...document.body.querySelectorAll('.counters .counter dd')]
    expect(counters).toHaveLength(6)
    expect(counters.every((dd) => dd.textContent?.trim() === getEmptyPlaceholder())).toBe(true)
    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)

    wrapper.unmount()
  })

  it('links made and bought entries to their item, and documents to none', async () => {
    const wrapper = await mountDialog({
      requested: false,
      run: null,
      recent_entries: [
        makeEntry({ id: 3, item_id: 9, kind: 'made' }),
        makeEntry({ id: 2, item_id: 5, kind: 'bought' }),
        makeEntry({ id: 1, item_id: 9, kind: 'document', name: 'I-26-00040 Rev0.step' }),
      ],
    })

    const links = wrapper.findAllComponents({ name: 'RouterLink' })
    expect(links.map((link) => link.props('to'))).toEqual([
      '/catalogue/made-items/9',
      '/catalogue/bought-items/5',
    ])
    expect(bodyText()).toContain('I-26-00040 Rev0.step')

    wrapper.unmount()
  })

  it('emits open-log from its sync log button', async () => {
    const wrapper = await mountDialog({ requested: false, run: null, recent_entries: [] })

    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === i18n.global.t('adminSettings.pdmSyncActivity.openLog'))
    await button!.trigger('click')

    expect(wrapper.emitted('open-log')).toHaveLength(1)

    wrapper.unmount()
  })
})
