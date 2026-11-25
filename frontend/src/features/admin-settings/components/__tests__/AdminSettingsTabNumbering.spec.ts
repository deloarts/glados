import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  AdminGeneralSettings,
  AdminMadeItemSettings,
  AdminOrderSettings,
  AdminPdmSettings,
  AdminProductionSettings,
  AllAdminSettings,
} from '../../types/adminSettingsTypes'

// Mount/user-fixture pattern mirrors AdminSettingsTabProduction.*.spec.ts. The
// tab includes new Revisions and External (PDM) pattern sections. The
// per-field ownership/mapping table moved to the SolidWorks PDM tab's
// section (see AdminSettingsTabSolidworksPdm.spec.ts) and is out of scope
// here: this file only covers the web_requires_revision checkbox list this
// tab itself owns.

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabNumbering from '../AdminSettingsTabNumbering.vue'

function makeOrderSettings(overrides: Partial<AdminOrderSettings> = {}): AdminOrderSettings {
  return {
    over_delivery_tolerance_percent: 0,
    under_delivery_tolerance_percent: 0,
    quote_request_number_format: 'RFQ-{yy}-{seq:05d}',
    quote_request_number_example: 'RFQ-26-00001',
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    order_number_format: 'ORD-{yy}-{seq:05d}',
    example: 'ORD-26-00001',
    part_number_format: 'PUR-{yy}-{seq:05d}',
    part_number_example: 'PUR-26-00001',
    part_number_auto: true,
    part_number_editable: false,
    web_creation_allowed: true,
    pdm_part_number_pattern: '',
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
    ],
    web_creation_allowed: true,
    pdm_part_number_pattern: '',
    ...overrides,
  }
}

function makeProductionSettings(
  overrides: Partial<AdminProductionSettings> = {},
): AdminProductionSettings {
  return {
    frozen_window_hours: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    production_order_number_format: 'PON-{yy}-{seq:05d}',
    default_weekly_hours: {},
    default_external_lead_days: 0,
    response_time_days: 1,
    internal_handoff_minutes: 0,
    external_safety_margin_days: 2,
    example: 'PON-26-00001',
    require_qa: false,
    default_inspection_method_id: null,
    require_source_item_approval: false,
    assign_approved_material_to_item: false,
    overwrite_item_material_on_approval: false,
    external_first_step_needs_no_material: true,
    ...overrides,
  }
}

// A small representative subset of the static ownership table, just enough to
// exercise the "one policy_applicable field, one row" logic. Deliberately
// matches makeMadeItemSettings()'s default revision_field_policy (a single
// 'article_name' entry) so tests that don't override either fixture stay
// consistent with each other.
function makePdmSettings(overrides: Partial<AdminPdmSettings> = {}): AdminPdmSettings {
  return {
    id: 1,
    addin_language: '',
    mutating_operations_enabled: false,
    public_id: '22222222-2222-2222-2222-222222222222',
    set_approver_from_pdm: false,
    made_item_variable_map: {},
    bought_item_variable_map: {},
    item_fields: {
      made: [
        { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
        { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
      ],
      bought: [],
    },
    // Empty by default: this tab never renders ItemFieldOwnershipTable
    // itself (see its own file's header comment), so no test here exercises
    // derived rows.
    enabled: false,
    base_url: '',
    vault_name: '',
    username: '',
    password_configured: false,
    verify_certificate: true,
    timeout_seconds: 15,
    configured: false,
    session: { active: false, obtained_at: null, user_id: null },
    watched_folders: [],
    made_released_state_ids: [],
    made_obsolete_state_ids: [],
    made_replaced_state_ids: [],
    bought_released_state_ids: [],
    bought_obsolete_state_ids: [],
    bought_replaced_state_ids: [],
    document_released_state_ids: [],
    poll_interval_minutes: 15,
    cold_folder_max_multiplier: 8,
    ingest_concurrency: 4,
    vault_id: '',
    cad_items_read_only: true,
    last_poll_at: null,
    last_poll_error: null,
    last_poll_summary: null,
    writeback_enabled: false,
    made_item_extensions: ['sldprt'],
    bought_item_extensions: ['sldasm', 'sldprt'],
    document_categories: {},
    document_excluded_kinds: {},
    thumbnails_enabled: false,
    stuck_after_days: 7,
    snapshot_counts: {},
    required_fields: { made: [], bought: [] },
    locked_required_fields: {
      made: ['part_number', 'revision', 'article_name'],
      bought: ['part_number', 'revision', 'article_name', 'order_code_1', 'manufacturer_id'],
    },
    required_field_rules: { made: [], bought: [] },
    made_feature_tree_template: '{part_number} Rev{revision} ({article_name})',
    bought_feature_tree_template: '{article_name} - {order_code_1} - {manufacturer_name}',
    ...overrides,
  }
}

function makeGeneralSettings(overrides: Partial<AdminGeneralSettings> = {}): AdminGeneralSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    company_name: null,
    company_legal_name: null,
    has_company_logo: false,
    contact_email: null,
    imprint_url: null,
    privacy_url: null,
    support_url: null,
    product_number_pattern: '',
    project_number_pattern: '',
    allow_headless_projects: false,
    empty_value_placeholder: '-',
    office_launcher_enabled: false,
    office_sharepoint_url: '',
    default_language: 'enGB',
    default_timezone: 'Europe/Vienna',
    default_date_format: 'iso',
    currency: 'EUR',
    ...overrides,
  }
}

