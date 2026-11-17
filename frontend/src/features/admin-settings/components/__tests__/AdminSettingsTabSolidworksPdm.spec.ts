import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  AdminMadeItemSettings,
  AdminPdmSettings,
  AllAdminSettings,
} from '../../types/adminSettingsTypes'

// Mount/user-fixture pattern mirrors AdminSettingsTabProduction.*.spec.ts:
// only `made_items` and `pdm` are seeded, the rest of AllAdminSettings would
// be dead weight for a tab that reads only those two domains. The
// SolidWorks PDM section's ownership/mapping table lives inside this tab's
// accordion, without a web_requires_revision column, which belongs to the
// Numbering tab (see AdminSettingsTabNumbering.spec.ts).

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()
const postMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    // PdmSyncSection fetches the workflow list on mount whenever `configured`
    // is true (the fixture default). An empty array is a harmless "no
    // states yet" default for every test in this file, none of which assert
    // on workflow options (see PdmSyncSection.spec.ts for that). `/users/directory`
    // is special-cased: usersStore.refresh() (PdmUsersDialog's Glados-user
    // picker) unwraps `response.items`, unlike every other GET here, which
    // returns a bare array.
    get: vi.fn<(url: string) => Promise<unknown>>((url: string) =>
      Promise.resolve({ data: url === '/users/directory' ? { items: [], total: 0, limit: 0, skip: 0 } : [] }),
    ),
    put: (url: string, payload: unknown) => putMock(url, payload),
    post: (url: string) => postMock(url),
  },
}))

import api from '@/core/api'
import { userWithPermissions } from '@/test-utils/factories'
import AdminSettingsTabSolidworksPdm from '../AdminSettingsTabSolidworksPdm.vue'

function makeRunningRun() {
  const now = new Date().toISOString()
  return {
    id: 7,
    public_id: '77777777-7777-7777-7777-777777777777',
    started_at: now,
    finished_at: null,
    trigger: 'manual',
    files_seen: 10,
    changed: 4,
    ingested: 2,
    skipped: 0,
    conflicts: 0,
    errors: 0,
    missing: 0,
    error: null,
    summary: null,
    folders_walked: 1,
    folders_skipped_cold: 0,
    phase: 'ingesting',
    current_path: '\\Development',
    files_queued: 4,
    files_processed: 2,
    progress_at: now,
  }
}

// A small representative subset of the real ownership table rather than
// the full 34/32-field list. Every field named here has real i18n labels
// and notes, so the component behaves exactly as it would with the full
// backend payload; the point of these tests is the tab's rendering and
// validation logic, not exhaustive field coverage.
function makePdmSettings(overrides: Partial<AdminPdmSettings> = {}): AdminPdmSettings {
  return {
    id: 1,
    addin_language: '',
    mutating_operations_enabled: false,
    public_id: '22222222-2222-2222-2222-222222222222',
    set_approver_from_pdm: false,
    made_item_variable_map: {
      part_number: 'PDM.PartNumber',
      revision: 'PDM.Revision',
      article_name: 'Glados.ArticleName',
      mass: 'Glados.Mass',
    },
    bought_item_variable_map: {
      part_number: 'PDM.PartNumber',
      revision: 'PDM.Revision',
      article_name: 'Glados.ArticleName',
    },
    item_fields: {
      made: [
        { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
        { field: 'mass', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
        { field: 'source_item_id', owner: 'addin_web', mappable: true, policy_applicable: true, label_of: null },
        { field: 'id', owner: 'server', mappable: false, policy_applicable: false, label_of: null },
      ],
      bought: [
        { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
        { field: 'id', owner: 'server', mappable: false, policy_applicable: false, label_of: null },
      ],
    },
    enabled: false,
    base_url: 'http://pdm.example.com:65453',
    vault_name: 'MainVault',
    username: 'glados-service',
    password_configured: true,
    verify_certificate: true,
    timeout_seconds: 15,
    configured: true,
    session: { active: true, obtained_at: '2026-09-01T10:00:00Z', user_id: 7 },
    watched_folders: [
      {
        path: '\\Made-Parts',
        kind: 'made',
        recursive: true,
        enabled: true,
        match_by: null,
        filename_pattern: null,
        folder_id: 5,
      },
    ],
    made_released_state_ids: [10],
    made_obsolete_state_ids: [20],
    made_replaced_state_ids: [30],
    bought_released_state_ids: [10],
    bought_obsolete_state_ids: [20],
    bought_replaced_state_ids: [30],
    document_released_state_ids: [40],
    poll_interval_minutes: 15,
    cold_folder_max_multiplier: 8,
    ingest_concurrency: 4,
    vault_id: 'vault-guid',
    cad_items_read_only: true,
    last_poll_at: '2026-09-02T08:00:00Z',
    last_poll_error: null,
    last_poll_summary: '3 files ingested',
    writeback_enabled: false,
    made_item_extensions: ['sldprt'],
    bought_item_extensions: ['sldasm', 'sldprt'],
    document_categories: { pdf: 'drawing', dxf: 'dxf', step: 'step', stp: 'step' },
    document_excluded_kinds: {},
    thumbnails_enabled: false,
    stuck_after_days: 7,
    snapshot_counts: { ingested: 3, pending: 0 },
    // Empty by default so the "saves ... together" full-payload test below
    // stays simple; individual required-field tests override these three.
    required_fields: { made: [], bought: [] },
    // revision is not locked for bought items (it is data, not identity,
    // see docs/FIELD_OWNERSHIP.md principle 2), unlike made items.
    locked_required_fields: {
      made: ['part_number', 'revision', 'article_name'],
      bought: ['part_number', 'article_name', 'order_code_1', 'manufacturer_id'],
    },
    required_field_rules: { made: [], bought: [] },
    // Empty by default, so no test outside the "feature-tree templates"
    // describe block below sees a link warning. That block overrides these
    // two explicitly with templates linking to the fixture's own mapping.
    made_feature_tree_template: '',
    bought_feature_tree_template: '',
    ...overrides,
  }
}

function makeMadeItemSettings(
  overrides: Partial<AdminMadeItemSettings> = {},
): AdminMadeItemSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    item_number_format: 'FAB-{yy}-{seq:05d}',
    lot_number_format: 'LOT-{yy}-{seq:05d}',
    example: 'FAB-26-00001',
    lot_example: 'LOT-26-00001',
    calculation_number_format: 'CAL-{yy}-{seq:04d}',
    checklist_number_format: 'CHK-{yy}-{seq:04d}',
    sequence_number_format: 'SEQ-{yy}-{seq:04d}',
    meeting_number_format: 'MTG-{yy}-{seq:04d}',
    calculation_example: 'CAL-26-0001',
    checklist_example: 'CHK-26-0001',
    sequence_example: 'SEQ-26-0001',
    meeting_example: 'MTG-26-0001',
    part_number_auto: true,
    part_number_editable: false,
    revision_start: '0',
    revision_separator: ':',
    revision_skip_ambiguous_letters: false,
    revision_only_newest_editable: true,
    revision_predecessor_status_web: 'ask',
    revision_predecessor_status_pdm: 'replaced',
    revision_field_policy: [
      { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
      { field: 'mass', web_requires_revision: true, pdm_update_in_place: true },
      { field: 'source_item_id', web_requires_revision: true, pdm_update_in_place: false },
    ],
    web_creation_allowed: true,
    pdm_part_number_pattern: '',
    ...overrides,
  }
}

async function mountTab(
  permissions: string[],
  pdm: AdminPdmSettings = makePdmSettings(),
  madeItems: AdminMadeItemSettings = makeMadeItemSettings(),
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = {
    pdm,
    made_items: madeItems,
  } as unknown as AllAdminSettings

  // A sibling <Toast/> is required for useToast().add(...) to render
  // anything at all (AdminSettingsTabNotifications.banner.spec.ts's
  // "Toast-alongside" pattern), needed here for the poll/save error toasts.
  const wrapper = mount(
    {
      components: { AdminSettingsTabSolidworksPdm, Toast },
      template: '<div><AdminSettingsTabSolidworksPdm /><Toast /></div>',
    },
    {
      attachTo: document.body,
      global: {
        plugins: [
          pinia,
          [OpenVue, { theme: { preset: Aura } }],
          ToastService,
          ConfirmationService,
          i18n,
        ],
        directives: { tooltip: Tooltip },
      },
    },
  )
  await flushPromises()
  return wrapper
}

function accordionPanels(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAllComponents({ name: 'AccordionPanel' })
}

// Scoped to the Datacard Mapping accordion: PdmSyncSection renders its
// own watched-folders DataTable further up the page (see "renders the sync
// section" below), and every other test in this file indexes
// [madeTable]/[madeTable, boughtTable] assuming exactly those two
// item-ownership tables, unaffected by a table PdmSyncSection adds or
// removes.
function dataTables(wrapper: ReturnType<typeof mount>) {
  return wrapper.findComponent({ name: 'Accordion' }).findAllComponents({ name: 'DataTable' })
}

function rowByFieldLabel(table: ReturnType<typeof dataTables>[number], labelKey: string) {
  const label = i18n.global.t(labelKey) as string
  const rows = table.findAll('tr')
  return rows.find((row) => row.text().includes(label))!
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

function pollButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find(
      (b) =>
        b.props('label') === (i18n.global.t('adminSettings.solidworksPdm.pdm.sync.pollButton') as string),
    )!
}

function pdmFilesButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('adminSettings.pdmFiles.dialogTitle') as string))!
}

function pdmSyncLogButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find(
      (b) => b.props('label') === (i18n.global.t('adminSettings.pdmSyncLog.dialogTitle') as string),
    )!
}

function pdmReconciliationButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find(
      (b) =>
        b.props('label') === (i18n.global.t('adminSettings.pdmReconciliation.dialogTitle') as string),
    )!
}

function pdmUsersButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find(
      (b) =>
        b.props('label') ===
        (i18n.global.t('adminSettings.solidworksPdm.pdm.userMatching.matchButton') as string),
    )!
}

function addFolderButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find(
      (b) =>
        b.props('label') ===
        (i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.addButton') as string),
    )!
}

describe('AdminSettingsTabSolidworksPdm', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockImplementation((url) => {
      if (url === '/admin/settings/made-items') return Promise.resolve({ data: makeMadeItemSettings() })
      if (url === '/admin/settings/pdm') return Promise.resolve({ data: makePdmSettings() })
      return Promise.resolve({ data: {} })
    })
    postMock.mockReset()
    postMock.mockResolvedValue({ data: { accepted: true } })
  })

  it('renders the connection section and an accordion with a made and a bought panel', async () => {
    const wrapper = await mountTab(['write:settings'])

    // The connection fields render above the
    // Datacard Mapping accordion via PdmConnectionSection.
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.connectionSection'),
    )
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.baseUrl'))
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.datacardSection'),
    )
    expect(accordionPanels(wrapper)).toHaveLength(2)
    expect(dataTables(wrapper)).toHaveLength(2)

    wrapper.unmount()
  })

  // PdmSyncSection renders below PdmConnectionSection and above the
  // Datacard Mapping accordion, contributing its own watched-folders
  // DataTable and Document Categories DataTable. Four DataTables total on
  // the page, only two of which are the item-ownership tables `dataTables()`
  // scopes to everywhere else in this file.
  it('renders the sync section between the connection fields and the Datacard accordion', async () => {
    const wrapper = await mountTab(['write:settings'])

    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.solidworksPdm.pdm.sync.title'))
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.title'),
    )
    expect(wrapper.findAllComponents({ name: 'DataTable' })).toHaveLength(4)

    const connectionIndex = wrapper.html().indexOf(
      i18n.global.t('adminSettings.solidworksPdm.pdm.connectionSection') as string,
    )
    const syncIndex = wrapper.html().indexOf(
      i18n.global.t('adminSettings.solidworksPdm.pdm.sync.title') as string,
    )
    const datacardIndex = wrapper.html().indexOf(
      i18n.global.t('adminSettings.solidworksPdm.pdm.datacardSection') as string,
    )
    expect(connectionIndex).toBeGreaterThanOrEqual(0)
    expect(connectionIndex).toBeLessThan(syncIndex)
    expect(syncIndex).toBeLessThan(datacardIndex)

    wrapper.unmount()
  })

  it('keeps both the made-items and bought-items panels collapsed by default', async () => {
    const wrapper = await mountTab(['write:settings'])
    const [madePanel, boughtPanel] = accordionPanels(wrapper)

    expect(madePanel!.classes()).not.toContain('p-accordionpanel-active')
    expect(boughtPanel!.classes()).not.toContain('p-accordionpanel-active')

    wrapper.unmount()
  })

  it('shows a mapped-field count on each panel header', async () => {
    const wrapper = await mountTab(['write:settings'])

    // Fixture: made has 5 mappable fields (part_number, revision,
    // article_name, mass, source_item_id), all mapped except source_item_id.
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.fieldsMappedCount', { mapped: 4, total: 5 }),
    )
    // Fixture: bought has 3 mappable fields, all mapped.
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.solidworksPdm.fieldsMappedCount', { mapped: 3, total: 3 }),
    )

    wrapper.unmount()
  })

  it('shows the owner badge for each row, including the "server" -> "System" label', async () => {
    const wrapper = await mountTab(['write:settings'])
    const [madeTable] = dataTables(wrapper)

    const pdmRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.part_number')
    expect(pdmRow.findComponent({ name: 'Tag' }).props('value')).toBe(
      i18n.global.t('adminSettings.itemFields.owners.pdm'),
    )

    const idRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.id')
    expect(idRow.findComponent({ name: 'Tag' }).props('value')).toBe(
      i18n.global.t('adminSettings.itemFields.owners.server'),
    )
    expect(idRow.findComponent({ name: 'Tag' }).props('value')).toBe('System')

    wrapper.unmount()
  })

  it('disables the Custom Property input for a non-mappable field and enables it for a mappable one', async () => {
    const wrapper = await mountTab(['write:settings'])
    const [madeTable] = dataTables(wrapper)

    const idRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.id')
    expect(idRow.findComponent({ name: 'InputText' }).props('disabled')).toBe(true)

    const nameRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.article_name')
    expect(nameRow.findComponent({ name: 'InputText' }).props('disabled')).toBe(false)

    wrapper.unmount()
  })

  it('renders the Update in Place (PDM) checkbox only for policy_applicable made fields, and never on bought', async () => {
    const wrapper = await mountTab(['write:settings'])
    const [madeTable, boughtTable] = dataTables(wrapper)

    // mass is both policy_applicable (Update in Place) and mappable, so it
    // also gets the Validation column's own checkbox (see the "PDM
    // required-field validation" describe block below), two in total.
    const massRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.mass')
    expect(massRow.findAllComponents({ name: 'Checkbox' })).toHaveLength(2)

    // part_number is mappable (Validation checkbox) but not
    // policy_applicable, so it still gets no Update in Place checkbox.
    const partNumberRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.part_number')
    expect(partNumberRow.findAllComponents({ name: 'Checkbox' })).toHaveLength(1)

    expect(
      boughtTable!.text().includes(i18n.global.t('adminSettings.itemFields.columns.updateInPlacePdm')),
    ).toBe(false)
    // Bought never shows Update in Place, but its three mappable rows
    // (part_number, revision, article_name) each still get a Validation
    // checkbox.
    expect(boughtTable!.findAllComponents({ name: 'Checkbox' })).toHaveLength(3)

    // The web-side column never appears here at all. It moved to Numbering.
    expect(wrapper.text()).not.toContain(
      i18n.global.t('adminSettings.numbering.revisionFieldsLabel'),
    )

    wrapper.unmount()
  })

  // The backend defaults a stored map's missing `kind` entry to "Glados.Kind"
  // on read (see _with_kind_default), but a row saved before the field
  // existed at all is still worth covering defensively. The seeding here
  // falls back to '' the same way it does for any other mappable field.
  it('renders the kind field row, prefilled from the variable map when set and empty when missing', async () => {
    const pdm = makePdmSettings({
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        kind: 'Glados.Kind',
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
      },
      item_fields: {
        made: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'kind', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
        ],
        bought: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'kind', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
        ],
      },
    })
    const wrapper = await mountTab(['write:settings'], pdm)
    const [madeTable, boughtTable] = dataTables(wrapper)

    const madeKindRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.kind')
    expect(madeKindRow.findComponent({ name: 'InputText' }).props('modelValue')).toBe('Glados.Kind')

    const boughtKindRow = rowByFieldLabel(boughtTable!, 'adminSettings.itemFields.fields.kind')
    expect(boughtKindRow.findComponent({ name: 'InputText' }).props('modelValue')).toBe('')

    wrapper.unmount()
  })

  it('blocks save and warns on a duplicate custom property within a map', async () => {
    const wrapper = await mountTab(['write:settings'])
    const [madeTable] = dataTables(wrapper)

    const nameRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.article_name')
    await nameRow.findComponent({ name: 'InputText' }).setValue('PDM.PartNumber') // collides with part_number's mapping

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.itemFields.validation.duplicateVariable'),
    )

    wrapper.unmount()
  })

  it('blocks save and warns when part_number/revision are unmapped while another field is mapped', async () => {
    const pdm = makePdmSettings({
      made_item_variable_map: { article_name: 'Glados.ArticleName' },
    })
    const wrapper = await mountTab(['write:settings'], pdm)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.itemFields.validation.missingIdentity'),
    )

    wrapper.unmount()
  })

  // The `kind` map entry (docs/FIELD_OWNERSHIP.md, principle 1) routes a `by_kind` watched folder's kind resolution from the made map
  // only, so UpdatePdmSettings rejects the bought map naming a different
  // variable rather than silently ignoring it, mirrored here client-side
  // via validateKindVariableMatch.
  it('blocks save and warns when the made and bought maps disagree on the kind variable', async () => {
    const pdm = makePdmSettings({
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        kind: 'Glados.Kind',
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        kind: 'Glados.Art',
      },
      item_fields: {
        made: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'kind', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
        ],
        bought: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'kind', owner: 'addin', mappable: true, policy_applicable: false, label_of: null },
        ],
      },
    })
    const wrapper = await mountTab(['write:settings'], pdm)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.validation.kindMismatch'))

    wrapper.unmount()
  })

  // writeback_enabled requires the three write-back variables to be
  // mapped, non-empty and identical between the made and bought maps,
  // mirrored here client-side via validateWritebackVariables, the same
  // shape as the kind-mismatch check above.
  function writebackFieldRows() {
    return [
      {
        field: 'glados_ids',
        owner: 'server' as const,
        mappable: true,
        policy_applicable: false,
        label_of: null,
      },
      {
        field: 'newest_revision_sync_state',
        owner: 'server' as const,
        mappable: true,
        policy_applicable: false,
        label_of: null,
      },
      {
        field: 'newest_revision_synced_at',
        owner: 'server' as const,
        mappable: true,
        policy_applicable: false,
        label_of: null,
      },
    ]
  }

  it('blocks save and warns when writeback_enabled is on and a write-back variable is missing', async () => {
    const pdm = makePdmSettings({
      writeback_enabled: true,
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        glados_ids: 'Glados.Ids',
        newest_revision_sync_state: 'Glados.NewestRevisionSyncState',
        // newest_revision_synced_at left unmapped.
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        glados_ids: 'Glados.Ids',
        newest_revision_sync_state: 'Glados.NewestRevisionSyncState',
        newest_revision_synced_at: 'Glados.NewestRevisionSyncedAt',
      },
      item_fields: {
        made: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
        bought: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
      },
    })
    const wrapper = await mountTab(['write:settings'], pdm)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.itemFields.validation.writebackMismatch'),
    )

    wrapper.unmount()
  })

  it('blocks save and warns when writeback_enabled is on and the maps disagree on a write-back variable', async () => {
    const writebackMap = {
      glados_ids: 'Glados.Ids',
      newest_revision_sync_state: 'Glados.NewestRevisionSyncState',
      newest_revision_synced_at: 'Glados.NewestRevisionSyncedAt',
    }
    const pdm = makePdmSettings({
      writeback_enabled: true,
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        ...writebackMap,
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        ...writebackMap,
        glados_ids: 'Glados.IdsList', // disagrees with the made map
      },
      item_fields: {
        made: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
        bought: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
      },
    })
    const wrapper = await mountTab(['write:settings'], pdm)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.itemFields.validation.writebackMismatch'),
    )

    wrapper.unmount()
  })

  it('allows save when writeback_enabled is on and all three write-back variables agree', async () => {
    const writebackMap = {
      glados_ids: 'Glados.Ids',
      newest_revision_sync_state: 'Glados.NewestRevisionSyncState',
      newest_revision_synced_at: 'Glados.NewestRevisionSyncedAt',
    }
    const pdm = makePdmSettings({
      writeback_enabled: true,
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        ...writebackMap,
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        ...writebackMap,
      },
      item_fields: {
        made: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
        bought: [
          { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          { field: 'revision', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
          ...writebackFieldRows(),
        ],
      },
    })
    const wrapper = await mountTab(['write:settings'], pdm)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(false)
    expect(wrapper.text()).not.toContain(
      i18n.global.t('adminSettings.itemFields.validation.writebackMismatch'),
    )

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
      writeback_enabled: boolean
    }
    expect(pdmPayload.writeback_enabled).toBe(true)

    wrapper.unmount()
  })

  it('saves saveMadeItems (policy) and savePdm (mapping) together, sending only mappable fields', async () => {
    const wrapper = await mountTab(['write:settings'])

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/made-items',
      expect.objectContaining({
        revision_field_policy: expect.arrayContaining([
          expect.objectContaining({ field: 'article_name' }),
          expect.objectContaining({ field: 'mass' }),
          expect.objectContaining({ field: 'source_item_id' }),
        ]),
      }),
    )
    const madeItemsPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/made-items')![1] as {
      revision_field_policy: { field: string }[]
    }
    expect(madeItemsPayload.revision_field_policy).toHaveLength(3)

    expect(putMock).toHaveBeenCalledWith('/admin/settings/pdm', {
      made_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        article_name: 'Glados.ArticleName',
        mass: 'Glados.Mass',
        // Mappable but never set by this fixture, sent as "" (not mapped).
        source_item_id: '',
      },
      bought_item_variable_map: {
        part_number: 'PDM.PartNumber',
        revision: 'PDM.Revision',
        article_name: 'Glados.ArticleName',
      },
      // Connection fields: the tab saves PdmConnectionSection's form
      // alongside the mapping, seeded unchanged from the fixture (the
      // password field is always sent as null ("keep") since the form's
      // own password input starts blank, mirroring the Mail tab).
      base_url: 'http://pdm.example.com:65453',
      vault_name: 'MainVault',
      username: 'glados-service',
      password: null,
      verify_certificate: true,
      timeout_seconds: 15,
      // Sync fields: PdmSyncSection's form, also seeded unchanged from the
      // fixture.
      enabled: false,
      watched_folders: [
        {
          path: '\\Made-Parts',
          kind: 'made',
          recursive: true,
          enabled: true,
          match_by: null,
          filename_pattern: null,
          folder_id: 5,
        },
      ],
      made_released_state_ids: [10],
      made_obsolete_state_ids: [20],
      made_replaced_state_ids: [30],
      bought_released_state_ids: [10],
      bought_obsolete_state_ids: [20],
      bought_replaced_state_ids: [30],
      document_released_state_ids: [40],
      poll_interval_minutes: 15,
      cold_folder_max_multiplier: 8,
      ingest_concurrency: 4,
      addin_language: '',
      cad_items_read_only: true,
      writeback_enabled: false,
      made_item_extensions: ['sldprt'],
      bought_item_extensions: ['sldasm', 'sldprt'],
      document_categories: { pdf: 'drawing', dxf: 'dxf', step: 'step', stp: 'step' },
      document_excluded_kinds: {},
      thumbnails_enabled: false,
      stuck_after_days: 7,
      // No required field checked and no rule checked in the fixture.
      required_fields: { made: [], bought: [] },
      // PDM user matching (see the dedicated describe block below); the
      // fixture default is off.
      set_approver_from_pdm: false,
      // Feature-tree templates (see the dedicated describe block below);
      // seeded unchanged from the fixture, empty by default here.
      made_feature_tree_template: '',
      bought_feature_tree_template: '',
    })
    // Non-mappable fields (e.g. "id") never appear in either map.
    const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
      made_item_variable_map: Record<string, string>
      bought_item_variable_map: Record<string, string>
    }
    expect(pdmPayload.made_item_variable_map).not.toHaveProperty('id')
    expect(pdmPayload.bought_item_variable_map).not.toHaveProperty('id')

    wrapper.unmount()
  })

  it('toasts the PdmSettingsInvalidError detail when the save is rejected with 400', async () => {
    putMock.mockImplementation((url) => {
      if (url === '/admin/settings/pdm') {
        return Promise.reject({
          isAxiosError: true,
          response: {
            status: 400,
            data: {
              detail: 'PDM sync cannot be enabled: no released state is configured.',
              code: 'PdmSettingsInvalidError',
            },
          },
        })
      }
      return Promise.resolve({ data: makeMadeItemSettings() })
    })
    const wrapper = await mountTab(['write:settings'])

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain(
      'PDM sync cannot be enabled: no released state is configured.',
    )

    wrapper.unmount()
  })

  it('merges only pdm_update_in_place on save, preserving web_requires_revision from the store', async () => {
    const madeItems = makeMadeItemSettings({
      revision_field_policy: [
        { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
        { field: 'mass', web_requires_revision: false, pdm_update_in_place: false },
        { field: 'source_item_id', web_requires_revision: true, pdm_update_in_place: false },
      ],
    })
    const wrapper = await mountTab(['write:settings'], makePdmSettings(), madeItems)
    const [madeTable] = dataTables(wrapper)

    const massRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.mass')
    await massRow.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', true)

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    const payload = putMock.mock.calls.find(([url]) => url === '/admin/settings/made-items')![1] as {
      revision_field_policy: { field: string; web_requires_revision: boolean; pdm_update_in_place: boolean }[]
    }
    expect(payload.revision_field_policy).toEqual(
      expect.arrayContaining([
        // pdm_update_in_place flipped to true by the checkbox above;
        // web_requires_revision stayed at its store value, untouched by
        // this tab (that column belongs to the Numbering tab).
        { field: 'mass', web_requires_revision: false, pdm_update_in_place: true },
        { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
        { field: 'source_item_id', web_requires_revision: true, pdm_update_in_place: false },
      ]),
    )

    wrapper.unmount()
  })

  it('disables every input and the save button without write:settings', async () => {
    const wrapper = await mountTab([])
    const [madeTable] = dataTables(wrapper)

    expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)
    const nameRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.article_name')
    expect(nameRow.findComponent({ name: 'InputText' }).props('disabled')).toBe(true)
    expect(nameRow.findComponent({ name: 'Checkbox' }).props('disabled')).toBe(true)

    wrapper.unmount()
  })

  // The "Synchronize with PDM" button (ControlsBar): gated on the SAVED enabled
  // state (store.settings.pdm.enabled), not the unsaved syncForm toggle,
  // and on write:settings.
  describe('"Synchronize with PDM"', () => {
    it('is disabled when the saved PDM settings are not enabled', async () => {
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ enabled: false }))

      expect(pollButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('is disabled without write:settings even when enabled is saved true', async () => {
      const wrapper = await mountTab([], makePdmSettings({ enabled: true }))

      expect(pollButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('requests a poll and toasts success when enabled and write:settings are both present', async () => {
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ enabled: true }))

      expect(pollButton(wrapper).element.hasAttribute('disabled')).toBe(false)
      await pollButton(wrapper).trigger('click')
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/admin/settings/pdm/poll')
      expect(document.body.textContent).toContain(
        i18n.global.t('adminSettings.solidworksPdm.pdm.sync.pollRequested'),
      )

      wrapper.unmount()
    })

    it('opens the activity dialog after requesting a poll', async () => {
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ enabled: true }))

      await pollButton(wrapper).trigger('click')
      await flushPromises()

      expect(postMock).toHaveBeenCalledWith('/admin/settings/pdm/poll')
      expect(wrapper.findComponent({ name: 'PdmSyncActivityDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })

    it('spins while a sync runs and only opens the activity dialog when clicked', async () => {
      vi.mocked(api.get).mockImplementation((url: string) =>
        Promise.resolve({
          data:
            url === '/admin/settings/pdm/sync-activity'
              ? { requested: false, run: { ...makeRunningRun() }, recent_entries: [] }
              : url === '/users/directory'
                ? { items: [], total: 0, limit: 0, skip: 0 }
                : [],
        }),
      )
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ enabled: true }))

      expect(pollButton(wrapper).props('icon')).toContain('mdi-spin')
      await pollButton(wrapper).trigger('click')
      await flushPromises()

      expect(postMock).not.toHaveBeenCalled()
      expect(wrapper.findComponent({ name: 'PdmSyncActivityDialog' }).exists()).toBe(true)

      wrapper.unmount()
      vi.mocked(api.get).mockImplementation((url: string) =>
        Promise.resolve({ data: url === '/users/directory' ? { items: [], total: 0, limit: 0, skip: 0 } : [] }),
      )
    })

    it('toasts the backend detail when the poll request is rejected', async () => {
      postMock.mockRejectedValue({
        isAxiosError: true,
        response: { status: 409, data: { detail: 'PDM sync is not enabled.', code: 'PdmNotEnabledError' } },
      })
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ enabled: true }))

      await pollButton(wrapper).trigger('click')
      await flushPromises()

      expect(document.body.textContent).toContain(
        i18n.global.t('adminSettings.solidworksPdm.pdm.sync.pollFailed'),
      )
      expect(document.body.textContent).toContain('PDM sync is not enabled.')

      wrapper.unmount()
    })
  })

  // The "Watch folder" button lives in this tab's ControlsBar, next to
  // Save/Test connection/Synchronize with PDM
  // (see PdmSyncSection.spec.ts for the picker-opening behaviour itself,
  // tested there directly against the exposed `openAddPicker`). These
  // tests only pin that the button lives here and reaches that
  // section's picker through the template ref.
  describe('"Watch folder" (ControlsBar)', () => {
    it('opens the folder picker dialog owned by PdmSyncSection', async () => {
      const wrapper = await mountTab(['write:settings'])

      const dialog = wrapper.findComponent({ name: 'PdmFolderPickerDialog' })
      expect(dialog.props('visible')).toBe(false)

      await addFolderButton(wrapper).trigger('click')

      expect(dialog.props('visible')).toBe(true)

      wrapper.unmount()
    })

    it('is disabled when PDM is not configured', async () => {
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ configured: false }))

      expect(addFolderButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('is disabled without write:settings, even when configured', async () => {
      const wrapper = await mountTab([], makePdmSettings({ configured: true }))

      expect(addFolderButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })
  })

  // The PDM files view is a dialog opened from this tab's
  // ControlsBar (mounted with v-if, see PdmFilesDialog.vue's own header
  // comment). Its own behaviour (filters, retry/dismiss, ...) is covered
  // by PdmFilesDialog.spec.ts, this only checks the opening affordance.
  describe('"View synchronized files" dialog', () => {
    it('is closed by default and opens on click, with no badge while every snapshot count is zero', async () => {
      const wrapper = await mountTab(['write:settings'], makePdmSettings({ snapshot_counts: {} }))

      expect(wrapper.findComponent({ name: 'PdmFilesDialog' }).exists()).toBe(false)
      // OpenVue's Button defaults the `badge` prop to null, not undefined,
      // when nothing is bound.
      expect(pdmFilesButton(wrapper).props('badge')).toBeFalsy()

      await pdmFilesButton(wrapper).trigger('click')

      expect(wrapper.findComponent({ name: 'PdmFilesDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })

    it('badges the button with pending + conflict + error, ignoring other states', async () => {
      const wrapper = await mountTab(
        ['write:settings'],
        makePdmSettings({
          snapshot_counts: { pending: 2, conflict: 1, error: 1, ingested: 9, skipped: 4 },
        }),
      )

      expect(pdmFilesButton(wrapper).props('badge')).toBe('4')

      wrapper.unmount()
    })
  })

  // The sync log dialog: same v-if-mounted opening affordance
  // as the PDM files dialog above, right after it in the same ControlsBar
  // group. Its own behaviour (runs/entries tables, filters, message detail)
  // is covered by PdmSyncLogDialog.spec.ts.
  describe('"View sync log" dialog', () => {
    it('is closed by default and opens on click', async () => {
      const wrapper = await mountTab(['write:settings'])

      expect(wrapper.findComponent({ name: 'PdmSyncLogDialog' }).exists()).toBe(false)

      await pdmSyncLogButton(wrapper).trigger('click')

      expect(wrapper.findComponent({ name: 'PdmSyncLogDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })
  })

  // The reconciliation dialog: same v-if-mounted opening affordance, right
  // after the sync log button in the same ControlsBar group. Its own
  // behaviour (tiles, filters, export, row actions) is covered by
  // PdmReconciliationDialog.spec.ts; this only checks the opening
  // affordance and the open-files hand-off.
  describe('"View reconciliation" dialog', () => {
    it('is closed by default and opens on click', async () => {
      const wrapper = await mountTab(['write:settings'])

      expect(wrapper.findComponent({ name: 'PdmReconciliationDialog' }).exists()).toBe(false)

      await pdmReconciliationButton(wrapper).trigger('click')

      expect(wrapper.findComponent({ name: 'PdmReconciliationDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })

    it('opens the PDM files dialog when the reconciliation dialog emits open-files', async () => {
      const wrapper = await mountTab(['write:settings'])
      await pdmReconciliationButton(wrapper).trigger('click')

      expect(wrapper.findComponent({ name: 'PdmFilesDialog' }).exists()).toBe(false)

      await wrapper.findComponent({ name: 'PdmReconciliationDialog' }).vm.$emit('open-files')
      await flushPromises()

      expect(wrapper.findComponent({ name: 'PdmFilesDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })
  })

  describe('"Match PDM Users" dialog', () => {
    it('is closed by default and opens on click', async () => {
      const wrapper = await mountTab(['write:settings'])

      expect(wrapper.findComponent({ name: 'PdmUsersDialog' }).exists()).toBe(false)

      await pdmUsersButton(wrapper).trigger('click')

      expect(wrapper.findComponent({ name: 'PdmUsersDialog' }).exists()).toBe(true)

      wrapper.unmount()
    })

    it('is disabled while PDM is not configured', async () => {
      const pdm = makePdmSettings({ base_url: '', configured: false })
      const wrapper = await mountTab(['write:settings'], pdm)

      expect(pdmUsersButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })
  })

  describe('PDM user matching toggle (set_approver_from_pdm)', () => {
    it('seeds the checkbox from the stored settings and sends it back on save', async () => {
      const pdm = makePdmSettings({ set_approver_from_pdm: true })
      const wrapper = await mountTab(['write:settings'], pdm)

      expect(
        wrapper.text().includes(
          i18n.global.t('adminSettings.solidworksPdm.pdm.userMatching.setApproverFromPdm') as string,
        ),
      ).toBe(true)

      await saveButton(wrapper).trigger('click')
      await flushPromises()

      const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
        set_approver_from_pdm: boolean
      }
      expect(pdmPayload.set_approver_from_pdm).toBe(true)

      wrapper.unmount()
    })
  })

  // Feature-tree templates (docs/FIELD_OWNERSHIP.md's "Label properties and
  // the feature-tree template" section): FeatureTreeTemplateField.vue, one
  // instance per kind under that kind's ItemFieldOwnershipTable.
  describe('feature-tree templates', () => {
    // Both templates link only to properties in the default fixture's own
    // variable maps (see makePdmSettings above).
    const MADE_TEMPLATE = '$PRP:"PDM.PartNumber" Rev$PRP:"PDM.Revision" ($PRP:"Glados.ArticleName")'
    const BOUGHT_TEMPLATE = '$PRP:"Glados.ArticleName" ($PRP:"PDM.PartNumber")'

    function templateInput(wrapper: ReturnType<typeof mount>, index: 0 | 1) {
      return accordionPanels(wrapper)[index]!.find<HTMLInputElement>('input.feature-tree-input')
    }

    function chip(wrapper: ReturnType<typeof mount>, index: 0 | 1, field: string) {
      return accordionPanels(wrapper)[index]!
        .findAllComponents({ name: 'Tag' })
        .find(
          (tag) =>
            tag.classes('var-chip') &&
            tag.text() === i18n.global.t(`adminSettings.itemFields.fields.${field}`),
        )
    }

    function mountWithTemplates(overrides: Partial<AdminPdmSettings> = {}) {
      return mountTab(
        ['write:settings'],
        makePdmSettings({
          made_feature_tree_template: MADE_TEMPLATE,
          bought_feature_tree_template: BOUGHT_TEMPLATE,
          ...overrides,
        }),
      )
    }

    it('seeds both inputs from the stored settings and sends them back unchanged on save', async () => {
      const wrapper = await mountWithTemplates()

      expect(templateInput(wrapper, 0).element.value).toBe(MADE_TEMPLATE)
      expect(templateInput(wrapper, 1).element.value).toBe(BOUGHT_TEMPLATE)

      await saveButton(wrapper).trigger('click')
      await flushPromises()

      const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
        made_feature_tree_template: string
        bought_feature_tree_template: string
      }
      expect(pdmPayload.made_feature_tree_template).toBe(MADE_TEMPLATE)
      expect(pdmPayload.bought_feature_tree_template).toBe(BOUGHT_TEMPLATE)

      wrapper.unmount()
    })

    it('sends an edited template verbatim on save', async () => {
      const wrapper = await mountWithTemplates()

      await templateInput(wrapper, 0).setValue('{Draft} $PRP:"Glados.ArticleName"')
      await saveButton(wrapper).trigger('click')
      await flushPromises()

      const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
        made_feature_tree_template: string
      }
      expect(pdmPayload.made_feature_tree_template).toBe('{Draft} $PRP:"Glados.ArticleName"')

      wrapper.unmount()
    })

    it('inserts a link to the mapped property of a chip', async () => {
      const wrapper = await mountWithTemplates()

      await templateInput(wrapper, 0).setValue('')
      await chip(wrapper, 0, 'mass')!.trigger('click')

      expect(templateInput(wrapper, 0).element.value).toBe('$PRP:"Glados.Mass"')

      wrapper.unmount()
    })

    it('offers no chip for an unmapped field', async () => {
      const wrapper = await mountWithTemplates()

      expect(chip(wrapper, 0, 'source_item_id')).toBeUndefined()
      expect(chip(wrapper, 0, 'article_name')).toBeDefined()

      wrapper.unmount()
    })

    it('renders a live preview with a generic sample per linked field', async () => {
      const wrapper = await mountWithTemplates()

      await templateInput(wrapper, 0).setValue('$PRP:"Glados.ArticleName" #$PRP:"PDM.PartNumber"')

      const preview = accordionPanels(wrapper)[0]!.find('.preview').text()
      expect(preview).toContain(`<${i18n.global.t('adminSettings.itemFields.fields.article_name')}>`)
      expect(preview).toContain(`<${i18n.global.t('adminSettings.itemFields.fields.part_number')}>`)
      expect(preview).not.toContain('$PRP')

      wrapper.unmount()
    })

    it('warns about a link outside the field mapping without blocking Save', async () => {
      const wrapper = await mountWithTemplates()

      await templateInput(wrapper, 0).setValue('$PRP:"SW-File Name"')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain(
        i18n.global.t('adminSettings.itemFields.featureTree.unknownProperties', {
          properties: 'SW-File Name',
        }),
      )
      expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(false)

      wrapper.unmount()
    })

    it('shows an inline error and disables Save for a link to its own property', async () => {
      const fixture = makePdmSettings()
      const wrapper = await mountWithTemplates({
        bought_item_variable_map: {
          ...fixture.bought_item_variable_map,
          feature_tree_representation: 'Glados.FeatureTreeRepresentation',
        },
        item_fields: {
          ...fixture.item_fields,
          bought: [
            ...fixture.item_fields.bought,
            {
              field: 'feature_tree_representation',
              owner: 'addin',
              mappable: true,
              policy_applicable: false,
              label_of: null,
            },
          ],
        },
      })

      await templateInput(wrapper, 1).setValue('$PRP:"Glados.FeatureTreeRepresentation"')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain(
        i18n.global.t('adminSettings.itemFields.featureTree.selfReference', {
          property: 'Glados.FeatureTreeRepresentation',
        }),
      )
      expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('shows an inline error and disables Save for a template over the length cap', async () => {
      const wrapper = await mountWithTemplates()

      await templateInput(wrapper, 0).setValue('x'.repeat(256))
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain(
        i18n.global.t('adminSettings.itemFields.featureTree.tooLong', { max: 255 }),
      )
      expect(saveButton(wrapper).element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('disables the input when canWrite is false', async () => {
      const wrapper = await mountTab([])

      expect(templateInput(wrapper, 0).attributes('disabled')).toBeDefined()

      wrapper.unmount()
    })
  })

  // Required-field validation (docs/PDM_INTEGRATION.md's "required fields"
  // section): the "Further Rules" checklist under the made table, one
  // checkbox per required_field_rules.made name, plus the required_fields
  // sent on save alongside the rest of the datacard mapping.
  describe('PDM required-field validation', () => {
    function ruleRow(wrapper: ReturnType<typeof mount>, label: string) {
      return wrapper.findAll('.required-rule-row').find((row) => row.text().includes(label))!
    }

    it('renders the "Further Rules" checklist under the made table with its helper sentence', async () => {
      const pdm = makePdmSettings({ required_field_rules: { made: ['fabrication_step'], bought: [] } })
      const wrapper = await mountTab(['write:settings'], pdm)

      expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.requiredRulesTitle'))
      expect(wrapper.text()).toContain(i18n.global.t('adminSettings.itemFields.requiredRulesHint'))
      expect(wrapper.text()).toContain(
        i18n.global.t('adminSettings.itemFields.requiredRules.fabrication_step'),
      )

      wrapper.unmount()
    })

    it('does not render the checklist for a kind whose required_field_rules list is empty', async () => {
      // The default fixture has both lists empty.
      const wrapper = await mountTab(['write:settings'])

      expect(wrapper.text()).not.toContain(
        i18n.global.t('adminSettings.itemFields.requiredRulesTitle'),
      )
      expect(wrapper.findAll('.required-rule-row')).toHaveLength(0)

      wrapper.unmount()
    })

    it('checks the rule checkbox iff its name is already in required_fields.made', async () => {
      const pdm = makePdmSettings({
        required_field_rules: { made: ['fabrication_step'], bought: [] },
        required_fields: { made: ['fabrication_step'], bought: [] },
      })
      const wrapper = await mountTab(['write:settings'], pdm)

      const label = i18n.global.t('adminSettings.itemFields.requiredRules.fabrication_step') as string
      const checkbox = ruleRow(wrapper, label).findComponent({ name: 'Checkbox' })
      expect(checkbox.props('modelValue')).toBe(true)

      wrapper.unmount()
    })

    it('sends required_fields on save, excluding locked names, including a checked configurable field and a checked rule', async () => {
      const pdm = makePdmSettings({
        required_field_rules: { made: ['fabrication_step'], bought: [] },
        required_fields: { made: [], bought: [] },
      })
      const wrapper = await mountTab(['write:settings'], pdm)
      const [madeTable] = dataTables(wrapper)

      // mass is a configurable (non-locked) mappable made field in the
      // fixture: two checkboxes on its row, Update in Place first and the
      // new Validation column's checkbox last.
      const massRow = rowByFieldLabel(madeTable!, 'adminSettings.itemFields.fields.mass')
      const massCheckboxes = massRow.findAllComponents({ name: 'Checkbox' })
      expect(massCheckboxes).toHaveLength(2)
      await massCheckboxes[1]!.setValue(true)

      const ruleLabel = i18n.global.t('adminSettings.itemFields.requiredRules.fabrication_step') as string
      await ruleRow(wrapper, ruleLabel).findComponent({ name: 'Checkbox' }).setValue(true)

      await saveButton(wrapper).trigger('click')
      await flushPromises()

      const pdmPayload = putMock.mock.calls.find(([url]) => url === '/admin/settings/pdm')![1] as {
        required_fields: { made: string[]; bought: string[] }
      }
      expect([...pdmPayload.required_fields.made].sort()).toEqual(['fabrication_step', 'mass'])
      expect(pdmPayload.required_fields.bought).toEqual([])
      // Locked rows render checked and disabled in the table, but a locked
      // name must never be sent back, the backend rejects it outright.
      expect(pdmPayload.required_fields.made).not.toContain('part_number')
      expect(pdmPayload.required_fields.made).not.toContain('revision')
      expect(pdmPayload.required_fields.made).not.toContain('article_name')

      wrapper.unmount()
    })

    it('shows the optional-revision hint under the bought table only while its checkbox is unchecked', async () => {
      // revision is not locked for bought items (unlike made), so it
      // renders as a normal checkbox in the bought table, see the
      // fixture's locked_required_fields.bought.
      const wrapper = await mountTab(['write:settings'])
      const [, boughtTable] = dataTables(wrapper)

      const revisionRow = rowByFieldLabel(boughtTable!, 'adminSettings.itemFields.fields.revision')
      const checkbox = revisionRow.findComponent({ name: 'Checkbox' })

      expect(checkbox.props('modelValue')).toBe(false)
      expect(wrapper.text()).toContain(
        i18n.global.t('adminSettings.solidworksPdm.pdm.boughtRevisionOptionalHint'),
      )

      await checkbox.setValue(true)

      expect(wrapper.text()).not.toContain(
        i18n.global.t('adminSettings.solidworksPdm.pdm.boughtRevisionOptionalHint'),
      )

      wrapper.unmount()
    })
  })

  describe('the critical endpoints switch', () => {
    function buttonLabelled(wrapper: ReturnType<typeof mount>, key: string) {
      return wrapper
        .findAllComponents({ name: 'Button' })
        .find((b) => b.props('label') === (i18n.global.t(key) as string))
    }

    async function openConsole(pdm: AdminPdmSettings) {
      const wrapper = await mountTab(['write:settings'], pdm)
      await buttonLabelled(wrapper, 'adminSettings.solidworksPdm.pdm.console.toggle')!.trigger('click')
      await flushPromises()
      return wrapper
    }

    it('is disabled while the deployment leaves mutating operations off', async () => {
      const wrapper = await openConsole(makePdmSettings({ mutating_operations_enabled: false }))

      const toggle = buttonLabelled(wrapper, 'adminSettings.solidworksPdm.pdm.console.criticalToggle')!
      expect(toggle.element.hasAttribute('disabled')).toBe(true)

      wrapper.unmount()
    })

    it('is available once the deployment allows mutating operations', async () => {
      const wrapper = await openConsole(makePdmSettings({ mutating_operations_enabled: true }))

      const toggle = buttonLabelled(wrapper, 'adminSettings.solidworksPdm.pdm.console.criticalToggle')!
      expect(toggle.element.hasAttribute('disabled')).toBe(false)

      wrapper.unmount()
    })
  })
})
