import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { userWithPermissions } from '@/test-utils/factories'

import type { AdminMaintenanceSettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabProduction.sourceApproval.spec.ts's mount/
// permission-user pattern and inline-store-seeding technique (here:
// `store.settings.maintenance`, since fetching would need the full
// getAllAdminSettings response mocked), plus AppSidebar.spec.ts's
// Toast-alongside-the-component pattern for asserting on toast content
// (useToast() needs a real <Toast/> in the tree to render anything).

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabMaintenance from '../AdminSettingsTabMaintenance.vue'

function makeMaintenanceSettings(
  overrides: Partial<AdminMaintenanceSettings> = {},
): AdminMaintenanceSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enabled: false,
    message: null,
    allowed_ips: [],
    ...overrides,
  }
}

async function mountTab(permissions: string[], maintenance: AdminMaintenanceSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  // Seeded directly rather than driven through fetch(): only `maintenance`
  // is under test, so the rest of AllAdminSettings would be dead weight.
  useAdminSettingsStore().settings = { maintenance } as unknown as AllAdminSettings

  const wrapper = mount(
    {
      components: { AdminSettingsTabMaintenance, Toast },
      template: '<div><AdminSettingsTabMaintenance /><Toast /></div>',
    },
    {
      attachTo: document.body,
      global: {
        plugins: [pinia, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
      },
    },
  )
  await flushPromises()
  return wrapper
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

function toggleSwitch(wrapper: ReturnType<typeof mount>) {
  return wrapper.findComponent({ name: 'ToggleSwitch' })
}

describe('AdminSettingsTabMaintenance', () => {
  beforeEach(() => {
    putMock.mockReset()
    // ToastService's teleported DOM lives in document.body and outlives one
    // test's wrapper.unmount(); see AppSidebar.spec.ts's own comment.
    document.body.innerHTML = ''
  })

  it('reflects settings.maintenance in the form', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeMaintenanceSettings({
        enabled: true,
        message: 'Upgrading the database.',
        allowed_ips: ['10.0.0.1', '10.1.0.0/16'],
      }),
    )

    expect(toggleSwitch(wrapper).props('modelValue')).toBe(true)
    expect(wrapper.findComponent({ name: 'Textarea' }).props('modelValue')).toBe(
      'Upgrading the database.',
    )
    expect(wrapper.findAllComponents({ name: 'Tag' }).map((t) => t.props('value'))).toEqual([
      '10.0.0.1',
      '10.1.0.0/16',
    ])

    wrapper.unmount()
  })

  it('disables the controls without write:settings', async () => {
    const wrapper = await mountTab([], makeMaintenanceSettings({ allowed_ips: ['10.0.0.1'] }))

    expect(toggleSwitch(wrapper).props('disabled')).toBe(true)
    // The IP list keeps its remove and add controls, disabled.
    const remove = wrapper.get('.ip-remove')
    expect(remove.attributes('disabled')).toBeDefined()
    const addRow = wrapper.get('.ip-add-row')
    expect(addRow.findAll('input').every((i) => i.attributes('disabled') !== undefined)).toBe(true)
    expect(addRow.get('button').attributes('disabled')).toBeDefined()
    // Button has no declared `disabled` prop; it derives disabled-ness
    // from $attrs.disabled at render time, so assert the rendered DOM
    // attribute rather than a component prop (see
    // AdminSettingsTabProduction.sourceApproval.spec.ts's saveButton()).
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('Save PUTs allowed_ips and the rest of the form', async () => {
    putMock.mockResolvedValue({
      data: makeMaintenanceSettings({ enabled: true, allowed_ips: ['10.0.0.1'] }),
    })
    const wrapper = await mountTab(['write:settings'], makeMaintenanceSettings())

    await toggleSwitch(wrapper).vm.$emit('update:modelValue', true)
    const ipInput = wrapper.find('input[type="text"]')
    await ipInput.setValue('10.0.0.1')
    await ipInput.trigger('keydown.enter')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/maintenance',
      expect.objectContaining({ enabled: true, allowed_ips: ['10.0.0.1'] }),
    )

    wrapper.unmount()
  })

  it('pushes the saved result onto hostStore so the in-app banner updates without a reload', async () => {
    putMock.mockResolvedValue({
      data: makeMaintenanceSettings({ enabled: true, message: 'Back in 10 minutes.' }),
    })
    const wrapper = await mountTab(['write:settings'], makeMaintenanceSettings())
    const hostStore = useHostStore()
    expect(hostStore.maintenanceEnabled).toBe(false)

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(hostStore.maintenanceEnabled).toBe(true)
    expect(hostStore.maintenanceMessage).toBe('Back in 10 minutes.')

    wrapper.unmount()
  })

  it('rejects a client-side-invalid IP without calling the backend', async () => {
    const wrapper = await mountTab(['write:settings'], makeMaintenanceSettings())

    const ipInput = wrapper.find('input[type="text"]')
    await ipInput.setValue('not an ip')
    await ipInput.trigger('keydown.enter')
    await flushPromises()

    expect(wrapper.findAllComponents({ name: 'Tag' })).toHaveLength(0)
    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.maintenance.invalidIp', { ip: 'not an ip' }) as string,
    )

    wrapper.unmount()
  })

  it('toasts the backend detail on a 422 instead of the generic error', async () => {
    putMock.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 422,
        data: { detail: 'message: String should have at most 500 characters' },
      },
    })
    const wrapper = await mountTab(['write:settings'], makeMaintenanceSettings())

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain(
      'message: String should have at most 500 characters',
    )
    expect(document.body.textContent).not.toContain(
      i18n.global.t('adminSettings.errors.unknown') as string,
    )

    wrapper.unmount()
  })

  it('toasts the generic error on a non-422 failure', async () => {
    putMock.mockRejectedValue(new Error('network down'))
    const wrapper = await mountTab(['write:settings'], makeMaintenanceSettings())

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.errors.unknown') as string,
    )

    wrapper.unmount()
  })
})
