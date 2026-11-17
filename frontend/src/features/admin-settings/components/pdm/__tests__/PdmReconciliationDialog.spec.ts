import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter, userWithPermissions } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'

import type { PageResponse } from '@/core/api/types'
import { PDM_RECONCILIATION_CATEGORIES } from '../../../types/adminSettingsTypes'
import type {
  PdmReconciliationFinding,
  PdmReconciliationFindingFilterParams,
  PdmReconciliationSummary,
  PdmReconcileResult,
  PdmSyncRun,
} from '../../../types/adminSettingsTypes'
import type {
  PdmReconciliationExportFormat,
  PdmReconciliationExportRow,
} from '../../../utils/pdmReconciliationExport'

const getPdmReconciliationMock = vi.fn<() => Promise<PdmReconciliationSummary>>()
const getPdmReconciliationFindingsMock =
  vi.fn<
    (params?: PdmReconciliationFindingFilterParams) => Promise<PageResponse<PdmReconciliationFinding>>
  >()
const requestPdmReconciliationMock = vi.fn<(deep: boolean) => Promise<PdmReconcileResult>>()
const writePdmReconciliationExportFileMock =
  vi.fn<(rows: PdmReconciliationExportRow[], format: PdmReconciliationExportFormat) => Promise<void>>()

vi.mock('../../../api/getPdmReconciliation', () => ({
  getPdmReconciliation: () => getPdmReconciliationMock(),
}))
vi.mock('../../../api/getPdmReconciliationFindings', () => ({
  getPdmReconciliationFindings: (params?: PdmReconciliationFindingFilterParams) =>
    getPdmReconciliationFindingsMock(params),
}))
const retryPdmVaultFileMock = vi.fn<(fileId: number) => Promise<{ accepted: boolean }>>()
vi.mock('../../../api/retryPdmVaultFile', () => ({
  retryPdmVaultFile: (fileId: number) => retryPdmVaultFileMock(fileId),
}))
vi.mock('../../../api/requestPdmReconciliation', () => ({
  requestPdmReconciliation: (deep: boolean) => requestPdmReconciliationMock(deep),
}))
// Only the actual xlsx-touching write is mocked. buildPdmReconciliationExportRows
// runs for real so the export test also exercises the real row-building
// logic, not just the wiring around it (that logic has its own dedicated
// spec, but re-running it here is what proves the dialog actually calls it
// with the right findings/labels).
vi.mock('../../../utils/pdmReconciliationExport', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../utils/pdmReconciliationExport')>()
  return {
    ...actual,
    writePdmReconciliationExportFile: (
      rows: PdmReconciliationExportRow[],
      format: PdmReconciliationExportFormat,
    ) => writePdmReconciliationExportFileMock(rows, format),
  }
})

import PdmReconciliationDialog from '../PdmReconciliationDialog.vue'

function makeRun(overrides: Partial<PdmSyncRun> = {}): PdmSyncRun {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    started_at: '2026-09-04T10:00:00Z',
    finished_at: '2026-09-04T10:00:05Z',
    trigger: 'reconciliation',
    files_seen: 0,
    changed: 0,
    ingested: 0,
    skipped: 0,
    conflicts: 0,
    errors: 0,
    missing: 0,
    error: null,
    summary: null,
    folders_walked: 0,
    folders_skipped_cold: 0,
    phase: null,
    current_path: null,
    files_queued: 0,
    files_processed: 0,
    progress_at: null,
    ...overrides,
  }
}

function makeFinding(overrides: Partial<PdmReconciliationFinding> = {}): PdmReconciliationFinding {
  return {
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    run_id: 1,
    category: 'stuck_file',
    severity: 'warning',
    kind: 'made',
    item_id: 99,
    file_id: 42,
    part_number: 'PUR-26-00001',
    revision: 'A',
    message: 'File has not been ingested for 9 days.',
    count: 1,
    created_at: '2026-09-04T10:00:03Z',
    ...overrides,
  }
}

