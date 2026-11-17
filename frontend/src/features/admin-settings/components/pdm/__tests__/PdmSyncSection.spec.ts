import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'
import type { ConfirmationOptions } from 'openvue/confirmationoptions'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import PdmSyncSection from '../PdmSyncSection.vue'
import type { PdmFolder, PdmWatchedFolder, PdmWorkflow } from '../../../types/adminSettingsTypes'

const confirmRequireMock = vi.fn<(options: ConfirmationOptions) => void>()
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: confirmRequireMock }),
}))

// Shared by the workflow-list fetch (PdmSyncSection itself) and the folder
// tree's root fetch (PdmFolderPickerDialog, opened by the "Choose Folder"
// and "Watch folder" buttons), both go through the same mocked
// `@/core/api`, so the mock has to branch on the URL rather than
// answering every GET the same way.
const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    // Forwards exactly the arguments the caller passed, rather than always
    // passing two: the workflows fetch calls `api.get(url)` with no
    // config object at all, and `toHaveBeenCalledWith(url)` would fail
    // against a call recorded as `(url, undefined)`.
    get: (...args: Parameters<typeof getMock>) => getMock(...args),
  },
}))

function makeFolder(overrides: Partial<PdmWatchedFolder> = {}): PdmWatchedFolder {
  return {
    path: '\\Made-Parts',
    kind: 'made',
    recursive: true,
    enabled: true,
    match_by: null,
    filename_pattern: null,
    folder_id: null,
    ...overrides,
  }
}

function workflowsFixture(): PdmWorkflow[] {
  return [
    {
      workflow_id: 1,
      workflow_name: 'Standard',
      states: [
        { state_id: 10, state_name: 'Approved' },
        { state_id: 11, state_name: 'In Review' },
      ],
    },
    {
      workflow_id: 2,
      workflow_name: 'Purchased',
      states: [{ state_id: 20, state_name: 'Obsolete' }],
    },
  ]
}

function rootFoldersFixture(): PdmFolder[] {
  return [
    { id: 2, name: 'Made-Parts', path: '\\Made-Parts' },
    { id: 3, name: 'Bought-Parts', path: '\\Bought-Parts' },
  ]
}

interface Props {
  canWrite: boolean
  configured: boolean
  enabled: boolean
  watchedFolders: PdmWatchedFolder[]
  madeReleasedStateIds: number[]
  madeObsoleteStateIds: number[]
  madeReplacedStateIds: number[]
  boughtReleasedStateIds: number[]
  boughtObsoleteStateIds: number[]
  boughtReplacedStateIds: number[]
  documentReleasedStateIds: number[]
  pollIntervalMinutes: number
  coldFolderMaxMultiplier: number
  ingestConcurrency: number
  cadItemsReadOnly: boolean
  writebackEnabled: boolean
  madeItemExtensions: string[]
  boughtItemExtensions: string[]
  documentCategories: Record<string, string>
  documentExcludedKinds: Record<string, string[]>
  thumbnailsEnabled: boolean
  stuckAfterDays: number
  lastPollAt: string | null
  lastPollError: string | null
  lastPollSummary: string | null
  snapshotCounts: Record<string, number>
}