async function mountTab(
  permissions: string[],
  overrides: {
    orders?: Partial<AdminOrderSettings>
    made_items?: Partial<AdminMadeItemSettings>
    pdm?: Partial<AdminPdmSettings>
  } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = {
    orders: makeOrderSettings(overrides.orders),
    made_items: makeMadeItemSettings(overrides.made_items),
    production: makeProductionSettings(),
    general: makeGeneralSettings(),
    pdm: makePdmSettings(overrides.pdm),
  } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabNumbering, {
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function sectionLabels(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper.findAll('.section-label').map((el) => el.text())
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

// The new revision-field checkbox rows share the .field-row--toggle class
// with every other toggle row on this tab, but they are the only ones built
// around a Checkbox rather than a ToggleSwitch, which is enough to tell them
// apart without relying on DOM order.
function revisionFieldRows(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAll('.field-row--toggle')
    .filter((row) => row.findComponent({ name: 'Checkbox' }).exists())
}

describe('AdminSettingsTabNumbering', () => {
  beforeEach(() => {
    putMock.mockReset()
    putMock.mockImplementation((url) => {
      if (url === '/admin/settings/orders') return Promise.resolve({ data: makeOrderSettings() })
      if (url === '/admin/settings/made-items')
        return Promise.resolve({ data: makeMadeItemSettings() })
      if (url === '/admin/settings/production')
        return Promise.resolve({ data: makeProductionSettings() })
      if (url === '/admin/settings/general') return Promise.resolve({ data: makeGeneralSettings() })
      return Promise.resolve({ data: {} })
    })
  })

  it('renders every expected section, in order', async () => {
    const wrapper = await mountTab(['write:settings'])

    expect(sectionLabels(wrapper)).toEqual([
      i18n.global.t('adminSettings.numbering.internalSection'),
      i18n.global.t('adminSettings.numbering.externalSection'),
      i18n.global.t('adminSettings.numbering.revisionsSection'),
      i18n.global.t('adminSettings.numbering.procurementSection'),
      i18n.global.t('adminSettings.numbering.lotsSection'),
      i18n.global.t('adminSettings.numbering.productionOrdersSection'),
      i18n.global.t('adminSettings.numbering.documentsSection'),
      i18n.global.t('adminSettings.numbering.projectsProductsSection'),
    ])

    wrapper.unmount()
  })

  it('does not render the removed Unique Part Number / Part Number Source controls', async () => {
    const wrapper = await mountTab(['write:settings'])

    expect(wrapper.text()).not.toContain('Unique Part Number')
    expect(wrapper.text()).not.toContain('Part Number Source')
    expect(wrapper.text()).not.toContain('Part Number Duplicate')

    wrapper.unmount()
  })

  it('saves the calculation and checklist number formats with the made-items payload', async () => {
    const wrapper = await mountTab(['write:settings'])

    await wrapper.get('[data-testid="numbering-calculation-format"]').setValue('BER-{year}-{seq:03d}')
    await wrapper.get('[data-testid="numbering-checklist-format"]').setValue('PL-{seq:05d}')
    expect(wrapper.text()).toContain('PL-00001')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    const payload = putMock.mock.calls.find(([url]) => url === '/admin/settings/made-items')![1] as {
      calculation_number_format: string
      checklist_number_format: string
    }
    expect(payload.calculation_number_format).toBe('BER-{year}-{seq:03d}')
    expect(payload.checklist_number_format).toBe('PL-{seq:05d}')
    wrapper.unmount()
  })

  it('saves the meeting number format with the made-items payload', async () => {
    const wrapper = await mountTab(['write:settings'])

    await wrapper.get('[data-testid="numbering-meeting-format"]').setValue('BSP-{seq:03d}')
    expect(wrapper.text()).toContain('BSP-001')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    const payload = putMock.mock.calls.find(([url]) => url === '/admin/settings/made-items')![1] as {
      meeting_number_format: string
    }
    expect(payload.meeting_number_format).toBe('BSP-{seq:03d}')
    wrapper.unmount()
  })

  it('saves the revision settings (Revisions section) as part of the made-items payload', async () => {
    const wrapper = await mountTab(['write:settings'], {
      made_items: { revision_start: '0', revision_skip_ambiguous_letters: false },
    })

    // Locate the Start Revision select specifically among the tab's several
    // Selects; it's the one whose current value is the seeded '0'.
    const selects = wrapper.findAllComponents({ name: 'Select' })
    const revisionStartSelect = selects.find((s) => s.props('modelValue') === '0')!
    expect(revisionStartSelect.exists()).toBe(true)

    await revisionStartSelect.vm.$emit('update:modelValue', 'A')

    const skipToggle = wrapper
      .findAll('.field-row--toggle')
      .find(
        (row) =>
          row.find('label').text() ===
          (i18n.global.t('adminSettings.numbering.revisionSkipAmbiguousLetters') as string),
      )!
      .findComponent({ name: 'ToggleSwitch' })
    await skipToggle.vm.$emit('update:modelValue', true)

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/made-items',
      expect.objectContaining({
        revision_start: 'A',
        revision_skip_ambiguous_letters: true,
        revision_separator: ':',
        revision_only_newest_editable: true,
        revision_predecessor_status_web: 'ask',
        revision_predecessor_status_pdm: 'replaced',
        // Rebuilt from item_fields.made and the store's current value,
        // unedited here: this tab never touched the checkbox in this test.
        revision_field_policy: [
          { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
        ],
      }),
    )

    wrapper.unmount()
  })

  it('renders a checkbox for each policy_applicable made field, labeled via itemFields.fields', async () => {
    const wrapper = await mountTab(['write:settings'], {
      pdm: {
        item_fields: {
          made: [
            { field: 'part_number', owner: 'pdm', mappable: true, policy_applicable: false, label_of: null },
            { field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
            { field: 'mass', owner: 'addin', mappable: true, policy_applicable: true, label_of: null },
          ],
          bought: [],
        },
      },
      made_items: {
        revision_field_policy: [
          { field: 'article_name', web_requires_revision: true, pdm_update_in_place: false },
          { field: 'mass', web_requires_revision: false, pdm_update_in_place: true },
        ],
      },
    })

    const rows = revisionFieldRows(wrapper)
    expect(rows).toHaveLength(2)

    const articleLabel = i18n.global.t('adminSettings.itemFields.fields.article_name') as string
    const articleRow = rows.find((row) => row.text().includes(articleLabel))!
    expect(articleRow.findComponent({ name: 'Checkbox' }).props('modelValue')).toBe(true)

    const massLabel = i18n.global.t('adminSettings.itemFields.fields.mass') as string
    const massRow = rows.find((row) => row.text().includes(massLabel))!
    expect(massRow.findComponent({ name: 'Checkbox' }).props('modelValue')).toBe(false)

    // part_number is not policy_applicable, so it gets no row here at all
    // (rows.length === 2, above, already proves it; this pins down why).
    const partNumberLabel = i18n.global.t('adminSettings.itemFields.fields.part_number') as string
    expect(rows.some((row) => row.text().includes(partNumberLabel))).toBe(false)

    wrapper.unmount()
  })

  it('merges only web_requires_revision on save, preserving pdm_update_in_place from the store', async () => {
    const wrapper = await mountTab(['write:settings'], {
      pdm: {
        item_fields: {
          made: [{ field: 'article_name', owner: 'addin', mappable: true, policy_applicable: true, label_of: null }],
          bought: [],
        },
      },
      made_items: {
        revision_field_policy: [
          { field: 'article_name', web_requires_revision: false, pdm_update_in_place: true },
        ],
      },
    })

    const [row] = revisionFieldRows(wrapper)
    await row!.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', true)

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    const payload = putMock.mock.calls.find(([url]) => url === '/admin/settings/made-items')![1] as {
      revision_field_policy: { field: string; web_requires_revision: boolean; pdm_update_in_place: boolean }[]
    }
    expect(payload.revision_field_policy).toEqual([
      // web_requires_revision flipped to true by the checkbox above;
      // pdm_update_in_place stayed true from the store, untouched by this
      // tab (that column belongs to the SolidWorks PDM tab).
      { field: 'article_name', web_requires_revision: true, pdm_update_in_place: true },
    ])

    wrapper.unmount()
  })

  it('warns when the external (PDM) pattern overlaps the internal format\'s own example', async () => {
    const wrapper = await mountTab(['write:settings'], {
      made_items: { item_number_format: 'FAB-{yy}-{seq:05d}' },
    })

    expect(wrapper.text()).not.toContain(
      i18n.global.t('adminSettings.numbering.externalOverlapWarning', { example: '' }).split('{')[0],
    )

    const madePatternInput = wrapper.find('#pattern-external-made')
    await madePatternInput.setValue('FAB-\\d{2}-\\d{5}')

    expect(wrapper.findComponent({ name: 'Message' }).exists()).toBe(true)
    expect(wrapper.text()).toContain(
      i18n.global.t('adminSettings.numbering.externalOverlapWarning', { example: 'FAB-26-00001' }),
    )

    wrapper.unmount()
  })
})