function page<T>(items: T[], total = items.length): PageResponse<T> {
  return { items, total, limit: 25, skip: 0 }
}

function bodyText(): string {
  return document.body.textContent ?? ''
}

// OpenVue's Dialog teleports its content to document.body, outside the
// mounted wrapper's own DOM subtree (same note as PdmFilesDialog.spec.ts/
// PdmSyncLogDialog.spec.ts). The category tiles are plain DOM (not a
// OpenVue component), so query them straight off `document` too.
function categoryTiles(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>('.category-tile'))
}

function findTileByLabel(label: string): HTMLElement {
  return categoryTiles().find((tile) => tile.textContent?.includes(label))!
}

async function mountDialog(permissions: string[] = ['write:settings']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const router = makeTestRouter()
  await router.push('/')
  await router.isReady()

  const wrapper = mountWithApp(PdmReconciliationDialog, {
    props: { visible: true },
    pinia,
    attachTo: document.body,
    global: { plugins: [router] },
  })
  await flushPromises()
  return { wrapper, router }
}

function quickButton(wrapper: Awaited<ReturnType<typeof mountDialog>>['wrapper']) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('adminSettings.pdmReconciliation.quickButton') as string))!
}

function deepButton(wrapper: Awaited<ReturnType<typeof mountDialog>>['wrapper']) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('adminSettings.pdmReconciliation.deepButton') as string))!
}

function exportButton(wrapper: Awaited<ReturnType<typeof mountDialog>>['wrapper']) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('adminSettings.pdmReconciliation.export') as string))!
}

function findButtonByAriaLabel(
  wrapper: Awaited<ReturnType<typeof mountDialog>>['wrapper'],
  label: string,
) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.attributes('aria-label') === label)
}

