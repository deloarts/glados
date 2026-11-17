import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories/router'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

const machinesPage = {
  items: [
    { id: 1, internal_name: 'CNC-01' },
    { id: 2, internal_name: 'CNC-02' },
  ],
  total: 2,
  limit: 500,
  skip: 0,
}

const downtimesPage = {
  items: [
    {
      id: 10,
      public_id: '33333333-3333-3333-3333-333333333333',
      created: '2026-01-01T08:00:00Z',
      changed: '2026-01-01T08:00:00Z',
      machine_id: 1,
      machine_internal_name: 'CNC-01',
      started_at: '2026-01-01T08:00:00Z',
      ended_at: null,
      reason: 'breakdown',
      note: null,
      reported_by_id: 1,
      reported_by_full_name: 'Tester',
      ended_by_id: null,
      ended_by_full_name: null,
      changes: [],
    },
  ],
  total: 1,
  limit: 100,
  skip: 0,
}

// Copies per call: ending a downtime updates the loaded row in place, and
// that must not leave the next test loading an already ended downtime.
const getMock = vi.fn<(url: string) => Promise<unknown>>().mockImplementation((url: string) => {
  if (url === '/production-machines/') return Promise.resolve({ data: structuredClone(machinesPage) })
  if (url === '/production-machines/downtimes') {
    return Promise.resolve({ data: structuredClone(downtimesPage) })
  }
  return Promise.reject(new Error(`unexpected GET ${url}`))
})

const postMock = vi.fn<() => Promise<unknown>>().mockResolvedValue({
  data: { ...downtimesPage.items[0], ended_at: '2026-01-01T12:00:00Z', ended_by_id: 1 },
})

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: () => postMock(),
    delete: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: undefined }),
  },
}))

const toastAddMock = vi.fn<(message: { severity: string; summary: string; detail?: string }) => void>()
vi.mock('openvue/usetoast', () => ({
  useToast: () => ({ add: toastAddMock }),
}))

import MachineDowntimesDialog from '../MachineDowntimesDialog.vue'

function mountDialog(
  props: { initialMachineId?: number | null } = {},
  permissions: string[] = ['write:machines'],
  stubs: Record<string, boolean> = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  return mountWithApp(MachineDowntimesDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false, ...props },
    global: {
      // The header's help button opens the handbook drawer, which needs a
      // router to resolve its page.
      plugins: [ConfirmationService, makeTestRouter()],
      stubs,
    },
  })
}

describe('MachineDowntimesDialog', () => {
  it('loads machines and downtimes when opened, without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountDialog()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(logs).toEqual([])
    expect(getMock).toHaveBeenCalledWith('/production-machines/')
    expect(getMock).toHaveBeenCalledWith('/production-machines/downtimes')
    // Dialog content is teleported to document.body, outside the wrapper's
    // own root element, so assert against the document rather than
    // wrapper.text() (same idiom as ProductionMachineFormDialog.spec.ts).
    expect(document.body.textContent).toContain('CNC-01')
    expect(document.body.textContent).toContain('Open')

    wrapper.unmount()
  })

  it('pre-fills the machine filter from initialMachineId', async () => {
    const wrapper = mountDialog({ initialMachineId: 2 })
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.props('modelValue')).toBe(2)

    wrapper.unmount()
  })

  it('ends an open downtime and reflects the update in the table', async () => {
    postMock.mockClear()

    const wrapper = mountDialog()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    expect(document.body.textContent).toContain('Open')

    const endButton = document.body.querySelector<HTMLButtonElement>('button[aria-label="End"]')
    expect(endButton).not.toBeNull()
    await endButton!.click()
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(document.body.textContent).not.toContain('Open')

    wrapper.unmount()
  })

  it('shows the server message when ending fails and reloads the list', async () => {
    postMock.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'The downtime has already ended.' } },
    })

    const wrapper = mountDialog()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()
    const loadsBefore = getMock.mock.calls.filter(([url]) => url === '/production-machines/downtimes').length

    const endButton = document.body.querySelector<HTMLButtonElement>('button[aria-label="End"]')
    expect(endButton).not.toBeNull()
    await endButton!.click()
    await flushPromises()

    expect(toastAddMock).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        summary: 'CNC-01',
        detail: 'The downtime has already ended.',
      }),
    )
    const loadsAfter = getMock.mock.calls.filter(([url]) => url === '/production-machines/downtimes').length
    expect(loadsAfter).toBe(loadsBefore + 1)

    wrapper.unmount()
  })

  it('opens the downtimes handbook section from the header help button', async () => {
    const wrapper = mountDialog({}, ['write:machines'], { HelpDrawer: true })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    document.body.querySelector<HTMLButtonElement>('[data-testid="downtimes-explain"]')!.click()
    await flushPromises()

    const drawer = wrapper.findComponent({ name: 'HelpDrawer' })
    expect(drawer.props('slug')).toBe('resources/machines')
    expect(drawer.props('anchor')).toBe('downtimes')
    expect(drawer.props('visible')).toBe(true)

    wrapper.unmount()
  })
})
