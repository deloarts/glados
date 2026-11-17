import { describe, it, expect, vi, afterEach } from 'vitest'
import { DOMWrapper, flushPromises, type VueWrapper } from '@vue/test-utils'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeMadeItemResponse } from '@/test-utils/factories'

const getMadeItemsMock = vi.fn<() => Promise<unknown>>()
vi.mock('../../api/getMadeItems', () => ({
  getMadeItems: () => getMadeItemsMock(),
}))

import MadeItemSelect from '../MadeItemSelect.vue'

import type { MadeItemResponse } from '../../types/madeItemsResponse'

function makeItem(id: number, name: string): MadeItemResponse {
  return makeMadeItemResponse({ id, article_name: name, part_number: `PN-${id}` })
}

const ALLOWED = makeItem(2, 'Allowed')
const REFUSED = makeItem(3, 'Refused')

const mounted: VueWrapper[] = []

async function mountSelect(props: Record<string, unknown> = {}) {
  const wrapper = mountWithApp(MadeItemSelect, {
    attachTo: document.body,
    props: { modelValue: null, ...props },
    global: { directives: { tooltip: Tooltip } },
  })
  mounted.push(wrapper)
  await flushPromises()
  return wrapper
}

// The overlay is teleported to the body, so its rows are looked up there.
async function openOverlay(wrapper: VueWrapper): Promise<void> {
  ;(wrapper.findComponent({ name: 'Select' }).vm as unknown as { show: () => void }).show()
  await flushPromises()
}

function optionRow(name: string): DOMWrapper<Element> {
  const row = [...document.querySelectorAll('[role="option"] .item-option-row')].find((el) =>
    el.textContent?.includes(name),
  )
  if (!row) throw new Error(`no option ${name}`)
  return new DOMWrapper(row)
}

describe('MadeItemSelect', () => {
  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
    getMadeItemsMock.mockReset()
  })

  it('searches the catalogue without a fetcher of its own', async () => {
    getMadeItemsMock.mockResolvedValue({ items: [ALLOWED], total: 1 })

    const wrapper = await mountSelect()

    expect(getMadeItemsMock).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'Select' }).props('options')).toEqual([ALLOWED])
  })

  it('offers what the given fetcher returns instead of the catalogue search', async () => {
    const fetchOptions = vi
      .fn<(query: string) => Promise<MadeItemResponse[]>>()
      .mockResolvedValue([ALLOWED, REFUSED])

    const wrapper = await mountSelect({ fetchOptions })

    expect(fetchOptions).toHaveBeenCalledWith('')
    expect(getMadeItemsMock).not.toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'Select' }).props('options')).toEqual([ALLOWED, REFUSED])
  })

  it('lists a refused option disabled and does not pick it, but picks an allowed one', async () => {
    const wrapper = await mountSelect({
      fetchOptions: async () => [ALLOWED, REFUSED],
      disabledReason: (item: MadeItemResponse) => (item.id === REFUSED.id ? 'Archived' : null),
    })
    await openOverlay(wrapper)

    const refused = optionRow('Refused')
    expect(refused.attributes('data-testid')).toBe('refused-option')
    expect(refused.element.closest('[role="option"]')?.getAttribute('aria-disabled')).toBe('true')
    await refused.trigger('mousedown')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await optionRow('Allowed').trigger('mousedown')
    expect(wrapper.emitted('update:modelValue')).toEqual([[ALLOWED]])
  })
})