describe('PdmReconciliationDialog', () => {
  beforeEach(() => {
    getPdmReconciliationMock.mockReset()
    getPdmReconciliationFindingsMock.mockReset()
    requestPdmReconciliationMock.mockReset()
    writePdmReconciliationExportFileMock.mockReset()
    getPdmReconciliationMock.mockResolvedValue({
      run: makeRun(),
      counts: { stuck_file: 3, orphaned_cad_row: 0 },
    })
    getPdmReconciliationFindingsMock.mockResolvedValue(page([makeFinding()]))
    document.body.innerHTML = ''
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads the summary and findings on mount', async () => {
    const { wrapper } = await mountDialog()

    expect(getPdmReconciliationMock).toHaveBeenCalledTimes(1)
    expect(getPdmReconciliationFindingsMock).toHaveBeenCalledTimes(1)
    expect(bodyText()).toContain('PUR-26-00001')

    wrapper.unmount()
  })

  it('shows the empty state and no tiles/table when reconciliation has never run', async () => {
    getPdmReconciliationMock.mockResolvedValue({ run: null, counts: {} })
    const { wrapper } = await mountDialog()

    expect(bodyText()).toContain(i18n.global.t('adminSettings.pdmReconciliation.empty'))
    expect(wrapper.findComponent({ name: 'DataTable' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('renders one tile per category, muting a zero count', async () => {
    const { wrapper } = await mountDialog()

    const tiles = categoryTiles()
    expect(tiles).toHaveLength(PDM_RECONCILIATION_CATEGORIES.length)

    const stuckTile = findTileByLabel(
      i18n.global.t('adminSettings.pdmReconciliation.categories.stuck_file.label'),
    )
    const orphanedTile = findTileByLabel(
      i18n.global.t('adminSettings.pdmReconciliation.categories.orphaned_cad_row.label'),
    )
    expect(stuckTile.className).not.toContain('category-tile--muted')
    expect(orphanedTile.className).toContain('category-tile--muted')
    expect(stuckTile.textContent).toContain('3')
    expect(orphanedTile.textContent).toContain('0')

    wrapper.unmount()
  })

  it('clicking a tile sets the category filter and refetches findings', async () => {
    const { wrapper } = await mountDialog()
    getPdmReconciliationFindingsMock.mockClear()

    const stuckTile = findTileByLabel(
      i18n.global.t('adminSettings.pdmReconciliation.categories.stuck_file.label'),
    )
    stuckTile.click()
    await flushPromises()

    expect(getPdmReconciliationFindingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ category: 'stuck_file', skip: 0 }),
    )

    wrapper.unmount()
  })

  it('the category Select refetches with the chosen category', async () => {
    const { wrapper } = await mountDialog()
    getPdmReconciliationFindingsMock.mockClear()

    const categorySelect = wrapper.findAllComponents({ name: 'Select' })[0]!
    await categorySelect.vm.$emit('update:modelValue', 'revision_lag')
    await flushPromises()

    expect(getPdmReconciliationFindingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ category: 'revision_lag', skip: 0 }),
    )

    wrapper.unmount()
  })

  it('the kind Select refetches with the chosen kind', async () => {
    const { wrapper } = await mountDialog()
    getPdmReconciliationFindingsMock.mockClear()

    const kindSelect = wrapper.findAllComponents({ name: 'Select' })[1]!
    await kindSelect.vm.$emit('update:modelValue', 'document')
    await flushPromises()

    expect(getPdmReconciliationFindingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ kind: 'document', skip: 0 }),
    )

    wrapper.unmount()
  })

  it('search debounces before refetching', async () => {
    vi.useFakeTimers()
    const { wrapper } = await mountDialog()
    const store = (await import('../../../stores/pdmReconciliationStore')).usePdmReconciliationStore()
    getPdmReconciliationFindingsMock.mockClear()

    store.search = 'PUR-26'
    await wrapper.vm.$nextTick()
    expect(getPdmReconciliationFindingsMock).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(500)

    expect(getPdmReconciliationFindingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: 'PUR-26' }),
    )

    wrapper.unmount()
  })

  it('renders findings rows with the category tag, kind, and combined part-number label', async () => {
    const { wrapper } = await mountDialog()

    expect(bodyText()).toContain(
      i18n.global.t('adminSettings.pdmReconciliation.categories.stuck_file.label'),
    )
    expect(bodyText()).toContain(i18n.global.t('adminSettings.itemFields.madeSection'))
    expect(bodyText()).toContain('PUR-26-00001:A')

    wrapper.unmount()
  })

  it('clicking a message cell opens the message detail dialog with the full text', async () => {
    const longMessage = 'A very long reconciliation message that would truncate in the table cell'
    getPdmReconciliationFindingsMock.mockResolvedValue(page([makeFinding({ message: longMessage })]))
    const { wrapper } = await mountDialog()

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

  it('opens the linked item via the Actions button, routed by kind', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(
      page([makeFinding({ kind: 'bought', item_id: 100 })]),
    )
    const { wrapper, router } = await mountDialog()
    const pushSpy = vi.spyOn(router, 'push')

    const openItemButton = findButtonByAriaLabel(
      wrapper,
      i18n.global.t('adminSettings.pdmReconciliation.openItem'),
    )
    expect(openItemButton).toBeDefined()
    await openItemButton!.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith('/catalogue/bought-items/100')

    wrapper.unmount()
  })

  it('does not render the open-item action when item_id is null', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(page([makeFinding({ item_id: null })]))
    const { wrapper } = await mountDialog()

    expect(
      findButtonByAriaLabel(wrapper, i18n.global.t('adminSettings.pdmReconciliation.openItem')),
    ).toBeUndefined()

    wrapper.unmount()
  })

  it('emits open-files when the Actions files button is clicked, only when file_id is set', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(
      page([makeFinding({ file_id: 42 }), makeFinding({ id: 2, file_id: null, item_id: null })]),
    )
    const { wrapper } = await mountDialog()

    const openFilesButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.attributes('aria-label') === i18n.global.t('adminSettings.pdmReconciliation.openFiles'))
    expect(openFilesButtons).toHaveLength(1)

    await openFilesButtons[0]!.trigger('click')

    expect(wrapper.emitted('open-files')).toHaveLength(1)

    wrapper.unmount()
  })

  it('re-checks a finding\'s file on rows with a file, disabled with the missing permission for readers', async () => {
    retryPdmVaultFileMock.mockResolvedValue({ accepted: true })
    getPdmReconciliationFindingsMock.mockResolvedValue(
      page([makeFinding({ file_id: 42 }), makeFinding({ id: 2, file_id: null, item_id: null })]),
    )
    const { wrapper } = await mountDialog()
    const label = i18n.global.t('adminSettings.pdmReconciliation.recheck')

    const recheckButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.attributes('aria-label') === label)
    expect(recheckButtons).toHaveLength(1)

    await recheckButtons[0]!.trigger('click')
    await flushPromises()

    expect(retryPdmVaultFileMock).toHaveBeenCalledWith(42)
    wrapper.unmount()

    const { wrapper: readOnly } = await mountDialog(['read:settings'])
    const blocked = readOnly
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.attributes('aria-label') === label)
    expect(blocked).toHaveLength(1)
    expect(blocked[0]!.attributes('disabled')).toBeDefined()
    const span = blocked[0]!.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')
    readOnly.unmount()
  })

  it('Quick Reconciliation requests a shallow run, Deep Reconciliation a deep one', async () => {
    requestPdmReconciliationMock.mockResolvedValue({ accepted: true })
    const { wrapper } = await mountDialog()

    await quickButton(wrapper).trigger('click')
    await flushPromises()
    expect(requestPdmReconciliationMock).toHaveBeenLastCalledWith(false)

    await deepButton(wrapper).trigger('click')
    await flushPromises()
    expect(requestPdmReconciliationMock).toHaveBeenLastCalledWith(true)

    wrapper.unmount()
  })

  it('disables both run buttons while a run is open', async () => {
    getPdmReconciliationMock.mockResolvedValue({ run: makeRun({ finished_at: null }), counts: {} })
    const { wrapper } = await mountDialog()

    expect(quickButton(wrapper).attributes('disabled')).toBeDefined()
    expect(deepButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('disables both run buttons without write:settings, even with no run open', async () => {
    const { wrapper } = await mountDialog([])

    expect(quickButton(wrapper).attributes('disabled')).toBeDefined()
    expect(deepButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('disables the export button when there are no findings', async () => {
    getPdmReconciliationFindingsMock.mockResolvedValue(page([]))
    const { wrapper } = await mountDialog()

    expect(exportButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('export fetches every page of the current filter and writes the built rows', async () => {
    getPdmReconciliationFindingsMock.mockImplementation(
      async (params?: PdmReconciliationFindingFilterParams) => {
        const skip = params?.skip ?? 0
        if (skip === 0) {
          return page(
            [makeFinding({ id: 1 }), makeFinding({ id: 2, category: 'revision_lag' })],
            2,
          )
        }
        return page([], 2)
      },
    )
    const { wrapper } = await mountDialog()

    await exportButton(wrapper).trigger('click')
    await flushPromises()

    expect(writePdmReconciliationExportFileMock).toHaveBeenCalledTimes(1)
    const [rows, format] = writePdmReconciliationExportFileMock.mock.calls[0]!
    expect(format.filename).toBe(i18n.global.t('adminSettings.pdmReconciliation.exportFile.filename'))
    expect(format.filename).toMatch(/\.xlsx$/)
    expect(format.sheetName).toBe(i18n.global.t('adminSettings.pdmReconciliation.exportFile.sheetName'))
    expect(format.headers.partNumber).toBe(
      i18n.global.t('adminSettings.pdmReconciliation.exportFile.columns.partNumber'),
    )
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({
      category: i18n.global.t('adminSettings.pdmReconciliation.categories.stuck_file.label'),
      partNumber: 'PUR-26-00001',
      revision: 'A',
      count: 1,
    })
    expect(rows[1]).toMatchObject({
      category: i18n.global.t('adminSettings.pdmReconciliation.categories.revision_lag.label'),
    })

    wrapper.unmount()
  })
})
