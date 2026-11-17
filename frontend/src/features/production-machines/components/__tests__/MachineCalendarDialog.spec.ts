import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'
import type { MachineCalendarExceptionResponse } from '../../types/machineCalendarResponse'

vi.mock('../../api/getMachineWorkingHours', () => ({
  getMachineWorkingHours: vi.fn<() => Promise<null>>().mockResolvedValue(null),
}))
vi.mock('../../api/getMachineCalendarExceptions', () => ({
  getMachineCalendarExceptions: vi
    .fn<() => Promise<MachineCalendarExceptionResponse[]>>()
    .mockResolvedValue([
      {
        id: 7,
        machine_id: 1,
        exception_date: '2026-12-24',
        available_minutes: 0,
        note: 'Christmas Eve',
      } as MachineCalendarExceptionResponse,
    ]),
}))
vi.mock('@/features/admin-settings', () => ({
  useAdminSettingsStore: () => ({ settings: { production: null }, fetch: vi.fn<() => Promise<void>>() }),
}))

import MachineCalendarDialog from '../MachineCalendarDialog.vue'

async function mountDialog(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(MachineCalendarDialog, {
    pinia,
    attachTo: document.body,
    props: { machine: { id: 1 } as ProductionMachineResponse, visible: false },
    global: { plugins: [ConfirmationService] },
  })
  await wrapper.setProps({ visible: true })
  await nextTick()
  await flushPromises()
  return wrapper
}

function tooltipOf(element: Element | null | undefined): string | undefined {
  return (element as (HTMLElement & { $_ptooltipValue?: string }) | null | undefined)?.$_ptooltipValue
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MachineCalendarDialog', () => {
  it('lets a holder of write:machines edit, delete and add exceptions', async () => {
    const wrapper = await mountDialog([Permission.WRITE_MACHINES])

    const submit = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="machine-calendar-exception-submit"]',
    )
    expect(submit?.disabled).toBe(false)
    const remove = document.body.querySelector<HTMLButtonElement>('.row-actions button[aria-label="Delete"]')
    expect(remove?.disabled).toBe(false)
    wrapper.unmount()
  })

  it('shows the exception controls disabled with the missing permission without write:machines', async () => {
    const wrapper = await mountDialog([])

    const submit = document.body.querySelector<HTMLButtonElement>(
      '[data-testid="machine-calendar-exception-submit"]',
    )
    expect(submit?.disabled).toBe(true)
    expect(tooltipOf(submit?.parentElement)).toBe('This needs the permission Write Production Machines.')

    const rowActions = document.body.querySelector('.row-actions')
    expect(rowActions?.querySelectorAll('button:disabled')).toHaveLength(2)
    expect(tooltipOf(rowActions)).toBe('This needs the permission Write Production Machines.')
    wrapper.unmount()
  })
})
