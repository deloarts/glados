import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '@/features/admin-settings'

import type { AdminProductionSettings, AllAdminSettings } from '@/features/admin-settings'

// Mirrors AdminSettingsTabProduction.sourceApproval.spec.ts's mount/store
// seeding pattern (see that file's header comment for why). This covers the
// two Material Approval toggles added alongside require_source_item_approval:
// assign_approved_material_to_item and overwrite_item_material_on_approval.

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

function toggleForLabel(wrapper: ReturnType<typeof mount>, labelKey: string) {
  // Matched against the row's own <label> element, not its whole text:
  // assignApprovedMaterialToItemHint's text names
  // "Overwrite Existing Upon Approval" inline, which would otherwise make a
  // substring match on the full row text pick the wrong row.
  const label = i18n.global.t(labelKey) as string
  const row = wrapper.findAll('.field-row--toggle').find((r) => r.find('label').text() === label)
  return row!.findComponent({ name: 'ToggleSwitch' })
}

function assignToggle(wrapper: ReturnType<typeof mount>) {
  return toggleForLabel(wrapper, 'adminSettings.production.assignApprovedMaterialToItem')
}

function overwriteToggle(wrapper: ReturnType<typeof mount>) {
  return toggleForLabel(wrapper, 'adminSettings.production.overwriteItemMaterialOnApproval')
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabProduction material assignment toggles', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('renders both the assign and overwrite toggles', async () => {
    const wrapper = await mountTab(['write:settings'], makeProductionSettings())

    expect(assignToggle(wrapper).exists()).toBe(true)
    expect(overwriteToggle(wrapper).exists()).toBe(true)

    wrapper.unmount()
  })

  it('disables the overwrite toggle while assign is off, and enables it once assign is on', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({ assign_approved_material_to_item: false }),
    )

    expect(overwriteToggle(wrapper).props('disabled')).toBe(true)

    await assignToggle(wrapper).vm.$emit('update:modelValue', true)

    expect(overwriteToggle(wrapper).props('disabled')).toBe(false)

    wrapper.unmount()
  })

  it('saveProduction is called with both fields once toggled and saved', async () => {
    putMock.mockResolvedValue({
      data: makeProductionSettings({
        assign_approved_material_to_item: true,
        overwrite_item_material_on_approval: true,
      }),
    })
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({
        assign_approved_material_to_item: false,
        overwrite_item_material_on_approval: false,
      }),
    )

    await assignToggle(wrapper).vm.$emit('update:modelValue', true)
    await overwriteToggle(wrapper).vm.$emit('update:modelValue', true)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/production',
      expect.objectContaining({
        assign_approved_material_to_item: true,
        overwrite_item_material_on_approval: true,
      }),
    )

    wrapper.unmount()
  })

  it('copies both values from store.settings.production into the form via the watch', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeProductionSettings({
        assign_approved_material_to_item: true,
        overwrite_item_material_on_approval: true,
      }),
    )

    expect(assignToggle(wrapper).props('modelValue')).toBe(true)
    expect(overwriteToggle(wrapper).props('modelValue')).toBe(true)

    wrapper.unmount()
  })
})
