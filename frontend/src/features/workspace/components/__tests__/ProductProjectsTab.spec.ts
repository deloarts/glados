import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories'
import type { ProjectResponse } from '@/features/projects'

import ProductProjectsTab from '../ProductProjectsTab.vue'

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 7,
    public_id: 'dddddddd-0000-0000-0000-000000000007',
    project_number: 'PRJ-007',
    customer_id: null,
    customer: null,
    product_id: 1,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01T00:00:00Z',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
    ...overrides,
  }
}

async function mountTab(projects: ProjectResponse[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeTestRouter()
  await router.push('/workspace/products/1')
  await router.isReady()
  const wrapper = mountWithApp(ProductProjectsTab, {
    pinia,
    props: { projects },
    global: { plugins: [router], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('ProductProjectsTab', () => {
  it('lists the projects with a link to each one', async () => {
    const { wrapper } = await mountTab([
      makeProject({
        status: 'on_hold',
        description: 'Line extension',
        customer: { id: 3, name: 'ACME Corp' } as ProjectResponse['customer'],
      }),
    ])

    const link = wrapper.get('a[href="/workspace/projects/7"]')
    expect(link.text()).toBe('PRJ-007')
    expect(wrapper.text()).toContain('On Hold')
    expect(wrapper.text()).toContain('ACME Corp')
    expect(wrapper.text()).toContain('Line extension')
  })

  it('opens a project on row double click', async () => {
    const { wrapper, router } = await mountTab([makeProject({ id: 12 })])

    await wrapper.get('[data-testid="product-project-row"]').trigger('dblclick')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/workspace/projects/12')
  })

  it('shows the empty state without projects', async () => {
    const { wrapper } = await mountTab([])

    expect(wrapper.get('[role="status"]').text()).toContain(
      'No projects belong to this product yet.',
    )
  })
})
