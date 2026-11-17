import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'

import type { PageResponse } from '@/core/api/types'
import type {
  PdmSyncRun,
  PdmSyncRunEntry,
  PdmSyncRunEntryFilterParams,
  PdmSyncRunFilterParams,
} from '../../../types/adminSettingsTypes'

const getPdmSyncRunsMock =
  vi.fn<(params?: PdmSyncRunFilterParams) => Promise<PageResponse<PdmSyncRun>>>()
const getPdmSyncRunEntriesMock =
  vi.fn<
    (runId: number, params?: PdmSyncRunEntryFilterParams) => Promise<PageResponse<PdmSyncRunEntry>>
  >()

vi.mock('../../../api/getPdmSyncRuns', () => ({
  getPdmSyncRuns: (params?: PdmSyncRunFilterParams) => getPdmSyncRunsMock(params),
}))
vi.mock('../../../api/getPdmSyncRunEntries', () => ({
  getPdmSyncRunEntries: (runId: number, params?: PdmSyncRunEntryFilterParams) =>
    getPdmSyncRunEntriesMock(runId, params),
}))

import PdmSyncLogDialog from '../PdmSyncLogDialog.vue'

function makeRun(overrides: Partial<PdmSyncRun> = {}): PdmSyncRun {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    started_at: '2026-09-01T10:00:00Z',
    finished_at: '2026-09-01T10:00:05Z',
    trigger: 'scheduled',
    files_seen: 12,
    changed: 3,
    ingested: 2,
    skipped: 8,
    conflicts: 1,
    errors: 0,
    missing: 0,
    error: null,
    summary: '12 files checked, 2 ingested.',
    folders_walked: 4,
    folders_skipped_cold: 0,
    phase: null,
    current_path: null,
    files_queued: 0,
    files_processed: 0,
    progress_at: null,
    ...overrides,
  }
}

function makeEntry(overrides: Partial<PdmSyncRunEntry> = {}): PdmSyncRunEntry {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    run_id: 1,
    vault_id: 'vault-guid',
    file_id: 42,
    name: 'bracket.sldprt',
    path: '\\Made-Parts\\bracket.sldprt',
    kind: 'made',
    action: 'created',
    item_id: 99,
    message: 'Item created from PDM data',
    created_at: '2026-09-01T10:00:02Z',
    ...overrides,
  }
}

function page<T>(items: T[], total = items.length): PageResponse<T> {
  return { items, total, limit: 25, skip: 0 }
}

// OpenVue's Dialog teleports its content to document.body, outside the
// mounted wrapper's own DOM subtree (same note as PdmFilesDialog.spec.ts),
// read text straight off `document` and query raw DOM nodes off it too.
// Component-tree lookups (findComponent/findAllComponents) are unaffected.
function bodyText(): string {
  return document.body.textContent ?? ''
}

