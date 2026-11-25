import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '@/features/admin-settings'

import type { AdminProductionSettings, AllAdminSettings } from '@/features/admin-settings'

// AdminSettingsTabProduction.vue has no sibling spec of its own yet (only
// AdminSettingsTabUsers.spec.ts exists, and that tab is a different shape:
// a CRUD shell, not a settings-fields form). This mirrors that file's
// mount/permission-user pattern, plus the inline-store-seeding technique
// LotsTable.spec.ts uses for `lotsStore.items` (here: `store.settings`,
// since fetching would need the full getAllAdminSettings response mocked).

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabProduction from '../AdminSettingsTabProduction.vue'

function makeProductionSettings(
  overrides: Partial<AdminProductionSettings> = {},
): AdminProductionSettings {
  return {
    frozen_window_hours: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    production_order_number_format: 'PO-{n}',
    default_weekly_hours: {},
    default_external_lead_days: 3,
    response_time_days: 1,
    external_safety_margin_days: 2,
    example: 'PO-1',
    require_qa: false,
    default_inspection_method_id: null,
    require_source_item_approval: false,
    assign_approved_material_to_item: false,
    overwrite_item_material_on_approval: false,
    external_first_step_needs_no_material: true,
    ...overrides,
  }
}

async function mountTab(permissions: string[], production: AdminProductionSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  // Seeded directly rather than driven through fetch(): only `production`
  // is under test, so the rest of AllAdminSettings would be dead weight.
  useAdminSettingsStore().settings = { production } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabProduction, {
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function sourceApprovalToggle(wrapper: ReturnType<typeof mount>) {
  // Two more toggles (assign/overwrite material on approval) follow this one
  // in the Material Approval section, so select by row label text instead of
  // position.
  const label = i18n.global.t('adminSettings.production.requireSourceItemApproval') as string
  const row = wrapper.findAll('.field-row--toggle').find((r) => r.text().includes(label))
  return row!.findComponent({ name: 'ToggleSwitch' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabProduction source approval toggle', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('reflects settings.production.require_source_item_approval when off', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({ require_source_item_approval: false }),
    )

    expect(sourceApprovalToggle(wrapper).props('modelValue')).toBe(false)

    wrapper.unmount()
  })

  it('reflects settings.production.require_source_item_approval when on', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({ require_source_item_approval: true }),
    )

    expect(sourceApprovalToggle(wrapper).props('modelValue')).toBe(true)

    wrapper.unmount()
  })

  it('saveProduction is called with the flipped value once toggled and saved', async () => {
    putMock.mockResolvedValue({
      data: makeProductionSettings({ require_source_item_approval: true }),
    })
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({ require_source_item_approval: false }),
    )

    await sourceApprovalToggle(wrapper).vm.$emit('update:modelValue', true)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/production',
      expect.objectContaining({ require_source_item_approval: true }),
    )

    wrapper.unmount()
  })

  it('disables the toggle without write:settings', async () => {
    const wrapper = await mountTab([], makeProductionSettings())

    expect(sourceApprovalToggle(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })
})
