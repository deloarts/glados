import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ConfirmationService from 'openvue/confirmationservice'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProjectFormDialog from '../ProjectFormDialog.vue'
import type { ProjectResponse } from '../../types/projectResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

const project: ProjectResponse = {
  id: 1,
  public_id: 'p-1',
  project_number: 'P-001',
  customer_id: null,
  customer: null,
  product_id: null,
  product: null,
  description: 'Test project',
  status: 'active',
  designated_user_id: 1,
  created: '2026-01-01T00:00:00+00:00',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  creator_id: 1,
  creator: null,
  production_time_budget: null,
  required_delivery_date_made: '2026-09-01',
  required_delivery_date_bought: null,
  edit_version: 0,
  actions: [],
  live_work: null,
}

function mountDialog(props: Record<string, unknown>) {
  return mountWithApp(ProjectFormDialog, {
    attachTo: document.body,
    props: { visible: true, ...props },
    global: {
      plugins: [ConfirmationService],
    },
  })
}

describe('ProjectFormDialog', () => {
  it('renders without errors when creating a project', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountDialog({})

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('renders without errors when editing a project with delivery dates and status set', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountDialog({ project })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })
})
