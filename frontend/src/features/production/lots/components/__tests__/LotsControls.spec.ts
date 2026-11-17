import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'

import LotsControls from '../LotsControls.vue'

function mountControls(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  return mountWithApp(LotsControls, {
    pinia,
    props: {
      showManageOrders: false,
      showManageQuotes: false,
      showManageProduction: false,
      showManageSource: false,
    },
    global: {
      directives: { tooltip: Tooltip },
      stubs: { LotCreateDialog: true, AutoPlanDialog: true, HelpButton: true },
    },
  })
}

type TooltipHost = HTMLElement & { $_ptooltipValue?: string }

function control(wrapper: ReturnType<typeof mountControls>, testId: string) {
  const button = wrapper.find(`[data-testid="${testId}"]`)
  const span = button.element.parentElement as TooltipHost
  return { disabled: button.attributes('disabled') !== undefined, tooltip: span.$_ptooltipValue }
}

describe('LotsControls', () => {
  it('shows every control disabled with the missing permission without any', async () => {
    const wrapper = mountControls([])
    await flushPromises()

    const lots = 'This needs the permission Write Production Lots.'
    expect(control(wrapper, 'new-lot')).toEqual({ disabled: true, tooltip: lots })
    expect(control(wrapper, 'edit-lots')).toEqual({ disabled: true, tooltip: lots })
    expect(control(wrapper, 'manage-production')).toEqual({ disabled: true, tooltip: lots })
    expect(control(wrapper, 'auto-plan')).toEqual({
      disabled: true,
      tooltip: 'This needs the permission Write Production Orders.',
    })
  })

  it('needs Write Production Orders for Manage Production, since it assigns machines', async () => {
    const wrapper = mountControls([Permission.WRITE_LOTS])
    await flushPromises()

    expect(control(wrapper, 'new-lot').disabled).toBe(false)
    expect(control(wrapper, 'manage-production')).toEqual({
      disabled: true,
      tooltip: 'This needs the permission Write Production Orders.',
    })
  })

  it('enables Manage Production and Auto-Plan with both permissions', async () => {
    const wrapper = mountControls([Permission.WRITE_LOTS, Permission.WRITE_PRODUCTION_ORDERS])
    await flushPromises()

    expect(control(wrapper, 'manage-production').disabled).toBe(false)
    expect(control(wrapper, 'auto-plan').disabled).toBe(false)
  })
})