function mountSection(overrides: Partial<Props> = {}) {
  const props: Props = {
    canWrite: true,
    configured: true,
    enabled: false,
    watchedFolders: [makeFolder()],
    madeReleasedStateIds: [10],
    madeObsoleteStateIds: [20],
    madeReplacedStateIds: [],
    boughtReleasedStateIds: [10],
    boughtObsoleteStateIds: [20],
    boughtReplacedStateIds: [],
    documentReleasedStateIds: [],
    pollIntervalMinutes: 15,
    coldFolderMaxMultiplier: 8,
    ingestConcurrency: 4,
    cadItemsReadOnly: true,
    writebackEnabled: false,
    madeItemExtensions: ['sldprt'],
    boughtItemExtensions: ['sldasm', 'sldprt'],
    documentCategories: { pdf: 'drawing' },
    documentExcludedKinds: {},
    thumbnailsEnabled: false,
    stuckAfterDays: 7,
    lastPollAt: null,
    lastPollError: null,
    lastPollSummary: null,
    snapshotCounts: {},
    ...overrides,
  }
  return mountWithApp(PdmSyncSection, {
    props,
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('PdmSyncSection', () => {
  beforeEach(() => {
    confirmRequireMock.mockReset()
    getMock.mockReset()
    getMock.mockImplementation((url) => {
      if (url === '/admin/settings/pdm/folders') return Promise.resolve({ data: rootFoldersFixture() })
      return Promise.resolve({ data: workflowsFixture() })
    })
  })

  it('shows the extension and category controls disabled with the missing permission without write access', async () => {
    const wrapper = mountSection({ canWrite: false })
    await flushPromises()

    const add = wrapper.get('[data-testid="pdm-category-add"]')
    expect(add.attributes('disabled')).toBeDefined()
    const span = add.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')
    const rows = wrapper.findAll('.extension-add-row')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      expect(row.get('button').attributes('disabled')).toBeDefined()
    }
  })

  it('fetches the workflow list on mount when configured, and builds MultiSelect options from it', async () => {
    const wrapper = mountSection()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith('/admin/settings/pdm/workflows')

    // One released + one obsolete + one replaced MultiSelect per item kind
    // (made, bought), plus the exported documents' released states.
    const multiSelects = wrapper.findAllComponents({ name: 'MultiSelect' })
    expect(multiSelects).toHaveLength(7)
    for (const select of multiSelects) {
      const options = select.props('options') as { label: string; value: number }[]
      expect(options).toEqual([
        { label: 'Standard › Approved', value: 10 },
        { label: 'Standard › In Review', value: 11 },
        { label: 'Purchased › Obsolete', value: 20 },
      ])
    }

    wrapper.unmount()
  })

  it('renders the made and bought state pickers under their own subsection labels, each bound to its own kind', async () => {
    const wrapper = mountSection({
      madeReleasedStateIds: [10],
      madeObsoleteStateIds: [11],
      madeReplacedStateIds: [12],
      boughtReleasedStateIds: [20],
      boughtObsoleteStateIds: [],
      boughtReplacedStateIds: [21],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.madeSection'))
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.boughtSection'))

    const [madeReleased, madeObsolete, madeReplaced, boughtReleased, boughtObsolete, boughtReplaced] =
      wrapper.findAllComponents({ name: 'MultiSelect' })
    expect(madeReleased!.props('modelValue')).toEqual([10])
    expect(madeObsolete!.props('modelValue')).toEqual([11])
    expect(madeReplaced!.props('modelValue')).toEqual([12])
    expect(boughtReleased!.props('modelValue')).toEqual([20])
    expect(boughtObsolete!.props('modelValue')).toEqual([])
    expect(boughtReplaced!.props('modelValue')).toEqual([21])

    await madeReleased!.vm.$emit('update:modelValue', [10, 11])
    expect(wrapper.emitted('update:madeReleasedStateIds')).toEqual([[[10, 11]]])

    await boughtObsolete!.vm.$emit('update:modelValue', [20])
    expect(wrapper.emitted('update:boughtObsoleteStateIds')).toEqual([[[20]]])

    await madeReplaced!.vm.$emit('update:modelValue', [12, 13])
    expect(wrapper.emitted('update:madeReplacedStateIds')).toEqual([[[12, 13]]])

    await boughtReplaced!.vm.$emit('update:modelValue', [])
    expect(wrapper.emitted('update:boughtReplacedStateIds')).toEqual([[[]]])

    wrapper.unmount()
  })

  it('renders the exported documents state picker under its own label, bound to its own model', async () => {
    const wrapper = mountSection({ documentReleasedStateIds: [10] })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.documentReleasedStatesHint'),
    )
    const documentStates = wrapper.findAllComponents({ name: 'MultiSelect' })[6]!
    expect(documentStates.props('modelValue')).toEqual([10])

    await documentStates.vm.$emit('update:modelValue', [10, 11])
    expect(wrapper.emitted('update:documentReleasedStateIds')).toEqual([[[10, 11]]])

    wrapper.unmount()
  })

  it('shows the write-back-to-PDM toggle and its explanatory hint', async () => {
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sync.writebackEnabled'))
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.writebackEnabledHint'),
    )

    wrapper.unmount()
  })

  it('shows the released/obsolete/replaced state explanatory hints', async () => {
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.releasedStatesHint'),
    )
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.obsoleteStatesHint'),
    )
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.replacedStatesHint'),
    )

    wrapper.unmount()
  })

  it('does not fetch the workflow list when not yet configured', async () => {
    const wrapper = mountSection({ configured: false })
    await flushPromises()

    expect(getMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('shows a warning Message when the workflow fetch fails, and keeps the selects usable with the saved ids', async () => {
    getMock.mockReset()
    getMock.mockRejectedValue(new Error('network error'))

    const wrapper = mountSection({
      madeReleasedStateIds: [10],
      madeObsoleteStateIds: [20],
      madeReplacedStateIds: [30],
      boughtReleasedStateIds: [10],
      boughtObsoleteStateIds: [20],
      boughtReplacedStateIds: [30],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.workflowsLoadFailed'),
    )
    const multiSelects = wrapper.findAllComponents({ name: 'MultiSelect' })
    expect(multiSelects).toHaveLength(7)
    // The saved ids are still there, even though there are no options to
    // resolve a label for them, so the section stays usable, not blocked.
    expect(multiSelects[0]!.props('modelValue')).toEqual([10])
    expect(multiSelects[1]!.props('modelValue')).toEqual([20])
    expect(multiSelects[2]!.props('modelValue')).toEqual([30])
    expect(multiSelects[3]!.props('modelValue')).toEqual([10])
    expect(multiSelects[4]!.props('modelValue')).toEqual([20])
    expect(multiSelects[5]!.props('modelValue')).toEqual([30])

    wrapper.unmount()
  })

  // The "Watch folder" button lives in the tab's ControlsBar (see
  // AdminSettingsTabSolidworksPdm.spec.ts for its button/disabled-state
  // coverage) and drives this section through the exposed `openAddPicker`,
  // the same way MadeItemProcessGrouping exposes save()/reset() for its
  // host dialog, so these two tests call it directly rather than through a
  // button in this component.
  it('the exposed openAddPicker() opens the folder picker rather than appending a row directly', async () => {
    const wrapper = mountSection({ watchedFolders: [makeFolder({ path: '\\Made-Parts' })] })
    await flushPromises()

    wrapper.vm.openAddPicker()
    await wrapper.vm.$nextTick()

    const dialog = wrapper.findComponent({ name: 'PdmFolderPickerDialog' })
    expect(dialog.props('visible')).toBe(true)
    // A folder already on the watched list must not be pickable a second
    // time via the "Watch folder" button (unlike editing an existing row's
    // own path, which is trivially already on the list).
    expect(dialog.props('allowWatched')).toBe(false)
    expect(dialog.props('watchedPaths')).toEqual(['\\Made-Parts'])
    expect(wrapper.emitted('update:watchedFolders')).toBeUndefined()

    wrapper.unmount()
  })

  // A newly added row defaults to `by_kind` (the backend's own default)
  // rather than `made`, since the file's own datacard decides which
  // catalogue it belongs to unless the admin picks an explicit kind for
  // the row.
  it('appends a full row with the picked path and folder id once the folder picker is applied, defaulting to by_kind', async () => {
    const wrapper = mountSection({ watchedFolders: [makeFolder({ path: '\\Made-Parts' })] })
    await flushPromises()

    wrapper.vm.openAddPicker()
    await wrapper.vm.$nextTick()
    await wrapper
      .findComponent({ name: 'PdmFolderPickerDialog' })
      .vm.$emit('apply', '\\Bought-Parts', 3)

    const emitted = wrapper.emitted('update:watchedFolders')!
    const last = emitted[emitted.length - 1]![0] as PdmWatchedFolder[]
    expect(last).toHaveLength(2)
    expect(last[1]).toEqual({
      path: '\\Bought-Parts',
      kind: 'by_kind',
      recursive: true,
      enabled: true,
      match_by: null,
      filename_pattern: null,
      folder_id: 3,
    })

    wrapper.unmount()
  })

  it('offers "By datacard" first among the per-row kind options', async () => {
    const wrapper = mountSection({ watchedFolders: [makeFolder({ kind: 'by_kind' })] })
    await flushPromises()

    const kindSelect = wrapper.findComponent({ name: 'Select' })
    expect(kindSelect.props('options')).toEqual([
      {
        label: i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKind'),
        value: 'by_kind',
      },
      { label: i18n.global.t('adminSettings.itemFields.madeSection'), value: 'made' },
      { label: i18n.global.t('adminSettings.itemFields.boughtSection'), value: 'bought' },
      {
        label: i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments'),
        value: 'documents',
      },
    ])
    expect(kindSelect.props('modelValue')).toBe('by_kind')

    wrapper.unmount()
  })

  it('shows the "by_kind" explanatory hint under the watched-folders table', async () => {
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKindHint'),
    )

    wrapper.unmount()
  })

  it('does not render a "Watch folder" button - it moved to the tab\'s ControlsBar', async () => {
    const wrapper = mountSection()
    await flushPromises()

    const label = i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.addButton') as string
    expect(wrapper.findAllComponents({ name: 'Button' }).some((b) => b.props('label') === label)).toBe(
      false,
    )

    wrapper.unmount()
  })

  it('editing a row via "Choose Folder" allows re-picking an already-watched folder', async () => {
    const folders = [makeFolder({ path: '\\Made-Parts' }), makeFolder({ path: '\\Bought-Parts' })]
    const wrapper = mountSection({ watchedFolders: folders })
    await flushPromises()

    const pickButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-folder-search-outline')!
    await pickButton.trigger('click')

    const dialog = wrapper.findComponent({ name: 'PdmFolderPickerDialog' })
    expect(dialog.props('allowWatched')).toBe(true)

    await dialog.vm.$emit('apply', '\\Bought-Parts', 3)

    // Row-edit mode mutates the existing row's `path`/`folder_id` in place
    // (same as manually typing into its InputText) rather than replacing
    // the whole array, so it never emits update:watchedFolders. Assert on
    // the source object the "watchedFolders" prop shares with the caller.
    expect(wrapper.emitted('update:watchedFolders')).toBeUndefined()
    expect(folders[0]).toEqual(expect.objectContaining({ path: '\\Bought-Parts', folder_id: 3 }))

    wrapper.unmount()
  })

  it('clears folder_id once the path is typed by hand instead of picked', async () => {
    const folders = [makeFolder({ path: '\\Made-Parts', folder_id: 2 })]
    const wrapper = mountSection({ watchedFolders: folders })
    await flushPromises()

    const pathInput = foldersTable(wrapper).findComponent({ name: 'InputText' })
    await pathInput.setValue('\\Made-Parts\\Sheet-Metal')

    expect(folders[0]!.folder_id).toBeNull()
    expect(folders[0]!.path).toBe('\\Made-Parts\\Sheet-Metal')

    wrapper.unmount()
  })

  it('removes a row after the remove confirmation is accepted', async () => {
    const folders = [makeFolder({ path: '\\Made-Parts' }), makeFolder({ path: '\\Bought-Parts', kind: 'bought' })]
    const wrapper = mountSection({ watchedFolders: folders })
    await flushPromises()

    const deleteButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('icon') === 'mdi mdi-delete-outline')
    await deleteButtons[0]!.trigger('click')

    expect(confirmRequireMock).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('update:watchedFolders')).toBeUndefined()

    const options = confirmRequireMock.mock.calls[0]![0] as { accept: () => void }
    options.accept()

    const emitted = wrapper.emitted('update:watchedFolders')!
    const last = emitted[emitted.length - 1]![0] as PdmWatchedFolder[]
    expect(last).toEqual([expect.objectContaining({ path: '\\Bought-Parts' })])

    wrapper.unmount()
  })

  // This section has no enable toggle of its own. The global "Enable PDM
  // integration" switch lives in PdmConnectionSection, which owns
  // update:enabled; `enabled` here is a plain read-only prop feeding the
  // validation hints below.
  it('does not render an enable toggle - `enabled` is a read-only prop here', async () => {
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).not.toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sync.enabled'))

    wrapper.unmount()
  })

  it('emits update:pollIntervalMinutes, update:cadItemsReadOnly and update:writebackEnabled on their own controls', async () => {
    const wrapper = mountSection()
    await flushPromises()

    const intervalInput = wrapper.findComponent({ name: 'InputNumber' })
    await intervalInput.vm.$emit('update:modelValue', 30)
    expect(wrapper.emitted('update:pollIntervalMinutes')).toEqual([[30]])

    // "CAD Items Read-Only" is the first field-row in this section
    // now (right after the status block, since the enable toggle moved
    // away), followed immediately by "Write sync result to PDM",
    // ahead of the watched-folders table's own per-row Recursive/Active
    // toggles, so these two are reliably the first two ToggleSwitches.
    const toggles = wrapper.findAllComponents({ name: 'ToggleSwitch' })
    await toggles[0]!.vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:cadItemsReadOnly')).toEqual([[false]])

    await toggles[1]!.vm.$emit('update:modelValue', true)
    expect(wrapper.emitted('update:writebackEnabled')).toEqual([[true]])

    wrapper.unmount()
  })

  it('renders the cold-folder backoff field right after the poll interval, with its hint, and emits on change', async () => {
    const wrapper = mountSection()
    await flushPromises()

    const numberInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(numberInputs).toHaveLength(4)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.coldFolderMaxMultiplierHint'),
    )

    await numberInputs[1]!.vm.$emit('update:modelValue', 16)
    expect(wrapper.emitted('update:coldFolderMaxMultiplier')).toEqual([[16]])

    wrapper.unmount()
  })

  it('renders the parallel ingests field after the cold-folder backoff, with its hint, and emits on change', async () => {
    const wrapper = mountSection()
    await flushPromises()

    const numberInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.ingestConcurrencyHint'),
    )

    await numberInputs[2]!.vm.$emit('update:modelValue', 8)
    expect(wrapper.emitted('update:ingestConcurrency')).toEqual([[8]])

    wrapper.unmount()
  })

  it('renders the stuck-after-days field after the poll interval and cold-folder backoff, with its hint, and emits on change', async () => {
    const wrapper = mountSection()
    await flushPromises()

    const numberInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(numberInputs).toHaveLength(4)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.stuckAfterDaysHint'),
    )

    await numberInputs[3]!.vm.$emit('update:modelValue', 14)
    expect(wrapper.emitted('update:stuckAfterDays')).toEqual([[14]])

    wrapper.unmount()
  })

  it('shows the empty-path validation hint when a row has a blank path', async () => {
    const wrapper = mountSection({ watchedFolders: [makeFolder({ path: '' })] })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.emptyPath'),
    )

    wrapper.unmount()
  })

  it('shows the duplicate-path validation hint when two rows normalise to the same path', async () => {
    const wrapper = mountSection({
      watchedFolders: [makeFolder({ path: '\\Made-Parts' }), makeFolder({ path: 'Made-Parts\\' })],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.duplicatePath'),
    )

    wrapper.unmount()
  })

  it('shows the missing-enabled-folder and missing-released-state hints only while the PDM integration is enabled', async () => {
    const disabledWrapper = mountSection({
      enabled: false,
      watchedFolders: [makeFolder({ enabled: false })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    await flushPromises()
    expect(disabledWrapper.text()).not.toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.validation.missingEnabledFolder'),
    )
    disabledWrapper.unmount()

    const enabledWrapper = mountSection({
      enabled: true,
      watchedFolders: [makeFolder({ enabled: false })],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [],
    })
    await flushPromises()
    expect(enabledWrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.validation.missingEnabledFolder'),
    )
    expect(enabledWrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.validation.missingReleasedState'),
    )
    enabledWrapper.unmount()
  })

  it('a released state configured for bought alone still clears the missing-released-state hint', async () => {
    const wrapper = mountSection({
      enabled: true,
      watchedFolders: [makeFolder()],
      madeReleasedStateIds: [],
      boughtReleasedStateIds: [20],
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.validation.missingReleasedState'),
    )

    wrapper.unmount()
  })

  it('shows the last-run status, the error Message and non-zero snapshot count Tags', async () => {
    const wrapper = mountSection({
      lastPollError: 'Vault unreachable',
      snapshotCounts: { ingested: 3, pending: 0, conflict: 1 },
    })
    await flushPromises()

    const message = wrapper
      .findAllComponents({ name: 'Message' })
      .find((m) => m.text().includes('Vault unreachable'))
    expect(message).toBeTruthy()

    const tags = wrapper.findAllComponents({ name: 'Tag' })
    const tagValues = tags.map((tag) => tag.props('value'))
    expect(tagValues.some((v) => String(v).startsWith('Ingested'))).toBe(true)
    expect(tagValues.some((v) => String(v).startsWith('Conflict'))).toBe(true)
    expect(tagValues.some((v) => String(v).startsWith('Pending'))).toBe(false)

    wrapper.unmount()
  })

  it('disables the folder picker button when not configured, even with write:settings', async () => {
    const wrapper = mountSection({ configured: false })
    await flushPromises()

    const pickButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('icon') === 'mdi mdi-folder-search-outline')!
    expect(pickButton.element.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })

  // ── "documents" watched-folder kind ──────────────────────────────────────

  // Scoped to the watched-folders table itself (the first DataTable): the
  // file-types add-row inputs and the document-categories table below it
  // also contain Selects/InputTexts of their own, which would otherwise
  // pollute a plain wrapper-wide count.
  function foldersTable(wrapper: ReturnType<typeof mountSection>) {
    return wrapper.findAllComponents({ name: 'DataTable' })[0]!
  }

  it('shows the Assignment select only for a "documents"-kind row, and the filename pattern input only once "By filename" is picked', async () => {
    const wrapper = mountSection({
      watchedFolders: [makeFolder({ kind: 'documents', match_by: null })],
      documentCategories: {},
    })
    await flushPromises()

    const selects = foldersTable(wrapper).findAllComponents({ name: 'Select' })
    const matchBySelect = selects[1]!
    expect(matchBySelect.props('options')).toEqual([
      {
        label: i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKind'),
        value: 'datacard',
      },
      {
        label: i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.matchByFilename'),
        value: 'filename',
      },
    ])
    // No match_by chosen yet, only the path input, no filename pattern input.
    expect(foldersTable(wrapper).findAllComponents({ name: 'InputText' })).toHaveLength(1)

    wrapper.unmount()
  })

  it('shows the filename pattern input once match_by is "filename", and not for "datacard"', async () => {
    const datacardWrapper = mountSection({
      watchedFolders: [makeFolder({ kind: 'documents', match_by: 'datacard' })],
      documentCategories: {},
    })
    await flushPromises()
    // Only the path InputText, no pattern field for datacard matching.
    expect(foldersTable(datacardWrapper).findAllComponents({ name: 'InputText' })).toHaveLength(1)
    datacardWrapper.unmount()

    const filenameWrapper = mountSection({
      watchedFolders: [makeFolder({ kind: 'documents', match_by: 'filename', filename_pattern: '' })],
      documentCategories: {},
    })
    await flushPromises()
    // The pattern field plus "Path".
    expect(foldersTable(filenameWrapper).findAllComponents({ name: 'InputText' })).toHaveLength(2)
    filenameWrapper.unmount()
  })

  it('does not show either "documents" control for a made/bought/by_kind row', async () => {
    const wrapper = mountSection({
      watchedFolders: [makeFolder({ kind: 'made' })],
      documentCategories: {},
    })
    await flushPromises()

    expect(foldersTable(wrapper).findAllComponents({ name: 'Select' })).toHaveLength(1) // just kind
    expect(foldersTable(wrapper).findAllComponents({ name: 'InputText' })).toHaveLength(1) // just "Path"

    wrapper.unmount()
  })

  it('shows the missing-filename-pattern validation hint only once match_by is "filename" and the pattern is blank', async () => {
    const wrapper = mountSection({
      watchedFolders: [makeFolder({ kind: 'documents', match_by: 'filename', filename_pattern: '' })],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t(
        'adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.missingFilenamePattern',
      ),
    )

    wrapper.unmount()
  })

  // ── File types (made/bought extension chips) ─────────────────────────────

  it('renders the made/bought file-type chips with their hints', async () => {
    const wrapper = mountSection({
      madeItemExtensions: ['sldprt'],
      boughtItemExtensions: ['sldprt', 'sldasm'],
    })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.hint'),
    )
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.hint'),
    )
    const tags = wrapper.findAllComponents({ name: 'Tag' }).map((tag) => tag.props('value'))
    expect(tags).toEqual(expect.arrayContaining(['sldprt', 'sldasm']))

    wrapper.unmount()
  })

  // InputText forwards `placeholder` through $attrs onto the native
  // <input> rather than declaring it as its own prop (same note as
  // Button's `disabled` elsewhere in this codebase), so it shows up on
  // `attributes()`, not `props()`.
  function extensionInput(
    wrapper: ReturnType<typeof mountSection>,
    key: 'madeItemExtensions' | 'boughtItemExtensions',
  ) {
    const placeholder = i18n.global.t(
      `adminSettings.solidworksPdm.pdm.sync.${key}.placeholder`,
    ) as string
    return wrapper
      .findAllComponents({ name: 'InputText' })
      .find((i) => i.attributes('placeholder') === placeholder)!
  }

  it('adds a normalised, deduplicated extension to the made-item list on Enter', async () => {
    const wrapper = mountSection({ madeItemExtensions: ['sldprt'] })
    await flushPromises()

    const madeInput = extensionInput(wrapper, 'madeItemExtensions')
    await madeInput.setValue('.SLDPRT')
    await madeInput.trigger('keydown.enter')

    // Already on the list once normalised (leading dot stripped, lower-cased).
    expect(wrapper.emitted('update:madeItemExtensions')).toBeUndefined()

    await madeInput.setValue('SLDDRW')
    await madeInput.trigger('keydown.enter')

    expect(wrapper.emitted('update:madeItemExtensions')).toEqual([[['sldprt', 'slddrw']]])

    wrapper.unmount()
  })

  it('removes an extension from the bought-item list by its own remove button', async () => {
    const wrapper = mountSection({ boughtItemExtensions: ['sldprt', 'sldasm'] })
    await flushPromises()

    const removeLabel = i18n.global.t(
      'adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.remove',
      { extension: 'sldasm' },
    ) as string
    const removeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.attributes('aria-label') === removeLabel)!
    await removeButton.trigger('click')

    expect(wrapper.emitted('update:boughtItemExtensions')).toEqual([[['sldprt']]])

    wrapper.unmount()
  })

  // ── Document categories (extension -> category) ───────────────────────────

  it('renders one row per document category entry, and adds/removes rows', async () => {
    const wrapper = mountSection({ documentCategories: { pdf: 'drawing', dxf: 'dxf' } })
    await flushPromises()

    const categoryTable = wrapper.findAllComponents({ name: 'DataTable' })[1]!
    expect(categoryTable.findAll('tbody tr')).toHaveLength(2)

    const addButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === i18n.global.t('adminSettings.solidworksPdm.pdm.sync.documentCategories.addRow'))!
    await addButton.trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.findAllComponents({ name: 'DataTable' })[1]!.findAll('tbody tr')).toHaveLength(3)

    wrapper.unmount()
  })

  it('writes an edited extension/category back onto the documentCategories model', async () => {
    const wrapper = mountSection({ documentCategories: { pdf: 'drawing' } })
    await flushPromises()

    const categoryTable = wrapper.findAllComponents({ name: 'DataTable' })[1]!
    const categorySelect = categoryTable.findComponent({ name: 'Select' })
    await categorySelect.vm.$emit('update:modelValue', 'image')
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('update:documentCategories')!
    const last = emitted[emitted.length - 1]![0]
    expect(last).toEqual({ pdf: 'image' })

    wrapper.unmount()
  })

  it('ticks the made and bought checkboxes for every kind a row does not exclude', async () => {
    const wrapper = mountSection({
      documentCategories: { pdf: 'drawing', step: 'step' },
      documentExcludedKinds: { step: ['bought'] },
    })
    await flushPromises()

    const checked = (kind: string) =>
      wrapper
        .findAllComponents({ name: 'Checkbox' })
        .filter((c) => c.attributes('data-testid') === `pdm-category-${kind}`)
        .map((c) => c.props('modelValue'))
    expect(checked('made')).toEqual([true, true])
    expect(checked('bought')).toEqual([true, false])

    wrapper.unmount()
  })

  it('writes an unticked kind back onto the documentExcludedKinds model', async () => {
    const wrapper = mountSection({ documentCategories: { pdf: 'drawing', step: 'step' } })
    await flushPromises()

    const boughtBoxes = wrapper
      .findAllComponents({ name: 'Checkbox' })
      .filter((c) => c.attributes('data-testid') === 'pdm-category-bought')
    await boughtBoxes[1]!.vm.$emit('update:modelValue', false)
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('update:documentExcludedKinds')!
    expect(emitted[emitted.length - 1]![0]).toEqual({ step: ['bought'] })

    wrapper.unmount()
  })

  // ── Load Thumbnails from PDM ─────────────────────────────────────────────

  it('shows the thumbnails-enabled toggle with its hint and emits on change', async () => {
    const wrapper = mountSection({ thumbnailsEnabled: false })
    await flushPromises()

    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.thumbnailsEnabled'),
    )
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.thumbnailsEnabledHint'),
    )

    const toggles = wrapper.findAllComponents({ name: 'ToggleSwitch' })
    await toggles[toggles.length - 1]!.vm.$emit('update:modelValue', true)

    expect(wrapper.emitted('update:thumbnailsEnabled')).toEqual([[true]])

    wrapper.unmount()
  })
})
