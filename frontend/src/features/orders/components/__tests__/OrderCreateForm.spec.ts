import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeOrderResponse } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'

import type { SupplierResponse } from '@/features/suppliers'

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import OrderCreateForm from '../OrderCreateForm.vue'

function makeSupplier(overrides: Partial<SupplierResponse> = {}): SupplierResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-07-01',
    changed: '2026-07-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Acme Supplier',
    legal_name: null,
    vat_id: null,
    level: 'B',
    capability_ids: [],
    capabilities: [],
    article_group_ids: [],
    article_groups: [],
    street: null,
    city: null,
    country: null,
    postal_code: null,
    email: null,
    phone: null,
    weblink: null,
    order_email: null,
    order_language: null,
    order_template: null,
    request_email: null,
    request_language: null,
    request_template: null,
    edp_type_number_first: false,
    creator_id: 1,
    creator: null,
    edp_code: null,
    external_lead_time_days: null,
    ...overrides,
  }
}

// Mounts closed and then opens, the way the dialog's own watch(visible) reset
// (and the supplier refresh) expects to be driven.
async function openForm() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(OrderCreateForm, {
    pinia,
    attachTo: document.body,
    props: { visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

async function clickSave(wrapper: Awaited<ReturnType<typeof openForm>>) {
  await wrapper.findAllComponents({ name: 'Button' }).at(-1)!.trigger('click')
  await flushPromises()
}

describe('OrderCreateForm', () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockResolvedValue({
      data: { items: [makeSupplier()], total: 1, limit: 1000, skip: 0 },
    })
    postMock.mockResolvedValue({ data: makeOrderResponse() })
  })

  it('associates every field label with its control via id/for', async () => {
    const wrapper = await openForm()

    const labels = document.querySelectorAll('.create-form label')
    expect(labels.length).toBeGreaterThanOrEqual(2)

    labels.forEach((label) => {
      const forId = label.getAttribute('for')
      expect(forId).toBeTruthy()
      expect(document.getElementById(forId!)).not.toBeNull()
    })

    wrapper.unmount()
  })

  it('marks the required supplier field with aria-required, but not the optional note field', async () => {
    const wrapper = await openForm()

    // Dialog teleports to document.body, so query there rather than the wrapper.
    const supplierLabel = Array.from(document.querySelectorAll('.create-form label')).find(
      (label) => label.textContent?.includes(i18n.global.t('orders.create.fields.supplier') as string),
    )!
    expect(supplierLabel.querySelector('span[aria-hidden="true"]')?.textContent).toBe(' *')

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.find('[role="combobox"]').attributes('aria-required')).toBe('true')

    const noteLabel = Array.from(document.querySelectorAll('.create-form label')).find((label) =>
      label.textContent?.includes(i18n.global.t('orders.create.fields.note') as string),
    )!
    expect(noteLabel.querySelector('span[aria-hidden="true"]')).toBeNull()
    expect(wrapper.findComponent({ name: 'Textarea' }).attributes('aria-required')).toBeUndefined()

    wrapper.unmount()
  })

  it('still submits the chosen supplier and note', async () => {
    const wrapper = await openForm()

    await wrapper
      .findComponent({ name: 'Select' })
      .vm.$emit('update:modelValue', 1)
    await wrapper.findComponent({ name: 'Textarea' }).vm.$emit('update:modelValue', 'Rush order')
    await flushPromises()

    await clickSave(wrapper)

    expect(postMock).toHaveBeenCalledWith(
      '/orders/',
      expect.objectContaining({ supplier_id: 1, note: 'Rush order' }),
    )
    expect(wrapper.emitted('created')).toBeTruthy()

    wrapper.unmount()
  })
})