async function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(PdmSyncLogDialog, {
    props: { visible: true },
    pinia,
    attachTo: document.body,
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

async function selectFirstRun(wrapper: Awaited<ReturnType<typeof mountDialog>>, run: PdmSyncRun) {
  const runsTable = wrapper.findAllComponents({ name: 'DataTable' })[0]!
  await runsTable.vm.$emit('row-select', { data: run, index: 0, originalEvent: new Event('click') })
  await flushPromises()
}

describe('PdmSyncLogDialog', () => {
  beforeEach(() => {
    getPdmSyncRunsMock.mockReset()
    getPdmSyncRunEntriesMock.mockReset()
    getPdmSyncRunsMock.mockResolvedValue(page([makeRun()]))
    getPdmSyncRunEntriesMock.mockResolvedValue(page([]))
    document.body.innerHTML = ''
  })

  it('loads and renders the runs table on mount, with only non-zero counts shown', async () => {
    const wrapper = await mountDialog()

    expect(getPdmSyncRunsMock).toHaveBeenCalledTimes(1)
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.runs.trigger.scheduled'))
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.runs.counts.ingested'))
    // errors: 0 in the fixture, so its tag must not render at all.
    expect(bodyText()).not.toContain(i18n.global.t('adminSettings.pdmSyncLog.runs.counts.errors'))

    wrapper.unmount()
  })

  it('labels a reconciliation-triggered run "Reconciliation" with secondary severity', async () => {
    getPdmSyncRunsMock.mockResolvedValue(page([makeRun({ trigger: 'reconciliation' })]))
    const wrapper = await mountDialog()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.runs.trigger.reconciliation'))

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const triggerTag = tags.find(
      (tag) =>
        tag.props('value') === i18n.global.t('adminSettings.pdmSyncLog.runs.trigger.reconciliation'),
    )
    expect(triggerTag?.props('severity')).toBe('secondary')

    wrapper.unmount()
  })

  it('labels the genuinely-first-ever poll "Initial run" with a neutral severity', async () => {
    getPdmSyncRunsMock.mockResolvedValue(page([makeRun({ trigger: 'initial' })]))
    const wrapper = await mountDialog()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.runs.trigger.initial'))

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const triggerTag = tags.find(
      (tag) => tag.props('value') === i18n.global.t('adminSettings.pdmSyncLog.runs.trigger.initial'),
    )
    expect(triggerTag?.props('severity')).toBe('secondary')

    wrapper.unmount()
  })

  it('shows the "no run selected" empty state and makes no entries request before a row is picked', async () => {
    const wrapper = await mountDialog()

    expect(getPdmSyncRunEntriesMock).not.toHaveBeenCalled()
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.entries.noRunSelected'))

    wrapper.unmount()
  })

  it('selecting a run loads its entries through the store', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry()]))
    const wrapper = await mountDialog()

    await selectFirstRun(wrapper, makeRun())

    expect(getPdmSyncRunEntriesMock).toHaveBeenCalledWith(1, { skip: 0, limit: 25 })
    expect(bodyText()).toContain('bracket.sldprt')

    wrapper.unmount()
  })

  it('the action filter refetches entries for the selected run with the action param', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry()]))
    const wrapper = await mountDialog()
    await selectFirstRun(wrapper, makeRun())
    getPdmSyncRunEntriesMock.mockClear()

    const actionSelect = wrapper.findComponent({ name: 'Select' })
    await actionSelect.vm.$emit('update:modelValue', 'conflict')
    await flushPromises()

    expect(getPdmSyncRunEntriesMock).toHaveBeenLastCalledWith(1, {
      action: 'conflict',
      skip: 0,
      limit: 25,
    })

    wrapper.unmount()
  })

  it('clicking a message opens the message detail dialog with the full text', async () => {
    const longMessage =
      'Item created from PDM data with a very long explanation that would truncate in the table cell'
    getPdmSyncRunEntriesMock.mockResolvedValue(page([makeEntry({ message: longMessage })]))
    const wrapper = await mountDialog()
    await selectFirstRun(wrapper, makeRun())

    const dialogs = wrapper.findAllComponents({ name: 'Dialog' })
    const messageDialog = dialogs[1]!
    expect(messageDialog.props('visible')).toBe(false)

    const messageCell = document.querySelector('.message-cell') as HTMLElement | null
    expect(messageCell).toBeTruthy()
    messageCell!.click()
    await flushPromises()

    expect(messageDialog.props('visible')).toBe(true)
    expect(bodyText()).toContain(longMessage)

    wrapper.unmount()
  })

  it('lists writeback and writeback_error in the action filter, and shows their labels/severities on entries', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(
      page([
        makeEntry({
          id: 1,
          public_id: '33333333-3333-3333-3333-333333333333',
          action: 'writeback',
          message: 'wrote back 3 variable(s) to 1 configuration(s).',
        }),
        makeEntry({
          id: 2,
          public_id: '44444444-4444-4444-4444-444444444444',
          action: 'writeback_error',
          message: 'variable(s) missing or not version-free on the datacard: Glados.Ids',
        }),
      ]),
    )
    const wrapper = await mountDialog()
    await selectFirstRun(wrapper, makeRun())

    const actionSelect = wrapper.findComponent({ name: 'Select' })
    expect(actionSelect.props('options')).toEqual(
      expect.arrayContaining([
        { label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback'), value: 'writeback' },
        {
          label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback_error'),
          value: 'writeback_error',
        },
      ]),
    )

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback'))
    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback_error'))

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const writebackTag = tags.find(
      (tag) => tag.props('value') === i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback'),
    )
    const writebackErrorTag = tags.find(
      (tag) =>
        tag.props('value') === i18n.global.t('adminSettings.pdmSyncLog.entries.action.writeback_error'),
    )
    expect(writebackTag?.props('severity')).toBe('success')
    expect(writebackErrorTag?.props('severity')).toBe('danger')

    wrapper.unmount()
  })

  it('lists document/document_error/thumbnail/thumbnail_error in the action filter, with their labels and severities', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(
      page([
        makeEntry({
          id: 1,
          public_id: '33333333-3333-3333-3333-333333333333',
          kind: 'document',
          action: 'document',
          message: 'Attached bracket-A.pdf to made item #99.',
        }),
        makeEntry({
          id: 2,
          public_id: '44444444-4444-4444-4444-444444444444',
          kind: 'document',
          action: 'document_error',
          message: 'No item matched the filename pattern.',
        }),
        makeEntry({
          id: 3,
          public_id: '55555555-5555-5555-5555-555555555555',
          action: 'thumbnail',
          message: 'Fetched preview image.',
        }),
        makeEntry({
          id: 4,
          public_id: '66666666-6666-6666-6666-666666666666',
          action: 'thumbnail_error',
          message: 'The vault returned no preview.',
        }),
      ]),
    )
    const wrapper = await mountDialog()
    await selectFirstRun(wrapper, makeRun())

    const actionSelect = wrapper.findComponent({ name: 'Select' })
    expect(actionSelect.props('options')).toEqual(
      expect.arrayContaining([
        { label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.document'), value: 'document' },
        {
          label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.document_error'),
          value: 'document_error',
        },
        { label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.thumbnail'), value: 'thumbnail' },
        {
          label: i18n.global.t('adminSettings.pdmSyncLog.entries.action.thumbnail_error'),
          value: 'thumbnail_error',
        },
      ]),
    )

    function severityFor(labelKey: string): string | undefined {
      const label = i18n.global.t(labelKey) as string
      return wrapper
        .findAllComponents({ name: 'Tag' })
        .find((tag) => tag.props('value') === label)
        ?.props('severity')
    }

    expect(severityFor('adminSettings.pdmSyncLog.entries.action.document')).toBe('success')
    expect(severityFor('adminSettings.pdmSyncLog.entries.action.document_error')).toBe('danger')
    expect(severityFor('adminSettings.pdmSyncLog.entries.action.thumbnail')).toBe('info')
    expect(severityFor('adminSettings.pdmSyncLog.entries.action.thumbnail_error')).toBe('warn')

    wrapper.unmount()
  })

  it('renders an item link routed by kind, and no link when item_id is null', async () => {
    getPdmSyncRunEntriesMock.mockResolvedValue(
      page([
        makeEntry({ id: 1, public_id: '33333333-3333-3333-3333-333333333333', kind: 'made', item_id: 99 }),
        makeEntry({
          id: 2,
          public_id: '44444444-4444-4444-4444-444444444444',
          kind: 'bought',
          item_id: 100,
          name: 'screw.sldprt',
        }),
        makeEntry({
          id: 3,
          public_id: '55555555-5555-5555-5555-555555555555',
          item_id: null,
          name: 'unresolved.sldprt',
        }),
      ]),
    )
    const wrapper = await mountDialog()
    await selectFirstRun(wrapper, makeRun())

    const links = wrapper.findAllComponents({ name: 'RouterLink' })
    expect(links.some((l) => l.props('to') === '/catalogue/made-items/99')).toBe(true)
    expect(links.some((l) => l.props('to') === '/catalogue/bought-items/100')).toBe(true)
    // Exactly two entries have an item_id; the third (null) renders no link.
    expect(links).toHaveLength(2)

    wrapper.unmount()
  })
})
